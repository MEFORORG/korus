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
         written. The fetch is one `ls-remote` and one `fetch`, because each is a round trip.
         A landed file is compared by its object id first, hashed here against the one `ls-tree`
         prints, and read with `git show` only when the ids differ. One `git show` per file cost
         208 s for 906 synthetic landed files. That was read with -Timings, added to korus
         e9814d4, on 2026-09-26.
      2. NOTHING PENDING, NOTHING TO DO. Exit 0 and say so.
      3. BUILD IN A TEMPORARY WORKTREE of `<Remote>/<Base>`, never in the clone's own working tree,
         which other sessions use.
      4. HOLD BACK WHAT WOULD LEAK (spec FR-028). Before anything is copied, every pending event is
         staged in one scratch directory and scanned ONCE by the record repository's own scanner,
         `scripts/publish/scan_forbidden.py` at Base, run as `python <scanner> --path <dir>`. An event
         it flags, or one whose text holds an email address, is HELD: it stays in the inbox, is
         never copied or rendered, still answers a local query, and is scanned again next run. Each
         event is scanned as its bytes AND as its decoded text, so a JSON escape hides nothing; one
         that is not UTF-8, or holds a NUL the scanner would skip as binary, is held unscanned.
         The hold fails closed, exit 2 with nothing filed or pushed: no scanner at Base, no python,
         a scanner exit other than 0 or 1, a crash, or an exit 1 whose hit lines do not all read,
         name staged events and agree with its own hit count. Held ids and counts are reported;
         the scanner's own lines never are, because its labels carry the token they matched. If
         every pending event is held, it is nothing pending. A held `supersede` or `retire`, and a
         standing branch that still carries a now-held event, are each warned about on stderr.
      5. FILE WHAT IS LEFT. Copy each filed event to `wiki/events/<yyyy>/<mm>/<id>.json`, never over
         an existing file. Render every page and the index from ALL events in the log, through the
         guard (`_render.ps1`). Append one line to `wiki/log.md`, which counts the held events.
      6. CONFLICTS are listed in `index.md` under `## Conflicts`, and counted in the log line: two
         or more live-candidate events on one key where neither supersedes the other.
      7. COMMIT AND FORCE-PUSH `wiki/compile`, then open a pull request for it unless one is open.
         The branch is always rebuilt from Base plus every filed event, so a re-run converges.
         The push carries `--force-with-lease`, which refuses a push that races another push. It
         does NOT merge two inboxes: a compile run against a second inbox rebuilds the branch
         without the first inbox's events. Those events stay in their inbox and return on its next
         compile, so nothing is lost, but the open pull request drops them. Run one compile job.
      8. IDEMPOTENT (FR-019). The commit carries a `Wiki-Content-Tree:` trailer: the tree before
         the log line. When `wiki/compile` already sits on Base with that trailer, the run adds
         nothing -- no commit, no push -- and only makes sure the pull request is open.

    The temporary worktree is removed in a `finally` block, whatever happened.

    -Timings prints, on stderr when the run ends, the seconds each phase took. Each line names a
    phase and a number, never an event, so it is safe to paste. It is off by default.

    -RebuildOnly regenerates `wiki/pages/` and `wiki/index.md` inside -RecordRepo from its
    `wiki/events/` alone: no inbox, no git (FR-012). It renders through the same code compile does,
    so its output must equal what compile committed.

    Exit codes:
        0  compiled, converged, rebuilt, or nothing pending
        1  refused: an id collision
        2  could not run: bad arguments, no record repository, a git or gh failure, or the leak
           hold could not scan (step 4)

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
    [switch] $Json,
    [switch] $Timings
)

$ErrorActionPreference = 'Stop'
# -Timings reads this clock. It starts before the libraries load, so their cost lands in `setup`.
$script:clock = [System.Diagnostics.Stopwatch]::StartNew()
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
        [hashtable] $Environment = @{},
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
    foreach ($k in $Environment.Keys) { $psi.Environment[$k] = [string]$Environment[$k] }
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

# -Timings: the seconds each phase took, printed to stderr when the run ends, whatever happened.
# Never on by default. Each line names a phase and a number, never an event or a path.
$script:lastMark = [timespan]::Zero
$script:phases = [System.Collections.Generic.List[object]]::new()

function Add-CompileTiming {
    <# Close the phase running since the last mark and record it under this name. #>
    param([Parameter(Mandatory)][string] $Phase)
    $now = $script:clock.Elapsed
    $script:phases.Add([pscustomobject]@{ phase = $Phase; seconds = [math]::Round(($now - $script:lastMark).TotalSeconds, 2) })
    $script:lastMark = $now
}

function Get-GitBlobId {
    <# The object id git gives these bytes as a blob: SHA-1, or SHA-256 when the id is 64 digits. #>
    param([Parameter(Mandatory)][AllowEmptyCollection()][byte[]] $Bytes, [Parameter(Mandatory)][int] $HexLength)
    $header = [System.Text.Encoding]::ASCII.GetBytes("blob $($Bytes.Length)`0")
    $algo = if ($HexLength -eq 64) { [System.Security.Cryptography.SHA256]::Create() } else { [System.Security.Cryptography.SHA1]::Create() }
    try {
        [void]$algo.TransformBlock($header, 0, $header.Length, $null, 0)
        [void]$algo.TransformFinalBlock($Bytes, 0, $Bytes.Length)
        return [System.Convert]::ToHexString($algo.Hash).ToLowerInvariant()
    } finally { $algo.Dispose() }
}

function ConvertTo-LfByte {
    <# The same bytes with each CRLF pair folded to LF. Latin-1 maps each byte to one character and back. #>
    param([Parameter(Mandatory)][AllowEmptyCollection()][byte[]] $Bytes)
    $latin = [System.Text.Encoding]::Latin1
    return , $latin.GetBytes($latin.GetString($Bytes).Replace("`r`n", "`n"))
}

function Get-NormalizedText {
    <# Line endings folded to LF and trailing whitespace dropped, for comparing one event two ways. #>
    param([string] $Text)
    return ($Text -replace "`r`n", "`n").TrimEnd()
}

# The record repository's own leak scanner, at Base. The vault's publish leak gate runs it over
# everything it holds, and a real customer name is a leak there in any folder (vault BACKLOG #1522).
$ScannerRel = 'scripts/publish/scan_forbidden.py'
# An address in the `local@domain.tld` shape, anywhere in the text. The scanner does not look for
# addresses. A `path@ref` citation has no dotted domain after the `@`, so it does not match.
$EmailRegex = [regex]::new('[\p{L}\p{N}._%+-]+@[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)*\.\p{L}{2,}',
    [System.Text.RegularExpressions.RegexOptions]::CultureInvariant)
# One hit line from the scanner in `--path` mode: two spaces, the path relative to the scan root,
# then `:<line>:`. Only the path is kept; the rest of the line carries the matched token.
$HitRegex = [regex]::new('^  (?<path>[^\s:][^:]*):\d+:', [System.Text.RegularExpressions.RegexOptions]::CultureInvariant)
# The scanner's closing count, `<n> hit(s).`. Required on exit 1 and checked against the lines read,
# so a hit list cut off before its end is never taken for the whole list.
# One line of `git ls-tree -r`: `<mode> blob <object id><TAB><path>`.
$LsTreeRegex = [regex]::new('^\d+ blob (?<blob>[0-9a-f]{40,64})\t(?<path>.+)$', [System.Text.RegularExpressions.RegexOptions]::CultureInvariant)
$HitCountRegex = [regex]::new('^(?<n>\d+) hit\(s\)\.', [System.Text.RegularExpressions.RegexOptions]::CultureInvariant)

function Get-WikiEventText {
    <#
    .SYNOPSIS
        Every property name and string value of one parsed event, decoded, one per line.
    .DESCRIPTION
        The file holds JSON, so a `\uXXXX` escape or a doubled backslash can hide a name from a scan
        of its bytes, while the page renders it decoded. This is the decoded text, for the same scan.

        Then every word again on its own line. The scanner skips a WHOLE LINE that matches its
        allowlist, so a name beside an allowlisted phrase would borrow its exemption; alone on its
        line it cannot. `write.ps1`'s `Get-ScanText` closes the same hole the same way.
    #>
    param($Node)
    $sb = [System.Text.StringBuilder]::new()
    $stack = [System.Collections.Generic.Stack[object]]::new()
    $stack.Push($Node)
    while ($stack.Count -gt 0) {
        $n = $stack.Pop()
        if ($null -eq $n) { continue }
        if ($n -is [string]) { [void]$sb.Append($n).Append("`n"); continue }
        if ($n -is [System.Management.Automation.PSCustomObject]) {
            foreach ($p in $n.PSObject.Properties) { [void]$sb.Append($p.Name).Append("`n"); $stack.Push($p.Value) }
            continue
        }
        if ($n -is [System.Collections.IEnumerable]) { foreach ($x in $n) { $stack.Push($x) }; continue }
        [void]$sb.Append([string]$n).Append("`n")
    }
    $whole = $sb.ToString()
    foreach ($word in ($whole -split '\s+')) { if ($word) { [void]$sb.Append($word).Append("`n") } }
    return $sb.ToString()
}

function Get-WikiLeakHold {
    <#
    .SYNOPSIS
        The ids of the pending events that must stay in the inbox: those the record repository's
        scanner flags, those whose text holds an email address, and those no scan can read.
        Fails closed with exit 2.
    .DESCRIPTION
        Each event is staged twice in one scratch directory: `<id>.json`, byte for byte what would be
        filed, and `<id>.decoded.txt`, its names and values with every JSON escape decoded. The
        scanner runs ONCE over the directory, which is removed before this returns.

        An event whose bytes, or whose decoded text, hold a NUL is held without a scan, and so is one
        that is not UTF-8: the scanner skips a file with a NUL as binary, so it would pass unread.

        NOTHING THE SCANNER PRINTS IS EVER REPEATED. Its hit lines and its category labels carry the
        token they matched, so every message here names an exit code or a count, never a line.
    #>
    param(
        [Parameter(Mandatory)][string] $Scanner,
        [Parameter(Mandatory)][string] $WorkDir,
        [Parameter(Mandatory)][System.Collections.Generic.Dictionary[string, byte[]]] $Bytes
    )
    if (-not (Test-Path -LiteralPath $Scanner -PathType Leaf)) {
        Stop-Compile 2 "the record repository has no leak scanner at $ScannerRel on its Base, so no event can be checked before it is filed. Nothing was filed or pushed."
    }
    $python = Find-Tool 'python'
    if (-not $python) { $python = Find-Tool 'python3' }
    if (-not $python) { Stop-Compile 2 'python is not on PATH, so the leak scanner cannot run. Nothing was filed or pushed.' }

    $held = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $strict = [System.Text.UTF8Encoding]::new($false, $true)
    $stage = Join-Path ([System.IO.Path]::GetTempPath()) ('korus-wiki-scan-' + [guid]::NewGuid().ToString('N').Substring(0, 12))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        $staged = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
        foreach ($id in $Bytes.Keys) {
            $b = $Bytes[$id]
            if ([System.Array]::IndexOf($b, [byte]0) -ge 0) { [void]$held.Add($id); continue }
            try { $text = $strict.GetString($b).TrimStart([char]0xFEFF) } catch { [void]$held.Add($id); continue }
            try { $plain = Get-WikiEventText (ConvertFrom-Json -InputObject $text -NoEnumerate -ErrorAction Stop) }
            catch { [void]$held.Add($id); continue }
            if ($plain.IndexOf([char]0) -ge 0) { [void]$held.Add($id); continue }
            [System.IO.File]::WriteAllBytes((Join-Path $stage "$id.json"), $b)
            [System.IO.File]::WriteAllText((Join-Path $stage "$id.decoded.txt"), $plain, [System.Text.UTF8Encoding]::new($false))
            $staged["$id.json"] = $id
            $staged["$id.decoded.txt"] = $id
            # In the raw text a two-character escape such as `\n` puts a letter before an `@` that
            # opens a line, so escapes are blanked first. An invisible format character inside an
            # address is dropped from the decoded text, so it cannot split the address in two.
            $rawForMail = [regex]::Replace($text, '\\[^u]', ' ')
            $plainForMail = [regex]::Replace($plain, '\p{Cf}', '')
            if ($EmailRegex.IsMatch($rawForMail) -or $EmailRegex.IsMatch($plainForMail)) { [void]$held.Add($id) }
        }
        Add-CompileTiming 'hold-stage'
        if ($staged.Count -gt 0) {
            # UTF-8 on the scanner's streams: under a cp1252 console a hit line with a non-ASCII
            # excerpt raises UnicodeEncodeError, and that crash exits 1 with part of the hit list.
            $scan = Invoke-Tool -Exe $python -Dir $WorkDir -Arguments @($Scanner, '--path', $stage) -AllowFail `
                -Environment @{ PYTHONIOENCODING = 'utf-8'; PYTHONDONTWRITEBYTECODE = '1' }
            $lines = @(($scan.Out + "`n" + $scan.Err) -split '\r?\n')
            if ($lines -match '^Traceback \(most recent call last\):') {
                Stop-Compile 2 "the leak scanner crashed (exit $($scan.Code)), so its hit list may be partial. Nothing was filed or pushed."
            }
            if ($scan.Code -eq 1) {
                $hits = 0
                $declared = -1
                foreach ($line in $lines) {
                    $count = $HitCountRegex.Match($line)
                    if ($count.Success) { $declared = [int]$count.Groups['n'].Value; continue }
                    # A hit line is indented and nothing else is. An indented line that does not read
                    # as a hit may be one in a shape this parser does not know, so it stops the run.
                    if ($line -notmatch '^\s+\S') { continue }
                    $m = $HitRegex.Match($line)
                    if (-not $m.Success) {
                        Stop-Compile 2 'a line of the leak scanner''s output could not be read as a hit, so what it flagged is unknown. Nothing was filed or pushed.'
                    }
                    $hits++
                    $path = $m.Groups['path'].Value
                    if (-not $staged.ContainsKey($path)) {
                        Stop-Compile 2 'the leak scanner reported a hit whose path names no staged event, so its output cannot be read. Nothing was filed or pushed.'
                    }
                    [void]$held.Add($staged[$path])
                }
                if ($hits -eq 0) {
                    Stop-Compile 2 'the leak scanner exited 1 but printed no hit path that could be read, so what it flagged is unknown. Nothing was filed or pushed.'
                }
                if ($declared -lt 0) {
                    Stop-Compile 2 'the leak scanner exited 1 without its closing hit count, so its hit list may be cut off. Nothing was filed or pushed.'
                }
                if ($declared -ne $hits) {
                    Stop-Compile 2 "the leak scanner counted $declared hit(s) and $hits could be read, so what it flagged is unknown. Nothing was filed or pushed."
                }
            } elseif ($scan.Code -ne 0) {
                Stop-Compile 2 "the leak scanner exited $($scan.Code) under '$python', which is neither clean (0) nor hits (1). Nothing was filed or pushed."
            }
            Add-CompileTiming 'hold-scan'
        }
    } finally {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $stage) {
            [Console]::Error.WriteLine("wiki compile: WARNING: could not remove the scan directory '$stage'. It holds copies of pending events; delete it.")
        }
    }
    $ids = [string[]]@($held)
    [System.Array]::Sort($ids, [System.StringComparer]::Ordinal)
    return , $ids
}

$report = [ordered]@{
    result    = $null
    deleted   = 0
    pending   = 0
    held      = 0
    held_ids  = [string[]]@()
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
    Add-CompileTiming 'setup'

    # ------------------------------------------------------------------------------------- fetch
    # ONE `ls-remote` and ONE `fetch`, because each is a round trip to the remote. With nothing to
    # file, four round trips took 19 of 27 seconds against the real record, read with -Timings
    # added to korus e9814d4, 2026-09-26. The `ls-remote` reads the default branch and whether the
    # standing branch exists.
    $ls = Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('ls-remote', '--symref', $Remote, 'HEAD', "refs/heads/$Branch")
    if ([string]::IsNullOrWhiteSpace($Base)) {
        if ($ls.Out -match '(?m)^ref: refs/heads/(\S+)\s+HEAD\s*$') { $Base = $Matches[1] }
        else { Stop-Compile 2 "could not read the default branch of '$Remote'; pass -Base." }
    }
    # The standing branch, if the remote has one, is fetched with Base so its message and parent can
    # be read. The lease is the value that fetch wrote: an `ls-remote` value could name a commit a
    # force-push replaced before the fetch, which this clone would then not hold.
    $hasBranch = $ls.Out -match ('(?m)^[0-9a-f]{40,64}\s+refs/heads/' + [regex]::Escape($Branch) + '\s*$')
    $refspecs = @("+refs/heads/${Base}:refs/remotes/$Remote/$Base")
    if ($hasBranch) { $refspecs += "+refs/heads/${Branch}:refs/remotes/$Remote/$Branch" }
    Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments (@('fetch', '--quiet', $Remote) + $refspecs) | Out-Null
    $baseSha = (Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('rev-parse', '--verify', "refs/remotes/$Remote/$Base^{commit}")).Out.Trim()
    $report.base = $baseSha
    $leased = ''
    if ($hasBranch) {
        $leased = (Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('rev-parse', '--verify', "refs/remotes/$Remote/$Branch^{commit}")).Out.Trim()
    }
    Add-CompileTiming 'fetch'

    # ------------------------------------------------------------- 1. clear what has landed
    # Ordinal, like the id pattern: a PowerShell hashtable ignores case, and would call an inbox file
    # named with an upper-case variant of a landed id a collision instead of a file to skip.
    $landed = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
    $landedBlob = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
    $tree = Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('ls-tree', '-r', $baseSha, '--', 'wiki/events')
    foreach ($line in ($tree.Out -split "`n")) {
        $m = $LsTreeRegex.Match($line.TrimEnd("`r"))
        if (-not $m.Success) { continue }
        $path = $m.Groups['path'].Value.Trim()
        if (-not $path.EndsWith('.json')) { continue }
        $id = [System.IO.Path]::GetFileNameWithoutExtension($path)
        if ($id -cmatch $script:WikiIdPattern) { $landed[$id] = $path; $landedBlob[$id] = $m.Groups['blob'].Value }
    }
    Add-CompileTiming 'landed-list'

    $inboxFiles = @()
    if (Test-Path -LiteralPath $inbox -PathType Container) {
        $inboxFiles = @([System.IO.Directory]::EnumerateFiles($inbox, '*.json', [System.IO.SearchOption]::TopDirectoryOnly))
    }
    $toDelete = [System.Collections.Generic.List[string]]::new()
    $collisions = [System.Collections.Generic.List[string]]::new()
    foreach ($f in $inboxFiles) {
        $id = [System.IO.Path]::GetFileNameWithoutExtension($f)
        if (-not $landed.ContainsKey($id)) { continue }
        # THE FAST PATH. Hash the inbox file as git would and compare with the object id `ls-tree`
        # already printed. Equal ids are equal bytes, so no `git show` runs. The second hash folds
        # CRLF to LF first. Git stores a text file that way under `core.autocrlf` or a `text`
        # attribute. A match on either passes the comparison below too, so the fast path never
        # deletes a file that comparison would keep. Step 1 of the header says why it exists.
        $inboxBytes = [System.IO.File]::ReadAllBytes($f)
        $want = $landedBlob[$id]
        if ((Get-GitBlobId -Bytes $inboxBytes -HexLength $want.Length) -ceq $want -or
            (Get-GitBlobId -Bytes (ConvertTo-LfByte $inboxBytes) -HexLength $want.Length) -ceq $want) {
            $toDelete.Add($f)
            continue
        }
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
    Add-CompileTiming 'clear-landed'

    # ------------------------------------------------------------------------ 2. what is pending
    $r = Read-WikiEventDir -Dir $inbox -Source inbox
    $pending = @($r.Events | Where-Object { -not $landed.ContainsKey([string]$_.id) })
    $report.skipped = $r.Skipped
    $report.pending = $pending.Count
    Add-CompileTiming 'read-inbox'
    if ($pending.Count -eq 0) {
        $report.result = 'nothing-pending'
        Write-Report "wiki compile: nothing pending. Removed $($toDelete.Count) landed inbox file(s); $($r.Skipped) inbox file(s) unreadable and skipped."
        return
    }

    # ------------------------------------------------------------------- 3. build in a worktree
    # THE WHOLE TREE, even when nothing will be filed. The scanner then runs beside every file it
    # could read at Base, with the repository's attributes applied. A checkout of its directory
    # alone was tried: it saved about 2 s and rested on how the record's scanner is written.
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('korus-wiki-compile-' + [guid]::NewGuid().ToString('N').Substring(0, 12))
    Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('worktree', 'add', '--quiet', '--detach', $tmp, $baseSha) | Out-Null
    # Recorded only once the add succeeded, so the cleanup never tries to remove what git refused.
    $script:tmp = $tmp
    Add-CompileTiming 'worktree-add'

    # ------------------------------------------------------------- 4. hold back what would leak
    # Read once, here: the bytes scanned are the bytes filed, so a file rewritten in the inbox after
    # the scan cannot reach the log unscanned. From the pending list itself, so what is counted and
    # what is copied are the same events: an inbox file that arrived after the listing is left for
    # the next run.
    $bytes = [System.Collections.Generic.Dictionary[string, byte[]]]::new([System.StringComparer]::Ordinal)
    foreach ($ev in $pending) {
        $bytes[[string]$ev.id] = [System.IO.File]::ReadAllBytes((Join-Path $inbox "$([string]$ev.id).json"))
    }
    $heldIds = Get-WikiLeakHold -Scanner (Join-Path $tmp $ScannerRel) -WorkDir $tmp -Bytes $bytes
    $heldSet = [System.Collections.Generic.HashSet[string]]::new([string[]]$heldIds, [System.StringComparer]::Ordinal)
    $filed = @($pending | Where-Object { -not $heldSet.Contains([string]$_.id) })
    $report.held = $heldIds.Count
    $report.held_ids = $heldIds
    $heldText = if ($heldIds.Count -gt 0) { " Held back in the inbox by the leak hold: $($heldIds -join ', ')." } else { '' }
    # A held marker cannot withdraw anything in the record: what it supersedes or retires stays live
    # on the pages until a marker without the flagged text lands. Said out loud, never absorbed.
    $heldMarkers = @($pending | Where-Object {
            $heldSet.Contains([string]$_.id) -and
            ([string]$_.type -cin $script:WikiMarkerTypes -or @($_.supersedes | Where-Object { $null -ne $_ }).Count -gt 0) } |
        ForEach-Object { [string]$_.id })
    if ($heldMarkers.Count -gt 0) {
        [Console]::Error.WriteLine("wiki compile: WARNING: $($heldMarkers.Count) held event(s) supersede or retire something: " +
            "$($heldMarkers -join ', '). What they withdraw stays live in the record until a clean marker is written.")
    }
    # A standing branch from an earlier run may carry an event the hold now flags. A rebuild below drops
    # it, though the old commit stays reachable from the pull request's history; with nothing to file
    # there is no rebuild, and the branch keeps it. Either way it is said out loud.
    $stale = 0
    if ($leased) {
        $stale = @((Invoke-Tool -Exe $git -Dir $RecordRepo -Arguments @('ls-tree', '-r', '--name-only', $leased, '--', 'wiki/events')).Out -split "`n" |
            ForEach-Object { [System.IO.Path]::GetFileNameWithoutExtension($_.Trim()) } | Where-Object { $heldSet.Contains($_) }).Count
    }
    if ($stale -gt 0 -and $filed.Count -eq 0) {
        [Console]::Error.WriteLine("wiki compile: WARNING: $Branch still carries $stale event(s) the leak hold now flags, " +
            'and nothing was filed to rebuild it. Close its pull request rather than land it.')
    } elseif ($stale -gt 0) {
        [Console]::Error.WriteLine("wiki compile: WARNING: $Branch carried $stale event(s) the leak hold now flags. " +
            "This run rebuilds it without them, but its earlier commit stays reachable from the pull request's history.")
    }
    Add-CompileTiming 'stale-check'
    if ($filed.Count -eq 0) {
        $report.result = 'nothing-pending'
        Write-Report ("wiki compile: nothing to file; all $($pending.Count) pending event(s) held back by the leak hold. " +
            "Removed $($toDelete.Count) landed inbox file(s); $($r.Skipped) inbox file(s) unreadable and skipped.$heldText")
        return
    }

    # ------------------------------------------------------------------ 5. file what is left
    foreach ($ev in $filed) {
        $id = [string]$ev.id
        $dir = Get-WikiLogDir -RecordRepo $tmp -Utc $ev._utc
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        $dest = Join-Path $dir "$id.json"
        if (Test-Path -LiteralPath $dest) {
            Stop-Compile 1 "id collision: $id is already filed in the log; an event is never overwritten."
        }
        # CreateNew as well, so even a file that appeared since the test above is never overwritten.
        $fs = [System.IO.FileStream]::new($dest, [System.IO.FileMode]::CreateNew)
        try { $fs.Write($bytes[$id], 0, $bytes[$id].Length) } finally { $fs.Dispose() }
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
    Add-CompileTiming 'render'

    Invoke-Tool -Exe $git -Dir $tmp -Arguments @('add', '--all', '--', 'wiki') | Out-Null
    $contentTree = (Invoke-Tool -Exe $git -Dir $tmp -Arguments @('write-tree')).Out.Trim()
    $report.content_tree = $contentTree
    $title = "wiki: compile $($filed.Count) events"

    # --------------------------------------------------------------------- 8. already converged?
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
        $line = "- ${now}: $($filed.Count) event(s) added, $($set.Pages) page(s) written, $($set.Conflicts.Count) conflict(s), $($heldIds.Count) held back`n"
        $enc = [System.Text.UTF8Encoding]::new($false)
        if (-not (Test-Path -LiteralPath $logPath)) {
            [System.IO.File]::WriteAllText($logPath, "# Wiki compile log`n`nOne line per compile, appended by ``scripts/wiki/compile.ps1``.`n`n", $enc)
        } else {
            $existing = [System.IO.File]::ReadAllText($logPath)
            if ($existing.Length -gt 0 -and -not $existing.EndsWith("`n")) { [System.IO.File]::AppendAllText($logPath, "`n", $enc) }
        }
        [System.IO.File]::AppendAllText($logPath, $line, $enc)
        Invoke-Tool -Exe $git -Dir $tmp -Arguments @('add', '--', 'wiki/log.md') | Out-Null

        # ------------------------------------------------------------------------ 7. commit, push
        $body = "Folds $($filed.Count) inbox event(s) into wiki/events and rebuilds $($set.Pages) page(s) and the index. " +
            "$($set.Conflicts.Count) conflict(s) listed in wiki/index.md. $($heldIds.Count) event(s) held back in the inbox by " +
            "the leak hold. Generated by scripts/wiki/compile.ps1; never merged by it."
        Invoke-Tool -Exe $git -Dir $tmp -Arguments @('commit', '--quiet', '-m', $title, '-m', $body,
            '-m', "Wiki-Content-Tree: $contentTree") | Out-Null
        $report.head = (Invoke-Tool -Exe $git -Dir $tmp -Arguments @('rev-parse', 'HEAD')).Out.Trim()
        $report.tree = (Invoke-Tool -Exe $git -Dir $tmp -Arguments @('rev-parse', 'HEAD^{tree}')).Out.Trim()
        Invoke-Tool -Exe $git -Dir $tmp -Arguments @('push', '--quiet', "--force-with-lease=refs/heads/${Branch}:$leased",
            $Remote, "HEAD:refs/heads/$Branch") | Out-Null
        $report.added = $filed.Count
        $report.result = 'compiled'
    }
    Add-CompileTiming 'commit-push'

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
        Add-CompileTiming 'pull-request'
    }

    $what = if ($report.result -ceq 'converged') { "already current at $($report.head); nothing added" }
    else { "pushed $Branch at $($report.head)" }
    $prText = if ($NoPr) { 'no pull request (-NoPr)' } else { "pull request $($report.pr)" }
    Write-Report ("wiki compile: $($pending.Count) event(s) pending, $($heldIds.Count) held back, $($set.Pages) page(s), " +
        "$($set.Conflicts.Count) conflict(s); $what; $prText. Removed $($toDelete.Count) landed inbox file(s); " +
        "$($r.Skipped) unreadable and skipped.$heldText")
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
    # The phase a stop cut short is closed here under its own name. Otherwise its time would be
    # counted as the worktree's removal and point a reader at the wrong phase.
    Add-CompileTiming $(if ($exitCode -ne 0) { 'until-stop' } else { 'report' })
    if ($script:tmp -and $script:git) {
        $rm = Invoke-Tool -Exe $script:git -Dir $script:recordDir -Arguments @('worktree', 'remove', '--force', $script:tmp) -AllowFail
        if ($rm.Code -ne 0 -or (Test-Path -LiteralPath $script:tmp)) {
            [Console]::Error.WriteLine("wiki compile: could not remove the temporary worktree '$($script:tmp)': $($rm.Err.Trim())")
            if ($exitCode -eq 0) { $exitCode = 2 }
        }
        Add-CompileTiming 'worktree-remove'
    }
    if ($Timings) {
        Add-CompileTiming 'finish'
        foreach ($p in $script:phases) {
            [Console]::Error.WriteLine([string]::Format([cultureinfo]::InvariantCulture, 'wiki compile: timing {0} {1:0.00} s', $p.phase, $p.seconds))
        }
        [Console]::Error.WriteLine([string]::Format([cultureinfo]::InvariantCulture, 'wiki compile: timing total {0:0.00} s', $script:clock.Elapsed.TotalSeconds))
    }
}
exit $exitCode
