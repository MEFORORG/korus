#Requires -Version 7.3
<#
.SYNOPSIS
    Register, show or remove the Windows scheduled task that runs the fleet wiki's cycle daily.

.DESCRIPTION
    The task runs `cycle.ps1` from a dedicated korus checkout once a day. The cycle imports on its
    day, compiles and lints, with zero model calls (Owner ruling 2026-09-26). This script only
    manages the task. `cycle.ps1` holds the behaviour and its own refusals.

    EVERY PATH COMES IN AS A PARAMETER. Nothing about one machine is written in this file.

    THE TASK RUNS AS YOU, INTERACTIVELY, AT RUN LEVEL LIMITED. Three things the cycle needs live in
    your profile: the git credentials compile pushes with, the `gh` login it opens a pull request
    with, and the memory stores the import reads. As SYSTEM or another account those are missing
    or different. Running whether or not you are logged on would need a stored password. So the
    task runs while you are logged on, and -StartWhenAvailable runs a missed day at your next logon.
    Nothing it does needs elevation, so it does not ask for it.

    IT RUNS ON BATTERY, AND IN A HIDDEN WINDOW. Task Scheduler's defaults skip a start on battery
    and kill a run when the power is pulled, which would drop a laptop's day without a word. An
    interactive task also opens a console window, and closing it would kill the run mid-push.

    THE TASK STOPS AFTER ONE HOUR. The cycle treats a lock older than two hours as dead, so a run
    the scheduler killed never blocks the next day's run, and a live run never looks stale. A
    second start while one runs is ignored.

    THE TASK RUNS THE CHECKOUT'S OWN cycle.ps1. That checkout is detached, and each run moves it to
    `origin/main` and refuses local changes. So what runs is what `main` holds. That is why this
    script does not refuse to run inside Claude Code: a session's edits to a working tree never
    reach the scheduled checkout.

    Modes:
        (none)      register the task, replacing one of the same name
        -WhatIf     print exactly what would be registered, and register nothing
        -Status     show the task and the cycle's last log line
        -Uninstall  remove the task

    -Json prints any mode's result as JSON. -WhatIf touches no task on any platform, so it also
    runs where Task Scheduler does not exist.

    Exit codes:
        0  done, or the plan was printed
        2  could not: a missing or bad argument, a path that does not exist, not Windows, or the
           task store refused

.EXAMPLE
    Register the task on the reference fleet. Placeholders as in roles/WIKI.md; `<store N>` is one
    account's memory directory, and every store is named.

    pwsh -NoProfile -File <korus>/scripts/wiki/register-cycle-task.ps1 -KorusCheckout <korus> `
      -StateRoot <coord> -RecordRepo <vault> -ReaderRepo <vault reader> `
      -Store <store 1>,<store 2>,<store 3>,<store 4>,<store 5>,<store 6> `
      -EvidenceRepo <engine>,<korus clone>,<vault> -LintOut <lint dir> -WhatIf

    Drop -WhatIf to register it.
.EXAMPLE
    pwsh -NoProfile -File <korus>/scripts/wiki/register-cycle-task.ps1 -Status -StateRoot <coord>
.EXAMPLE
    pwsh -NoProfile -File <korus>/scripts/wiki/register-cycle-task.ps1 -Uninstall
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
    [string] $ImportDay = 'Sunday',
    # Daily start time, local, 24-hour "HH:mm".
    [string] $At = '06:30',
    [string] $TaskName = 'KORUS-Wiki-Cycle',
    [switch] $Status,
    [switch] $Uninstall,
    [switch] $WhatIf,
    [switch] $Json
)

$ErrorActionPreference = 'Stop'

# One definition of each value the task is built from. The plan and the registration both read
# these, so the plan cannot claim a setting the task does not have.
$RunLevel = 'Limited'
$LogonType = 'Interactive'
$TimeLimitHours = 1

function Stop-Register {
    param([string] $Message)
    [Console]::Error.WriteLine("register-cycle-task: $Message")
    exit 2
}

function Resolve-TaskDir {
    param([string] $Path)
    $full = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    $full = [System.IO.Path]::GetFullPath($full)
    $root = [System.IO.Path]::GetPathRoot($full)
    # A trailing backslash before a closing quote escapes the quote on a Windows command line.
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
        foreach ($p in $parts) { if (-not [string]::IsNullOrWhiteSpace($p)) { $list.Add((Resolve-TaskDir $p.Trim())) } }
    }
    return , $list.ToArray()
}

function Write-Result {
    param($Object, [string[]] $Lines)
    if ($Json) { ConvertTo-Json -InputObject $Object -Depth 6 }
    else { foreach ($l in $Lines) { Write-Output $l } }
}

$modes = @($Status, $Uninstall) | Where-Object { $_ }
if ($modes.Count -gt 1) { Stop-Register '-Status and -Uninstall cannot both be given.' }

# ------------------------------------------------------------------------------------ -Status
if ($Status) {
    if (-not $IsWindows) { Stop-Register 'Windows only: -Status reads Windows Task Scheduler.' }
    $result = [ordered]@{ taskName = $TaskName; registered = $false }
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        $info = $task | Get-ScheduledTaskInfo
        $result.registered = $true
        $result.state = [string]$task.State
        $result.lastRunTime = if ($info.LastRunTime) { $info.LastRunTime.ToString('s') } else { $null }
        $result.lastTaskResult = $info.LastTaskResult
        $result.nextRunTime = if ($info.NextRunTime) { $info.NextRunTime.ToString('s') } else { $null }
        $result.execute = $task.Actions[0].Execute
        $result.argument = $task.Actions[0].Arguments
    }
    if (-not [string]::IsNullOrWhiteSpace($StateRoot)) {
        $logDir = Join-Path (Resolve-TaskDir $StateRoot) 'wiki-cycle'
        $last = Get-ChildItem -LiteralPath $logDir -Filter 'log-*.jsonl' -File -ErrorAction SilentlyContinue |
            Sort-Object Name | Select-Object -Last 1
        $result.lastLogLine = if ($last) { (Get-Content -LiteralPath $last.FullName -Tail 1) } else { $null }
    }
    $lines = @(if ($result.registered) {
        "Task '$TaskName': $($result.state). Last run $($result.lastRunTime), result $($result.lastTaskResult). Next run $($result.nextRunTime)."
        "  runs: $($result.execute) $($result.argument)"
    } else { "No scheduled task '$TaskName'." })
    if ($result.Contains('lastLogLine')) { $lines += "  last log line: $(if ($result.lastLogLine) { $result.lastLogLine } else { '(none)' })" }
    Write-Result $result $lines
    exit 0
}

# ------------------------------------------------------------------------------------ -Uninstall
if ($Uninstall) {
    $result = [ordered]@{ taskName = $TaskName; whatIf = [bool]$WhatIf; registered = $null; removed = $false }
    if ($IsWindows) {
        $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        $result.registered = [bool]$existing
        if ($existing -and -not $WhatIf) {
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
            $result.removed = $true
        }
    } elseif (-not $WhatIf) {
        Stop-Register 'Windows only: -Uninstall removes a Windows scheduled task.'
    }
    $line = if ($WhatIf) { "-WhatIf: would remove task '$TaskName' (registered: $($result.registered))." }
    elseif ($result.removed) { "Removed scheduled task '$TaskName'." }
    else { "No scheduled task '$TaskName' to remove." }
    Write-Result $result @($line)
    exit 0
}

# ------------------------------------------------------------------------------------ plan
foreach ($pair in @(@('KorusCheckout', $KorusCheckout), @('StateRoot', $StateRoot), @('RecordRepo', $RecordRepo),
        @('ReaderRepo', $ReaderRepo), @('LintOut', $LintOut))) {
    if ([string]::IsNullOrWhiteSpace($pair[1])) { Stop-Register "-$($pair[0]) is required." }
}
$stores = Split-DirList $Store
if ($stores.Count -eq 0) { Stop-Register '-Store is required: the task imports weekly, and the cycle refuses an import with no store.' }
$evidence = Split-DirList $EvidenceRepo

# The rule cycle.ps1 applies, so the task never carries a day every run would refuse. Letters only:
# Enum.TryParse also takes a number, and ORs a comma list such as `Friday,Saturday` into no single day.
$day = [System.DayOfWeek]::Sunday
if ($ImportDay -notmatch '^\s*[A-Za-z]+\s*$' -or -not [System.Enum]::TryParse([System.DayOfWeek], $ImportDay.Trim(), $true, [ref]$day)) {
    Stop-Register "-ImportDay '$ImportDay' is not one day of the week."
}
$atTime = [datetime]::MinValue
if (-not [datetime]::TryParseExact($At, 'HH:mm', [cultureinfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::None, [ref]$atTime)) {
    Stop-Register "-At '$At' is not a 24-hour HH:mm time."
}

$korus = Resolve-TaskDir $KorusCheckout
$paths = [ordered]@{
    korusCheckout = $korus
    stateRoot     = Resolve-TaskDir $StateRoot
    recordRepo    = Resolve-TaskDir $RecordRepo
    readerRepo    = Resolve-TaskDir $ReaderRepo
    lintOut       = Resolve-TaskDir $LintOut
}
$cycle = Join-Path (Join-Path (Join-Path $korus 'scripts') 'wiki') 'cycle.ps1'

foreach ($v in @($paths.Values) + $stores + $evidence) {
    if ($v.Contains('"')) { Stop-Register "a path holds a double quote, which cannot pass through the task's command line: $v" }
}
# The lists reach the wiki scripts joined by commas, and each splits them again.
foreach ($v in $stores + $evidence) {
    if ($v.Contains(',')) { Stop-Register "a path holds a comma, which the wiki scripts would split into two paths: $v" }
}

# lintOut is left out: the cycle creates it.
$missing = [System.Collections.Generic.List[string]]::new()
foreach ($k in @('korusCheckout', 'stateRoot', 'recordRepo', 'readerRepo')) {
    if (-not (Test-Path -LiteralPath $paths[$k] -PathType Container)) { $missing.Add($paths[$k]) }
}
foreach ($d in $stores + $evidence) { if (-not (Test-Path -LiteralPath $d -PathType Container)) { $missing.Add($d) } }
$cycleExists = Test-Path -LiteralPath $cycle -PathType Leaf

function Format-Arg {
    <# Quoted for a Windows command line, where backslashes before a closing quote must be doubled. #>
    param([string] $Value)
    $trail = $Value.Length - $Value.TrimEnd('\').Length
    return '"' + $Value + ('\' * $trail) + '"'
}

# Hidden on Windows only: pwsh elsewhere refuses -WindowStyle as not implemented on that platform.
$window = if ($IsWindows) { '-WindowStyle Hidden ' } else { '' }
$argument = '-NoProfile -NonInteractive ' + $window + '-ExecutionPolicy Bypass -File ' + (Format-Arg $cycle) +
    ' -KorusCheckout ' + (Format-Arg $paths.korusCheckout) +
    ' -StateRoot ' + (Format-Arg $paths.stateRoot) +
    ' -RecordRepo ' + (Format-Arg $paths.recordRepo) +
    ' -ReaderRepo ' + (Format-Arg $paths.readerRepo) +
    ' -Store ' + (Format-Arg ($stores -join ','))
if ($evidence.Count -gt 0) { $argument += ' -EvidenceRepo ' + (Format-Arg ($evidence -join ',')) }
$argument += ' -LintOut ' + (Format-Arg $paths.lintOut) + " -ImportDay $day"

$userId = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } elseif ($env:USERNAME) { $env:USERNAME } else { $env:USER }
$executable = (Get-Process -Id $PID).Path

$plan = [ordered]@{
    taskName           = $TaskName
    whatIf             = [bool]$WhatIf
    executable         = $executable
    argument           = $argument
    workingDirectory   = $korus
    cycle              = $cycle
    cycleExists        = $cycleExists
    trigger            = [ordered]@{ kind = 'daily'; at = $At }
    importDay          = [string]$day
    userId             = $userId
    logonType          = $LogonType
    runLevel           = $RunLevel
    startWhenAvailable = $true
    allowStartIfOnBatteries = $true
    dontStopIfGoingOnBatteries = $true
    executionTimeLimitHours = $TimeLimitHours
    multipleInstances  = 'IgnoreNew'
    paths              = $paths
    stores             = $stores
    evidenceRepos      = $evidence
    missing            = @($missing)
}

$planLines = @(
    "Task '$TaskName': daily at $At local, as $userId ($LogonType logon, run level $RunLevel).",
    "  runs:  $executable $argument",
    "  in:    $korus",
    "  start when available: yes; runs on battery too; stop after $TimeLimitHours h; a second start while one runs is ignored.",
    "  imports on $day."
)
if (-not $cycleExists) { $planLines += "  MISSING: $cycle" }
foreach ($m in $missing) { $planLines += "  MISSING: $m" }

if ($WhatIf) {
    Write-Result $plan (@('-WhatIf: nothing was registered.') + $planLines)
    exit 0
}

# ------------------------------------------------------------------------------------ register
if (-not $IsWindows) { Stop-Register 'Windows only: this registers a Windows scheduled task. The cycle itself runs under any scheduler.' }
if (-not $cycleExists) { Stop-Register "the korus checkout has no scripts/wiki/cycle.ps1: $cycle. Move it to origin/main after this change lands." }
if ($missing.Count -gt 0) { Stop-Register "these directories do not exist: $($missing -join '; ')" }

try {
    $action = New-ScheduledTaskAction -Execute $executable -Argument $argument -WorkingDirectory $korus
    $trigger = New-ScheduledTaskTrigger -Daily -At $At
    $principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType $LogonType -RunLevel $RunLevel
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours $TimeLimitHours) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
} catch {
    Stop-Register "the task store refused: $($_.Exception.Message)"
}
$plan.whatIf = $false
Write-Result $plan (@("Registered.") + $planLines)
exit 0
