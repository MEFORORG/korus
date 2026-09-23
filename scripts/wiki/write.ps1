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

    BATCH MODE, -FromJson <file>. The file holds a JSON array of events. Each is an object whose
    field names are the event's own: type, key, summary, evidence, and optionally body, supersedes,
    paths, stale_after and trust. It exists for the one-time import, where a process per event cost
    about 0.6 seconds each.

    EVERY BATCH EVENT TAKES THE SAME STEPS, IN THE SAME ORDER, AS A SINGLE WRITE. The same presence
    check, control-character check, three renderings, scanner, schema check and atomic rename. Only
    the scanner is started once per chunk of events rather than once per event.

    An event in the file cannot carry `id`, `ts` or `seat`, and any other unknown field is refused.
    The seat comes from -Seat, the marker or KORUS_SEAT, once for the whole batch.

    One event refused does not stop the others. Stdout is a JSON array with one entry per input, in
    input order: `{ index, status, id, code, reason }`. Status is `written`, `passed` (with
    -CheckOnly) or `refused`. The exit code is the worst code of any entry.

    -CheckOnly, with -FromJson only, runs every check and writes nothing. Its scan files go to the
    system temp directory, so the state root is not touched.

    Exit codes:
        0  written; the event id is the only thing on stdout (batch: every event written or passed)
        1  refused: a field is missing or malformed, or the leak scan fired (batch: at least one)
        2  could not run: no inbox, no python for the leak scan, or the scan itself failed. In batch
           mode also an unreadable -FromJson file, or -FromJson mixed with single-event parameters.
           When a batch could not run, nothing was written.

.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/write.ps1 -Type gotcha -Key git/show/dotpath-msys `
        -Summary "git show ref:.dotpath returns empty under MSYS" -Evidence "2aec304"
.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/write.ps1 -FromJson events.json -Seat import -StateRoot <dir>
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
    [string] $StateRoot,
    [string] $FromJson,
    [switch] $CheckOnly
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_event.ps1')

function Stop-Write {
    param([int] $Code, [string] $Message)
    [Console]::Error.WriteLine("wiki write: REFUSED: $Message")
    exit $Code
}

$batch = -not [string]::IsNullOrWhiteSpace($FromJson)
$jsonKind = [System.Text.Json.JsonValueKind]

# ------------------------------------------------------------------------------------ inputs
# One list of raw inputs, whichever mode: an ordered map of field name to value, spelled as the
# event spells it. `_bad` carries a refusal found while reading the batch file.
$inputs = [System.Collections.Generic.List[object]]::new()
if ($batch) {
    $singleParams = @('Type', 'Key', 'Summary', 'Evidence', 'Body', 'Supersedes', 'Paths', 'StaleAfter', 'Trust')
    $mixed = @($singleParams | Where-Object { $PSBoundParameters.ContainsKey($_) })
    if ($mixed.Count -gt 0) {
        Stop-Write 2 "-FromJson takes every event from the file; do not also pass -$($mixed -join ', -')."
    }
    $FromJson = Resolve-WikiDir $FromJson
    if (-not (Test-Path -LiteralPath $FromJson -PathType Leaf)) { Stop-Write 2 "-FromJson file '$FromJson' does not exist." }
    # System.Text.Json rather than ConvertFrom-Json. ConvertFrom-Json turns a string that looks like
    # a date into a [datetime], and casting it back renders it in the current culture, so a summary
    # that happened to be an ISO stamp would be written as different text.
    $doc = $null
    try { $doc = [System.Text.Json.JsonDocument]::Parse([System.IO.File]::ReadAllText($FromJson)) }
    catch { Stop-Write 2 "-FromJson file is not JSON: $($_.Exception.Message)" }
    if ($doc.RootElement.ValueKind -ne $jsonKind::Array) {
        $doc.Dispose()
        Stop-Write 2 '-FromJson file must hold a JSON array of events.'
    }
    foreach ($el in $doc.RootElement.EnumerateArray()) {
        $raw = [ordered]@{ _bad = $null }
        $inputs.Add($raw)
        if ($el.ValueKind -ne $jsonKind::Object) { $raw._bad = 'an entry is not a JSON object'; continue }
        foreach ($prop in $el.EnumerateObject()) {
            $name = $prop.Name
            $v = $prop.Value
            if ($name -cin @('id', 'ts', 'seat')) {
                $raw._bad = "an event cannot carry '$name'; the script supplies it"
            } elseif ($name -cin @('supersedes', 'paths')) {
                if ($v.ValueKind -eq $jsonKind::String) { $raw[$name] = @($v.GetString()) }
                elseif ($v.ValueKind -eq $jsonKind::Array) {
                    $list = [System.Collections.Generic.List[string]]::new()
                    foreach ($x in $v.EnumerateArray()) {
                        if ($x.ValueKind -ne $jsonKind::String) { $raw._bad = "field '$name' must hold strings"; break }
                        $list.Add($x.GetString())
                    }
                    $raw[$name] = $list.ToArray()
                } elseif ($v.ValueKind -ne $jsonKind::Null) { $raw._bad = "field '$name' must be a string or a list of strings" }
            } elseif ($name -cin @('type', 'key', 'summary', 'evidence', 'body', 'stale_after', 'trust')) {
                if ($v.ValueKind -eq $jsonKind::String) { $raw[$name] = $v.GetString() }
                elseif ($v.ValueKind -ne $jsonKind::Null) { $raw._bad = "field '$name' must be a string" }
            } else {
                # The field NAME only is echoed: a name is the caller's schema, not its content.
                $raw._bad = "unknown field '$name'"
            }
            if ($raw._bad) { break }
        }
    }
    $doc.Dispose()
} else {
    if ($CheckOnly) { Stop-Write 2 '-CheckOnly is for -FromJson only.' }
    $inputs.Add([ordered]@{
            _bad = $null; type = $Type; key = $Key; summary = $Summary; evidence = $Evidence; body = $Body
            supersedes = $Supersedes; paths = $Paths; stale_after = $StaleAfter; trust = $Trust
        })
}

# One result per input. A refused input keeps its code and message and is not looked at again.
$results = [object[]]::new($inputs.Count)
function Set-Refused {
    param([int] $Index, [int] $Code, [string] $Message)
    $results[$Index] = [pscustomobject]@{ index = $Index; status = 'refused'; id = $null; code = $Code; reason = $Message }
}
# In single mode the first refusal ends the run, exactly as it did before batch mode existed.
function Stop-IfSingleRefused {
    if (-not $batch -and $results[0] -and $results[0].status -ceq 'refused') { Stop-Write $results[0].code $results[0].reason }
}

# ------------------------------------------------------------------------------------ required
# Presence only, here. Nothing a caller typed is echoed until the leak scan has passed it.
for ($i = 0; $i -lt $inputs.Count; $i++) {
    $raw = $inputs[$i]
    if ($raw._bad) { Set-Refused $i 1 "$($raw._bad)."; continue }
    foreach ($pair in @(@('Type', 'type'), @('Key', 'key'), @('Summary', 'summary'), @('Evidence', 'evidence'))) {
        if ([string]::IsNullOrWhiteSpace([string]$raw[$pair[1]])) {
            Set-Refused $i 1 "-$($pair[0]) is required."
            break
        }
    }
}
Stop-IfSingleRefused

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
$records = [object[]]::new($inputs.Count)
for ($i = 0; $i -lt $inputs.Count; $i++) {
    if ($results[$i]) { continue }
    $raw = $inputs[$i]
    $now = Get-WikiClock
    $id = New-WikiId -Utc $now
    $trustValue = if ($null -eq $raw.trust) { 'generated' } else { [string]$raw.trust }

    $record = [ordered]@{
        id       = $id
        ts       = Format-WikiStamp -Utc $now
        type     = [string]$raw.type
        key      = ([string]$raw.key).Trim()
        seat     = $Seat
        summary  = ([string]$raw.summary).Trim()
        evidence = ([string]$raw.evidence).Trim()
        trust    = $trustValue
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$raw.body)) { $record.body = [string]$raw.body }
    # `pwsh -File` hands `-Supersedes a,b` over as ONE string, not two, so a list is also accepted as
    # a comma-separated value. An id never contains a comma; a path that does cannot be passed this way.
    $sup = @($raw.supersedes | ForEach-Object { $_ -split '[,\s]+' } | Where-Object { $_ })
    if ($sup.Count -gt 0) { $record.supersedes = $sup }
    $rel = @($raw.paths | ForEach-Object { $_ -split ',' } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object { ConvertTo-WikiRelPath $_ })
    if ($rel.Count -gt 0) { $record.paths = $rel }
    if (-not [string]::IsNullOrWhiteSpace([string]$raw.stale_after)) { $record.stale_after = ([string]$raw.stale_after).Trim() }

    # A control character is refused before the scan, by field name and never by value. The scanner
    # reads a file with a NUL in its first 4096 bytes as BINARY and passes it unscanned, so one NUL in
    # any field would carry a credential in the same field straight past it. Tab and newline are
    # allowed in -Body only, where they are ordinary text.
    $badField = $null
    foreach ($k in @($record.Keys)) {
        $bad = if ($k -ceq 'body') { $script:WikiBodyControl } else { $script:WikiControl }
        foreach ($v in @($record[$k])) { if ([string]$v -match $bad) { $badField = $k; break } }
        if ($badField) { break }
    }
    if ($badField) { Set-Refused $i 1 "field '$badField' contains a control character."; continue }
    $records[$i] = $record
}
Stop-IfSingleRefused

# ------------------------------------------------------------------------------------ where to
if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    . (Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'coord') '_common.ps1')
    try { $StateRoot = Get-CcxStateRoot }
    catch { Stop-Write 2 "the inbox is not reachable: no -StateRoot, and $($_.Exception.Message)" }
}
$givenStateRoot = $StateRoot
# A drive that does not exist (`Q:\coord`) makes resolving throw. That is an unreachable inbox, so it
# exits 2 like one, not 1 as an uncaught error would.
try { $StateRoot = Resolve-WikiDir $StateRoot }
catch { Stop-Write 2 "the inbox is not reachable: state root '$givenStateRoot' cannot be resolved ($($_.Exception.Message))." }
# A missing state root is refused rather than created: a typo'd path would otherwise swallow the
# event into a directory no reader looks in, which is worse than no memory (spec, Edge Cases).
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    Stop-Write 2 "the inbox is not reachable: state root $(Format-WikiDirName $givenStateRoot $StateRoot) does not exist."
}
$inbox = Get-WikiInboxDir -StateRoot $StateRoot
if ($CheckOnly) {
    # A check creates nothing under the state root.
    $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ('wiki-check-' + [guid]::NewGuid().ToString('N'))
    try { New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null }
    catch { Stop-Write 2 "could not create a scratch directory for the leak scan: $($_.Exception.Message)" }
} else {
    $tmpDir = Get-WikiTmpDir -StateRoot $StateRoot
    try {
        foreach ($d in @($inbox, $tmpDir)) {
            if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
        }
    } catch {
        Stop-Write 2 "the inbox is not reachable: could not create '$inbox': $($_.Exception.Message)"
    }
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

function Get-ScanText {
    <#
    THREE RENDERINGS, each closing a hole the others leave. The machine-made id and ts are left out
    of all three: nothing a caller typed is in them, and a random id suffix could spell a short token.
      1. One field per line, raw. The JSON below doubles every backslash, which hides a Windows home
         path from the detector that looks for one.
      2. Every whitespace-separated word on its own line. The scanner skips a WHOLE LINE that matches
         its allowlist, so a home path sitting beside an allowlisted example path passed renderings 1
         and 3; alone on its line, it cannot borrow its neighbour's exemption.
      3. The JSON, as it will be written.
    #>
    param($Record)
    $scanned = [ordered]@{}
    foreach ($k in $Record.Keys) { if ($k -cnotin @('id', 'ts')) { $scanned[$k] = $Record[$k] } }
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
    return $plain.ToString()
}

# Each scan file is named with no directory part and the scan runs FROM its directory, so no path
# component can trip the scanner's skip list and turn the scan into a scan of nothing. The scanner
# takes many files in one call and names the file on every hit line, so a hit is still attributed to
# the one event that carried it. Chunked, so the command line stays well under the Windows limit.
$pending = @(for ($i = 0; $i -lt $inputs.Count; $i++) { if ($records[$i]) { $i } })
$classesByIndex = @{}
$structuralOnly = $false
$chunkSize = 200
for ($c = 0; $c -lt $pending.Count; $c += $chunkSize) {
    $last = [math]::Min($c + $chunkSize, $pending.Count) - 1
    $names = [ordered]@{}
    $scanOut = @()
    $scanCode = -1
    $scanError = $null
    Push-Location -LiteralPath $tmpDir
    try {
        foreach ($i in $pending[$c..$last]) {
            $scanName = ".$($records[$i].id).scan.txt"
            $names[$scanName] = $i
            [System.IO.File]::WriteAllText((Join-Path $tmpDir $scanName), (Get-ScanText $records[$i]), [System.Text.UTF8Encoding]::new($false))
        }
        $ErrorActionPreference = 'Continue'
        $scanOut = @(& $python $scanner @($names.Keys) 2>&1 | ForEach-Object { [string]$_ })
        $scanCode = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
    } catch {
        $scanError = $_.Exception.Message
    } finally {
        Pop-Location
        foreach ($n in @($names.Keys)) { Remove-Item -LiteralPath (Join-Path $tmpDir $n) -Force -ErrorAction SilentlyContinue }
    }
    if ($scanError) {
        if ($CheckOnly) { Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue }
        Stop-Write 2 "the leak scan could not run ($scanError), so nothing was written."
    }

    # A hit line is `  <file>:<line>: <class>`. Only the class is kept; without --show-context the
    # scanner prints no value, and this keeps it that way even if that ever changes.
    $hitCount = 0
    foreach ($line in $scanOut) {
        if ($line -notmatch '^\s+(\.[0-9A-Za-z-]+\.scan\.txt):\d+: (.+)$') { continue }
        if (-not $names.Contains($Matches[1])) { continue }
        $class = ($Matches[2] -replace '\s*:.*$', '').Trim()
        if (-not $class) { continue }
        $idx = $names[$Matches[1]]
        if (-not $classesByIndex.ContainsKey($idx)) {
            $classesByIndex[$idx] = [System.Collections.Generic.SortedSet[string]]::new([System.StringComparer]::Ordinal)
        }
        [void]$classesByIndex[$idx].Add($class)
        $hitCount++
    }
    # Exit 1 with no hit line is a crash -- a python traceback also exits 1 -- and is not a finding.
    # A scan that could not run stops the WHOLE batch before anything is written.
    if (-not ($scanCode -eq 0 -or ($scanCode -eq 1 -and $hitCount -gt 0))) {
        if ($CheckOnly) { Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue }
        Stop-Write 2 "the leak scan could not run (exit $scanCode), so nothing was written."
    }
    if (@($scanOut | Where-Object { $_ -match 'STRUCTURAL-ONLY' }).Count -gt 0) { $structuralOnly = $true }
}
if ($CheckOnly) { Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue }
foreach ($i in $pending) {
    if ($classesByIndex.ContainsKey($i)) {
        Set-Refused $i 1 "the leak scan matched: $(@($classesByIndex[$i]) -join '; '). Nothing was written."
        $records[$i] = $null
    }
}
Stop-IfSingleRefused
# Passed. Say so when it passed on shapes alone, because that is a weaker pass than an armed one and
# nothing else would tell the writer: private names are not checked without a token source.
if ($structuralOnly) {
    [Console]::Error.WriteLine('wiki write: note: the leak scan ran structural-only (no token source), so private names were not checked.')
}

# ------------------------------------------------------------------------------------ schema
# AFTER the scan, on purpose. Several refusals below quote the offending value back ("key 'X' is
# not..."), and a refusal that echoed a secret would print the very thing the scan exists to stop.
# By this point every value has passed the scan.
for ($i = 0; $i -lt $inputs.Count; $i++) {
    if (-not $records[$i]) { continue }
    $why = Test-WikiEvent -Item ([pscustomobject]$records[$i])
    if ($why) { Set-Refused $i 1 "$why."; $records[$i] = $null }
}
Stop-IfSingleRefused

# ------------------------------------------------------------------------------------ write
# Temp file then rename, so a reader never sees a torn event. The temp name does not end in .json,
# and it lives outside the inbox, so no reader globs it up half-written.
for ($i = 0; $i -lt $inputs.Count; $i++) {
    if (-not $records[$i]) { continue }
    if ($CheckOnly) {
        $results[$i] = [pscustomobject]@{ index = $i; status = 'passed'; id = $null; code = 0; reason = $null }
        continue
    }
    $id = $records[$i].id
    $json = $records[$i] | ConvertTo-Json -Depth 5
    $final = Join-Path $inbox "$id.json"
    $tmp = Join-Path $tmpDir ".$id.json.tmp"
    try {
        [System.IO.File]::WriteAllText($tmp, $json + "`n", [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::Move($tmp, $final)
        $results[$i] = [pscustomobject]@{ index = $i; status = 'written'; id = $id; code = 0; reason = $null }
    } catch {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        Set-Refused $i 2 "could not write '$final': $($_.Exception.Message)"
    }
}
Stop-IfSingleRefused

if (-not $batch) {
    Write-Output $results[0].id
    exit 0
}

ConvertTo-Json -InputObject @($results) -Depth 3
$worst = 0
foreach ($r in $results) { if ($r.code -gt $worst) { $worst = $r.code } }
exit $worst
