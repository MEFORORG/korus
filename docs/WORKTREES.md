# Worktrees

## TLDR/BLUF

Give each concurrent session its own worktree. These commands create checkouts, rescue misplaced
work, restore the shared primary, and remove finished worktrees while preserving commit recovery.

A shared `git checkout` can replace another session's files without warning. These PowerShell 7
scripts target concurrent work and have been tested on Windows; test other platforms before relying
on them.

[Concepts](CONCEPTS.md) defines the terms. Use [Install](INSTALL.md) for the gate and backstop, and
[Pruning](PRUNING.md) for automatic cleanup.

---

Each agent or human needs a separate worktree to avoid branch changes replacing a peer's files.
Worktrees have separate directories, branches, and indexes, with shared git history and remotes.

The usual branch, pull request, and merge process stays the same.

> These scripts use PowerShell 7 and were developed and tested on Windows. Their path handling
> supports other platforms, but the defaults assume Windows; limits are noted below.

---

## Command reference

Commands normally resolve the primary checkout from the first `git worktree list` entry. These three
have extra location rules:

- `prune-merged.ps1` refuses unless you run it from the primary, exiting 2 and naming both paths.
  From a linked worktree the candidate set is empty for the wrong reason.
- `remove.ps1` refuses when you are standing inside the worktree you named.
- `bin/ccx-doctor.ps1` does not anchor at all. With no `-Repo` it reports on your current directory,
  which is how a long green report about the wrong clone happens.

Five of the eight commands validate `-Name` with `\A[A-Za-z0-9._-]+\z`, since it becomes a
directory and branch name. `restore-primary.ps1`, `sessions.ps1`, and the doctor take no name.

`prune-merged.ps1` instead accepts an unvalidated name list. It limits the sweep to those worktrees
and explicitly overrides their recent-activity veto.

That override never bypasses liveness, nested-worktree exclusion, or a worktree lock. See
[Pruning](PRUNING.md).

Use `\A...\z` for full .NET string matching. `^...$` also accepts a trailing newline because `$`
matches before it.

| Task | Command |
|---|---|
| Create a worktree on its own branch | `pwsh -NoProfile -File scripts/worktree/new.ps1 -Name <name>` |
| Create it and open an editor there | `pwsh -NoProfile -File scripts/worktree/spawn.ps1 -Name <name>` |
| Move uncommitted work out of the primary | `pwsh -NoProfile -File scripts/worktree/rescue.ps1 -Name <name>` |
| Put the primary back on its home branch | `pwsh -NoProfile -File scripts/worktree/restore-primary.ps1` |
| Remove one worktree | `pwsh -NoProfile -File scripts/worktree/remove.ps1 -Name <name>` |
| Remove the finished ones in bulk | `pwsh -NoProfile -File scripts/worktree/prune-merged.ps1` (dry run; `-Apply` acts) |
| Find sessions whose transcript moved | `pwsh -NoProfile -File scripts/worktree/sessions.ps1` |
| Prove the guards are actually live | `pwsh -NoProfile -File bin/ccx-doctor.ps1` |

Repository-root `ccx.config.json` holds the command settings and enables announce.

The worktree gate and SessionStart backstop instead use `~/.claude/hooks/ccx-gate.repos.txt`. Apart
from the backstop's `prefix` setting, config does not control them; see
[Limits](LIMITS.md#what-actually-switches-each-control-on).

| Key | Effect on this document |
|---|---|
| `trunk` | The default `-Base` for a new worktree and the ref merged work is measured against. `auto` asks the remote what its default branch is. Overridable per session with `CCX_TRUNK`. |
| `worktreeLayout` | `sibling` (default) or `nested` -- see [Two layouts](#two-layouts-coexist-and-only-one-has-scripted-teardown). |
| `setupHook` | The per-checkout bootstrap `new.ps1` runs after creating a worktree. |
| `prefix` | The stem for the state root, the `<prefix>.homeBranch` git config key, and the `<prefix>-home-branch` sidecar record. |

---

## Creating a worktree

Create your checkout and branch from the current remote tip.

Run either command from any checkout of the repository:

```powershell
pwsh -NoProfile -File scripts/worktree/new.ps1 -Name alerts
pwsh -NoProfile -File scripts/worktree/new.ps1 -Name sqltuning -Base feature/sql-tuning
pwsh -NoProfile -File scripts/worktree/new.ps1 -Name quicklook -NoSetup
```

`new.ps1` fetches, creates the worktree, runs setup, and prints
`Worktree ready: <path> (branch '<branch>')` with next steps.

`spawn.ps1` forwards `-Name`, `-Base`, and `-NoSetup`, then opens an editor only after creation
succeeds. It reports an editor missing from `PATH`.

`-Editor` overrides `CCX_EDITOR`, then `EDITOR`, then default `code`.

### The base is the freshly fetched remote tip, not local `main`

Local `main` often lags upstream in a multi-worktree repository. Starting from it creates stale work
and stale merge judgments, including the reaper's check.

`new.ps1` fetches first and defaults to a remote-tracking ref such as `origin/main`. Two rules
govern that fetch:

- It fetches the remote the trunk lives on, parsed out of the base ref, rather than a hardcoded
  `origin`. A fork-based workflow whose trunk is `upstream/main` would otherwise fetch the wrong
  remote and report success.
- A fetch failure (offline) is a loud warning, not fatal. You can still branch off the refs you have
  -- you just need to know that is what happened.

An explicit local `-Base` that trails upstream triggers a warning with the branch, lag count, and
suggested remote ref. Remote-tracking refs lack `@{upstream}`, so the default skips this check.

### Read from a ref, not from a working tree

The rule above governs where a branch starts. The same lag defeats reading, and that failure is
quieter: a search of a checkout answers for whatever that checkout last had.

Measured in this repository on 2026-09-17, from the primary checkout:

```powershell
git rev-parse --abbrev-ref HEAD                                      # a feature branch, not main
git rev-list --count HEAD..origin/main                               # 48
git ls-files .github/workflows/required-workflow-state.yml           # 0 lines
git show 'origin/main:.github/workflows/required-workflow-state.yml' # 158 lines
```

The primary sat 48 commits behind the trunk, on a branch nobody had switched back. A file that
exists on `origin/main` reads as absent there.

A second clone on the same machine read 257 behind by the same command. Three analysis passes
reported a file missing from that project because they had searched its primary tree.

So name the ref. `git show <ref>:<path>` and `git grep <pattern> <ref>` answer about the ref rather
than about wherever your shell happens to be standing.

Their positive control fired, which is why nobody caught it.
[Tips and tricks](TIPS-AND-TRICKS.md#a-control-can-fire-and-still-miss-the-subject) carries that half.

### Concurrent creation races `.git/config.lock`

Concurrent `git worktree add` calls can fail with
`could not lock config file .git/config: File exists`, leaving an orphaned branch. Creation writes
upstream settings into shared `.git/config`.

`new.ps1` serializes creation with `Enter-CcxLock -Name 'worktree-add'` and a 90-second timeout. The
lock has three required properties:

- Atomic exclusive-create is the mutex. The lock is a file created with create-new semantics; the
  filesystem, not a read-then-write, decides who won.
- It never steals. On timeout it fails loudly and names the holder. Breaking a lock can admit
  simultaneous writers. No reliable liveness signal here proves that a lock is abandoned.
- The script refuses to run without it. If `scripts/coord/lock.ps1` is missing, or does not define
  `Enter-CcxLock`, `new.ps1` throws rather than racing quietly. A safety property that degrades to
  "not applied" when a file is missing is not a safety property.

### One dependency environment per worktree

A shared editable or linked dependency install points to its original source directory. Tests in
worktree B can import worktree A, passing locally while CI fails.

Build each worktree's dependency environment inside that worktree through `setupHook`. `new.ps1`
runs the language-specific hook and reports its result:

| Contract | Detail |
|---|---|
| Working directory | The **new** worktree. Relative paths resolve against it. |
| `CCX_WORKTREE_PATH` | Absolute path of the new worktree |
| `CCX_WORKTREE_NAME` | The `-Name` it was created with |
| `CCX_PRIMARY_ROOT` | Absolute path of the primary checkout |
| `CCX_BASE_REF` | The ref the branch was created from |
| Arguments | None are passed, so a hook may declare whatever parameters it likes |
| Exit code | A `.ps1` hook runs in a **child** `pwsh`, so its exit code is a real contract and it cannot leave state behind in the calling session |

`examples/worktree-setup.ps1.example` includes Python and Node examples. Copy the parts you need to
`setupHook` 's path, shipped as `.ccx/worktree-setup.ps1`, and follow these rules:

- Build the environment inside the worktree, for the reason above.
- Install from your lockfile, not from your version ranges. A worktree that re-resolves dependencies
  gets whatever the registry serves today -- a different formatter from CI. With a `--fix` mode in a
  commit hook, that formatter rewrites your source to match a version CI does not have.

Setup reports two distinct failures:

- The hook file is not found in the new worktree or the primary -> a warning that the worktree has
  *not* been set up. The worktree's versioned copy takes precedence. The primary copy supports
  git-ignored hooks that `git worktree add` cannot deliver.
- The hook exits non-zero -> a throw that states the worktree *was* created, at which path, on which
  branch, and is not rolled back. A bare "setup failed" reads as "nothing happened", and the next
  session re-runs creation into a path that is now occupied.

Use `-NoSetup` to create files without an environment. The printed next steps explicitly report that
setup has not run.

### Environments multiply, so start the removal habit in week one

One environment per worktree stays right. It is also the line item that grows, and nothing here
removes an environment for you.

Measured on the development host on 2026-09-17:

- 110 registered worktrees in one clone and 40 in a second, by `git worktree list`. The first clone
  read 107 earlier the same day, so treat these as a shape rather than a level.
- 0.86 GB for a single worktree's `.venv`, by `Get-ChildItem <path>/.venv -Recurse -File -Force`
  piped into `Measure-Object -Property Length -Sum`.
- 63.36 GB across every worktree directory on the machine, by `du -sb`. Dependency environments were
  19.66 GB of that total, or 31 percent.
- 18.75 GB across 322,826 files in the agent scratchpad directories, by `Get-ChildItem -Recurse`.

[Pruning](PRUNING.md) is the sweep that clears them. `prune-merged.ps1` defaults to a dry run, so
reading its decisions costs nothing and is the cheapest habit to start with.

---

## Rescuing work already in the primary

Use `rescue.ps1` to move unfinished work out of the shared primary when the gate blocks further
edits.

Name the destination worktree:

```powershell
pwsh -NoProfile -File scripts/worktree/rescue.ps1 -Name alerts-fix
```

The script stashes primary changes, creates a worktree, and applies the stash there by object name.
Four details preserve the work:

- `--include-untracked`. Without it, untracked files stay behind in the primary. The new worktree
  then recreates them: two diverging copies, with no indication which one you are editing.
- **The new branch is cut from the primary's *current* commit**, not from the trunk, so the stash
  applies cleanly. This is the one case where the fetched-remote-tip rule above is deliberately not
  applied -- a rescue that conflicts is a rescue that failed.
- **The entry is named, never taken off the top.** The push carries a per-run token, the script reads
  the entry's object name back, and the restore is `git stash apply <sha>`. Building the worktree
  takes minutes, and `stash@{0}` by then may be a peer's.
- The stash is the safety net, and the recovery path is printed at the moment of failure. If the
  restore fails, `finally` prints the object name and the commands to inspect and apply it. Mid-panic
  is not when someone opens a document.

If the primary is clean, the script reports nothing to rescue and suggests `new.ps1`. It creates no
empty worktree.

### Known defect: `rescue.ps1` pops the stack by position

**RETIRED 2026-09-17. Fixed in #119, which landed after #118 wrote the text below.** The script now
pins the entry it pushed and restores it by object name. Both pops are gone: the one it ran, and the
one it printed.

`tests/test_the_rescue_names_the_stash_entry_it_pushed.py` holds the fixture. Its mutation control
reverts the restore to a bare pop and requires the case to go red, so the claim is falsifiable.

Two constraints shaped it. `git stash drop` refuses an object name -- `is not a stash reference` --
so a drop must resolve the SHA back to a `stash@{n}` first. And `git stash create` avoids the race
but cannot capture untracked files, which is why this command exists.

Kept rather than deleted, per the rule that retired text stays with its reason. A reader who sees
only a removal cannot tell whether the defect was fixed or the claim was wrong.

The retired text follows.

Read at `6eb6be0`, both of the script's pops are bare. It pushes with a unique `-m` tag, runs
`new.ps1` as a child process, then pops whatever now sits on top.

Its `finally` block prints the same shape: find your entry in `stash list` by its message, then
`git stash pop`. The stack is shared, so those are two different entries whenever a peer stashed in
between.

The fix is to resolve the pushed entry to a SHA and apply that SHA, which is what
[the shared-stack row](#what-a-worktree-does-not-isolate) asks of every other caller. It is filed
and not yet made.

Until it lands, run `rescue.ps1` when no peer session is mid-stash, and read the message on the
entry before you accept the result.

---

## What actually stops the failure

Three mechanisms address primary branch changes. Only the gate prevents them:

| Role | Script | What it does |
|---|---|---|
| **Prevention** | `scripts/hooks/worktree_gate.ps1` | Refuses the git verbs that would swap or discard the primary's tree, before the tool call runs. It reads command strings, so a script or a shell redirect is invisible to it, and it fails open |
| **Repair** | `scripts/worktree/worktree-selfheal.ps1` | Restores the primary when its HEAD has drifted and the tree is clean. On a dirty tree it declines and touches nothing |
| **Detection** | the home-branch record | Covers a **linked worktree** that drifted, not the primary -- so it does not see the failure above. Warn-only, and [wrong by design](#the-sidecar-home-branch-record-is-wrong-by-design) |

## Restoring the primary

`restore-primary.ps1` returns the shared primary to its home branch after a checkout or detached
HEAD replaced peers' files. The gate blocks ordinary tree-swapping git commands there.

A session may repair the primary but must not take it over.

Preview the switch with `-WhatIf`:

```powershell
pwsh -NoProfile -File scripts/worktree/restore-primary.ps1
pwsh -NoProfile -File scripts/worktree/restore-primary.ps1 -Branch main
pwsh -NoProfile -File scripts/worktree/restore-primary.ps1 -WhatIf
```

The script chooses the home branch in this order:

1. `-Branch`, for this run only
2. `git config <prefix>.homeBranch`
3. the local branch matching the configured trunk (`origin/main` -> `main` )
4. `main`, then `master`

Step 3 supports trunks with other names using the shared config source. It avoids maintaining a
second list of branch defaults.

`worktree-selfheal.ps1` lacks step 3. It tries the config key, then `main`, then `master`.

If a primary drifts from `develop` and `main` exists, the unattended backstop can wrongly switch it
to `main` at session start.

For a non-`main` trunk, save the home branch once so both scripts agree:

```powershell
git -C <primary> config <prefix>.homeBranch <your-trunk>
```

The script refuses a dirty primary and points to `rescue.ps1`. Switching could move or lose
someone's uncommitted work, and the script cannot identify its owner.

`-Force` skips the script's dirty check only. Its underlying `git checkout` uses neither `--force`
nor `-m`.

Git still refuses if modified tracked files differ across branches; neither path discards changes.
Use `rescue.ps1` to move that work first.

### The SessionStart backstop, and the half-failed auto-worktree

`install-selfheal.ps1` wires `worktree-selfheal.ps1` as an unattended `SessionStart` repair hook.

On Windows, automatic worktree creation can move the primary's `HEAD` to a session branch while
leaving an empty stub. See
[anthropics/claude-code#76590](https://github.com/anthropics/claude-code/issues/76590).

The backstop handles each state as follows:

| Situation | Action |
|---|---|
| A governed primary has drifted off its home branch **and its tree is clean** | Switch it back, and **say so** in the session's context. A silent repair is indistinguishable from nothing having happened. |
| A governed primary has drifted **and its tree is dirty** | **Touch nothing, and say why.** Uncommitted work is never at risk from this hook -- but the decline is reported, not silent: the checkout stays on the wrong branch until a person commits, stashes or rescues that work, and a silent decline reads exactly like a primary that was fine. |
| A governed primary is on a **detached** HEAD, or has no resolvable home branch | Nothing, silently. Neither state says which branch it was meant to be on, and switching a shared checkout onto a guess is worse than leaving it. |
| This session's cwd is under `<primary>/.claude/worktrees/<name>` with **no `.git` there** | Report it as a ghost stub and tell the model to create a real worktree before editing. A real linked worktree has a `.git` **file** pointing at its private git directory; a half-failed stub has nothing there at all. That single test separates them. |
| This session's own linked worktree is on a different branch from its recorded home | **Warn only.** Never auto-switch a linked worktree under the session standing in it. |

The hook's only safety check is its dirty-tree refusal. The doctor requires a reasoned refusal on a
dirty, drifted fixture; a repair produces `RED`.

A clean fixture cannot prove that guard exists.

Every error path exits 0 silently. The installed hook is self-contained, duplicating
`scripts/coord/_common.ps1` rather than loading helpers from a working tree.

That keeps branch switches from removing its dependencies; a missing hook would also fail silently.

Both installers use the same fixed allowlist, `~/.claude/hooks/ccx-gate.repos.txt`. The backstop
and `PreToolUse` gate read it.

Earlier installers kept separate files: one rewrote its list, while the other only created a missing
copy. Changes did not propagate between them.

Uninstalling the gate could leave the backstop active and able to switch the shared primary.

Deleting the shared file disables both controls immediately, including in running sessions.

### The sidecar home-branch record is wrong by design

`new.ps1` records home in `<git-common-dir>/worktrees/<id>/<prefix>-home-branch`, inside that
worktree's private git directory. The drift detector reads it; branch changes cannot move it or
expose another worktree's value.

The record preserves the creation branch and never updates after intentional branch changes. The
detector must only warn; automatic repair could replace a live session's files.

During the audit, most live worktrees differed from their records. Creation and first-sighting
bootstrap both wrote records, but neither updated them.

The suggested repair would have moved sessions off their actual branches. Apply these rules:

- Prefer the authoritative source. `git worktree list --porcelain` needs no sidecar at all. Use the
  record only for the question it can answer.
- Treat a mismatch as a question, never a verdict. The hook warns and names both branches; the human
  decides.
- Never print a destructive remediation command from a detector you have not proven correct. The
  warning tells you to commit or stash first, and to run the switch yourself from a plain terminal.

Take the commit. Those are the hook's words, and a stash lands on the stack
[every worktree shares](#what-a-worktree-does-not-isolate).

When no record exists, the backstop records the worktree's current branch. That bootstrap can race
the harness's session setup.

If bootstrap runs before the harness switches branches, it records the pre-setup branch. Every later
start then repeats a stale mismatch warning.

Measured here on 2026-08-05: creation at 09:21:50, record at 09:21:54, and session-branch switch at
09:23:10. The record became stale after 76 seconds; no hijack occurred.

The record alone cannot distinguish setup from hijacking. Check the worktree reflog for a branch
change caused by an agent tool call before interpreting the warning.

`<prefix>.homeBranch` configures the primary's home for restore and selfheal. `<prefix>-home-branch`
records each worktree's creation branch.

Both derive their names from `prefix`, preventing separate renames from splitting the convention.

---

## Removing a worktree

Remove a finished worktree while preserving a route back to its commits.

Run from any checkout except the one you are removing:

```powershell
pwsh -NoProfile -File scripts/worktree/remove.ps1 -Name alerts
pwsh -NoProfile -File scripts/worktree/remove.ps1 -Name alerts -DeleteBranch
pwsh -NoProfile -File scripts/worktree/remove.ps1 -Name alerts -Force    # discard tracked changes too
```

The script prints the tip before deleting the worktree. With `-DeleteBranch`, it then asks git to
delete the branch using `-d`.

The script refuses if you stand inside the target worktree. Its message explains that location error
before git attempts removal.

It also refuses a worktree that contains another registered worktree, and names each one. `-Force`
does not override that. Remove the nested worktrees first. See
[Two layouts](#two-layouts-coexist-and-only-one-has-scripted-teardown).

Uncommitted tracked changes block removal unless you pass `-Force`. Untracked dependencies, build
output, and scratch databases do not block it.

**Removal deletes untracked files permanently.** Every path uses `git worktree remove --force`,
even without the script's `-Force` flag.

Inspect `.env`, databases, and scratch files before removal. Git never stored them, so neither
reflog nor `fsck` can recover them.

> The automatic reaper blocks on untracked files. Manual `remove.ps1` assumes you inspected those
> files and judged them disposable; keep this stricter rule for unattended cleanup.

### Reference the tip before anything is destroyed

Deleting a worktree and its branch can leave commits in no ref or reflog. The interface then offers
no evidence that the work existed.

Resolve and print the tip before deleting anything. With `-DeleteBranch`, save it in a keep-ref
before removing the branch:

```text
List them:    git for-each-ref refs/<prefix>/removed/
Recover one:  git branch <branch-that-was-deleted> refs/<prefix>/removed/<name>
Drop one:     git update-ref -d refs/<prefix>/removed/<name>
```

The keep-ref uses directory `-Name`, while deletion uses the worktree's actual branch. Recovery
must preserve that distinction.

`new.ps1 -Name my-task -Branch feature/my-task` gives them different names. Use the deleted branch
name printed by `remove.ps1` when restoring it.

The keep-ref preserves commit recovery past the next `gc`.

### `git branch -d` refusing is a signal

`git branch -d` may refuse work merged into remote trunk while local trunk lags. Using `-D` for that
reason bypasses git's protection against losing commits.

`remove.ps1` always uses `-d`. On refusal it preserves the branch, prints git's reason verbatim and
the tip again, then offers the forcing command.

It deletes the worktree's actual branch, not its directory `-Name`. Namespaced branches work with
`new.ps1 -Name my-task -Branch feature/my-task`, though directory names cannot contain `/`.

Deleting `my-task` in that example gives *branch not found*. The script now relays git's reason
instead of claiming the branch contains unique commits.

That old diagnosis sent users searching for nonexistent commits while the actual namespaced branch
remained after apparent cleanup.

A detached worktree has no branch to delete. The script reports that state without guessing from the
directory name.

### Never `git worktree prune` as cleanup

`remove.ps1` does not run `git worktree prune`. Prune can deregister worktrees on disconnected
drives, unmounted volumes, or temporarily missing nested paths.

`git worktree remove` already deregisters its own target.

Removal can also deregister a worktree before failing to delete its directory. Follow
[Pruning](PRUNING.md) to recover that leftover folder.

For bulk cleanup, `prune-merged.ps1` defaults to a dry run. It requires merged, clean, unoccupied
worktrees; occupancy may veto removal but never authorize it.

---

## Two layouts coexist, and only one has scripted teardown

Both sibling and nested worktrees were live together in the source project:

| Layout | Path | Created by | Torn down by |
|---|---|---|---|
| **sibling** (default) | `<parent-of-primary>/<primary-leaf>-<name>` | `new.ps1` / `spawn.ps1` / `rescue.ps1` | `remove.ps1`, `prune-merged.ps1` |
| **nested** | `<primary>/.claude/worktrees/<name>` | the harness itself -- and these scripts too, under `worktreeLayout: nested` | `remove.ps1` only, and only for one you named |

`worktreeLayout` selects where `new.ps1`, `spawn.ps1`, and `rescue.ps1` create worktrees. Setting
`nested` gives them the same layout the harness uses.

`Test-CcxHarnessWorktreePath` excludes `.claude/worktrees/` paths from the gate and reaper.
`remove.ps1` never calls it; under `nested`, `remove.ps1 -Name x` removes that named nested
worktree.

`remove.ps1` refuses a target that contains another registered worktree, under either layout. It
names each one, exits non-zero, and `-Force` does not override it. It uses the reaper's own check,
`Get-NestedWorktrees` in `scripts/coord/occupancy.ps1`.

The rule is containment, not path shape. A `.claude/worktrees/x` with nothing inside it is still
removed, so the `nested` layout keeps its teardown.

The target must be a registered worktree first. `-Name .` and `-Name ..` pass the name pattern,
and under `nested` they resolve to `.claude/worktrees` and `.claude`, which hold every harness
worktree. `remove.ps1` refuses both before the nested check runs.

The refusal prints the commands that clear it, deepest first. `git worktree remove` without
`--force` refuses modified or untracked files but deletes ignored ones. Where a child is ignored
inside its parent, removing the parent first would delete the child.

A nested worktree gets a command only if removing it loses nothing the script can read. Otherwise
it gets **NO COMMAND** and a line to look with first:

| It holds | What plain `git worktree remove` does | The line to look with |
|---|---|---|
| Changed or untracked files | Exits 128, and the next try is `--force`. An untracked file that `status.showUntrackedFiles=no` hides, it deletes. | `git -C '<path>' status --untracked-files=normal --ignored` |
| An edit to a file flagged skip-worktree or assume-unchanged | Deletes it. `git status` does not check those files. | The same `status` line, which cannot show them. The refusal names up to three paths instead. |
| Ignored files | Deletes them without asking. This repository ignores `*.local.*`, so a seat's `.claude/seat.local.txt` counts. | the same `status` line |
| Commits on a detached HEAD that no branch, tag or other ref holds | Deletes the last thing pointing at them, so gc can collect them. | `git -C '<primary>' log --oneline <sha> --not --exclude=refs/stash --glob='refs/*'` |
| Commits only its HEAD reflog holds, such as one left behind on a detached HEAD | Deletes that reflog. | `git -C '<path>' reflog` |
| A checked-out submodule | Exits 128 whether or not the submodule holds anything, and the next try is `--force`. That deletes the submodule's repository, which lives in this worktree's admin directory. | `git -C '<path>' submodule foreach --recursive git log --oneline HEAD --branches --not --remotes` |
| Files, where git calls it prunable because its `.git` file is gone | Exits 128 with or without `--force`. `git worktree prune` gets past that, and removing the parent then deletes the files. | `Get-ChildItem -Force -LiteralPath '<path>'`, then `git -C '<primary>' worktree repair`, which deletes nothing, and a re-run |

Every path in a printed command sits in single quotes, which PowerShell expands nothing inside.
Until 2026-09-23 they sat in double quotes. There a `$name` in a path expanded, and the command ran
on a different path, which could be another clone's worktree.

**Nearly every worktree a session has used holds an ignored file, so nearly every one gets NO
COMMAND.** A cache, a seat marker and a local settings file all count. That is deliberate: the script
cannot tell a cache from a local database. The refusal names up to three paths so you can.

The check lists every file, through `Read-WorktreeStatus` in `scripts/coord/occupancy.ps1`. The
`status` line uses `normal`, so a cache directory reads as one line. Both override the setting,
which plain `git status` obeys, and plain `git status` never shows ignored files.

The refs are read with `git rev-list --count <sha> --not --exclude=refs/stash --glob="refs/*"`.
`git branch --contains` cannot see a tag. `--not --all` adds every worktree's HEAD, this one's too,
so it never finds a commit lost. `refs/stash` is left out because every worktree shares it.

The reflog read subtracts every ref's own reflog, because those outlive the removal. So a commit
amended or rebased away on a branch does not count: the branch's reflog still holds it. `--reflog`
cannot stand in, because it adds every worktree's HEAD reflog, this one's included.

Nor does a parent whose child holds work get a command: removing the parent takes the child. A
registered worktree nested in another is not counted as the parent's file. It gets its own row.

**What it does not read.** A nested worktree whose directory is already gone has its HEAD checked,
but not its HEAD reflog. And the check is a reading taken when the refusal prints. Anything written
into a nested worktree after that is not covered, and the refusal says so beside the commands.

**RETRACTED 2026-09-23.** This section said "A printed command still deletes ignored files,
untracked files hidden by `status.showUntrackedFiles=no`, and commits on a detached HEAD that no
branch holds". It went on: "The refusal says so. Found by the third review round, 2026-09-22, and
not fixed".

The reading, on git 2.55.0.windows.5. Cases in
`tests/test_remove_never_deletes_a_nested_worktree.py` build each of those nested worktrees, run
the printed commands, and check the work survived. Run that file, as it stood at `8f2e366`, against
an export of the script before the fix:

```bash
git archive a58981d | tar -x -C <scratch>
git show 8f2e366:tests/test_remove_never_deletes_a_nested_worktree.py > <scratch>/tests/test_remove_never_deletes_a_nested_worktree.py
cd <scratch> && python -m pytest -q tests/test_remove_never_deletes_a_nested_worktree.py
```

It returns `6 failed, 17 passed, 11 subtests passed`. The six are the five rows above and the
target's own guard, which now refuses when `git status` on the target fails. Each fails on the loss
itself. At `8f2e366` the same file returns
`23 passed, 11 subtests passed`.

`3d778a0` closed the three the retracted text named. Review round one then found the reflog and
skip-worktree rows and the target guard. Against an export of `fd7028f`, just before that round's
fix, the same file returns `3 failed, 20 passed, 11 subtests passed`.

The controls pass at all three. A clean nested worktree gets a command that runs. So does a detached
one whose commit a tag, a keep-ref or a remote-tracking ref holds, and one whose commit was amended
away on its branch.

**The nested row's "only for one you named" was false until 2026-09-22.** `remove.ps1` also deleted
any registered worktree inside its target, exited 0, and left that worktree registered with no
directory. This section did not say so.

Measured at `05eb4a7` with git 2.55.0.windows.5, under `sibling`: removing `P-work` also deleted
`P-work/.claude/worktrees/h`, and `h` stayed registered as prunable. The instrument is
`tests/test_remove_never_deletes_a_nested_worktree.py`.

The cause is the guard, not ignoring. `remove.ps1` read the parent's `git status` and dropped every
`??` line, then always passed `--force`. With no ignore rule the parent reads `?? .claude/`, the
filter drops it, and the loss happens all the same. The test's fixture is that case.

Run it against the old script from an export:

```bash
git archive 05eb4a7 | tar -x -C <scratch>
git show a58981d:tests/test_remove_never_deletes_a_nested_worktree.py > <scratch>/tests/test_remove_never_deletes_a_nested_worktree.py
cd <scratch> && python -m pytest -q tests/test_remove_never_deletes_a_nested_worktree.py
```

It returns `10 failed, 3 passed, 2 subtests passed`. Every refusal case fails. The two controls pass,
so the fix does not refuse everything.

**The second line read `cp tests/test_remove_never_deletes_a_nested_worktree.py <scratch>/tests/`
until 2026-09-23.** The file has grown since, so the copy on the trunk returns a different count.
The count is for the file at `a58981d`, re-measured that day with the line above.

The `.` and `..` case fails only in its two `nested` subtests, and only on the missing refusal
message. At `05eb4a7` that typo already failed safely, with git exit 128. The hazard arrived with the
first cut of this check.

It sees only worktrees registered to this repository. A checkout of another repository inside the
target is not in that list, and `remove.ps1` still deletes it.

One helper handles two different requirements:

- A gate protecting the primary must *not* govern a nested worktree. Its path starts with primary,
  but its git commands change only its own tree. Governing it refused the most ordinary thing a
  session does.
- A reaper must *never* remove one. Some nested paths also start with `<primary>-`, misleading a
  sibling-prefix scan. Removing one can destroy a live session's checkout.

Two related path rules also apply:

- "Sibling" is not a prefix match. `<primary>-work/x` has the prefix but is no sibling.
  `Test-CcxSiblingWorktreePath` requires the same parent directory, a leaf of exactly
  `<primary-leaf>-<something>`, and not a harness worktree.

  Even then it only *looks* like ours: removal turns on occupancy, cleanliness and merge state.
- A nested checkout reads as untracked in its parent, or not at all where ignored. A guard that
  skips untracked files passes the parent, and a `--force` removal of it deletes both, leaving the
  nested worktree registered with no directory. Both removal scripts refuse such a parent.

  **That bullet began "A nested checkout is git-ignored inside its parent. The parent therefore reads
  perfectly clean" until 2026-09-22.** Ignoring is one case, not the cause. Without an ignore rule
  the parent reads `?? .claude/`, which `remove.ps1`'s guard dropped.

### A wrong-cwd run must refuse loudly, never green no-op

A sweep once ran from a linked worktree, found no siblings, and exited 0. The apparent all-clear hid
that it had searched from the wrong root.

Resolve primary through the first `git worktree list --porcelain` entry, as `Get-CcxPrimaryRoot`
does. Do not derive it from `$PSScriptRoot/../..`.

`prune-merged.ps1` now exits nonzero with
`REFUSED: this is a linked worktree, not the primary checkout` and names both paths.

`remove.ps1` likewise refuses when invoked inside its target.

`Get-CcxWorktreePath` in `scripts/coord/_common.ps1` owns the layout formula. Four scripts once
duplicated it and a fifth pattern-matched it, letting rules drift apart.

---

## What a worktree does *not* isolate

Worktrees separate files, branches, indexes, and setup-hook dependency environments. These six
resources still need shared rules:

| Shared thing | Why | What to do |
|---|---|---|
| **The git stash stack** | One stack lives in the shared git directory, so every worktree sees every session's entries. A bare `pop` takes whichever was pushed last: one session restores another's work into its own tree, and neither notices. | Set work aside with a WIP commit. Where you must stash, use `git stash push -m "<tag>"`, read the SHA back with `git stash list --format='%H %gs'`, and restore with `git stash apply <sha>`. Recovery needs that SHA. |
| **Coordination state** | It lives at `<git-common-dir>/<prefix>-coord`, which is identical across every worktree of a clone (that is the point -- a claim taken in one worktree must be visible in another). | Its corollary: **state outlives the worktree.** Remove a worktree and the claims it took are still there. Release on *evidence* -- the directory is gone **and** deregistered -- never on a timer. See [Coordination](COORDINATION.md). |
| **The git hooks directory** | One `commit-msg` / `pre-push` set lives in the shared git directory and governs every worktree of that clone at once. | Install once per clone, not per worktree. It also sees every write route, because it inspects the tree at commit time rather than a tool call. |
| **`.git/config`** | Written by `git worktree add`. | Already handled by the mutex above. |
| **The AI coding assistant's project memory** | It lives outside the repository, in one directory shared by every session on the machine. Last write wins. | Reads are fine. Coordinate **writes** explicitly, or let exactly one session own them. |
| **`.claude/` mostly does not reach a new worktree** | A project-scoped settings file is a creation-time snapshot at best, lives on one branch, and is commonly git-ignored. Anything *tracked* under `.claude/` is checked out like any other file; what is git-ignored cannot arrive at all. | Wire cross-session hooks at **user** scope, with the script installed outside every working tree. See [Install](INSTALL.md). |

Ports, development databases, Redis keyspaces, package caches, and git-ignored `.env` files also
remain outside these checks. See [Limits and requirements](LIMITS.md).

### A dropped stash is recoverable until the next `gc`, and only from its SHA

Nothing detects a wrong stash pop. The stack records no worktree, so a popped entry leaves no trace
of where it came from or where it went.

**The row above read "record the SHA it prints" and "`git stash drop` does not undo" until
2026-09-17. Both were false.** Measured on git 2.55.0.windows.5, in a throwaway `git init`
repository rather than against this machine's shared stack.

Push prints no SHA, so the published instruction could not be followed. The read-back is a second
command:

```text
$ git stash push -u -m "tag-alpha"
Saved working directory and index state On master: tag-alpha
$ git stash list --format='%H %gs'
a39e73a87b7f2678bb59674f794f21fdc1ece1b7 On master: tag-alpha
```

`grep -c -E '[0-9a-f]{40}'` over that push output returns 0, against 1 over `git rev-parse HEAD` as
a control, so the pattern was live rather than empty.

The drop leaves the commit object in place, and `git stash store` puts the entry back:

```text
$ git stash drop
Dropped refs/stash@{0} (a39e73a87b7f2678bb59674f794f21fdc1ece1b7)
$ git cat-file -t a39e73a87b7f2678bb59674f794f21fdc1ece1b7
commit
$ git stash store -m "tag-alpha" a39e73a87b7f2678bb59674f794f21fdc1ece1b7
$ git stash list
stash@{0}: tag-alpha
```

`git stash apply` then restored the tracked edit and the untracked file both.

**Recovery needs three things, and the session that lost the work holds none of them.**

| What recovery needs | Why the losing session lacks it |
|---|---|
| The SHA | `git stash push` prints none. The `Dropped ... (<sha>)` line prints in whoever ran the drop, not in you. |
| The object, unpruned | `git reflog expire --expire-unreachable=now --all` then `git gc --prune=now` took it. `cat-file` exited 128 and `stash store` refused it as *not a stash-like commit*. |
| A reason to look | The pop is silent in your tree. You find out when something is missing, which may be after the window has shut. |

`git fsck --unreachable` finds the commit without a recorded SHA. It names every unreachable object
in the repository, so it identifies the entry only where there is one candidate.

A raw object name cannot be dropped: `git stash drop <sha>` answers *is not a stash reference*. So a
drop re-resolves `stash@{n}` at drop time, and that is the step where it takes a peer's entry.

---

## Known limits

KORUS needs Claude Code for Desktop and vendored scripts in the governed repository.
[Limits and requirements](LIMITS.md) details those needs; these platform limits affect worktree
commands:

- PowerShell 7, Windows-first. Most scripts are `#Requires -Version 7.3` and were exercised on
  Windows. Since `$env:USERPROFILE` is Windows-only, home lookups fall back safely to the .NET
  accessor. Windows remains the tested platform.

  `worktree-selfheal.ps1` and its installer declare `-Version 7`, not 7.3. That is why 7.0-7.2 is
  worse than unsupported: the backstop installs there and the gates do not.
- Paths fold case on Windows and macOS, not on a case-sensitive filesystem. Use the folded form for
  comparison only, never for git, the filesystem, or a human. One silent gate failure on Linux CI: a
  lower-cased path went to `git -C`, git failed, and the rule fell through to allow.
- The harness's session record format is a vendor contract. The liveness fence behind the reaper
  reads per-session records the harness writes; that schema can change without notice. The fence
  then reports itself unavailable and nothing is pruned -- the intended failure direction, and an
  outage.
- Session listings do not see every session kind. Sessions relocated into a worktree file their
  transcript under a different key and drop out of the list of the window they were born in.
  `sessions.ps1` is how you find them, and `-Rehome` is how you put one back:

  ```powershell
  pwsh -NoProfile -File scripts/worktree/sessions.ps1                          # list
  pwsh -NoProfile -File scripts/worktree/sessions.ps1 -Id <id-prefix>          # one session
  pwsh -NoProfile -File scripts/worktree/sessions.ps1 -Rehome <id> -WhatIf     # preview the move
  pwsh -NoProfile -File scripts/worktree/sessions.ps1 -Rehome <id>             # move it back
  ```

  A bare invocation only ever lists. `-Rehome` is the one action that moves anything, and it honours
  `-WhatIf`.
- Nothing here can prove a session is gone. There is no heartbeat. Every occupancy verdict is the
  absence of a veto, not a permission.

Run `pwsh -NoProfile -File bin/ccx-doctor.ps1` to check which guards are installed and enforcing on
this machine.

The [shared-state map](CONCEPTS.md#g01) separates each worktree from the records the clone shares.
