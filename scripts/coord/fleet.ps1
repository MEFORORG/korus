#Requires -Version 7.3
<#
.SYNOPSIS
    Project the fleet from the episode records seat.ps1 wrote: the roster a session on a DIFFERENT
    account reads to rebuild a fleet after an account switch.

.DESCRIPTION
    A PURE READER over <git-common-dir>/ccx-coord/seats/. It writes nothing except its own render to
    stdout, and it holds NO liveness opinion of its own: the fence is session-registry.ps1's and the
    cwd-to-worktree match is occupancy.ps1's, both dot-sourced. A second copy of a safety check is
    how the copy nobody tests becomes the copy in use.

        fleet.ps1                  # roster, receipt first (same as -Text)
        fleet.ps1 -Text -All       # do not fold stale rows
        fleet.ps1 -Json            # machine-readable; the contract is in docs/SCRIPTS.md
        fleet.ps1 -Chip -BoxKey <box> -SessionKey <key>   # a standalone briefing for one row

    PORTED FROM THE ENGINE REPOSITORY'S scripts/coord/fleet.ps1, AND ADAPTED TO KORUS RATHER THAN
    THE OTHER WAY ROUND. Three differences, each read off this tree:

      * THE SEATS ROOT IS WHERE seat.ps1 WRITES. seat.ps1 joins `ccx-coord/seats` onto the git
        common dir by a literal name and does not read the configured prefix. This reads the same
        literal. Get-CcxStateRoot is NOT used: it creates the directory, and this script writes
        nothing, and it follows the prefix, which seat.ps1 does not.
      * THE RECORD SHAPE IS seat.ps1's: seat, goal, done_when, out_of_scope, handoff, worktree,
        branch, session, declared_at, updated_at, closed_at. A korus record carries no session id
        unless the writer was given one, so the fence is joined by SESSION where the record names one
        and by WORKTREE where it does not. Each row says which, in FenceBasis.
      * ENGINE-ONLY INPUTS ARE STATED ABSENT, NOT GUESSED. The engine's writer heartbeat, its
        handoffs directory, and the claims, allocations and stash fields of its records have no
        writer in korus. The receipt's `notCarried` names each one, so a reader sees an absence
        rather than a zero that looks measured.

    WHY THE RECEIPT COMES BEFORE THE ROSTER, AND WHY IT CAN REFUSE. An empty roster and a dead
    writer print the same thing. The reader of this output is the person least able to notice: they
    are reading it because they lost the context that would have told them. So the receipt states
    what was EXAMINED, and any stop condition below tells the reader not to treat the roster as
    complete.

    THE DENOMINATOR IS THE POINT. Joining records to the fence says nothing about a session that
    wrote NO record. `liveSessionsWithoutRecord` starts from the fence and subtracts, so a session
    that never declared shows up as a positive count instead of as silence.

    EVERY VERDICT IS COMPUTED AT READ TIME AND NONE IS STORED. A stored verdict is read after the
    world moved.
#>
[CmdletBinding()]
param(
    [switch]$Text,
    [switch]$Json,
    [switch]$All,
    [switch]$Chip,
    [string]$BoxKey,
    [string]$SessionKey,
    [int]$FoldDays = 7,
    # The repository to read. Defaults to the current directory.
    [string]$RepoHint,
    # Read seat records from this directory instead of <git-common-dir>/ccx-coord/seats. For a test
    # fixture, or for pointing the reader at another clone's records as a control.
    [string]$SeatsRoot,
    # Read the session registry from these config roots instead of discovering <home>/.claude*.
    [string[]]$ConfigRoot
)

$ErrorActionPreference = 'Stop'

# The fence, the matcher and the path rule. occupancy.ps1 dot-sources session-registry.ps1 and
# _common.ps1 itself.
. "$PSScriptRoot/occupancy.ps1"

function Get-Field($Obj, [string]$Name) {
    if ($null -eq $Obj) { return $null }
    $p = $Obj.PSObject.Properties[$Name]
    if ($p) { return $p.Value }
    return $null
}

# ConvertFrom-Json parses an ISO stamp into a [DateTime]. Casting that to [string] drops the offset
# and re-parsing reads it as LOCAL time, so handle the [DateTime] case before any string parse.
function Get-StampUtc($iso) {
    if (-not $iso) { return $null }
    try {
        if ($iso -is [DateTime]) {
            if ($iso.Kind -eq [DateTimeKind]::Utc) { return $iso }
            return $iso.ToUniversalTime()
        }
        if ($iso -is [DateTimeOffset]) { return $iso.UtcDateTime }
        return [DateTimeOffset]::Parse([string]$iso, [cultureinfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal).UtcDateTime
    }
    catch { return $null }
}

function Get-RecordStampUtc($rec) {
    # `asOf` is the engine repository's record shape, read so a foreign record still dates.
    foreach ($name in 'updated_at', 'declared_at', 'asOf') {
        $u = Get-StampUtc (Get-Field $rec $name)
        if ($null -ne $u) { return $u }
    }
    return $null
}

$repo = if ($RepoHint) { $RepoHint } else { (Get-Location).Path }
$common = Get-CcxGitCommonDir -Repo $repo
if (-not $common) {
    # Not Write-Error: under ErrorActionPreference Stop it ends the script with exit 1, and the
    # documented code for this case is 2.
    [Console]::Error.WriteLine('fleet.ps1: not inside a git repository (or git failed). Cannot locate the seats layer.')
    exit 2
}
# The literal seat.ps1 writes to. Keep the two in step: a reader pointed somewhere else reads an
# empty directory and reports it as an empty fleet.
$seatsDir = if ($SeatsRoot) { $SeatsRoot } else { Join-Path (Join-Path $common 'ccx-coord') 'seats' }

# ---------------------------------------------------------------------------------------------
# Gather. Records first, then the fence, then the denominator.
# ---------------------------------------------------------------------------------------------

$records = @()
$unreadableRecords = 0
$seatsDirPresent = Test-Path -LiteralPath $seatsDir -PathType Container
if ($seatsDirPresent) {
    foreach ($d in @(Get-ChildItem -LiteralPath $seatsDir -Directory -EA SilentlyContinue |
                Where-Object { $_.Name -notlike '.*' })) {
        foreach ($f in @(Get-ChildItem -LiteralPath $d.FullName -Filter *.json -File -EA SilentlyContinue)) {
            try {
                $j = Get-Content -LiteralPath $f.FullName -Raw -EA Stop | ConvertFrom-Json -EA Stop
                if ($null -eq $j) { throw 'empty' }
                $records += [pscustomobject]@{ Rec = $j; File = $f.FullName; Box = $d.Name; Key = $f.BaseName }
            }
            catch {
                # A record being written RIGHT NOW has exactly this shape. Counted, never dropped:
                # dropping turns an occupied seat into an absent one in the receipt's own numbers.
                $unreadableRecords++
            }
        }
    }
}

# The fence. Its availability is a FACT IN THE RECEIPT, not an assumption.
# A malformed registry entry can throw inside the matcher. That is an unavailable fence, never a
# crash with no receipt.
try {
    $occ = Get-WorktreeOccupancy -Repo $repo -ConfigRoot $ConfigRoot
}
catch {
    $occ = [pscustomobject]@{
        Available = $false; Detail = "session registry could not be read: $($_.Exception.Message)"
        RootsExamined = 0; RecordsExamined = 0; RecordsUnplaceable = 0; Worktrees = @(); Sessions = @()
    }
}
# AVAILABLE MEANS THE FENCE HAD SOMETHING TO EXAMINE: a config root, and at least one readable
# session record in it. Unplaceable records do not withdraw it here, unlike occupancy's own
# Available, because this reader destroys nothing; they get their own stop condition instead.
$fenceAvailable = ($occ.RootsExamined -gt 0) -and ($occ.RecordsExamined -gt 0) -and
    -not ($occ.Detail -like 'session registry*')
$sessionsInRepo = @($occ.Sessions)
$liveInRepo = @($sessionsInRepo | Where-Object { $_.State -eq 'LIVE' })
$possiblyLiveInRepo = @($sessionsInRepo | Where-Object { $_.State -in @('UNVERIFIED', 'UNREADABLE') })

# seat.ps1 sanitises the session key it writes, so the fence's id is sanitised the same way.
function ConvertTo-SessionKey([string]$Id) { return ($Id -replace '[^A-Za-z0-9._-]', '-') }

# Could this session have written this record? Only if the record was last written after the
# session started. A record from an earlier session in the same checkout is older than the session
# now sitting there, and that session wrote nothing. One minute of slack covers clock jitter.
function Test-SessionCouldHaveWritten($Session, $Rec) {
    $started = Get-StampUtc ([string]$Session.StartedAt)
    $stamp = Get-RecordStampUtc $Rec
    if ($null -eq $started -or $null -eq $stamp) { return $true }
    return ($stamp -ge $started.AddMinutes(-1))
}

# Does an OPEN record cover this session? By session id anywhere in the repository where the record
# names one, since a session can declare from a worktree other than the one it started in. By
# worktree, and by time, where the record is `unnamed-session`. A closed record covers nobody.
function Test-SessionHasRecord($Session) {
    $tree = ConvertTo-CcxComparablePath -Path $Session.WorktreePath
    $sid = ConvertTo-SessionKey ([string]$Session.SessionId)
    foreach ($r in $records) {
        if (Get-Field $r.Rec 'closed_at') { continue }
        $key = [string](Get-Field $r.Rec 'session')
        if (-not $key) { $key = $r.Key }
        if ($key -and $key -ne 'unnamed-session') {
            if ($sid -and $sid.StartsWith($key, 'OrdinalIgnoreCase')) { return $true }
        }
        elseif ((ConvertTo-CcxComparablePath -Path ([string](Get-Field $r.Rec 'worktree'))) -eq $tree -and
            (Test-SessionCouldHaveWritten $Session $r.Rec)) { return $true }
    }
    return $false
}
$liveWithoutRecord = @($liveInRepo | Where-Object { -not (Test-SessionHasRecord $_) })
$possiblyLiveWithoutRecord = @($possiblyLiveInRepo | Where-Object { -not (Test-SessionHasRecord $_) })

# ---------------------------------------------------------------------------------------------
# How fresh is the trunk every verdict would be judged against?
#
# A remote-tracking ref is refreshed only by a fetch, so the age of the last fetch OF THE TRUNK is
# the age of the ref. FETCH_HEAD records WHAT was fetched, one line per ref, and is per-worktree, so
# every worktree's copy is read and the newest one naming origin's trunk wins. The ref file's mtime
# and the reflog both record ref MOVEMENTS, not fetches, and are deliberately not used. This works
# offline: a stranded session runs it, so it makes no network call.
# ---------------------------------------------------------------------------------------------

$trunk = $null
try { $trunk = Get-CcxTrunk -Repo $repo } catch { $trunk = $null }
# Only a trunk on origin can be timed by origin's fetch clock. Any other trunk is named in the
# receipt and the clock falls back to origin's `main`.
$trunkOnOrigin = [bool]($trunk -and $trunk -match '^(refs/remotes/)?origin/')
$mainBranch = if ($trunkOnOrigin) { $trunk -replace '^(refs/remotes/)?origin/', '' } else { 'main' }
$originMainSha = Invoke-CcxGit -Repo $repo -Arguments @('rev-parse', '--verify', '--quiet', "refs/remotes/origin/$mainBranch")

# Both sides of the url compare go through this: git CONFIGURES `git@host:org/repo.git` and WRITES
# `host:org/repo` into FETCH_HEAD, dropping the `.git` suffix and any `user@` part. Nothing else is
# folded; an ssh alias and an https url are genuinely not comparable.
function ConvertTo-ComparableUrl([string]$u) {
    if (-not $u) { return '' }
    $s = ($u.Trim() -replace '\\', '/').TrimEnd('/')
    if ($s.EndsWith('.git', [System.StringComparison]::OrdinalIgnoreCase)) { $s = $s.Substring(0, $s.Length - 4) }
    $s = $s -replace '^([A-Za-z][A-Za-z0-9+.-]*://)?[^/@]+@', '$1'
    return $s.TrimEnd('/').ToLowerInvariant()
}

# Does this FETCH_HEAD record a fetch of origin's trunk? A pull-ref fetch or another remote's fetch
# bumps the clock and leaves the ref alone, so it must not count.
function Test-FetchHeadNamesOriginMain([string]$Path, [string]$Branch, [string]$Url) {
    if (-not $Url) { return $false }
    $wanted = "branch '$Branch' of "
    try { $lines = @(Get-Content -LiteralPath $Path -EA Stop) } catch { return $false }
    foreach ($line in $lines) {
        $parts = $line -split "`t"
        if ($parts.Count -lt 3) { continue }
        $desc = ($parts[2..($parts.Count - 1)] -join "`t").Trim()
        if (-not $desc.StartsWith($wanted, [System.StringComparison]::Ordinal)) { continue }
        if ((ConvertTo-ComparableUrl $desc.Substring($wanted.Length)) -eq $Url) { return $true }
    }
    return $false
}

$originUrl = ConvertTo-ComparableUrl (Invoke-CcxGit -Repo $repo -Arguments @('remote', 'get-url', 'origin'))
$fetchClockPaths = @(Join-Path $common 'FETCH_HEAD')
$worktreeGitDirs = Join-Path $common 'worktrees'
if (Test-Path -LiteralPath $worktreeGitDirs) {
    foreach ($d in @(Get-ChildItem -LiteralPath $worktreeGitDirs -Directory -EA SilentlyContinue)) {
        $fetchClockPaths += (Join-Path $d.FullName 'FETCH_HEAD')
    }
}
$allClocks = @($fetchClockPaths |
        ForEach-Object { Get-Item -LiteralPath $_ -EA SilentlyContinue } |
        Sort-Object LastWriteTimeUtc -Descending)

$originMainFetchAgeMinutes = $null
# NEVER NULL: a blank value beside a null age is how a blind instrument passes for a healthy one.
$originMainFetchClock = 'UNMEASURABLE -- no FETCH_HEAD in this clone (see stop conditions)'
$originMainFetchStop = "originMainFetchAgeMinutes=UNMEASURABLE -- no FETCH_HEAD exists anywhere in this clone, so this instrument cannot tell a fetch made seconds ago from one never made. Run ``git fetch origin``"
$mainClock = $null
foreach ($c in $allClocks) {
    if (Test-FetchHeadNamesOriginMain $c.FullName $mainBranch $originUrl) { $mainClock = $c; break }
}
if ($null -ne $mainClock) {
    $originMainFetchAgeMinutes = [int]([DateTime]::UtcNow - $mainClock.LastWriteTimeUtc).TotalMinutes
    $originMainFetchClock = $mainClock.FullName
    $originMainFetchStop = $null
}
elseif ($allClocks.Count -ge 1) {
    $originMainFetchClock = "UNMEASURABLE -- $($allClocks.Count) FETCH_HEAD file(s) here, none naming origin/$mainBranch (newest: $($allClocks[0].FullName))"
    $originMainFetchStop = "originMainFetchAgeMinutes=UNMEASURABLE -- $($allClocks.Count) FETCH_HEAD file(s) exist and none records a fetch of origin/$mainBranch, so the cached ref is of unknown age. Run ``git fetch origin``"
}

# ---------------------------------------------------------------------------------------------
# Classify. Every state is derived here and none is read from a record.
# ---------------------------------------------------------------------------------------------

$now = [DateTime]::UtcNow

# Most-alive first, the same ranking session-registry.ps1's Get-SessionLiveness uses.
$rank = @{ 'LIVE' = 0; 'UNVERIFIED' = 1; 'UNREADABLE' = 2; 'STALE' = 3; 'DEAD' = 4 }

# The handoff pointer, resolved at read time. seat.ps1 stores it as given, so a relative path is
# relative to the record's worktree.
#
# A record of another shape must not take the reader down. The engine repository writes `handoff`
# as an object with a `path` field, so that is read too, and anything else that fails to resolve
# is reported as `unreadable` rather than thrown.
function Resolve-HandoffState($rec) {
    $raw = Get-Field $rec 'handoff'
    if ($raw -and -not ($raw -is [string])) { $raw = Get-Field $raw 'path' }
    $h = [string]$raw
    if (-not $h) { return @{ Path = $null; State = $null } }
    $full = $h
    try {
        $wt = [string](Get-Field $rec 'worktree')
        if (-not [System.IO.Path]::IsPathRooted($h) -and $wt) { $full = Join-Path $wt $h }
        if (Test-Path -LiteralPath $full -PathType Leaf) { return @{ Path = $full; State = 'resolves' } }
        return @{ Path = $full; State = 'dangling' }
    }
    catch { return @{ Path = $full; State = 'unreadable' } }
}

$rows = @()
foreach ($r in $records) {
    $rec = $r.Rec
    $wt = [string](Get-Field $rec 'worktree')
    $wtNorm = ConvertTo-CcxComparablePath -Path $wt
    $key = [string](Get-Field $rec 'session')
    if (-not $key) { $key = $r.Key }

    # FENCE, positive answers only. Nothing here can PROVE a session is gone.
    #   session  : the record names a session, and the fence is joined on that id.
    #   worktree : the record names none (seat.ps1 falls back to `unnamed-session`), so it is joined
    #              on the worktree, which is what the record is keyed on in that case.
    #   A session-keyed record whose id the fence does not find falls back to the worktree, but can
    #   only reach UNVERIFIED that way: another session in the same checkout is not proof this one
    #   is running, and it is not proof it stopped either.
    $fence = 'UNKNOWN'
    $basis = 'none'
    if ($fenceAvailable -and $wtNorm) {
        $here = @($sessionsInRepo | Where-Object { (ConvertTo-CcxComparablePath -Path $_.WorktreePath) -eq $wtNorm })
        $othersHere = @($here | Where-Object { Test-OccupancyVeto $_.State }).Count -gt 0
        if ($key -and $key -ne 'unnamed-session') {
            $basis = 'session'
            # Across the whole repository: the session may have started in another worktree.
            $hit = @($sessionsInRepo | Where-Object { $_.SessionId -and (ConvertTo-SessionKey ([string]$_.SessionId)).StartsWith($key, 'OrdinalIgnoreCase') })
            if ($hit.Count -gt 0) { $fence = ($hit | Sort-Object { $rank[$_.State] } | Select-Object -First 1).State }
            elseif ($othersHere) { $basis = 'worktree'; $fence = 'UNVERIFIED' }
        }
        else {
            $basis = 'worktree'
            # Only a session that could have written this record vouches for it. A newer session in
            # the same checkout proves neither that this one is running nor that it stopped.
            $writers = @($here | Where-Object { Test-SessionCouldHaveWritten $_ $rec })
            if ($writers.Count -gt 0) { $fence = ($writers | Sort-Object { $rank[$_.State] } | Select-Object -First 1).State }
            elseif ($othersHere) { $fence = 'UNVERIFIED' }
        }
    }

    $closed = [bool](Get-Field $rec 'closed_at')
    $stamp = Get-RecordStampUtc $rec
    $ageH = if ($null -ne $stamp) { [Math]::Round(($now - $stamp).TotalHours, 1) } else { $null }

    # SUPERSEDED: a newer record in the same box. Compared on the unrounded stamps, and only after
    # the fence, so the older of two sessions still running in one worktree reads as running.
    $superseded = $false
    foreach ($o in $records) {
        if ($o.File -eq $r.File -or $o.Box -ne $r.Box) { continue }
        $oStamp = Get-RecordStampUtc $o.Rec
        if ($null -ne $oStamp -and $null -ne $stamp -and $oStamp -gt $stamp) { $superseded = $true }
    }

    $state = switch ($true) {
        { $closed } { 'CLOSED'; break }
        { $fence -eq 'LIVE' } { 'RUNNING'; break }
        { $fence -in @('UNVERIFIED', 'UNREADABLE') } { 'POSSIBLY RUNNING'; break }
        { $superseded } { 'SUPERSEDED'; break }
        { -not $fenceAvailable } { 'UNKNOWN-NO-FENCE'; break }
        default { 'INTERRUPTED' }
    }
    if ($state -eq 'INTERRUPTED' -and $null -ne $ageH -and $ageH -gt ($FoldDays * 24)) { $state = 'ORPHANED-STALE' }

    $seatName = [string](Get-Field $rec 'seat')
    $hs = Resolve-HandoffState $rec
    $rows += [pscustomobject]@{
        Box            = $r.Box
        SessionKey     = $key
        Seat           = if ($seatName) { $seatName } else { $null }
        Goal           = [string](Get-Field $rec 'goal')
        State          = $state
        Fence          = $fence
        FenceBasis     = $basis
        AgeHours       = $ageH
        Branch         = [string](Get-Field $rec 'branch')
        Worktree       = $wt
        WorktreeExists = [bool]($wt -and (Test-Path -LiteralPath $wt -PathType Container))
        HandoffPath    = $hs.Path
        HandoffState   = $hs.State
        Rec            = $rec
    }
}

# ---------------------------------------------------------------------------------------------
# The receipt, and the stop conditions it can fire.
# ---------------------------------------------------------------------------------------------

$ptr = @($rows | Where-Object { $_.HandoffPath })
$ptrDangling = @($ptr | Where-Object { $_.HandoffState -eq 'dangling' }).Count

$stops = @()
if (-not $fenceAvailable) { $stops += "fenceAvailable=false -- $($occ.Detail); every state below would be a guess" }
if ($occ.RecordsUnplaceable -gt 0) { $stops += "sessionRecordsUnplaceable=$($occ.RecordsUnplaceable) -- a session record could not be placed in any worktree, so liveSessionsInRepo may undercount" }
if ($possiblyLiveWithoutRecord.Count -gt 0) { $stops += "possiblyLiveSessionsWithoutRecord=$($possiblyLiveWithoutRecord.Count) -- a session the fence could not rule out has written no seat record" }
if ($unreadableRecords -gt 0) { $stops += "recordsUnreadable=$unreadableRecords -- a seat record could not be parsed, so its row is missing below" }
if ($liveWithoutRecord.Count -gt 0) { $stops += "liveSessionsWithoutRecord=$($liveWithoutRecord.Count) -- a live session in this repository has written no seat record, so this roster is INCOMPLETE by at least that many" }
if ($records.Count -eq 0) { $stops += 'recordsExamined=0 -- indistinguishable from seat.ps1 never having run in this clone' }
if ($null -eq $originMainFetchAgeMinutes) { $stops += $originMainFetchStop }
elseif ($originMainFetchAgeMinutes -gt 60) {
    $stops += "originMainFetchAgeMinutes=$originMainFetchAgeMinutes -- the newest fetch of origin/$mainBranch in this clone is that old, so branch state below may be stale"
}
if ($ptrDangling -gt 0) { $stops += "handoffPointersDangling=$ptrDangling of $($ptr.Count) -- a seat told to READ THE HANDOFF would be sent to a file that is missing" }

$receipt = [ordered]@{
    renderedAtUtc             = $now.ToString('yyyy-MM-ddTHH:mm:ssZ')
    seatsDir                  = $seatsDir
    seatsDirPresent           = $seatsDirPresent
    rootsExamined             = $occ.RootsExamined
    fenceAvailable            = $fenceAvailable
    sessionRecordsExamined    = $occ.RecordsExamined
    sessionRecordsUnplaceable = $occ.RecordsUnplaceable
    recordsExamined           = $records.Count
    recordsUnreadable         = $unreadableRecords
    liveSessionsInRepo        = $liveInRepo.Count
    liveSessionsWithoutRecord = $liveWithoutRecord.Count
    possiblyLiveSessionsInRepo = $possiblyLiveInRepo.Count
    possiblyLiveSessionsWithoutRecord = $possiblyLiveWithoutRecord.Count
    repoWorktrees             = @($occ.Worktrees).Count
    trunk                     = $trunk
    trunkOnOrigin             = $trunkOnOrigin
    originMainSha             = $originMainSha
    originMainFetchAgeMinutes = $originMainFetchAgeMinutes
    originMainFetchClock      = $originMainFetchClock
    handoffPointers           = $ptr.Count
    handoffPointersDangling   = $ptrDangling
    # Inputs the engine repository's fleet.ps1 reads that have no writer in korus. Stated, so a
    # missing number is never read as a measured zero.
    notCarried                = @(
        'writerHeartbeat -- korus seat.ps1 writes no .writer-alive heartbeat',
        'handoffsDirectory -- the handoffs/ directory exists only in the engine repository''s coordination directory',
        'claims, allocations, stashSha, touchedPaths -- korus seat records do not carry these fields'
    )
    stopConditions            = @($stops)
}

# ---------------------------------------------------------------------------------------------
# Render.
# ---------------------------------------------------------------------------------------------

$code = if ($fenceAvailable) { 0 } else { 2 }

if ($Chip) {
    $row = $rows | Where-Object { $_.Box -eq $BoxKey -and $_.SessionKey -eq $SessionKey } | Select-Object -First 1
    if (-not $row) { [Console]::Error.WriteLine("fleet.ps1: no record for $BoxKey/$SessionKey"); exit 2 }
    $rec = $row.Rec
    $stampUtc = Get-RecordStampUtc $rec
    $asOf = if ($null -ne $stampUtc) { $stampUtc.ToString('o') } else { 'an unknown time' }
    $lines = @()
    # The briefing presumes its predecessor is gone, so it says loudly when the row does not show
    # that. Starting a replacement for a seat that is still running is two sessions on one worktree.
    $lines += "ROW STATE: $($row.State)   (fence $($row.Fence), joined by $($row.FenceBasis))"
    if ($row.State -notin @('INTERRUPTED', 'ORPHANED-STALE')) {
        $lines += "WARNING: THIS ROW IS $($row.State), NOT INTERRUPTED. A replacement is not called for unless you have"
        $lines += 'other evidence the predecessor is gone. Check before you start one.'
    }
    if ($stops.Count -gt 0) {
        $lines += "STOP CONDITIONS FIRED -- $($stops.Count). The row state above may be wrong:"
        foreach ($st in $stops) { $lines += "  - $st" }
    }
    $lines += ''
    $lines += 'You are a REPLACEMENT SEAT. The session that held this work is gone. You inherit nothing'
    $lines += "from it except what is written below, which was recorded as of $asOf. Re-verify before you act."
    $lines += ''
    $lines += "PREDECESSOR CHECKOUT: $($row.Worktree)"
    $lines += "BRANCH: $($row.Branch)   (named by branch, never by a commit id: a rebase reissues the id)"
    $lines += ''
    if ($row.Seat) { $lines += "SEAT: $($row.Seat)" } else { $lines += 'SEAT: NOT DECLARED. Do not invent a role.' }
    if ($row.Goal) { $lines += "GOAL AS DECLARED: $($row.Goal)" } else { $lines += 'GOAL: NOT DECLARED.' }
    $doneWhen = [string](Get-Field $rec 'done_when')
    $oos = [string](Get-Field $rec 'out_of_scope')
    if ($doneWhen) { $lines += "DONE MEANS: $doneWhen" }
    if ($oos) { $lines += "OUT OF SCOPE: $oos" }
    $lines += ''
    $lines += 'FIRST ACTIONS, IN THIS ORDER, BEFORE ANY BUILDING:'
    $lines += '  1. Look at the predecessor checkout. Uncommitted work there is the only thing that truly dies:'
    $lines += "     git -C `"$($row.Worktree)`" status --porcelain"
    $lines += "     git -C `"$($row.Worktree)`" log --oneline origin/$mainBranch..HEAD"
    $lines += '  2. git fetch origin first, then decide whether the work already landed. Compare content, not'
    $lines += '     ancestry: squash-merge makes the two disagree routinely.'
    $lines += '  3. Re-check claims before taking any (scripts/coord/claim.ps1 -List). This record carries none.'
    if ($row.HandoffPath) {
        $lines += ''
        $lines += "  4. READ THE HANDOFF: $($row.HandoffPath)"
        if ($row.HandoffState -ne 'resolves') { $lines += '     WARNING: THAT FILE IS NOT THERE NOW. Treat it as a lead, not a document.' }
    }
    $lines += ''
    $lines += '  5. Declare yourself so the next reader finds fresh state:'
    $lines += '     pwsh -NoProfile -File scripts/coord/seat.ps1 -Declare -Seat <seat> -Goal "..."'
    $lines += ''
    $lines += 'ACCOUNT BOUNDARY: usage figures, project memory and the realtime send channel do not cross'
    $lines += 'accounts. Read your own.'
    $lines -join "`n"
    exit 0
}

if ($Json) {
    [ordered]@{
        receipt = $receipt
        rows    = @($rows | Select-Object Box, SessionKey, Seat, Goal, State, Fence, FenceBasis, AgeHours,
            Branch, Worktree, WorktreeExists, HandoffPath, HandoffState)
    } | ConvertTo-Json -Depth 8
    exit $code
}

# Default: text.
'FLEET CONTINUITY ROSTER'
"rendered $($receipt.renderedAtUtc)"
''
'RECEIPT -- what was EXAMINED, not merely what was found:'
foreach ($k in $receipt.Keys) {
    if ($k -in @('stopConditions', 'notCarried')) { continue }
    # A null must not render as whitespace: a blank column reads exactly like a quiet, healthy one.
    $v = if ($null -eq $receipt[$k]) { '(null)' } else { $receipt[$k] }
    '  {0,-34} {1}' -f $k, $v
}
'  not carried in korus:'
foreach ($n in $receipt.notCarried) { "    - $n" }
''
if ($stops.Count -gt 0) {
    "STOP CONDITIONS FIRED -- $($stops.Count). DO NOT TREAT THE ROSTER BELOW AS COMPLETE:"
    foreach ($s in $stops) { "  - $s" }
    ''
}
else {
    'NO STOP CONDITIONS. The roster below is as complete as this instrument can establish.'
    ''
}

$shown = if ($All) { $rows } else { @($rows | Where-Object { $_.State -ne 'ORPHANED-STALE' }) }
$folded = @($rows).Count - @($shown).Count

if (@($rows).Count -eq 0) {
    "NO EPISODE RECORDS EXIST. That is NOT the same as 'no seats were working' -- see the receipt above."
}
else {
    '{0,-44} {1,-20} {2,-14} {3,-18} {4,-7} {5}' -f 'BOX', 'KEY', 'SEAT', 'STATE', 'AGE_H', 'BRANCH'
    foreach ($row in ($shown | Sort-Object State, Box)) {
        $seatName = if ($row.Seat) { $row.Seat } else { 'NOT-DECLARED' }
        $gone = if (-not $row.WorktreeExists) { ' [WORKTREE GONE]' } else { '' }
        '{0,-44} {1,-20} {2,-14} {3,-18} {4,-7} {5}{6}' -f $row.Box, $row.SessionKey, $seatName, $row.State, $row.AgeHours, $row.Branch, $gone
    }
}
if ($folded -gt 0) { ''; "$folded row(s) folded as ORPHANED-STALE (older than $FoldDays days). Show with -All." }

''
'RESPAWN POPULATION (INTERRUPTED): ' + @($rows | Where-Object { $_.State -eq 'INTERRUPTED' }).Count
'  Never respawned: RUNNING, POSSIBLY RUNNING, SUPERSEDED, CLOSED.'
'  Briefing for one row:  fleet.ps1 -Chip -BoxKey <box> -SessionKey <key>'

exit $code
