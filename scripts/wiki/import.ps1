#Requires -Version 7.3
<#
.SYNOPSIS
    Fold the existing per-account memory stores into the fleet wiki, once (spec Story 4).

.DESCRIPTION
    Reads each `*.md` note in the directories named by -Store, turns each into one event, and hands
    them all to `write.ps1`, the only write path (FR-001). It never writes an inbox file itself.

    IT READS ONLY THE DIRECTORIES IT IS GIVEN (FR-023, Article VIII). There is no default, no glob
    and no search for account roots. A -Store value holding `*` or `?` is refused rather than
    expanded. Subdirectories of a store are not read.

    ONE NOTE BECOMES ONE EVENT.
        key       memory/<slug>. The slug is the note's `name`, else its file stem, lower-cased,
                  with every run of other characters turned into `-`.
        type      from the note's `type`, top level or under `metadata`:
                      feedback  -> lesson
                      project   -> decision
                      reference -> gotcha
                      user      -> decision
                  Anything else, or no type at all, becomes `lesson`, and the report counts it.
        summary   the note's `description`, on one line. With no description, the body's first
                  sentence. Over 400 characters it is cut to fit, and the full description goes at
                  the top of the body so nothing is lost.
        body      `Source note last modified: <yyyy-MM-dd>.`, a blank line, then the note's body.
                  The date is the day the note file was last written, in UTC. Over 20000
                  characters in all, the note's body is cut, with a line saying the full note is
                  the evidence file.
        stale_after
                  that date plus 45 days ($WikiStaleDays in _event.ps1). A query labels an event
                  stale after its stale_after, and a native event from 46 days old, so an imported
                  note reads stale on the day a native event written on the note's date would.
                  Lint ages only a native gotcha or lesson, but files ANY event past its
                  stale_after. So lint files an imported decision, from a project or user note, as
                  stale where it would not file a native one. That is deliberate: a project note
                  untouched for 45 days is worth a second look.
        evidence  memory:<store label>/<file name>. When the store sits at
                  <root>/projects/<project>/memory the label is <root>/<project>, such as
                  `.claude-account-3/~-Code-MessageFoundry`. The project folder is part of it
                  because one account holds a store per project, and two stores under one root
                  must not share evidence. The project folder spells the home directory in it,
                  as `C--Users-<u>-...`, so that prefix becomes `~` too. Any other store is
                  labelled by its own folder name.
        seat      -Seat, default `import`. Always passed to write.ps1, never left to its fallback.

    `MEMORY.md` is an index, not a note, and is never imported. A file with no front matter is
    skipped and counted.

    THE HOME DIRECTORY BECOMES `~` BEFORE ANYTHING IS SCANNED. The leak scan refuses an absolute
    home path, and an ordinary note often carries one. So the prefix of -HomeDir (default: the
    current user's profile) is replaced in the summary and body, in the forms `C:\Users\<u>`,
    `C:/Users/<u>` and `/c/Users/<u>`, ignoring case. Anything the scan still refuses is not
    imported, and the report names it by store, file and class, never by value.

    WHY THE DATE IS NOT `ts`. write.ps1 stamps `ts` from its own clock (FR-004), so every event one
    run writes carries that run's time. Back-dating it would break the rule every other reader
    relies on. The date line and stale_after carry the note's age beside it instead.

    RE-RUNNING IS SAFE (FR-027). The existing events are read from the inbox, and from the log with
    -RecordRepo. A note's TEXT is its summary and its body without the date line, so a file whose
    date moved and whose text did not is unchanged. For each note:
      1. The newest event with the SAME evidence, on any key, is the note's own earlier import.
         Same key and text: skipped, even if someone has since superseded or retired it. The
         note's date still dates that event for rule 4, which is how an event imported before
         notes carried a date gets one. A long note cut before the date line took its room counts
         as the same text too. Otherwise, a text edit or a rename: a new event that supersedes it,
         unless rule 4 holds it.
         Ahead of this rule, a note is skipped while its live hold still describes it: the same
         text, no later date, and nothing of the note written since.
      2. Otherwise, a note merged before whose text has not changed since is skipped, again
         whatever became of the event it merged into. An Owner who withdrew that text has
         withdrawn the copy too.
      3. Otherwise, a CURRENT event on the key with the same text is a MERGE. Current means no
         event supersedes it and no `retire` withdrew it. The note is not written. Instead a
         `decision` on memory-merge/<slug>/<store> records it (FR-024): its summary names both
         stores, its evidence is the kept event's, and its body carries `kept:`, `merged:`,
         `text:` and `date:` lines. `text:` is a hash of the merged note's text, and `date:` is
         its date, which counts as the kept text's date from then on.
      4. Otherwise THE NEWEST DATE ON THE KEY DECIDES, never the order the stores were read in.
         The texts compared are the current events on the key and the notes this run would write
         there. A text's date is the latest of its own and those of the notes merged into it. An
         event this script wrote before notes carried a date has none, and counts as older than
         any note, unless rule 1 dated it. Any other event, a seat's own, is dated by its `ts`.
           - A different text with a LATER date: the note is HELD, and nothing is written on its
             key. A `decision` on memory-held/<slug>/<store> records it instead: its evidence is
             the held note, and its body carries `kept:`, `held:`, `text:` and `date:` lines. It
             supersedes the note's earlier hold, and after a rename the note's import under its
             old name. When the note is later written, its event supersedes the hold.
           - Otherwise the note is written, and supersedes every current event on the key whose
             date is EARLIER. The report counts those events as older_superseded. A note that
             would have merged into one of them is held behind the newer text instead.
           - A different text with the SAME date is a tie. Both are kept and neither supersedes
             the other, and lint files the pair (Story 4, scenario 2). The report counts a conflict.
             Tied notes in one run are written in store-label order, one batch each, so the later
             label is the newer event and the one a reader sees. Against an event already there,
             the note is written and is the newer.
    Rule 1 runs over every note before rules 2 to 4 run over any, so a text this run replaces is
    no longer current when a later note looks for one to merge into. It goes first at all so that
    two stores holding different text under one name do not trade places on every run. Rule 3
    takes notes newest first, so where several stores hold one text the event kept is the newest.
    Rule 4 runs in rounds: when a note that outranked others is refused, the next round decides
    again without it, so a note is never held behind a text that did not reach the wiki.

    A DATE THAT MOVED WITH THE TEXT UNCHANGED WRITES NOTHING, so the event keeps the date line and
    stale_after it was written with. Rule 4 still ranks the text by the newer date. An event is
    never edited, and writing a copy for a date alone would churn every re-saved note.

    -WhatIf writes nothing. It runs every check, the leak scan included, through `write.ps1
    -CheckOnly`, and prints the same report.

    WITHOUT -RecordRepo, events already compiled into the log are not seen, and a re-run after a
    compile would import every note again. The run says so on stderr. A -RecordRepo that is named
    but holds no wiki/events directory is refused, because a wrong path would do the same silently.

    Exit codes:
        0  finished, and every note was imported, merged, held or already there
        1  finished, and something needs a look: a note refused or not written, or a note or an
           existing event that could not be read. Each is listed in the report.
        2  could not run: no -Store, a store that is not a directory, a pattern in -Store, two
           stores with one label, a bad -Seat, a -RecordRepo that is missing or holds no
           wiki/events, or `write.ps1` could not run a batch. Nothing was written in any of these
           cases, except when `write.ps1` failed on a later batch, a tie's or the records', which
           the message says.

.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/import.ps1 -Store <dir1>,<dir2> -WhatIf
#>
[CmdletBinding()]
param(
    # Not [Parameter(Mandatory)]: a missing mandatory parameter makes pwsh PROMPT, which hangs a
    # headless caller. `pwsh -File` hands `-Store a,b` over as ONE string, so a comma list is split.
    [string[]] $Store,
    [string] $StateRoot,
    [string] $RecordRepo,
    [string] $Seat = 'import',
    [string] $HomeDir,
    [switch] $WhatIf,
    [switch] $Json
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_event.ps1')

$started = [System.Diagnostics.Stopwatch]::StartNew()

function Stop-Import {
    param([string] $Message)
    [Console]::Error.WriteLine("wiki import: $Message")
    exit 2
}

$TypeMap = @{ feedback = 'lesson'; project = 'decision'; reference = 'gotcha'; user = 'decision' }
$SummaryMax = $script:WikiLimits.summary
$BodyMax = $script:WikiLimits.body
$TruncatedMarker = "`n`n[truncated at import; the full note is the evidence file]"
# A merge record's key is memory-merge/<slug>/<store>, which must fit the 200-character key limit.
$SlugMax = 140
$StoreSlugMax = 40

# ------------------------------------------------------------------------------------ home path
function New-HomePattern {
    <# A regex for the home directory's prefix in all three spellings, or $null for no usable home. #>
    param([string] $Dir)
    if ([string]::IsNullOrWhiteSpace($Dir)) { return $null }
    $segments = @($Dir.Trim() -split '[\\/]+' | Where-Object { $_ -ne '' })
    if ($segments.Count -gt 0 -and $segments[0] -match '^([A-Za-z]):$') {
        $drive = $Matches[1]
        $rest = @($segments | Select-Object -Skip 1)
        $prefix = "(?:$drive`:[\\/]+|/$drive/+)"
    } else {
        $rest = $segments
        $prefix = '/+'
    }
    # A bare drive or root is not a home directory, and replacing it would rewrite every path.
    if ($rest.Count -eq 0) { return $null }
    $body = ($rest | ForEach-Object { [regex]::Escape($_) }) -join '[\\/]+'
    # The look-ahead keeps `<home>2`, `<home>ish` or `<home>.bak` from losing its prefix, and
    # still matches a home path that ends a sentence with a full stop.
    return [regex]::new('(?i)' + $prefix + $body + '(?![A-Za-z0-9_-]|\.[A-Za-z0-9])')
}

if ([string]::IsNullOrWhiteSpace($HomeDir)) { $HomeDir = [Environment]::GetFolderPath('UserProfile') }
if ([string]::IsNullOrWhiteSpace($HomeDir)) { $HomeDir = $HOME }
$homePattern = New-HomePattern $HomeDir
# The home directory as a project folder spells it: every character but a letter or digit becomes
# `-`. Not only the separators: `john.smith` is spelled `john-smith` there, and missing it shipped
# the account name in every event's evidence.
$homeSlug = if ([string]::IsNullOrWhiteSpace($HomeDir)) { '' } else { $HomeDir.Trim().TrimEnd('\', '/') -replace '[^A-Za-z0-9]', '-' }

if ([string]::IsNullOrWhiteSpace($Seat)) { $Seat = 'import' }
$Seat = $Seat.Trim().ToLowerInvariant()
if ($Seat -cnotmatch $script:WikiSeatPattern) { Stop-Import "-Seat '$Seat' is not a lower-case seat name." }

function Hide-Home {
    param([string] $Text)
    if ($null -eq $homePattern -or [string]::IsNullOrEmpty($Text)) { return $Text }
    return $homePattern.Replace($Text, '~')
}

# ------------------------------------------------------------------------------------ stores
$storeArgs = @($Store | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($storeArgs.Count -eq 0) { Stop-Import '-Store is required: name each memory directory to import, by path.' }

$stores = [System.Collections.Generic.List[object]]::new()
$seenPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$seenLabels = @{}
foreach ($s in $storeArgs) {
    # Refused, not expanded: a pattern is discovery, and discovery is the Owner's (Article VIII).
    if ($s.IndexOfAny([char[]]@('*', '?')) -ge 0) {
        Stop-Import "-Store takes directories, not patterns: '$(Hide-Home $s)'. Name each directory."
    }
    $full = (Resolve-WikiDir $s).TrimEnd('\', '/')
    if (-not (Test-Path -LiteralPath $full -PathType Container)) {
        Stop-Import "store '$(Hide-Home $full)' is not a directory. Nothing was read or written."
    }
    if (-not $seenPaths.Add($full)) { continue }
    $parts = @($full -split '[\\/]+' | Where-Object { $_ -ne '' })
    if ($parts.Count -ge 4 -and $parts[-3] -ieq 'projects') {
        $project = $parts[-2]
        if ($homeSlug -and $project.Length -ge $homeSlug.Length -and
            $project.StartsWith($homeSlug, [System.StringComparison]::OrdinalIgnoreCase) -and
            ($project.Length -eq $homeSlug.Length -or $project[$homeSlug.Length] -eq '-')) {
            $project = '~' + $project.Substring($homeSlug.Length)
        }
        $label = ($parts[-4] -replace '[^A-Za-z0-9._~-]', '-') + '/' + ($project -replace '[^A-Za-z0-9._~-]', '-')
    } else {
        $label = $parts[-1] -replace '[^A-Za-z0-9._~-]', '-'
    }
    if ($seenLabels.ContainsKey($label)) {
        Stop-Import ("stores '$(Hide-Home $seenLabels[$label])' and '$(Hide-Home $full)' both take the label " +
            "'$label', so their evidence could not be told apart. Nothing was read or written.")
    }
    $seenLabels[$label] = $full
    $stores.Add([pscustomobject]@{ Label = $label; Path = $full })
}

# ------------------------------------------------------------------------------------ state
if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    . (Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'coord') '_common.ps1')
    try { $StateRoot = Get-CcxStateRoot }
    catch { Stop-Import "the inbox is not reachable: no -StateRoot, and $($_.Exception.Message)" }
}
$StateRoot = Resolve-WikiDir $StateRoot
if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) {
    Stop-Import "the inbox is not reachable: state root '$(Hide-Home $StateRoot)' does not exist."
}

# Every existing event, so a re-run can tell what it already wrote. A -RecordRepo that is named and
# missing, or that holds no log, stops the run: importing without the log would write every note a
# second time, and a wrong path would do it silently.
$existing = @()
$unreadableEvents = 0
$r = Read-WikiEventDir -Dir (Get-WikiInboxDir -StateRoot $StateRoot) -Source inbox
$inboxEvents = @($r.Events)
$unreadableEvents += $r.Skipped
$logEvents = @()
if (-not [string]::IsNullOrWhiteSpace($RecordRepo)) {
    $RecordRepo = Resolve-WikiDir $RecordRepo
    if (-not (Test-Path -LiteralPath $RecordRepo -PathType Container)) {
        Stop-Import "record repository '$(Hide-Home $RecordRepo)' does not exist. Nothing was read or written."
    }
    $eventsRoot = Get-WikiEventsRoot -RecordRepo $RecordRepo
    if (-not (Test-Path -LiteralPath $eventsRoot -PathType Container)) {
        Stop-Import ("record repository '$(Hide-Home $RecordRepo)' holds no wiki/events directory, so it is not " +
            'the record, or it has never been compiled. Pass the right one, or leave -RecordRepo out. Nothing was read or written.')
    }
    $r = Read-WikiEventDir -Dir $eventsRoot -Source log -Recurse
    $logEvents = @($r.Events)
    $unreadableEvents += $r.Skipped
}
if ([string]::IsNullOrWhiteSpace($RecordRepo)) {
    [Console]::Error.WriteLine(('wiki import: WARNING: no -RecordRepo, so events already compiled into the log are not ' +
            'seen. After a compile, a re-run without it imports every note again.'))
}
$existing = @(Merge-WikiEvent -Log $logEvents -Inbox $inboxEvents)

function ConvertTo-Text {
    <# A field as the comparison sees it: absent and empty are the same thing. #>
    param($Value)
    if ($null -eq $Value) { return '' }
    return [string]$Value
}

function Get-EventText {
    <#
    .SYNOPSIS
        An event's summary and body exactly as its file holds them.
    .DESCRIPTION
        The shared reader parses with ConvertFrom-Json, which turns a string shaped like an ISO stamp
        into a [datetime]. Cast back, it renders in the current culture, compares unequal to the
        note, and every run would supersede the note again. So when either field came back as a
        date, the file is read again with System.Text.Json, which leaves strings alone.
    #>
    param($Item)
    $summary = $Item.summary
    $body = $Item.body
    if ($summary -is [datetime] -or $body -is [datetime]) {
        if ([string]$Item._source -ceq 'log') {
            # Found by file name, not rebuilt from the stamp's month: the compile job may file an
            # event elsewhere, and a missed file here would supersede the note on every run.
            if ($null -eq $script:LogFiles) {
                $script:LogFiles = @{}
                foreach ($f in [System.IO.Directory]::EnumerateFiles((Get-WikiEventsRoot -RecordRepo $RecordRepo), '*.json', [System.IO.SearchOption]::AllDirectories)) {
                    $script:LogFiles[[System.IO.Path]::GetFileNameWithoutExtension($f)] = $f
                }
            }
            $path = $script:LogFiles[[string]$Item.id]
        } else { $path = Join-Path (Get-WikiInboxDir -StateRoot $StateRoot) "$($Item.id).json" }
        try {
            $doc = [System.Text.Json.JsonDocument]::Parse([System.IO.File]::ReadAllText($path))
            try {
                $prop = [System.Text.Json.JsonElement]::new()
                if ($doc.RootElement.TryGetProperty('summary', [ref]$prop)) { $summary = $prop.GetString() }
                if ($doc.RootElement.TryGetProperty('body', [ref]$prop)) { $body = $prop.GetString() }
            } finally { $doc.Dispose() }
        } catch {
            # The file went between the read and now. The cast is the best left.
            $null = $_
        }
    }
    return @((ConvertTo-Text $summary), (ConvertTo-Text $body))
}
$script:LogFiles = $null

function Get-TextHash {
    <# A note's text as one short, stable token, so a merge record can say which text it merged. #>
    param([string] $Summary, [string] $Body)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Summary + "`n" + $Body)
    return 'sha256:' + [System.Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
}

# The line an imported body opens with. It carries the note's own date, which `ts` cannot: `ts` is
# the write clock (FR-004), so every event one run writes shares one stamp whatever its note's age.
$script:SourceDateLine = [regex]::new('\ASource note last modified: (\d{4}-\d{2}-\d{2})\.(?:\n\n|\z)')

function Split-SourceDate {
    <# An imported body as its date and the note's text. With no date line: '' and the body whole. #>
    param([string] $Body)
    $m = $script:SourceDateLine.Match($Body)
    if ($m.Success) { return @($m.Groups[1].Value, $Body.Substring($m.Length)) }
    return @('', $Body)
}

function Get-LaterDate {
    <# The later of two yyyy-MM-dd dates. '' is no date, and sorts before every date. #>
    param([string] $A, [string] $B)
    if ([string]::CompareOrdinal($B, $A) -gt 0) { return $B }
    return $A
}

function Get-EffectiveDate {
    <# An entry's own date, or a later one from a note merged into it: that note re-dated the text. #>
    param($Entry)
    $d = [string]$Entry.Date
    foreach ($x in $Entry.MergedDates) { $d = Get-LaterDate $d $x }
    return $d
}

# key -> list of entries: every existing content event, then every note this run plans to write.
# An entry is @{ Id; Key; Evidence; Summary; Text; Date; TsKey; Current; Candidate; MergedDates }.
# Text is the body without its date line, so a date alone never reads as a changed note.
$byKey = @{}
# evidence -> the newest existing event citing it, on ANY key. Evidence names one note file, so this
# is the note's own last import even after its name, and so its key, changed.
$byEvidence = @{}
function Add-KeyEntry {
    param([string] $Key, $Entry)
    if (-not $byKey.ContainsKey($Key)) { $byKey[$Key] = [System.Collections.Generic.List[object]]::new() }
    $byKey[$Key].Add($Entry)
}
# An event is CURRENT unless another event supersedes it or a later `retire` withdrew its key: the
# guard's first two rules. Its third rule, the newer event on a key hiding the older, is left out
# on purpose, so both sides of a conflict pair still count as current and a third store holding
# either text merges into it.
$supersededIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$retiredAt = @{}
foreach ($ev in $existing) {
    foreach ($x in @($ev.supersedes)) { if ($null -ne $x) { [void]$supersededIds.Add([string]$x) } }
    if ([string]$ev.type -ceq 'retire') {
        $k = [string]$ev.key
        if (-not $retiredAt.ContainsKey($k) -or [string]::CompareOrdinal([string]$ev._tsKey, $retiredAt[$k]) -gt 0) {
            $retiredAt[$k] = [string]$ev._tsKey
        }
    }
}
function Test-Current {
    param($Ev)
    $k = [string]$Ev.key
    return -not $supersededIds.Contains([string]$Ev.id) -and
        -not ($retiredAt.ContainsKey($k) -and [string]::CompareOrdinal([string]$Ev._tsKey, $retiredAt[$k]) -lt 0)
}

# The two record kinds this script writes beside the notes, read back so a re-run knows them.
#   memory-merge/<slug>/<store>  a note with the same text as a current event: `kept`, `merged`,
#                                `text` (a hash of the merged note's text) and `date` lines.
#   memory-held/<slug>/<store>   a note older than a different text on its key: `kept`, `held`,
#                                `text` and `date` lines.
# "<key>|<evidence>|<text hash>" for every note a merge record covers, as it read when merged. Keyed
# on the MERGED note's own text, not on whether the event it merged into is still current: an Owner
# who retires or supersedes that event has withdrawn the text, and the merged copy must not come
# back on the next run.
$mergedTexts = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
# "<key>|<kept evidence>|<text hash>" -> the newest date a current merge record gives that text.
$mergeDates = @{}
# "<key>|<evidence>" -> the newest CURRENT held record for that note: @{ Id; TsKey; Hash; Date }.
# A re-run skips the note while this record still describes it, and any later write about the
# note supersedes it.
$heldRecord = @{}
$entries = [System.Collections.Generic.List[object]]::new()
foreach ($ev in $existing) {
    $k = [string]$ev.key
    if ([string]$ev.type -cin $script:WikiMarkerTypes) { continue }
    $isMerge = $k.StartsWith('memory-merge/')
    if ($isMerge -or $k.StartsWith('memory-held/')) {
        $segments = $k.Split('/')
        $base = 'memory/' + $segments[1]
        $f = @{}
        foreach ($line in ((ConvertTo-Text $ev.body) -split "`n")) {
            # To the end of the line, not to the first space: a file name may hold one.
            if ($line -match '^(kept|merged|held|text|date): (.+?)\s*$' -and -not $f.ContainsKey($Matches[1])) { $f[$Matches[1]] = $Matches[2] }
        }
        $live = Test-Current $ev
        if ($isMerge) {
            if ($f['merged'] -and $f['text']) { [void]$mergedTexts.Add("$base|$($f['merged'])|$($f['text'])") }
            if ($live -and $f['kept'] -and $f['text'] -and [string]$f['date'] -match '^\d{4}-\d{2}-\d{2}$') {
                $mk = "$base|$($f['kept'])|$($f['text'])"
                $mergeDates[$mk] = Get-LaterDate ([string]$mergeDates[$mk]) $f['date']
            }
        } elseif ($live -and $f['held'] -and $f['text']) {
            $rk = "$base|$($f['held'])"
            if (-not $heldRecord.ContainsKey($rk) -or [string]::CompareOrdinal([string]$ev._tsKey, $heldRecord[$rk].TsKey) -gt 0) {
                $heldRecord[$rk] = [pscustomobject]@{ Id = [string]$ev.id; TsKey = [string]$ev._tsKey; Hash = $f['text']; Date = [string]$f['date'] }
            }
        }
        continue
    }
    $text = Get-EventText $ev
    $split = Split-SourceDate $text[1]
    $date = $split[0]
    # No date line. An event this script wrote before notes carried a date is left undated, which
    # ranks it before every note. Any other event, written by a seat, is dated by the day it was
    # written, as a reader ages it: a note older than an Owner's ruling must not outrank it.
    if (-not $date -and -not ([string]$ev.evidence).StartsWith('memory:')) {
        $date = ([datetime]$ev._utc).ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
    }
    $entry = [pscustomobject]@{
        Id = [string]$ev.id; Key = $k; Evidence = [string]$ev.evidence; Summary = $text[0]; Text = $split[1]
        Date = $date; TsKey = [string]$ev._tsKey; Current = (Test-Current $ev); Candidate = $null
        MergedDates = [System.Collections.Generic.List[string]]::new(); Gone = $false
    }
    $entries.Add($entry)
    Add-KeyEntry $k $entry
    $prev = $byEvidence[$entry.Evidence]
    if ($null -eq $prev -or [string]::CompareOrdinal($entry.TsKey, $prev.TsKey) -gt 0) { $byEvidence[$entry.Evidence] = $entry }
}
# A merge record's date counts only for the text it merged, so an edit of the kept note drops it.
foreach ($entry in $entries) {
    $mk = "$($entry.Key)|$($entry.Evidence)|$(Get-TextHash $entry.Summary $entry.Text)"
    if ($mergeDates.ContainsKey($mk)) { $entry.MergedDates.Add($mergeDates[$mk]) }
}

# ------------------------------------------------------------------------------------ parsing
function ConvertFrom-QuotedScalar {
    <#
    .SYNOPSIS
        The inside of a YAML double-quoted scalar, escapes undone, or $null when it is not one.
    .DESCRIPTION
        $null when text follows the closing quote. Strict YAML would reject that line, but notes
        carry it: a plain description that opens with a quoted phrase. Reading it as a quoted
        scalar kept only the phrase, so the caller reads it as plain instead.
    #>
    param([string] $Text)
    $sb = [System.Text.StringBuilder]::new()
    $i = 1
    while ($i -lt $Text.Length) {
        $ch = $Text[$i]
        if ($ch -eq '"') { break }
        if ($ch -eq '\' -and $i + 1 -lt $Text.Length) {
            $n = $Text[$i + 1]
            $i += 2
            switch -CaseSensitive ([string]$n) {
                'n' { [void]$sb.Append("`n") }
                't' { [void]$sb.Append("`t") }
                'r' { }
                '0' { }
                'u' {
                    if ($i + 4 -le $Text.Length -and $Text.Substring($i, 4) -match '^[0-9A-Fa-f]{4}$') {
                        [void]$sb.Append([char][Convert]::ToInt32($Text.Substring($i, 4), 16)); $i += 4
                    } else { [void]$sb.Append('u') }
                }
                'x' {
                    if ($i + 2 -le $Text.Length -and $Text.Substring($i, 2) -match '^[0-9A-Fa-f]{2}$') {
                        [void]$sb.Append([char][Convert]::ToInt32($Text.Substring($i, 2), 16)); $i += 2
                    } else { [void]$sb.Append('x') }
                }
                default { [void]$sb.Append($n) }
            }
            continue
        }
        [void]$sb.Append($ch)
        $i++
    }
    if ($i -lt $Text.Length) {
        $after = $Text.Substring($i + 1).Trim()
        if ($after -and -not $after.StartsWith('#')) { return $null }
    }
    return $sb.ToString()
}

function ConvertFrom-YamlScalar {
    <#
    .SYNOPSIS
        One top-level scalar from the note's front matter: its first line and its continuation lines.
    .DESCRIPTION
        The subset the memory tool writes: plain (on one line or several), double-quoted,
        single-quoted, and `|` or `>` blocks. A value is used as one line or as body text, so line
        folding is approximate on purpose; nothing downstream depends on YAML's exact folding.
    #>
    param([string] $First, $Cont)
    $v = $First.Trim()
    $more = @($Cont | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
    if ($v -match '^[|>][-+0-9]*$') { return ($more -join "`n") }
    $plain = ((@($v) + $more) | Where-Object { $_ -ne '' }) -join ' '
    if ($v.StartsWith('"')) {
        $quoted = ConvertFrom-QuotedScalar $plain
        if ($null -ne $quoted) { return $quoted }
        return $plain
    }
    if ($v.StartsWith("'")) {
        $m = [regex]::Match($plain, "^'((?:[^']|'')*)'(.*)$")
        if (-not $m.Success) { return $plain.Substring(1).Replace("''", "'") }
        $after = $m.Groups[2].Value.Trim()
        if ($after -and -not $after.StartsWith('#')) { return $plain }
        return $m.Groups[1].Value.Replace("''", "'")
    }
    return $plain
}

function Read-MemoryNote {
    <# The note's name, description, type and body, or $null when it has no front matter. #>
    param([string] $Path)
    $text = [System.IO.File]::ReadAllText($Path)
    $text = $text.TrimStart([char]0xFEFF).Replace("`r`n", "`n").Replace("`r", "`n")
    $lines = $text.Split("`n")
    if ($lines.Count -lt 2 -or $lines[0].TrimEnd() -cne '---') { return $null }
    $end = -1
    for ($i = 1; $i -lt $lines.Count; $i++) {
        $t = $lines[$i].TrimEnd()
        if ($t -ceq '---' -or $t -ceq '...') { $end = $i; break }
    }
    if ($end -lt 0) { return $null }

    $top = @{}
    $current = $null
    for ($i = 1; $i -lt $end; $i++) {
        $l = $lines[$i]
        if ($l -match '^([A-Za-z_][A-Za-z0-9_-]*):(.*)$') {
            $current = [pscustomobject]@{ First = $Matches[2]; Cont = [System.Collections.Generic.List[string]]::new() }
            if (-not $top.ContainsKey($Matches[1])) { $top[$Matches[1]] = $current }
        } elseif ($null -ne $current) {
            $current.Cont.Add($l)
        }
    }
    $get = { param($name) if ($top.ContainsKey($name)) { ConvertFrom-YamlScalar $top[$name].First $top[$name].Cont } else { $null } }

    $type = & $get 'type'
    if ($null -eq $type -and $top.ContainsKey('metadata')) {
        foreach ($l in $top['metadata'].Cont) {
            if ($l -match '^\s+type:(.*)$') { $type = ConvertFrom-YamlScalar $Matches[1] @(); break }
        }
    }
    $body = if ($end + 1 -lt $lines.Count) { $lines[($end + 1)..($lines.Count - 1)] -join "`n" } else { '' }
    $body = ($body -replace '^(?:[ \t]*\n)+', '').TrimEnd()
    return [pscustomobject]@{
        Name        = & $get 'name'
        Description = & $get 'description'
        Type        = if ($null -ne $type) { ([string]$type).Trim().ToLowerInvariant() } else { $null }
        Body        = $body
    }
}

function Get-Slug {
    param([string] $Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return '' }
    $s = ($Text.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    if ($s.Length -gt $SlugMax) { $s = $s.Substring(0, $SlugMax).TrimEnd('-') }
    return $s
}

function Get-OneLine {
    <# Whitespace runs to one space, and any other control character dropped. #>
    param([string] $Text)
    if ($null -eq $Text) { return '' }
    return (($Text -replace '\s+', ' ') -replace '[\x00-\x1F\x7F]', '').Trim()
}

function Get-Cut {
    <# The first $Length characters, never splitting a surrogate pair. #>
    param([string] $Text, [int] $Length)
    if ($Text.Length -le $Length) { return $Text }
    if ($Length -gt 0 -and [char]::IsHighSurrogate($Text[$Length - 1])) { $Length-- }
    return $Text.Substring(0, $Length)
}

# ------------------------------------------------------------------------------------ plan
$counts = [ordered]@{
    seen = 0; imported = 0; superseded = 0; unchanged = 0; merged = 0; held = 0; older_superseded = 0
    refused = 0; not_written = 0; no_front_matter = 0; unreadable = 0; conflicts = 0; home_normalised = 0
    summary_truncated = 0; body_truncated = 0; type_defaulted = 0
}
$refusedNotes = [System.Collections.Generic.List[object]]::new()
$noFrontMatter = [System.Collections.Generic.List[string]]::new()
$unreadableNotes = [System.Collections.Generic.List[string]]::new()

# Notes this run will write or hold, in store and file order.
$candidates = [System.Collections.Generic.List[object]]::new()
# Notes with no import of their own, held for pass 2.
$pending = [System.Collections.Generic.List[object]]::new()
# Notes whose text is already current on their key, from another store.
$merges = [System.Collections.Generic.List[object]]::new()

function New-CandidateEntry {
    <# The entry a note this run plans to write adds to its key, so a later note can merge into it. #>
    param($Cand)
    $e = [pscustomobject]@{
        Id = $null; Key = $Cand.Key; Evidence = $Cand.Evidence; Summary = $Cand.Summary; Text = $Cand.Text
        Date = $Cand.Date; TsKey = ''; Current = $true; Candidate = $Cand
        MergedDates = [System.Collections.Generic.List[string]]::new()
    }
    $Cand.Entry = $e
    Add-KeyEntry $Cand.Key $e
}

function Get-StoreSlug {
    param([string] $Label)
    $s = ($Label.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    if ($s.Length -gt $StoreSlugMax) { $s = $s.Substring(0, $StoreSlugMax).TrimEnd('-') }
    if (-not $s) { $s = 'store' }
    return $s
}

function Get-EvidenceLabel {
    <# The store label out of memory:<label>/<file>. #>
    param([string] $Evidence)
    if ($Evidence -match '^memory:(.+)/[^/]+$') { return $Matches[1] }
    return $Evidence
}

foreach ($st in $stores) {
    $files = @([System.IO.Directory]::EnumerateFiles($st.Path, '*', [System.IO.SearchOption]::TopDirectoryOnly) |
            Where-Object { [System.IO.Path]::GetExtension($_) -ieq '.md' -and [System.IO.Path]::GetFileName($_) -ine 'MEMORY.md' })
    [System.Array]::Sort($files, [System.StringComparer]::Ordinal)
    foreach ($file in $files) {
        $fileName = [System.IO.Path]::GetFileName($file)
        $where = "$($st.Label)/$fileName"
        $counts.seen++
        try {
            $note = Read-MemoryNote $file
            # The note's own date: the day its file was last written, in UTC. The notes carry no date
            # in their front matter, so the file is the only witness.
            $srcDate = [System.IO.File]::GetLastWriteTimeUtc($file).ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
        } catch { $counts.unreadable++; $unreadableNotes.Add($where); continue }
        if ($null -eq $note) { $counts.no_front_matter++; $noFrontMatter.Add($where); continue }

        $slug = Get-Slug $note.Name
        if (-not $slug) { $slug = Get-Slug ([System.IO.Path]::GetFileNameWithoutExtension($fileName)) }
        if (-not $slug) {
            $counts.refused++
            $refusedNotes.Add([pscustomobject]@{ note = $where; class = 'no usable name for a key' })
            continue
        }
        $key = "memory/$slug"
        $type = $TypeMap[[string]$note.Type]
        if (-not $type) { $type = 'lesson'; $counts.type_defaulted++ }
        $evidence = "memory:$where"

        $description = Hide-Home ([string]$note.Description)
        $body = Hide-Home ([string]$note.Body)
        if ($description -cne [string]$note.Description -or $body -cne [string]$note.Body) { $counts.home_normalised++ }

        $summary = Get-OneLine $description
        if (-not $summary) {
            $flat = Get-OneLine ((($body -split "`n") | Where-Object { $_ -notmatch '^\s*#' }) -join ' ')
            $summary = if ($flat -match '^(.+?[.!?])(\s|$)') { $Matches[1] } else { $flat }
        }
        if (-not $summary) { $summary = $slug }
        if ($summary.Length -gt $SummaryMax) {
            # The full description moves into the body, so the cut loses nothing.
            if ($description) { $body = "Description: $(Get-OneLine $description)`n`n$body".TrimEnd() }
            $summary = (Get-Cut $summary ($SummaryMax - 3)).TrimEnd() + '...'
            $counts.summary_truncated++
        }
        $dateLine = "Source note last modified: $srcDate."
        # The date line and the blank line after it come out of the body's limit.
        $textMax = $BodyMax - $dateLine.Length - 2
        # A long note imported before the date line was cut at the whole limit. Its old cut is kept
        # beside the new one, so the move alone does not read as an edit on the first run after.
        $legacyText = $null
        if ($body.Length -gt $textMax) {
            if ($body.Length -gt $BodyMax) { $legacyText = (Get-Cut $body ($BodyMax - $TruncatedMarker.Length)).TrimEnd() + $TruncatedMarker }
            else { $legacyText = $body }
            $body = (Get-Cut $body ($textMax - $TruncatedMarker.Length)).TrimEnd() + $TruncatedMarker
            $counts.body_truncated++
        }

        # stale_after is the last day a query does not age the event, counted from the note's date,
        # so it turns stale on the day a native event written that day would. `ts` stays the clock.
        $staleAfter = [datetime]::ParseExact($srcDate, 'yyyy-MM-dd', [cultureinfo]::InvariantCulture).AddDays($script:WikiStaleDays).ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
        $item = [ordered]@{
            type = $type; key = $key; summary = $summary; evidence = $evidence
            body = $(if ($body) { "$dateLine`n`n$body" } else { $dateLine })
            stale_after = $staleAfter
        }
        $cand = [pscustomobject]@{
            Where = $where; Label = $st.Label; File = $fileName; Key = $key; Slug = $slug; Evidence = $evidence
            Summary = $summary; Text = $body; Date = $srcDate; Hash = (Get-TextHash $summary $body); Item = $item
            LegacyHash = $(if ($null -ne $legacyText) { Get-TextHash $summary $legacyText } else { $null })
            Prior = $null; Entry = $null; Held = $false; Kept = $null; Tier = 0; Conflict = $false
            Supersedes = [System.Collections.Generic.List[string]]::new()
            Outranked = [System.Collections.Generic.List[string]]::new()
            Action = 'imported'; Status = $null; Class = $null
        }

        # Held already, and the live hold still describes this note: the same text, no later date,
        # and nothing of the note written since. Any of those moved, and the note is looked at again.
        $prior = $byEvidence[$evidence]
        $hr = $heldRecord["$key|$evidence"]
        if ($null -ne $hr -and $hr.Hash -ceq $cand.Hash -and [string]::CompareOrdinal($srcDate, $hr.Date) -le 0 -and
            ($null -eq $prior -or [string]::CompareOrdinal($hr.TsKey, $prior.TsKey) -gt 0)) {
            $counts.unchanged++
            continue
        }

        # Rule 1, in the first pass: this note's own earlier import, found by evidence on any key.
        # Every supersede is planned before any merge is decided, so a text this run replaces is no
        # longer current when pass 2 looks for one to merge into. The date line is not compared: a
        # file whose date moved and whose text did not is the same note.
        if ($null -ne $prior) {
            if ($prior.Key -ceq $key -and $prior.Summary -ceq $summary -and
                ($prior.Text -ceq $body -or ($null -ne $legacyText -and -not $prior.Date -and $prior.Text -ceq $legacyText))) {
                # Unchanged. The file's date still dates the text for ranking, which dates an event
                # imported without one, and counts a re-save with the text unchanged.
                $prior.Date = Get-LaterDate $prior.Date $srcDate
                $counts.unchanged++
                continue
            }
            # Changed text, or a changed name and so a changed key: the new event replaces the old.
            $cand.Prior = $prior
            $cand.Action = 'superseded'
            $prior.Current = $false
            New-CandidateEntry $cand
            $candidates.Add($cand)
            continue
        }
        $pending.Add($cand)
    }
}

# Pass 2: notes with no import of their own yet. Newest first, so where several stores hold one text
# the event kept is the newest copy; then by store label and file, so the order never depends on
# the order -Store named the stores in.
$pending.Sort([System.Comparison[object]] {
        param($x, $y)
        $d = [string]::CompareOrdinal($y.Date, $x.Date)
        if ($d -ne 0) { return $d }
        $d = [string]::CompareOrdinal($x.Label, $y.Label)
        if ($d -ne 0) { return $d }
        return [string]::CompareOrdinal($x.File, $y.File)
    })
foreach ($n in $pending) {
    $onKey = if ($byKey.ContainsKey($n.Key)) { $byKey[$n.Key] } else { @() }
    $same = $null
    foreach ($e in $onKey) { if ($e.Current -and $e.Summary -ceq $n.Summary -and $e.Text -ceq $n.Text) { $same = $e; break } }
    # Merged before, and unchanged since: nothing to do, whatever became of the event it joined. Its
    # date still dates the kept text for ranking, as rule 1 does for a note's own import.
    if ($mergedTexts.Contains("$($n.Key)|$($n.Evidence)|$($n.Hash)") -or
        ($null -ne $n.LegacyHash -and $mergedTexts.Contains("$($n.Key)|$($n.Evidence)|$($n.LegacyHash)"))) {
        if ($null -ne $same) { $same.MergedDates.Add($n.Date) }
        $counts.unchanged++
        continue
    }
    if ($null -ne $same) {
        # Rule 3: the same text is current on this key, from somewhere else. Its date counts for the
        # kept text, so an older different text cannot outrank a text this store confirmed later.
        [void]$mergedTexts.Add("$($n.Key)|$($n.Evidence)|$($n.Hash)")
        $same.MergedDates.Add($n.Date)
        $merges.Add([pscustomobject]@{ Note = $n; Target = $same })
        continue
    }
    New-CandidateEntry $n
    $candidates.Add($n)
}

# Rule 4: on each key a note writes to, the newest date decides. A note is HELD, and not written,
# when a different text on its key carries a later date. Undated events, imported before notes
# carried a date, sort before every date.
function Test-SameText { param($A, $B) return ($A.Summary -ceq $B.Summary -and $A.Text -ceq $B.Text) }
function Test-Contender {
    <# A text on its key right now: current, not replaced this run, and not a note that was refused. #>
    param($E)
    if (-not $E.Current) { return $false }
    if ($null -eq $E.Candidate) { return -not $E.Gone }
    return $E.Candidate.Status -cnotin @('refused', 'failed')
}
function Get-Rank {
    <# Orders the texts on a key: date, then a note this run writes over an event already there. #>
    param($E)
    $order = if ($null -ne $E.Candidate) { '1|' + $E.Candidate.Label + '/' + $E.Candidate.File } else { '0|' + $E.TsKey }
    return (Get-EffectiveDate $E) + '|' + $order
}
$candKeys = [System.Collections.Generic.List[string]]::new()
$candKeySet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
foreach ($c in $candidates) { if ($candKeySet.Add($c.Key)) { $candKeys.Add($c.Key) } }

function Resolve-Plan {
    <#
    .SYNOPSIS
        Decide, for every note not yet written, whether it is held, and what a written one replaces.
    .DESCRIPTION
        Runs again after a round in which a note that outranked others was refused, so a note held
        only behind a text that never reached the wiki is looked at without it.
    #>
    $open = @($candidates | Where-Object { $null -eq $_.Status })
    foreach ($c in $open) {
        $c.Held = $false; $c.Kept = $null; $c.Tier = 0; $c.Conflict = $false
        $c.Supersedes.Clear(); $c.Outranked.Clear()
        # A note's own earlier import is not a rival to it.
        if ($null -ne $c.Prior) { $c.Prior.Current = $false }
    }
    # Held until nothing changes: a note held on its own key leaves its earlier import there
    # current, and that import can in turn outrank a note from another store.
    do {
        $changed = $false
        foreach ($k in $candKeys) {
            $contenders = @($byKey[$k] | Where-Object { Test-Contender $_ })
            foreach ($ce in $contenders) {
                $c = $ce.Candidate
                if ($null -eq $c -or $null -ne $c.Status -or $c.Held) { continue }
                $mine = Get-EffectiveDate $ce
                foreach ($x in $contenders) {
                    if (-not [object]::ReferenceEquals($x, $ce) -and -not (Test-SameText $x $ce) -and
                        [string]::CompareOrdinal((Get-EffectiveDate $x), $mine) -gt 0) {
                        $c.Held = $true
                        $changed = $true
                        if ($null -ne $c.Prior -and $c.Prior.Key -ceq $c.Key) { $c.Prior.Current = $true }
                        break
                    }
                }
            }
        }
    } while ($changed)
    foreach ($c in $open) {
        if (-not $c.Held) { continue }
        $best = $null
        $bestRank = $null
        foreach ($x in $byKey[$c.Key]) {
            if (-not (Test-Contender $x) -or (Test-SameText $x $c.Entry)) { continue }
            if ($null -ne $x.Candidate -and $null -eq $x.Candidate.Status -and $x.Candidate.Held) { continue }
            $r = Get-Rank $x
            if ($null -eq $best -or [string]::CompareOrdinal($r, $bestRank) -gt 0) { $best = $x; $bestRank = $r }
        }
        $c.Kept = $best
    }
    foreach ($k in $candKeys) {
        $onKey = $byKey[$k]
        $winners = [System.Collections.Generic.List[object]]::new()
        foreach ($e in $onKey) { if ($null -ne $e.Candidate -and $null -eq $e.Candidate.Status -and -not $e.Candidate.Held) { $winners.Add($e.Candidate) } }
        # Two notes with one date write in store-label order, one batch each, so the later label is
        # the newer event and the one a reader sees. In one batch, one millisecond could order them
        # by the random end of the id.
        $winners.Sort([System.Comparison[object]] {
                param($x, $y)
                $d = [string]::CompareOrdinal($x.Label, $y.Label)
                if ($d -ne 0) { return $d }
                return [string]::CompareOrdinal($x.File, $y.File)
            })
        for ($i = 0; $i -lt $winners.Count; $i++) {
            $w = $winners[$i]
            $w.Tier = $i
            $mine = Get-EffectiveDate $w.Entry
            if ($null -ne $w.Prior) { $w.Supersedes.Add($w.Prior.Id) }
            foreach ($x in $onKey) {
                if ([object]::ReferenceEquals($x, $w.Entry) -or -not (Test-Contender $x)) { continue }
                if ($null -ne $x.Candidate -and $null -eq $x.Candidate.Status) { continue }
                if ($null -eq $x.Candidate -and [string]::CompareOrdinal((Get-EffectiveDate $x), $mine) -lt 0) {
                    # An older text on the key, from another store or undated: this note replaces it.
                    if ($w.Supersedes -cnotcontains $x.Id) { $w.Supersedes.Add($x.Id); $w.Outranked.Add($x.Id) }
                } elseif (-not (Test-SameText $x $w.Entry)) {
                    $w.Conflict = $true
                }
            }
            for ($j = 0; $j -lt $i; $j++) { if (-not (Test-SameText $winners[$j].Entry $w.Entry)) { $w.Conflict = $true } }
            # A hold the note left behind is history once the note is written.
            foreach ($id in (Get-HoldIds $w)) { if ($w.Supersedes -cnotcontains $id) { $w.Supersedes.Add($id) } }
            if ($w.Supersedes.Count -gt 0) { $w.Item.supersedes = @($w.Supersedes) } else { $w.Item.Remove('supersedes') }
        }
    }
}

function Get-HoldIds {
    <# The live hold records about this note: on its key, and on its old key after a rename. #>
    param($Cand)
    $ids = [System.Collections.Generic.List[string]]::new()
    $keys = @($Cand.Key)
    if ($null -ne $Cand.Prior -and $Cand.Prior.Key -cne $Cand.Key) { $keys += $Cand.Prior.Key }
    foreach ($k in $keys) {
        $hr = $heldRecord["$k|$($Cand.Evidence)"]
        if ($null -ne $hr -and $ids -cnotcontains $hr.Id) { $ids.Add($hr.Id) }
    }
    return , $ids
}

# ------------------------------------------------------------------------------------ write
$writeScript = Join-Path $PSScriptRoot 'write.ps1'
# The pwsh that ships beside this one, not the host process: a script hosted in another program
# would otherwise start that program.
$pwshExe = Join-Path $PSHOME $(if ($IsWindows) { 'pwsh.exe' } else { 'pwsh' })
# Installed as a .NET tool, PSHOME holds no pwsh executable. This process is then the best left.
if (-not (Test-Path -LiteralPath $pwshExe -PathType Leaf)) { $pwshExe = (Get-Process -Id $PID).Path }

function Invoke-WriteBatch {
    <#
    .SYNOPSIS
        Hand a list of events to write.ps1 -FromJson and return its per-event results.
    .DESCRIPTION
        write.ps1 prints one result per event whenever it got as far as writing, including when
        one write failed and it exits 2. So the results decide, not the exit code. No results at all
        means it stopped before writing anything.
    #>
    param($Items, [string] $Stage, [bool] $First)
    if ($Items.Count -eq 0) { return @() }
    $before = if ($First) { 'Nothing was written.' } else { "The batches before it were already written; the $Stage batch was not." }
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('wiki-import-' + [guid]::NewGuid().ToString('N') + '.json')
    $out = @()
    $code = -1
    try {
        $payload = ConvertTo-Json -InputObject @($Items) -Depth 5
        [System.IO.File]::WriteAllText($tmp, $payload, [System.Text.UTF8Encoding]::new($false))
        $argv = @('-NoProfile', '-File', $writeScript, '-FromJson', $tmp, '-Seat', $Seat, '-StateRoot', $StateRoot)
        if ($WhatIf) { $argv += '-CheckOnly' }
        # A non-zero exit is data here, never a thrown error, whatever the caller's preference.
        $PSNativeCommandUseErrorActionPreference = $false
        $ErrorActionPreference = 'Continue'
        $out = @(& $pwshExe @argv)
        $code = $LASTEXITCODE
    } catch {
        Stop-Import "write.ps1 could not be started for the $Stage batch: $($_.Exception.Message). $before"
    } finally {
        $ErrorActionPreference = 'Stop'
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
    $results = $null
    $text = ($out | ForEach-Object { [string]$_ }) -join "`n"
    if ($text.TrimStart().StartsWith('[')) {
        try { $results = @($text | ConvertFrom-Json -ErrorAction Stop) } catch { $results = $null }
    }
    if ($null -eq $results) { Stop-Import "write.ps1 could not run the $Stage batch (exit $code). $before" }
    if ($results.Count -ne $Items.Count) {
        Stop-Import "write.ps1 returned $($results.Count) results for $($Items.Count) events in the $Stage batch; check the inbox by hand."
    }
    return $results
}

function Get-RefusalClass {
    <# The class alone for a scan refusal, and the schema reason otherwise. Never a value. #>
    param([string] $Reason)
    if ($Reason -match '^the leak scan matched: (.+)\. Nothing was written\.$') { return $Matches[1] }
    return $Reason.TrimEnd('.')
}

# One batch per tier of notes, then one for the records, because a record is only true if the note
# it points at was written.
$firstBatch = $true
$outrankedBy = @{}
$entryById = @{}
foreach ($e in $entries) { $entryById[$e.Id] = $e }
# Rounds: plan, then write one batch per tier. A refused note that outranked others ends its round
# early for them, and the next round plans again without it. Each round writes or refuses at least
# one note, so the loop ends.
for ($round = 0; $round -le $candidates.Count; $round++) {
    Resolve-Plan
    $winners = @($candidates | Where-Object { $null -eq $_.Status -and -not $_.Held })
    if ($winners.Count -eq 0) { break }
    $maxTier = 0
    foreach ($c in $winners) { if ($c.Tier -gt $maxTier) { $maxTier = $c.Tier } }
    $lostARival = $false
    for ($t = 0; $t -le $maxTier; $t++) {
        $batch = @($winners | Where-Object { $_.Tier -eq $t })
        $stage = if ($t -eq 0 -and $round -eq 0) { 'notes' } else { "notes (round $($round + 1), tier $($t + 1))" }
        $results = @(Invoke-WriteBatch @($batch | ForEach-Object { $_.Item }) $stage $firstBatch)
        if ($batch.Count -gt 0) { $firstBatch = $false }
        for ($i = 0; $i -lt $results.Count; $i++) {
            $res = $results[$i]
            $c = $batch[$i]
            $c.Status = [string]$res.status
            if ($res.status -ceq 'refused' -or $res.status -ceq 'failed') {
                if ($res.status -ceq 'refused') {
                    $c.Class = Get-RefusalClass ([string]$res.reason)
                    $counts.refused++
                } else {
                    # Passed every check and could not be written: a disk or permission fault.
                    $c.Class = 'not written: ' + (Hide-Home ([string]$res.reason))
                    $counts.not_written++
                }
                $refusedNotes.Add([pscustomobject]@{ note = $c.Where; class = $c.Class })
                # Nothing of the note was written, so its own earlier import is still there.
                if ($null -ne $c.Prior) { $c.Prior.Current = $true }
                foreach ($h in $candidates) { if ($null -eq $h.Status -and $h.Held -and $h.Key -ceq $c.Key) { $lostARival = $true } }
                continue
            }
            if ($c.Action -ceq 'superseded') { $counts.superseded++ } else { $counts.imported++ }
            if ($c.Conflict) { $counts.conflicts++ }
            foreach ($id in $c.Supersedes) {
                if ($entryById.ContainsKey($id)) { $entryById[$id].Gone = $true }
            }
            foreach ($id in $c.Outranked) { if (-not $outrankedBy.ContainsKey($id)) { $outrankedBy[$id] = $c } }
        }
    }
    if (-not $lostARival) { break }
}
$counts.older_superseded = $outrankedBy.Count

function Test-NotWritten { param($Cand) return ($null -ne $Cand -and $Cand.Status -cin @('refused', 'failed')) }

# Held notes: every note still held, and every merge whose text this run outranked or held.
$heldNotes = [System.Collections.Generic.List[object]]::new()
foreach ($c in $candidates) { if ($null -eq $c.Status -and $c.Held) { $heldNotes.Add($c) } }
$recordItems = [System.Collections.Generic.List[object]]::new()
$recordMeta = [System.Collections.Generic.List[object]]::new()
$heldReport = [System.Collections.Generic.List[object]]::new()
foreach ($m in $merges) {
    $n = $m.Note
    $tc = $m.Target.Candidate
    if ($null -ne $tc -and $null -eq $tc.Status -and $tc.Held) {
        # The text it matched is held, so this copy is held behind the same text.
        $n.Held = $true; $n.Kept = $tc.Kept; $heldNotes.Add($n); continue
    }
    if ($null -eq $tc -and $outrankedBy.ContainsKey($m.Target.Id)) {
        # The text it matched was replaced this run by a newer one. A merge into it would record a
        # copy of a withdrawn text; the note is held behind the newer text instead.
        $n.Held = $true; $n.Kept = $outrankedBy[$m.Target.Id].Entry; $heldNotes.Add($n); continue
    }
    # A merge into a note this run failed to write would point at nothing. Its text is the refused
    # note's text, so it is refused for the same class.
    if (Test-NotWritten $tc) {
        if ($tc.Class.StartsWith('not written: ')) { $counts.not_written++ } else { $counts.refused++ }
        $refusedNotes.Add([pscustomobject]@{ note = $n.Where; class = $tc.Class })
        continue
    }
    # One merge record per merged store, on its own key, so a third store's record does not hide a
    # second's.
    $recordItems.Add([ordered]@{
            type     = 'decision'
            key      = "memory-merge/$($n.Slug)/$(Get-StoreSlug $n.Label)"
            summary  = "Merged memory note '$($n.Slug)' from $($n.Label) into $(Get-EvidenceLabel $m.Target.Evidence)`: same name, same text"
            evidence = $m.Target.Evidence
            body     = "kept: $($m.Target.Evidence)`nmerged: $($n.Evidence)`ntext: $($n.Hash)`ndate: $($n.Date)"
        })
    $recordMeta.Add([pscustomobject]@{ Kind = 'merge'; Note = $n })
}
foreach ($h in $heldNotes) {
    $kc = if ($null -ne $h.Kept) { $h.Kept.Candidate } else { $null }
    if ($null -eq $h.Kept -or (Test-NotWritten $kc)) {
        # Nothing the hold could point at reached the wiki. The next run looks at the note again.
        $counts.not_written++
        $refusedNotes.Add([pscustomobject]@{ note = $h.Where; class = 'not held: the newer note that outranks it was not written' })
        continue
    }
    $keptDate = Get-EffectiveDate $h.Kept
    if (-not $keptDate) { $keptDate = 'undated' }
    $summary = "Held memory note '$($h.Slug)' from $($h.Label), modified $($h.Date): older than the text kept from $(Get-EvidenceLabel $h.Kept.Evidence), modified $keptDate"
    if ($summary.Length -gt $SummaryMax) { $summary = (Get-Cut $summary ($SummaryMax - 3)).TrimEnd() + '...' }
    $item = [ordered]@{
        type     = 'decision'
        key      = "memory-held/$($h.Slug)/$(Get-StoreSlug $h.Label)"
        summary  = $summary
        evidence = $h.Evidence
        body     = "kept: $($h.Kept.Evidence)`nheld: $($h.Evidence)`ntext: $($h.Hash)`ndate: $($h.Date)"
    }
    # The hold replaces an earlier hold of the same note. After a rename it also retires the note's
    # import under its old name, since the file no longer carries that name.
    $sup = Get-HoldIds $h
    if ($null -ne $h.Prior -and $h.Prior.Key -cne $h.Key -and $sup -cnotcontains $h.Prior.Id) { $sup.Add($h.Prior.Id) }
    if ($sup.Count -gt 0) { $item.supersedes = @($sup) }
    $recordItems.Add($item)
    $recordMeta.Add([pscustomobject]@{ Kind = 'held'; Note = $h })
}
$recordResults = @(Invoke-WriteBatch $recordItems 'records' $firstBatch)
for ($i = 0; $i -lt $recordResults.Count; $i++) {
    $meta = $recordMeta[$i]
    $label = if ($meta.Kind -ceq 'merge') { 'merge record' } else { 'held record' }
    if ($recordResults[$i].status -ceq 'refused') {
        $counts.refused++
        $refusedNotes.Add([pscustomobject]@{ note = $meta.Note.Where; class = "${label}: " + (Get-RefusalClass ([string]$recordResults[$i].reason)) })
    } elseif ($recordResults[$i].status -ceq 'failed') {
        $counts.not_written++
        $refusedNotes.Add([pscustomobject]@{ note = $meta.Note.Where; class = "$label not written: " + (Hide-Home ([string]$recordResults[$i].reason)) })
    } elseif ($meta.Kind -ceq 'merge') {
        $counts.merged++
    } else {
        $counts.held++
        $heldReport.Add([pscustomobject]@{ note = $meta.Note.Where; behind = ([string]$meta.Note.Kept.Evidence -replace '^memory:', '') })
    }
}

# ------------------------------------------------------------------------------------ report
$seconds = [math]::Round($started.Elapsed.TotalSeconds, 1)
if ($Json) {
    [ordered]@{
        what_if              = [bool]$WhatIf
        stores               = @($stores | ForEach-Object { [ordered]@{ label = $_.Label; path = Hide-Home $_.Path } })
        counts               = $counts
        existing_unreadable  = $unreadableEvents
        refused_notes        = @($refusedNotes)
        held_notes           = @($heldReport)
        no_front_matter      = @($noFrontMatter)
        unreadable_notes     = @($unreadableNotes)
        seconds              = $seconds
    } | ConvertTo-Json -Depth 5
} else {
    if ($WhatIf) { Write-Output 'wiki import: -WhatIf, so NOTHING WAS WRITTEN. The counts are what a run would do.' }
    Write-Output "wiki import: read $($stores.Count) store(s), and only these:"
    foreach ($st in $stores) { Write-Output "  $($st.Label)  $(Hide-Home $st.Path)" }
    Write-Output "  existing events read: $($existing.Count), unreadable and skipped: $unreadableEvents"
    foreach ($k in $counts.Keys) { Write-Output ("  {0,-18} {1}" -f $k, $counts[$k]) }
    if ($refusedNotes.Count -gt 0) {
        Write-Output 'refused, not imported (store/file, class):'
        foreach ($x in $refusedNotes) { Write-Output "  $($x.note)  $($x.class)" }
    }
    if ($heldReport.Count -gt 0) {
        Write-Output 'held, older than a different text on the key (store/file, the note it is held behind):'
        foreach ($x in $heldReport) { Write-Output "  $($x.note)  $($x.behind)" }
    }
    if ($noFrontMatter.Count -gt 0) {
        Write-Output 'no front matter, skipped:'
        foreach ($x in $noFrontMatter) { Write-Output "  $x" }
    }
    if ($unreadableNotes.Count -gt 0) {
        Write-Output 'could not be read, skipped:'
        foreach ($x in $unreadableNotes) { Write-Output "  $x" }
    }
    Write-Output "  seconds            $seconds"
}
$needsLook = $counts.refused + $counts.not_written + $counts.unreadable + $unreadableEvents
exit $(if ($needsLook -gt 0) { 1 } else { 0 })
