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

      1. CHECK THE INPUTS BEFORE TOUCHING ANYTHING. The state root, the record repository and both
         checkouts must exist. Each checkout must be the top of a git work tree, on a DETACHED
         head, with no tracked change. The reader must share a root commit with the record
         repository, so a reader aimed at the wrong repository is refused rather than read as a
         record with no log. A failure here exits 2, and nothing has moved.
      2. TAKE THE LOCK, `<StateRoot>/wiki-cycle/lock`, created only if absent. A lock younger than
         four hours means another cycle runs: exit 2. An older one is dead, because the registered
         task is stopped after two hours. The run sets it aside, deletes it, says so in the log,
         and carries on.
      3. FETCH BOTH CHECKOUTS, and check that moving either strands no commit. A fetch is tried
         three times, a minute apart at most, because a run started at logon often beats the
         network. Both checkouts are checked for a tracked change again, since an edit can land
         during the fetch. Only when both pass does either move.
      4. MOVE -KorusCheckout AND -ReaderRepo TO `origin/main`. The wiki scripts then run FROM the
         korus checkout, so a run always uses the scripts `main` holds. Import and lint read the
         compiled log from the reader.
      5. IMPORT when it is due: see below. `-RecordRepo <ReaderRepo>` goes to the import ONLY when
         `<ReaderRepo>/wiki/events` exists. Before the first compile lands there is no log, and
         import.ps1 refuses a named record repository that has none.
      6. COMPILE: `compile.ps1 -StateRoot -RecordRepo -Json`. It opens its own pull request.
      7. LINT: `lint.ps1 -StateRoot -RecordRepo <ReaderRepo> -EvidenceRepo -Out
         <LintOut>/lint-<yyyy-MM-dd>.md`, dated by the UTC day the run started.
      8. APPEND ONE JSON LINE to `<StateRoot>/wiki-cycle/log-<yyyy-MM>.jsonl`, by the UTC month
         the run started, then release the lock. Every run that reaches its state root writes a
         line, a refused one included. A -WhatIf run writes none, and neither does a run the
         scheduler kills.

    WHEN THE IMPORT IS DUE. On -ImportDay, by local time. Also on a later day, when the log shows
    the cycle ran before the last import day and no import has run since that day began. So a
    machine that was off on the import day imports at its next run instead of a week late. -Import
    forces it and -NoImport skips it. An import that exited 0 or 1 counts as run; one that could
    not run is tried again the next day.

    A FAILED STEP DOES NOT STOP THE STEPS AFTER IT. Each step's exit code is recorded as returned,
    with its key counts: the import counts, compile's result, added count and pull request, and
    lint's totals. The stores and evidence repositories are checked by the step that reads them,
    so a missing store fails the import and leaves compile and lint to run. A step that runs past
    its limit is killed with its process tree and recorded as timed out.

    EACH STEP HAS ITS OWN LIMIT: compile 30 minutes, import and lint 15 each. Compile's is double
    the worst measured case. The first real compile took 203 s from a shell, and the task ran lint
    4.35 times slower than a shell did (87 s against 20 s, 2026-09-26). So a first compile could
    take about 15 minutes in the task, which is where the old limit sat.

    THE RUN KEEPS INSIDE 100 MINUTES, because the registered task is stopped at two hours and a run
    stopped there writes no log line. The 20 minutes to spare let a step cut off at the budget be
    killed and logged before the scheduler stops the run. A step gets its limit or what is left of
    the 100, whichever is less. A step with less than a minute left does not start, and is recorded
    as a failure.

    A KILLED COMPILE CAN LEAVE A TEMPORARY WORKTREE behind in the record clone, and a scan
    directory in the temp folder that holds copies of pending events. The message says so. To make
    a hang less likely, every step runs with git's terminal prompt and Git Credential Manager's
    prompts turned off, so a missing HTTPS credential fails at once instead of waiting. An SSH
    remote is not covered: ssh can still wait on a passphrase or a host key until the time limit.

    WHY A DETACHED HEAD IS REQUIRED. A dedicated scheduled checkout sits detached. A checkout on a
    branch is somebody's working tree, and moving it would pull the ground out from under a session.
    So the cycle refuses one rather than guess. To prepare a checkout, run
    `git -C <dir> switch --detach origin/main` once.

    WHAT COUNTS AS A LOCAL CHANGE. A tracked file that differs from HEAD, staged or not. And a HEAD
    that no branch, tag or remote-tracking ref reaches, because moving off it would strand it. A
    HEAD that some ref reaches is safe to leave even when `origin/main` lacks it, as after a squash
    merge. Untracked files do not block a run: a detached checkout never deletes one, and git itself
    refuses to overwrite one.

    THE CYCLE'S OWN COPY LAGS ONE RUN. The task runs the `cycle.ps1` in -KorusCheckout, as it stood
    when the run started. The run then moves that checkout, so the wiki scripts are current at once
    and a change to this file takes effect on the next run.

    IT NEVER MERGES, AND IT PUSHES ONLY THROUGH compile.ps1. It writes only under -StateRoot and
    -LintOut, and moves only the two checkouts named above.

    -WhatIf runs the checks of step 1, reads the lock, and prints the plan. It fetches nothing,
    moves nothing, takes no lock and writes no log line. It shows the scripts as the korus checkout
    holds them now, before a run would move it. Its -Json plan also carries each step's
    `timeout_minutes`, the run's `budget_minutes` and the `stale_lock_hours`.

    Exit codes:
        0  every step ran, whatever it found
        1  a step returned an error, timed out, or could not start or finish. The other steps
           still ran.
        2  the cycle could not run: a bad or missing argument, a missing state root, record
           repository or checkout, a checkout on a branch or with local changes, a fetch or checkout
           that failed, a missing wiki script, or the lock held by a live cycle

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

# Four hours is double the task's two-hour limit, so a live run never looks stale.
$StaleLockHours = 4
# Per step. See EACH STEP HAS ITS OWN LIMIT in the header for why compile gets 30.
$StepTimeoutMinutes = @{ import = 15; compile = 30; lint = 15 }
$RunBudgetMinutes = 100
$GitTimeoutSeconds = 120
$FetchWaits = @(0, 15, 45)
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
            # The list reaches import.ps1 and lint.ps1 joined by commas, and both split it again.
            if ($p.Contains(',')) { Stop-Cycle "the path '$p' holds a comma, which the wiki scripts would split into two paths." }
            $list.Add((Resolve-CycleDir $p.Trim()))
        }
    }
    return , $list.ToArray()
}

function ConvertTo-ImportDay {
    <#
    .SYNOPSIS
        One day name, or $null. The registrar applies the same rule.
    .DESCRIPTION
        Letters only: Enum.TryParse also takes a number, and ORs a comma list such as
        `Friday,Saturday` into a value that is no single day.
    #>
    param([string] $Text)
    if ($Text -notmatch '^\s*[A-Za-z]+\s*$') { return $null }
    $day = [System.DayOfWeek]::Sunday
    if (-not [System.Enum]::TryParse([System.DayOfWeek], $Text.Trim(), $true, [ref]$day)) { return $null }
    return $day
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
    # Nobody is watching a scheduled run, so a credential prompt would only wait for the time limit.
    $psi.Environment['GIT_TERMINAL_PROMPT'] = '0'
    $psi.Environment['GCM_INTERACTIVE'] = 'never'
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    $p = [System.Diagnostics.Process]::Start($psi)
    $out = $p.StandardOutput.ReadToEndAsync()
    $err = $p.StandardError.ReadToEndAsync()
    $timedOut = $false
    if (-not $p.WaitForExit($TimeoutMs)) {
        $timedOut = $true
        # Kill throws when part of the tree exits or refuses in the middle. The run must still go on
        # to record the timeout and run the next step, so no failure here may escape.
        try { $p.Kill($true) } catch [System.Exception] { [Console]::Error.WriteLine("wiki cycle: killing a timed-out step: $($_.Exception.Message)") }
        $null = $p.WaitForExit(30000)
    }
    $finished = $p.HasExited
    # A descendant that outlives the child can hold the pipe open, so the reads are bounded too.
    $readOut = $out.Wait(30000)
    $readErr = $err.Wait(30000)
    return [pscustomobject]@{
        Code     = if ($timedOut -or -not $finished) { $null } else { $p.ExitCode }
        TimedOut = $timedOut
        Out      = if ($readOut) { $out.Result } else { '' }
        Err      = if ($readErr) { $err.Result } else { 'stderr was not read: a process still held the pipe' }
        Seconds  = [math]::Round($clock.Elapsed.TotalSeconds, 1)
    }
}

function Invoke-Git {
    param([string] $Dir, [string[]] $Arguments)
    return Invoke-Proc -Exe $script:git -Dir $Dir -Arguments $Arguments -TimeoutMs ($GitTimeoutSeconds * 1000)
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
        Read-only checks on a checkout the cycle will move. Returns a record; a refusal sets .problem.
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

function Get-CheckoutTarget {
    <# Fetch, then find origin/main and refuse a move that would strand HEAD. Moves nothing. #>
    param([string] $Label, [System.Collections.IDictionary] $Rec)
    $dir = $Rec.path
    $fetch = $null
    foreach ($wait in $FetchWaits) {
        if ($wait -gt 0) {
            [Console]::Error.WriteLine("wiki cycle: $Label fetch failed; trying again in $wait s: $(Get-Tail $fetch.Err)")
            Start-Sleep -Seconds $wait
        }
        $fetch = Invoke-Git $dir @('fetch', '--quiet', $Remote)
        if ($fetch.Code -eq 0) { break }
    }
    if ($fetch.Code -ne 0) { Stop-Cycle "$Label '$dir': git fetch $Remote failed $($FetchWaits.Count) times: $(Get-Tail $fetch.Err)" }
    $target = Invoke-Git $dir @('rev-parse', '--verify', "$Remote/$Base^{commit}")
    if ($target.Code -ne 0) { Stop-Cycle "$Label '$dir' has no $Remote/$Base after the fetch." }
    # Checked again: an edit made during the fetch would otherwise ride along through the checkout.
    $again = Test-Checkout $Label $dir
    if ($again.problem) { Stop-Cycle $again.problem }
    if ($again.head -ne $Rec.head) { Stop-Cycle "$Label '$dir' moved to $($again.head) while the cycle fetched. Another process is using it." }
    # Stranded means no ref reaches HEAD. An ancestry test against origin/main alone would refuse a
    # checkout left at a pull request's head forever once it squash-merged.
    $holders = Invoke-Git $dir @('for-each-ref', '--contains', 'HEAD', '--count=1', '--format=%(refname)')
    if ($holders.Code -ne 0) { Stop-Cycle "$Label '$dir': git for-each-ref failed: $(Get-Tail $holders.Err)" }
    if (-not $holders.Out.Trim()) {
        Stop-Cycle "$Label '$dir' holds commits that no branch, tag or remote-tracking ref reaches. Moving it would strand them, so the cycle will not."
    }
    return $target.Out.Trim()
}

function Move-Checkout {
    param([string] $Label, [System.Collections.IDictionary] $Rec, [string] $Sha)
    if ($Rec.head -ne $Sha) {
        $co = Invoke-Git $Rec.path @('checkout', '--quiet', '--detach', $Sha)
        if ($co.Code -ne 0) { Stop-Cycle "$Label '$($Rec.path)': git checkout of $Remote/$Base failed: $(Get-Tail $co.Err)" }
    }
    $Rec.head = $Sha
}

function Test-SameRepository {
    <# True when two repositories share a root commit, which clones of one repository always do. #>
    param([string] $A, [string] $B)
    $ra = Invoke-Git $A @('rev-list', '--max-parents=0', 'HEAD')
    $rb = Invoke-Git $B @('rev-list', '--max-parents=0', 'HEAD')
    if ($ra.Code -ne 0 -or $rb.Code -ne 0) { return $false }
    $roots = @(($ra.Out -split "`r?`n") | Where-Object { $_.Trim() })
    foreach ($r in ($rb.Out -split "`r?`n")) { if ($r.Trim() -and $roots -contains $r.Trim()) { return $true } }
    return $false
}

function Get-StepPlan {
    <# The one definition of each step's script and arguments. -WhatIf prints it; a run executes it. #>
    param([string] $Korus, [string] $Reader, [string] $Record, [string[]] $Stores, [string[]] $Evidence,
        [string] $LintFile, [bool] $ImportDue)
    $wiki = Join-Path (Join-Path $Korus 'scripts') 'wiki'
    $steps = [System.Collections.Generic.List[object]]::new()
    if ($ImportDue) {
        $importArgs = @('-Store', ($Stores -join ','), '-StateRoot', $script:StateRoot, '-Json')
        $passRecord = Test-Path -LiteralPath (Join-Path (Join-Path $Reader 'wiki') 'events') -PathType Container
        if ($passRecord) { $importArgs += @('-RecordRepo', $Reader) }
        $steps.Add([ordered]@{ name = 'import'; script = (Join-Path $wiki 'import.ps1'); arguments = $importArgs; record_repo_passed = $passRecord
                timeout_minutes = $StepTimeoutMinutes['import'] })
    }
    $steps.Add([ordered]@{ name = 'compile'; script = (Join-Path $wiki 'compile.ps1'); arguments = @('-StateRoot', $script:StateRoot, '-RecordRepo', $Record, '-Json')
            timeout_minutes = $StepTimeoutMinutes['compile'] })
    $lintArgs = @('-StateRoot', $script:StateRoot, '-RecordRepo', $Reader)
    if ($Evidence.Count -gt 0) { $lintArgs += @('-EvidenceRepo', ($Evidence -join ',')) }
    $lintArgs += @('-Out', $LintFile)
    $steps.Add([ordered]@{ name = 'lint'; script = (Join-Path $wiki 'lint.ps1'); arguments = $lintArgs; timeout_minutes = $StepTimeoutMinutes['lint'] })
    return , $steps.ToArray()
}

function Invoke-Step {
    <# Run one wiki script from the korus checkout in its own pwsh process. #>
    param([System.Collections.IDictionary] $Step)
    $name = $Step.name
    $leftMs = [int](($script:deadline - [datetime]::UtcNow).TotalMilliseconds)
    if ($leftMs -lt 60000) {
        $script:stepFailed = $true
        [Console]::Error.WriteLine("wiki cycle: $name did not start: the run's $RunBudgetMinutes-minute budget is spent.")
        return [pscustomobject]@{ Record = [ordered]@{ exit = $null; problem = "not started: the $RunBudgetMinutes-minute run budget is spent" }; Out = '' }
    }
    $limitMs = [math]::Min($Step.timeout_minutes * 60000, $leftMs)
    $r = Invoke-Proc -Exe $script:pwsh -Dir $script:korusDir -TimeoutMs $limitMs `
        -Arguments (@('-NoProfile', '-NonInteractive', '-File', $Step.script) + $Step.arguments)
    $rec = [ordered]@{ exit = $r.Code; seconds = $r.Seconds }
    if ($r.TimedOut) {
        $rec.timed_out = $true
        $script:stepFailed = $true
        $extra = if ($name -eq 'compile') { ' A killed compile can leave a temporary worktree in the record clone and a korus-wiki-scan directory in the temp folder; remove both by hand.' } else { '' }
        [Console]::Error.WriteLine("wiki cycle: $name ran past its $([math]::Round($limitMs / 60000, 1))-minute limit and was killed.$extra")
    } elseif ($r.Code -ne 0) {
        $script:stepFailed = $true
        $rec.stderr_tail = Get-Tail $r.Err
        [Console]::Error.WriteLine("wiki cycle: $name exited $($r.Code): $($rec.stderr_tail)")
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

function Read-CycleLog {
    <# Every readable line of this month's and last month's log, as objects. A torn line is skipped. #>
    param([datetime] $Now)
    $lines = [System.Collections.Generic.List[object]]::new()
    foreach ($month in @($Now.AddMonths(-1), $Now)) {
        $path = Join-Path $script:logDir ("log-{0}.jsonl" -f $month.ToString('yyyy-MM', [cultureinfo]::InvariantCulture))
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        foreach ($text in [System.IO.File]::ReadAllLines($path)) {
            if (-not $text.Trim()) { continue }
            try { $lines.Add((ConvertFrom-Json -InputObject $text -ErrorAction Stop)) } catch { continue }
        }
    }
    return , $lines.ToArray()
}

function Get-LineStart {
    param($Line)
    if (-not $Line.PSObject.Properties['start']) { return $null }
    $when = [datetime]::MinValue
    $styles = [System.Globalization.DateTimeStyles]::AdjustToUniversal -bor [System.Globalization.DateTimeStyles]::AssumeUniversal
    if ([datetime]::TryParse([string]$Line.start, [cultureinfo]::InvariantCulture, $styles, [ref]$when)) { return $when }
    return $null
}

function Get-ImportDecision {
    <# Whether the import is due, and why. See WHEN THE IMPORT IS DUE in the header. #>
    param([System.DayOfWeek] $Day)
    if ($NoImport) { return @{ Due = $false; Why = '-NoImport' } }
    if ($Import) { return @{ Due = $true; Why = '-Import' } }
    $today = [datetime]::Now.Date
    if ($today.DayOfWeek -eq $Day) { return @{ Due = $true; Why = "import day ($Day)" } }
    $back = ([int]$today.DayOfWeek - [int]$Day + 7) % 7
    $lastDay = $today.AddDays(-$back)
    $since = $lastDay.ToUniversalTime()
    $ranBefore = $false
    $importedSince = $false
    foreach ($line in (Read-CycleLog ([datetime]::UtcNow))) {
        $start = Get-LineStart $line
        if ($null -eq $start) { continue }
        if ($start -lt $since) { $ranBefore = $true; continue }
        $imp = if ($line.PSObject.Properties['import']) { $line.import } else { $null }
        if ($imp -and $imp.PSObject.Properties['exit'] -and $null -ne $imp.exit -and @(0, 1) -contains [int]$imp.exit) { $importedSince = $true }
    }
    $dayText = $lastDay.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
    if ($ranBefore -and -not $importedSince) {
        return @{ Due = $true; Why = "catch-up: no import has run since the import day, $Day $dayText" }
    }
    $owed = if ($ranBefore) { "an import has run since $dayText" } else { "the log shows no run before $dayText" }
    return @{ Due = $false; Why = "not the import day: today is $($today.DayOfWeek), import runs on $Day, and no catch-up is owed ($owed)" }
}

function Enter-CycleLock {
    <#
    .SYNOPSIS
        Take the lock, or stop. A lock older than the stale limit is set aside and deleted first.
    .DESCRIPTION
        The age is read in place first, so a live lock is never touched. Only a lock that looks
        stale is RENAMED aside and judged again there. Two runs can both read one stale lock; the
        one that renames second then holds whatever file sits at the path by then. If that is a
        fresh lock another run just took, it goes back and this run stops, so a stale-lock break
        never deletes a live holder's lock.
    #>
    param([string] $Holder)
    for ($attempt = 0; $attempt -lt 4; $attempt++) {
        try {
            $fs = [System.IO.File]::Open($script:lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
            try {
                $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($Holder)
                $fs.Write($bytes, 0, $bytes.Length)
            } finally { $fs.Dispose() }
            $script:lockTaken = $true
            if (-not $log.lock) { $log.lock = [ordered]@{ state = 'taken' } }
            return
        } catch [System.IO.IOException] {
            if (-not (Test-Path -LiteralPath $script:lockPath -PathType Leaf)) { continue }
        }
        $inPlace = $null
        try { $inPlace = ([datetime]::UtcNow - (Get-Item -LiteralPath $script:lockPath).LastWriteTimeUtc).TotalHours }
        catch [System.Management.Automation.ItemNotFoundException] { continue }
        if ($inPlace -lt $StaleLockHours) {
            $who = 'unreadable'
            try { $who = ([System.IO.File]::ReadAllText($script:lockPath)).Trim() } catch [System.IO.IOException] { $null = $_ }
            $log.lock = [ordered]@{ state = 'held'; age_hours = [math]::Round($inPlace, 2); holder = $who }
            Stop-Cycle "another cycle holds the lock '$($script:lockPath)' ($who, $([math]::Round($inPlace, 2)) h old)."
        }
        $aside = "$($script:lockPath).aside-$PID-$([guid]::NewGuid().ToString('N'))"
        try { [System.IO.File]::Move($script:lockPath, $aside) }
        catch [System.IO.IOException] { continue }
        $age = ([datetime]::UtcNow - (Get-Item -LiteralPath $aside).LastWriteTimeUtc).TotalHours
        $who = 'unreadable'
        try { $who = ([System.IO.File]::ReadAllText($aside)).Trim() } catch [System.IO.IOException] { $null = $_ }
        if ($age -lt $StaleLockHours) {
            try { [System.IO.File]::Move($aside, $script:lockPath) }
            catch [System.IO.IOException] { [Console]::Error.WriteLine("wiki cycle: could not put back the live lock set aside at '$aside'.") }
            $log.lock = [ordered]@{ state = 'held'; age_hours = [math]::Round($age, 2); holder = $who }
            Stop-Cycle "another cycle holds the lock '$($script:lockPath)' ($who, $([math]::Round($age, 2)) h old)."
        }
        Remove-Item -LiteralPath $aside -Force
        $log.lock = [ordered]@{ state = 'stale lock cleared'; age_hours = [math]::Round($age, 2); holder = $who }
        [Console]::Error.WriteLine("wiki cycle: cleared a stale lock, $([math]::Round($age, 2)) h old, held by: $who")
    }
    Stop-Cycle "could not take the lock '$($script:lockPath)'."
}

function Exit-CycleLock {
    <# Release the lock only while it still holds this run's own text. #>
    param([string] $Holder)
    if (-not $script:lockTaken) { return }
    try {
        if ((Test-Path -LiteralPath $script:lockPath -PathType Leaf) -and ([System.IO.File]::ReadAllText($script:lockPath)).Trim() -ceq $Holder) {
            Remove-Item -LiteralPath $script:lockPath -Force
        } else {
            [Console]::Error.WriteLine("wiki cycle: the lock no longer holds this run's text, so it was left alone.")
        }
    } catch [System.IO.IOException] {
        [Console]::Error.WriteLine("wiki cycle: could not release the lock: $($_.Exception.Message)")
    }
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
$holder = "pid $PID on $([System.Environment]::MachineName), started $($log.start), $([guid]::NewGuid().ToString('N'))"
$script:stepFailed = $false
$script:lockPath = $null
$script:lockTaken = $false
$script:logDir = $null
$script:korusDir = $null
$script:git = $null
$script:pwsh = (Get-Process -Id $PID).Path
$script:deadline = $started.AddMinutes($RunBudgetMinutes)

function Invoke-WikiCycle {
    # -------------------------------------------------------------------------------- arguments
    foreach ($pair in @(@('KorusCheckout', $KorusCheckout), @('StateRoot', $StateRoot), @('RecordRepo', $RecordRepo),
            @('ReaderRepo', $ReaderRepo), @('LintOut', $LintOut))) {
        if ([string]::IsNullOrWhiteSpace($pair[1])) { Stop-Cycle "-$($pair[0]) is required." }
    }
    $script:StateRoot = Resolve-CycleDir $StateRoot
    if (-not (Test-Path -LiteralPath $script:StateRoot -PathType Container)) { Stop-Cycle "state root '$($script:StateRoot)' does not exist." }
    $script:logDir = Join-Path $script:StateRoot 'wiki-cycle'
    $script:lockPath = Join-Path $script:logDir 'lock'

    if ($Import -and $NoImport) { Stop-Cycle '-Import and -NoImport cannot both be given.' }
    $day = ConvertTo-ImportDay $ImportDay
    if ($null -eq $day) { Stop-Cycle "-ImportDay '$ImportDay' is not one day of the week." }
    $decision = Get-ImportDecision $day

    $korus = Resolve-CycleDir $KorusCheckout
    $record = Resolve-CycleDir $RecordRepo
    $reader = Resolve-CycleDir $ReaderRepo
    $lintDir = Resolve-CycleDir $LintOut
    $stores = Split-DirList $Store
    $evidence = Split-DirList $EvidenceRepo
    if (-not (Test-Path -LiteralPath $record -PathType Container)) { Stop-Cycle "record repository '$record' does not exist." }
    if (Test-Path -LiteralPath $lintDir -PathType Leaf) { Stop-Cycle "-LintOut '$lintDir' is a file, not a directory." }

    $gitCmd = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $gitCmd) { Stop-Cycle 'git is not on PATH.' }
    $script:git = $gitCmd.Source
    $script:korusDir = $korus
    $script:sameRepoProblem = "the reader '$reader' shares no root commit with the record repository '$record', so it is not a checkout of it."

    # -------------------------------------------------------------------------------- checkouts
    # Both are checked before either moves, so a refusal leaves both where they were.
    $korusRec = Test-Checkout 'the korus checkout' $korus
    $readerRec = Test-Checkout 'the reader checkout' $reader
    $lintFile = Join-Path $lintDir ("lint-{0}.md" -f $started.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture))

    if ($WhatIf) {
        $plan.korus = $korusRec
        $plan.reader = $readerRec
        $problems = [System.Collections.Generic.List[string]]::new()
        foreach ($rec in @($korusRec, $readerRec)) { if ($rec.problem) { $problems.Add($rec.problem) } }
        if (-not $readerRec.problem -and -not (Test-SameRepository $reader $record)) { $problems.Add($script:sameRepoProblem) }
        if ($decision.Due -and $stores.Count -eq 0) { $problems.Add("the import is due ($($decision.Why)) and no -Store was given, so the import step would fail.") }
        $lockState = 'free'
        if (Test-Path -LiteralPath $script:lockPath -PathType Leaf) {
            $age = ([datetime]::UtcNow - (Get-Item -LiteralPath $script:lockPath).LastWriteTimeUtc).TotalHours
            if ($age -ge $StaleLockHours) { $lockState = "stale ($([math]::Round($age, 1)) h old); a run would clear it" }
            else { $lockState = "held ($([math]::Round($age, 1)) h old)"; $problems.Add("the lock '$($script:lockPath)' is held by a live cycle.") }
        }
        $plan.lock = $lockState
        $plan.import = [ordered]@{ due = $decision.Due; reason = $decision.Why
            note = 'Whether -RecordRepo reaches the import is read from the reader as it stands now; a run reads it again after the move.' }
        $plan.steps = Get-StepPlan -Korus $korus -Reader $reader -Record $record -Stores $stores -Evidence $evidence `
            -LintFile $lintFile -ImportDue $decision.Due
        $plan.budget_minutes = $RunBudgetMinutes
        $plan.stale_lock_hours = $StaleLockHours
        $plan.log = Join-Path $script:logDir ("log-{0}.jsonl" -f $started.ToString('yyyy-MM', [cultureinfo]::InvariantCulture))
        $plan.problems = @($problems)
        $refused = (@($korusRec, $readerRec) | Where-Object { $_.problem }) -or $problems.Contains($script:sameRepoProblem) -or $lockState -like 'held*'
        $plan.would_exit = if ($refused) { 2 } elseif ($problems.Count -gt 0) { 1 } else { 0 }
        return
    }

    foreach ($rec in @($korusRec, $readerRec)) { if ($rec.problem) { Stop-Cycle $rec.problem } }
    if (-not (Test-SameRepository $reader $record)) { Stop-Cycle $script:sameRepoProblem }

    # -------------------------------------------------------------------------------- lock
    $null = New-Item -ItemType Directory -Force -Path $script:logDir
    Enter-CycleLock $holder

    # -------------------------------------------------------------------------------- move the checkouts
    # Every fetch and every stranding check passes before either checkout moves.
    $korusSha = Get-CheckoutTarget 'the korus checkout' $korusRec
    $readerSha = Get-CheckoutTarget 'the reader checkout' $readerRec
    Move-Checkout 'the korus checkout' $korusRec $korusSha
    $log.korus_sha = $korusSha
    Move-Checkout 'the reader checkout' $readerRec $readerSha
    $log.reader_sha = $readerSha

    $steps = Get-StepPlan -Korus $korus -Reader $reader -Record $record -Stores $stores -Evidence $evidence `
        -LintFile $lintFile -ImportDue $decision.Due
    foreach ($s in $steps) {
        if (-not (Test-Path -LiteralPath $s.script -PathType Leaf)) { Stop-Cycle "the korus checkout has no scripts/wiki/$($s.name).ps1 at $korusSha." }
    }
    if (-not $decision.Due) { $log.import = [ordered]@{ skipped = $decision.Why } }

    foreach ($s in $steps) {
        if ($s.name -eq 'import' -and $stores.Count -eq 0) {
            # A configuration fault in one step, not a reason to skip compile and lint.
            $script:stepFailed = $true
            $log.import = [ordered]@{ exit = $null; reason = $decision.Why; problem = 'the import is due and no -Store was given' }
            [Console]::Error.WriteLine("wiki cycle: the import is due ($($decision.Why)) and no -Store was given; it did not run.")
            continue
        }
        # Anything a step throws is that step's failure. The steps after it still run.
        try {
            if ($s.name -eq 'lint' -and -not (Test-Path -LiteralPath $lintDir -PathType Container)) {
                $null = New-Item -ItemType Directory -Force -Path $lintDir
            }
            $step = Invoke-Step $s
            $rec = $step.Record
            $doc = ConvertFrom-StepJson $step.Out
            if ($s.name -eq 'lint') {
                $rec.out = $lintFile
                if ($rec.exit -eq 0) { $rec.totals = Read-LintTotals $lintFile }
            }
        } catch [WikiCycleStop] {
            throw
        } catch {
            $script:stepFailed = $true
            $rec = [ordered]@{ exit = $null; problem = "the step could not run: $($_.Exception.Message)" }
            $doc = $null
            [Console]::Error.WriteLine("wiki cycle: $($s.name) could not run: $($_.Exception.Message)")
        }
        switch ($s.name) {
            'import' {
                $rec.reason = $decision.Why
                $rec.record_repo_passed = $s.record_repo_passed
                if ($doc -and $doc.PSObject.Properties['counts']) { $rec.counts = $doc.counts }
                $log.import = $rec
            }
            'compile' {
                if ($doc) {
                    foreach ($f in @('result', 'pending', 'added', 'held', 'conflicts', 'pr')) {
                        if ($doc.PSObject.Properties[$f]) { $rec[$f] = $doc.$f }
                    }
                }
                $log.compile = $rec
            }
            'lint' { $log.lint = $rec }
        }
    }
}

# ------------------------------------------------------------------------------------ run
$exitCode = 0
try {
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
            foreach ($p in @($plan.problems)) { Write-Output "  PROBLEM: $p" }
            Write-Output "  a run would exit $($plan.would_exit)"
        }
        exit $exitCode
    }

    # The line is written while the lock is still held, so two runs' lines never interleave.
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
} finally {
    # Only the run that took the lock releases it. A refused run leaves a live holder's lock alone.
    Exit-CycleLock $holder
}

if ($Json) { Write-Output $line }
else {
    $imp = if ($log.import -and $log.import.Contains('skipped')) { "skipped ($($log.import.skipped))" } elseif ($log.import) { "exit $($log.import.exit)" } else { 'not reached' }
    $cmp = if ($log.compile) { "exit $($log.compile.exit), $($log.compile.result)" } else { 'not reached' }
    $lnt = if ($log.lint) { "exit $($log.lint.exit), report $($log.lint.out)" } else { 'not reached' }
    Write-Output "wiki cycle: korus at $($log.korus_sha); import $imp; compile $cmp; lint $lnt; exit $exitCode."
}
exit $exitCode
