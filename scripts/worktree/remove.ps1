#Requires -Version 7.3
<#
.SYNOPSIS
    Remove a worktree created by new.ps1, and optionally its branch, without orphaning commits.

.DESCRIPTION
    The manual counterpart to the pruning tool. It removes the worktree directory for <Name> and, with
    -DeleteBranch, THE BRANCH THAT WORKTREE WAS ON -- which is often not <Name>. <Name> is a directory
    component and cannot contain '/'; `new.ps1 -Name my-task -Branch feature/my-task` is a documented
    invocation, so the two names diverge as a matter of routine rather than as an edge case.

    IT REFUSES IF THE WORKTREE HAS UNCOMMITTED *TRACKED* CHANGES unless -Force. Untracked entries are
    expected -- a per-checkout environment directory, build output, a scratch database -- and do not
    block removal. Note the deliberate asymmetry with the automated pruning tool, which treats
    untracked files as a BLOCKER: a human running this command has just looked at the directory and can
    say those files are disposable, and an unattended reaper cannot. The stricter test belongs to the
    tool that runs without a human. Do not "fix" the difference by making them agree.

    IT REFUSES A WORKTREE THAT CONTAINS ANOTHER REGISTERED WORKTREE, and -Force does not override
    that. It names each one and exits non-zero. Remove the nested worktrees first. The note above the
    check says why, and why the rule is containment rather than a `.claude/worktrees/` path shape.

    Run it from any checkout EXCEPT the one being removed (git cannot remove the worktree you are
    standing in).

    WHY THE TIP IS REFERENCED BEFORE ANYTHING IS REMOVED. Removing a worktree can take its branch ref
    with it, and a commit that is in no ref is also in no reflog -- there is then no `git reflog` entry
    to recover it from and nothing in the interface admits the work existed. So the tip is resolved
    first, printed, and (when -DeleteBranch is used) written to a keep-ref before the branch goes. The
    keep-ref costs nothing and is the difference between "recoverable" and "gone at the next gc".

.EXAMPLE
    ./remove.ps1 -Name alerts
    ./remove.ps1 -Name alerts -DeleteBranch
    ./remove.ps1 -Name alerts -Force        # discard uncommitted tracked changes too
#>
[CmdletBinding()]
param(
    # The worktree DIRECTORY component, exactly as passed to new.ps1 -- NOT a branch name. The pattern
    # is the same literal new.ps1 uses (see its note on why '\A..\z' rather than '^..$', and on keeping
    # all five copies identical). Which branch -DeleteBranch removes is read from the worktree's own
    # HEAD, because these two are routinely different: see the note above the delete.
    [Parameter(Mandatory = $true)]
    [ValidatePattern('\A[A-Za-z0-9._-]+\z')]
    [string]$Name,

    # Remove even with uncommitted tracked changes. It does NOT override the nested-worktree refusal.
    [switch]$Force,

    # Also delete the local branch.
    [switch]$DeleteBranch
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot '../coord/_common.ps1')
# The nested-worktree detector and the worktree-list parser, shared with prune-merged.ps1. One copy
# of a safety check, not two.
. (Join-Path $PSScriptRoot '../coord/occupancy.ps1')

$PrimaryRoot = Get-CcxPrimaryRoot
if (-not $PrimaryRoot) { throw "Not inside a git repository (could not locate the primary checkout)." }

$cfg = Get-CcxConfig -From $PrimaryRoot
$WorktreePath = Get-CcxWorktreePath -Name $Name -PrimaryRoot $PrimaryRoot

if (-not (Test-Path -LiteralPath $WorktreePath)) { throw "No such worktree: $WorktreePath" }

# Every registered worktree, primary first. FAIL CLOSED: an unreadable list is the same empty answer
# as a repository with none, so it must never read as permission.
function Read-RegisteredWorktrees([string]$Primary, [string]$Target) {
    $registered = @(Get-RepoWorktrees $Primary)
    if ($registered.Count -eq 0) {
        throw ("Could not list this repository's registered worktrees, so there is no way to check " +
            "'$Target'. Nothing was removed.")
    }
    return $registered
}

# THE TARGET MUST BE A REGISTERED LINKED WORKTREE, and this runs before anything else reads it.
# -Name's pattern accepts '.' and '..'. Under the nested layout those resolve to .claude/worktrees and
# .claude, the directories that hold every harness worktree, and the nested check below would list
# each of them with the commands to delete it. The primary is excluded too. No -Name reaches it
# today, and this keeps it that way.
$there = ConvertTo-CcxComparablePath $WorktreePath
$linked = @(Read-RegisteredWorktrees -Primary $PrimaryRoot -Target $WorktreePath | Select-Object -Skip 1 |
        Where-Object { $there -and (ConvertTo-CcxComparablePath $_.Path) -eq $there })
if ($linked.Count -eq 0) {
    Write-Host "REFUSED: '$WorktreePath' is not a registered worktree of this repository." -ForegroundColor Red
    Write-Host ("-Name is the directory name new.ps1 was given. List them with:  git -C `"$PrimaryRoot`" " +
        "worktree list") -ForegroundColor Red
    throw "Not a registered worktree. Nothing was removed."
}

# Refuse to remove the worktree we are standing in. git would refuse too, but its message describes
# the git-level problem rather than the thing you did, and a wrong-cwd run must fail loudly rather
# than half-succeed.
$here = ConvertTo-CcxComparablePath $PWD.Path
if (Test-CcxPathUnder -Path $here -Root $there) {
    throw ("You are standing inside '$WorktreePath'. Run this from another checkout -- git cannot " +
        "remove the worktree that is the current directory.")
}

# REFUSE A WORKTREE THAT CONTAINS ANOTHER REGISTERED WORKTREE. The --force removal below deletes the
# whole directory tree. The only guard above it reads `git status` and drops every '??' line, and a
# nested checkout shows there as '?? .claude/', or not at all where it is ignored. So nothing stopped
# it: git deleted the nested checkout with the parent, left it registered with no directory, and
# exited 0. A session started inside a sibling worktree creates its own worktrees under that tree's
# .claude/worktrees/, so the one deleted can be a live session's.
#
# RETRACTED 2026-09-22, the day it was written: this note said the nested checkout "is git-ignored
# inside its parent, so the parent reads clean". The fixture in
# tests/test_remove_never_deletes_a_nested_worktree.py has no ignore rule, its parent reads
# '?? .claude/', and the loss happened anyway. Ignoring was never the cause.
#
# The detector is the reaper's, from occupancy.ps1, not a second copy: prune-merged.ps1 refuses this
# case with the same Get-NestedWorktrees call. The rule is CONTAINMENT, never path shape. Under the
# nested layout every worktree these scripts create lives under .claude/worktrees/, so refusing that
# path shape would leave the layout with no scripted teardown.
#
# NOT overridable, and deliberately not by -Force. -Force means "discard uncommitted tracked
# changes", and a switch with two meanings is how a caller discards a live session by accident. The
# remedy is to remove the nested worktrees first, deepest first.
#
# It reads ONLY the worktree list. Get-WorktreeOccupancy would also read every session record and
# fence each one, which this check does not use, and one malformed record would then stop every
# manual removal. So the occupancy header's rule for callers of the liveness fence does not bind here.
#
# It sees only worktrees registered to THIS repository. A checkout of some other repository sitting
# inside the target is not in this list, and the removal below deletes it.
function Assert-NoNestedWorktree([string]$Target, [string]$Primary) {
    $registered = @(Read-RegisteredWorktrees -Primary $Primary -Target $Target)
    # Get-NestedWorktrees reads only .Worktrees off its -Occupancy argument.
    $nested = @(Get-NestedWorktrees -Occupancy ([pscustomobject]@{ Worktrees = $registered }) -Path $Target)
    if ($nested.Count -eq 0) { return }

    # DEEPEST FIRST. `git worktree remove` without --force refuses modified or untracked files but
    # deletes ignored ones. Where a child is ignored inside its parent, removing the parent first
    # deletes the child and leaves it registered: the loss refused here. A child's path is always
    # longer than its parent's, so longest first puts every child first.
    $nested = @($nested | Sort-Object { (ConvertTo-CcxComparablePath $_.Path).Length } -Descending)

    # NO COMMAND FOR A WORKTREE HOLDING WORK. Plain `git worktree remove` exits 128 on changed or
    # untracked files, and an operator's next try is --force: the loss this check prevents. Nor for a
    # parent whose ignored child holds work, because the parent then reads clean and removing it takes
    # the child. Children come first in this order, so their verdicts are known by the parent's turn.
    $rows = @()
    foreach ($n in $nested) {
        $why = ''
        if (-not $n.Prunable) {
            $status = @(& git -C $n.Path --no-optional-locks status --porcelain 2>$null)
            $code = $LASTEXITCODE
            if ($code -ne 0) { $why = "git status failed on it (exit $code), so what it holds is unknown" }
            elseif ($status.Count -gt 0) {
                $why = "it holds $($status.Count) changed or untracked path(s), so git worktree remove refuses it"
            }
        }
        if (-not $why) {
            $heldBelow = @($rows | Where-Object { $_.Why } | ForEach-Object { $_.Wt })
            $inside = @(Get-NestedWorktrees -Occupancy ([pscustomobject]@{ Worktrees = $heldBelow }) -Path $n.Path)
            if ($inside.Count -gt 0) { $why = "it contains $($inside[0].Path), which holds work, and removing this deletes that" }
        }
        $rows += [pscustomobject]@{ Wt = $n; Why = $why }
    }

    Write-Host ("REFUSED: '$Target' contains $($nested.Count) registered worktree(s). Removing it " +
        "would delete each one still on disk, and leave it registered with no directory:") -ForegroundColor Red
    foreach ($n in $nested) {
        $state = @()
        if ($n.Detached) { $state += 'detached' } elseif ($n.Branch) { $state += "branch $($n.Branch)" }
        if ($n.Locked) { $state += $(if ($n.LockReason) { "locked: $($n.LockReason)" } else { 'locked' }) }
        if ($n.Prunable) { $state += "directory already missing: $($n.Prunable)" }
        Write-Host "  $($n.Path)  [$($state -join '; ')]" -ForegroundColor Red
    }
    Write-Host ("A session started inside this worktree puts its own worktrees here, so any of these " +
        "may belong to a live session. Once you know nobody is using them, clear them in this order, " +
        "deepest first:") -ForegroundColor Red
    foreach ($row in $rows) {
        $p = $row.Wt.Path
        if ($row.Why) {
            Write-Host "  NO COMMAND for $p -- $($row.Why)." -ForegroundColor Red
            if ($row.Why -notlike 'it contains *') {
                Write-Host "    Decide whether that work is wanted before anything deletes it. Look first:" -ForegroundColor Red
                Write-Host "    git -C `"$p`" status" -ForegroundColor Red
            }
            continue
        }
        # A locked worktree refuses `remove` until it is unlocked. The lock is its owner saying "in
        # use", so the unlock is printed as a step to take deliberately, never folded into a --force.
        if ($row.Wt.Locked) { Write-Host "  git -C `"$Primary`" worktree unlock `"$p`"" -ForegroundColor Red }
        Write-Host "  git -C `"$Primary`" worktree remove `"$p`"" -ForegroundColor Red
    }
    if (@($rows | Where-Object { $_.Why }).Count -gt 0) {
        Write-Host ("This script prints no step that deletes work. Keep, move or discard that work " +
            "yourself once you have looked at it.") -ForegroundColor Red
    }
    Write-Host "Then re-run this command. It checks again, and -Force does not override it." -ForegroundColor Red
    throw "Worktree contains $($nested.Count) registered worktree(s). Nothing was removed."
}

Assert-NoNestedWorktree -Target $WorktreePath -Primary $PrimaryRoot

# Guard against losing committed-but-unpushed or modified tracked work. Untracked entries ('??') are
# expected and do not block removal.
$tracked = & git -C $WorktreePath status --porcelain | Where-Object { $_ -notmatch '^\?\?' }
if ($tracked -and -not $Force) {
    Write-Host ($tracked -join "`n")
    throw "Worktree has uncommitted tracked changes. Commit/push them, or re-run with -Force."
}

# REFERENCE THE TIP FIRST -- before any destructive step, while the branch still exists.
$branch = Invoke-CcxGit -Repo $WorktreePath -Arguments @('rev-parse', '--abbrev-ref', 'HEAD')
$tip = Invoke-CcxGit -Repo $WorktreePath -Arguments @('rev-parse', 'HEAD')
if ($tip) {
    Write-Host "worktree : $WorktreePath"
    Write-Host "branch   : $(if ($branch -and $branch -ne 'HEAD') { $branch } else { '(detached)' })"
    Write-Host "tip      : $tip"
}

# THE BRANCH TO DELETE IS THE ONE THIS WORKTREE WAS ACTUALLY ON -- never -Name.
#
# -Name is the DIRECTORY component and cannot contain '/' (see its ValidatePattern, and new.ps1's note
# on why that pattern is load-bearing). A branch name can, and `new.ps1 -Name my-task -Branch
# feature/my-task` is a documented invocation -- it is how the worktree gate's branch-reuse remediation
# hands a namespaced ref back. So a worktree whose $Name is not a branch name AT ALL is ordinary, not
# exotic, and `git branch -d $Name` there fails with "branch not found" while the real branch is never
# considered and quietly survives a run the human read as a full cleanup.
#
# Resolved HERE, before anything is removed, because `git worktree remove` is what takes away the
# ability to ask. $null means detached HEAD (or git could not answer) -- handled explicitly below
# rather than by falling back to $Name, which would be guessing at a destructive step.
$branchToDelete = if ($branch -and $branch -ne 'HEAD') { $branch } else { $null }

# RE-READ, as prune-merged.ps1 re-reads before each removal. `git status` on a large tree takes long
# enough for a session inside the target to create a worktree there. This bounds that window to the
# keep-ref write below; it does not close it, since nothing here takes a lock.
Assert-NoNestedWorktree -Target $WorktreePath -Primary $PrimaryRoot

if ($DeleteBranch -and $tip) {
    # A keep-ref, written BEFORE the branch is deleted. It keeps the commits reachable, so they survive
    # gc and can be recovered by name instead of by a SHA someone has to have scrolled back to find.
    #
    # List them:    git for-each-ref refs/<prefix>/removed/
    # Recover one:  git branch <name> refs/<prefix>/removed/<name>
    # Drop one:     git update-ref -d refs/<prefix>/removed/<name>
    $keepRef = "refs/$($cfg.prefix)/removed/$Name"
    & git -C $PrimaryRoot update-ref $keepRef $tip
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not write the keep-ref '$keepRef'. Note the tip yourself before continuing: $tip"
    } else {
        # Recover under the branch's REAL name where we know it. The keep-ref itself stays named after
        # $Name (it is the stable, always-ref-safe label, and the listing commands above are written
        # against it), but a recovery hint that renames a namespaced branch back to its directory
        # component hands you a differently-named branch and does not say so.
        $recoverAs = if ($branchToDelete) { $branchToDelete } else { $Name }
        Write-Host "Kept the tip as '$keepRef' (recover with: git branch $recoverAs $keepRef)." -ForegroundColor DarkGray
    }
}

# --force is needed regardless: the untracked per-checkout environment makes git consider the worktree
# non-empty. The tracked-changes refusal above is what protects the work; this flag only tells git that
# the untracked files it can see are expected.
& git -C $PrimaryRoot worktree remove --force $WorktreePath
if ($LASTEXITCODE -ne 0) { throw "git worktree remove failed (exit $LASTEXITCODE)" }

# Deliberately NOT followed by `git worktree prune`. That command deregisters every worktree whose
# directory git cannot currently see -- which includes one sitting on a disconnected network drive, an
# unmounted volume, or a path a live session is about to come back to. `git worktree remove` already
# deregisters the one we removed; a blanket prune is a second, much wider action wearing the costume of
# a cleanup step.

if ($DeleteBranch) {
    if (-not $branchToDelete) {
        # Detached HEAD, or git could not answer. There is no branch here to delete, and the previous
        # version guessed one: it ran `git branch -d $Name` regardless, which either failed (and was
        # then reported as unmerged commits that do not exist) or deleted some OTHER branch that merely
        # shares this directory's name. Neither is something a cleanup step gets to do silently.
        Write-Warning ("-DeleteBranch: this worktree had no branch checked out (detached HEAD), so " +
            "there is no branch to delete. Nothing has been lost -- its tip is printed above.")
    }
    else {
        # -d, NOT -D. git refusing to delete an unmerged branch is a SIGNAL: it is telling you this
        # branch holds commits that are on no other ref. Forcing past it is how work disappears. If you
        # have read the refusal and still mean it, delete it by hand -- deliberately, not as a side
        # effect of tidying up a directory.
        #
        # CAPTURE GIT'S OWN REASON RATHER THAN ASSERTING ONE. This warning used to name a single cause
        # for ANY non-zero exit -- "it is not merged into its upstream, so it holds commits no other ref
        # has" -- which the script had not established and, in the namespaced-branch case above, had not
        # even tested: `branch -d` also refuses when the branch does not exist under that name, and when
        # it is checked out in another worktree. Both print a precise explanation on stderr, which was
        # discarded. Asserting the wrong cause is worse than reporting none: it sends the reader off to
        # look for commits that were never at risk, and it reads as a considered verdict either way.
        #
        # 2>&1 so git's stderr lands in $refusal instead of the console. On SUCCESS the same capture
        # holds git's "Deleted branch ..." line, which is re-emitted below -- capturing output must not
        # cost the confirmation the caller used to get.
        $refusal = & git -C $PrimaryRoot branch -d -- $branchToDelete 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Warning ("git refused to delete branch '$branchToDelete' (exit $LASTEXITCODE). The " +
                "branch has been LEFT IN PLACE. git's own reason:")
            foreach ($line in @($refusal)) { Write-Warning "  $line" }
            Write-Warning ("  If that reason is 'not fully merged', the branch holds commits no other " +
                "ref has, and the refusal is the signal -- not an obstacle to get past.")
            if ($tip) { Write-Warning "  its tip: $tip" }
            Write-Warning "  If you are certain it is disposable:  git -C `"$PrimaryRoot`" branch -D $branchToDelete"
        }
        else {
            foreach ($line in @($refusal)) { Write-Host $line }
        }
    }
}

Write-Host "Removed worktree '$WorktreePath'." -ForegroundColor Green
