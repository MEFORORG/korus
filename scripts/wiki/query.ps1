#Requires -Version 7.3
<#
.SYNOPSIS
    Search the fleet wiki: the uncompiled inbox, and the compiled log when -RecordRepo is given.

.DESCRIPTION
    Every result has passed the guard (`_guard.ps1`, spec FR-011), so a superseded or retired event
    is never returned unless -History asks for it. A query for the OLD wording of a replaced fact
    returns the event that replaced it, marked with the id it was found through.

    Each result shows id, date, seat, evidence and ONE label (FR-014):

        historical  hidden by the guard; shown only with -History, with a pointer to what replaced it
        stale       past its stale_after date, or 46 days old or more
        inbox       written but not yet compiled into the log
        fresh       under 14 days old
        aging       14 to 45 days old

    The first label that applies is the one shown, in that order.

    BELOW THE MATCH FLOOR IT PRINTS EXACTLY `no note` (FR-015), never the nearest miss. A result
    must match at least 60 percent of the query's words. Words are lower-cased, split on anything
    not a letter or digit, and dropped when under three characters or on a short stopword list.

    A MEMORY MISS NEVER BLOCKS WORK (FR-016). An unreachable record repository or state root is
    reported on one line on stderr, the search goes on with whatever it could reach, and the exit
    is 0. Stdout carries only results, or exactly `no note`.

    A receipt goes to stderr on every run: how many events were searched from each source, and how
    many files could not be read. `no note` over zero events and `no note` over a thousand are
    different readings, and only the receipt tells them apart.

    Exit codes: 0 always, except 2 for arguments that cannot be run. An argument pwsh itself cannot
    bind, such as an unknown parameter name, exits 1 before this script starts.

.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/query.ps1 -Text "ascii gate exit code on windows"
.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/query.ps1 -Path scripts/coord/seat.ps1 -RecordRepo ../vault
#>
[CmdletBinding()]
param(
    [string] $Text,
    [string] $Path,
    [switch] $History,
    # A string, parsed below: an [int] binding failure exits 1 from pwsh itself, and a bad argument
    # here is documented as exit 2.
    [string] $Limit = '5',
    [switch] $Json,
    [string] $StateRoot,
    [string] $RecordRepo
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_event.ps1')
. (Join-Path $PSScriptRoot '_guard.ps1')

function Write-Note {
    # A one-line notice, always on stderr. Stdout carries only results or exactly `no note`, so a
    # caller testing for `no note` is never misled by a notice printed above it.
    param([string] $Message)
    [Console]::Error.WriteLine($Message)
}

if ([string]::IsNullOrWhiteSpace($Text) -and [string]::IsNullOrWhiteSpace($Path)) {
    [Console]::Error.WriteLine('wiki query: give -Text, -Path, or both.')
    exit 2
}
# A query made only of short words and stopwords has nothing to search for, and a `no note` for it
# would read as a real miss. It is a usage error, said as one.
if (-not [string]::IsNullOrWhiteSpace($Text) -and (Get-WikiToken $Text).Count -eq 0 -and [string]::IsNullOrWhiteSpace($Path)) {
    [Console]::Error.WriteLine('wiki query: -Text has no searchable word (three letters or more, not a stopword).')
    exit 2
}
$limitValue = 0
if (-not [int]::TryParse($Limit, [ref]$limitValue)) { $limitValue = 0 }
$Limit = $limitValue
if ($Limit -lt 1) {
    [Console]::Error.WriteLine('wiki query: -Limit must be 1 or more.')
    exit 2
}

# ------------------------------------------------------------------------------------ read
$inboxEvents = @()
$logEvents = @()
$skipped = 0
$inboxLabel = 'inbox'

if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    try {
        . (Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'coord') '_common.ps1')
        $StateRoot = Get-CcxStateRoot
    } catch {
        $StateRoot = $null
        Write-Note "state root unreachable ($($_.Exception.Message)); the inbox was not searched."
        $inboxLabel = 'inbox unreachable'
    }
}
if ($StateRoot) {
    $givenStateRoot = $StateRoot
    $StateRoot = Resolve-WikiDir $StateRoot
    if (Test-Path -LiteralPath $StateRoot -PathType Container) {
        try {
            $r = Read-WikiEventDir -Dir (Get-WikiInboxDir -StateRoot $StateRoot) -Source inbox
            $inboxEvents = @($r.Events)
            $skipped += $r.Skipped
        } catch {
            Write-Note "inbox unreadable ($($_.Exception.Message)); the inbox was not searched."
            $inboxLabel = 'inbox unreadable'
        }
    } else {
        Write-Note "state root unreachable: $(Format-WikiDirName $givenStateRoot $StateRoot) does not exist; the inbox was not searched."
        $inboxLabel = 'inbox unreachable'
    }
}

$logLabel = 'log not requested'
if (-not [string]::IsNullOrWhiteSpace($RecordRepo)) {
    $givenRecordRepo = $RecordRepo
    $RecordRepo = Resolve-WikiDir $RecordRepo
    if (-not (Test-Path -LiteralPath $RecordRepo -PathType Container)) {
        Write-Note "record repository unreachable: $(Format-WikiDirName $givenRecordRepo $RecordRepo) does not exist; searched the inbox only."
        $logLabel = 'log unreachable'
    } else {
        $eventsRoot = Get-WikiEventsRoot -RecordRepo $RecordRepo
        if (-not (Test-Path -LiteralPath $eventsRoot -PathType Container)) {
            Write-Note "record repository has no wiki/events directory at $(Format-WikiDirName $givenRecordRepo $RecordRepo); searched the inbox only."
            $logLabel = 'log absent'
        } else {
            try {
                $r = Read-WikiEventDir -Dir $eventsRoot -Source log -Recurse
                $logEvents = @($r.Events)
                $skipped += $r.Skipped
                $logLabel = "log $($logEvents.Count)"
            } catch {
                Write-Note "record repository unreadable ($($_.Exception.Message)); searched the inbox only."
                $logLabel = 'log unreadable'
            }
        }
    }
}

$all = @(Merge-WikiEvent -Log $logEvents -Inbox $inboxEvents)
$inboxPart = if ($inboxLabel -eq 'inbox') { "inbox $($inboxEvents.Count)" } else { $inboxLabel }
[Console]::Error.WriteLine("wiki query: searched $($all.Count) event(s): $inboxPart, $logLabel; $skipped file(s) unreadable and skipped")

# ------------------------------------------------------------------------------------ guard
# Labelled once, with every event, so a hidden hit can be followed to its replacement.
$labelled = Select-WikiLiveEvent -Events $all -History
$byId = @{}
foreach ($e in $labelled) { $byId[[string]$e.id] = $e }

$results = [System.Collections.Generic.List[object]]::new()
if ($History) {
    foreach ($h in (Find-WikiMatch -Events $labelled -Text $Text -Path $Path)) {
        $results.Add([pscustomobject]@{ Event = $h.Event; Score = $h.Score; Rank = $h.Rank; Order = $h.Order; Via = $null })
    }
} else {
    $live = [System.Collections.Generic.List[object]]::new()
    $hidden = [System.Collections.Generic.List[object]]::new()
    foreach ($e in $labelled) {
        if ($e._status -ceq 'historical') { $hidden.Add($e) }
        elseif ([string]$e.type -cnotin $script:WikiMarkerTypes) { $live.Add($e) }
    }
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($h in (Find-WikiMatch -Events $live -Text $Text -Path $Path)) {
        if ($seen.Add([string]$h.Event.id)) {
            $results.Add([pscustomobject]@{ Event = $h.Event; Score = $h.Score; Rank = $h.Rank; Order = $h.Order; Via = $null })
        }
    }
    # A hit on hidden text is followed to the live event that replaced it. The hidden event itself
    # is never shown: only its id, as the route the result was found by.
    foreach ($h in (Find-WikiMatch -Events $hidden -Text $Text -Path $Path)) {
        $succ = Resolve-WikiSuccessor -Item $h.Event -ById $byId
        if ($null -eq $succ) { continue }
        # With -Path, the replacement has to be about that file too. Otherwise a hidden event that
        # named the file would hand back a successor that does not.
        if ($Path -and -not (Test-WikiPathMatch -Item $succ -Path $Path)) { continue }
        if ($seen.Add([string]$succ.id)) {
            $results.Add([pscustomobject]@{ Event = $succ; Score = $h.Score; Rank = $h.Rank; Order = $succ._tsKey; Via = [string]$h.Event.id })
        }
    }
}

# ------------------------------------------------------------------------------------ label
$today = (Get-WikiClock).Date
function Get-ResultLabel {
    param($Item)
    if ([string]$Item._status -ceq 'historical') { return 'historical' }
    $sa = $Item.stale_after
    if ($null -ne $sa) {
        $saDate = if ($sa -is [datetime]) { $sa.Date } else {
            [datetime]::ParseExact([string]$sa, 'yyyy-MM-dd', [cultureinfo]::InvariantCulture) }
        if ($today -gt $saDate) { return 'stale' }
    }
    if ([string]$Item._source -ceq 'inbox') { return 'inbox' }
    $days = [math]::Floor(($today - $Item._utc.Date).TotalDays)
    if ($days -lt 14) { return 'fresh' }
    if ($days -le 45) { return 'aging' }
    return 'stale'
}

$ordered = @(Sort-WikiHit $results | Select-Object -First $Limit)

# ------------------------------------------------------------------------------------ print
if ($Json) {
    $rows = @(foreach ($r in $ordered) {
            $e = $r.Event
            [ordered]@{
                id          = [string]$e.id
                ts          = Format-WikiStamp -Utc $e._utc
                date        = $e._utc.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
                label       = Get-ResultLabel $e
                type        = [string]$e.type
                key         = [string]$e.key
                seat        = [string]$e.seat
                summary     = [string]$e.summary
                evidence    = [string]$e.evidence
                trust       = [string]$e.trust
                body        = $e.body
                paths       = @(foreach ($x in @($e.paths)) { if ($null -ne $x) { [string]$x } })
                supersedes  = @(foreach ($x in @($e.supersedes)) { if ($null -ne $x) { [string]$x } })
                source      = [string]$e._source
                replaced_by = $e._replacedBy
                found_via   = $r.Via
                score       = [math]::Round($r.Score, 3)
            }
        })
    ConvertTo-Json -InputObject $rows -Depth 5
    exit 0
}

if ($ordered.Count -eq 0) {
    Write-Output 'no note'
    exit 0
}

foreach ($r in $ordered) {
    $e = $r.Event
    $date = $e._utc.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
    Write-Output "$($e.id)  $date  $($e.seat)  [$(Get-ResultLabel $e)]  $($e.type)  $($e.key)"
    Write-Output "  $($e.summary)"
    Write-Output "  evidence: $($e.evidence)"
    $rb = $e._replacedBy
    if ($rb) { Write-Output "  replaced by: $rb" }
    if ($r.Via) { Write-Output "  found through: $($r.Via), which this event replaced" }
}
exit 0
