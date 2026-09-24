# Pruning worktrees

<a id="tldrbluf"></a>

Use `prune-merged.ps1` to sweep finished sibling worktrees, or `remove.ps1` to remove one by name.
Both require care to preserve work and avoid live sessions.

Removal can leave commits without a recovery reference. The pruner once destroyed a live session's
worktree; its rules come from that incident and near misses.

From the primary checkout, run `prune-merged.ps1` without flags for a dry run. Only `-Apply`
removes worktrees; check recovery and occupancy before using it.

Use `-Fetch` in the preview to match apply's refreshed state. Without it, apply may remove
worktrees absent from the preview; refresh uses only `origin`, leaving other remotes stale.

---

Two scripts remove a worktree:

| Script | Who runs it | Posture |
|---|---|---|
| `scripts/worktree/prune-merged.ps1` | unattended sweep over every sibling worktree | dry run by default; `-Apply` acts. Consults the liveness fence |
| `scripts/worktree/remove.ps1` | a human, one named worktree at a time | acts immediately, refuses on uncommitted tracked changes. **Consults no fence at all** |

`remove.ps1` checks no occupancy. It refuses from inside its target and blocks uncommitted
tracked changes without `-Force`; you must check whether another session uses the checkout.

Every removal path uses `git worktree remove --force`. It deletes untracked `.env` files, local
databases, and build output; git cannot restore them.

Check the recovery reference and occupancy before running either script.

## First: A removal can delete commits into nothing

Removing a worktree can also remove its branch reference. A commit left in no reference has no
reflog entry or branch name through which this system can recover it.

Before removal, `remove.ps1` resolves and prints the tip. With `-DeleteBranch`, it first writes
a keep-ref: a spare tip pointer that survives branch deletion.

A detached worktree whose commits no ref holds gets a keep-ref without `-DeleteBranch` too. Until
2026-09-23 it did not, and removing it left those commits on no ref. A keep-ref name another commit
already holds gets the tip's short SHA added, so a second worktree of the same name never overwrites
the first one's.

`-Name` selects the worktree directory; `-DeleteBranch` reads the checked-out branch from
`HEAD`. Detached `HEAD` produces a warning and no branch deletion; check the
printed branch and tip.

Recover a branch deleted by `remove.ps1 -DeleteBranch` from its keep-ref.

The script creates the keep-ref before deletion. Read it and recreate the branch:

```powershell
# remove.ps1 -DeleteBranch, before the branch goes:
git -C <primary> update-ref refs/<prefix>/removed/<worktree-name> <tip>

# later, to see what is being kept and to get one back:
git for-each-ref refs/<prefix>/removed/
git branch <real-branch-name> refs/<prefix>/removed/<worktree-name>
git update-ref -d refs/<prefix>/removed/<worktree-name>
```

`<prefix>` is `ccx` unless you changed `prefix` in `ccx.config.json`.

The keep-ref uses the ref-safe directory label. The deleted branch may have a different name, as in
`new.ps1 -Name my-task -Branch feature/my-task`.

Using the directory name for both slots restores the right commits under the wrong branch name. Use
the exact recovery command printed by `remove.ps1`.

`for-each-ref` lists retained tips. Keep-refs preserve recovery pointers instead of leaving
commits eligible for the next garbage collection.

### Under squash-merge, the obvious merge tests lie

Squash-merge creates one new commit with a new hash and no parent link to the branch. After the work
lands, these checks still report its original commits as unmerged:

| Test | What it answers after a squash merge | Why |
|---|---|---|
| `git rev-list --count <trunk>..<branch>` | still counts every original commit -> "not merged" | the originals are unreachable from the trunk |
| `git merge-base --is-ancestor <branch> <trunk>` | false -> "not merged" | no parent link was created |
| `git cherry <trunk> <branch>` | marks commits `+` (unmerged) | patch-ids stop matching the moment anything was rebased, amended, or conflict-resolved |

A branch ahead of the trunk may already be squash-merged. `Test-Merged` in `prune-merged.ps1`
therefore uses three signals:

1. nothing beyond the trunk (`Test-ContainedInMain`);
2. a merged PR whose head is this exact tip. Matching only the branch name can delete commits added
   after its PR merged. A reused branch name can also identify the wrong commits;
3. the branch's **own** upstream is gone (the squash-merge + auto-delete shape).

Signal 3 requires the branch's own upstream. `-Base origin/<parent>` tracks the parent, whose deletion can
make an unpushed child report `[gone]`.

`gone` means an absent remote ref; a closed PR or `push --delete` also produces it.
Remove the worktree under this signal, never the branch.

### A two-dot diff answers a different question, and the answer looks identical

`git diff --name-only main branch` compares tips. It includes files the trunk gained after branching, even though the
branch never changed them.

Three-dot compares the branch to its merge base and shows what the branch changed.

On 2026-08-11, a stale branch showed 85 files with two dots and zero with three. Its tree matched
its base; the 85-file result answered a different question.

> **Rule.** Make three dots the default and justify two, rather than writing another caution. A
> caution competes with muscle memory and loses. A default is what muscle memory reaches for.

### The converse trap is the one that destroyed a worktree

Zero commits beyond the trunk can describe a branch created seconds ago. `Test-BranchNeverUsed` identifies
a branch with just one reflog entry, `branch: Created from ...`, that never advanced.

## The rule: Merged AND clean AND NOT occupied

<!-- no-copy -->
```text
prune = merged AND clean AND NOT occupied
```

Merged and clean describe branch state, not whether someone uses its directory. Apply this fixed
rule:

> A false SKIP is a minor annoyance. A false PRUNE destroys a session.

<a id="g05"></a>

<figure class="explain-figure">
<picture>
<source media="(max-width: 1100px)" srcset="/assets/diagrams/g05-pruner-decisions-mobile.svg">
<img src="/assets/diagrams/g05-pruner-decisions.svg" alt="Every pruner check must pass, including a fresh check before removal; failures skip the worktree." loading="lazy" width="777" height="1117">
</picture>
<figcaption>This maps the automated pruner, with its default activity veto. Every failure or unknown state takes the SKIP path. The manual remover follows a different policy. <a href="/assets/diagrams/g05-pruner-decisions.drawio">Editable diagram</a>.</figcaption>
</figure>

The merge check accepts trunk containment, an exact-tip merged pull request, or the branch's own gone upstream.
The gone-upstream signal keeps the branch; it does not prove the commits merged.

`-Name` can override recent activity, but never a session veto, nested worktree, or Git lock.
The fresh checks narrow a race window; they do not make removal atomic. Check recovery references
and invisible occupants before acting. Ignored files can still be lost.

Any uncertain check produces SKIP. Cleanup must never take priority over preserving work.

`Test-WorktreeClean` blocks removal whenever it cannot establish cleanliness.

- Uncommitted tracked changes block, and so do **untracked files**. They are the one loss class with
  no recovery through git at all: not in the index, not in a stash, not in the reflog.
- `--force` is not a safety net. It suppresses git's refusal on untracked and modified files
  that would have prevented the incident, so the reaper proves cleanliness itself first. Its other
  edges:
  - it deletes **ignored** files, invisible to `git status --porcelain`: unrecoverable, merely regenerable;
  - it does *not* override a git lock. That needs `-f -f`, which neither script passes.
- A `git status` that exits non-zero, or a directory that has vanished, is **not clean**. Those
  states used to be indistinguishable from "no changes" and pointed straight at destruction.

One routine supplies reasons for both the decision and pre-removal check. It distinguishes a missing
directory, status exit 128, untracked files, and tracked edits.

**The untracked-files rule above was false until 2026-09-23 wherever `status.showUntrackedFiles`
was `no`.** The check read plain `git status --porcelain`, which obeys that setting. An untracked
file read as clean, and `-Apply` deleted it.

Measured against `a58981d` with `tests/test_the_reaper_sees_untracked_files_a_setting_hides.py`: the
row read `Clean: True` and the file was gone. The check now reads status through `Read-WorktreeStatus`
in `scripts/coord/occupancy.ps1`, whose `--untracked-files=normal` overrides the setting.

**An edit to a file flagged skip-worktree or assume-unchanged was the same hole.** `git status` does
not check those files, so the edit read as clean. The same read now lists them from `git ls-files
-v`, and they block as tracked changes. Measured against `fd7028f`: `-Apply` deleted one.

Ignored files still do not block the reaper, and it still deletes them, as the policy above says.
`remove.ps1` shares the status read but withholds its printed command for them, because it names
nested worktrees that may belong to a live session.

## Occupancy is a veto, never a permission

Occupancy checks whether someone works in the directory. There is no heartbeat, so it can block
removal but cannot prove a session gone or authorize deletion.

`DEAD`, `STALE`, or absent records provide no veto and no permission.
`$OccupancyVetoStates` in `scripts/coord/occupancy.ps1` defines the blocking states:

| State | Meaning | Vetoes? |
|---|---|---|
| `LIVE` | pid resolves and its start time is consistent | yes |
| `UNVERIFIED` | pid resolves; the fence could not be evaluated | yes |
| `UNREADABLE` | the record cannot be fenced at all (no pid, or a non-numeric one) | yes |
| `STALE` | pid resolves but belongs to a different process | no -- and not permission either |
| `DEAD` | no such pid | no -- and not permission either |

Two independent signals are required, and **either one vetoes**:

Signal 1 uses `Get-WorktreeOccupancy` to map session `cwd` records to worktrees and check
process id plus start time. Nested occupants veto ancestors through `Get-WorktreeOccupants -IncludeNested`.

Signal 2 checks the newest private git metadata mtime against `-IdleHours`, default 36. It reads
`index`, `HEAD`, `ORIG_HEAD`, `FETCH_HEAD`, `COMMIT_EDITMSG`,
`MERGE_MSG`, and `logs/HEAD`.

Do not use working-file mtimes. Test runs change those files and would veto every removal.

Signal 1 sees launch directories only. Over 30 days where this tooling was built, 29% of
primary-seated Edit/Write calls targeted sibling worktrees by absolute path.

One audit found signal 1 vetoed none of the siblings, including one in use. Each run counts
candidates vetoed by each signal so execution cannot be mistaken for coverage.

## An empty roster and an unreadable roster are different outcomes

Empty and unreadable rosters both yield no rows. `Get-WorktreeOccupancy` therefore reports
`RootsExamined`, `RecordsExamined`, `RecordsUnplaceable`, and `UnplaceableFiles`, setting `Available`
only when:

- at least one config root holding a session registry,
- at least one **readable** record in it,
- **no** record that could not be *placed*.

An unparseable record or one without `cwd` cannot be assigned to a worktree. A
half-written record could belong to a session launched one second ago in the target.

An unavailable fence makes every candidate SKIP and the run exit non-zero. There is no override
flag; repair the fence.

`bin/ccx-doctor.ps1` reports config roots, records read, unplaceable records, and enumerated worktrees.
It explicitly says an empty roster does not establish that nobody is live.

## "Sibling" is not a prefix match

The old `<primary>-` prefix match included `<primary>-work/.claude/worktrees/x`, a live-session location. Nested
trees under `<primary>/` escaped only because that prefix differs; tests covered only that case.

Candidate selection is now two stages:

1. a **deliberately over-inclusive** sweep on the literal prefix: `StartsWith`,
   `Ordinal`, not `-like`. In `-like`, `[ ]` is a character
   class. A bracketed repository directory could match nothing, letting survival-only tests pass
   without examining it;
2. structural exclusions, each printed as a non-candidate with its reason rather than silently
   filtered out. A tool that silently filters cannot be checked.

The exclusions, in order:

- nested in another registered worktree (`Get-ContainingWorktrees`);
- harness-managed: `Test-CcxHarnessWorktreePath`, any `.claude/worktrees/` segment, unconditionally;
- not a structural sibling: `Test-CcxSiblingWorktreePath` wants the **same parent directory** and a leaf spelled
  exactly `<primary-leaf>-<something>`;
- detached or bare.

`-Name` cannot select excluded trees. A worktree containing another registered worktree is
never removed: `--force` would delete the nested directory while leaving its registration.

These scripts create sibling worktrees; Claude Code creates nested ones. Only siblings have scripted
teardown here, and a gitignored nested checkout can leave its parent looking clean.

## Print your blind spots, and name everything that narrows the fence

Every run prints its blind spots in the terminal and receipt. Otherwise readers may assume the fence
covers more than it does:

- a session writing into a worktree by absolute path from elsewhere (the 29% above);
- a `cwd` using a UNC (`\\host\C$\...`) or 8.3 short path. Neither spelling normalizes
  to the worktree's path for string comparison;
- a session that never registered;
- a session that only edits files without running git. It touches none of the seven metadata files,
  leaving signal 2 blind too.

The file registry includes editor-hosted and terminal sessions. Path matching sees both.

Anything narrowing a signal appears in red as REDUCED ASSURANCE, also recorded in JSON:

- `-IdleHours 0`;
- an `-IdleHours` below the floor;
- an explicit `-ConfigRoot`, which *replaces* the machine's real registry;
- a **failed fetch**, after which merge decisions rest on stale refs;
- a merged-PR probe that errored;
- every `-Name`-confirmed worktree.

### A plausible threshold can disarm a signal completely

`-IdleHours 0.5` can remove protection instead of strengthening it. An occupied worktree measured
10.4 hours idle by git metadata; two guards address this:

- `$IDLE_FLOOR_HOURS = 12` -- deliberately not a parameter. A floor an operator can lower is not a floor, it
  is a second copy of `-IdleHours` with a reassuring name. Change it in a commit, with the
  measurement that justifies the new value.
- a negative `-IdleHours` puts the cut-off in the future, so the veto can never fire while still
  appearing to be set. The run **refuses** (exit 2) rather than running with a disarmed veto.

Previously only literal `0` produced a warning. Values above 0 but below the floor also
disabled effective activity protection without reporting it.

`-Name` bypasses signal 2 for one tree, like scoped `-IdleHours 0`. Since signal 1 once
vetoed no busy-repo siblings, `-Apply -Name <slug>` may have no effective occupancy signal.

`-Name` remains available for legitimate use, but always warns about the reduced
protection.

## A wrong-cwd run must refuse loudly, never green no-op

A linked checkout produces the wrong sibling prefix. The old tool called the resulting empty set
"nothing to consider"; three refusals now prevent that:

- not the primary checkout -> exit 2, printing both paths.
- the trunk cannot be resolved -> exit 2. Guessing `origin/main` when the trunk has another name
  reports "not merged" for every candidate. That can look like a healthy run despite examining the
  wrong base.
- `-Name` matched no prunable sibling -> exit 2 (or 1 if something was already removed),
  because what the operator asked for did not happen.

## Re-check immediately before each destructive step

`-Apply` rebuilds the decision table in its own run. Immediately before each removal, it
checks again:

1. fence availability -- a fence that **dies mid-run** stops the rest of the run;
2. occupants, including nested;
3. newly appeared nested worktrees;
4. signal 2 (activity), which was once the one signal missing from this block;
5. cleanliness.

A merged-PR probe takes roughly half a second per candidate, plus earlier removals' time. A session
can arrive during that delay.

Refresh for every candidate. One read before the loop is fresh only for the first removal.

In a three-worktree fixture, a session entered candidate two while candidate one was removed. The
single-snapshot version removed all three and reported `vetoedCandidates: 0`.

A fence read costs about 64 ms for `git worktree list` and a registry scan. The same candidate already
costs ~500 ms for the PR probe, and removal already lists worktrees.

The check reduces staleness to one candidate's work but is not atomic. Steps 4 and 5 still occur
between the fence read and removal.

`readsAtApply` should equal `counts.prunable` on a healthy run. A lower count means the fence
stopped the run; `availableAtApply` becomes false and `detailAtApply` explains where.

`rootsExamined`, `recordsExamined`, and `liveInRepo` describe the decision-pass read, not totals
across the run.

A later healthy read cannot cancel an unavailable one: candidate 4 says nothing about candidate 2.
The run exits 2, or 1 if it already removed something.

A re-check veto writes its occupants back to the decision. Otherwise the saved candidate would show
`Occupants: []` and undercount signal 1's protection as zero.

## Count outcomes, not intentions

Count completed outcomes, not planned removals:

- a removal counts as `removed` only once the directory is **verified gone** and
  **deregistered**. Exit 0 is git's claim; the directory being gone is the fact.
- `orphaned` is a **subset** of `failed`, and `failedNonOrphan` is spelled out so a
  consumer cannot reach a wrong total by adding all four numbers.
- `BranchOutcome` starts at `not attempted`, never `kept`. Otherwise every skipped
  candidate claims a decision nobody made: the JSON once said 7 branches were kept on a run whose
  summary said 0.
- `Merged` stays `$null` when the test never ran. `$false`, serialized as
  `false`, would claim "checked, and it is not merged" instead of "never asked".
- the final line is coloured by the **exit code**, not by the failure count. A run where the fence
  died and every removal was refused has `failed 0`, and used to print that in green next to
  exit 2.

### Exit codes

Highest severity wins.

| Code | Name | Meaning |
|---|---|---|
| 0 | OK | nothing wrong |
| 1 | FAILED | something was attempted and did not fully succeed, **without leaving anything broken on disk** -- a removal that failed, or a run that stopped partway with earlier removals already done |
| 2 | REFUSED | nothing was attempted, because safety could not be established (wrong cwd, unresolvable trunk, unavailable fence, a `-Name` that matched nothing) |
| 3 | ORPHANED | a directory is broken on disk **right now** (this run, or an earlier one) |

3 outranks 2 because damage on disk outranks a refusal to act.

## A failed removal is worse than no removal

`git worktree remove --force` removes the `.git` pointer and registration before walking the tree. A
failed walk can leave a broken directory reporting `fatal: not a git repository`.

Diagnose failures immediately. Report whether the directory, `.git` pointer, and
registration survived.

Repair the partial worktree or move it aside so its files can be recovered.

Run the recovery recipe printed by the tool from the primary checkout:

```powershell
# 1. close anything holding files open in it (an editor, a shell sitting in it)
# 2. if the .git file survived, try this FIRST -- the registration may be re-creatable in place:
git -C <primary> worktree repair <path>
# 3. otherwise move it aside and re-add it:
Move-Item <path> <path>.salvage
git -C <primary> worktree add <path> <branch>
# 4. copy anything you need out of <path>.salvage
#    (stashes are safe -- they live in the shared .git)
```

Step 2 requires a surviving `.git` file for `worktree repair`. Without it, move the
directory aside as in step 3; even `worktree add --force` refuses an existing directory.

### Never run `git worktree prune`

Neither `prune-merged.ps1` nor `remove.ps1` runs `git worktree prune`.

`git worktree prune` deregisters any momentarily missing directory, including live-session paths and
harness-managed nested trees. Use `git worktree remove` to deregister only the chosen worktree.

### An orphan outlives the run that made it

A deregistered worktree disappears from `git worktree list`. Previously the next run reported all-clear
while the broken directory and recovery instructions were left behind.

The shared ledger `<git-common-dir>/<prefix>-coord/prune-merged-orphans.json` preserves orphan reports and recovery commands until repair or
deletion. Two independent detectors cover them:

- the **ledger** written at the moment of the failure;
- a **ledger-free** scan: an unregistered sibling whose `.git` **file** points into this
  repo's worktree admin area. The `<primary>-` prefix alone is not enough. A relative
  `gitdir:` resolves against the `.git` file's directory, not this process's cwd;
  get that wrong and an orphan reports as fine.

Only `-Apply` writes the ledger. A dry run reports it without changes; repaired or fully
deleted entries clear themselves.

Ghost stubs from failed auto-worktree creation have no `.git` pointer or registration
(`scripts/worktree/worktree-selfheal.ps1`, `anthropics/claude-code#76590`). This detector requires the pointer and excludes them.

## Deleting the branch: `-d` refusing is a signal

`git branch -d` may refuse work merged into a remote trunk when the local trunk lags. Routine
`-D` use would bypass git's last protection for unrelated reasons.

`Remove-BranchSafely` now does:

1. `git branch -d` first;
2. if that refuses, re-verify at that moment that `<trunk>..<branch>` is empty;
3. `-D` only then, reporting "re-verified: 0 commits beyond `<trunk>`, so nothing
   was lost";
4. otherwise **keep the branch** and say why, with the command to delete it by hand.

Never touch the branch after an unverified removal. A leftover reference is preferable to destroyed
commits.

`remove.ps1` uses only `-d`. On refusal, it retains the branch, prints the tip, and
supplies a `-D` command for deliberate manual use.

## Claims stranded by a removal

Claims survive in shared `<git-common-dir>/<prefix>-coord/`. `-Take` stays blocked until `-Release <key> -Force`
removes the claim (`scripts/coord/claim.ps1`).

The pruner releases claims under these rules:

- on evidence, never on a timer. Release requires proof that the directory is gone **and**
  deregistered. No session can then remain there to collide with. A claim whose holder is merely
  quiet is never touched; an auto-expiring claim would re-open the race it prevents.
- full normalized path equality only -- no leaf name, no prefix, no `StartsWith`. Releasing a
  *living* worktree's claim hands its key to another session, inviting the duplicate build the
  registry prevents. One normalizer on both sides, or the match silently misses and the claim stays
  stranded.
- a dry run releases nothing.
- an **unreadable** claim file belongs to the registry, not to any worktree: by definition we could
  not read whose it is. It is surveyed once, at run level, so a dry run sees it and no removal can
  count it twice. It is left in place, listed by filename, and it moves the exit code.
- `claims.scanned: false` is emitted when there was no claims directory to read. Never looked is not clean:
  an empty `unreadable` list means something only when you can prove you looked.

## The manual path, and a deliberate asymmetry

`remove.ps1` blocks tracked changes unless forced but permits untracked environments, build
output, and scratch databases. `prune-merged.ps1` blocks untracked files.

The manual command relies on the human checking which files are disposable. Keep the unattended
pruner stricter; do not make the two policies agree.

`remove.ps1` also refuses from inside its target worktree and explains that caller error.

**Since 2026-09-23 its tracked-changes guard uses the same read as the reaper.** It refuses, without
`-Force`, when `git status` on its target fails. Before, it ignored the exit code, so a corrupt index
read as no changes, and the `--force` removal deleted an uncommitted edit.

Here the two agree. Both refuse a worktree that contains another registered worktree, through the
same `Get-NestedWorktrees` call. `-Force` does not override it. `remove.ps1` gained the check on
2026-09-22; see [Worktrees](WORKTREES.md#two-layouts-coexist-and-only-one-has-scripted-teardown).

## Reference

Remove finished worktrees while preserving unfinished ones.

Run these from the primary checkout:

```powershell
pwsh -NoProfile -File scripts/worktree/prune-merged.ps1                   # dry run, no action
pwsh -NoProfile -File scripts/worktree/prune-merged.ps1 -Fetch            # dry run, refresh refs first
pwsh -NoProfile -File scripts/worktree/prune-merged.ps1 -Apply            # remove the ones that pass
pwsh -NoProfile -File scripts/worktree/prune-merged.ps1 -Apply -Name auth # confirm past the activity veto
pwsh -NoProfile -File scripts/worktree/prune-merged.ps1 -Apply -SkipFetch # offline / faster
pwsh -NoProfile -File scripts/worktree/prune-merged.ps1 -Json             # machine-readable receipt

pwsh -NoProfile -File scripts/coord/presence.ps1                          # who is here, read-only
pwsh -NoProfile -File scripts/worktree/remove.ps1 -Name auth -DeleteBranch
```

The dry run prints each sibling's decision, reason, fence receipt, and blind spots. Read SKIP
reasons before applying; exit 2 means refusal with no removal.

| Flag | Effect | Narrows the fence? |
|---|---|---|
| `-Apply` | actually remove; re-evaluates the whole table first | -- |
| `-Fetch` | fetch during a **dry run** too (off by default: `fetch --prune` rewrites remote-tracking refs, which is what turns an upstream into `[gone]`, so a "safe preview" should not enlarge the next apply's blast radius) | -- |
| `-SkipFetch` | skip the fetch even under `-Apply` | merge decisions use stale refs |
| `-Name <slug>` | restrict to these worktrees **and confirm them past the activity veto**. Never overrides signal 1, a nested worktree, or a git lock | yes, loudly |
| `-SkipGh` | do not ask about merged PRs | drops merge signal 2 |
| `-Json` | emit the decision objects, the fence receipt and the counts | -- |
| `-RepoRoot <path>` | repo to operate on -- a **hint**, validated against the primary; the run refuses if they differ | -- |
| `-ConfigRoot <path>` | config roots for the fence. **Replaces** the real registry | yes |
| `-IdleHours <n>` | signal 2 window, default 36, floor 12, negative refused | yes below the floor |
| `-StartSkewMinutes <n>` | liveness fence tolerance for process start vs session registration | -- |
| `-MainRef <ref>` | the ref work must be merged into; defaults to the configured trunk | -- |

## Testing a destructive tool

Use these checks when testing removal:

Assert both decision and reason. Survival-only tests missed a broken primary fence because the
re-check saved the directory; include a positive control unless the whole run must refuse.

Use a probe shim that changes state before returning: add a session, break the fence, or touch
metadata. This deterministically tests apply steps 1, 2, and 4 without threads or sleeps.

Wrap the real function instead of replacing it. A hand-written safety stub can drift away from the
actual check.

Place the arriving session in git's second removal candidate. Worktree order is not alphabetical,
and even a stale snapshot is fresh for candidate one.

## Limits, stated plainly

- **PowerShell 7, Windows-first.** These scripts are `#Requires -Version 7.3`. Path folding is
  case-insensitive only where the filesystem is (`$IsWindows -or $IsMacOS`). The folded form is for
  comparison **only**: never pass it to git or the filesystem. A Linux CI run was bitten by that
  once.
- The session record schema is a vendor contract. The liveness fence rests on Claude Code's own
  per-session records (`<config-root>/sessions/<pid>.json`, carrying `pid` / `startedAt` /
  `sessionId` / `cwd`). When it changes, the fence must become *unavailable* and
  refuse, not quietly empty.
- `list_sessions` cannot see every session kind. The Desktop app's session tooling enumerates
  sessions it spawned; an editor-extension session in the same config root never appears. The file
  registry above is the only source carrying every surface, so the fence reads that, not the MCP
  tool.
- There is no heartbeat. Nothing here can prove a session is gone. That is not an implementation gap
  to be closed later; it is why occupancy may only ever veto.
- Signal 1 has measurably low coverage of the population this tool prunes. Treat signal 2, and the
  refusal to run without a fence, as load-bearing rather than as belt-and-braces.
- **Only the sibling layout has scripted teardown *here*.** `prune-merged.ps1` excludes nested
  worktrees under `.claude/worktrees/` unconditionally, and the gate leaves them alone.

`remove.ps1` applies no such test. Under `worktreeLayout: nested` it resolves its target to that path
and removes it ([Worktrees](WORKTREES.md#two-layouts-coexist-and-only-one-has-scripted-teardown)).
