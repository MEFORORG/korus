#Requires -Version 7.3
<#
.SYNOPSIS
    Fold the fleet wiki's inbox into the record repository: the log, the pages, the index and one
    log line, carried by ONE pull request on the standing branch `wiki/compile`. It never merges.

.DESCRIPTION
    The only writer of `wiki/events/`, `wiki/pages/`, `wiki/index.md` and `wiki/log.md` in the
    record repository (spec FR-018). It runs in this order:

      1. FETCH, THEN CLEAR WHAT HAS LANDED. Read the log at `<Remote>/<Base>` with `git ls-tree`,
         never from a working tree, and delete each inbox file whose id is already there. This is
         the ONLY place an inbox file is deleted, so a file leaves the inbox only after the pull
         request carrying it has merged (spec, Edge Cases). An inbox file whose id is in the landed
         log with DIFFERENT content is an id collision: the run stops, and nothing is deleted or
         written.
      2. NOTHING PENDING, NOTHING TO DO. Exit 0 and say so.
      3. BUILD IN A TEMPORARY WORKTREE of `<Remote>/<Base>`, never in the clone's own working tree,
         which other sessions use. Copy each pending event to `wiki/events/<yyyy>/<mm>/<id>.json`,
         never over an existing file. Render every page and the index from ALL events, through the
         guard (`_render.ps1`). Append one line to `wiki/log.md`.
      4. CONFLICTS are listed in `index.md` under `## Conflicts`, and counted in the log line: two
         or more live-candidate events on one key where neither supersedes the other.
      5. COMMIT AND FORCE-PUSH `wiki/compile`, then open a pull request for it unless one is open.
         The branch is always rebuilt from Base plus every pending event, so a re-run converges.
         The push carries `--force-with-lease`, which refuses a push that races another push. It
         does NOT merge two inboxes: a compile run against a second inbox rebuilds the branch
         without the first inbox's events. Those events stay in their inbox and return on its next
         compile, so nothing is lost, but the open pull request drops them. Run one compile job.
      6. IDEMPOTENT (FR-019). The commit carries a `Wiki-Content-Tree:` trailer: the tree before
         the log line. When `wiki/compile` already sits on Base with that trailer, the run adds
         nothing -- no commit, no push -- and only makes sure the pull request is open.

    The temporary worktree is removed in a `finally` block, whatever happened.

    -RebuildOnly regenerates `wiki/pages/` and `wiki/index.md` inside -RecordRepo from its
    `wiki/events/` alone: no inbox, no git (FR-012). It renders through the same code compile does,
    so its output must equal what compile committed.

    Exit codes:
        0  compiled, converged, rebuilt, or nothing pending
        1  refused: an id collision
        2  could not run: bad arguments, no record repository, a git or gh failure

.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/compile.ps1 -RecordRepo ../MessageFoundry-vault
.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/compile.ps1 -RecordRepo ./checkout -RebuildOnly
#>
[CmdletBinding()]
param(
    [string] $StateRoot,
    [string] $RecordRepo,
    [string] $Remote = 'origin',
    [string] $Base,
    [switch] $NoPr,
    [switch] $RebuildOnly,
    [switch] $Json
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_event.ps1')
. (Join-Path $PSScriptRoot '_guard.ps1')
. (Join-Path $PSScriptRoot '_render.ps1')

$Branch = 'wiki/compile'

class WikiCompileStop : System.Exception {
    [int] $Code
    WikiCompileStop([int] $code, [string] $message) : base($message) { $this.Code = $code }
}

function Stop-Compile {
    param([int] $Code, [string] $Message)
    throw [WikiCompileStop]::new($Code, $Message)
}

function Find-Tool {
    param([string] $Name)
    $cmd = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    return $null
}

function Invoke-Tool {
    <#
    .SYNOPSIS
        Run git or gh with an argument LIST, capturing both streams as UTF-8.
    .DESCRIPTION
        A ProcessStartInfo rather than `& git`, so no argument is re-parsed by a shell and native
        stderr never turns into a PowerShell error record under ErrorActionPreference Stop.
    #>
    param(
        [Parameter(Mandatory)][string] $Exe,
        [Parameter(Mandatory)][string] $Dir,
        [Parameter(Mandatory)][string[]] $Arguments,
        [switch] $AllowFail
    )
    $psi = [System.Diagnostics.ProcessStartInfo]::new($Exe)
    foreach ($a in $Arguments) { $psi.ArgumentList.Add($a) }
    $psi.WorkingDirectory = $Dir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $psi.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
    $psi.Environment['GIT_TERMINAL_PROMPT'] = '0'
    $p = [System.Diagnostics.Process]::Start($psi)
    $out = $p.StandardOutput.ReadToEndAsync()
    $err = $p.StandardError.ReadToEndAsync()
    $p.WaitForExit()
    $res = [pscustomobject]@{ Code = $p.ExitCode; Out = $out.Result; Err = $err.Result }
    if (-not $AllowFail -and $res.Code -ne 0) {
        $name = [System.IO.Path]::GetFileNameWithoutExtension($Exe)
        Stop-Compile 2 "$name $($Arguments -join ' ') failed (exit $($res.Code)): $($res.Err.Trim())"
    }
    return $res
}

function Get-NormalizedText {
    <# Line endings folded to LF and trailing whitespace dropped, for comparing one event two ways. #>
    param([string] $Text)
    return ($Text -replace "`r`n", "`n").TrimEnd()
}

$report = [ordered]@{
    result    = $null
    deleted   = 0
    pending   = 0
    skipped   = 0
    log_skipped = 0
    added     = 0
    pages     = 0
    conflicts = 0
    branch    = $Branch
    base      = $null
    head      = $null
    tree      = $null
    content_tree = $null
    pr        = $null
}

function Write-LogSkipWarning {
    <# A log file that no longer reads is said out loud, in compile and in -RebuildOnly alike. #>
    param([int] $Count)
    if ($Count -gt 0) {
        [Console]::Error.WriteLine("wiki compile: WARNING: $Count file(s) in the log could not be read and were left out of the pages. An event they hid may show as live.")
    }
}

function Write-Report {
    param([string] $Line)
    if ($Json) { ConvertTo-Json -InputObject $report -Depth 4 }
    else { Write-Output $Line }
}

# The run is a function so that an early `return` leaves the function and still reaches the
# `finally` below and the one `exit` at the bottom. A bare `return` at script scope would end the
# script with whatever exit code pwsh chose, not the one reported.
$script:tmp = $null
$script:git = $null
$script:recordDir = $null

function Invoke-WikiCompile {
    if ([string]::IsNullOrWhiteSpace($RecordRepo)) { Stop-Compile 2 '-RecordRepo is required: a clone of the private record repository.' }
    $RecordRepo = Resolve-WikiDir $RecordRepo
    if (-not (Test-Path -LiteralPath $RecordRepo -PathType Container)) {
        Stop-Compile 2 "the record repository '$RecordRepo' does not exist."
    }
    $script:recordDir = $RecordRepo

    # -------------------------------------------------------------------------------- rebuild only
    if ($RebuildOnly) {
        $eventsRoot = Get-WikiEventsRoot -RecordRepo $RecordRepo
        if (-not (Test-Path -LiteralPath $eventsRoot -PathType Container)) {
            Stop-Compile 2 "there is no wiki/events directory under '$RecordRepo' to rebuild from."
        }
        $r = Read-WikiEventDir -Dir $eventsRoot -Source log -Recurse
        Write-LogSkipWarning $r.Skipped
        $set = Build-WikiPageSet -Events @($r.Events)
        Write-WikiPageSet -WikiDir (Join-Path $RecordRepo 'wiki') -PageSet $set
        $report.result = 'rebuilt'
        $report.log_skipped = $r.Skipped
        $report.pages = $set.Pages
        $report.conflicts = $set.Conflicts.Count
        Write-Report "wiki compile: rebuilt $($set.Pages) page(s) and the index from $($r.Events.Count) event(s); $($set.Conflicts.Count) conflict(s); $($r.Skipped) file(s) unreadable and skipped."
        return
    }

    foreach ($pair in @(@('Remote', $Remote), @('Base', $Base))) {
        if ($pair[1] -and ($pair[1].StartsWith('-') -or $pair[1] -match '\s')) {
            Stop-Compile 2 "-$($pair[0]) '$($pair[1])' is not a git name."
        }
    }
    $script:git = Find-Tool 'git'
    $git = $script:git
    if (-not $git) { Stop-Compile 2 'git is not on PATH.' }
    # The top level, not the path given: `ls-tree` reads paths relative to the directory it runs in,
    # so a subdirectory would find no landed event and report every landed id as a collision.
    $top = Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('rev-parse', '--show-toplevel') -AllowFail
    if ($top.Code -ne 0 -or -not $top.Out.Trim()) { Stop-Compile 2 "'$RecordRepo' is not inside a git working tree." }
    $RecordRepo = Resolve-WikiDir $top.Out.Trim()
    $script:recordDir = $RecordRepo

    if ([string]::IsNullOrWhiteSpace($StateRoot)) {
        try {
            . (Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'coord') '_common.ps1')
            $StateRoot = Get-CcxStateRoot
        } catch {
            Stop-Compile 2 "the inbox is not reachable: no -StateRoot, and $($_.Exception.Message)"
        }
    }
    $StateRoot = Resolve-WikiDir $StateRoot
    if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
        Stop-Compile 2 "the inbox is not reachable: state root '$StateRoot' does not exist."
    }
    $inbox = Get-WikiInboxDir -StateRoot $StateRoot

    # ------------------------------------------------------------------------------------- fetch
    if ([string]::IsNullOrWhiteSpace($Base)) {
        $sym = Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('ls-remote', '--symref', $Remote, 'HEAD')
        if ($sym.Out -match '(?m)^ref: refs/heads/(\S+)\s+HEAD') { $Base = $Matches[1] }
        else { Stop-Compile 2 "could not read the default branch of '$Remote'; pass -Base." }
    }
    Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('fetch', '--quiet', $Remote,
        "+refs/heads/${Base}:refs/remotes/$Remote/$Base") | Out-Null
    $baseSha = (Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('rev-parse', '--verify', "refs/remotes/$Remote/$Base^{commit}")).Out.Trim()
    $report.base = $baseSha

    # The standing branch, if the remote has one. Fetched so its message and parent can be read, and
    # the lease is the value that fetch wrote: an `ls-remote` value could name a commit a force-push
    # replaced before the fetch, which this clone would then not hold.
    $leased = ''
    $ls = Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('ls-remote', $Remote, "refs/heads/$Branch")
    if ($ls.Out -match '(?m)^[0-9a-f]{40,64}\s+refs/heads/') {
        Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('fetch', '--quiet', $Remote,
            "+refs/heads/${Branch}:refs/remotes/$Remote/$Branch") | Out-Null
        $leased = (Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('rev-parse', '--verify', "refs/remotes/$Remote/$Branch^{commit}")).Out.Trim()
    }

    # ------------------------------------------------------------- 1. clear what has landed
    # Ordinal, like the id pattern: a PowerShell hashtable ignores case, and would call an inbox file
    # named with an upper-case variant of a landed id a collision instead of a file to skip.
    $landed = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
    $tree = Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('ls-tree', '-r', '--name-only', $baseSha, '--', 'wiki/events')
    foreach ($line in ($tree.Out -split "`n")) {
        $path = $line.Trim()
        if (-not $path.EndsWith('.json')) { continue }
        $id = [System.IO.Path]::GetFileNameWithoutExtension($path)
        if ($id -cmatch $script:WikiIdPattern) { $landed[$id] = $path }
    }

    $inboxFiles = @()
    if (Test-Path -LiteralPath $inbox -PathType Container) {
        $inboxFiles = @([System.IO.Directory]::EnumerateFiles($inbox, '*.json', [System.IO.SearchOption]::TopDirectoryOnly))
    }
    $toDelete = [System.Collections.Generic.List[string]]::new()
    $collisions = [System.Collections.Generic.List[string]]::new()
    foreach ($f in $inboxFiles) {
        $id = [System.IO.Path]::GetFileNameWithoutExtension($f)
        if (-not $landed.ContainsKey($id)) { continue }
        $landedText = (Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('show', "${baseSha}:$($landed[$id])")).Out
        $inboxText = [System.IO.File]::ReadAllText($f)
        if ((Get-NormalizedText $landedText) -ceq (Get-NormalizedText $inboxText)) { $toDelete.Add($f) }
        else { $collisions.Add($id) }
    }
    # Checked before ANY file is deleted, so a collision leaves the inbox exactly as it was.
    if ($collisions.Count -gt 0) {
        Stop-Compile 1 ("id collision: the landed log already holds $($collisions -join ', ') with different content. " +
            'An event is never overwritten; nothing was deleted or written. Rename neither file; a person decides.')
    }
    foreach ($f in $toDelete) { Remove-Item -LiteralPath $f -Force }
    $report.deleted = $toDelete.Count

    # ------------------------------------------------------------------------ 2. what is pending
    $r = Read-WikiEventDir -Dir $inbox -Source inbox
    $pending = @($r.Events | Where-Object { -not $landed.ContainsKey([string]$_.id) })
    $report.skipped = $r.Skipped
    $report.pending = $pending.Count
    if ($pending.Count -eq 0) {
        $report.result = 'nothing-pending'
        Write-Report "wiki compile: nothing pending. Removed $($toDelete.Count) landed inbox file(s); $($r.Skipped) inbox file(s) unreadable and skipped."
        return
    }

    # ------------------------------------------------------------------- 3. build in a worktree
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('korus-wiki-compile-' + [guid]::NewGuid().ToString('N').Substring(0, 12))
    Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('worktree', 'add', '--quiet', '--detach', $tmp, $baseSha) | Out-Null
    # Recorded only once the add succeeded, so the cleanup never tries to remove what git refused.
    $script:tmp = $tmp

    # From the pending list itself, so what is counted and what is copied are the same events: an
    # inbox file that arrived after the listing above is left for the next run.
    foreach ($ev in $pending) {
        $id = [string]$ev.id
        $dir = Get-WikiLogDir -RecordRepo $tmp -Utc $ev._utc
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        $dest = Join-Path $dir "$id.json"
        if (Test-Path -LiteralPath $dest) {
            Stop-Compile 1 "id collision: $id is already filed in the log; an event is never overwritten."
        }
        # CreateNew as well, so even a file that appeared since the test above is never overwritten.
        $bytes = [System.IO.File]::ReadAllBytes((Join-Path $inbox "$id.json"))
        $fs = [System.IO.FileStream]::new($dest, [System.IO.FileMode]::CreateNew)
        try { $fs.Write($bytes, 0, $bytes.Length) } finally { $fs.Dispose() }
    }

    $all = Read-WikiEventDir -Dir (Get-WikiEventsRoot -RecordRepo $tmp) -Source log -Recurse
    # A landed file that no longer reads is reported, never absorbed: were it a `supersede` or
    # `retire` marker, the event it hid would render as live again.
    $report.log_skipped = $all.Skipped
    Write-LogSkipWarning $all.Skipped
    $set = Build-WikiPageSet -Events @($all.Events)
    $wikiDir = Join-Path $tmp 'wiki'
    Write-WikiPageSet -WikiDir $wikiDir -PageSet $set
    $report.pages = $set.Pages
    $report.conflicts = $set.Conflicts.Count

    Invoke-Tool -Exe $git -Dir $tmp -Arguments @('add', '--all', '--', 'wiki') | Out-Null
    $contentTree = (Invoke-Tool -Exe $git -Dir $tmp -Arguments @('write-tree')).Out.Trim()
    $report.content_tree = $contentTree
    $title = "wiki: compile $($pending.Count) events"

    # --------------------------------------------------------------------- 6. already converged?
    $converged = $false
    if ($leased) {
        $parent = Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('rev-parse', '--verify', '--quiet', "$leased^1") -AllowFail
        $msg = (Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('log', '-1', '--format=%B', $leased)).Out
        if ($parent.Code -eq 0 -and $parent.Out.Trim() -ceq $baseSha -and
            $msg -cmatch "(?m)^Wiki-Content-Tree: $contentTree\s*$") {
            $converged = $true
        }
    }

    if ($converged) {
        $report.result = 'converged'
        $report.head = $leased
        $report.tree = (Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('rev-parse', "$leased^{tree}")).Out.Trim()
    } else {
        # ------------------------------------------------------------------- the one log line
        $logPath = Join-Path $wikiDir 'log.md'
        $now = (Get-WikiClock).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", [cultureinfo]::InvariantCulture)
        $line = "- ${now}: $($pending.Count) event(s) added, $($set.Pages) page(s) written, $($set.Conflicts.Count) conflict(s)`n"
        $enc = [System.Text.UTF8Encoding]::new($false)
        if (-not (Test-Path -LiteralPath $logPath)) {
            [System.IO.File]::WriteAllText($logPath, "# Wiki compile log`n`nOne line per compile, appended by ``scripts/wiki/compile.ps1``.`n`n", $enc)
        } else {
            $existing = [System.IO.File]::ReadAllText($logPath)
            if ($existing.Length -gt 0 -and -not $existing.EndsWith("`n")) { [System.IO.File]::AppendAllText($logPath, "`n", $enc) }
        }
        [System.IO.File]::AppendAllText($logPath, $line, $enc)
        Invoke-Tool -Exe $git -Dir $tmp -Arguments @('add', '--', 'wiki/log.md') | Out-Null

        # ------------------------------------------------------------------------ 5. commit, push
        $body = "Folds $($pending.Count) inbox event(s) into wiki/events and rebuilds $($set.Pages) page(s) and the index. " +
            "$($set.Conflicts.Count) conflict(s) listed in wiki/index.md. Generated by scripts/wiki/compile.ps1; never merged by it."
        Invoke-Tool -Exe $git -Dir $tmp -Arguments @('commit', '--quiet', '-m', $title, '-m', $body,
            '-m', "Wiki-Content-Tree: $contentTree") | Out-Null
        $report.head = (Invoke-Tool -Exe $git -Dir $tmp -Arguments @('rev-parse', 'HEAD')).Out.Trim()
        $report.tree = (Invoke-Tool -Exe $git -Dir $tmp -Arguments @('rev-parse', 'HEAD^{tree}')).Out.Trim()
        Invoke-Tool -Exe $git -Dir $tmp -Arguments @('push', '--quiet', "--force-with-lease=refs/heads/${Branch}:$leased",
            $Remote, "HEAD:refs/heads/$Branch") | Out-Null
        $report.added = $pending.Count
        $report.result = 'compiled'
    }

    # ------------------------------------------------------------------------ the pull request
    if (-not $NoPr) {
        $gh = Find-Tool 'gh'
        if (-not $gh) { Stop-Compile 2 "gh is not on PATH, so no pull request was opened. $Branch is pushed at $($report.head)." }
        # Named from -Remote's URL, so gh cannot pick a different default repository in a clone with
        # several remotes. An https URL names its host. An ssh URL names owner and repository only,
        # because its host may be an ssh-config alias such as `github.com-work` that gh cannot reach;
        # gh then uses its default host. A URL that does not parse leaves gh to its own resolution.
        $repoArgs = @()
        $remoteUrl = (Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('remote', 'get-url', $Remote)).Out.Trim()
        if ($remoteUrl -match '^https?://(?:[^@/]+@)?([a-zA-Z0-9][^/:]*)(?::\d+)?/([^/]+)/([^/]+?)(?:\.git)?/?$') {
            $repoArgs = @('--repo', "$($Matches[1])/$($Matches[2])/$($Matches[3])")
        } elseif ($remoteUrl -match '^(?:ssh://)?[^@/]+@[^/:]+(?::\d+)?[:/]([^/]+)/([^/]+?)(?:\.git)?/?$') {
            $repoArgs = @('--repo', "$($Matches[1])/$($Matches[2])")
        }
        $open = Invoke-Tool -Exe $gh -Dir $RecordRepo -Arguments (@('pr', 'list') + $repoArgs +
            @('--head', $Branch, '--state', 'open', '--json', 'url', '--jq', '.[0].url'))
        $url = $open.Out.Trim()
        if (-not $url) {
            $prBody = "Generated by ``scripts/wiki/compile.ps1``. It folds the inbox into ``wiki/events`` and rebuilds " +
                "``wiki/pages`` and ``wiki/index.md`` from the log alone. The compile job never merges; the Lander lands it."
            $created = Invoke-Tool -Exe $gh -Dir $RecordRepo -Arguments (@('pr', 'create') + $repoArgs +
                @('--base', $Base, '--head', $Branch, '--title', $title, '--body', $prBody))
            $url = ($created.Out.Trim() -split "`n")[-1].Trim()
        }
        $report.pr = $url
    }

    $what = if ($report.result -ceq 'converged') { "already current at $($report.head); nothing added" }
    else { "pushed $Branch at $($report.head)" }
    $prText = if ($NoPr) { 'no pull request (-NoPr)' } else { "pull request $($report.pr)" }
    Write-Report ("wiki compile: $($pending.Count) event(s) pending, $($set.Pages) page(s), $($set.Conflicts.Count) conflict(s); " +
        "$what; $prText. Removed $($toDelete.Count) landed inbox file(s); $($r.Skipped) unreadable and skipped.")
}

$exitCode = 0
try {
    Invoke-WikiCompile
} catch [WikiCompileStop] {
    [Console]::Error.WriteLine("wiki compile: $($_.Exception.Message)")
    $exitCode = $_.Exception.Code
} catch {
    [Console]::Error.WriteLine("wiki compile: could not run: $($_.Exception.Message)")
    $exitCode = 2
} finally {
    if ($script:tmp -and $script:git) {
        $rm = Invoke-Tool -Exe $script:git -Dir $script:recordDir -Arguments @('worktree', 'remove', '--force', $script:tmp) -AllowFail
        if ($rm.Code -ne 0 -or (Test-Path -LiteralPath $script:tmp)) {
            [Console]::Error.WriteLine("wiki compile: could not remove the temporary worktree '$($script:tmp)': $($rm.Err.Trim())")
            if ($exitCode -eq 0) { $exitCode = 2 }
        }
    }
}
exit $exitCode
