#Requires -Version 7.3
<#
.SYNOPSIS
    The guard: the ONE filter every wiki read passes through (spec FR-011). It hides what is
    superseded or retired.

.DESCRIPTION
    Dot-source this beside `_event.ps1`:

        . "$PSScriptRoot/_event.ps1"
        . "$PSScriptRoot/_guard.ps1"

    WHY A GUARD AND NOT A FLAG ON THE RECORD. Five memory systems were tested in arXiv 2609.08258
    and none hid a revoked fact by default; the revoked fact often outranked its replacement. And a
    rebuild from a log resurrected every superseded event when the "superseded" flag lived only in
    the index. So retirement is decided HERE, from the events alone, every time anything reads.

    THE RULES, applied in this order. All are deterministic, keyed on ids and keys, never on text.

      1. An event named in ANY event's `supersedes` list is hidden. Its pointer is the newest event
         that named it.
      2. A `retire` event withdraws every event on ITS OWN key that sorts before it. A later event
         on that key is live again, so a key can be reused.
      3. On each key, a content event is hidden by any NEWER content event on that key -- whether
         or not the newer one is itself hidden -- unless the newer one is an event it supersedes.
         So superseding the newest event on a key leaves nothing live there (an older event the
         newest had already replaced never comes back), while a correction that names its target
         is never hidden BY that target, even when clock skew stamped the target later.
      4. `supersede` and `retire` events carry an effect, not content. They are never returned as
         a default result.

    AN EFFECT IS NEVER UNDONE. Superseding a `supersede` or `retire` event hides the marker from
    history and does NOT bring back what it hid. To restore a fact, write it again as a new event,
    which rule 2 and rule 3 then treat as the newest on its key. That keeps the live set a function
    of the events alone, with no fixpoint and no cycle to resolve.

    Each returned event carries two note properties:
        _status       'live' or 'historical'
        _replacedBy   the id that replaced or withdrew it, or $null
#>

function Select-WikiLiveEvent {
    <#
    .SYNOPSIS
        Given events, return the live set -- or, with -History, every event, labelled.
    .PARAMETER Events
        Events as `Read-WikiEventDir` returns them: each has `_tsKey` for ordering.
    .PARAMETER History
        Return everything, markers included. Hidden events are labelled `historical` and point at
        the id that replaced or withdrew them.
    #>
    param(
        [object[]] $Events = @(),
        [switch] $History
    )

    # Sorted by an ordinal key array rather than Sort-Object: it is the same order, a tenth the time.
    #
    # THE ITEMS ARRAY IS AN [int[]] OF POSITIONS, NEVER THE EVENTS. Handed an [object[]] of events,
    # `[Array]::Sort($keys, $items, ...)` sorted the keys and left the events in arrival order,
    # measured on pwsh 7.6. Windows hands files over in name order, which is stamp order, so every
    # case passed there. Linux hands them over in no fixed order, so the newest event on a key
    # changed from run to run. An [int[]] is sorted in place, and the events are then read by it.
    $present = [System.Collections.Generic.List[object]]::new()
    foreach ($ev in $Events) { if ($null -ne $ev) { $present.Add($ev) } }
    $keys = [string[]]::new($present.Count)
    $order = [int[]]::new($present.Count)
    for ($i = 0; $i -lt $present.Count; $i++) { $keys[$i] = [string]$present[$i]._tsKey; $order[$i] = $i }
    [System.Array]::Sort($keys, $order, [System.StringComparer]::Ordinal)
    $all = [object[]]::new($present.Count)
    for ($i = 0; $i -lt $order.Count; $i++) { $all[$i] = $present[$order[$i]] }

    # Rule 1. The newest superseder wins the pointer, so iterate oldest first and overwrite. Every
    # superseder is also kept, newest first, so a query can reach a live replacement even when a
    # later marker named the same event.
    $supersededBy = @{}
    $allSuperseders = @{}
    foreach ($ev in $all) {
        foreach ($s in @($ev.supersedes)) {
            if ($null -eq $s) { continue }
            $supersededBy[[string]$s] = [string]$ev.id
            if (-not $allSuperseders.ContainsKey([string]$s)) {
                $allSuperseders[[string]$s] = [System.Collections.Generic.List[string]]::new()
            }
            $allSuperseders[[string]$s].Insert(0, [string]$ev.id)
        }
    }

    # Rule 2. The newest retire on each key.
    $retiredAt = @{}
    foreach ($ev in $all) {
        if ([string]$ev.type -ceq 'retire') { $retiredAt[[string]$ev.key] = $ev }
    }

    $hiddenBy = @{}
    foreach ($ev in $all) {
        $id = [string]$ev.id
        if ($supersededBy.ContainsKey($id)) { $hiddenBy[$id] = $supersededBy[$id]; continue }
        if ([string]$ev.type -cin $script:WikiMarkerTypes) { continue }
        $r = $retiredAt[[string]$ev.key]
        if ($null -ne $r -and [string]::CompareOrdinal([string]$ev._tsKey, [string]$r._tsKey) -lt 0) {
            $hiddenBy[$id] = [string]$r.id
        }
    }

    # Rule 3. Two earlier versions were each wrong in one direction. Choosing the newest among
    # SURVIVORS resurrected an older event whenever the newest was superseded. Choosing the newest
    # among ALL hid a correction behind the very event it superseded, when that event carried a
    # later stamp. The newer event hides this one unless this one names it in `supersedes`.
    $byKey = @{}
    foreach ($ev in $all) {
        if ([string]$ev.type -cin $script:WikiMarkerTypes) { continue }
        $k = [string]$ev.key
        if (-not $byKey.ContainsKey($k)) { $byKey[$k] = [System.Collections.Generic.List[object]]::new() }
        $byKey[$k].Add($ev)   # ascending, because $all is
    }
    foreach ($list in $byKey.Values) {
        for ($i = 0; $i -lt $list.Count; $i++) {
            $ev = $list[$i]
            $id = [string]$ev.id
            if ($hiddenBy.ContainsKey($id)) { continue }
            $mine = @($ev.supersedes | ForEach-Object { [string]$_ })
            for ($j = $list.Count - 1; $j -gt $i; $j--) {
                $newer = [string]$list[$j].id
                if ($mine -cnotcontains $newer) { $hiddenBy[$id] = $newer; break }
            }
        }
    }

    $out = [System.Collections.Generic.List[object]]::new()
    foreach ($ev in $all) {
        $id = [string]$ev.id
        $isMarker = [string]$ev.type -cin $script:WikiMarkerTypes
        $hidden = $hiddenBy.ContainsKey($id)
        if (-not $History -and ($hidden -or $isMarker)) { continue }
        Set-WikiNote $ev '_status' $(if ($hidden) { 'historical' } else { 'live' })
        Set-WikiNote $ev '_replacedBy' $(if ($hidden) { $hiddenBy[$id] } else { $null })
        Set-WikiNote $ev '_supersededBy' $(if ($allSuperseders.ContainsKey($id)) { $allSuperseders[$id].ToArray() } else { @() })
        $out.Add($ev)
    }
    return , $out
}

function Resolve-WikiSuccessor {
    <#
    .SYNOPSIS
        The live content event that replaced a hidden one, or $null when it was withdrawn outright.
    .DESCRIPTION
        Walks outward from a historical event -- its `_replacedBy` first, then every event that
        superseded it, newest first -- until it reaches a live content event. It does not walk
        THROUGH a `supersede` or `retire` marker, because a marker withdraws and carries no fact to
        offer in the old one's place; but a marker on one route does not block another, so a
        correction stays reachable after a later marker names the same event. Each event is visited
        once, so a malformed chain cannot loop.

        This is how a query for the OLD wording finds the NEW ruling (spec Story 2, scenario 1)
        without ever returning the old one.
    .PARAMETER ById
        Every event by id, from the output of `Select-WikiLiveEvent -History`, which labels them all.
        Built once by the caller rather than here, so a query with many hidden hits stays linear.
    #>
    param(
        [Parameter(Mandatory)] $Item,
        [Parameter(Mandatory)][hashtable] $ById
    )
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $queue = [System.Collections.Generic.Queue[object]]::new()
    [void]$seen.Add([string]$Item.id)
    $queue.Enqueue($Item)
    while ($queue.Count -gt 0) {
        $cur = $queue.Dequeue()
        $next = @()
        if ($cur._replacedBy) { $next += [string]$cur._replacedBy }
        $next += @($cur._supersededBy | Where-Object { $_ })
        foreach ($n in $next) {
            if (-not $seen.Add([string]$n) -or -not $ById.ContainsKey([string]$n)) { continue }
            $cand = $ById[[string]$n]
            if ([string]$cand.type -cin $script:WikiMarkerTypes) { continue }
            if ([string]$cand._status -ceq 'live') { return $cand }
            $queue.Enqueue($cand)
        }
    }
    return $null
}
