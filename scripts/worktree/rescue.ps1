#Requires -Version 7.3
<#
.SYNOPSIS
    Move uncommitted work OUT of the shared primary checkout and into a fresh worktree + branch.

.DESCRIPTION
    The companion to the worktree gate. A gate that stops you writing into the primary is infuriating
    if you are already half-way through a change there -- so this MOVES what you have instead of asking
    you to redo it.

    It stashes the primary's uncommitted work (tracked AND untracked), creates a worktree branched off
    the primary's CURRENT commit -- not the trunk, so the stash applies cleanly -- and applies the
    stash there BY OBJECT NAME.

    THE ENTRY IS NAMED, NEVER TAKEN OFF THE TOP. The stash stack lives in the shared git directory, so
    one stack serves every worktree of this clone. `git stash pop` means `stash@{0}`, and between the
    push and the restore this script runs new.ps1 as a child process -- a fetch and a setup hook,
    seconds to minutes. A peer session stashing inside that window puts ITS entry on top. A bare pop
    then moves the peer's work into this rescue worktree and leaves the rescued work on the stack.

    THE STASH IS THE SAFETY NET. If the restore fails for any reason the work is still recoverable,
    and this script says so -- by object name -- instead of swallowing it. Nothing is ever discarded.

.EXAMPLE
    pwsh -NoProfile -File scripts/worktree/rescue.ps1 -Name alerts-fix
    pwsh -NoProfile -File scripts/worktree/rescue.ps1 -Name alerts-fix -NoSetup
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('\A[A-Za-z0-9._-]+\z')]
    [string]$Name,

    # Forwarded to new.ps1: create the worktree without running the repository's setup hook.
    [switch]$NoSetup
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot '../coord/_common.ps1')

function Get-RescueStashSha {
    <#
    .SYNOPSIS
        Object name of the stash entry carrying $Token, or $null if no entry does.
    .DESCRIPTION
        `git stash push` prints no object name, so the entry has to be found again after the fact.
        Reading `stash@{0}` alone would be a guess: a peer can push between our push and our read, and
        then `stash@{0}` is theirs. The token settles it -- this run generated it, so exactly one entry
        on the stack can carry it.

        The subject git writes is "On <branch>: <our message>", which is why the token is matched as a
        substring. `.Contains` and not `-like`: in a -like pattern the square brackets around the token
        are a character class, so `*[abc123]*` matches any subject containing any one of those
        characters -- which is very nearly all of them.
    #>
    param([string]$Repo, [string]$Token)

    $rows = @(& git -C $Repo stash list --format='%H %gs')
    if ($LASTEXITCODE -ne 0) { return $null }
    foreach ($row in $rows) {
        if (-not $row) { continue }
        $entry, $subject = $row -split ' ', 2
        if ($subject -and $subject.Contains("[$Token]")) { return $entry }
    }
    return $null
}

function Get-RescueStashIndex {
    <#
    .SYNOPSIS
        The `stash@{n}` currently naming $Sha, or $null if the entry is no longer on the stack.
    .DESCRIPTION
        `git stash drop` refuses an object name outright -- "<sha> is not a stash reference" -- so the
        only way to drop a known entry is to resolve it back to an index. That index is read HERE,
        immediately before the drop, and never carried from push time: dropping an entry renumbers
        every entry beneath it, so an index captured earlier can name somebody else by the time it is
        used.
    #>
    param([string]$Repo, [string]$Sha)

    $rows = @(& git -C $Repo stash list --format='%H %gd')
    if ($LASTEXITCODE -ne 0) { return $null }
    foreach ($row in $rows) {
        if (-not $row) { continue }
        $entry, $ref = $row -split ' ', 2
        if ($entry -eq $Sha) { return $ref }
    }
    return $null
}

# The PRIMARY, explicitly -- not "the checkout this script lives in". This command exists to empty the
# one directory several sessions share, so resolving it from the script's own location would quietly
# rescue a linked worktree instead, and report success for having done the wrong thing.
$PrimaryRoot = Get-CcxPrimaryRoot
if (-not $PrimaryRoot) { throw "Not inside a git repository (could not locate the primary checkout)." }

$Target = Get-CcxWorktreePath -Name $Name -PrimaryRoot $PrimaryRoot
if (Test-Path -LiteralPath $Target) {
    throw "Worktree path already exists: $Target  (pick another -Name, or just work in it)"
}

$dirty = @(& git -C $PrimaryRoot status --porcelain)
if ($dirty.Count -eq 0) {
    Write-Host "Nothing to rescue: $PrimaryRoot is clean." -ForegroundColor Yellow
    Write-Host "You want a plain new worktree instead:  scripts/worktree/new.ps1 -Name $Name"
    return
}

$sha = (& git -C $PrimaryRoot rev-parse HEAD).Trim()
Write-Host "Rescuing $($dirty.Count) change(s) from $PrimaryRoot (at $($sha.Substring(0,7)))..."
$dirty | Select-Object -First 12 | ForEach-Object { Write-Host "  $_" }
if ($dirty.Count -gt 12) { Write-Host "  ... and $($dirty.Count - 12) more" }

# --include-untracked carries untracked files too. Without it they are left behind in the primary and
# then silently DUPLICATED the moment the new worktree recreates them -- two copies, diverging, and no
# indication which one the session is editing.
#
# The token is what makes the entry findable again afterwards. Two sessions rescuing the same -Name
# write the same message, and git prefixes both with the same "On <branch>:", so the message alone
# does not identify one entry on a stack every worktree of this clone shares.
#
# `git stash create` would hand back the object name with no stack interaction at all and no window to
# close -- but it cannot capture untracked files, and that is not negotiable here.
$stashToken = [guid]::NewGuid().ToString('N').Substring(0, 8)
$stashMsg = "rescue -> $Name [$stashToken]"
& git -C $PrimaryRoot stash push --include-untracked -m $stashMsg
if ($LASTEXITCODE -ne 0) { throw "git stash push failed (exit $LASTEXITCODE) -- nothing was moved." }

$stashSha = Get-RescueStashSha -Repo $PrimaryRoot -Token $stashToken

# The work has already left the primary by this line, so nothing below may fail quietly.
$stashSurvives = $true
$partiallyApplied = $false
try {
    if (-not $stashSha) {
        throw ("git stash push reported success, but no entry on the stack carries this run's token " +
               "[$stashToken]. The push and the read are two commands, so something took the entry " +
               "in between. Do not re-run: find the work first.")
    }

    # Branch the worktree off the primary's CURRENT commit so the stash applies without conflict.
    # new.ps1 would otherwise default to the trunk, which the primary is often many commits behind.
    $newArgs = @('-NoProfile', '-File', (Join-Path $PSScriptRoot 'new.ps1'), '-Name', $Name, '-Base', $sha)
    if ($NoSetup) { $newArgs += '-NoSetup' }
    & pwsh @newArgs
    if ($LASTEXITCODE -ne 0) { throw "new.ps1 failed (exit $LASTEXITCODE)" }

    # `apply <object name>`, never `pop`. The object name cannot drift while new.ps1 runs, and it
    # still resolves even if a peer has dropped the entry off the stack meanwhile -- a dropped stash
    # commit outlives its reflog entry until the next gc.
    & git -C $Target stash apply $stashSha
    if ($LASTEXITCODE -ne 0) {
        # Measured: on an untracked-file collision apply exits 1, refuses the untracked files, and
        # lands the tracked changes anyway. The work is then in two places, and the warning below has
        # to say so rather than "it is all still in the stash".
        $partiallyApplied = $true
        throw "git stash apply $stashSha failed in $Target (exit $LASTEXITCODE)"
    }
    $stashSurvives = $false

    # Only now is the entry spent. Drop it by the index it holds RIGHT NOW, then read git's own
    # receipt -- "Dropped stash@{n} (<sha>)" -- to confirm the entry that died was this one. If a peer
    # renumbered the stack between the lookup and the drop, that receipt is the only record of whose
    # entry went, and `git stash store` puts it straight back: a dropped commit is still a commit.
    $index = Get-RescueStashIndex -Repo $PrimaryRoot -Sha $stashSha
    if (-not $index) {
        Write-Warning 'The rescued stash entry had already left the stack, so nothing was dropped.'
        Write-Warning "Your work is in $Target regardless. Object name: $stashSha"
    }
    else {
        $receipt = (& git -C $PrimaryRoot stash drop $index 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Could not drop the spent stash entry $index (exit $LASTEXITCODE)."
            Write-Warning "Your work is in $Target. Drop it by hand when convenient: $stashSha"
        }
        else {
            $receiptSha = [regex]::Match($receipt, '\(([0-9a-f]{40})\)')
            if ($receiptSha.Success -and $receiptSha.Groups[1].Value -ne $stashSha) {
                $other = $receiptSha.Groups[1].Value
                $otherMsg = (& git -C $PrimaryRoot log -1 --format='%s' $other)
                & git -C $PrimaryRoot stash store -m $otherMsg $other
                Write-Warning 'A peer renumbered the stash stack between the lookup and the drop, so'
                Write-Warning "the drop took $other rather than this run's entry. It is back on the"
                Write-Warning "stack, unchanged, as:  $otherMsg"
                Write-Warning "This run's spent entry is still there too. Leave it: retrying the drop"
                Write-Warning "reopens the same race. Object name: $stashSha"
            }
        }
    }

    Write-Host ''
    Write-Host "Rescued into $Target (branch '$Name', off $($sha.Substring(0,7)))." -ForegroundColor Green
    Write-Host 'The primary checkout is clean again. Continue here:'
    Write-Host "  cd `"$Target`""
}
finally {
    if ($stashSurvives) {
        # Print the recovery path, not just the failure. This block is the difference between "your
        # work is somewhere" and "your work is gone": the exact commands to see it and put it back are
        # here rather than in a document nobody opens mid-panic.
        #
        # Every command printed names the entry by object name. A bare pop handed to somebody in a
        # hurry is this script's own bug, moved out of the script and into the operator.
        Write-Warning 'Rescue did not complete.'
        if ($partiallyApplied) {
            Write-Warning "PART of the work reached $Target and the rest did not. git stash apply"
            Write-Warning 'refuses the whole entry when an untracked file it carries already exists in'
            Write-Warning 'the target, and lands the tracked changes anyway. Read both before you act.'
        }
        else {
            Write-Warning 'YOUR WORK IS SAFE -- all of it is still in the stash.'
        }
        if ($stashSha) {
            Write-Warning "    git -C `"$PrimaryRoot`" stash show -p $stashSha"
            Write-Warning "    git -C `"$PrimaryRoot`" stash apply $stashSha"
            Write-Warning '  then find its row and drop that one alone, once you are sure:'
            Write-Warning "    git -C `"$PrimaryRoot`" stash list --format='%H %gd %gs'"
            Write-Warning "    git -C `"$PrimaryRoot`" stash drop 'stash@{N}'"
        }
        else {
            Write-Warning 'This run could not pin its entry. Find it by the message it was saved under:'
            Write-Warning "    git -C `"$PrimaryRoot`" stash list --format='%H %gd %gs'"
            Write-Warning "  look for:  $stashMsg"
            Write-Warning '  then apply the object name in that row, never a bare pop: the stack is'
            Write-Warning '  shared with every other worktree of this clone.'
        }
        Write-Warning 'Nothing was discarded. Resolve the failure above, then retry or apply it by hand.'
    }
}
