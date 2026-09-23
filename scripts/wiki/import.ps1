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
        body      the note's body. Over 20000 characters it is cut, with a line saying the full
                  note is the evidence file.
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

    RE-RUNNING IS SAFE (FR-027). The existing events are read from the inbox, and from the log with
    -RecordRepo. For each note:
      1. The newest event with the SAME evidence, on any key, is the note's own earlier import.
         Same key, summary and body: skipped, even if someone has since superseded or retired it.
         Otherwise, a text edit or a rename: a new event that supersedes it.
      2. Otherwise, a note merged before whose text has not changed since is skipped, again
         whatever became of the event it merged into. An Owner who withdrew that text has
         withdrawn the copy too.
      3. Otherwise, a CURRENT event on the key with the same summary and body is a MERGE. Current
         means no event supersedes it and no `retire` withdrew it. The note is not written.
         Instead a `decision` on memory-merge/<slug>/<store> records it (FR-024): its summary
         names both stores, its evidence is the kept event's, and its body carries `kept:`,
         `merged:` and `text:` lines, the last a hash of the merged note's text.
      4. Otherwise the note is written. If the key holds different current text from another
         store, both are kept and neither supersedes the other: the newer is live, and lint files
         the pair (Story 4, scenario 2). The report counts these as conflicts.
    Rule 1 runs over every note before rules 2 to 4 run over any, so a text this run replaces is
    no longer current when a later note looks for one to merge into. It goes first at all so that
    two stores holding different text under one name do not trade places on every run.

    -WhatIf writes nothing. It runs every check, the leak scan included, through `write.ps1
    -CheckOnly`, and prints the same report.

    WITHOUT -RecordRepo, events already compiled into the log are not seen, and a re-run after a
    compile would import every note again. The run says so on stderr. A -RecordRepo that is named
    but holds no wiki/events directory is refused, because a wrong path would do the same silently.

    Exit codes:
        0  finished, and every note was imported, merged or already there
        1  finished, and something needs a look: a note refused or not written, or a note or an
           existing event that could not be read. Each is listed in the report.
        2  could not run: no -Store, a store that is not a directory, a pattern in -Store, two
           stores with one label, a bad -Seat, a -RecordRepo that is missing or holds no
           wiki/events, or `write.ps1` could not run a batch. Nothing was written in any of these
           cases, except when `write.ps1` failed on the second (merge) batch, which the message
           says.

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

# key -> list of @{ Id; Key; Evidence; Summary; Body; TsKey; Planned; Current }
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

# "<key>|<evidence>|<text hash>" for every note a merge record covers, as it read when merged. Keyed
# on the MERGED note's own text, not on whether the event it merged into is still current: an Owner
# who retires or supersedes that event has withdrawn the text, and the merged copy must not come
# back on the next run.
$mergedTexts = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
foreach ($ev in $existing) {
    $k = [string]$ev.key
    if ([string]$ev.type -cin $script:WikiMarkerTypes) { continue }
    if ($k.StartsWith('memory-merge/')) {
        $segments = $k.Split('/')
        $base = 'memory/' + $segments[1]
        $merged = $null
        $hash = $null
        foreach ($line in ((ConvertTo-Text $ev.body) -split "`n")) {
            # To the end of the line, not to the first space: a file name may hold one.
            if ($line -match '^merged: (.+?)\s*$') { $merged = $Matches[1] }
            elseif ($line -match '^text: (\S+)\s*$') { $hash = $Matches[1] }
        }
        if ($merged -and $hash) { [void]$mergedTexts.Add("$base|$merged|$hash") }
        continue
    }
    $text = Get-EventText $ev
    $current = -not $supersededIds.Contains([string]$ev.id) -and
        -not ($retiredAt.ContainsKey($k) -and [string]::CompareOrdinal([string]$ev._tsKey, $retiredAt[$k]) -lt 0)
    $entry = [pscustomobject]@{
        Id = [string]$ev.id; Key = $k; Evidence = [string]$ev.evidence; Summary = $text[0]
        Body = $text[1]; TsKey = [string]$ev._tsKey; Planned = $null; Current = $current
    }
    Add-KeyEntry $k $entry
    $prev = $byEvidence[$entry.Evidence]
    if ($null -eq $prev -or [string]::CompareOrdinal($entry.TsKey, $prev.TsKey) -gt 0) { $byEvidence[$entry.Evidence] = $entry }
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
    seen = 0; imported = 0; superseded = 0; unchanged = 0; merged = 0; refused = 0; not_written = 0
    no_front_matter = 0; unreadable = 0; conflicts = 0; home_normalised = 0
    summary_truncated = 0; body_truncated = 0; type_defaulted = 0
}
$refusedNotes = [System.Collections.Generic.List[object]]::new()
$noFrontMatter = [System.Collections.Generic.List[string]]::new()
$unreadableNotes = [System.Collections.Generic.List[string]]::new()

# Two batches. Notes first; merge records second, because a merge record is only true if the event
# it points at was written.
$noteItems = [System.Collections.Generic.List[object]]::new()
$noteMeta = [System.Collections.Generic.List[object]]::new()
$mergeItems = [System.Collections.Generic.List[object]]::new()
$mergeMeta = [System.Collections.Generic.List[object]]::new()
# Notes with no import of their own, held for pass 2.
$pending = [System.Collections.Generic.List[object]]::new()

foreach ($st in $stores) {
    $files = @([System.IO.Directory]::EnumerateFiles($st.Path, '*', [System.IO.SearchOption]::TopDirectoryOnly) |
            Where-Object { [System.IO.Path]::GetExtension($_) -ieq '.md' -and [System.IO.Path]::GetFileName($_) -ine 'MEMORY.md' })
    [System.Array]::Sort($files, [System.StringComparer]::Ordinal)
    foreach ($file in $files) {
        $fileName = [System.IO.Path]::GetFileName($file)
        $where = "$($st.Label)/$fileName"
        $counts.seen++
        try { $note = Read-MemoryNote $file }
        catch { $counts.unreadable++; $unreadableNotes.Add($where); continue }
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
        if ($body.Length -gt $BodyMax) {
            $body = (Get-Cut $body ($BodyMax - $TruncatedMarker.Length)).TrimEnd() + $TruncatedMarker
            $counts.body_truncated++
        }

        $item = [ordered]@{ type = $type; key = $key; summary = $summary; evidence = $evidence }
        if ($body) { $item.body = $body }

        # Rule 1, in the first pass: this note's own earlier import, found by evidence on any key.
        # Every supersede is planned before any merge is decided, so a text this run replaces is no
        # longer current when pass 2 looks for one to merge into.
        $prior = $byEvidence[$evidence]
        if ($null -ne $prior) {
            if ($prior.Key -ceq $key -and $prior.Summary -ceq $summary -and $prior.Body -ceq $body) { $counts.unchanged++; continue }
            # Changed text, or a changed name and so a changed key: the new event replaces the old.
            $item.supersedes = @($prior.Id)
            $prior.Current = $false
            Add-KeyEntry $key ([pscustomobject]@{
                    Id = $null; Key = $key; Evidence = $evidence; Summary = $summary; Body = $body; TsKey = ''
                    Planned = $noteItems.Count; Current = $true
                })
            $noteItems.Add($item)
            $noteMeta.Add([pscustomobject]@{ Where = $where; Action = 'superseded'; Conflict = $false })
            continue
        }
        $pending.Add([pscustomobject]@{
                Where = $where; Label = $st.Label; Key = $key; Slug = $slug; Evidence = $evidence
                Summary = $summary; Body = $body; Item = $item
            })
    }
}

# Pass 2: notes with no import of their own yet.
foreach ($n in $pending) {
    $entries = if ($byKey.ContainsKey($n.Key)) { $byKey[$n.Key] } else { @() }
    $hash = Get-TextHash $n.Summary $n.Body
    # Merged before, and unchanged since: nothing to do, whatever became of the event it joined.
    if ($mergedTexts.Contains("$($n.Key)|$($n.Evidence)|$hash")) { $counts.unchanged++; continue }
    $same = $null
    foreach ($e in $entries) { if ($e.Current -and $e.Summary -ceq $n.Summary -and $e.Body -ceq $n.Body) { $same = $e; break } }
    if ($null -ne $same) {
        # Rule 2: the same text is current on this key, from somewhere else. One merge record per
        # merged store, on its own key, so a third store's record does not hide a second's.
        [void]$mergedTexts.Add("$($n.Key)|$($n.Evidence)|$hash")
        $keptLabel = if ($same.Evidence -match '^memory:(.+)/[^/]+$') { $Matches[1] } else { $same.Evidence }
        $storeSlug = ($n.Label.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
        if ($storeSlug.Length -gt $StoreSlugMax) { $storeSlug = $storeSlug.Substring(0, $StoreSlugMax).TrimEnd('-') }
        if (-not $storeSlug) { $storeSlug = 'store' }
        $mergeItems.Add([ordered]@{
                type     = 'decision'
                key      = "memory-merge/$($n.Slug)/$storeSlug"
                summary  = "Merged memory note '$($n.Slug)' from $($n.Label) into $keptLabel`: same name, same text"
                evidence = $same.Evidence
                body     = "kept: $($same.Evidence)`nmerged: $($n.Evidence)`ntext: $hash"
            })
        $mergeMeta.Add([pscustomobject]@{ Where = $n.Where; KeptPlanned = $same.Planned })
        continue
    }
    # Rule 3: new to this key. Different CURRENT text already there is a conflict for lint, kept as
    # is; a withdrawn one is not.
    $conflict = @($entries | Where-Object { $_.Current }).Count -gt 0
    Add-KeyEntry $n.Key ([pscustomobject]@{
            Id = $null; Key = $n.Key; Evidence = $n.Evidence; Summary = $n.Summary; Body = $n.Body; TsKey = ''
            Planned = $noteItems.Count; Current = $true
        })
    $noteItems.Add($n.Item)
    $noteMeta.Add([pscustomobject]@{ Where = $n.Where; Action = 'imported'; Conflict = $conflict })
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
    param($Items, [string] $Stage)
    if ($Items.Count -eq 0) { return @() }
    $before = if ($Stage -eq 'merge') { 'The notes batch was already written; the merge records were not.' } else { 'Nothing was written.' }
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

$noteResults = @(Invoke-WriteBatch $noteItems 'notes')
$refusedPlanned = @{}
for ($i = 0; $i -lt $noteResults.Count; $i++) {
    $res = $noteResults[$i]
    $meta = $noteMeta[$i]
    if ($res.status -ceq 'refused') {
        $class = Get-RefusalClass ([string]$res.reason)
        $refusedPlanned[$i] = $class
        $counts.refused++
        $refusedNotes.Add([pscustomobject]@{ note = $meta.Where; class = $class })
        continue
    }
    if ($res.status -ceq 'failed') {
        # Passed every check and could not be written: a disk or permission fault, not the note.
        $refusedPlanned[$i] = 'not written: ' + (Hide-Home ([string]$res.reason))
        $counts.not_written++
        $refusedNotes.Add([pscustomobject]@{ note = $meta.Where; class = $refusedPlanned[$i] })
        continue
    }
    if ($meta.Action -ceq 'superseded') { $counts.superseded++ } else { $counts.imported++ }
    if ($meta.Conflict) { $counts.conflicts++ }
}

# A merge into a note this run failed to write would point at nothing. Its text is the refused
# note's text, so it is refused for the same class.
$mergeToWrite = [System.Collections.Generic.List[object]]::new()
$mergeToWriteMeta = [System.Collections.Generic.List[object]]::new()
for ($i = 0; $i -lt $mergeItems.Count; $i++) {
    $kp = $mergeMeta[$i].KeptPlanned
    if ($null -ne $kp -and $refusedPlanned.ContainsKey($kp)) {
        if ($refusedPlanned[$kp].StartsWith('not written: ')) { $counts.not_written++ } else { $counts.refused++ }
        $refusedNotes.Add([pscustomobject]@{ note = $mergeMeta[$i].Where; class = $refusedPlanned[$kp] })
        continue
    }
    $mergeToWrite.Add($mergeItems[$i])
    $mergeToWriteMeta.Add($mergeMeta[$i])
}
$mergeResults = @(Invoke-WriteBatch $mergeToWrite 'merge')
for ($i = 0; $i -lt $mergeResults.Count; $i++) {
    if ($mergeResults[$i].status -ceq 'refused') {
        $counts.refused++
        $refusedNotes.Add([pscustomobject]@{ note = $mergeToWriteMeta[$i].Where; class = 'merge record: ' + (Get-RefusalClass ([string]$mergeResults[$i].reason)) })
    } elseif ($mergeResults[$i].status -ceq 'failed') {
        $counts.not_written++
        $refusedNotes.Add([pscustomobject]@{ note = $mergeToWriteMeta[$i].Where; class = 'merge record not written: ' + (Hide-Home ([string]$mergeResults[$i].reason)) })
    } else {
        $counts.merged++
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
