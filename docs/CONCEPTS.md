# Concepts

## TLDR/BLUF

Five rules govern concurrent sessions: one checkout each, shared coordination state, liveness checks
that can only veto, exclusive file creation, and no expiry timers.

These rules come from failures observed while sessions worked in parallel. A single-session workflow
does not need this coordination.

Use [Quickstart](QUICKSTART.md) to install, [Hooks](HOOKS.md) to connect controls to events, and
[Worktrees](WORKTREES.md) for daily commands.

---

The system has three layers:

<!-- no-copy -->
```text
  worktree-per-session      one checkout per concurrent session, so two sessions
                            cannot clobber each other's working tree
        |
  a shared state root       one directory every worktree of a clone resolves
                            identically, holding claims, locks, allocations
        |
  the liveness fence        the single answer to "is that session still there",
                            which may only ever say NO to an action
```

Hooks, pruning, allocation, and announcements all use these layers.

Each checkout has separate files and an index. Worktrees in one clone resolve the same coordination root.

<a id="g01"></a>

<figure class="explain-figure">
<picture>
<source media="(max-width: 1100px)" srcset="/assets/diagrams/g01-shared-state-mobile.svg">
<img src="/assets/diagrams/g01-shared-state.svg" alt="Separate worktree files connect to one shared coordination root." loading="lazy" width="777" height="427">
</picture>
<figcaption>One clone shares coordination state across its primary and linked worktrees. Branches separate the work; the common directory keeps claims visible to peers. <a href="/assets/diagrams/g01-shared-state.drawio">Editable diagram</a>.</figcaption>
</figure>

---

## 1. Worktree-per-session

A git worktree shares history, remotes, and objects with its clone, but has its own directory,
branch, and index. Sharing one checkout lets a session's `git checkout` replace another's files
mid-edit.

Give each session a worktree and each unit of work a branch.

### Primary and linked

The primary is the clone's main checkout, listed first by `git worktree list --porcelain`.
`Get-CcxPrimaryRoot` in
[`_common.ps1`](https://claude-multisession.pages.dev/scripts/coord/_common.ps1) uses that entry.

> Four older copies used `$PSScriptRoot/../..`, which finds the script's checkout. From a linked
> worktree, they created siblings of that worktree, beyond the primary-based pruner's search.

> Always anchor layout on the primary. Tooling must behave the same from every checkout.

### Two layouts, and both are real

| Layout | Path | Who creates it |
|---|---|---|
| `sibling` (default) | `<parent-of-primary>/<primary-leaf>-<name>` | this tooling, via `scripts/worktree/new.ps1` |
| `nested` | `<primary>/.claude/worktrees/<name>` | the client itself, and this tooling if you configure it |

`worktreeLayout` in `ccx.config.json` selects the created layout; both layouts can already exist on
a machine. `Get-CcxWorktreePath` now owns the formula previously copied into four scripts and
matched in a fifth.

> A git-ignored nested checkout leaves its parent looking clean. Removing the parent with
> `git worktree remove --force` deletes both and leaves the child registered without a directory.

> One wrong-directory sweep printed "no sibling worktrees to consider" and exited 0, hiding the
> wrong search location.

> The gate and reaper exclude `.claude/worktrees/` paths through `Test-CcxHarnessWorktreePath`,
> regardless of layout. The older blanket rule overstated this protection.

> Manual `remove.ps1` can remove a named nested worktree. See
> [the removal exception](WORKTREES.md#two-layouts-coexist-and-only-one-has-scripted-teardown).

> The primary gate must not govern nested worktrees, since their git commands change only their own
> files. The reaper must never remove them while sessions occupy them.

### "Sibling" is a structure, not a string prefix

`Test-CcxSiblingWorktreePath` requires the primary's parent directory, an exact
`<primary-leaf>-<something>` leaf, and exclusion of nested worktrees.

> A `<primary>-*` scan included `<primary>-pins/.claude/worktrees/x` and deleted that nested
> worktree and branch. Only nesting under primary had been tested.

> Those cases survived because `<primary>/` differs from `<primary>-`. Match directory structure
> and exclude containment explicitly instead of relying on that punctuation.

Those three checks identify a candidate path only. Occupancy in section 3, cleanliness, and merge
state determine whether it may be touched.

### What a worktree does *not* isolate

Worktrees separate files, branches, indexes, and build environments. Three resources remain shared:

| Shared thing | Consequence |
|---|---|
| the git directory | one `.git/config.lock`; concurrent `git worktree add` races it, which is why creation is serialised under a cross-session mutex |
| the git hooks directory | one `pre-commit` / `commit-msg` / `pre-push` set governs **every** worktree at once, and sees every write route into the repo |
| the AI coding assistant's own project memory | it lives outside the repo, one directory per machine, and last write wins. Reads are fine; coordinate writes, or let exactly one session own them |

Project `.claude/settings.json` files are often missing, git-ignored, or stale creation-time copies.
Install coordination hooks at user scope; see [Install](INSTALL.md).

`setupHook` builds the environment using `CCX_WORKTREE_PATH`, `CCX_WORKTREE_NAME`,
`CCX_PRIMARY_ROOT`, and `CCX_BASE_REF`. See the
[setup example](https://claude-multisession.pages.dev/examples/worktree-setup.ps1.example);
`new.ps1` itself has no language-specific setup.

### A worktree narrows the branch, not the file set

> Not yet adopted. No seat uses a narrowed checkout, and nothing described here is installed. This
> proposal comes from an outside essay and remains unmeasured here.

A worktree selects a branch but contains the entire repository. A Watchdog who only reads check logs
still has source files available to edit.

`git sparse-checkout` limits which files a worktree contains while keeping its branch. A seat can
then lack files its job never needs.

The idea comes from an Every team's essay about an operations folder that "has no app code, so it
cannot accidentally modify production code". It reports one operator over three months, with few
instrumented numbers.

Treat the proposal as a hypothesis.

KORUS's two-repository split protects privacy: `roles/COMMON.md` keeps material that "must never
reach the public repository" private. Narrowing would instead limit what an agent can access to
change.

These counts use `1b6b7fc`, the commit before this section existed:

```powershell
(git grep -l -i "no app code" 1b6b7fc)     | Measure-Object -Line   # 0 files
(git grep -l -i "cannot modify" 1b6b7fc)   | Measure-Object -Line   # 0 files
(git grep -l -i "sparse-checkout" 1b6b7fc) | Measure-Object -Line   # 1 file, HOOKS.md, unrelated
```

> Keep those queries pinned to the commit. Against current files, each finds one extra file: this
> section, which includes the search phrases.

> The first attempted count already included its own queries. Record the reference with any
> measurement.

Four prohibition methods leave different amounts of evidence:

| Item | Rule |
| --- | --- |
| Remove the data | Fails legibly. The error is "that file does not exist", which is true and names the real cause. Most evidence. |
| Gate with a hook | Fails with a receipt. The denial is written down, so you can count the rule's false positives afterwards. |
| Remove the tool | Fails, but may misattribute. The error names a cause, and that cause can be the wrong one. |
| A rule in prose | Leaves no trace. Obedience and violation look identical from outside. [`KORUS-BUILD.md`](KORUS-BUILD.md#before-you-open-any-session) states the consequence: "Roles are advisory; the gates are not". |

This orders evidence, not enforcement strength. A written rule may hold, as
[one measurement](WORKER-BRIEF.md#why-a-prohibition-rather-than-ask-if-you-are-unsure) shows,
without leaving a record of compliance.

> Removing data and removing tools can both remove a capability, but their failures differ. The
> essay treats them together.

> With missing data, the tool can truthfully report that the path does not exist. With a missing or
> broken tool, errors describe its own failure.

> Readers can mistake those tool errors for facts about the underlying system.

Only the first of these two cases has an artifact in this tree:

| Item | Rule |
| --- | --- |
| `roles/MANAGER.md` section 6a, "the careful, least-privilege tool grant is the broken one" | A command-scoped grant like `PowerShell(pwsh:*)` silently disables the tool. Every command then returns a parse error naming a cause that is not the real one. Nobody could tell from the error. |
| A broken shell validator, reported 2026-09-04, with no artifact in this tree | An oversized environment broke a session's shell validator, so every command failed identically. It concluded "there is no nested-process check" when there was one. **Unmeasured.** `git grep -l -i "nested-process" 1b6b7fc` returns 0 files. |

The nearest measurement concerns false refusals from a cwd-based gate:

| Item | Rule |
| --- | --- |
| The measurement | Over 30 days, **29 percent** of Edit and Write calls by primary-seated sessions wrote into a sibling worktree by absolute path. Those writes were already correct. A directory-keyed gate would have denied every one. |
| Its scope | Writes by sessions sitting in the primary. Not all fleet traffic, and not a per-seat rate. |
| What it actually measures | A cwd-keyed gate, not a sparse checkout. It bounds the cost of narrowing; it is not that cost. |
| The condition it did not vary | The seat. One fleet, one machine, no per-role breakdown. |
| Source of record | [Tips and tricks](TIPS-AND-TRICKS.md#4-when-you-write-a-guardrail) |

No one has measured each seat's actual write paths. Sparse-checkout patterns would therefore be
guesses that could make needed files unavailable during correct work.

> Publish a per-seat census of Edit and Write targets over a fixed window first. Adopt narrowing for
> one seat only if its write set stays a stable subset.

> Before installing anything, compare its measured denial rate with the 29 percent above.

---

## 2. The shared state root

All cross-session coordination state uses this location:

<!-- no-copy -->
```text
<git-common-dir>/<prefix>-coord/
    alloc/              one file per allocated sequence number
    claims/             one file per claimed unit of work
    locks/              one file per held short-lived mutex
    announce/           per-session announce bookkeeping, and the OFF kill switch
    gate-unresolved/    receipts from a collision check that could not resolve
    overlap-cache.json  the overlap detector's cache
```

`Get-CcxStateRoot` and Python `state_root()` in
[`_ccxconfig.py`](https://claude-multisession.pages.dev/scripts/hooks/_ccxconfig.py) must return
identical paths. Each language reads records written by the other.

The git common directory provides three properties:

1. Identical across worktrees. Every linked worktree of a clone resolves the same git-common-dir, so
   a claim taken in one worktree is visible to a session in another. A state root under the
   *working* tree would give each worktree its own private, useless copy.
2. Isolated per clone. Two clones of the same project on one machine do not share it, so their locks
   and claims cannot collide. A state root under the home directory would merge them.
3. Uncommittable. It lives inside the git directory, so no `git add -A` anywhere can sweep
   coordination state into a commit, and no checkout can delete it.

Path resolution must handle both relative output and git failures:

> Five call sites disagreed in two ways. Two omitted `--path-format=absolute`, then joined relative
> `.git` output to the hook process's startup directory.

> Two others ignored exit codes. Git failure yielded an empty path and placed state at the
> filesystem root.

> Always request `--path-format=absolute` and check the exit code. `Invoke-CcxGit` returns `$null`
> for nonzero exits so callers must handle failure.

> Otherwise an empty result can wrongly mean no worktrees, no refs, or repository root `''`.

### The corollary: State outlives the worktree

Claims survive worktree removal because state lives beside the shared object store. Removing the
checkout does not release its keys.

That preserves crash evidence for peers without timers. The reaper releases a claim only after its
full canonical path is both gone and deregistered.

---

## 3. The liveness fence

[`session-registry.ps1`](https://claude-multisession.pages.dev/scripts/coord/session-registry.ps1)
holds the single liveness check. All other controls use it to ask whether a session is still
present.

### It rests on a vendor contract

The client owns the format, location, and lifetime of `<config-root>/sessions/<pid>.json`:

| Field | Type | Meaning |
|---|---|---|
| `pid` | number | OS process id hosting the session, and also the filename |
| `startedAt` | number | unix epoch **milliseconds** at which the session registered |
| `sessionId` | string | uuid; callers may match on a unique prefix |
| `cwd` | string | absolute directory the session was launched in |
| `entrypoint` | string | which surface launched it |
| `kind` | string | interactive, or whatever else the client decides to write |

Discovery includes every `<home>/.claude*` directory containing `sessions`. Several logins can
coexist, but each session is visible only to its owning login.

A renamed field or changed `startedAt` unit makes the fence report "cannot tell" while counts can
stay unchanged. A moved registry directory can instead reduce the count to zero.

The older claim that every schema change zeroes the census was too broad. See
[the discovery limits](LIMITS.md#session-discovery-rests-on-a-vendor-surface-this-project-does-not-own)
.

### It is not a pid check

> Process IDs get reused, and registry records outlive their processes. Checking only that a pid
> exists can mistake a dead session for a live one.

> Do not rely on client `procStart`: it can be missing or use an unexpected form. Its guard returns
> true when uncertain, failing open toward "still alive".

> Read process start time directly and compare it with recorded session registration. A process
> started afterward has reused the ID.

### The five answers, and what each licenses

| State | Meaning | Vetoes a destructive action? |
|---|---|---|
| `LIVE` | pid resolves and its start time is consistent | yes |
| `UNVERIFIED` | pid resolves; the fence could not be evaluated (start time unreadable, no `startedAt`) | yes |
| `UNREADABLE` | the record itself cannot be fenced (no pid, or a non-numeric one) | yes |
| `STALE` | pid resolves but belongs to a different process | no |
| `DEAD` | no such pid | no |
| not found | no record at all | no |

`UNREADABLE` counts as possibly live. It once reported `DEAD`, although a session launched one
second ago can leave the same incomplete record.

Destructive callers wrongly read that state as an empty worktree.

<a id="g02"></a>

<figure class="explain-figure">
<picture>
<source media="(max-width: 1100px)" srcset="/assets/diagrams/g02-liveness-veto-mobile.svg">
<img src="/assets/diagrams/g02-liveness-veto.svg" alt="Unavailable scans refuse removal; visible occupants veto it; no veto grants no permission." loading="lazy" width="777" height="507">
</picture>
<figcaption>Read the availability receipt before interpreting the rows. A missing occupant does not establish that removal is safe. <a href="/assets/diagrams/g02-liveness-veto.drawio">Editable diagram</a>.</figcaption>
</figure>

The diagram concerns destructive actions and held state. Mail uses separate
[expiry rules](#the-rule-is-about-held-state-and-a-message-is-not-held-state).

### Liveness may only veto, never permit

Without heartbeats, event-driven registry records cannot prove abandonment. Liveness can establish
presence only, and every destructive caller must honor that limit.

> A `DEAD`, `STALE`, or missing result once served as permission to delete a worktree. It
> establishes only that no veto was found.

> Liveness must only block destructive actions. `Get-WorktreeOccupants` in `occupancy.ps1` returns
> veto-worthy rows and excludes `DEAD` and `STALE`; document this beside callers.

### Availability is part of the answer, not an absence of one

Both a completed empty scan and a failed scan can return no rows.

> An occupancy check once reported all-clear without reading the registry. It silently skipped
> unparsable records and records missing `cwd`, leaving neither counted.

> Return `RootsExamined`, `RecordsExamined`, `RecordsUnplaceable`, and `UnplaceableFiles` with
> the rows. `Get-WorktreeOccupancy` supplies this receipt.

> `Available` requires at least one registry root, one readable record, and no unplaceable records.
> Destructive callers must print the receipt and refuse when it is false.

An unplaceable record makes the whole fence unavailable. It could belong to the very worktree being
deleted, so no individual worktree can be cleared.

The same uncertainty applies to unreadable claim owners. An empty problem list needs evidence that
its source directory existed and was scanned.

### What the fence cannot see

Document these measured blind spots wherever the fence is used:

| Blind spot | Why |
|---|---|
| a session writing into a worktree **by absolute path** from somewhere else | records carry the cwd a session was *launched* in. Measured on the repo this tooling was developed in, over a month, **29% of the writes made by sessions sitting in the primary** landed in a sibling worktree |
| a cwd recorded as a UNC path or an 8.3 short path | the match is a string compare on the canonicalised path, and neither spelling canonicalises to the worktree's own |
| a session that never registered at all | nothing to read |

The 29% of correct cross-worktree writes require a second, independent non-cwd signal before
deletion; either signal may veto. Primary write gates use target paths because cwd-based rules would
deny that 29%.

The surrounding tools have two more limits:

- The desktop client's `list_sessions` cannot see every session kind: it answers "who can be
  messaged", not "who exists". Only `<config-root>/sessions/<pid>.json` carries every surface.
  Measured at [the two rosters answer different questions](COORDINATION.md#presence-who-is-here).
- Transcript mtime is not liveness. Workflow output can go under a subdirectory while its main transcript stays idle. One verified
  live session reached three times its mtime threshold. Consult the registry and mtime; refuse if either says live.

### One copy of the fence, on purpose

Presence, transcript moves, and worktree pruning share this liveness answer. Their effects differ,
including deletion by `prune-merged.ps1`.

> Keep a safety check in one shared file and dot-source it from every caller. Explain that ownership
> in a comment so future edits do not create drifting copies.

Dependencies run in this order:

<!-- no-copy -->
```text
prune-merged.ps1 / presence.ps1 / sessions.ps1     callers
        |
occupancy.ps1        cwd -> worktree matching, the availability receipt, veto sets
        |
session-registry.ps1 the liveness fence itself
        |
_common.ps1          path comparison, the state root, git plumbing
```

`occupancy.ps1` keeps `ConvertTo-Norm` as a one-line call to `ConvertTo-CcxComparablePath`. That
retains the old interface without duplicating path comparison.

---

## 4. Exclusive-create, never read-modify-write

`alloc.ps1`, `claim.ps1`, and `lock.ps1` protect numbers, units of work, and short critical
sections. All three use atomic file creation:

```powershell
# The failed create IS the mutual exclusion.
$fs = [System.IO.File]::Open(
    $file,
    [System.IO.FileMode]::CreateNew,      # throws IOException if it already exists
    [System.IO.FileAccess]::Write,
    [System.IO.FileShare]::None)
```

> In the source project, 8 concurrent PowerShell writers silently lost 4 of 8 updates to one shared
> file.

> Atomically create a separate file per item instead. If it exists, creation throws and the caller
> moves on.

> The same harness ran 8 allocator processes this way, producing 8 distinct numbers and zero
> collisions.

The users differ in lifetime and collision handling:

| | `alloc.ps1` | `claim.ps1` | `lock.ps1` |
|---|---|---|---|
| Protects | a number in a shared sequence | a unit of work | a critical section |
| File | `alloc/<kind>/<n>.json` | `claims/<key>.json` | `locks/<name>.lock` |
| Lifetime | forever, never reclaimed | until released by hand | seconds |
| On collision | try the next number | report the holder and refuse | retry until timeout, then fail loudly |
| Released by | nothing | the holder, or `-Force` after proving the holder is gone | the caller's `finally` |

Allocated numbers are never reclaimed, even after branches are abandoned. Gaps are harmless; reused
numbers can merge without conflict because the sessions edited different bytes.

### Replacing a file that is itself the lock

A claim file's existence provides ownership. Delete-and-replace updates briefly free its name,
allowing another worktree to take the key.

> `Move-Item -Force` deletes then renames. Across 400 moves, the destination was absent in 2,559 of
> 154,506 polls.

> Write a temporary file, then use `[System.IO.File]::Move($tmp, $file, $true)` for an atomic NTFS
> replacement. The same harness found no missing name in 134,581 polls.

> Replacement can fail transiently when scanners or editors hold the destination: about 13.5% under
> continuous churn. The old note and claim then survive.

> Always clean up the temporary file; it sits in the claim registry.

PowerShell wraps .NET method exceptions in `MethodInvocationException`, so
`catch [System.IO.IOException]` misses `Move` failures. With `$ErrorActionPreference = "Stop"`,
cleanup then fails and leaves a temp file.

The catch is deliberately untyped.

---

## 5. There are no TTLs anywhere, and that is the design

Locks and claims never expire, and no timer reaps them.

An expiry timer can admit a second process while the first still holds the critical section. Slow
operations make that silent double-write especially likely:

| | Failure it prevents | Failure it causes |
|---|---|---|
| TTL | a wedged lock: visible, one command from fixed | a concurrent double-write nobody observes |

On timeout, `Enter-CcxLock` reports the holder and manual override. It retries but never steals,
since no liveness signal can prove abandonment and safely reopen the lock.

`claim.ps1 -List` likewise reports holder liveness instead of using claim age.

### The rule is about held state, and a message is not held state

Messages can expire; locks and claims cannot.

Expiring held state can admit duplicate work. Expiring a message can prevent a stale instruction,
such as a three-day-old "hold the trunk", from being followed.

Broadcasts already
[require a hard expiry or a condition recipients can check](COORDINATION.md#a-broadcast-needs-an-expiry-or-a-recipient-evaluable-predicate)
.

Message expiry still has an unresolved failure: neither recipient nor sender learns that a message
went unread. Like the rejected lock expiry, that failure stays invisible.

On 2026-08-11, the separate [session mail](SESSION-MAIL.md) implementation used a 720-minute mail
TTL, short enough to expire overnight. It now uses 4320 minutes; no script ships here.

The longer lifetime reduces missed messages but does not report them.

> A claim labeled `STALE ~21h` was recommended for release despite its holder committing two minutes
> earlier. That advice would have admitted duplicate work.

> Report the holder's activity. Recommend force-release only when its worktree is provably absent on
> disk; otherwise say "confirm first".

> Failed probes must report `failed`, never `gone`. An unreadable path cannot authorize releasing
> a live claim.

Broadcast notes need in-place correction because claims do not expire:

> `-Take -Note` once accepted and discarded a new note while reporting success. Release-then-retake
> was the only correction, briefly dropping ownership as the stale note kept broadcasting.

> Refresh published records in place, with separate claim and refresh times. Do not require deletion
> to correct their content.

Publish coordination state that gates can consume. Two sessions' prose handover agreement failed
because the collision gate reads git, leaving the edit blocked.

---

## 6. Conventions that make comparisons work

Path, encoding, and timestamp rules keep separate tools comparing the same values.

### Canonicalise before comparing, and fold for comparison only

Only `ConvertTo-CcxComparablePath` and `fold_path()` implement path comparison. They apply
`GetFullPath` or `abspath`, use `/` separators, remove trailing `/`, and lowercase only on
case-insensitive filesystems.

> Four of five old copies skipped canonicalization. `<primary>-work/../<primary>/x.md` then bypassed
> the primary-prefix check.

> Resolve relative paths against the command's cwd from the hook payload. Using the hook process cwd
> once hid `cd ../../.. && git reset --hard` from a nested worktree.

> Another gate passed its lowercased path to `git -C`. On case-sensitive CI, git missed the
> directory and the gate failed open.

> Keep folded paths for comparison only. Use original paths for git, filesystem access, and
> messages.

> Fold case only where the filesystem does. On case-sensitive systems, `/tmp/Primary` and
> `/tmp/primary` are different directories.

Both helpers return `''` instead of throwing on fail-open paths. Callers interpret it as unresolved
and therefore ungoverned; throwing would also allow the call, without explanation.

### A prefix test is not a containment test

`Test-CcxPathUnder` requires `$Path -eq $Root -or $Path.StartsWith("$Root/")`. That slash prevents
sibling `<primary>-<task>` paths from falsely matching primary containment.

When prefix matching is required, explicitly choose the longest prefix.

> A first-match lookup assigned nested sessions to primary because its path prefixes theirs.
> Hash-table order decided which session appeared live on trunk.

> `Get-WorktreeOccupancy` chooses the longest prefix and tests nesting. Destructive callers use
> `Get-WorktreeOccupants -IncludeNested` to include descendants, whose sessions must veto ancestor
> removal.

A roster reports the innermost checkout. A destructive check must also include ancestors, since
`--force` removal of a parent deletes nested worktrees.

### Name folding: The filename is the mutex

`ConvertTo-CcxSafeName` and `safe_name()` reduce text to `[a-z0-9._-]`, collapse runs to `-`, and
trim. Both languages must produce identical names.

New claim names always lowercase, regardless of filesystem rules. `Auth-Fix` and `auth-fix` must
identify one claim everywhere to preserve mutual exclusion.

Reject an empty `''` name. Substituting a default hides a caller error and can create an unintended
lock shared by everyone.

### UTF-8 without a BOM

Write state as UTF-8 without a byte-order mark using `[System.Text.Encoding]::UTF8.GetBytes(...)`.
Some cmdlets can prepend a mark.

The Python commit-msg gate reads claims with `encoding="utf-8"`; a BOM makes `json.loads` raise.
The key then reads as unclaimed and the guarded commit is refused.

An earlier explanation called this a disabled gate. [Coordination](COORDINATION.md) and
`claim_check.py` establish the fail-closed behavior: malformed claims grant no ownership.

Set `encoding="utf-8"` on Python `subprocess.run`. `text=True` alone uses locale defaults,
including Windows `cp1252`.

A UTF-8 index once broke the reader thread, returned `proc.stdout` as `None`, and silently failed
every guarded commit.

Both languages must print ASCII-only hook output. Other bytes can become unreadable on non-UTF-8
consoles and break consumers.

### ISO-8601, round-tripped

Write timestamps with `.ToString("o")` and preserve that form when reading them back:

> `ConvertFrom-Json` converts ISO-8601 strings to `[datetime]`. Casting back with
> `[string]$record.claimed` loses fractions and the UTC offset through local short-date formatting.

> `ConvertTo-Stamp` in `claim.ps1` explicitly rerenders `[datetime]` and `[datetimeoffset]` values
> with `"o"`, preserving each refresh.

The same coercion changes a key such as `2020-01-01T00:00:00` into a local date that `-Release`
cannot match. Preserve the caller's spelling in the record; folded filenames define identity.

---

## 7. `ccx.config.json`: Six knobs, and nothing else

Root `ccx.config.json` supplies settings and the opt-in marker. User-scope hooks need a
file-presence check because they load in every repository on the machine.

Checking for implementation scripts would wrongly include half-installs and copied forks. It would
also miss repositories that store scripts elsewhere.

```json
{
  "prefix": "ccx",
  "trunk": "auto",
  "worktreeLayout": "sibling",
  "setupHook": ".ccx/worktree-setup.ps1",
  "protectedRefs": ["refs/heads/main", "refs/heads/master"],
  "sequences": {
    "adr": {
      "dir": "docs/adr",
      "filePattern": "^docs/adr/(\\d{4})-[^/]+\\.md$",
      "pad": 4,
      "indexFile": "docs/adr/README.md",
      "indexRowPattern": "^\\|\\s*\\[(\\d{4})\\]"
    }
  }
}
```

| # | Knob | Default | What it derives or controls |
|---|---|---|---|
| 1 | `prefix` | `ccx` | the state root `<git-common-dir>/<prefix>-coord`, the git config key `<prefix>.homeBranch`, and the per-worktree home-branch marker file `<prefix>-home-branch` |
| 2 | `trunk` | `auto` | the base for new worktrees, the allocator's floor sweep, the overlap detector's comparison, the sequence gate's base ref |
| 3 | `worktreeLayout` | `sibling` | where **we** create worktrees. The reaper never removes a `.claude/worktrees/` path, under either layout. `remove.ps1` does not check, so under `nested` it removes the one you name |
| 4 | `setupHook` | none | a script run after `git worktree add`, which is what keeps this repo language-agnostic |
| 5 | `protectedRefs` | `main`, `master` | which refs `push_guard.py` refuses a direct push to |
| 6 | `sequences` | none | `alloc.ps1 -Kind <name>` and `seq_check.py`. **Omit the key entirely and the sequence machinery is simply off** |

**Row 3 read "Nested-worktree *exclusion* from destructive operations is unconditional regardless"
until 2026-09-22, and it was false.** `remove.ps1` is destructive and never calls
`Test-CcxHarnessWorktreePath`.

Measured at `05eb4a7`, with `prune-merged.ps1` as the control:

```bash
git show 05eb4a7:scripts/worktree/remove.ps1       | grep -c Test-CcxHarnessWorktreePath   # 0
git show 05eb4a7:scripts/worktree/prune-merged.ps1 | grep -c Test-CcxHarnessWorktreePath   # 1
```

The control returns a hit, so the pattern was live rather than empty.

Config loading enforces two validation rules:

- `prefix` must match `^[A-Za-z][A-Za-z0-9-]{0,31}$`. It becomes a directory name, a git config key
  *and* an environment-variable stem. Anything that would need escaping in any of those is rejected
  once, at load, rather than producing a state root nobody can type.
- `sequences` absent and `sequences` empty mean the same thing on purpose. A caller must not treat
  "no sequences" as an error; a repository that maintains no numbered sequence should not have to
  carry a disabled allocator.

Three names remain fixed: `~/.claude/hooks/ccx-gate.repos.txt`, `ccx-coord`, and `ccx-announce`.
Neither settings marker may contain the other because ownership uses substring matching.

Keep a marker rename within one commit.

`protectedRefs: []` explicitly protects nothing and disables the guard with a stderr explanation. An
absent key uses defaults, preserving the difference between opt-out and no choice.

Python `load_config` raises on corrupt config instead of using unchosen defaults. An unreadable
governed configuration must stop work.

### Environment overrides and kill switches

| Variable | Effect |
|---|---|
| `CCX_CONFIG` | names the config file directly and short-circuits the upward walk (tests, `ccx doctor`) |
| `CCX_TRUNK` | overrides `trunk` for this session; wins over the config file |
| `CCX_PYTHON` | which interpreter the git hooks use |
| `CCX_ALLOW_DIRECT_PUSH=1` | the push guard's documented escape hatch |
| `CCX_ANNOUNCE_DISABLE` | secondary announce off switch |
| `CCX_EDITOR` | which editor `spawn.ps1` launches (falls back to `EDITOR`, then `code`) |
| `CCX_SESSION_BANNER` | path to the session banner text |
| `CCX_WORKTREE_PATH`, `CCX_WORKTREE_NAME`, `CCX_PRIMARY_ROOT`, `CCX_BASE_REF` | set for the `setupHook` process |

Use files for kill switches that must reach running sessions. New environment variables and hook
settings take effect only at launch:

- delete `~/.claude/hooks/ccx-gate.repos.txt`, or empty it, and the primary-checkout gate is off;
- create `<state-root>/announce/OFF` and the announce hook stands down.

### Couplings you cannot abstract away, so document them

These dependencies and limits remain part of the design:

1. PowerShell 7 and Windows-first. A shell port is a separate project. The Python part -- git-hook
   checkers, leak gate, shared substrate -- is stdlib-only and portable. Case-folding and process
   start-time reads degrade off Windows; the doctor names that blind spot on every run.
2. The client's session-record schema is a vendor contract, see section 3. It can break under you.
3. The `ccd_session_mgmt` MCP server is desktop-only, and announce delivery depends on it. On a
   plain CLI install the hook still fires and asks the model for tools it does not have, so nothing
   is delivered. Leave that hook uninstalled there, or create the OFF file. Nothing else needs it.
4. `<git-common-dir>` as the state root. Correct, deliberate, and not portable to a non-git-backed
   setup. Keep it, and keep its corollary in mind.
5. Windows path case-insensitivity in the folding rule. This has already broken once on a
   case-sensitive CI runner; see section 6.

---

## 8. The failure mode this whole design is guarding against

These failures can produce the same bytes as successful checks:

- a wired hook that resolves nothing prints what a healthy one with no peers prints;
- a fence that could not read the registry returns the empty list of one that found nobody;
- a gate missing its helper files exits 0;
- a control merged but never installed is a source artifact with green tests.

Print what was scanned, count examined records, distinguish empty results from failed scans, and
name untested cases.

### Prove the controls before you trust them

Check which controls run in this clone after [Quickstart](QUICKSTART.md) installation.

Run the doctor:

```powershell
pwsh -NoProfile -File bin/ccx-doctor.ps1
```

It reports each control with a tag:

- `OK` -- installed, wired, and where it can be attacked it refused what it must;
- `RED` -- proven broken: it allowed something it must deny, or denied something it must allow;
- `OFF` -- implemented here, but nothing invokes it: zero enforcement;
- `??` -- the check could not be run, and a skip is never a pass.

The doctor attacks controls and requires refusals paired with allowed cases. Run it before relying
on installed settings alone.
