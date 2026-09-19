# Landing work: PRs and merges

<a id="tldrbluf"></a>

Check the merge base before landing parallel branches in one trunk. Then read the merge state and
resolve conflicts while preserving both sides' work.

A branch ahead of the trunk may already be merged. Treating that reading as proof of unmerged work
has destroyed commits.

These procedures address parallel branches. `git` commands are portable; `pwsh`
scripts require PowerShell 7.3+ and were exercised on Windows; `gh` requires GitHub
([Limits and requirements](LIMITS.md)).

Run the merge-base check below before trusting merge status. [WORKTREES.md](WORKTREES.md) covers creating
worktrees; [PRUNING.md](PRUNING.md) covers cleanup.

---

Parallel sessions produce branches that must all merge into one trunk.

The incidents and numbers come from the repository where this tooling was built. They support the
rules but do not establish universal rates.

These procedures assume squash-merging and concurrent changes to the trunk:

- **The trunk squash-merges.** A branch's own commits never become ancestors of the trunk. So every
  reachability-based test -- `rev-list`, `merge-base --is-ancestor`, `git cherry` -- answers "not
  merged" forever, for work that landed weeks ago.
- Somebody else lands something while you are working. Not hypothetically. Measured on the repo this
  tooling was developed in, the trunk moved seven times during the life of one pair of pull
  requests.

## What "trunk" means to these scripts

Every script resolves the trunk through one function, `Get-CcxTrunk` in [`scripts/coord/_common.ps1`](https://claude-multisession.pages.dev/scripts/coord/_common.ps1), in this
order:

| Order | Source | Notes |
|---|---|---|
| 1 | `$env:CCX_TRUNK` | Per-session override; wins over everything. |
| 2 | `trunk` in [`ccx.config.json`](https://claude-multisession.pages.dev/ccx.config.json) | Unless it is the literal `auto`. |
| 3 | `git symbolic-ref --short refs/remotes/origin/HEAD` | What the remote says its default branch is -- the only source that survives a rename. |
| 4 | First of `origin/main`, `origin/master`, `main`, `master` that resolves | Last resort. |

The function prefers a remote-tracking ref because local `main` can silently lag. If step
3 fails on an older clone, record the remote head with `git remote set-head origin -a`.

The examples below spell the trunk `origin/main`. Substitute yours.

## Check the merge base before anything else

Before reading a diff or opening a pull request, check whether your branch contains the trunk tip.

```bash
git fetch origin
git merge-base --is-ancestor origin/main HEAD   # exit 0 = your branch contains the trunk tip
```

Exit 0 confirms the branch contains the trunk tip. Otherwise, merge the trunk before continuing; the
pre-squash case below may explain more than a branch simply falling behind.

In PowerShell, read `$LASTEXITCODE`. `$?` describes the last statement and can report
success after a check answered "no".

### The trap: A branch cut from a pre-squash commit

One branch began from a commit pushed to an already-squash-merged pull request. Its three-dot diff
and "Files changed" showed roughly 13 files, 2,967 insertions, and 19 deletions.

Those views omitted five conflicting files; the merge base was eleven squash-merged pull requests
behind. Squashing creates a new trunk commit instead of making the branch commits ancestors.

A branch from an original commit inherits that pre-squash base. `git diff origin/main...HEAD` uses that base;
compare two-dot after `--is-ancestor` fails:

```bash
git diff --stat origin/main HEAD      # two-dot: what still DIFFERS from the trunk
git diff --stat origin/main...HEAD    # three-dot: what the BRANCH AUTHORED
```

Two-dot deletions show content the trunk has and the branch lacks. They do not establish what the
merge would remove.

Two-dot compares two trees, so everything the trunk gained since the merge base reads as a deletion.

Measured on a three-commit fixture: a branch one commit behind, adding one file and removing
nothing, reported 4 deletions across 2 files. Merging the trunk in removed none of them.

The example below showed 22 two-dot deletions before merge and identical diffs after.
[Coordination](COORDINATION.md) records a 63-commit-behind branch whose 3,247 deletions were briefly misread as
proposed removals.

Run `git merge origin/main`; the trunk's squashed content is authoritative. Rebase repeats that conflict
per commit ([merge over rebase](#prefer-merge-over-rebase-when-every-commit-touches-one-block)).

### The staleness check that agrees with itself

Matching two-dot and three-dot diffs adds no independent proof that a branch is current.

Once `--is-ancestor` passes, both diffs use `origin/main` and cannot disagree. Before merge,
two-dot showed 2 files / 52 insertions / 22 deletions; three-dot showed 1 file / 50 insertions.

The forms became identical after merge. Use `--is-ancestor` as the actual check; diff agreement
merely confirms it.

## Reading "can't merge": Four states, three different fixes

<a id="g08"></a>
<figure class="explain-figure">
  <picture>
    <source media="(max-width: 1100px)" srcset="/assets/diagrams/g08-merge-states-mobile.svg">
    <img src="/assets/diagrams/g08-merge-states.svg" alt="Four merge states connect to their distinct fixes." loading="lazy" width="799" height="668">
  </picture>
  <figcaption>Read the exact state before acting. Auto-merge waits for checks but does not update a BEHIND branch. <a href="/assets/diagrams/g08-merge-states.drawio">Editable diagram</a>.</figcaption>
</figure>

A pull request can stop being mergeable within ten minutes. Rebasing and force-pushing without
reading its state can cancel checks or damage conflict resolution.

Read which of the four merge states applies before changing the branch.

```bash
gh pr view <N> --json state,mergeable,mergeStateStatus,statusCheckRollup
```

Read `mergeStateStatus`, then follow the matching row's **Do** column:

| State | What it actually is | Do | Do not |
|---|---|---|---|
| `BEHIND` | The branch does not contain the trunk tip. Mechanical; no conflict. | Merge the trunk in, or `gh pr update-branch <N>`. | -- |
| `DIRTY` | A real textual conflict. | Resolve by hand, deliberately, in a worktree. | Treat it as `BEHIND`. That means resolving conflicts in a hurry to make a force-push succeed. |
| `BLOCKED` | Required checks or reviews are not satisfied. Usually still running. | Take every rollup entry whose `conclusion` is **not** `SUCCESS`, `SKIPPED` or `NEUTRAL`. Nothing in that set plus pending legs means **wait**. | Count *actual failures*. A cancelled check is not a failure and not pending, so it vanishes from both counts and a blocked branch reads ready. |
| `UNKNOWN` | The code host is still recomputing mergeability. | Re-read in a few seconds. | Anything else. |

Do not confuse `BEHIND` with `DIRTY`; a textual conflict needs deliberate
resolution. `BLOCKED` usually requires waiting for checks.

> **Limit.** `mergeStateStatus` is GitHub's field and `gh` is a GitHub client. On another code host the
> four states still exist conceptually -- behind, conflicting, gated, not-yet-computed -- but you will
> read them from a different API. What does not change is the rule: **establish which of the four you
> are in before you touch the branch.**

## Two pull requests at once

### Armed auto-merge does not win the race against the trunk moving

Two pull requests had auto-merge armed. After the first merged, the second stalled indefinitely
without either failing or merging.

Auto-merge waits for checks but does not update a `BEHIND` branch. The first merge puts the
second branch behind and leaves it there.

When queuing two pull requests, plan to update the second after the first merges. Cap the update
loop.

> Measured with the repository's "allow update branch" setting off. Whether turning that setting on
> changes the behavior is **unverified**. No back-fill was ever observed, and the code host's own
> documentation does not connect the setting to this case. Do not repeat it as fact.

### A merge-watcher needs three arms, not two

A watcher checking only merge and failure can time out while a branch stays `BEHIND`. It
must also detect when the trunk moves.

Watch for a decision and handle a stale branch.

Poll for merged, failing, and stale states; update on the third:

```powershell
$pr = <N>
for ($i = 0; $i -lt 40; $i++) {
    $j = gh pr view $pr --json state,mergeStateStatus,statusCheckRollup | ConvertFrom-Json
    if ($j.state -eq 'MERGED') { 'merged'; break }

    # Check-run entries carry `conclusion`; legacy commit statuses carry `state`. Handle both or
    # you will poll past a failure without seeing it.
    #
    # ALLOW-LIST, not deny-list. This read `-in @('FAILURE','TIMED_OUT','CANCELLED')` until
    # 2026-09-09. A deny-list has to name every bad value, and ACTION_REQUIRED and STALE were
    # both missing. Naming the three GOOD values cannot be incomplete in that direction.
    $bad = @($j.statusCheckRollup | Where-Object {
            ($_.conclusion -and $_.conclusion -notin @('SUCCESS','SKIPPED','NEUTRAL')) -or
            ($_.state -eq 'FAILURE') })
    if ($bad.Count -gt 0) { "failing: $($bad[0].name) [$($bad[0].conclusion)]"; break }

    # THE THIRD ARM.
    if ($j.mergeStateStatus -eq 'BEHIND') { gh pr update-branch $pr | Out-Null }

    Start-Sleep -Seconds 30
}
```

The loop stops after printing `merged` or the first failing leg. Continued updates mean the
trunk keeps moving ahead of the branch.

### "Nothing pending" right after a push means "nothing has started"

Immediately after a push, checks showed no pending legs because the new run had not started. No
pending checks does not mean checks finished.

Assert the expected check-leg count. Read that set from current required-check configuration, not
memory.

The same mistake appears in the `--ours` example below: an accurate reading omitted the
content needed to answer the real question.

### A green check attests to a base, so record the base beside it

A green run applies to the trunk commit tested at that moment. Without recording that commit, the
result cannot show which base it verified.

`gastown` stores the CI result and trunk SHA together in `internal/refinery/engineer.go`. Its merge path
then compares the recorded base:

```powershell
$recorded = '<the trunk sha stored beside the green result>'
if ((git rev-parse origin/main) -eq $recorded) { 'pre-verified' } else { 'stale -- re-run the gates' }
```

If the trunk still matches, pre-verification holds and gates need not rerun. If it moved, the gates
must run again.

Auto-rebase must refuse while the pre-verified flag is set. Rebase changes the base that the flag
certifies.

Without that refusal, the flag can survive rebase and falsely certify the new base.

This helps only while the trunk is quiet. A deep queue keeps changing it.

Here, the trunk moved seven times during one pair of pull requests. Separately, eighteen queued
entries produced zero merges in an hour ([FAQ](FAQ.md)).

The mechanism can prevent a queue from reaching eighteen entries. It cannot clear one already that
deep.

KORUS does not store the result/base pair today. Adoption requires recording the trunk SHA and
making rebase refuse while pre-verification stands.

## Resolving conflicts without losing work

### A stamped bookkeeping field makes two disjoint writes collide

Two sessions can change different ledger rows and still conflict.

Every mutation may stamp `updated_at`, causing both sessions to change the same bookkeeping
line.

The `beads` issue store measured timestamp stamping increasing conflicts in its own ledger.
This is an external finding.

Write only fields relevant to the change. A change that did not touch a timestamp or counter must
not stamp one.

Git already records when lines changed and who changed them. Read that history with `git log -L`
or `git blame` without adding conflicting fields.

KORUS measured 33 of 34 merged commits touching the item ledger ([roles/MANAGER.md](https://claude-multisession.pages.dev/roles/MANAGER.md)). It treats that
contention as a design property.

Nobody has measured the bookkeeping-only share here. The beads result supports the mechanism, not a
local conflict rate.

To measure it, merge two ledger-changing branches and count conflict hunks containing only
bookkeeping differences.

Sample open branch pairs. Already-landed branches merge cleanly into a trunk containing their work,
leaving no conflicts to count.

```powershell
$ledger = '<the ledger path in your repository>'
$a = '<head SHA of one open pull request>'
$b = '<head SHA of another that touches the same ledger>'

# --write-tree prints the tree OID on its first line. A CONFLICT is what we want here, so a
# non-zero exit is the expected case; only an empty OID means the command itself failed.
$tree = (git merge-tree --write-tree $a $b) -split "`n" | Select-Object -First 1
if (-not $tree) { throw "merge-tree produced no tree -- check both SHAs exist locally" }

# READ THE EXIT CODE. Without this a wrong ledger path makes `git show` fail, prints nothing,
# and the count comes back zero -- reported as "no bookkeeping-only conflicts". That is the
# calm zero this page exists to attack, and an earlier draft of this recipe had it.
$conflicted = git show "${tree}:$ledger" 2>$null
if ($LASTEXITCODE -ne 0) { throw "cannot read $ledger from tree $tree -- wrong path or wrong tree" }
if (-not $conflicted) { throw "$ledger read as empty -- that is not the same as no conflicts" }

$hunks = $conflicted | Select-String -Pattern '^<<<<<<<' 
"conflicted hunks: $($hunks.Count)"   # print the denominator beside any share you report
```

Define the bookkeeping fields before counting. A hunk qualifies only when every differing line
belongs to that set; choosing fields afterwards changes the reported share.

### Never take a side wholesale on an append-only file

Changelogs, backlogs, and decision indexes receive appends from many sessions. Their frequent
conflicts make wholesale `--ours` or `--theirs` tempting.

```bash
git checkout --ours docs/CHANGELOG.md    # <-- this is the one that loses work silently
```

Either side can produce a well-formed file while silently discarding the other's entries:

- no conflict markers
- `git status` clean
- the structure check passes
- the linter passes
- CI green

Two pull requests each added `### Changed`. Both blocks were needed: `--ours` would
discard two published breaking-change notices, while `--theirs` would discard the incoming
notice.

Either one-sided resolution could pass CI. Keep all entries from both sides, then search for
distinctive text from each:

```bash
git grep -n "one distinctive phrase from THEIR entry"
git grep -n "one distinctive phrase from YOUR entry"
```

### Anchor a find-and-replace, and re-verify it after the conflict is resolved

Renumbering an item from `1252` to `1316` across a changelog turned
`cp1252` into `cp1316`, in a file nobody re-reads.

The bare number matched inside unrelated tokens. Repeating the sweep during conflict resolution then
applied it to newly changed content.

Match anchored forms such as `item #1252`, `## 1252.`, or `^1252\|`, never a bare
number. Recheck replacements after conflict resolution as well as after the first edit.

### Prefer merge over rebase when every commit touches one block

When every commit appends at one location, rebase repeats the same conflict per commit. Resolving
against an intermediate revision once preserved an earlier draft.

The result had clean status and no conflict markers. Its shortened entry still had one heading, so
the structure check passed.

Use one `git merge origin/main` to resolve against the final text. Then search for a string found only in
your latest revision; structure alone cannot prove the version.

### A content comparison does not predict a clean merge

Five files matched in a byte comparison. Twenty minutes later, a queued pull request changed those
files on the trunk, making the comparison stale.

A content comparison establishes equality now, not whether a later merge will succeed. Another
queued change to those files can invalidate it.

Use `git merge-tree --write-tree` or a trial merge in a throwaway worktree to test for conflicts.

Pass `--write-tree`. The old `git merge-tree <base> <ours> <theirs>` form exits 0 even on conflicts.

The bare form can therefore falsely suggest a clean merge. `--write-tree` exits 1 and names
conflicting paths ([Coordination](COORDINATION.md)).

Test the merge in a disposable worktree to protect the working branch.

```powershell
# A real trial merge, isolated, disposable.
pwsh -NoProfile -File scripts/worktree/new.ps1 -Name mergetrial -Base my-branch
# ...in the new worktree:  git merge origin/main
# then, from ANOTHER checkout -- and abort first if it conflicted:
pwsh -NoProfile -File scripts/worktree/remove.ps1 -Name mergetrial -DeleteBranch -Force
```

A conflicted trial leaves modified tracked files, so `remove.ps1` refuses without
`-Force`.

Removal also refuses from inside the target worktree. Run `git merge --abort` first or use
`-Force`, then remove it from another checkout.

`-DeleteBranch` uses `git branch -d`, which may refuse the unmerged trial branch. If it remains,
verify it is disposable before deleting it by hand.

The trial either merges or exposes real conflicts in the disposable worktree. `gh pr update-branch`
merges the base server-side and cannot resolve those conflicts.

Before you start resolving, ask who else is in those files right now:

```powershell
pwsh -NoProfile -File scripts/coord/overlap.ps1 -File path/to/file.md
```

Overlap reports both uncommitted and committed-but-unlanded peer changes to the path. It intersects
two-dot and three-dot file sets, usually clearing landed branches.

The map may be cached for up to 60 seconds. Pass `-Refresh` to request current state.

Self-clearing lasts only until someone edits that file again. Two-dot can then blame a landed branch
for the later edit ([Coordination](COORDINATION.md)).

## Writing up the result: Two true numbers can make a false sentence

An earlier version paired post-merge three-dot results with pre-merge two-dot results. Both readings
were real, but their comparison falsely described a diff as proposing a revert.

The error survived the author, a second reviewer, independent verification, and green CI. None
checked whether the readings belonged together.

Before comparing numbers, confirm they describe the same commit at the same moment. Record each ref
and measurement time.

## After it lands

After squash-merge, common reachability checks can still report unmerged work:

- `git rev-list --count origin/main..<branch>` still counts every original commit -> says *not merged*
- `git merge-base --is-ancestor <branch> origin/main` is false -> says *not merged*
- `git cherry origin/main <branch>` marks the commits `+` unless the patch-ids match exactly, which they
  stop doing the moment anything was rebased, amended or conflict-resolved

Squash-merge creates a new trunk commit without retaining the original commits as ancestors. A
branch ahead of the trunk therefore need not hold unmerged work.

[`scripts/worktree/prune-merged.ps1`](https://claude-multisession.pages.dev/scripts/worktree/prune-merged.ps1) carries three merge signals instead of one:

- nothing beyond the trunk
- *or* a merged PR whose head is this exact tip
- *or* the branch's own upstream ref is gone

Zero commits beyond the trunk also does not prove a merge: a seconds-old branch has that state.
Cleanup once destroyed an occupied worktree this way ([PRUNING.md](PRUNING.md)).

Remove only worktrees whose work has landed.

```powershell
# from the PRIMARY checkout -- it refuses from a linked worktree, exit 2
pwsh -NoProfile -File scripts/worktree/prune-merged.ps1 -Fetch          # dry run, decision table
pwsh -NoProfile -File scripts/worktree/prune-merged.ps1 -Fetch -Apply   # act on a table re-derived now
```

The dry run prints decisions without changing anything. `-Apply` recalculates those
decisions when it acts.

Use `-Fetch` for preview and apply so both use refreshed state. [Pruning](PRUNING.md#a-wrong-cwd-run-must-refuse-loudly-never-green-no-op) explains
the flags and linked-worktree refusal.

Use [`remove.ps1`](https://claude-multisession.pages.dev/scripts/worktree/remove.ps1) for one finished worktree. At merge time, these two behaviors matter:

- It references the tip before removing anything, and with `-DeleteBranch` writes it to
  `refs/<prefix>/removed/<name>` first. A commit in no ref is in no reflog either, and nothing in the interface
  admits it ever existed.
- It uses `git branch -d`, **never** `-D`. Git refusing to delete an unmerged branch is
  a *signal* that the branch holds commits no other ref has. If the local trunk merely lags the
  remote, fetch and retry. Do not force past the refusal as a tidying step.

Work claims taken with [`claim.ps1`](https://claude-multisession.pages.dev/scripts/coord/claim.ps1) do not expire, and they do not release themselves when a PR
merges.

Release your claims after the work lands so other sessions can use them.

The lander does this for a builder's claim, in the same act as the backlog update. An orphaned claim
blocks the next session on that row, and nothing anywhere reports it.

```powershell
pwsh -NoProfile -File scripts/coord/claim.ps1 -Release <key>
pwsh -NoProfile -File scripts/coord/claim.ps1 -List
```

`-List` confirms which claims remain. The pruner releases a worktree's claims only after
proving the directory is gone and deregistered, never on a timer.

`-Release` acts on the worktree your shell stands in. Releasing another worktree's claim needs
`-Force`, and the script refuses first and probes the holder.

Read that probe line. `HOLDER GONE` means the worktree is off disk and forcing is safe. `HOLDER IS
STILL THERE` is a fact about a directory, not about a live session.

## What this tooling does and does not do for you

Check these limits before relying on the tools:

- **PowerShell 7, Windows-first.** The scripts are PowerShell 7 (`#Requires -Version 7.3`). The git commands
  in this document are portable. The scripts are not yet.
- GitHub is assumed where `gh` appears. The PR-state table, the watcher loop, and the
  merged-PR signal in the pruning tool all call `gh`. The pruning tool degrades
  explicitly -- `-SkipGh`, and a failed probe is reported as a failed probe rather than as
  "not merged".
- The push guard is a guardrail, not a security boundary. [`scripts/hooks/push_guard.py`](https://claude-multisession.pages.dev/scripts/hooks/push_guard.py) refuses a direct push to
  anything in `protectedRefs` (default `main` and `master`), locally and before
  the round trip.

Limit: `git push --no-verify` skips it, and it is installed per clone, so configure server-side protection
too. The escape hatch is `CCX_ALLOW_DIRECT_PUSH=1`, distinct from `--no-verify` so it is greppable in
shell history.
- An installed guard and a working guard are different claims. These hooks are copied into place.
  One whose helpers were not copied can refuse *every* push, for reasons unrelated to what it
  checks. One never installed is just a source file. Prove it by receipt before you rely on it:

  ```powershell
  pwsh -NoProfile -File bin/ccx-doctor.ps1
  ```

## The traps in one table

| Trap | What it looked like | Rule |
|---|---|---|
| Pre-squash merge base | A clean three-dot diff and a tidy "Files changed" tab | Run `git merge-base --is-ancestor origin/main HEAD` **first**; fix by merging, not rebasing |
| Self-agreeing staleness check | Two-dot and three-dot diffs matched | They cannot disagree once `--is-ancestor` passes; it is the load-bearing check |
| Four states, one symptom | "Can't merge" | Read `mergeStateStatus`; `BEHIND` != `DIRTY`, and `BLOCKED` usually means wait |
| Armed auto-merge | Queued, green, and stalled forever | Auto-merge waits for checks, never updates a `BEHIND` branch |
| Two-armed watcher | "Still running" until timeout | Poll merged / failing / **went stale** |
| No pending checks | "Everything settled" right after a push | Assert on the expected leg **count**, not on absent pending legs |
| A green check with no base | "It passed" -- against a trunk that has since moved | Record the trunk SHA beside the result; refuse to rebase while the flag stands |
| A stamped bookkeeping field | Two sessions changed different rows and still conflicted | Write only the fields the change is about; never stamp `updated_at` on a write that did not touch it |
| `--ours` on an append-only file | Well-formed file, clean status, green CI | Union both sides, then verify surviving entries by name |
| Unanchored renumber | `cp1252` became `cp1316` | Anchor the pattern; re-verify **after** conflict resolution |
| Rebasing a one-block stack | Clean tree, one heading, half the prose | One `git merge`; grep for a string only the latest revision has |
| Blob comparison | Five files identical -- twenty minutes ago | `git merge-tree --write-tree` or a trial merge; `update-branch` cannot resolve conflicts |
| Two true numbers | Both figures verified individually | Confirm they describe the same commit at the same moment |
| Ahead of the trunk | "This branch is not merged" | Under squash-merge, reachability lies in both directions |
