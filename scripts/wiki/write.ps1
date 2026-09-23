#Requires -Version 7.3
<#
.SYNOPSIS
    Add one event to the fleet wiki. The ONLY write path (spec FR-001); every other wiki script reads.

.DESCRIPTION
    Validates the event, runs the leak scan over it, then drops ONE JSON file into the inbox:

        <StateRoot>/wiki/inbox/<id>.json

    The inbox lives in the coordination directory, which every account on the machine shares, so a
    seat on another account can query the event before any compile has run (spec Story 3).

    A WRITE NEVER WAITS ON GIT (FR-007). It makes no network call and runs no git command. The one
    exception is resolving the default -StateRoot, which asks `git rev-parse` where the shared git
    directory is; pass -StateRoot and no git process runs at all.

    THE CLOCK IS READ HERE, IN UTC (FR-004). There is no parameter for it. A seat that guessed a
    stamp would write an event that sorts wrong against every other.

    THE LEAK SCAN RUNS BEFORE ANY FILE EXISTS IN THE INBOX (FR-006). It is
    `scripts/security/scan_forbidden.py`, run over a plain rendering of every field: one field per
    line with its raw value, then the JSON. The plain rendering is not optional. JSON doubles every
    backslash, so a Windows home path serialised as JSON no longer has the shape the home-path
    detector looks for, and a scan of the JSON alone passes it. On a hit the write refuses and names
    the CLASS; the matched value is never printed.

    Exit codes:
        0  written; the event id is the only thing on stdout
        1  refused: a field is missing or malformed, or the leak scan fired
        2  could not run: no inbox, no python for the leak scan, or the scan itself failed

.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/write.ps1 -Type gotcha -Key git/show/dotpath-msys `
        -Summary "git show ref:.dotpath returns empty under MSYS" -Evidence "2aec304"
#>
[CmdletBinding()]
param(
    # Not [Parameter(Mandatory)]: a missing mandatory parameter makes pwsh PROMPT, which hangs a
    # headless caller. Each is checked below and refused on one line instead.
    [string] $Type,
    [string] $Key,
    [string] $Summary,
    [string] $Evidence,
    [string] $Body,
    [string[]] $Supersedes,
    [string[]] $Paths,
    [string] $StaleAfter,
    [string] $Trust = 'generated',
    [string] $Seat,
    [string] $StateRoot
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_event.ps1')

function Stop-Write {
    param([int] $Code, [string] $Message)
    [Console]::Error.WriteLine("wiki write: REFUSED: $Message")
    exit $Code
}

# ------------------------------------------------------------------------------------ required
# Presence only, here. Nothing a caller typed is echoed until the leak scan has passed it.
foreach ($pair in @(@('Type', $Type), @('Key', $Key), @('Summary', $Summary), @('Evidence', $Evidence))) {
    if ([string]::IsNullOrWhiteSpace($pair[1])) { Stop-Write 1 "-$($pair[0]) is required." }
}

# ---------------------------------------------------------------------------------------- seat
# The seat marker is `.claude/seat.local.txt` at the root of THIS checkout, which `seat.ps1
# -Declare` writes, then $env:KORUS_SEAT -- the same two sources, in the same order, that
# `scripts/hooks/role-card-inject.ps1` reads, so a session that got a role card can also write. The
# root is found by walking up to the nearest `.git` entry rather than by asking git, so the write
# stays git-free.
if ([string]::IsNullOrWhiteSpace($Seat)) {
    $dir = $PWD.Path
    $marker = $null
    while ($dir) {
        if (Test-Path -LiteralPath (Join-Path $dir '.git')) {
            $candidate = Join-Path (Join-Path $dir '.claude') 'seat.local.txt'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { $marker = $candidate }
            break
        }
        $parent = Split-Path -Parent $dir
        if (-not $parent -or $parent -eq $dir) { break }
        $dir = $parent
    }
    if ($marker) { $Seat = ([System.IO.File]::ReadAllText($marker)).Trim() }
    if ([string]::IsNullOrWhiteSpace($Seat)) { $Seat = $env:KORUS_SEAT }
    if ([string]::IsNullOrWhiteSpace($Seat)) {
        Stop-Write 1 ("no -Seat given, no .claude/seat.local.txt in this checkout, and no KORUS_SEAT. " +
            "Declare with scripts/coord/seat.ps1 -Declare, or pass -Seat.")
    }
}
$Seat = $Seat.Trim().ToLowerInvariant()

# ------------------------------------------------------------------------------------ the event
$now = Get-WikiClock
$id = New-WikiId -Utc $now

$record = [ordered]@{
    id       = $id
    ts       = Format-WikiStamp -Utc $now
    type     = $Type
    key      = $Key.Trim()
    seat     = $Seat
    summary  = $Summary.Trim()
    evidence = $Evidence.Trim()
    trust    = $Trust
}
if (-not [string]::IsNullOrWhiteSpace($Body)) { $record.body = $Body }
# `pwsh -File` hands `-Supersedes a,b` over as ONE string, not two, so a list is also accepted as a
# comma-separated value. An id never contains a comma; a path that does cannot be passed this way.
$sup = @($Supersedes | ForEach-Object { $_ -split '[,\s]+' } | Where-Object { $_ })
if ($sup.Count -gt 0) { $record.supersedes = $sup }
$rel = @($Paths | ForEach-Object { $_ -split ',' } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { ConvertTo-WikiRelPath $_ })
if ($rel.Count -gt 0) { $record.paths = $rel }
if (-not [string]::IsNullOrWhiteSpace($StaleAfter)) { $record.stale_after = $StaleAfter.Trim() }

# A control character is refused before the scan, by field name and never by value. The scanner
# reads a file with a NUL in its first 4096 bytes as BINARY and passes it unscanned, so one NUL in
# any field would carry a credential in the same field straight past it. Tab and newline are allowed
# in -Body only, where they are ordinary text.
foreach ($k in @($record.Keys)) {
    foreach ($v in @($record[$k])) {
        $bad = if ($k -ceq 'body') { $script:WikiBodyControl } else { $script:WikiControl }
        if ([string]$v -match $bad) { Stop-Write 1 "field '$k' contains a control character." }
    }
}

$json = $record | ConvertTo-Json -Depth 5

# ------------------------------------------------------------------------------------ where to
if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    . (Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'coord') '_common.ps1')
    try { $StateRoot = Get-CcxStateRoot }
    catch { Stop-Write 2 "the inbox is not reachable: no -StateRoot, and $($_.Exception.Message)" }
}
$StateRoot = Resolve-WikiDir $StateRoot
# A missing state root is refused rather than created: a typo'd path would otherwise swallow the
# event into a directory no reader looks in, which is worse than no memory (spec, Edge Cases).
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    Stop-Write 2 "the inbox is not reachable: state root '$StateRoot' does not exist."
}
$inbox = Get-WikiInboxDir -StateRoot $StateRoot
$tmpDir = Get-WikiTmpDir -StateRoot $StateRoot
try {
    foreach ($d in @($inbox, $tmpDir)) {
        if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    }
} catch {
    Stop-Write 2 "the inbox is not reachable: could not create '$inbox': $($_.Exception.Message)"
}

# ------------------------------------------------------------------------------------ leak scan
$scanner = Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'security') 'scan_forbidden.py'
if (-not (Test-Path -LiteralPath $scanner -PathType Leaf)) {
    Stop-Write 2 "the leak scan is missing (scripts/security/scan_forbidden.py), so nothing is written."
}
$python = $null
foreach ($name in @('python', 'python3')) {
    $cmd = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python) { Stop-Write 2 "no python on PATH to run the leak scan, so nothing is written." }

# THREE RENDERINGS, each closing a hole the others leave. The machine-made id and ts are left out of
# all three: nothing a caller typed is in them, and a random id suffix could spell a short token.
#   1. One field per line, raw. The JSON below doubles every backslash, which hides a Windows home
#      path from the detector that looks for one.
#   2. Every whitespace-separated word on its own line. The scanner skips a WHOLE LINE that matches
#      its allowlist, so a home path sitting beside an allowlisted example path passed renderings 1
#      and 3; alone on its line, it cannot borrow its neighbour's exemption.
#   3. The JSON, as it will be written.
$scanned = [ordered]@{}
foreach ($k in $record.Keys) { if ($k -cnotin @('id', 'ts')) { $scanned[$k] = $record[$k] } }
$plain = [System.Text.StringBuilder]::new()
foreach ($k in $scanned.Keys) {
    foreach ($v in @($scanned[$k])) { [void]$plain.AppendLine("${k}: $v") }
}
foreach ($k in $scanned.Keys) {
    foreach ($v in @($scanned[$k])) {
        foreach ($word in ([string]$v -split '\s+')) { if ($word) { [void]$plain.AppendLine($word) } }
    }
}
[void]$plain.AppendLine(($scanned | ConvertTo-Json -Depth 5))

# The scan file is named with no directory part and the scan runs FROM its directory, so no path
# component can trip the scanner's skip list and turn the scan into a scan of nothing.
$scanName = ".$id.scan.txt"
$scanPath = Join-Path $tmpDir $scanName
$scanOut = @()
$scanCode = -1
$scanError = $null
Push-Location -LiteralPath $tmpDir
try {
    [System.IO.File]::WriteAllText($scanPath, $plain.ToString(), [System.Text.UTF8Encoding]::new($false))
    $ErrorActionPreference = 'Continue'
    $scanOut = @(& $python $scanner $scanName 2>&1 | ForEach-Object { [string]$_ })
    $scanCode = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
} catch {
    $scanError = $_.Exception.Message
} finally {
    Pop-Location
    Remove-Item -LiteralPath $scanPath -Force -ErrorAction SilentlyContinue
}
if ($scanError) { Stop-Write 2 "the leak scan could not run ($scanError), so nothing was written." }

# A hit line is `  <file>:<line>: <class>`. Only the class is kept; without --show-context the
# scanner prints no value, and this keeps it that way even if that ever changes.
$pattern = '^\s+' + [regex]::Escape($scanName) + ':\d+: (.+)$'
$classes = @($scanOut | ForEach-Object {
        if ($_ -match $pattern) { ($Matches[1] -replace '\s*:.*$', '').Trim() }
    } | Where-Object { $_ } | Sort-Object -Unique)
if ($scanCode -eq 1 -and $classes.Count -gt 0) {
    Stop-Write 1 "the leak scan matched: $($classes -join '; '). Nothing was written."
}
# Exit 1 with no hit line is a crash -- a python traceback also exits 1 -- and is not a finding.
if ($scanCode -ne 0) {
    Stop-Write 2 "the leak scan could not run (exit $scanCode), so nothing was written."
}
# Passed. Say so when it passed on shapes alone, because that is a weaker pass than an armed one and
# nothing else would tell the writer: private names are not checked without a token source.
if (@($scanOut | Where-Object { $_ -match 'STRUCTURAL-ONLY' }).Count -gt 0) {
    [Console]::Error.WriteLine('wiki write: note: the leak scan ran structural-only (no token source), so private names were not checked.')
}

# ------------------------------------------------------------------------------------ schema
# AFTER the scan, on purpose. Several refusals below quote the offending value back ("key 'X' is
# not..."), and a refusal that echoed a secret would print the very thing the scan exists to stop.
# By this point every value has passed the scan.
$why = Test-WikiEvent -Item ([pscustomobject]$record)
if ($why) { Stop-Write 1 "$why." }

# ------------------------------------------------------------------------------------ write
# Temp file then rename, so a reader never sees a torn event. The temp name does not end in .json,
# and it lives outside the inbox, so no reader globs it up half-written.
$final = Join-Path $inbox "$id.json"
$tmp = Join-Path $tmpDir ".$id.json.tmp"
try {
    [System.IO.File]::WriteAllText($tmp, $json + "`n", [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::Move($tmp, $final)
} catch {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    Stop-Write 2 "could not write '$final': $($_.Exception.Message)"
}

Write-Output $id
exit 0
