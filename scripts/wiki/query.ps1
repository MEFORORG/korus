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
    must match at least 60 percent of the query's words, where a word found in the key, summary or
    paths counts whole and a word found only in the body counts half. So an event whose only
    matches are in its body is never returned. Words are lower-cased, split on anything not a
    letter or digit, and dropped when under three characters or on a short stopword list.

    Results rank by that fraction plus a bonus for words in the key. Ties go to the higher BM25
    weight, which favours the event the words are about over one that mentions them in passing,
    then to the newer event. `Find-WikiMatch` in `_event.ps1` holds the arithmetic.

    THE IMPORT'S OWN RECORDS ARE HIDDEN BY DEFAULT. A key under a prefix in
    `$WikiImportRecordPrefixes` (`_event.ps1`), such as a `memory-merge/` merge record (spec FR-024),
    is bookkeeping about the import, not knowledge. -History returns them, with everything else the
    default hides. The receipt on stderr counts how many a default query hid.

    A MEMORY MISS NEVER BLOCKS WORK (FR-016). An unreachable record repository or state root is
    reported on one line on stderr, the search goes on with whatever it could reach, and the exit
    is 0. Stdout carries only results, or exactly `no note`, with one exception below.

    A FILE THAT MAY HAVE BEEN A RETIREMENT IS NOT READ PAST QUIETLY (FR-011). A `supersede` or
    `retire` marker that fails the full schema is still honoured when the fields the guard acts on
    are sound (`Test-WikiMarkerLoose` in `_event.ps1`). A file that is not a JSON object at all, a
    marker that fails even that check, or a content event that names `supersedes` and fails the
    schema, could have hidden something that now shows. So the first line of stdout is then

        warning: <n> event file(s) unreadable; a retirement may be missing

    and `-Json` prints an object in place of the bare array:

        { "warning": "<that line>", "unreadable": <n>, "results": [ ... ] }

    The shape changes only then, so a caller that reads an array fails loudly rather than reading a
    result that may carry a withdrawn fact. The exit is still 0.

    The reach of that warning is the files it names. A file whose `type` is damaged into a word
    that is not a marker, and that names no `supersedes`, reads as broken content: it is counted
    in the receipt on stderr and does not warn.

    A receipt goes to stderr on every run: how many events were searched from each source, and how
    many files could not be read. `no note` over zero events and `no note` over a thousand are
    different readings, and only the receipt tells them apart.

    EVERY QUERY IS LOGGED, LOCALLY. One tab-separated line is appended to
    `<StateRoot>/wiki/query-log/<yyyy-MM>.tsv`, by UTC month, with a header on a new file:

        utc  seat  text  path  results  top_score  no_note

    `seat` is -Seat, or empty. Every field has each control character, tabs and newlines included,
    and each Unicode line separator turned into a space. `results` is the number printed, `top_score` the first one's
    score, and `no_note` is `yes` when nothing was printed. It shows whether seats query the wiki
    and what they miss. It stays on this machine: nothing compiles, commits or sends it.

    Logging never changes stdout or the exit code. A log that cannot be written is one line on
    stderr and the query carries on (FR-016). No state root, or one that does not exist, logs
    nothing.

    Exit codes: 0 always, except 2 for arguments that cannot be run. An argument pwsh itself cannot
    bind, such as an unknown parameter name, exits 1 before this script starts.

.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/query.ps1 -Text "ascii gate exit code on windows" -Seat builder
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
    [string] $RecordRepo,
    # Only written to the query log. Never checked, so a mistyped seat cannot turn a query away.
    [string] $Seat
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_event.ps1')
. (Join-Path $PSScriptRoot '_guard.ps1')

function Write-Note {
    # A one-line notice, always on stderr. Stdout carries only results or `no note`, plus the one
    # unreadable-file warning described above, so no other notice is ever printed above a result.
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
$unreadable = 0
$loose = 0
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
    # Resolving can throw, for a drive that does not exist (`Q:\coord`). FR-016 says a store the query
    # cannot reach is reported and the search goes on, so a throw here is an unreachable store too.
    try { $StateRoot = Resolve-WikiDir $StateRoot }
    catch {
        $StateRoot = $null
        Write-Note "state root unreachable: '$givenStateRoot' cannot be resolved ($($_.Exception.Message)); the inbox was not searched."
        $inboxLabel = 'inbox unreachable'
    }
}
$stateRootFound = $false
if ($StateRoot) {
    if (Test-Path -LiteralPath $StateRoot -PathType Container) {
        $stateRootFound = $true
        try {
            $r = Read-WikiEventDir -Dir (Get-WikiInboxDir -StateRoot $StateRoot) -Source inbox
            $inboxEvents = @($r.Events)
            $skipped += $r.Skipped
            $unreadable += $r.Unreadable
            $loose += $r.Loose
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
    $resolved = $false
    $resolveError = ''
    try { $RecordRepo = Resolve-WikiDir $RecordRepo; $resolved = $true } catch { $resolveError = $_.Exception.Message }
    if (-not $resolved) {
        Write-Note "record repository unreachable: '$givenRecordRepo' cannot be resolved ($resolveError); searched the inbox only."
        $logLabel = 'log unreachable'
    } elseif (-not (Test-Path -LiteralPath $RecordRepo -PathType Container)) {
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
                $unreadable += $r.Unreadable
                $loose += $r.Loose
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
$looseNote = if ($loose -gt 0) { "; $loose marker(s) honoured on the loose check" } else { '' }
# The import's own records are read but not scored by default. Said here, so a `no note` over a
# store that is mostly bookkeeping does not read as a miss over all of it.
$importRecords = 0
if (-not $History) { foreach ($e in $all) { if (Test-WikiImportRecord $e) { $importRecords++ } } }
$importNote = if ($importRecords -gt 0) { "; $importRecords import record(s) hidden, -History shows them" } else { '' }
[Console]::Error.WriteLine("wiki query: searched $($all.Count) event(s): $inboxPart, $logLabel; $skipped file(s) unreadable and skipped$looseNote$importNote")
$warning = if ($unreadable -gt 0) { "warning: $unreadable event file(s) unreadable; a retirement may be missing" } else { $null }

# ------------------------------------------------------------------------------------ guard
# Labelled once, with every event, so a hidden hit can be followed to its replacement.
$labelled = Select-WikiLiveEvent -Events $all -History
$byId = @{}
foreach ($e in $labelled) { $byId[[string]$e.id] = $e }

$results = [System.Collections.Generic.List[object]]::new()
if ($History) {
    foreach ($h in (Find-WikiMatch -Events $labelled -Text $Text -Path $Path)) {
        $results.Add([pscustomobject]@{ Event = $h.Event; Score = $h.Score; Rank = $h.Rank; Weight = $h.Weight; Order = $h.Order; Via = $null })
    }
} else {
    # Live content and hidden events are scored in ONE call, so every BM25 weight is taken over the
    # same corpus and a redirected hit's weight compares fairly with a direct one.
    $searchable = [System.Collections.Generic.List[object]]::new()
    foreach ($e in $labelled) {
        # The import's own records are bookkeeping, shown only with -History. Dropped before
        # scoring, so they do not count toward BM25's document frequencies either.
        if (Test-WikiImportRecord $e) { continue }
        if ($e._status -ceq 'historical' -or [string]$e.type -cnotin $script:WikiMarkerTypes) { $searchable.Add($e) }
    }
    # No @(): Find-WikiMatch returns its list as ONE object, and @() would nest it.
    $found = Find-WikiMatch -Events $searchable -Text $Text -Path $Path
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($h in $found) {
        if ($h.Event._status -ceq 'historical') { continue }
        if ($seen.Add([string]$h.Event.id)) {
            $results.Add([pscustomobject]@{ Event = $h.Event; Score = $h.Score; Rank = $h.Rank; Weight = $h.Weight; Order = $h.Order; Via = $null })
        }
    }
    # A hit on hidden text is followed to the live event that replaced it. The hidden event itself
    # is never shown: only its id, as the route the result was found by.
    foreach ($h in $found) {
        if ($h.Event._status -cne 'historical') { continue }
        $succ = Resolve-WikiSuccessor -Item $h.Event -ById $byId
        if ($null -eq $succ -or (Test-WikiImportRecord $succ)) { continue }
        # With -Path, the replacement has to be about that file too. Otherwise a hidden event that
        # named the file would hand back a successor that does not.
        if ($Path -and -not (Test-WikiPathMatch -Item $succ -Path $Path)) { continue }
        if ($seen.Add([string]$succ.id)) {
            $results.Add([pscustomobject]@{ Event = $succ; Score = $h.Score; Rank = $h.Rank; Weight = $h.Weight; Order = $succ._tsKey; Via = [string]$h.Event.id })
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

# ------------------------------------------------------------------------------------ log
# One line per query, so an owner can see whether seats query at all and what they miss. Nothing
# here may reach stdout or the exit code: every failure is one line on stderr (FR-016).
if ($stateRootFound) {
    try {
        $now = Get-WikiClock
        $inv = [cultureinfo]::InvariantCulture
        $logDir = Get-WikiQueryLogDir -StateRoot $StateRoot
        $logFile = Join-Path $logDir ($now.ToString('yyyy-MM', $inv) + '.tsv')
        $enc = [System.Text.UTF8Encoding]::new($false)
        $top = if ($ordered.Count -gt 0) { ([math]::Round([double]$ordered[0].Score, 3)).ToString('0.###', $inv) } else { '' }
        $fields = @(
            (Format-WikiStamp -Utc $now),
            $Seat, $Text, $Path,
            $ordered.Count.ToString($inv), $top,
            $(if ($ordered.Count -eq 0) { 'yes' } else { 'no' })
        )
        # Every control character, tab and newline included, becomes a space, and so do the Unicode
        # line and paragraph separators, so one query is one line of seven fields whatever it held.
        $line = (@(foreach ($f in $fields) { [regex]::Replace([string]$f, '[\p{Cc}\p{Zl}\p{Zp}]', ' ') }) -join "`t") + "`n"
        [void][System.IO.Directory]::CreateDirectory($logDir)
        if (-not [System.IO.File]::Exists($logFile)) {
            # CreateNew, so two first queries of a month cannot both write the header.
            try {
                $fs = [System.IO.FileStream]::new($logFile, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
                try {
                    $b = $enc.GetBytes("utc`tseat`ttext`tpath`tresults`ttop_score`tno_note`n")
                    $fs.Write($b, 0, $b.Length)
                } finally { $fs.Dispose() }
            } catch [System.IO.IOException] {
                # Another query created it first. Anything else wrong with the file fails the append.
            }
        }
        # One write per line, under an exclusive write share, so two queries appending at once never
        # interleave. A writer that finds the file held retries briefly, then gives up on stderr.
        $bytes = $enc.GetBytes($line)
        for ($attempt = 1; ; $attempt++) {
            try {
                $fs = [System.IO.FileStream]::new($logFile, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
                try { $fs.Write($bytes, 0, $bytes.Length) } finally { $fs.Dispose() }
                break
            } catch [System.IO.IOException] {
                if ($attempt -ge 5) { throw }
                Start-Sleep -Milliseconds 20
            }
        }
    } catch {
        Write-Note ("wiki query: query log not written ($($_.Exception.Message)); the query is unaffected." -replace '\s+', ' ')
    }
}

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
                loose       = [bool]$e._loose
                score       = [math]::Round($r.Score, 3)
            }
        })
    if ($warning) {
        ConvertTo-Json -InputObject ([ordered]@{ warning = $warning; unreadable = $unreadable; results = $rows }) -Depth 6
    } else {
        ConvertTo-Json -InputObject $rows -Depth 5
    }
    exit 0
}

if ($warning) { Write-Output $warning }
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
    if ($e._loose) { Write-Output "  loose: failed the full schema; honoured for its effect only" }
}
exit 0
