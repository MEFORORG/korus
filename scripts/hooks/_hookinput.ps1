<#
.SYNOPSIS
    Shared by the harness hooks: read the hook input, and find the session's own directory in it.

.DESCRIPTION
    WHY THIS EXISTS. The desktop app starts a worktree session's CLI with
    `--project-config-root <primary checkout>`. Measured 2026-10-12 in a fixture launched with that
    flag (korus#220 records it): a hook runs with its working directory, `$env:CLAUDE_PROJECT_DIR`
    and `git rev-parse --show-toplevel` all naming the PRIMARY. Only the `cwd` field of the JSON on
    stdin names the worktree the session is in.

    Seen live 2026-10-13: this repository's announce hook told a session in a worktree to announce
    itself as "<primary> (main)". Every hook that asks git, `$PWD` or CLAUDE_PROJECT_DIR where it is
    gets the same wrong answer.

    THE CWD IS WHERE THE SESSION IS NOW, NOT WHERE IT STARTED, SO IT IS CHECKED BEFORE IT IS USED.
    A session that runs `cd` moves its `cwd`, and a hook that trusted it answered for wherever the
    session went: a sibling's mail box and steering note, or another repository entirely. The korus#223
    review measured each. So Resolve-CcxHookSession accepts the `cwd` only under two rules:

      * SAME CLONE. The `cwd` must sit in a checkout whose git common directory is the one the hook
        started in. A `cwd` in another repository, in no repository, or under a `.git` file that names
        no real git directory is refused, and the hook stays where it started and says so.
      * FIRST SEEN WINS. The first accepted `cwd` for a session id is pinned under the common
        directory, in ccx-session-root/. Later events answer for the pinned worktree, so a `cd` to a
        sibling does not move them. A SessionStart that is not a compaction (startup, resume, clear)
        pins again, because its `cwd` is where the session was launched.

    The cost of the pin: a session that moves into another worktree on purpose, mid-session, keeps
    answering for the one it started in until its next SessionStart. docs/WORKTREES.md already says to
    start a session in its worktree rather than move into one.

    No git call is made. The common directory is read from `.git` and its `commondir` file, which is
    what git itself reads, so the steering hook can afford this before every tool call.

    So a hook reads its input with Read-CcxHookInput and then does ONE of two things:

      * Enter-CcxHookCwd moves the hook into the session's directory, so every later git call, every
        `$PWD` read and every child script answers for the session. Use it where the hook asks git.
      * Get-CcxHookWorktree returns the worktree root. Use it where the hook only needs a path, such
        as a file under `.claude/`.

    NO CWD IS NOT A FAULT. A payload with no `cwd` (an older harness, a hand-run test) leaves the
    hook where it started, which is the old behaviour. A payload that NAMES a cwd the hook cannot use
    is a fault, and both functions return the reason so the caller can say it aloud. Falling back in
    silence is the defect this file exists to fix.

    Dot-source it. It defines functions only and has no side effect on load.
#>

function Read-CcxHookInput {
    <#
      .SYNOPSIS
        The hook input on stdin as text, or '' when there is none.

      .DESCRIPTION
        Read as UTF-8 BYTES, not through [Console]::In. That reader decodes with the console code
        page, which mangles a non-ASCII `cwd` and sends the hook quietly back to its own directory.

        Guarded on IsInputRedirected, so a hook run by hand from a terminal does not wait for input.

        AND BOUNDED IN TIME. IsInputRedirected is True from an agent shell with no pipe at all
        (announce-session.ps1 measured it), and a caller that leaves stdin open would hang an
        unbounded read. The harness writes its JSON and closes the pipe, so it never meets the bound.
        A read that does meet it says so on stderr, so "no input" and "input still open" differ.
    #>
    param([int] $TimeoutMs = 2000)
    try {
        if (-not [Console]::IsInputRedirected) { return '' }
        $reader = [System.IO.StreamReader]::new([Console]::OpenStandardInput(), [System.Text.UTF8Encoding]::new($false))
        $read = $reader.ReadToEndAsync()
        if ($read.Wait($TimeoutMs)) { return $read.Result }
        [Console]::Error.WriteLine("[hook-input] stdin was still open after $TimeoutMs ms, so the hook read no input and answers for $($PWD.Path).")
        return ''
    }
    catch { return '' }
}

function Get-CcxHookPayloadCwd {
    <#
      .SYNOPSIS
        What the hook input says about its directory: Named, Cwd and Reason.

      .DESCRIPTION
        Named is $false when the input names no cwd at all, which is not a fault. Cwd is the resolved
        directory when it exists. Reason says why a named cwd could not be used.
    #>
    param([string] $Text)
    $out = [pscustomobject]@{ Named = $false; Cwd = $null; Reason = '' }
    if ([string]::IsNullOrWhiteSpace($Text)) { return $out }
    try { $payload = $Text | ConvertFrom-Json -ErrorAction Stop } catch { return $out }
    if ($null -eq $payload -or $payload -isnot [pscustomobject] -or -not $payload.PSObject.Properties['cwd']) { return $out }
    $dir = [string]$payload.cwd
    if ([string]::IsNullOrWhiteSpace($dir)) { return $out }
    $out.Named = $true
    try {
        if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
            $out.Reason = "the hook input names cwd $dir, which does not exist"
            return $out
        }
        $out.Cwd = (Resolve-Path -LiteralPath $dir -ErrorAction Stop).ProviderPath
    }
    catch { $out.Reason = "the hook input names cwd $dir, which could not be resolved ($($_.Exception.Message))" }
    return $out
}

function ConvertTo-CcxHookPathKey {
    # One spelling per directory, for comparing two paths. Case folds on Windows only.
    param([string] $Path)
    if (-not $Path) { return '' }
    try { $full = [System.IO.Path]::GetFullPath($Path) } catch { return '' }
    $k = ($full -replace '\\', '/').TrimEnd('/')
    if ($IsWindows) { $k = $k.ToLowerInvariant() }
    return $k
}

function Get-CcxGitLocation {
    <#
      .SYNOPSIS
        The checkout a path sits in: Root and CommonDir, or $null when it is in none.

      .DESCRIPTION
        Walks up from the nearest existing directory to the first `.git`. A DIRECTORY there is a
        primary checkout, and it is its own common directory. A FILE is a linked worktree: its
        `gitdir:` line names the worktree's git directory, and that directory's `commondir` file
        names the shared one. A `.git` that names no real git directory (empty, or pointing at
        nothing) answers $null rather than walking past it.

        The path need not exist, so a file a Write is about to create still resolves.
    #>
    param([string] $Path)
    if (-not $Path) { return $null }
    try { $at = [System.IO.Path]::GetFullPath($Path) } catch { return $null }
    while (-not (Test-Path -LiteralPath $at -PathType Container)) {
        $parent = Split-Path -Parent $at
        if (-not $parent -or $parent -eq $at) { return $null }
        $at = $parent
    }
    while ($at) {
        $dotgit = Join-Path $at '.git'
        if (Test-Path -LiteralPath $dotgit -PathType Container) {
            if (-not (Test-Path -LiteralPath (Join-Path $dotgit 'HEAD') -PathType Leaf)) { return $null }
            return [pscustomobject]@{ Root = $at; CommonDir = (ConvertTo-CcxHookPathKey $dotgit) }
        }
        if (Test-Path -LiteralPath $dotgit -PathType Leaf) {
            try {
                $line = [string]@(Get-Content -LiteralPath $dotgit -TotalCount 1 -ErrorAction Stop)[0]
                if ($line -notmatch '^gitdir:\s*(.+?)\s*$') { return $null }
                $gd = $Matches[1]
                if (-not [System.IO.Path]::IsPathRooted($gd)) { $gd = Join-Path $at $gd }
                $gd = [System.IO.Path]::GetFullPath($gd)
                if (-not (Test-Path -LiteralPath (Join-Path $gd 'HEAD') -PathType Leaf)) { return $null }
                $common = $gd
                $cf = Join-Path $gd 'commondir'
                if (Test-Path -LiteralPath $cf -PathType Leaf) {
                    $c = ([string](Get-Content -LiteralPath $cf -Raw -ErrorAction Stop)).Trim()
                    if ($c) {
                        if (-not [System.IO.Path]::IsPathRooted($c)) { $c = Join-Path $gd $c }
                        $common = [System.IO.Path]::GetFullPath($c)
                    }
                }
                if (-not (Test-Path -LiteralPath $common -PathType Container)) { return $null }
                return [pscustomobject]@{ Root = $at; CommonDir = (ConvertTo-CcxHookPathKey $common) }
            }
            catch { return $null }
        }
        $parent = Split-Path -Parent $at
        if (-not $parent -or $parent -eq $at) { break }
        $at = $parent
    }
    return $null
}

function Resolve-CcxHookSession {
    <#
      .SYNOPSIS
        Where this session is: Named, Dir, Root, Source and Reason.

      .DESCRIPTION
        Dir is the directory to stand in and Root the worktree it sits in. Both are $null when the
        hook should stay where it started. Source is 'pin', 'cwd' or 'start'. Reason is set when the
        input named a cwd this function refused, and says why. The file header gives the two rules.

        StartDir is the directory the hook would answer for without its input: its working directory,
        or CLAUDE_PROJECT_DIR for the steering hook. A StartDir in no checkout gives nothing to check
        the cwd against, so the hook stays put in silence, as it did before it read any cwd. That is
        the user-scope case: an unrelated project with no repository.
    #>
    param([string] $Text, [string] $StartDir = $PWD.Path)
    $out = [pscustomobject]@{ Named = $false; Dir = $null; Root = $null; Source = 'start'; Reason = '' }
    $p = Get-CcxHookPayloadCwd -Text $Text
    $out.Named = $p.Named
    $start = Get-CcxGitLocation -Path $StartDir
    if (-not $start) { return $out }

    $sid = ''; $hookEvent = ''; $source = ''
    try {
        $payload = $Text | ConvertFrom-Json -ErrorAction Stop
        if ($payload -is [pscustomobject]) {
            $sid = [string]$payload.session_id
            $hookEvent = [string]$payload.hook_event_name
            $source = [string]$payload.source
        }
    }
    catch { }
    $pinFile = $null
    if ($sid) {
        $key = $sid -replace '[^A-Za-z0-9._-]', ''
        if ($key.Length -gt 72) { $key = $key.Substring(0, 72) }
        if ($key -ne $sid -or -not $key) {
            # Two session ids must never share a pin.
            $sha = [System.Security.Cryptography.SHA256]::Create()
            $key += '-' + (-join ($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($sid))[0..3] | ForEach-Object { $_.ToString('x2') }))
            $sha.Dispose()
        }
        $pinFile = Join-Path (Join-Path $start.CommonDir 'ccx-session-root') "$key.txt"
    }

    $repin = ($hookEvent -eq 'SessionStart' -and $source -ne 'compact')
    if ($pinFile -and -not $repin -and (Test-Path -LiteralPath $pinFile -PathType Leaf)) {
        try {
            $pinned = ([string](Get-Content -LiteralPath $pinFile -Raw -ErrorAction Stop)).Trim()
            $loc = Get-CcxGitLocation -Path $pinned
            if ($loc -and $loc.CommonDir -eq $start.CommonDir -and (ConvertTo-CcxHookPathKey $loc.Root) -eq (ConvertTo-CcxHookPathKey $pinned)) {
                $out.Dir = $loc.Root; $out.Root = $loc.Root; $out.Source = 'pin'
                return $out
            }
        }
        catch { }   # an unreadable or stale pin is not this session's answer; the cwd decides below
    }

    # A launch whose cwd is refused leaves no pin behind. An older run's pin would otherwise answer, in
    # silence, for every later event of this session.
    if ($repin -and $pinFile) { Remove-Item -LiteralPath $pinFile -Force -ErrorAction SilentlyContinue }

    if (-not $p.Named) { return $out }
    if (-not $p.Cwd) { $out.Reason = $p.Reason; return $out }
    $loc = Get-CcxGitLocation -Path $p.Cwd
    if (-not $loc) {
        $out.Reason = "the hook input names cwd $($p.Cwd), which is inside no checkout"
        return $out
    }
    if ($loc.CommonDir -ne $start.CommonDir) {
        $out.Reason = "the hook input names cwd $($p.Cwd), which is in a different repository from $StartDir"
        return $out
    }
    $out.Dir = $p.Cwd; $out.Root = $loc.Root; $out.Source = 'cwd'
    if ($pinFile) {
        try {
            $pinDir = Split-Path $pinFile
            New-Item -ItemType Directory -Force -Path $pinDir -ErrorAction Stop | Out-Null
            Set-Content -LiteralPath $pinFile -Value $loc.Root -Encoding UTF8 -ErrorAction Stop
            # A pin is written about once per session, so pruning here is rare. Thirty days is far
            # past any session's life.
            Get-ChildItem -LiteralPath $pinDir -Filter '*.txt' -File -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
                Remove-Item -Force -ErrorAction SilentlyContinue
        }
        catch { }   # no pin means a later `cd` is followed, not that this answer is wrong
    }
    return $out
}

function Get-CcxHookWorktree {
    <#
      .SYNOPSIS
        The worktree root the session is in: Named, Root and Reason. Root is $null to stay put.
    #>
    param([string] $Text, [string] $StartDir = $PWD.Path)
    $r = Resolve-CcxHookSession -Text $Text -StartDir $StartDir
    return [pscustomobject]@{ Named = $r.Named; Root = $r.Root; Reason = $r.Reason }
}

function Enter-CcxHookCwd {
    <#
      .SYNOPSIS
        Move into the session's directory. Returns '' or the reason it could not.

      .DESCRIPTION
        Moves into the `cwd` itself when the input's `cwd` decided, not a root walked up from it, so
        git resolves the worktree exactly as it would in the session. Into the pinned root when the
        pin decided. A hook that keys anything on `$PWD` then keys it on the session.

        PowerShell starts native children in the current location, so a git call or a child pwsh
        launched after this answers for the session too.

        '' means the hook is where it should be, or the input named no cwd and the hook stays put.
    #>
    param([string] $Text, [string] $StartDir = $PWD.Path)
    $r = Resolve-CcxHookSession -Text $Text -StartDir $StartDir
    if (-not $r.Dir) { return $r.Reason }
    try { Set-Location -LiteralPath $r.Dir -ErrorAction Stop }
    catch { return "the hook could not enter $($r.Dir) ($($_.Exception.Message))" }
    return ''
}
