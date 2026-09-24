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
    It prints a removal command only for a nested worktree whose removal loses nothing it can read:
    no changed, untracked or ignored file, no hidden edit to a skip-worktree or assume-unchanged
    file, and no commit that only its detached HEAD or its HEAD reflog holds. The note above
    Get-RemovalLoss says how each is read, and what it does not read.

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

# One argument of a command this script prints, in PowerShell single quotes, which expand nothing.
# Double quotes expand `$name` and read a backtick as an escape, so a path holding either printed a
# command that ran somewhere else. Measured 2026-09-23 at 06e8ca3: under a directory named `d$x`, a
# printed `git -C "<...>/d$x/P" worktree remove "<...>/d$x/P-work/..."` ran in pwsh against
# `<...>/d/P`, and where a second clone sat there it removed that clone's worktree. PowerShell reads
# a doubled single quote inside single quotes as one; a POSIX shell does not, and this script is
# PowerShell.
function Format-Literal([string]$Text) { return "'" + ($Text -replace "'", "''") + "'" }

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
#
# THE LAST COMPONENT MUST MATCH AS SPELLED. Windows drops a trailing dot from a path component, so
# `-Name a.` resolved to `<primary>-a.`, and Test-Path, GetFullPath and git all read that as
# `<primary>-a`. The check below then matched worktree `a`, and the script removed it and exited 0.
# Measured 2026-09-23 at 06e8ca3 on git 2.55.0.windows.5. Only the leaf is compared as spelled, since
# -Name is one component and the rest of the path comes from git. Case still folds where the
# filesystem folds it.
$there = ConvertTo-CcxComparablePath $WorktreePath
$leafRule = if ($script:CcxCaseInsensitiveFs) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
$leaf = Split-Path -Leaf $WorktreePath
$linked = @(Read-RegisteredWorktrees -Primary $PrimaryRoot -Target $WorktreePath | Select-Object -Skip 1 |
        Where-Object { $there -and (ConvertTo-CcxComparablePath $_.Path) -eq $there -and
            [string]::Equals((Split-Path -Leaf $_.Path), $leaf, $leafRule) })
if ($linked.Count -eq 0) {
    Write-Host "REFUSED: '$WorktreePath' is not a registered worktree of this repository." -ForegroundColor Red
    Write-Host ("-Name is the directory name new.ps1 was given. List them with:  git -C " +
        "$(Format-Literal $PrimaryRoot) worktree list") -ForegroundColor Red
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

# WHAT REMOVING ONE NESTED WORKTREE WOULD LOSE, as the reasons its command is withheld. The refusal
# prints `git worktree remove` for a nested worktree only when this returns nothing.
#
# Plain `git worktree remove` deletes without asking in each case below. A printed command did the
# first three until 3d778a0, and the last two until that change's first review round, the same day.
# tests/test_remove_never_deletes_a_nested_worktree.py reproduces each one:
#
#   * Untracked files that status.showUntrackedFiles=no hides. git's own clean check obeys the
#     setting. Read-WorktreeStatus overrides it.
#   * Ignored files. git never counts them, so any one withholds the command. This repository ignores
#     *.local.*, so a seat's .claude/seat.local.txt is one. So is a cache, and this cannot tell a
#     cache from a local database, so nearly every used worktree is withheld. That is deliberate.
#   * Commits on a detached HEAD that no ref holds. The removal deletes the last thing pointing at
#     them, and gc can then collect them.
#   * Commits only this worktree's HEAD reflog holds: a session that committed on a detached HEAD
#     and switched back to its branch. The removal deletes that reflog.
#   * Edits to a tracked file flagged skip-worktree or assume-unchanged, which git status does not
#     check. Read-WorktreeStatus lists those as Flagged.
#
# A registered worktree nested inside this one shows in its status as a single `<dir>/` entry. That
# entry is not counted: it gets its own row, deepest first, and the caller withholds a parent whose
# child holds work. Only an entry ending in `/` can be one, so only those are compared, and the
# compare is case-sensitive, because the folded form keeps case where the filesystem does.
#
# THE REFS ARE READ WITH `rev-list --not --glob=refs/*`, and two obvious reads are wrong. `git branch
# --contains` sees branches only, so a commit a tag holds reads as lost. `--not --all` is blind the
# other way: it adds every worktree's HEAD, this one's included, so it never finds anything lost.
# Measured 2026-09-23 on git 2.55.0.windows.5, on a detached commit: held only by a tag, `branch
# --contains` printed nothing and this read printed 0; held by nothing, `--not --all` printed 0 and
# this read printed 1. refs/stash is left out because every worktree shares it, and any session's
# next stash moves it.
#
# THE REFLOG READ SUBTRACTS EVERY REF'S OWN REFLOG, which survives the removal. Without that, a
# commit amended or rebased away on a branch counts as lost, although the branch's reflog still
# holds it. Measured the same day: after an amend, the plain read counted 1 and this one 0; after a
# commit left behind on a detached HEAD, this one counted 1. `--reflog` cannot stand in for it,
# because it adds every worktree's HEAD reflog, this one's included, and counted 0 there.
#
# WHAT IT DOES NOT READ. A worktree whose directory is gone (prunable) has its HEAD checked but not
# its HEAD reflog, which lives in an admin directory `git worktree list` does not name.
#
# WHY NOT prune-merged.ps1's Test-WorktreeClean. The two share the status read and deliberately not
# the policy. The reaper removes only merged, idle, unoccupied siblings, never a detached one, and
# docs/PRUNING.md says it deletes ignored files. This names nested worktrees that may belong to a
# live session, so everything above withholds the command here.
#
# Each reason carries what to look with: 'status' for files, 'log' for a detached HEAD's commits,
# 'reflog' for commits only the reflog holds, 'submodule' for a submodule's own commits, 'repair'
# for a directory git no longer links to its worktree.
function Get-RemovalLoss([object]$Wt, [object[]]$Registered, [string]$Primary) {
    $why = @()
    if ($Wt.Detached -and -not $Wt.Head) {
        $why += [pscustomobject]@{ Look = 'status'; Text = "its detached HEAD could not be read, so what it holds is unknown" }
    }
    elseif ($Wt.Detached) {
        $lost = @(& git -C $Primary rev-list --count $Wt.Head --not --exclude=refs/stash '--glob=refs/*' 2>$null)
        $code = $LASTEXITCODE
        if ($code -ne 0 -or "$lost" -notmatch '\A\d+\z') {
            $why += [pscustomobject]@{ Look = 'log'
                Text = "git could not tell which refs hold its detached HEAD $($Wt.Head) (exit $code), so what it holds is unknown" }
        }
        elseif ([int]"$lost" -gt 0) {
            $why += [pscustomobject]@{ Look = 'log'
                Text = "its detached HEAD $($Wt.Head) has $lost commit(s) that no branch, tag or other ref holds" }
        }
    }
    # A missing directory has no files to lose. Its HEAD, read above, lives in the admin directory.
    #
    # BUT GIT ALSO CALLS A WORKTREE PRUNABLE WHEN ONLY ITS `.git` FILE IS GONE, and then its directory
    # and files are still there. Every git read in it then runs in the repository around it, the
    # parent worktree here, so no read below would be about it. A printed `git worktree remove` exits
    # 128 ("validation failed") with or without --force. What gets past that is `git worktree prune`,
    # and removing the parent then deletes the files. Measured 2026-09-23 at 06e8ca3 on git
    # 2.55.0.windows.5: the refusal printed that command and called the directory "already missing".
    # `git worktree repair`, run in the primary, writes the `.git` file back, deletes nothing and
    # exits 0, so it is the step printed instead. The path form of it repaired too, but exited 1.
    if ($Wt.Prunable) {
        if (-not (Test-Path -LiteralPath $Wt.Path)) { return $why }
        return $why + [pscustomobject]@{ Look = 'repair'
            Text = "git marks it prunable ($($Wt.Prunable)), but its directory is still there, and git cannot read it until its link is repaired" }
    }

    # Skipped where the HEAD read above already withheld the command: that commit heads the reflog.
    if ($why.Count -eq 0) {
        # Read once per run: every ref's reflog, as `^<sha>` lines that rev-list reads as exclusions.
        if ($null -eq $script:KeptByRefReflogs) {
            $kept = @(& git -C $Primary log -g '--format=^%H' --exclude=refs/stash '--glob=refs/*' 2>$null)
            $script:KeptByRefReflogs = [pscustomobject]@{ Ok = ($LASTEXITCODE -eq 0); Lines = $kept }
        }
        $mine = @(& git -C $Wt.Path log -g --format=%H HEAD 2>$null)
        $code = $LASTEXITCODE
        $lost = ''
        if ($code -eq 0 -and $script:KeptByRefReflogs.Ok) {
            $lost = @(@($mine) + @($script:KeptByRefReflogs.Lines) |
                    & git -C $Primary rev-list --count --ignore-missing --stdin --not --exclude=refs/stash '--glob=refs/*' 2>$null)
            $code = $LASTEXITCODE
        }
        if ($code -ne 0 -or "$lost" -notmatch '\A\d+\z') {
            $why += [pscustomobject]@{ Look = 'reflog'
                Text = "git could not read which commits only its HEAD reflog holds, so what it holds is unknown" }
        }
        elseif ([int]"$lost" -gt 0) {
            $why += [pscustomobject]@{ Look = 'reflog'
                Text = "its HEAD reflog holds $lost commit(s) that no ref or ref reflog holds, and removing it deletes that reflog" }
        }
    }

    $status = Read-WorktreeStatus -Path $Wt.Path -IncludeIgnored
    if ($status.Exit -ne 0) {
        return $why + [pscustomobject]@{ Look = 'status'
            Text = "git status failed on it (exit $($status.Exit)), so what it holds is unknown" }
    }
    $children = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($c in @(Get-NestedWorktrees -Occupancy ([pscustomobject]@{ Worktrees = $Registered }) -Path $Wt.Path)) {
        $folded = ConvertTo-CcxComparablePath $c.Path
        if ($folded) { [void]$children.Add($folded) }
    }
    $isChild = { param($rel) $rel.EndsWith('/') -and $children.Contains((ConvertTo-CcxComparablePath -Path $rel -Base $Wt.Path)) }
    $untracked = @($status.Untracked | Where-Object { -not (& $isChild $_) })
    $ignored = @($status.Ignored | Where-Object { -not (& $isChild $_) })
    $counts = @()
    if ($status.Tracked.Count -gt 0) { $counts += "$($status.Tracked.Count) changed tracked file(s)" }
    if ($status.Flagged.Count -gt 0) {
        $counts += "$($status.Flagged.Count) tracked file(s) flagged skip-worktree or assume-unchanged, whose edits git status does not show"
    }
    if ($untracked.Count -gt 0) { $counts += "$($untracked.Count) untracked file(s)" }
    if ($ignored.Count -gt 0) { $counts += "$($ignored.Count) ignored file(s), which plain git status does not show" }
    if ($counts.Count -gt 0) {
        # A few paths, so an operator can tell a cache from a database without running anything.
        $some = @(@($status.Tracked | ForEach-Object { if ($_.Length -gt 3) { $_.Substring(3) } else { $_ } }) +
                @($status.Flagged) + $untracked + $ignored |
                Select-Object -First 3)
        $why += [pscustomobject]@{ Look = 'status'
            Text = "it holds $($counts -join ' and ') (among them: $($some -join ', '))" }
    }

    # A SUBMODULE. git refuses to remove a worktree holding a checked-out submodule, clean or not:
    # "working trees containing submodules cannot be moved or removed", exit 128. So a printed command
    # fails, and the next try is --force, which deletes each submodule's repository with this
    # worktree's admin directory, and any commit only that repository holds. Measured 2026-09-23 at
    # 06e8ca3 on git 2.55.0.windows.5, with a clean submodule. git's first test is read as git reads
    # it: the admin directory holds `modules`. A submodule checked out with its own `.git` instead is
    # found through .gitmodules. One that is not checked out is an empty directory, and git removes it.
    $modules = @(& git -C $Wt.Path rev-parse --path-format=absolute --git-path modules 2>$null)
    $subs = @()
    if ($LASTEXITCODE -eq 0 -and "$modules" -and (Test-Path -LiteralPath "$modules")) {
        $subs = @(Get-ChildItem -LiteralPath "$modules" -Force -ErrorAction SilentlyContinue | ForEach-Object Name)
        if ($subs.Count -eq 0) { $subs = @('modules') }
    }
    $declared = @(& git -C $Wt.Path config --file .gitmodules --get-regexp '^submodule\..*\.path$' 2>$null)
    foreach ($d in $declared) {
        $rel = ($d -split ' ', 2)[-1]
        if ($rel -and (Test-Path -LiteralPath (Join-Path (Join-Path $Wt.Path $rel) '.git'))) { $subs += $rel }
    }
    $subs = @($subs | Select-Object -Unique)
    if ($subs.Count -gt 0) {
        $why += [pscustomobject]@{ Look = 'submodule'
            Text = ("it holds $($subs.Count) checked-out submodule(s) (among them: $(@($subs | Select-Object -First 3) -join ', ')). " +
                "git will not remove a worktree holding one, and forcing it deletes each submodule's repository, " +
                "with any commit only that repository holds") }
    }
    return $why
}

# Filled on first use by Get-RemovalLoss.
$script:KeptByRefReflogs = $null

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
    # untracked files, and an operator's next try is --force: the loss this check prevents. What it
    # does not refuse, it deletes, so Get-RemovalLoss counts that too. Nor for a parent whose ignored
    # child holds work, because removing the parent takes the child. Children come first in this
    # order, so their verdicts are known by the parent's turn.
    $rows = @()
    foreach ($n in $nested) {
        $why = @(Get-RemovalLoss -Wt $n -Registered $registered -Primary $Primary)
        if ($why.Count -eq 0) {
            $heldBelow = @($rows | Where-Object { $_.Why.Count -gt 0 } | ForEach-Object { $_.Wt })
            $inside = @(Get-NestedWorktrees -Occupancy ([pscustomobject]@{ Worktrees = $heldBelow }) -Path $n.Path)
            if ($inside.Count -gt 0) {
                # No pointer of its own: the child's row, printed above this one, carries it.
                $why = @([pscustomobject]@{ Look = ''
                        Text = "it contains $($inside[0].Path), which holds work, and removing this deletes that" })
            }
        }
        $rows += [pscustomobject]@{ Wt = $n; Why = $why }
    }

    Write-Host ("REFUSED: '$Target' contains $($nested.Count) registered worktree(s). Removing it " +
        "would delete each one still on disk, and leave it registered with no directory:") -ForegroundColor Red
    foreach ($n in $nested) {
        $state = @()
        if ($n.Detached) { $state += 'detached' } elseif ($n.Branch) { $state += "branch $($n.Branch)" }
        if ($n.Locked) { $state += $(if ($n.LockReason) { "locked: $($n.LockReason)" } else { 'locked' }) }
        if ($n.Prunable) {
            $state += $(if (Test-Path -LiteralPath $n.Path) { "prunable: $($n.Prunable); its directory is still there" }
                else { "directory already missing: $($n.Prunable)" })
        }
        Write-Host "  $($n.Path)  [$($state -join '; ')]" -ForegroundColor Red
    }
    Write-Host ("A session started inside this worktree puts its own worktrees here, so any of these " +
        "may belong to a live session. Once you know nobody is using them, clear them in this order, " +
        "deepest first:") -ForegroundColor Red
    foreach ($row in $rows) {
        $p = $row.Wt.Path
        if ($row.Why.Count -gt 0) {
            Write-Host "  NO COMMAND for $p -- $(($row.Why | ForEach-Object Text) -join '; ')." -ForegroundColor Red
            $looks = @($row.Why | ForEach-Object Look | Where-Object { $_ } | Select-Object -Unique)
            if ($looks.Count -gt 0) {
                Write-Host "    Decide whether that work is wanted before anything deletes it. Look first:" -ForegroundColor Red
            }
            # Plain `git status` hides ignored files, and hides untracked ones where
            # status.showUntrackedFiles is no. Both flags override that. `normal` rather than the
            # check's `all`, so a cache directory reads as one line and not twenty thousand.
            if ($looks -contains 'status') {
                Write-Host "    git -C $(Format-Literal $p) status --untracked-files=normal --ignored" -ForegroundColor Red
            }
            if ($looks -contains 'log') {
                Write-Host ("    git -C $(Format-Literal $Primary) log --oneline $($row.Wt.Head) --not " +
                    "--exclude=refs/stash --glob='refs/*'") -ForegroundColor Red
            }
            if ($looks -contains 'reflog') { Write-Host "    git -C $(Format-Literal $p) reflog" -ForegroundColor Red }
            # The commits in each submodule that no remote-tracking branch holds: the ones a forced
            # removal would take with the submodule's repository.
            if ($looks -contains 'submodule') {
                Write-Host ("    git -C $(Format-Literal $p) submodule foreach --recursive git log --oneline HEAD " +
                    "--branches --not --remotes") -ForegroundColor Red
            }
            if ($looks -contains 'repair') {
                Write-Host "    Get-ChildItem -Force -LiteralPath $(Format-Literal $p)" -ForegroundColor Red
                Write-Host ("    Then restore its link, which deletes nothing, and re-run this command so it can " +
                    "read what the directory holds:") -ForegroundColor Red
                Write-Host "    git -C $(Format-Literal $Primary) worktree repair" -ForegroundColor Red
            }
            continue
        }
        # A locked worktree refuses `remove` until it is unlocked. The lock is its owner saying "in
        # use", so the unlock is printed as a step to take deliberately, never folded into a --force.
        if ($row.Wt.Locked) {
            Write-Host "  git -C $(Format-Literal $Primary) worktree unlock $(Format-Literal $p)" -ForegroundColor Red
        }
        Write-Host "  git -C $(Format-Literal $Primary) worktree remove $(Format-Literal $p)" -ForegroundColor Red
    }
    if (@($rows | Where-Object { $_.Why.Count -gt 0 }).Count -gt 0) {
        Write-Host ("Keep, move or discard that work yourself once you have looked at it.") -ForegroundColor Red
    }
    # RETRACTED 2026-09-23. This printed "A printed command can still delete what git status does not
    # show: ignored files, and commits on a detached HEAD that no branch holds. Look before you run
    # one." Get-RemovalLoss now withholds the command in each case, and in a third the warning did not
    # name: untracked files that status.showUntrackedFiles=no hides. Against a58981d, following the
    # printed command lost the work in all three test cases. At 3d778a0 no command is printed.
    #
    # What replaced it is a limit rather than a warning, and it prints only where a command did.
    if (@($rows | Where-Object { $_.Why.Count -eq 0 }).Count -gt 0) {
        Write-Host ("Each command was checked against what that worktree holds now, not when you run " +
            "it.") -ForegroundColor Red
    }
    Write-Host "Then re-run this command. It checks again, and -Force does not override it." -ForegroundColor Red
    throw "Worktree contains $($nested.Count) registered worktree(s). Nothing was removed."
}

Assert-NoNestedWorktree -Target $WorktreePath -Primary $PrimaryRoot

# Guard against losing committed-but-unpushed or modified tracked work. Untracked entries ('??') are
# expected and do not block removal.
#
# Read through Read-WorktreeStatus since 2026-09-23, the read the nested check uses. The raw read it
# replaced ignored git's exit code, so a status that failed read as no changes and the --force removal
# below went ahead. It also missed edits to files flagged skip-worktree or assume-unchanged, which
# count here as the tracked changes they are. -Force still discards all of it, as it always has.
$targetStatus = Read-WorktreeStatus -Path $WorktreePath -UntrackedFiles normal
$tracked = @($targetStatus.Tracked) + @($targetStatus.Flagged | ForEach-Object { "$_ (skip-worktree or assume-unchanged)" })
if ($targetStatus.Exit -ne 0 -and -not $Force) {
    throw ("git status failed on '$WorktreePath' (exit $($targetStatus.Exit)), so its uncommitted tracked " +
        "changes are unknown. Nothing was removed. Re-run with -Force to discard them anyway.")
}
if ($tracked.Count -gt 0 -and -not $Force) {
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
        Write-Host "Kept the tip as '$keepRef' (recover with: git branch $(Format-Literal $recoverAs) $keepRef)." -ForegroundColor DarkGray
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
            Write-Warning ("  If you are certain it is disposable:  git -C $(Format-Literal $PrimaryRoot) branch -D " +
                "$(Format-Literal $branchToDelete)")
        }
        else {
            foreach ($line in @($refusal)) { Write-Host $line }
        }
    }
}

Write-Host "Removed worktree '$WorktreePath'." -ForegroundColor Green
