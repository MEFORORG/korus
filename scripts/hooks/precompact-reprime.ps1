#Requires -Version 7.3
<#
.SYNOPSIS
    SessionStart hook, scoped to the `compact` source: put back the ledger facts a compaction
    destroys.

.DESCRIPTION
    POSTURE: FAILS OPEN, AND NEVER BLOCKS. Every path exits 0.

    WHAT A COMPACTION TAKES. A compaction summarises the conversation, and everything a session
    knows about its own held state lives in that conversation: which numbers this worktree
    allocated, which keys it claimed, and whether the branch is pushed. Afterwards the session has
    no idea it is holding an unfiled allocation, and an unfiled number BURNS if the worktree is
    removed. Allocation is a one-way door: numbers are never reclaimed.

    WHY IT READS RATHER THAN ASKS. At SessionStart the right move is to ask, because nothing is
    known yet and a machine that invents an intent writes a record that looks declared and says
    nothing. After a compaction the record ALREADY EXISTS on disk. The compaction dropped it from
    context, not from the record. So this hook reads it back, which restates a stated intent
    rather than inventing one.

    IT RESTORES BOTH HALVES. The DECLARATION half reads scripts/coord/seat.ps1's episode record:
    the seat, the goal, and what the session said it would not do. The LEDGER half reads what this
    worktree holds from scripts/coord/alloc.ps1 and claim.ps1, which is the half with a PERMANENT
    cost attached -- an allocated number that is never filed BURNS.

    THE DECLARATION HALF SHIPPED SECOND, and the gap was not an oversight. Until seat.ps1 existed
    there was no declaration on disk to read, and a hook that filled the gap by inferring a goal
    would have written exactly the record this design refuses: one that looks declared and says
    nothing.

    LEGIBLE SILENCE. Holding nothing and being unable to read the ledger have opposite fixes, so
    they must not both render as blank. Each says which it is.

    IT FLAGS A RECORD THAT IS PROBABLY A PREVIOUS OCCUPANT'S. A worktree outlives the sessions in
    it. A claim whose recorded branch differs from the branch checked out now is more likely to be
    an earlier session's than this one's, and restoring it as current intent would be a
    confidently-wrong coordination fact.

    IT RUNS AT SessionStart, NOT PreCompact. It was wired on PreCompact first, and it put nothing
    back there. The harness refuses `PreCompact` as a hookSpecificOutput.hookEventName, and
    PreCompact fires BEFORE the summary is written, so anything it added would be summarised away.
    The MessageFoundry copy of this hook measured both on 2026-09-15 and moved to SessionStart; this
    copy follows it. The payload now names `SessionStart`.

    THE SOURCE GUARD LIVES HERE, AND IT IS THE ONLY ONE. The settings row stays match-all, with no
    `"matcher": "compact"`, so the guard below is the one place that decides. A plugin or a settings
    row that runs this script must not add a second guard: two guards can disagree, and the one
    that is wrong is silent. The guard goes quiet only when the payload POSITIVELY says this is not
    a compaction restart. No payload, or one it cannot parse, speaks anyway.

    Adopted from gastown, which registers its primer at SessionStart AND PreCompact for this reason.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Context {
    param([string] $Text)
    $payload = [pscustomobject]@{
        hookSpecificOutput = [pscustomobject]@{
            hookEventName     = 'SessionStart'
            additionalContext = $Text
        }
    }
    [Console]::Out.Write(($payload | ConvertTo-Json -Compress -Depth 6))
}

function Compare-Path {
    # Case- and separator-insensitive, which is what a Windows path comparison needs. A raw string
    # compare reports two spellings of one worktree as two worktrees.
    param([string] $A, [string] $B)
    if (-not $A -or -not $B) { return $false }
    $na = ($A -replace '/', '\').TrimEnd('\').ToLowerInvariant()
    $nb = ($B -replace '/', '\').TrimEnd('\').ToLowerInvariant()
    return $na -eq $nb
}

# ---- scope: a compaction restart, and nothing else --------------------------------------------
# Read before any other work, so a cold start costs one JSON parse and exits.
$hookSource = ''
$hookEvent = ''
try {
    $raw = [Console]::In.ReadToEnd()
    if ($raw) {
        $payload = $raw | ConvertFrom-Json -ErrorAction Stop
        $names = @($payload.PSObject.Properties.Name)
        if ($names -contains 'source' -and $payload.source) { $hookSource = [string]$payload.source }
        if ($names -contains 'hook_event_name' -and $payload.hook_event_name) {
            $hookEvent = [string]$payload.hook_event_name
        }
    }
}
catch {
    # An unreadable payload is the fail-open case: both stay empty and the hook speaks.
}

# The test is "not a compaction", an equality against `compact`. A list of the other sources
# (`startup`, `resume`, `clear`, `fork`) would be one short the day the harness adds one.
# A payload naming another event is a leftover registration, for instance an old PreCompact row.
# Its output never reaches context, so it stays quiet.
if ($hookSource -and $hookSource -ne 'compact') { exit 0 }
if ($hookEvent -and $hookEvent -ne 'SessionStart') { exit 0 }

try {
    $common = (& git rev-parse --path-format=absolute --git-common-dir 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $common) { exit 0 }
    $stateRoot = Join-Path $common.Trim() 'ccx-coord'
    if (-not (Test-Path -LiteralPath $stateRoot)) { exit 0 }

    $top = (& git rev-parse --path-format=absolute --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $top) { exit 0 }
    $top = $top.Trim()

    $branchNow = (& git rev-parse --abbrev-ref HEAD 2>$null)
    if ($branchNow) { $branchNow = $branchNow.Trim() }

    $lines = [System.Collections.Generic.List[string]]::new()
    $readFailed = $false

    # ------------------------------------------------------------------- the declaration, if any
    # THE HALF THAT WAS NOT BUILT UNTIL scripts/coord/seat.ps1 EXISTED. Before it there was no
    # declaration on disk to read, and inventing one is the failure this hook avoids by reading
    # rather than asking.
    $seatsRoot = Join-Path $stateRoot 'seats'
    if (Test-Path -LiteralPath $seatsRoot) {
        try {
            $declared = $null
            $records = Get-ChildItem -LiteralPath $seatsRoot -Recurse -Filter '*.json' -File -ErrorAction Stop |
                Sort-Object LastWriteTimeUtc -Descending
            foreach ($f in $records) {
                try { $rec = Get-Content -LiteralPath $f.FullName -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
                catch { continue }
                if (-not $rec.PSObject.Properties['worktree']) { continue }
                if (-not (Compare-Path ([string]$rec.worktree) $top)) { continue }
                if ($rec.PSObject.Properties['goal'] -and $rec.goal) { $declared = $rec; break }
            }

            if ($declared) {
                $onBranch = if ($declared.PSObject.Properties['branch']) { [string]$declared.branch } else { '' }
                # A WORKTREE OUTLIVES THE SESSION THAT DECLARED IN IT. A record from another branch
                # is more likely a previous occupant's, and restoring a three-day-old goal as though
                # it were current is worse than restoring nothing: it reads as recovered memory.
                if ($branchNow -and $onBranch -and ($onBranch -ne $branchNow)) {
                    $lines.Add("DECLARATION FOUND, BUT PROBABLY NOT YOURS: seat '$([string]$declared.seat)', declared on '$onBranch' while this worktree is on '$branchNow'.")
                    $lines.Add("  Treat it as a previous occupant's and re-declare rather than adopting it:")
                    $lines.Add("  pwsh -NoProfile -File scripts/coord/seat.ps1 -Declare -Seat <seat> -Goal ""...""")
                }
                else {
                    $lines.Add("SEAT: $([string]$declared.seat)")
                    $lines.Add("GOAL: $([string]$declared.goal)")
                    if ($declared.PSObject.Properties['done_when'] -and $declared.done_when) {
                        $lines.Add("DONE WHEN: $([string]$declared.done_when)")
                    }
                    if ($declared.PSObject.Properties['out_of_scope'] -and $declared.out_of_scope) {
                        $lines.Add("OUT OF SCOPE: $([string]$declared.out_of_scope)")
                    }
                    if ($declared.PSObject.Properties['handoff'] -and $declared.handoff) {
                        $lines.Add("HANDOFF: $([string]$declared.handoff)")
                    }
                }
            }
            else {
                $lines.Add("NO SEAT DECLARED for this worktree, so none was restored. That is a reading, not a failure to look.")
                $lines.Add("  pwsh -NoProfile -File scripts/coord/seat.ps1 -Declare -Seat <seat> -Goal ""...""")
            }
        }
        catch { $readFailed = $true }
    }

    # ---------------------------------------------------------------- allocations this tree holds
    $held = [System.Collections.Generic.List[string]]::new()
    $allocRoot = Join-Path $stateRoot 'alloc'
    if (Test-Path -LiteralPath $allocRoot) {
        try {
            foreach ($f in (Get-ChildItem -LiteralPath $allocRoot -Recurse -Filter '*.json' -File -ErrorAction Stop)) {
                try { $rec = Get-Content -LiteralPath $f.FullName -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
                catch { continue }
                if (-not $rec.PSObject.Properties['worktree']) { continue }
                if (-not (Compare-Path ([string]$rec.worktree) $top)) { continue }
                $kind = if ($rec.PSObject.Properties['kind']) { [string]$rec.kind } else { 'item' }
                $num = if ($rec.PSObject.Properties['number']) { [string]$rec.number } else { $f.BaseName }
                $held.Add("$kind #$num")
            }
        }
        catch { $readFailed = $true }
    }

    if ($held.Count -gt 0) {
        $lines.Add("HELD ALLOCATIONS: $($held -join ', ')")
        $lines.Add(
            "  An allocated number that is never filed BURNS. Allocation is a one-way door and " +
            "numbers are never reclaimed, so if this worktree is removed before the file and its " +
            "index row are committed, that number is gone. Add the index row in the SAME commit as " +
            "the file."
        )
    }

    # ---------------------------------------------------------------------- claims this tree holds
    $mine = [System.Collections.Generic.List[string]]::new()
    $stale = [System.Collections.Generic.List[string]]::new()
    $claimsDir = Join-Path $stateRoot 'claims'
    if (Test-Path -LiteralPath $claimsDir) {
        try {
            foreach ($f in (Get-ChildItem -LiteralPath $claimsDir -Filter '*.json' -File -ErrorAction Stop)) {
                try { $rec = Get-Content -LiteralPath $f.FullName -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
                catch { continue }
                if (-not $rec.PSObject.Properties['worktree']) { continue }
                if (-not (Compare-Path ([string]$rec.worktree) $top)) { continue }

                $key = if ($rec.PSObject.Properties['key']) { [string]$rec.key } else { $f.BaseName }
                $note = if ($rec.PSObject.Properties['note']) { [string]$rec.note } else { '' }
                $onBranch = if ($rec.PSObject.Properties['branch']) { [string]$rec.branch } else { '' }
                $text = if ($note) { "$key -- $note" } else { $key }

                # The discriminator, read before the claim is reported rather than noted after it.
                if ($branchNow -and $onBranch -and ($onBranch -ne $branchNow)) {
                    $stale.Add("$text  [claimed on '$onBranch', this worktree is on '$branchNow']")
                }
                else {
                    $mine.Add($text)
                }
            }
        }
        catch { $readFailed = $true }
    }

    if ($mine.Count -gt 0) {
        $lines.Add("HELD CLAIMS: $($mine -join '; ')")
    }

    if ($stale.Count -gt 0) {
        $lines.Add("CLAIMS THAT MAY NOT BE YOURS: $($stale -join '; ')")
        $lines.Add(
            "  A worktree outlives the sessions in it. Each of those was claimed on a different " +
            "branch, so it is probably a previous occupant's rather than this session's work. " +
            "Confirm before acting on one, and do NOT read it as your current intent."
        )
    }

    # ------------------------------------------------------------------------- is the work pushed
    $upstream = (& git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null)
    if ($LASTEXITCODE -eq 0 -and $upstream) {
        $counts = (& git rev-list --left-right --count "$($upstream.Trim())...HEAD" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $counts) {
            $parts = $counts.Trim() -split '\s+'
            if ($parts.Count -ge 2 -and [int]$parts[1] -gt 0) {
                $lines.Add("UNPUSHED: $($parts[1]) commit(s) on '$branchNow' are not on its upstream.")
            }
        }
    }
    elseif ($branchNow -and $branchNow -ne 'HEAD') {
        $anyCommit = (& git rev-parse --verify HEAD 2>$null)
        if ($LASTEXITCODE -eq 0 -and $anyCommit) {
            $lines.Add("NO UPSTREAM: branch '$branchNow' has never been pushed, so nothing here is recoverable from the remote.")
        }
    }

    # ------------------------------------------------------------------------------- say something
    if ($lines.Count -eq 0) {
        if ($readFailed) {
            Write-Context (
                "[precompact] The ledger COULD NOT BE READ, so this is not a report that you hold " +
                "nothing. Check by hand before assuming a clean slate:  pwsh -NoProfile -File " +
                "scripts/coord/claim.ps1 -List"
            )
        }
        else {
            Write-Context (
                "[precompact] This worktree holds no allocations and no claims, and its branch is " +
                "pushed or has no upstream commits. Nothing to carry across the compaction. This " +
                "is a reading, not a failure to look."
            )
        }
        exit 0
    }

    $body = ($lines -join "`n")
    $caveat = if ($readFailed) {
        "`n`nPART OF THE LEDGER COULD NOT BE READ, so this list may be incomplete. Verify with scripts/coord/claim.ps1 -List."
    }
    else { '' }

    Write-Context (
        "[precompact] A compaction has just dropped what this session knew about its own held " +
        "state. These are read from the ledger on disk, not from the conversation, so they survive " +
        "it:`n`n$body$caveat"
    )
    exit 0
}
catch {
    # Fail open, always. A compaction must never be blocked by this.
    exit 0
}
