#Requires -Version 7.3
<#
.SYNOPSIS
    Shared substrate for the fleet wiki: the event schema, id minting, the UTC clock stamp, the
    inbox and log paths, reading events back, and keyword scoring.

.DESCRIPTION
    Dot-source this. It defines functions in the caller's scope and writes nothing to stdout.

        . "$PSScriptRoot/_event.ps1"

    AN EVENT is one JSON file. Required fields (spec FR-002): id, ts, type, key, seat, summary,
    evidence, trust. Optional: body, supersedes, paths, stale_after. An event is never edited or
    deleted once it is in the log (FR-008); a correction is a NEW event.

    WHERE EVENTS LIVE.
        inbox  <StateRoot>/wiki/inbox/<id>.json               written by write.ps1, uncompiled
        log    <RecordRepo>/wiki/events/<yyyy>/<mm>/<id>.json  written by the compile job only

    One file per event is the contention answer: two seats writing at once create two files, so
    they cannot conflict.

    NOTHING HERE DECIDES WHAT IS LIVE. That is `_guard.ps1`, and every read path goes through it
    (FR-011). `Find-WikiMatch` scores whatever it is handed, which is why a test can hand it the
    unguarded set as a control.

.NOTES
    Stdlib PowerShell 7 only. No git, no network, no module.
#>

# Deliberately no Set-StrictMode: this is dot-sourced, and the caller owns its own preferences.

$script:WikiTypes = @('decision', 'lesson', 'correction', 'gotcha', 'supersede', 'retire')

# The two types that carry an EFFECT rather than content. The guard applies them and never returns
# them as a default result.
$script:WikiMarkerTypes = @('supersede', 'retire')

$script:WikiTrust = @('generated', 'verified')

$script:WikiRequired = @('id', 'ts', 'type', 'key', 'seat', 'summary', 'evidence', 'trust')

# The id: a UTC stamp to the millisecond, then six random base-36 characters. The stamp makes ids
# sort in write order; the suffix makes two writes in the same millisecond distinct.
$script:WikiIdPattern = '^\d{8}T\d{9}Z-[0-9a-z]{6}\z'

# A key is a stable, lower-case, slash-separated name, e.g. `gate/ascii/windows-exit-code`.
# Lower case only, so two keys cannot differ by case alone and silently split one subject in two.
$script:WikiKeyPattern = '^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*\z'

# A seat name as the roster writes it: `builder`, `manager`, `lander`.
$script:WikiSeatPattern = '^[a-z][a-z0-9-]{0,39}\z'

# Anchored with \z, not $: in .NET `$` also matches before a trailing newline, so `gate/ascii` plus a
# newline would pass as a key and silently split one subject in two.

# Control characters. None is allowed in any field but the body, which may hold tab and newlines.
$script:WikiControl = '[\x00-\x1F\x7F]'
$script:WikiBodyControl = '[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]'

$script:WikiLimits = @{ key = 200; summary = 400; evidence = 500; body = 20000; path = 400 }

# FR-005: evidence names a commit, a pull request, a file path at a ref, a memory note, or an Owner
# ruling with its date. Deliberately loose -- it refuses "trust me", not an unusual spelling of a real citation. A
# path needs `/` or `.` so a clock time (`14:05`) is not a ref:path. A sha may be all digits --
# `9379109` is a real one in this repository -- so an eight-digit date also passes as one; refusing
# it would refuse a real citation, and that is the worse error for this check.
#
# The fifth shape is the note a memory store holds, as `import.ps1` cites it. The ref:path shape
# passed most of those by accident and refused a store label holding `~`, which the home directory
# becomes in a project folder's name. It is ANCHORED to the whole field and to the import's own
# shape, memory:<root>[/<project>]/<file>.md, because an unanchored form let prose that merely
# ended in `.md` pass as a citation.
$script:WikiEvidencePatterns = @(
    '\b(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}\b',                  # a commit sha, at least one digit
    '(?i)(#|\bPR\s*#?\s*|/pull/)\d+',                          # a pull request
    '[A-Za-z0-9_./-]+:[A-Za-z0-9_-]*[/.][A-Za-z0-9_./-]*[A-Za-z0-9_]',  # ref:path, the path has / or .
    '(?i)\bowner\b.*\b\d{4}-\d{2}-\d{2}\b',              # an Owner ruling with its date
    '^memory:[A-Za-z0-9.][A-Za-z0-9._~-]*(?:/[A-Za-z0-9._~-]+)?/[^/\s][^/\r\n]*\.md\z'  # a memory note
)

$script:WikiStopwords = [System.Collections.Generic.HashSet[string]]::new(
    [string[]]@(
        'the', 'and', 'for', 'with', 'that', 'this', 'from', 'into', 'what', 'when', 'where',
        'which', 'who', 'why', 'how', 'are', 'was', 'were', 'has', 'have', 'had', 'not', 'but',
        'its', 'our', 'you', 'your', 'does', 'did', 'can', 'will', 'about', 'there', 'their',
        'them', 'then', 'than', 'also', 'only', 'over', 'under', 'after', 'before', 'all', 'any',
        'some', 'each', 'out', 'get', 'got', 'use', 'used', 'should', 'would', 'could'),
    [System.StringComparer]::Ordinal)

# The match floor (FR-015): the fraction of query tokens an event must match to be returned at all.
# 0.6 means two of two, two of three, three of four, three of five.
$script:WikiMatchFloor = 0.6

# ------------------------------------------------------------------------------------------------
# Clock and id
# ------------------------------------------------------------------------------------------------

function Get-WikiClock {
    <# The one clock read. UTC, always. A caller cannot supply a time (FR-004). #>
    return [datetime]::UtcNow
}

function New-WikiId {
    param([Parameter(Mandatory)][datetime] $Utc)
    $alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    $bytes = [byte[]]::new(6)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $suffix = -join @(foreach ($b in $bytes) { $alphabet[$b % 36] })
    return $Utc.ToString('yyyyMMdd\THHmmssfff\Z', [cultureinfo]::InvariantCulture) + '-' + $suffix
}

function Format-WikiStamp {
    param([Parameter(Mandatory)][datetime] $Utc)
    return $Utc.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'", [cultureinfo]::InvariantCulture)
}

function ConvertTo-WikiUtc {
    <#
    .SYNOPSIS
        Parse a stamp into a UTC [datetime], or $null.
    .DESCRIPTION
        ConvertFrom-Json already turns an ISO string into a [datetime], and renders it back through
        the CURRENT CULTURE if it is ever cast to [string]. So both shapes are accepted here and the
        string is never trusted to round-trip.
    #>
    param($Value)
    if ($null -eq $Value) { return $null }
    # A [datetime] with no zone (Kind Unspecified) came from a stamp with no offset. It is read as
    # UTC, as the string branch below reads it; ToUniversalTime would read it as the READER's local
    # time, and two readers in two zones would then order the same events differently.
    if ($Value -is [datetime]) {
        if ($Value.Kind -eq [System.DateTimeKind]::Unspecified) { return [datetime]::SpecifyKind($Value, [System.DateTimeKind]::Utc) }
        return $Value.ToUniversalTime()
    }
    if ($Value -is [datetimeoffset]) { return $Value.UtcDateTime }
    $parsed = [datetimeoffset]::MinValue
    if ([datetimeoffset]::TryParse([string]$Value, [cultureinfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::AssumeUniversal, [ref]$parsed)) {
        return $parsed.UtcDateTime
    }
    return $null
}

# ------------------------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------------------------

function Get-WikiInboxDir {
    param([Parameter(Mandatory)][string] $StateRoot)
    return (Join-Path (Join-Path $StateRoot 'wiki') 'inbox')
}

function Get-WikiTmpDir {
    <# Staging for the atomic write and the leak scan. Same volume as the inbox, so rename is atomic. #>
    param([Parameter(Mandatory)][string] $StateRoot)
    return (Join-Path (Join-Path $StateRoot 'wiki') 'tmp')
}

function Get-WikiEventsRoot {
    param([Parameter(Mandatory)][string] $RecordRepo)
    return (Join-Path (Join-Path $RecordRepo 'wiki') 'events')
}

function Get-WikiLogDir {
    <# Where the compile job files one event: <RecordRepo>/wiki/events/<yyyy>/<mm>/. #>
    param(
        [Parameter(Mandatory)][string] $RecordRepo,
        [Parameter(Mandatory)][datetime] $Utc
    )
    $root = Get-WikiEventsRoot -RecordRepo $RecordRepo
    $yyyy = $Utc.ToString('yyyy', [cultureinfo]::InvariantCulture)
    $mm = $Utc.ToString('MM', [cultureinfo]::InvariantCulture)
    return (Join-Path (Join-Path $root $yyyy) $mm)
}

function Resolve-WikiDir {
    <#
    .SYNOPSIS
        An absolute path for a caller-supplied directory, resolved against the PowerShell location.
    .DESCRIPTION
        `Test-Path` resolves a relative path against the PowerShell location, and every
        [System.IO] call resolves it against the PROCESS directory. The two differ after any
        `Set-Location`, so a relative -StateRoot passed the existence check and then failed to open.
        Resolving once, up front, makes both see the same directory.
    #>
    param([string] $Path)
    # The provider resolves `~` and PowerShell drive paths, which GetFullPath alone does not.
    $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    return [System.IO.Path]::GetFullPath($resolved)
}

function Format-WikiDirName {
    <#
    .SYNOPSIS
        A directory as a message names it: the caller's own spelling, then the resolved one if it
        differs.
    .DESCRIPTION
        `Resolve-WikiDir` can change the spelling as well as the form. On Windows GetFullPath expands
        an 8.3 short name, so `C:\PROGRA~1\x` comes back as `C:\Program Files\x`. A refusal that
        names only the resolved path names a string the caller never typed, and a typo is then hard
        to spot in it.
    #>
    param([string] $Given, [string] $Resolved)
    if ($Given -ceq $Resolved) { return "'$Resolved'" }
    return "'$Given' (resolved to '$Resolved')"
}

function ConvertTo-WikiRelPath {
    <# Forward slashes, no leading `./`. Paths in an event are repository-relative. #>
    param([string] $Path)
    $p = ($Path -replace '\\', '/').Trim()
    while ($p.StartsWith('./')) { $p = $p.Substring(2) }
    return $p
}

# ------------------------------------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------------------------------------

function Set-WikiNote {
    <#
    .SYNOPSIS
        Set a note property on an event, replacing one of the same name.
    .DESCRIPTION
        The reader's own bookkeeping lives in underscore-named properties (_source, _utc, _status).
        The reader strips any a file carried, and this replaces rather than adds, so a value set
        here is always the reader's. Cheaper than `Add-Member -Force`.
    #>
    param($Item, [string] $Name, $Value)
    $props = $Item.PSObject.Properties
    $props.Remove($Name)
    $props.Add([psnoteproperty]::new($Name, $Value))
}

function Test-WikiEvidence {
    param([string] $Evidence)
    foreach ($pat in $script:WikiEvidencePatterns) {
        if ($Evidence -match $pat) { return $true }
    }
    return $false
}

function Test-WikiEvent {
    <#
    .SYNOPSIS
        Validate one event. Returns $null when it is valid, else a one-line reason.
    .DESCRIPTION
        The same check runs on the way in (write.ps1) and on the way out (every reader), so an event
        planted by hand is held to the schema a written one was.

        WRITTEN FOR SPEED, because every reader runs it once per event. No pipeline, no advanced
        parameter binding, and properties read directly: a first version built on `Where-Object` and
        a helper call per field spent over three seconds validating a thousand events, against the
        two-second budget for a whole query (spec SC-004). Direct property access needs the caller
        not to be under `Set-StrictMode`, which no wiki script sets.
    #>
    param($Item)

    foreach ($f in $script:WikiRequired) {
        $v = $Item.$f
        if ($null -eq $v -or ([string]$v).Trim() -eq '') { return "missing required field '$f'" }
    }
    # Checked in every reader, not only in write.ps1: a planted or compiled event carrying an escape
    # sequence would otherwise reach a terminal raw through query.ps1.
    foreach ($f in @('id', 'type', 'key', 'seat', 'summary', 'evidence', 'trust', 'stale_after')) {
        if ($null -ne $Item.$f -and $Item.$f -isnot [datetime] -and [string]$Item.$f -match $script:WikiControl) {
            return "field '$f' contains a control character"
        }
    }
    foreach ($f in @('supersedes', 'paths')) {
        foreach ($x in @($Item.$f)) {
            if ($null -ne $x -and [string]$x -match $script:WikiControl) { return "field '$f' contains a control character" }
        }
    }
    if ($null -ne $Item.body -and [string]$Item.body -match $script:WikiBodyControl) {
        return "field 'body' contains a control character"
    }
    $id = [string]$Item.id
    if ($id -cnotmatch $script:WikiIdPattern) { return "id '$id' is not in the form yyyyMMddTHHmmssfffZ-xxxxxx" }
    $utc = ConvertTo-WikiUtc $Item.ts
    if ($null -eq $utc) { return "ts is not a timestamp" }
    # The id carries the same stamp to the millisecond. A hand-planted event whose ts disagrees with
    # its id, or that is dated ahead of the clock, would sort wrong forever -- a future stamp wins its
    # key against every later write and outlives a retire. One day of slack covers clock skew.
    if ($id.Substring(0, 19) -cne $utc.ToString('yyyyMMdd\THHmmssfff\Z', [cultureinfo]::InvariantCulture)) {
        return "ts does not match the stamp in the id"
    }
    if ($utc -gt [datetime]::UtcNow.AddDays(1)) { return "ts is in the future" }

    $type = [string]$Item.type
    if ($type -cnotin $script:WikiTypes) {
        return "unknown type '$type'; expected one of: $($script:WikiTypes -join ', ')"
    }
    $key = [string]$Item.key
    if ($key.Length -gt $script:WikiLimits.key) { return "key is longer than $($script:WikiLimits.key) characters" }
    if ($key -cnotmatch $script:WikiKeyPattern) {
        return "key '$key' is not lower-case slash-separated words, e.g. gate/ascii/windows-exit-code"
    }
    $seat = [string]$Item.seat
    if ($seat -cnotmatch $script:WikiSeatPattern) { return "seat '$seat' is not a lower-case seat name" }

    $summary = [string]$Item.summary
    if ($summary.IndexOfAny([char[]]@("`r", "`n")) -ge 0) { return "summary must be one line; put detail in -Body" }
    if ($summary.Length -gt $script:WikiLimits.summary) { return "summary is longer than $($script:WikiLimits.summary) characters" }

    $evidence = [string]$Item.evidence
    if ($evidence.Length -gt $script:WikiLimits.evidence) { return "evidence is longer than $($script:WikiLimits.evidence) characters" }
    if (-not (Test-WikiEvidence $evidence)) {
        return "evidence names no commit, pull request, ref:path, memory note, or Owner ruling with its date"
    }

    $trust = [string]$Item.trust
    if ($trust -cnotin $script:WikiTrust) { return "trust must be 'generated' or 'verified', not '$trust'" }

    $body = $Item.body
    if ($null -ne $body -and ([string]$body).Length -gt $script:WikiLimits.body) {
        return "body is longer than $($script:WikiLimits.body) characters"
    }

    $supCount = 0
    foreach ($s in @($Item.supersedes)) {
        if ($null -eq $s) { continue }
        $supCount++
        if ([string]$s -cnotmatch $script:WikiIdPattern) { return "supersedes names '$s', which is not an event id" }
        if ([string]$s -ceq $id) { return "an event cannot supersede itself" }
    }
    if ($type -ceq 'supersede' -and $supCount -eq 0) {
        return "a supersede event must name the event(s) it replaces with -Supersedes"
    }

    foreach ($p in @($Item.paths)) {
        if ($null -eq $p) { continue }
        $ps = [string]$p
        if ($ps.Trim() -eq '') { return "paths holds an empty entry" }
        if ($ps.Length -gt $script:WikiLimits.path) { return "a path is longer than $($script:WikiLimits.path) characters" }
        if ($ps -match '^[A-Za-z]:' -or $ps.StartsWith('/') -or $ps.StartsWith('\')) {
            return "path '$ps' is absolute; paths are repository-relative"
        }
    }

    $sa = $Item.stale_after
    if ($null -ne $sa) {
        $parsed = [datetime]::MinValue
        $saText = if ($sa -is [datetime]) { $sa.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture) } else { [string]$sa }
        if (-not [datetime]::TryParseExact($saText, 'yyyy-MM-dd', [cultureinfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::None, [ref]$parsed)) {
            return "stale_after '$saText' is not a yyyy-MM-dd date"
        }
    }
    return $null
}

function Test-WikiMarkerLoose {
    <#
    .SYNOPSIS
        Can a `supersede` or `retire` marker that failed the full schema still be honoured? Returns
        the UTC stamp in its id when it can, else $null.
    .DESCRIPTION
        A marker carries an effect, and dropping it undoes that effect: what it hid comes back live
        (spec FR-011). One torn field, or a later tightening of a pattern such as evidence, would do
        that silently. So a marker is honoured when the fields the guard acts on are sound, whatever
        the rest says:

          * the type is `supersede` or `retire`;
          * the id is in the id form, is the file's own name, and is not dated ahead of the clock;
          * the key is a valid key;
          * `supersedes`, where present, holds only ids, and a `supersede` names at least one;
          * `stale_after`, where present, is a date, because `-History` labels a marker by it;
          * no field carries a control character, because `-History` prints a marker.

        The stamp in the id orders it, so a bad `ts` does not stop it.
    .PARAMETER Stem
        The file name without `.json`.
    #>
    param($Item, [string] $Stem)
    $type = [string]$Item.type
    if ($type -cnotin $script:WikiMarkerTypes) { return $null }
    $id = [string]$Item.id
    if ($id -cnotmatch $script:WikiIdPattern -or $id -cne $Stem) { return $null }
    $idUtc = [datetime]::MinValue
    if (-not [datetime]::TryParseExact($id.Substring(0, 19), 'yyyyMMdd\THHmmssfff\Z', [cultureinfo]::InvariantCulture,
            ([System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal),
            [ref]$idUtc)) { return $null }
    if ($idUtc -gt [datetime]::UtcNow.AddDays(1)) { return $null }
    $key = [string]$Item.key
    if ($key.Length -gt $script:WikiLimits.key -or $key -cnotmatch $script:WikiKeyPattern) { return $null }
    $supCount = 0
    foreach ($s in @($Item.supersedes)) {
        if ($null -eq $s) { continue }
        if ($s -isnot [string] -or $s -cnotmatch $script:WikiIdPattern) { return $null }
        $supCount++
    }
    if ($type -ceq 'supersede' -and $supCount -eq 0) { return $null }
    # `-History` labels every result from `stale_after`, and a value it cannot read would throw there.
    $sa = $Item.stale_after
    if ($null -ne $sa -and $sa -isnot [datetime]) {
        $saDate = [datetime]::MinValue
        if (-not [datetime]::TryParseExact([string]$sa, 'yyyy-MM-dd', [cultureinfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::None, [ref]$saDate)) { return $null }
    }
    foreach ($p in $Item.PSObject.Properties) {
        $bad = if ($p.Name -ceq 'body') { $script:WikiBodyControl } else { $script:WikiControl }
        foreach ($v in @($p.Value)) {
            if ($null -ne $v -and $v -isnot [datetime] -and [string]$v -match $bad) { return $null }
        }
    }
    return $idUtc
}

# ------------------------------------------------------------------------------------------------
# Reading
# ------------------------------------------------------------------------------------------------

function Read-WikiEventDir {
    <#
    .SYNOPSIS
        Every valid event under one directory, and every marker the loose check honours, each
        tagged with where it came from.
    .DESCRIPTION
        Returns @{ Events = <list>; Skipped = <int>; Unreadable = <int>; Loose = <int> }. A file that
        does not parse, or fails the schema, or whose name is not its own id, is COUNTED and skipped
        -- never dropped in silence, because a reader that loses a file reports the same "nothing
        here" as a reader that found nothing.

        A `supersede` or `retire` MARKER IS NEVER DROPPED ON THE FULL SCHEMA ALONE (spec FR-011). A
        skipped marker never reaches the guard, so what it hid comes back live. A marker that fails
        the full schema but passes `Test-WikiMarkerLoose` is returned and counted in `Loose`.
        Such a marker carries a `_loose` note of $true, because it did NOT pass the schema, and a
        caller that files or republishes events must decide what to do with it.

        `Unreadable` counts the skipped files whose effect may be missing: a file that is not a JSON
        object at all, a file whose type reads as a marker and fails even the loose check, and a
        content event that names `supersedes` and fails the schema. A reader shows that count where
        a caller will see it, because a retirement may be missing. `Skipped` counts every file not
        returned, those included.

        Adds three note properties: _source ('inbox' or 'log'), _utc (the parsed [datetime]) and
        _tsKey (a sortable string, so ordering never depends on culture). A file cannot plant
        `_loose`, since every underscore name it carries is stripped first.
    #>
    param(
        [Parameter(Mandatory)][string] $Dir,
        [Parameter(Mandatory)][ValidateSet('inbox', 'log')][string] $Source,
        [switch] $Recurse
    )
    $events = [System.Collections.Generic.List[object]]::new()
    $skipped = 0
    $unreadable = 0
    $loose = 0
    if (-not (Test-Path -LiteralPath $Dir -PathType Container)) {
        return @{ Events = $events; Skipped = 0; Unreadable = 0; Loose = 0 }
    }
    $option = if ($Recurse) { [System.IO.SearchOption]::AllDirectories } else { [System.IO.SearchOption]::TopDirectoryOnly }
    # Sorted, because Linux lists a directory in no fixed order and Windows lists it by name. A
    # [string[]] is sorted in place; an [object[]] handed to [Array]::Sort is not (see _guard.ps1).
    $files = [string[]]@([System.IO.Directory]::EnumerateFiles($Dir, '*.json', $option))
    [System.Array]::Sort($files, [System.StringComparer]::Ordinal)
    if ($files.Count -eq 0) { return @{ Events = $events; Skipped = 0; Unreadable = 0; Loose = 0 } }
    $texts = [string[]]::new($files.Count)
    for ($i = 0; $i -lt $files.Count; $i++) {
        try { $texts[$i] = [System.IO.File]::ReadAllText($files[$i]) } catch { $texts[$i] = $null }
    }

    # ONE PARSE FOR THE WHOLE DIRECTORY when every file parses, which is the common case. Any
    # failure -- one torn file is enough -- falls back to a parse per file, so a bad file costs the
    # speed-up and never costs its neighbours.
    $parsed = $null
    if ($texts -notcontains $null) {
        try {
            $batch = @(('[' + ($texts -join ",`n") + ']') | ConvertFrom-Json -ErrorAction Stop)
            if ($batch.Count -eq $files.Count) { $parsed = $batch }
        } catch { $parsed = $null }
    }
    if ($null -eq $parsed) {
        $parsed = [object[]]::new($files.Count)
        for ($i = 0; $i -lt $files.Count; $i++) {
            if ($null -eq $texts[$i]) { continue }
            # -NoEnumerate: a file holding a one-element ARRAY must stay an array and be refused,
            # exactly as the batch parse above refuses it.
            try { $parsed[$i] = ConvertFrom-Json -InputObject $texts[$i] -NoEnumerate -ErrorAction Stop } catch { $parsed[$i] = $null }
        }
    }

    for ($i = 0; $i -lt $files.Count; $i++) {
        $ev = $parsed[$i]
        # Not a JSON object at all: a torn write, say. It may have been a marker, and nothing in it
        # can say it was not, so it counts as unreadable as well as skipped.
        if ($null -eq $ev -or $ev -isnot [System.Management.Automation.PSCustomObject]) { $skipped++; $unreadable++; continue }
        # Underscore names are the reader's own bookkeeping (_source, _utc, _hay, _status). A file
        # that carries one must not be able to set it: a planted `_hay` made a note match every
        # query, and a malformed one made every query throw.
        $props = $ev.PSObject.Properties
        foreach ($name in @($props.Name)) { if ($name.StartsWith('_')) { $props.Remove($name) } }
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($files[$i])
        $isLoose = $false
        if ($null -ne (Test-WikiEvent $ev) -or $stem -cne [string]$ev.id) {
            if ([string]$ev.type -cnotin $script:WikiMarkerTypes) {
                # Content is never honoured loosely, since it would be shown. But one that named
                # `supersedes` hid something, and that something is now live.
                $skipped++
                if (@($ev.supersedes | Where-Object { $null -ne $_ }).Count -gt 0) { $unreadable++ }
                continue
            }
            $idUtc = Test-WikiMarkerLoose -Item $ev -Stem $stem
            if ($null -eq $idUtc) { $skipped++; $unreadable++; continue }
            # Honoured. It is ordered by the stamp in its id, because its own `ts` may be what failed.
            $loose++
            $isLoose = $true
            $utc = $idUtc
        } else {
            $utc = ConvertTo-WikiUtc $ev.ts
        }
        if ($isLoose) { Set-WikiNote $ev '_loose' $true }
        Set-WikiNote $ev '_source' $Source
        Set-WikiNote $ev '_utc' $utc
        Set-WikiNote $ev '_tsKey' ($utc.Ticks.ToString('D19') + '|' + [string]$ev.id)
        $events.Add($ev)
    }
    return @{ Events = $events; Skipped = $skipped; Unreadable = $unreadable; Loose = $loose }
}

function Merge-WikiEvent {
    <#
    .SYNOPSIS
        Inbox plus log, one copy per id.
    .DESCRIPTION
        An event sits in BOTH places between compile and the merge of the pull request carrying it:
        the inbox file is removed only after that merge (spec, Edge Cases). The log copy wins, since
        it is the record; the inbox copy is the same bytes.
    #>
    param(
        [object[]] $Log = @(),
        [object[]] $Inbox = @()
    )
    $byId = [ordered]@{}
    foreach ($e in $Log) { if ($null -ne $e) { $byId[[string]$e.id] = $e } }
    foreach ($e in $Inbox) {
        if ($null -ne $e -and -not $byId.Contains([string]$e.id)) { $byId[[string]$e.id] = $e }
    }
    return @($byId.Values)
}

# ------------------------------------------------------------------------------------------------
# Scoring
# ------------------------------------------------------------------------------------------------

function Get-WikiToken {
    <#
    .SYNOPSIS
        Lower-case word tokens of three or more characters, stopwords removed, de-duplicated.
    #>
    param([string] $Text)
    $out = [System.Collections.Generic.List[string]]::new()
    if (-not $Text) { return , $out }
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($t in ($Text.ToLowerInvariant() -split '[^a-z0-9]+')) {
        if ($t.Length -lt 3) { continue }
        if ($script:WikiStopwords.Contains($t)) { continue }
        if ($seen.Add($t)) { $out.Add($t) }
    }
    return , $out
}

function Get-WikiStem {
    <#
    .SYNOPSIS
        A crude suffix strip, so `retired` finds `retire` and `commits` finds `commit`.
    .DESCRIPTION
        Matching is by PREFIX against the event's tokens, so the stem only has to be a prefix of the
        forms it should find. It never strips below four characters.
    #>
    param([string] $Token)
    if ($Token.Length -ge 7 -and $Token.EndsWith('ing')) { return $Token.Substring(0, $Token.Length - 3) }
    if ($Token.Length -ge 6 -and $Token.EndsWith('ed')) { return $Token.Substring(0, $Token.Length - 2) }
    if ($Token.Length -ge 5 -and $Token.EndsWith('s') -and -not $Token.EndsWith('ss')) {
        return $Token.Substring(0, $Token.Length - 1)
    }
    return $Token
}

function Get-WikiHaystack {
    <#
    .SYNOPSIS
        One event's searchable text as two space-delimited word strings: key alone, and everything.
    .DESCRIPTION
        Cached on the event. A query then asks `Contains(" " + stem)` per query token, which is a
        prefix test in .NET rather than a loop in PowerShell, and is what keeps a 1000-event query
        inside its two seconds. Nothing here filters short words or stopwords: the QUERY side is
        filtered, and a haystack word that no query token can be is simply never looked for.
    #>
    param($Item)
    $cached = $Item.PSObject.Properties['_hay']
    if ($null -ne $cached) { return $cached.Value }
    $key = ([string]$Item.key).ToLowerInvariant()
    $text = $key + ' ' + [string]$Item.summary + ' ' + [string]$Item.body + ' ' + (@($Item.paths) -join ' ')
    $hay = @{
        Key = ' ' + [regex]::Replace($key, '[^a-z0-9]+', ' ') + ' '
        All = ' ' + [regex]::Replace($text.ToLowerInvariant(), '[^a-z0-9]+', ' ') + ' '
    }
    Set-WikiNote $Item '_hay' $hay
    return $hay
}

function Test-WikiPathMatch {
    <#
    .SYNOPSIS
        Does this event name the file? Exact match, or the query path ends with the event's path.
    .DESCRIPTION
        The suffix rule lets a caller pass an absolute path from its own checkout and still match a
        repository-relative path in the event, without a git call to find the checkout root.
    #>
    param($Item, [string] $Path)
    $want = (ConvertTo-WikiRelPath $Path).ToLowerInvariant()
    foreach ($p in @($Item.paths)) {
        if ($null -eq $p) { continue }
        $have = (ConvertTo-WikiRelPath ([string]$p)).ToLowerInvariant()
        if (-not $have) { continue }
        if ($want -eq $have -or $want.EndsWith('/' + $have)) { return $true }
    }
    return $false
}

function Sort-WikiHit {
    <#
    .SYNOPSIS
        Best rank first, then newest first. By property name, never by script block: a script-block
        sort key is evaluated per comparison and cost a third of a second over three hundred hits.
    #>
    param($Hits)
    return @($Hits | Sort-Object -Property @{ Expression = 'Rank'; Descending = $true },
        @{ Expression = 'Order'; Descending = $true })
}

function Find-WikiMatch {
    <#
    .SYNOPSIS
        Score events against a query and return those at or above the match floor, best first.
    .DESCRIPTION
        The score is the FRACTION of query tokens the event matches anywhere, and the floor is on
        that fraction alone. A match in the key adds a quarter-weight bonus to the rank, never to the
        floor, so a key match can reorder results but cannot admit an event the floor refused.

        With -Path, only events whose `paths` name that file are considered. With -Path and no
        -Text, every such event qualifies and they rank newest first.

        Returns objects of @{ Event; Score; Rank; Order }. It applies NO guard: hand it the live set.
    #>
    param(
        [object[]] $Events = @(),
        [string] $Text,
        [string] $Path
    )
    $queryTokens = Get-WikiToken $Text
    # De-duplicated AFTER stemming: `commits commit` is one word asked twice, and counting it twice
    # let an event matching only that word clear the floor.
    $stems = [System.Collections.Generic.List[string]]::new()
    $stemSeen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($q in $queryTokens) { $st = Get-WikiStem $q; if ($stemSeen.Add($st)) { $stems.Add($st) } }
    $hits = [System.Collections.Generic.List[object]]::new()
    if ($stems.Count -eq 0 -and -not $Path) { return , $hits }

    foreach ($ev in $Events) {
        if ($null -eq $ev) { continue }
        if ($Path -and -not (Test-WikiPathMatch -Item $ev -Path $Path)) { continue }
        if ($stems.Count -eq 0) {
            $hits.Add([pscustomobject]@{ Event = $ev; Score = 1.0; Rank = 1.0; Order = $ev._tsKey })
            continue
        }
        $hay = Get-WikiHaystack -Item $ev
        $all = 0; $inKey = 0
        foreach ($s in $stems) {
            $needle = " $s"
            if ($hay.All.Contains($needle)) {
                $all++
                if ($hay.Key.Contains($needle)) { $inKey++ }
            }
        }
        $score = $all / $stems.Count
        if ($score -lt $script:WikiMatchFloor) { continue }
        $hits.Add([pscustomobject]@{ Event = $ev; Score = $score; Rank = $score + 0.25 * ($inKey / $stems.Count); Order = $ev._tsKey })
    }
    return , (Sort-WikiHit $hits)
}
