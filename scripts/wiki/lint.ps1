#Requires -Version 7.3
<#
.SYNOPSIS
    Report on the health of the fleet wiki. Report only: it changes no event (spec FR-020).

.DESCRIPTION
    Reads the inbox, the compiled log, the pages and the index, and reports five classes of finding
    (spec FR-021). Each finding has a stable id, the event ids involved, and a one-line reason.

        conflict             two or more live-candidate events on one key, and neither supersedes
                             the other. The guard shows only the newest; lint names all of them.
        dead-evidence        a commit that resolves in none of -EvidenceRepo, a ref:path whose path
                             is not at that ref, or (with -Online) a pull request closed unmerged
        stale                past its stale_after date, or a gotcha or lesson 46 days old or more
        orphan-page          a page that wiki/index.md does not link and no other page links
        promotion-candidate  a key written by two or more distinct seats, or for memory/* keys the
                             same summary text: a lesson learned twice. Two memory: stores count
                             as two learners too, since one importer seat reads every store

    A LIVE CANDIDATE is a content event that no event supersedes and no retire withdraws. That is
    the guard's live set plus the events the guard hid only because a newer event on the same key
    exists (its rule 3). Those are exactly the events a conflict is made of.

    A COMMIT OR REF:PATH IS DEAD WHEN IT IS ABSENT FROM EVERY -EvidenceRepo. So pass every
    repository the evidence can cite: a citation from a repository left off the list reads dead.

    EVIDENCE LINT CANNOT CHECK IS COUNTED AS UNCHECKED, never as passing and never as dead: an Owner
    ruling, a `memory:` source, any citation when no -EvidenceRepo is given, and a pull request
    without -Online. The report prints the count, so a zero dead count over nothing checked cannot
    be read as clean.

    PROMOTION IS LISTED, NEVER ACTED ON. Drafting the playbook pull request is the scheduled Claude
    Code job's work, and it opens that pull request as a DRAFT that only the Owner decides (FR-022).

    IT WRITES NOTHING UNDER THE STATE ROOT OR THE RECORD REPOSITORY. No inbox file, no event, no
    page, no line in wiki/log.md. The only file it may write is -Out, and it refuses an -Out
    anywhere under <StateRoot>/wiki or <RecordRepo>/wiki.

    Exit codes:
        0  the report was produced, whether or not it holds findings
        2  it could not run: a bad argument, a store that does not exist, an evidence repository
           that is not a git repository, or any unexpected failure (a trap turns it into 2). A
           parameter pwsh itself cannot bind exits 1 before the script starts.

.PARAMETER EvidenceRepo
    Git repositories in which to resolve commits and ref:paths, e.g. the engine and korus clones.
    Under `pwsh -File` a list arrives as ONE string, so an entry that is not itself a directory is
    split on commas.

.PARAMETER Today
    The date staleness is measured against, yyyy-MM-dd. Defaults to today, UTC. For tests.

.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/lint.ps1 -RecordRepo ../vault -EvidenceRepo ../engine,.
.EXAMPLE
    pwsh -NoProfile -File scripts/wiki/lint.ps1 -RecordRepo ../vault -Json -Out lint.json
#>
[CmdletBinding()]
param(
    [string] $StateRoot,
    [string] $RecordRepo,
    [string[]] $EvidenceRepo,
    [switch] $Online,
    [string] $Out,
    [switch] $Json,
    [string] $Today
)

$ErrorActionPreference = 'Stop'
# Anything that fails without a message of its own -- an unreadable page, an -Out in a directory that
# does not exist -- is still "could not run", and exits 2 as documented rather than pwsh's 1.
trap {
    [Console]::Error.WriteLine("wiki lint: cannot run: $($_.Exception.Message)")
    exit 2
}
. (Join-Path $PSScriptRoot '_event.ps1')
. (Join-Path $PSScriptRoot '_guard.ps1')

function Stop-Lint {
    param([string] $Message)
    [Console]::Error.WriteLine("wiki lint: cannot run: $Message")
    exit 2
}

$Classes = @('conflict', 'dead-evidence', 'stale', 'orphan-page', 'promotion-candidate')

# ------------------------------------------------------------------------------------ arguments
$todayDate = (Get-WikiClock).Date
$todaySource = 'UTC clock'
if (-not [string]::IsNullOrWhiteSpace($Today)) {
    $parsedToday = [datetime]::MinValue
    if (-not [datetime]::TryParseExact($Today, 'yyyy-MM-dd', [cultureinfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::None, [ref]$parsedToday)) {
        Stop-Lint "-Today '$Today' is not a yyyy-MM-dd date."
    }
    $todayDate = $parsedToday.Date
    $todaySource = '-Today'
}

$repos = [System.Collections.Generic.List[string]]::new()
foreach ($entry in @($EvidenceRepo)) {
    if ([string]::IsNullOrWhiteSpace($entry)) { continue }
    $parts = if (Test-Path -LiteralPath $entry -PathType Container) { @($entry) } else { @($entry -split ',') }
    foreach ($p in $parts) {
        if ([string]::IsNullOrWhiteSpace($p)) { continue }
        $full = Resolve-WikiDir $p.Trim()
        if (-not (Test-Path -LiteralPath $full -PathType Container)) { Stop-Lint "evidence repository '$full' does not exist." }
        $null = & git -C $full rev-parse --git-dir 2>$null
        if ($LASTEXITCODE -ne 0) { Stop-Lint "evidence repository '$full' is not a git repository." }
        if (-not $repos.Contains($full)) { $repos.Add($full) }
    }
}

# ------------------------------------------------------------------------------------ read
$inboxDir = $null
$inboxNote = 'not read'
$inboxEvents = @()
$logEvents = @()
$skipped = 0

if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    # The same path Get-CcxStateRoot returns, built without calling it: that function CREATES the
    # directory when it is absent, and lint writes nothing.
    try {
        . (Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'coord') '_common.ps1')
        $common = Get-CcxGitCommonDir
        if (-not $common) { throw 'not inside a git repository' }
        $StateRoot = Join-Path $common "$((Get-CcxConfig -From $PWD.Path).prefix)-coord"
    } catch {
        $StateRoot = $null
        $inboxNote = "not read: no state root ($($_.Exception.Message))"
    }
} else {
    $StateRoot = Resolve-WikiDir $StateRoot
    if (-not (Test-Path -LiteralPath $StateRoot -PathType Container)) { Stop-Lint "state root '$StateRoot' does not exist." }
}
if ($StateRoot) {
    $inboxDir = Get-WikiInboxDir -StateRoot $StateRoot
    $r = Read-WikiEventDir -Dir $inboxDir -Source inbox
    $inboxEvents = @($r.Events)
    $skipped += $r.Skipped
    $inboxNote = if (Test-Path -LiteralPath $inboxDir -PathType Container) { "$($inboxEvents.Count) event(s)" } else { '0 event(s), directory absent' }
}

$eventsRoot = $null
$logNote = 'not read: no -RecordRepo'
$pagesDir = $null
$indexPath = $null
if (-not [string]::IsNullOrWhiteSpace($RecordRepo)) {
    $RecordRepo = Resolve-WikiDir $RecordRepo
    if (-not (Test-Path -LiteralPath $RecordRepo -PathType Container)) { Stop-Lint "record repository '$RecordRepo' does not exist." }
    $eventsRoot = Get-WikiEventsRoot -RecordRepo $RecordRepo
    $r = Read-WikiEventDir -Dir $eventsRoot -Source log -Recurse
    $logEvents = @($r.Events)
    $skipped += $r.Skipped
    $logNote = if (Test-Path -LiteralPath $eventsRoot -PathType Container) { "$($logEvents.Count) event(s)" } else { '0 event(s), directory absent' }
    $pagesDir = Join-Path (Join-Path $RecordRepo 'wiki') 'pages'
    $indexPath = Join-Path (Join-Path $RecordRepo 'wiki') 'index.md'
}

if (-not $StateRoot -and -not $RecordRepo) { Stop-Lint "no state root could be found and no -RecordRepo was given, so there is nothing to read." }

if ($Out) {
    $Out = Resolve-WikiDir $Out
    # The whole wiki tree on both sides: the inbox, the log, the pages, the index and wiki/log.md.
    $wikiTrees = @(
        $(if ($StateRoot) { Join-Path $StateRoot 'wiki' }),
        $(if ($RecordRepo) { Join-Path $RecordRepo 'wiki' })
    )
    foreach ($forbidden in $wikiTrees) {
        if (-not $forbidden) { continue }
        $f = [System.IO.Path]::GetFullPath($forbidden).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
        if ($Out.StartsWith($f, [System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-Lint "-Out '$Out' is inside '$forbidden', which lint never writes to."
        }
    }
}

$all = @(Merge-WikiEvent -Log $logEvents -Inbox $inboxEvents)

# ------------------------------------------------------------------------------------ guard
# Labelled through the guard, with history, so every hidden event says what hid it.
$labelled = Select-WikiLiveEvent -Events $all -History
$byId = @{}
foreach ($e in $labelled) { $byId[[string]$e.id] = $e }

function Test-LiveCandidate {
    <# A content event no event supersedes and no retire withdraws. See the header. #>
    param($Item)
    if ([string]$Item.type -cin $script:WikiMarkerTypes) { return $false }
    # The guard stores an empty list as `$(@())`, which is $null, so count only real ids.
    if (@($Item._supersededBy | Where-Object { $_ }).Count -gt 0) { return $false }
    $rb = [string]$Item._replacedBy
    if (-not $rb) { return $true }
    $by = $byId[$rb]
    return ($null -ne $by -and [string]$by.type -cnotin $script:WikiMarkerTypes)
}

$candidates = @($labelled | Where-Object { Test-LiveCandidate $_ })

# The newest retire on each key, as the guard's rule 2 reads it. Promotion reads a key's whole
# history rather than only its candidates, so it needs this directly: an event the guard hid by a
# supersede carries the superseder in `_replacedBy`, not the retire that also withdrew it.
$retiredAt = @{}
foreach ($e in $labelled) { if ([string]$e.type -ceq 'retire') { $retiredAt[[string]$e.key] = [string]$e._tsKey } }
function Test-Retired {
    param($Item)
    $r = $retiredAt[[string]$Item.key]
    return ($null -ne $r -and [string]::CompareOrdinal([string]$Item._tsKey, $r) -lt 0)
}

$findings = [System.Collections.Generic.List[object]]::new()
function Add-Finding {
    param([string] $Class, [string] $Id, [string[]] $Events, [string] $Reason, [hashtable] $Extra)
    $f = [ordered]@{ id = "${Class}:$Id"; class = $Class; events = @($Events); reason = $Reason }
    if ($Extra) { foreach ($k in $Extra.Keys) { $f[$k] = $Extra[$k] } }
    $findings.Add([pscustomobject]$f)
}

# ------------------------------------------------------------------------------------ 1. conflict
$byKey = [ordered]@{}
foreach ($e in $candidates) {
    $k = [string]$e.key
    if (-not $byKey.Contains($k)) { $byKey[$k] = [System.Collections.Generic.List[object]]::new() }
    $byKey[$k].Add($e)
}
foreach ($k in $byKey.Keys) {
    $list = $byKey[$k]
    if ($list.Count -lt 2) { continue }
    $ids = @($list | ForEach-Object { [string]$_.id } | Sort-Object)
    $newest = $ids[-1]
    Add-Finding 'conflict' $k $ids "$($ids.Count) live events on key '$k' and none supersedes another; a reader sees at most the newest, $newest"
}

# ------------------------------------------------------------------------------------ 2. dead evidence
$shaRx = [regex]'\b(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}\b'
$refPathRx = [regex]'(?<![A-Za-z0-9_./-])([A-Za-z0-9_./-]+):([A-Za-z0-9_-]*[/.][A-Za-z0-9_./-]*[A-Za-z0-9_])'
# A `#N` after a word such as BACKLOG or ADR names a ledger row, not a pull request, and so does
# every number in the run that follows it: `BACKLOG #1250, #1754`, `items #1089-#1093`. Looked up
# with -Online, each would test an unrelated pull request that happens to carry the same number.
$ledgerRx = [regex]'(?i)\b(?:backlog|items?|issues?|adrs?|rows?)\b(?:[\s,*/&-]|\band\b|#\d+|\b\d+\b)*'
$prRx = [regex]'(?i)(?:#|\bPR\s*#?\s*|/pull/)(\d+)'
$urlRx = [regex]'(?i)\bhttps?://[^\s<>()]+'
$memoryRx = [regex]'(?i)(?<![A-Za-z0-9_./-])memory:[^\s,;]+'
# An Owner ruling is RECORDED and never blanked. Its date carries hyphens, so the sha pattern cannot
# read it as a commit, and blanking the span hid every commit cited between `owner` and the date.
$ownerRx = [regex]'(?i)\bowner\b.*?\b\d{4}-\d{2}-\d{2}\b'

function Get-LintCitation {
    <#
    .SYNOPSIS
        Split one evidence string into citations, each of one kind. A matched span is blanked before
        the next pattern runs, so a sha inside a ref:path or a URL is not counted twice. The same
        citation repeated in one string is kept once.
    #>
    param([string] $Evidence)
    $out = [System.Collections.Generic.List[object]]::new()
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $state = @{ Work = $Evidence }
    $take = {
        param($m, [hashtable] $Citation)
        $state.Work = $state.Work.Remove($m.Index, $m.Length).Insert($m.Index, (' ' * $m.Length))
        if ($seen.Add("$($Citation.Kind)|$($Citation.Text)")) { $out.Add($Citation) }
    }

    foreach ($m in @($memoryRx.Matches($state.Work))) { & $take $m @{ Kind = 'memory'; Text = $m.Value } }
    foreach ($m in @($urlRx.Matches($state.Work))) {
        $u = $m.Value.TrimEnd('.', ',', ';')
        if ($u -match '(?i)github\.com/[^/\s]+/[^/\s]+/pull/(\d+)') { & $take $m @{ Kind = 'pr'; Text = $u; Number = $Matches[1]; Url = $u } }
        elseif ($u -match '(?i)/commit/([0-9a-f]{7,40})\b') { & $take $m @{ Kind = 'commit'; Text = $Matches[1].ToLowerInvariant() } }
        else { & $take $m @{ Kind = 'url'; Text = $u } }
    }
    foreach ($m in @($refPathRx.Matches($state.Work))) {
        & $take $m @{ Kind = 'refpath'; Text = $m.Value; Ref = $m.Groups[1].Value; Path = $m.Groups[2].Value }
    }
    foreach ($m in @($ledgerRx.Matches($state.Work))) {
        if ($m.Value -match '\d') { & $take $m @{ Kind = 'ledger'; Text = $m.Value.Trim(' ', ',', '*', '/', '&', '-') } }
    }
    foreach ($m in @($prRx.Matches($state.Work))) { & $take $m @{ Kind = 'pr'; Text = $m.Value.Trim(); Number = $m.Groups[1].Value; Url = $null } }
    foreach ($m in @($ownerRx.Matches($state.Work))) {
        if ($seen.Add("owner|$($m.Value)")) { $out.Add(@{ Kind = 'owner'; Text = $m.Value }) }
    }
    foreach ($m in @($shaRx.Matches($state.Work))) {
        $v = $m.Value
        # An all-digit yyyyMMdd reads as a date as readily as a sha, so it is not called dead.
        $d = [datetime]::MinValue
        if ($v -match '^\d{8}$' -and [datetime]::TryParseExact($v, 'yyyyMMdd', [cultureinfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::None, [ref]$d) -and $d.Year -ge 1990 -and $d.Year -le 2100) {
            & $take $m @{ Kind = 'ambiguous'; Text = $v }
        } else {
            & $take $m @{ Kind = 'commit'; Text = $v }
        }
    }
    if ($out.Count -eq 0) { $out.Add(@{ Kind = 'unrecognised'; Text = $Evidence }) }
    return , $out
}

function Test-LeavesRepo {
    <# A ref:path whose path climbs out of the repository or is absolute. git refuses it outright. #>
    param([string] $Path)
    return ($Path.StartsWith('/') -or @($Path -split '/') -contains '..')
}

# Every citation of every candidate, parsed once.
$cites = [System.Collections.Generic.List[object]]::new()
foreach ($e in $candidates) {
    foreach ($c in (Get-LintCitation ([string]$e.evidence))) {
        $c.Event = [string]$e.id
        $cites.Add($c)
    }
}

function Test-GitObject {
    <# One object name, one git process. $true when it exists, or is an ambiguous short sha. #>
    param([string] $Repo, [string] $Line)
    # The word `ambiguous` below is git's English message; a translated git would hide it.
    $saved = $env:LC_ALL
    $env:LC_ALL = 'C'
    try { $said = & git -C $Repo cat-file -t $Line 2>&1 } finally { $env:LC_ALL = $saved }
    if ($LASTEXITCODE -eq 0) { return $true }
    return (($said | Out-String) -match '(?i)ambiguous')
}

function Invoke-BatchCheck {
    <#
    .SYNOPSIS
        Which object names exist in one repository. One `git cat-file --batch-check` answers them
        all; if git dies partway, or returns a different number of lines than it was given, every
        name is asked again, ONE PROCESS EACH. A fatal on one line must not read as "missing" for
        every line after it -- that reported real commits dead.
    #>
    param([string] $Repo, [string[]] $Lines)
    $result = [System.Collections.Generic.Dictionary[string, bool]]::new([System.StringComparer]::Ordinal)
    if ($Lines.Count -eq 0) { return , $result }
    $answer = @($Lines | & git -C $Repo cat-file --batch-check 2>$null)
    if ($LASTEXITCODE -eq 0 -and $answer.Count -eq $Lines.Count) {
        for ($i = 0; $i -lt $Lines.Count; $i++) {
            # Found: "<oid> <type> <size>". Not found: "<input> missing". An ambiguous short sha,
            # "<input> ambiguous", still proves the object exists.
            $result[$Lines[$i]] = -not ([string]$answer[$i]).EndsWith(' missing')
        }
        return , $result
    }
    foreach ($l in $Lines) { $result[$l] = Test-GitObject -Repo $Repo -Line $l }
    return , $result
}

# line -> $true when it resolved in at least one repository. Ordinal: git names are case-sensitive.
$found = [System.Collections.Generic.Dictionary[string, bool]]::new([System.StringComparer]::Ordinal)
if ($repos.Count -gt 0) {
    $lines = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($c in $cites) {
        if ($c.Kind -eq 'commit') { [void]$lines.Add("$($c.Text)^{commit}") }
        elseif ($c.Kind -eq 'refpath') {
            [void]$lines.Add("$($c.Ref)^{commit}")
            if (-not (Test-LeavesRepo $c.Path)) { [void]$lines.Add("$($c.Ref):$($c.Path)") }
        }
    }
    $unique = [string[]]@($lines)
    foreach ($l in $unique) { $found[$l] = $false }
    foreach ($repo in $repos) {
        $ans = Invoke-BatchCheck -Repo $repo -Lines $unique
        foreach ($l in $unique) { if ($ans[$l]) { $found[$l] = $true } }
    }
}
function Test-Found { param([string] $Line) return ($found.ContainsKey($Line) -and $found[$Line]) }

$ghReady = $false
$onlineNote = 'off'
if ($Online) {
    if (Get-Command gh -ErrorAction SilentlyContinue) { $ghReady = $true; $onlineNote = 'on' }
    else { $onlineNote = 'requested, but gh is not on PATH; pull requests unchecked' }
}
$prCache = @{}
function Get-PrState {
    <# OPEN, CLOSED, MERGED, or $null when gh cannot answer. #>
    param([string] $Target, [string] $Repo)
    $ck = "$Repo|$Target"
    if ($prCache.ContainsKey($ck)) { return $prCache[$ck] }
    $state = $null
    if ($Repo) { Push-Location -LiteralPath $Repo }
    try {
        $o = & gh pr view $Target --json state --jq .state 2>$null
        if ($LASTEXITCODE -eq 0 -and $o) { $state = ([string]($o | Select-Object -First 1)).Trim().ToUpperInvariant() }
    } catch { $state = $null }
    finally { if ($Repo) { Pop-Location } }
    $prCache[$ck] = $state
    return $state
}

$evResolved = 0; $evDead = 0; $evUnchecked = 0
$uncheckedWhy = [ordered]@{}
function Add-Unchecked { param([string] $Why) $script:evUnchecked++; $script:uncheckedWhy[$Why] = 1 + [int]$script:uncheckedWhy[$Why] }

# Inside a switch, `continue` ends the switch for this citation; $dead stays $null, so nothing is
# recorded below for it. Every branch either counts the citation or sets $dead.
foreach ($c in $cites) {
    $dead = $null
    switch ($c.Kind) {
        'memory' { Add-Unchecked 'memory: source'; continue }
        'owner' { Add-Unchecked 'Owner ruling'; continue }
        'url' { Add-Unchecked 'URL that names no pull request or commit'; continue }
        'ambiguous' { Add-Unchecked 'eight digits that read as a date as well as a commit'; continue }
        'ledger' { Add-Unchecked 'a ledger or ADR number, not a pull request'; continue }
        'unrecognised' { Add-Unchecked 'no citation lint can parse'; continue }
        'commit' {
            if ($repos.Count -eq 0) { Add-Unchecked 'no -EvidenceRepo given'; continue }
            if (Test-Found "$($c.Text)^{commit}") { $evResolved++; continue }
            $dead = "commit $($c.Text) resolves in none of $($repos.Count) evidence repo(s)"
        }
        'refpath' {
            if ($repos.Count -eq 0) { Add-Unchecked 'no -EvidenceRepo given'; continue }
            if (Test-LeavesRepo $c.Path) {
                # The path cannot be asked, but a sha ref can: a missing commit is dead either way.
                if ($shaRx.Match($c.Ref).Value -ceq $c.Ref -and -not (Test-Found "$($c.Ref)^{commit}")) {
                    $dead = "commit $($c.Ref) resolves in none of $($repos.Count) evidence repo(s)"
                } else { Add-Unchecked 'a path that leaves the repository'; continue }
            }
            elseif (Test-Found "$($c.Ref):$($c.Path)") { $evResolved++; continue }
            elseif (Test-Found "$($c.Ref)^{commit}") {
                $dead = "path '$($c.Path)' is not at '$($c.Ref)' in any of $($repos.Count) evidence repo(s) where that ref resolves"
            } elseif ($shaRx.Match($c.Ref).Value -ceq $c.Ref) {
                $dead = "commit $($c.Ref) resolves in none of $($repos.Count) evidence repo(s)"
            } else { Add-Unchecked 'a ref that resolves in no evidence repo'; continue }
        }
        'pr' {
            if (-not $ghReady) { Add-Unchecked 'pull request, and -Online is off'; continue }
            $states = @()
            if ($c.Url) { $states = @(Get-PrState -Target $c.Url -Repo $null) }
            else { $states = @(foreach ($repo in $repos) { Get-PrState -Target $c.Number -Repo $repo }) }
            $states = @($states | Where-Object { $_ })
            if ($states.Count -eq 0) { Add-Unchecked 'pull request gh could not find'; continue }
            $closed = @($states | Where-Object { $_ -eq 'CLOSED' }).Count
            if ($closed -eq 0) { $evResolved++; continue }
            if ($closed -lt $states.Count) { Add-Unchecked 'pull request number with different states in different repos'; continue }
            $dead = "pull request $($c.Text) was closed without merging"
        }
    }
    if ($dead) {
        $evDead++
        Add-Finding 'dead-evidence' "$($c.Event):$($c.Text)" @($c.Event) $dead @{ citation = $c.Text }
    }
}

# ------------------------------------------------------------------------------------ 3. stale
foreach ($e in $candidates) {
    $sa = $e.stale_after
    if ($null -ne $sa) {
        $saDate = if ($sa -is [datetime]) { $sa.Date } else { [datetime]::ParseExact([string]$sa, 'yyyy-MM-dd', [cultureinfo]::InvariantCulture) }
        if ($todayDate -gt $saDate) {
            Add-Finding 'stale' ([string]$e.id) @([string]$e.id) "past its stale_after date $($saDate.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture))"
            continue
        }
    }
    $type = [string]$e.type
    if ($type -cin @('gotcha', 'lesson')) {
        $days = [math]::Floor(($todayDate - $e._utc.Date).TotalDays)
        if ($days -gt $script:WikiStaleDays) { Add-Finding 'stale' ([string]$e.id) @([string]$e.id) "a $type $days days old; $($script:WikiStaleDays + 1) or more is stale" }
    }
}

# ------------------------------------------------------------------------------------ 4. orphan pages
$pages = @()
$indexNote = 'not read: no -RecordRepo'
$pagesNote = 'not read: no -RecordRepo'
if ($pagesDir) {
    if (Test-Path -LiteralPath $pagesDir -PathType Container) {
        $pages = @([System.IO.Directory]::EnumerateFiles($pagesDir, '*.md', [System.IO.SearchOption]::AllDirectories) | ForEach-Object { [System.IO.Path]::GetFullPath($_) })
        $pagesNote = "$($pages.Count) page(s)"
    } else { $pagesNote = '0 page(s), directory absent' }
    $indexNote = if (Test-Path -LiteralPath $indexPath -PathType Leaf) { 'present' } else { 'absent, so only page-to-page links count' }
}

$ignore = [System.StringComparer]::OrdinalIgnoreCase
$linkedPath = [System.Collections.Generic.Dictionary[string, System.Collections.Generic.HashSet[string]]]::new($ignore)
$linkedName = [System.Collections.Generic.Dictionary[string, System.Collections.Generic.HashSet[string]]]::new($ignore)
function Add-Link {
    param($Table, [string] $Target, [string] $Source)
    if (-not $Table.ContainsKey($Target)) { $Table[$Target] = [System.Collections.Generic.HashSet[string]]::new($ignore) }
    [void]$Table[$Target].Add($Source)
}
$inlineRx = [regex]'\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)'
$refDefRx = [regex]'(?m)^[ ]{0,3}\[[^\]]+\]:\s*<?([^\s>]+)>?'
$wikiRx = [regex]'\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]'

$sources = @($pages)
if ($indexPath -and (Test-Path -LiteralPath $indexPath -PathType Leaf)) { $sources += [System.IO.Path]::GetFullPath($indexPath) }
foreach ($src in $sources) {
    $text = [System.IO.File]::ReadAllText($src)
    $dir = Split-Path -Parent $src
    $targets = @($inlineRx.Matches($text) | ForEach-Object { $_.Groups[1].Value }) + @($refDefRx.Matches($text) | ForEach-Object { $_.Groups[1].Value })
    foreach ($t in $targets) {
        if ($t -match '^[A-Za-z][A-Za-z0-9+.-]*:' -or $t.StartsWith('#')) { continue }
        $t = ($t -split '[#?]', 2)[0]
        if (-not $t) { continue }
        try { $t = [uri]::UnescapeDataString($t) } catch { }
        $base = if ($t.StartsWith('/')) { $RecordRepo } else { $dir }
        try { $full = [System.IO.Path]::GetFullPath((Join-Path $base $t.TrimStart('/'))) } catch { continue }
        Add-Link $linkedPath $full $src
        if (-not $full.EndsWith('.md', [System.StringComparison]::OrdinalIgnoreCase)) { Add-Link $linkedPath ($full + '.md') $src }
    }
    foreach ($m in $wikiRx.Matches($text)) {
        $n = ($m.Groups[1].Value.Trim() -replace '\\', '/')
        if ($n.EndsWith('.md', [System.StringComparison]::OrdinalIgnoreCase)) { $n = $n.Substring(0, $n.Length - 3) }
        Add-Link $linkedName $n $src
        Add-Link $linkedName (($n -split '/')[-1]) $src
    }
}
foreach ($p in $pages) {
    $rel = [System.IO.Path]::GetRelativePath($pagesDir, $p) -replace '\\', '/'
    $relNoExt = $rel.Substring(0, $rel.Length - 3)
    $leaf = [System.IO.Path]::GetFileNameWithoutExtension($p)
    $linked = $false
    foreach ($set in @($linkedPath[$p], $linkedName[$relNoExt], $linkedName[$leaf])) {
        if ($null -eq $set) { continue }
        foreach ($s in $set) { if (-not $ignore.Equals($s, $p)) { $linked = $true; break } }
        if ($linked) { break }
    }
    if (-not $linked) { Add-Finding 'orphan-page' $rel @() "wiki/pages/$rel is linked by neither wiki/index.md nor any other page" @{ page = "wiki/pages/$rel" } }
}

# ------------------------------------------------------------------------------------ 5. promotion
# A key's whole history counts, not only its candidates: a second seat that corrected the first by
# superseding it has learned the same lesson twice. A retired key counts for nothing.
$promoKey = [ordered]@{}
foreach ($e in $labelled) {
    if ([string]$e.type -cin $script:WikiMarkerTypes) { continue }
    if (Test-Retired $e) { continue }
    $k = [string]$e.key
    if (-not $promoKey.Contains($k)) { $promoKey[$k] = [System.Collections.Generic.List[object]]::new() }
    $promoKey[$k].Add($e)
}
function Get-MemoryStore {
    <# The store named in an imported event's `memory:<store>/` evidence, lower-cased, or $null. #>
    param($Item)
    $m = [regex]::Match([string]$Item.evidence, '(?i)(?<![A-Za-z0-9_./-])memory:([^/\s,;]+)/')
    if ($m.Success) { return $m.Groups[1].Value.ToLowerInvariant() }
    return $null
}
function Add-Promotion {
    <#
    Two distinct seats, or two distinct memory stores. An imported note carries the seat that ran
    the import, so one importer reading two accounts' stores would otherwise hide a lesson learned
    on both. Seats and stores are counted apart and never fused, so a seat that imports a note and
    later supersedes it is still one seat.
    #>
    param([string] $Id, $Events, [string] $What)
    $seats = @($Events | ForEach-Object { [string]$_.seat } | Sort-Object -Unique)
    $stores = @($Events | ForEach-Object { Get-MemoryStore $_ } | Where-Object { $_ } | Sort-Object -Unique)
    if ($seats.Count -lt 2 -and $stores.Count -lt 2) { return }
    $ids = @($Events | ForEach-Object { [string]$_.id } | Sort-Object)
    $by = @()
    if ($seats.Count -ge 2) { $by += "$($seats.Count) seats ($($seats -join ', '))" }
    if ($stores.Count -ge 2) { $by += "$($stores.Count) memory stores ($($stores -join ', '))" }
    Add-Finding 'promotion-candidate' $Id $ids "$What written by $($by -join ' and ')" @{ seats = $seats; stores = $stores }
}
foreach ($k in $promoKey.Keys) { Add-Promotion "key:$k" $promoKey[$k] "key '$k'" }

# For imported memory notes, the same summary under two different keys is the same lesson.
$bySummary = [ordered]@{}
foreach ($k in $promoKey.Keys) {
    if (-not $k.StartsWith('memory/')) { continue }
    foreach ($e in $promoKey[$k]) {
        $norm = ([regex]::Replace(([string]$e.summary).Trim().ToLowerInvariant(), '\s+', ' '))
        if (-not $bySummary.Contains($norm)) { $bySummary[$norm] = [System.Collections.Generic.List[object]]::new() }
        $bySummary[$norm].Add($e)
    }
}
foreach ($norm in $bySummary.Keys) {
    $list = $bySummary[$norm]
    if (@($list | ForEach-Object { [string]$_.key } | Sort-Object -Unique).Count -lt 2) { continue }
    $hash = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($norm))
    $hex = ([System.Convert]::ToHexString($hash)).Substring(0, 12).ToLowerInvariant()
    Add-Promotion "summary:$hex" $list 'the same memory summary'
}

# ------------------------------------------------------------------------------------ report
$ordered = @($findings | Sort-Object -Property @{ Expression = { [array]::IndexOf($Classes, $_.class) } }, @{ Expression = 'id' })
$totals = [ordered]@{}
foreach ($c in $Classes) { $totals[$c] = @($ordered | Where-Object { $_.class -eq $c }).Count }
$totals['unchecked'] = $evUnchecked
$eventsRead = $all.Count
$repoText = if ($repos.Count -gt 0) { $repos -join ', ' } else { 'none given' }
$dateText = $todayDate.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
$inputsLine = "inputs: $eventsRead event(s) read (inbox $($inboxEvents.Count), log $($logEvents.Count)), $skipped file(s) unreadable and skipped; $($pages.Count) page(s); $($repos.Count) evidence repo(s); online $(if ($ghReady) { 'on' } else { 'off' })"

if ($Json) {
    $doc = [ordered]@{
        date     = $dateText
        findings = @($ordered)
        totals   = $totals
        evidence = [ordered]@{ citations = $cites.Count; resolved = $evResolved; dead = $evDead; unchecked = $evUnchecked; unchecked_by_reason = $uncheckedWhy }
        inputs   = [ordered]@{
            events = $eventsRead; inbox_events = $inboxEvents.Count; log_events = $logEvents.Count; skipped = $skipped
            inbox = $inboxDir; log = $eventsRoot; index = $indexPath; pages_dir = $pagesDir; pages = $pages.Count
            evidence_repos = @($repos); online = $onlineNote; today = "$dateText ($todaySource)"
        }
    }
    $text = ConvertTo-Json -InputObject $doc -Depth 6
} else {
    $sb = [System.Text.StringBuilder]::new()
    $null = $sb.AppendLine('# Wiki lint report').AppendLine()
    $null = $sb.AppendLine("Measured against $dateText ($todaySource). Lint reports and changes nothing.").AppendLine()
    foreach ($c in $Classes) {
        $rows = @($ordered | Where-Object { $_.class -eq $c })
        $null = $sb.AppendLine("## $c ($($rows.Count))").AppendLine()
        if ($rows.Count -eq 0) { $null = $sb.AppendLine('None.').AppendLine(); continue }
        foreach ($f in $rows) {
            $evs = if ($f.events.Count -gt 0) { ' -- events ' + (($f.events | ForEach-Object { "``$_``" }) -join ', ') } else { '' }
            $null = $sb.AppendLine("- ``$($f.id)``$evs -- $($f.reason)")
        }
        $null = $sb.AppendLine()
    }
    $null = $sb.AppendLine('## Totals').AppendLine()
    $null = $sb.AppendLine('| Class | Count |').AppendLine('|---|---|')
    foreach ($c in $totals.Keys) { $null = $sb.AppendLine("| $c | $($totals[$c]) |") }
    $null = $sb.AppendLine()
    $null = $sb.AppendLine("Evidence: $($cites.Count) citation(s) read, $evResolved resolved, $evDead dead, $evUnchecked unchecked. A dead count covers only the citations lint resolved.")
    foreach ($why in $uncheckedWhy.Keys) { $null = $sb.AppendLine("- unchecked, $($why): $($uncheckedWhy[$why])") }
    $null = $sb.AppendLine()
    $null = $sb.AppendLine('## Inputs').AppendLine()
    $null = $sb.AppendLine($inputsLine).AppendLine()
    $null = $sb.AppendLine("- inbox: $(if ($inboxDir) { $inboxDir } else { '(none)' }) -- $inboxNote")
    $null = $sb.AppendLine("- log: $(if ($eventsRoot) { $eventsRoot } else { '(none)' }) -- $logNote")
    $null = $sb.AppendLine("- index: $(if ($indexPath) { $indexPath } else { '(none)' }) -- $indexNote")
    $null = $sb.AppendLine("- pages: $(if ($pagesDir) { $pagesDir } else { '(none)' }) -- $pagesNote")
    $null = $sb.AppendLine("- evidence repos: $repoText")
    $null = $sb.AppendLine("- online pull request check: $onlineNote")
    if ($eventsRead -eq 0) { $null = $sb.AppendLine().AppendLine('WARNING: no event was read, so every event-based zero above measured nothing.') }
    $null = $sb.AppendLine()
    $null = $sb.AppendLine('Promotion candidates are listed only. Drafting the playbook pull request is the scheduled Claude Code job''s work, and it opens that pull request as a DRAFT that only the Owner decides (spec FR-022).')
    $text = $sb.ToString()
}

if ($Out) {
    [System.IO.File]::WriteAllText($Out, $text, [System.Text.UTF8Encoding]::new($false))
    [Console]::Error.WriteLine("wiki lint: report written to $Out; $($ordered.Count) finding(s), $evUnchecked unchecked citation(s)")
} else {
    Write-Output $text.TrimEnd()
}
[Console]::Error.WriteLine("wiki lint: $inputsLine")
exit 0
