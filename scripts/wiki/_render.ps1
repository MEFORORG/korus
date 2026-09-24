#Requires -Version 7.3
<#
.SYNOPSIS
    Render the fleet wiki's pages and index from a set of events. Shared by `compile.ps1` and its
    `-RebuildOnly` mode, so a rebuild and a compile cannot render differently (spec FR-012).

.DESCRIPTION
    Dot-source this after `_event.ps1` and `_guard.ps1`:

        . "$PSScriptRoot/_event.ps1"
        . "$PSScriptRoot/_guard.ps1"
        . "$PSScriptRoot/_render.ps1"

    WHAT IS RENDERED. One page per key prefix: the key up to its last `/`, or the key itself when
    it has none. The file name is the prefix with each `/` written as `--` (`Get-WikiPageFileName`
    names two exceptions). Each page lists its live events, then a "Replaced" section naming its
    hidden events by id with a pointer to what replaced them. `index.md` holds one line per page and
    a `## Conflicts` section.

    RETIRED TEXT NEVER REACHES A PAGE. The "Replaced" section carries an id, a key, a date and a
    pointer, and links to the event file; it does not copy the old summary. So a search over the
    pages cannot surface the wording of a superseded fact, and the rebuild test can assert that the
    old wording is absent from every page.

    DETERMINISTIC BY CONSTRUCTION. No clock is read here. Pages sort by prefix and events by stamp
    then id, all with ordinal comparison, and every file is written with LF line endings. Two
    renders of the same events give the same bytes, which is what makes compile idempotent
    (FR-019) and a rebuild comparable to a compile (FR-012).

    -NoGuard IS FOR THE CONTROL ONLY. It labels every event live and skips the guard, so a test
    can show that an event hidden by a normal render DOES appear when the guard is out of the way
    (spec SC-001). `compile.ps1` never passes it.
#>

function Get-WikiKeyPrefix {
    <# The key up to its last `/`, or the key itself when it has none. #>
    param([string] $Key)
    $i = $Key.LastIndexOf('/')
    if ($i -lt 0) { return $Key }
    return $Key.Substring(0, $i)
}

function Get-WikiPageFileName {
    <#
    .SYNOPSIS
        The page file name for a prefix: each `/` written as `--`, then `.md`.
    .DESCRIPTION
        A key may itself contain `--`, so `a/b` and the one-segment `a--b` would both become
        `a--b.md`. A prefix that contains `--` is therefore written with `~` for each `/` and one
        trailing `~`. No key can contain `~`, so the two forms never meet, and the name of a page
        depends on its own prefix alone: a new prefix can never rename an old page and break links.

        A name whose part before the first dot is a Windows device name (`aux`, `con`, `nul`,
        `prn`, `com1`-`com9`, `lpt1`-`lpt9`) gets a leading `_`. .NET writes such a file, then Git
        for Windows refuses to add it, and every compile after would stop there. No key starts with
        `_`, so the prefixed name cannot collide either.

        A name longer than 100 characters keeps its first 80 and ends `~h` plus 12 hex characters of
        the prefix's SHA-256. A key may be 200 characters, and each `/` doubles, so an uncut name
        could pass the 255-character file-name limit, or push the path past the 260 that Git for
        Windows refuses without `core.longpaths`; either would stop every compile at `git add`. The
        cut name ends in a hex digit where the `--` form ends in `~`, and a plain name holds no `~`.
    #>
    param([string] $Prefix)
    $name = if ($Prefix.Contains('--')) { $Prefix.Replace('/', '~') + '~' } else { $Prefix.Replace('/', '--') }
    if ($name.Length -gt 100) {
        $hash = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($Prefix))
        $name = $name.Substring(0, 80) + '~h' + [System.Convert]::ToHexString($hash).Substring(0, 12).ToLowerInvariant()
    }
    if (($name -split '\.')[0] -match '^(con|prn|aux|nul|com[0-9]|lpt[0-9])$') { $name = '_' + $name }
    return "$name.md"
}

function Get-WikiEventRelPath {
    <# Where the compile job files an event, relative to `wiki/`: events/<yyyy>/<mm>/<id>.json. #>
    param($Item)
    $utc = $Item._utc
    return 'events/' + $utc.ToString('yyyy', [cultureinfo]::InvariantCulture) + '/' +
        $utc.ToString('MM', [cultureinfo]::InvariantCulture) + '/' + [string]$Item.id + '.json'
}

function Format-WikiYamlString {
    <# A YAML single-quoted scalar. A quote inside is doubled; nothing else needs escaping. #>
    param([string] $Text)
    return "'" + $Text.Replace("'", "''") + "'"
}

function Get-WikiStaleText {
    <# stale_after as yyyy-MM-dd, whether ConvertFrom-Json left it a string or made it a date. #>
    param($Value)
    if ($null -eq $Value) { return $null }
    if ($Value -is [datetime]) { return $Value.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture) }
    return [string]$Value
}

function Get-WikiNewestFirst {
    <#
    .SYNOPSIS
        Events newest first, by `_tsKey` under ORDINAL comparison.
    .DESCRIPTION
        Not Sort-Object: it compares strings by culture, which can ignore a hyphen, and an id holds
        one. The guard orders by ordinal, so the renderer must too or the two could disagree on a tie.
    #>
    param([object[]] $Events = @())
    $items = @($Events | Where-Object { $null -ne $_ })
    $keys = [string[]]::new($items.Count)
    for ($i = 0; $i -lt $items.Count; $i++) { $keys[$i] = [string]$items[$i]._tsKey }
    [System.Array]::Sort($keys, $items, [System.StringComparer]::Ordinal)
    [System.Array]::Reverse($items)
    return , $items
}

function Find-WikiConflict {
    <#
    .SYNOPSIS
        Keys held by two or more live-candidate events, where neither supersedes the other.
    .DESCRIPTION
        A live candidate is a content event (not a `supersede` or `retire` marker) that no event
        names in `supersedes`, and that sorts after the newest `retire` on its key. The guard keeps
        only the newest of them live; the others are hidden by recency alone, which is a decision
        nobody made. That is what lint needs to see, so it is listed.

        Returns objects of @{ Key; Kept; Others } sorted by key. Kept is the candidate the guard
        labelled live, or $null when none is: a newer event on the key that a later event superseded
        still hides the older ones, so a key can hold a conflict and nothing live. Pass the events
        as `Select-WikiLiveEvent -History` labelled them.
    #>
    param([object[]] $Events = @())
    $superseded = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $retireAt = @{}
    foreach ($ev in $Events) {
        if ($null -eq $ev) { continue }
        foreach ($s in @($ev.supersedes)) { if ($null -ne $s) { [void]$superseded.Add([string]$s) } }
        if ([string]$ev.type -ceq 'retire') {
            $k = [string]$ev.key
            if (-not $retireAt.ContainsKey($k) -or [string]::CompareOrdinal([string]$ev._tsKey, $retireAt[$k]) -gt 0) {
                $retireAt[$k] = [string]$ev._tsKey
            }
        }
    }
    $byKey = @{}
    foreach ($ev in $Events) {
        if ($null -eq $ev) { continue }
        if ([string]$ev.type -cin $script:WikiMarkerTypes) { continue }
        if ($superseded.Contains([string]$ev.id)) { continue }
        $k = [string]$ev.key
        if ($retireAt.ContainsKey($k) -and [string]::CompareOrdinal([string]$ev._tsKey, $retireAt[$k]) -lt 0) { continue }
        if (-not $byKey.ContainsKey($k)) { $byKey[$k] = [System.Collections.Generic.List[object]]::new() }
        $byKey[$k].Add($ev)
    }
    $keys = [string[]]@($byKey.Keys)
    [System.Array]::Sort($keys, [System.StringComparer]::Ordinal)
    $out = [System.Collections.Generic.List[object]]::new()
    foreach ($k in $keys) {
        $list = $byKey[$k]
        if ($list.Count -lt 2) { continue }
        $sorted = Get-WikiNewestFirst -Events $list.ToArray()
        $kept = @($sorted | Where-Object { [string]$_._status -ceq 'live' } | Select-Object -First 1)
        $keptEvent = if ($kept.Count -gt 0) { $kept[0] } else { $null }
        $out.Add([pscustomobject]@{
                Key    = $k
                Kept   = $keptEvent
                Others = @($sorted | Where-Object { $null -eq $keptEvent -or [string]$_.id -cne [string]$keptEvent.id })
            })
    }
    return , $out
}

function Build-WikiPageSet {
    <#
    .SYNOPSIS
        Render every page and the index from a set of events. Writes nothing.
    .PARAMETER Events
        Events as `Read-WikiEventDir` returns them, each carrying `_utc` and `_tsKey`.
    .PARAMETER NoGuard
        The control. Label every event live instead of asking the guard. Never used by compile.
    .OUTPUTS
        @{ Files = ordered map of path under `wiki/` to content; Pages = <int>; Conflicts = <list> }
    #>
    param(
        [object[]] $Events = @(),
        [switch] $NoGuard
    )

    if ($NoGuard) {
        $labelled = [System.Collections.Generic.List[object]]::new()
        foreach ($ev in $Events) {
            if ($null -eq $ev) { continue }
            Set-WikiNote $ev '_status' 'live'
            Set-WikiNote $ev '_replacedBy' $null
            Set-WikiNote $ev '_supersededBy' @()
            $labelled.Add($ev)
        }
    } else {
        $labelled = Select-WikiLiveEvent -Events $Events -History
    }
    $byId = @{}
    foreach ($ev in $labelled) { $byId[[string]$ev.id] = $ev }

    # Content events grouped by prefix. Markers carry an effect, not content, so they get no row;
    # a hidden event's pointer still links to the marker that hid it.
    $groups = @{}
    foreach ($ev in $labelled) {
        if ([string]$ev.type -cin $script:WikiMarkerTypes) { continue }
        $prefix = Get-WikiKeyPrefix ([string]$ev.key)
        if (-not $groups.ContainsKey($prefix)) { $groups[$prefix] = [System.Collections.Generic.List[object]]::new() }
        $groups[$prefix].Add($ev)
    }
    $prefixes = [string[]]@($groups.Keys)
    [System.Array]::Sort($prefixes, [System.StringComparer]::Ordinal)

    $fileOf = @{}
    $byFirst = @{}
    foreach ($p in $prefixes) {
        $fileOf[$p] = Get-WikiPageFileName $p
        $first = ($p -split '/')[0]
        if (-not $byFirst.ContainsKey($first)) { $byFirst[$first] = [System.Collections.Generic.List[string]]::new() }
        $byFirst[$first].Add($p)   # ordinal order, because $prefixes is
    }

    $files = [ordered]@{}
    $indexLines = [System.Collections.Generic.List[string]]::new()
    foreach ($p in $prefixes) {
        $pageEvents = Get-WikiNewestFirst -Events $groups[$p].ToArray()
        $live = @($pageEvents | Where-Object { [string]$_._status -ceq 'live' })
        $hidden = @($pageEvents | Where-Object { [string]$_._status -cne 'live' })

        $stale = $null
        $sources = [System.Collections.Generic.List[string]]::new()
        foreach ($ev in $live) {
            $sa = Get-WikiStaleText $ev.stale_after
            if ($sa -and ($null -eq $stale -or [string]::CompareOrdinal($sa, $stale) -lt 0)) { $stale = $sa }
            $e = [string]$ev.evidence
            if ($sources -cnotcontains $e) { $sources.Add($e) }
        }

        $sb = [System.Text.StringBuilder]::new()
        [void]$sb.Append("---`n")
        [void]$sb.Append("type: wiki-page`n")
        [void]$sb.Append("title: $(Format-WikiYamlString $p)`n")
        [void]$sb.Append("status: stable`n")
        if ($stale) { [void]$sb.Append("stale_after: $stale`n") }
        if ($sources.Count -eq 0) { [void]$sb.Append("sources: []`n") }
        else {
            [void]$sb.Append("sources:`n")
            foreach ($s in $sources) { [void]$sb.Append("  - $(Format-WikiYamlString $s)`n") }
        }
        [void]$sb.Append("generated_by: scripts/wiki/compile.ps1`n")
        [void]$sb.Append("---`n`n")
        [void]$sb.Append("# $p`n`n")
        [void]$sb.Append("Generated from ``wiki/events`` by ``scripts/wiki/compile.ps1``. Do not edit it by hand: write an event with ``scripts/wiki/write.ps1`` instead.`n`n")

        [void]$sb.Append("## Live`n`n")
        if ($live.Count -eq 0) {
            [void]$sb.Append("No live event. Every event under this prefix was replaced or withdrawn.`n")
        }
        foreach ($ev in $live) {
            $date = $ev._utc.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
            [void]$sb.Append("- ``$($ev.key)``: $($ev.summary)`n")
            [void]$sb.Append("  - date $date, seat $($ev.seat), type $($ev.type), trust $($ev.trust)`n")
            [void]$sb.Append("  - evidence: $($ev.evidence)`n")
            [void]$sb.Append("  - id: [$($ev.id)](../$(Get-WikiEventRelPath $ev))`n")
        }

        if ($hidden.Count -gt 0) {
            [void]$sb.Append("`n## Replaced`n`n")
            [void]$sb.Append("Hidden by the guard. The old text stays in the event file and is not repeated here.`n`n")
            foreach ($ev in $hidden) {
                $date = $ev._utc.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
                $line = "- [$($ev.id)](../$(Get-WikiEventRelPath $ev)) ``$($ev.key)``, $date, seat $($ev.seat)"
                $rb = [string]$ev._replacedBy
                if ($rb -and $byId.ContainsKey($rb)) {
                    $by = $byId[$rb]
                    $verb = if ([string]$by.type -ceq 'retire') { 'withdrawn by' } else { 'replaced by' }
                    $line += "; $verb [$rb](../$(Get-WikiEventRelPath $by))"
                    $succ = Resolve-WikiSuccessor -Item $ev -ById $byId
                    if ($null -ne $succ -and [string]$succ.id -cne $rb) {
                        $line += "; now live: [$($succ.id)](../$(Get-WikiEventRelPath $succ))"
                    }
                }
                [void]$sb.Append("$line`n")
            }
        }

        $related = @($byFirst[($p -split '/')[0]] | Where-Object { $_ -cne $p })
        if ($related.Count -gt 0) {
            [void]$sb.Append("`n## Related`n`n")
            foreach ($r in $related) { [void]$sb.Append("- [$r]($($fileOf[$r]))`n") }
        }
        $files["pages/$($fileOf[$p])"] = $sb.ToString()

        $newest = if ($live.Count -gt 0) {
            'newest ' + $live[0]._utc.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
        } else { 'no live event' }
        $indexLines.Add("- [$p](pages/$($fileOf[$p])) -- $($live.Count) live, $newest")
    }

    $conflicts = Find-WikiConflict -Events @($labelled)
    $ix = [System.Text.StringBuilder]::new()
    [void]$ix.Append("# Fleet wiki index`n`n")
    [void]$ix.Append("Generated from ``wiki/events`` by ``scripts/wiki/compile.ps1``. Do not edit it by hand.`n`n")
    [void]$ix.Append("## Pages`n`n")
    if ($indexLines.Count -eq 0) { [void]$ix.Append("No page yet.`n") }
    foreach ($l in $indexLines) { [void]$ix.Append("$l`n") }
    [void]$ix.Append("`n## Conflicts`n`n")
    if ($conflicts.Count -eq 0) {
        [void]$ix.Append("None.`n")
    } else {
        [void]$ix.Append("Two or more events on one key, and neither supersedes the other. The guard shows the newest; lint reports the rest.`n`n")
        foreach ($c in $conflicts) {
            $others = @($c.Others | ForEach-Object { "[$($_.id)]($(Get-WikiEventRelPath $_))" }) -join ', '
            $keptText = if ($null -ne $c.Kept) { "kept [$($c.Kept.id)]($(Get-WikiEventRelPath $c.Kept))" } else { 'nothing live' }
            [void]$ix.Append("- ``$($c.Key)``: $keptText; also: $others`n")
        }
    }
    $files['index.md'] = $ix.ToString()

    return @{ Files = $files; Pages = $prefixes.Count; Conflicts = $conflicts }
}

function Write-WikiPageSet {
    <#
    .SYNOPSIS
        Replace `<WikiDir>/pages/` and `<WikiDir>/index.md` with a rendered page set.
    .DESCRIPTION
        The pages directory is removed first, so a page for a prefix that no longer renders cannot
        outlive it. UTF-8 without a byte order mark, LF line endings, as rendered.
    #>
    param(
        [Parameter(Mandatory)][string] $WikiDir,
        [Parameter(Mandatory)] $PageSet
    )
    $pages = Join-Path $WikiDir 'pages'
    if (Test-Path -LiteralPath $pages) { Remove-Item -LiteralPath $pages -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $pages | Out-Null
    $enc = [System.Text.UTF8Encoding]::new($false)
    foreach ($rel in $PageSet.Files.Keys) {
        $path = Join-Path $WikiDir $rel
        [System.IO.File]::WriteAllText($path, $PageSet.Files[$rel], $enc)
    }
}
