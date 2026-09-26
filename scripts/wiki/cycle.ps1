#Requires -Version 7.3
<#
.SYNOPSIS
    One run of the fleet wiki's scheduled maintenance: import on its day, then compile, then lint.
    Plain PowerShell and git. It makes zero model calls and needs no app to be open.

.DESCRIPTION
    An operating-system scheduler runs this script (Owner ruling 2026-09-26). It replaced a Claude
    Code scheduled task that ran only while one desktop app was open (Owner ruling 2026-09-23).
    `register-cycle-task.ps1` registers it with Windows Task Scheduler. Any other scheduler that
    can start `pwsh` runs it the same way.

    LINT'S PROMOTION STEP IS NOT PART OF THIS CYCLE. Drafting a playbook pull request needs a
    model, so it stays a Claude Code job or a manual step. The cycle writes lint's report and stops.

    ONE RUN DOES THIS, IN ORDER:

      1. CHECK EVERY INPUT BEFORE TOUCHING ANYTHING. Each named directory must exist. Both
         checkouts must be the top of a git work tree, on a DETACHED head, with no tracked change.
         A failure here exits 2, and nothing has moved.
      2. TAKE THE LOCK, `<StateRoot>/wiki-cycle/lock`, created only if absent. A lock younger than
         two hours means another cycle runs: exit 2. An older one is dead, because the registered
         task is stopped after one hour. The run removes it, says so in the log, and carries on.
      3. MOVE -KorusCheckout TO `origin/main` after a fetch, then run the wiki scripts FROM IT.
         So a run always uses the scripts `main` holds, never what some working checkout has.
      4. MOVE -ReaderRepo TO `origin/main` after a fetch. Import and lint read the compiled log
         from it.
      5. IMPORT, on -ImportDay (local time), or whenever -Import is given. -NoImport skips it.
         `-RecordRepo <ReaderRepo>` goes to the import ONLY when `<ReaderRepo>/wiki/events` exists.
         Before the first compile lands there is no log, and import.ps1 refuses a named record
         repository that has none.
      6. COMPILE: `compile.ps1 -StateRoot -RecordRepo -Json`. It opens its own pull request.
      7. LINT: `lint.ps1 -StateRoot -RecordRepo <ReaderRepo> -EvidenceRepo -Out
         <LintOut>/lint-<yyyy-MM-dd>.md`, dated by the UTC day the run started.
      8. APPEND ONE JSON LINE to `<StateRoot>/wiki-cycle/log-<yyyy-MM>.jsonl`, by UTC month.

    A failed step does not stop the steps after it. Each step's exit code is recorded as returned,
    with its key counts: the import counts, compile's result, added count and pull request, and
    lint's totals. A step that runs past 15 minutes is killed with its process tree and recorded
    as timed out.

    WHY A DETACHED HEAD IS REQUIRED. A dedicated scheduled checkout sits detached. A checkout on a
    branch is somebody's working tree, and moving it would pull the ground out from under a session.
    So the cycle refuses one rather than guess. To prepare a checkout, run
    `git -C <dir> switch --detach origin/main` once.

    WHAT COUNTS AS A LOCAL CHANGE. A tracked file that differs from HEAD, staged or not, and a HEAD
    holding commits that `origin/main` does not. The cycle refuses either and moves nothing.
    Untracked files do not block it: a detached checkout never deletes one, and git itself refuses
    to overwrite one.

    THE CYCLE'S OWN COPY LAGS ONE RUN. The task runs the `cycle.ps1` in -KorusCheckout, as it stood
    when the run started. The run then moves that checkout, so the wiki scripts are current at once
    and a change to this file takes effect on the next run.

    IT NEVER MERGES, AND IT PUSHES ONLY THROUGH compile.ps1. It writes only under -StateRoot and
    -LintOut, and moves only the two checkouts named above.

    -WhatIf runs the checks of step 1, reads the lock, and prints the plan. It fetches nothing,
    moves nothing, takes no lock and writes no log line. It shows the scripts as the korus checkout
    holds them now, before a run would move it.

    Exit codes:
        0  every step ran, whatever it found
        1  a step returned an error, or timed out. The other steps still ran.
        2  the cycle could not run: a bad or missing argument or path, a checkout on a branch or
           with local changes, a fetch or checkout that failed, a missing wiki script, or the lock
           held by a live cycle

.PARAMETER Store
    The memory stores to import. Under `pwsh -File` a list arrives as ONE string, so an entry that
    is not itself a directory is split on commas. Needed only when the import runs.

.PARAMETER EvidenceRepo
    Git repositories lint resolves evidence in. Split on commas the same way as -Store.

.EXAMPLE
    pwsh -NoProfile -File <korus>/scripts/wiki/cycle.ps1 -KorusCheckout <korus> -StateRoot <coord> `
      -RecordRepo <vault> -ReaderRepo <vault reader> -Store <store1>,<store2> `
      -EvidenceRepo <engine>,<korus>,<vault> -LintOut <lint dir> -WhatIf
#>
[CmdletBinding()]
param(
    [string] $KorusCheckout,
    [string] $StateRoot,
    [string] $RecordRepo,
    [string] $ReaderRepo,
    [string[]] $Store,
    [string[]] $EvidenceRepo,
    [string] $LintOut,
    # A string rather than [DayOfWeek], so a bad value exits 2 as documented instead of 1.
    [string] $ImportDay = 'Sunday',
    [switch] $Import,
    [switch] $NoImport,
    [switch] $WhatIf,
    [switch] $Json
)

$ErrorActionPreference = 'Stop'

# Two hours is double the task's one-hour limit, so a live run never looks stale.
$StaleLockHours = 2
$StepTimeoutMinutes = 15
$Remote = 'origin'
$Base = 'main'

class WikiCycleStop : System.Exception {
    [int] $Code
    WikiCycleStop([int] $code, [string] $message) : base($message) { $this.Code = $code }
}

function Stop-Cycle {
    param([string] $Message)
    throw [WikiCycleStop]::new(2, $Message)
}

function Get-UtcStamp {
    param([datetime] $When)
    return $When.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ', [cultureinfo]::InvariantCulture)
}

function Resolve-CycleDir {
    <# An absolute path, resolved against the PowerShell location, with no trailing separator. #>
    param([string] $Path)
    $full = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    $full = [System.IO.Path]::GetFullPath($full)
    $root = [System.IO.Path]::GetPathRoot($full)
    if ($full.Length -gt $root.Length) { $full = $full.TrimEnd('\', '/') }
    return $full
}

function Split-DirList {
    <# `pwsh -File` hands `-Store a,b` over as one string, so an entry that is not a directory is split on commas. #>
    param([string[]] $Entries)
    $list = [System.Collections.Generic.List[string]]::new()
    foreach ($entry in @($Entries)) {
        if ([string]::IsNullOrWhiteSpace($entry)) { continue }
        $parts = if (Test-Path -LiteralPath $entry -PathType Container) { @($entry) } else { @($entry -split ',') }
        foreach ($p in $parts) {
            if ([string]::IsNullOrWhiteSpace($p)) { continue }
            $list.Add((Resolve-CycleDir $p.Trim()))
        }
    }
    return , $list.ToArray()
}

function Invoke-Proc {
    <#
    .SYNOPSIS
        Run a program with an argument LIST and capture both streams, with an optional time limit.
    .DESCRIPTION
        A ProcessStartInfo, so no argument is re-parsed by a shell and native stderr never turns
        into a PowerShell error. Both streams are read asynchronously, so a full pipe cannot hang
        the child. A child past its limit is killed with its whole process tree.
    #>
    param(
        [Parameter(Mandatory)][string] $Exe,
        [Parameter(Mandatory)][string] $Dir,
        [Parameter(Mandatory)][string[]] $Arguments,
        [int] $TimeoutMs = -1
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
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    $p = [System.Diagnostics.Process]::Start($psi)
    $out = $p.StandardOutput.ReadToEndAsync()
    $err = $p.StandardError.ReadToEndAsync()
    $timedOut = $false
    if (-not $p.WaitForExit($TimeoutMs)) {
        $timedOut = $true
        try { $p.Kill($true) } catch [System.InvalidOperationException] { $null = $_ }
        $null = $p.WaitForExit(30000)
    }
    $p.WaitForExit()
    return [pscustomobject]@{
        Code     = if ($timedOut) { $null } else { $p.ExitCode }
        TimedOut = $timedOut
        Out      = $out.GetAwaiter().GetResult()
        Err      = $err.GetAwaiter().GetResult()
        Seconds  = [math]::Round($clock.Elapsed.TotalSeconds, 1)
    }
}

function Invoke-Git {
    param([string] $Dir, [string[]] $Arguments)
    return Invoke-Proc -Exe $script:git -Dir $Dir -Arguments $Arguments -TimeoutMs 300000
}

function Get-Tail {
    <# The last few stderr lines of a failed step, for the log. The log stays on this machine. #>
    param([string] $Text)
    $lines = @(($Text -split "`r?`n") | Where-Object { $_.Trim() })
    $tail = ($lines | Select-Object -Last 5) -join ' | '
    if ($tail.Length -gt 600) { $tail = $tail.Substring($tail.Length - 600) }
    return $tail
}

function Test-Checkout {
    <#
    .SYNOPSIS
        Read-only checks on a checkout the cycle will move. Returns a record; a refusal sets .Problem.
    #>
    param([string] $Label, [string] $Dir)
    $rec = [ordered]@{ path = $Dir; head = $null; detached = $null; clean = $null; problem = $null }
    if (-not (Test-Path -LiteralPath $Dir -PathType Container)) {
        $rec.problem = "$Label '$Dir' does not exist."
        return $rec
    }
    $inside = Invoke-Git $Dir @('rev-parse', '--is-inside-work-tree')
    if ($inside.Code -ne 0 -or $inside.Out.Trim() -ne 'true') {
        $rec.problem = "$Label '$Dir' is not a git work tree."
        return $rec
    }
    # An empty prefix means the directory IS the top of the work tree. Comparing path strings would
    # trip over a short 8.3 name or a slash direction; asking git does not.
    $prefix = Invoke-Git $Dir @('rev-parse', '--show-prefix')
    if ($prefix.Code -ne 0 -or $prefix.Out.Trim()) {
        $rec.problem = "$Label '$Dir' is inside a git work tree but is not its top. Name the checkout itself."
        return $rec
    }
    $head = Invoke-Git $Dir @('rev-parse', '--verify', 'HEAD^{commit}')
    if ($head.Code -ne 0) {
        $rec.problem = "$Label '$Dir' has no commit at HEAD."
        return $rec
    }
    $rec.head = $head.Out.Trim()
    $sym = Invoke-Git $Dir @('symbolic-ref', '-q', 'HEAD')
    $rec.detached = ($sym.Code -ne 0)
    if (-not $rec.detached) {
        $rec.problem = "$Label '$Dir' is on branch $($sym.Out.Trim()), so it is somebody's working tree. The cycle moves only a detached checkout. Prepare it once with: git -C `"$Dir`" switch --detach $Remote/$Base"
        return $rec
    }
    $status = Invoke-Git $Dir @('status', '--porcelain', '--untracked-files=no')
    if ($status.Code -ne 0) {
        $rec.problem = "$Label '$Dir': git status failed: $(Get-Tail $status.Err)"
        return $rec
    }
    $changed = @(($status.Out -split "`r?`n") | Where-Object { $_.Trim() })
    $rec.clean = ($changed.Count -eq 0)
    if (-not $rec.clean) {
        $rec.problem = "$Label '$Dir' has $($changed.Count) tracked file(s) with local changes. The cycle will not move it. Commit them elsewhere or discard them by hand."
    }
    return $rec
}

function Update-Checkout {
    <# Fetch, refuse to strand local commits, then move to detached origin/main. #>
    param([string] $Label, [System.Collections.IDictionary] $Rec)
    $dir = $Rec.path
    $fetch = Invoke-Git $dir @('fetch', '--quiet', $Remote)
    if ($fetch.Code -ne 0) { Stop-Cycle "$Label '$dir': git fetch $Remote failed: $(Get-Tail $fetch.Err)" }
    $target = Invoke-Git $dir @('rev-parse', '--verify', "$Remote/$Base^{commit}")
    if ($target.Code -ne 0) { Stop-Cycle "$Label '$dir' has no $Remote/$Base after the fetch." }
    $sha = $target.Out.Trim()
    $anc = Invoke-Git $dir @('merge-base', '--is-ancestor', 'HEAD', $sha)
    if ($anc.Code -eq 1) {
        Stop-Cycle "$Label '$dir' holds commits that $Remote/$Base does not. Moving it would strand them, so the cycle will not."
    } elseif ($anc.Code -ne 0) {
        Stop-Cycle "$Label '$dir': git merge-base failed: $(Get-Tail $anc.Err)"
    }
    if ($Rec.head -ne $sha) {
        $co = Invoke-Git $dir @('checkout', '--quiet', '--detach', $sha)
        if ($co.Code -ne 0) { Stop-Cycle "$Label '$dir': git checkout of $Remote/$Base failed: $(Get-Tail $co.Err)" }
    }
    $Rec.before = $Rec.head
    $Rec.head = $sha
    return $sha
}

function Invoke-Step {
    <# Run one wiki script from the korus checkout in its own pwsh process. #>
    param([string] $Name, [string] $Script, [string[]] $Arguments)
    $r = Invoke-Proc -Exe $script:pwsh -Dir $script:korusDir -TimeoutMs ($StepTimeoutMinutes * 60000) `
        -Arguments (@('-NoProfile', '-NonInteractive', '-File', $Script) + $Arguments)
    $rec = [ordered]@{ exit = $r.Code; seconds = $r.Seconds }
    if ($r.TimedOut) {
        $rec.timed_out = $true
        $script:stepFailed = $true
        [Console]::Error.WriteLine("wiki cycle: $Name ran past $StepTimeoutMinutes minutes and was killed.")
    } elseif ($r.Code -ne 0) {
        $script:stepFailed = $true
        $rec.stderr_tail = Get-Tail $r.Err
        [Console]::Error.WriteLine("wiki cycle: $Name exited $($r.Code): $($rec.stderr_tail)")
    }
    return [pscustomobject]@{ Record = $rec; Out = $r.Out }
}

function ConvertFrom-StepJson {
    <# A step's -Json output, or $null when it printed none, as a script that stopped early does. #>
    param([string] $Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $null }
    try { return ConvertFrom-Json -InputObject $Text -ErrorAction Stop }
    catch { return $null }
}

function Read-LintTotals {
    <# The `| class | count |` rows under `## Totals` in lint's Markdown report. #>
    param([string] $Path)
    $totals = [ordered]@{}
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $inTotals = $false
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match '^## ') { $inTotals = ($line -ceq '## Totals'); continue }
        if ($inTotals -and $line -match '^\| ([a-z-]+) \| (\d+) \|$') { $totals[$Matches[1]] = [int]$Matches[2] }
    }
    if ($totals.Count -eq 0) { return $null }
    return $totals
}

# ------------------------------------------------------------------------------------ state
$started = [datetime]::UtcNow
$log = [ordered]@{
    start      = Get-UtcStamp $started
    end        = $null
    exit       = $null
    outcome    = $null
    problem    = $null
    korus_sha  = $null
    reader_sha = $null
    lock       = $null
    import     = $null
    compile    = $null
    lint       = $null
}
$plan = [ordered]@{ what_if = $true; would_exit = $null; problems = @() }
$script:stepFailed = $false
$script:lockPath = $null
$script:lockTaken = $false
$script:logDir = $null
$script:korusDir = $null
$script:git = $null
$script:pwsh = (Get-Process -Id $PID).Path

function Invoke-WikiCycle {
    # -------------------------------------------------------------------------------- arguments
    foreach ($pair in @(@('KorusCheckout', $KorusCheckout), @('StateRoot', $StateRoot), @('RecordRepo', $RecordRepo),
            @('ReaderRepo', $ReaderRepo), @('LintOut', $LintOut))) {
        if ([string]::IsNullOrWhiteSpace($pair[1])) { Stop-Cycle "-$($pair[0]) is required." }
    }
    $script:StateRoot = Resolve-CycleDir $StateRoot
    if (-not (Test-Path -LiteralPath $script:StateRoot -PathType Container)) { Stop-Cycle "state root '$($script:StateRoot)' does not exist." }
    $script:logDir = Join-Path $script:StateRoot 'wiki-cycle'

    if ($Import -and $NoImport) { Stop-Cycle '-Import and -NoImport cannot both be given.' }
    $day = [System.DayOfWeek]::Sunday
    if (-not [System.Enum]::TryParse([System.DayOfWeek], $ImportDay, $true, [ref]$day) -or
        -not [System.Enum]::IsDefined([System.DayOfWeek], $day) -or $ImportDay -match '^\s*\d') {
        Stop-Cycle "-ImportDay '$ImportDay' is not a day of the week."
    }
    $today = [datetime]::Now.DayOfWeek
    $importDue = $false
    $importWhy = $null
    if ($NoImport) { $importWhy = '-NoImport' }
    elseif ($Import) { $importDue = $true; $importWhy = '-Import' }
    elseif ($today -eq $day) { $importDue = $true; $importWhy = "import day ($day)" }
    else { $importWhy = "not the import day: today is $today, import runs on $day" }

    $korus = Resolve-CycleDir $KorusCheckout
    $record = Resolve-CycleDir $RecordRepo
    $reader = Resolve-CycleDir $ReaderRepo
    $lintDir = Resolve-CycleDir $LintOut
    $stores = Split-DirList $Store
    $evidence = Split-DirList $EvidenceRepo
    if (-not (Test-Path -LiteralPath $record -PathType Container)) { Stop-Cycle "record repository '$record' does not exist." }
    if (Test-Path -LiteralPath $lintDir -PathType Leaf) { Stop-Cycle "-LintOut '$lintDir' is a file, not a directory." }
    if ($importDue -and $stores.Count -eq 0) { Stop-Cycle "the import is due ($importWhy) and no -Store was given. Name the stores, or pass -NoImport." }
    foreach ($s in $stores) { if (-not (Test-Path -LiteralPath $s -PathType Container)) { Stop-Cycle "store '$s' does not exist." } }
    foreach ($e in $evidence) { if (-not (Test-Path -LiteralPath $e -PathType Container)) { Stop-Cycle "evidence repository '$e' does not exist." } }

    $gitCmd = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $gitCmd) { Stop-Cycle 'git is not on PATH.' }
    $script:git = $gitCmd.Source
    $script:korusDir = $korus

    # -------------------------------------------------------------------------------- checkouts
    # Both are checked before either moves, so a refusal leaves both where they were.
    $korusRec = Test-Checkout 'the korus checkout' $korus
    $readerRec = Test-Checkout 'the reader checkout' $reader
    $lintFile = Join-Path $lintDir ("lint-{0}.md" -f $started.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture))
    $script:lockPath = Join-Path $script:logDir 'lock'

    if ($WhatIf) {
        $plan.korus = $korusRec
        $plan.reader = $readerRec
        $problems = [System.Collections.Generic.List[string]]::new()
        foreach ($rec in @($korusRec, $readerRec)) { if ($rec.problem) { $problems.Add($rec.problem) } }
        $lockState = 'free'
        if (Test-Path -LiteralPath $script:lockPath -PathType Leaf) {
            $age = ([datetime]::UtcNow - (Get-Item -LiteralPath $script:lockPath).LastWriteTimeUtc).TotalHours
            if ($age -ge $StaleLockHours) { $lockState = "stale ($([math]::Round($age, 1)) h old); a run would clear it" }
            else { $lockState = "held ($([math]::Round($age, 1)) h old)"; $problems.Add("the lock '$($script:lockPath)' is held by a live cycle.") }
        }
        $plan.lock = $lockState
        $eventsDir = Join-Path (Join-Path $reader 'wiki') 'events'
        $wiki = Join-Path (Join-Path $korus 'scripts') 'wiki'
        $importArgs = @('-Store', ($stores -join ','), '-StateRoot', $script:StateRoot, '-Json')
        $passRecord = Test-Path -LiteralPath $eventsDir -PathType Container
        if ($passRecord) { $importArgs += @('-RecordRepo', $reader) }
        $lintArgs = @('-StateRoot', $script:StateRoot, '-RecordRepo', $reader)
        if ($evidence.Count -gt 0) { $lintArgs += @('-EvidenceRepo', ($evidence -join ',')) }
        $lintArgs += @('-Out', $lintFile)
        $plan.import = [ordered]@{ due = $importDue; reason = $importWhy; record_repo_passed = $passRecord
            note = 'record_repo_passed is read from the reader as it stands now; a run reads it again after the move.' }
        $steps = [System.Collections.Generic.List[object]]::new()
        if ($importDue) { $steps.Add([ordered]@{ name = 'import'; script = (Join-Path $wiki 'import.ps1'); arguments = $importArgs }) }
        $steps.Add([ordered]@{ name = 'compile'; script = (Join-Path $wiki 'compile.ps1'); arguments = @('-StateRoot', $script:StateRoot, '-RecordRepo', $record, '-Json') })
        $steps.Add([ordered]@{ name = 'lint'; script = (Join-Path $wiki 'lint.ps1'); arguments = $lintArgs })
        $plan.steps = $steps.ToArray()
        $plan.log = Join-Path $script:logDir ("log-{0}.jsonl" -f $started.ToString('yyyy-MM', [cultureinfo]::InvariantCulture))
        $plan.problems = @($problems)
        $plan.would_exit = if ($problems.Count -gt 0) { 2 } else { 0 }
        return
    }

    foreach ($rec in @($korusRec, $readerRec)) { if ($rec.problem) { Stop-Cycle $rec.problem } }

    # -------------------------------------------------------------------------------- lock
    $null = New-Item -ItemType Directory -Force -Path $script:logDir
    $holder = "pid $PID on $([System.Environment]::MachineName), started $($log.start)"
    for ($attempt = 0; $attempt -lt 2 -and -not $script:lockTaken; $attempt++) {
        try {
            $fs = [System.IO.File]::Open($script:lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
            try {
                $bytes = [System.Text.Encoding]::ASCII.GetBytes($holder)
                $fs.Write($bytes, 0, $bytes.Length)
            } finally { $fs.Dispose() }
            $script:lockTaken = $true
        } catch [System.IO.IOException] {
            # The holder may have released it a moment ago. Then the next attempt takes it.
            if (-not (Test-Path -LiteralPath $script:lockPath -PathType Leaf)) { continue }
            $item = Get-Item -LiteralPath $script:lockPath
            $age = ([datetime]::UtcNow - $item.LastWriteTimeUtc).TotalHours
            $who = 'unreadable'
            try { $who = ([System.IO.File]::ReadAllText($script:lockPath)).Trim() } catch [System.IO.IOException] { $null = $_ }
            if ($age -lt $StaleLockHours -or $attempt -gt 0) {
                $log.lock = [ordered]@{ state = 'held'; age_hours = [math]::Round($age, 2); holder = $who }
                Stop-Cycle "another cycle holds the lock '$($script:lockPath)' ($who, $([math]::Round($age, 2)) h old)."
            }
            Remove-Item -LiteralPath $script:lockPath -Force
            $log.lock = [ordered]@{ state = 'stale lock cleared'; age_hours = [math]::Round($age, 2); holder = $who }
            [Console]::Error.WriteLine("wiki cycle: cleared a stale lock, $([math]::Round($age, 2)) h old, held by: $who")
        }
    }
    if (-not $script:lockTaken) { Stop-Cycle "could not take the lock '$($script:lockPath)'." }
    if (-not $log.lock) { $log.lock = [ordered]@{ state = 'taken' } }

    # -------------------------------------------------------------------------------- move the checkouts
    $log.korus_sha = Update-Checkout 'the korus checkout' $korusRec
    $log.reader_sha = Update-Checkout 'the reader checkout' $readerRec

    $wiki = Join-Path (Join-Path $korus 'scripts') 'wiki'
    $scripts = @{}
    foreach ($n in @('import', 'compile', 'lint')) {
        $p = Join-Path $wiki "$n.ps1"
        if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { Stop-Cycle "the korus checkout has no scripts/wiki/$n.ps1 at $($log.korus_sha)." }
        $scripts[$n] = $p
    }

    # -------------------------------------------------------------------------------- import
    if ($importDue) {
        $eventsDir = Join-Path (Join-Path $reader 'wiki') 'events'
        $passRecord = Test-Path -LiteralPath $eventsDir -PathType Container
        $importArgs = @('-Store', ($stores -join ','), '-StateRoot', $script:StateRoot, '-Json')
        if ($passRecord) { $importArgs += @('-RecordRepo', $reader) }
        $step = Invoke-Step 'import' $scripts.import $importArgs
        $rec = $step.Record
        $rec.reason = $importWhy
        $rec.record_repo_passed = $passRecord
        $doc = ConvertFrom-StepJson $step.Out
        if ($doc -and $doc.PSObject.Properties['counts']) { $rec.counts = $doc.counts }
        $log.import = $rec
    } else {
        $log.import = [ordered]@{ skipped = $importWhy }
    }

    # -------------------------------------------------------------------------------- compile
    $step = Invoke-Step 'compile' $scripts.compile @('-StateRoot', $script:StateRoot, '-RecordRepo', $record, '-Json')
    $rec = $step.Record
    $doc = ConvertFrom-StepJson $step.Out
    if ($doc) {
        foreach ($f in @('result', 'pending', 'added', 'held', 'conflicts', 'pr')) {
            if ($doc.PSObject.Properties[$f]) { $rec[$f] = $doc.$f }
        }
    }
    $log.compile = $rec

    # -------------------------------------------------------------------------------- lint
    if (-not (Test-Path -LiteralPath $lintDir -PathType Container)) { $null = New-Item -ItemType Directory -Force -Path $lintDir }
    $lintArgs = @('-StateRoot', $script:StateRoot, '-RecordRepo', $reader)
    if ($evidence.Count -gt 0) { $lintArgs += @('-EvidenceRepo', ($evidence -join ',')) }
    $lintArgs += @('-Out', $lintFile)
    $step = Invoke-Step 'lint' $scripts.lint $lintArgs
    $rec = $step.Record
    $rec.out = $lintFile
    if ($rec.exit -eq 0) { $rec.totals = Read-LintTotals $lintFile }
    $log.lint = $rec
}

# ------------------------------------------------------------------------------------ run
$exitCode = 0
try {
    Invoke-WikiCycle
    if ($WhatIf) { $exitCode = $plan.would_exit }
    elseif ($script:stepFailed) { $exitCode = 1; $log.outcome = 'a step returned an error' }
    else { $log.outcome = 'every step ran' }
} catch [WikiCycleStop] {
    $exitCode = $_.Exception.Code
    $log.outcome = 'could not run'
    $log.problem = $_.Exception.Message
    [Console]::Error.WriteLine("wiki cycle: could not run: $($_.Exception.Message)")
} catch {
    $exitCode = 2
    $log.outcome = 'could not run'
    $log.problem = "unexpected: $($_.Exception.Message)"
    [Console]::Error.WriteLine("wiki cycle: could not run: $($_.Exception.Message)")
} finally {
    # Only the run that took the lock releases it. A refused run leaves a live holder's lock alone.
    if ($script:lockTaken -and $script:lockPath) {
        Remove-Item -LiteralPath $script:lockPath -Force -ErrorAction SilentlyContinue
    }
}

if ($WhatIf) {
    if ($exitCode -eq 2 -and -not $plan.would_exit) {
        $plan.would_exit = 2
        $plan.problems = @($plan.problems) + @($log.problem)
    }
    if ($Json) { ConvertTo-Json -InputObject $plan -Depth 6 }
    else {
        Write-Output "wiki cycle: -WhatIf, so nothing was fetched, moved, locked or written."
        foreach ($s in @($plan.steps)) { Write-Output ("  {0,-8} {1} {2}" -f $s.name, $s.script, ($s.arguments -join ' ')) }
        if ($plan.import) { Write-Output "  import: $($plan.import.reason)" }
        if ($plan.lock) { Write-Output "  lock: $($plan.lock)" }
        foreach ($p in @($plan.problems)) { Write-Output "  REFUSED: $p" }
        Write-Output "  a run would exit $($plan.would_exit)"
    }
    exit $exitCode
}

$log.end = Get-UtcStamp ([datetime]::UtcNow)
$log.exit = $exitCode
$line = ConvertTo-Json -InputObject $log -Depth 6 -Compress
if ($script:logDir -and (Test-Path -LiteralPath $script:StateRoot -PathType Container)) {
    try {
        $null = New-Item -ItemType Directory -Force -Path $script:logDir
        $logFile = Join-Path $script:logDir ("log-{0}.jsonl" -f $started.ToString('yyyy-MM', [cultureinfo]::InvariantCulture))
        [System.IO.File]::AppendAllText($logFile, $line + "`n", [System.Text.UTF8Encoding]::new($false))
    } catch {
        [Console]::Error.WriteLine("wiki cycle: could not write the log line: $($_.Exception.Message)")
        if ($exitCode -eq 0) { $exitCode = 2 }
    }
}

if ($Json) { Write-Output $line }
else {
    $imp = if ($log.import -and $log.import.Contains('skipped')) { "skipped ($($log.import.skipped))" } elseif ($log.import) { "exit $($log.import.exit)" } else { 'not reached' }
    $cmp = if ($log.compile) { "exit $($log.compile.exit), $($log.compile.result)" } else { 'not reached' }
    $lnt = if ($log.lint) { "exit $($log.lint.exit), report $($log.lint.out)" } else { 'not reached' }
    Write-Output "wiki cycle: korus at $($log.korus_sha); import $imp; compile $cmp; lint $lnt; exit $exitCode."
}
exit $exitCode
