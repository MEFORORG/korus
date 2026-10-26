# Lander playbook: sections that belong to another seat

> Split out of [LANDER.md](LANDER.md) on 2026-09-05. Each block below is a rule the Lander
> seat does not perform. **Nothing here has been edited.** Each needs a destination seat
> chosen by the owner before it is merged into that seat's playbook or deleted.
> Added to this header 2026-10-22, with no block edited: the `driver` and `empower` rules are on
> by default for every seat but Special. [COMMON.md](COMMON.md), *The empower rules are on by
> default, for every seat but Special*.

### 6c. A negative control must be ASYMMETRIC

| Item | Rule |
| --- | --- |
| Why it is the rule most likely to be skipped | A control that fails on EVERYTHING when you neuter the rule cannot tell you which layer does the work. |
| What it therefore cannot distinguish | "The other cases are safe by design" from "safe by luck". |
| The good shape, measured | Against a pre-fix artifact, **7 tests fail and 8 pass**. The 7 are exactly the classes the fix covers, the 8 exactly the shapes another layer catches. |
| What that buys | It distinguishes a correction from a widening. A uniform control would have passed and taught nothing. |

### 6d. Red-then-green does not prove a test can fail for the reason you think

| Item | Rule |
| --- | --- |
| The bad shape | Written as `if not <precondition>: assert <thing>`, the guard never ran once the defect's mechanism was removed. |
| What that hid | The red came from the FULL defect. The assertion could not see a PARTIAL one, and the test passed against code with half the defect restored. |
| What exposed it | A mutation putting the suppression back. |
| The fix | Make the assertion unconditional and verify it is red under BOTH the original defect and a partial regression. |
| The general form | Red-then-green certifies the path you happened to exercise, not the assertion's reach. |
| An unexplained failure is a stop signal | The same edit silently deleted an assignment inside the matched region, and nine tests went red for that reason rather than for the design change. |
| What saved it | Refusing to touch the expected failures until the one unexplained failure was explained. Reported blast radius 13; real number 4. |

### 6g. A check that runs after the destructive action is not a control

| Item | Rule |
| --- | --- |
| Ordering is the whole control | A lander update-branched three PRs, THEN checked whether live sessions held those branches. |
| Why the outcome does not clear it | The answer was "nobody", so nothing broke. The honest telling is "acted first and got lucky", not "caught it in time". |
| The line | The same check one minute earlier is a gate, one minute later is a story. |
| Re-measure the WATCHER, not just the condition | Background watches here cap at ten minutes. |
| The measured case | A session cited "my armed watch" across two messages as the reason its release condition was trustworthy. The condition was fine and the watch had expired hours earlier. |
| The rule | A monitor is a fact with a timestamp, exactly like the thing it monitors. |

### 6j. Budget an outside vantage point -- you cannot perform this review on yourself

Source of record: COMMON.md, row *A separate reader*.

| Item | Rule |
| --- | --- |
| Every trigger came from outside | One author narrowed a published claim three times in one night: an adversarial lens, then a false-deny lens, then a fork session measuring an independent copy. |
| What did not trigger any of them | Re-reading their own work. The findings are recoverable from files; this is not. |
| The structural version | Across three rounds of one fix, the implementing pass wrote "written and verified" into the ledger while its own verification had not reported, and verification then rejected it. |
| The cause is structural | Writing the verdict is part of the implementing task, so the artefact under test authors its own grade. **Fix the task boundary, not the agent.** |

## 10. Usage monitoring -- prevent lost work

**This is yours unless a Steward session is running.** Owner ruling 2026-08-13.

**Settle it with `pwsh -NoProfile -File scripts\coord\fleet.ps1`:** read the SEAT column on rows whose
STATE is RUNNING, and **match the seat name case-insensitively**. That roster renders seat names in
mixed casings, so a case-sensitive test reports a live seat as absent.

**`list_sessions` cannot settle it: it returns records, not liveness.** The seat is optional, and when
none runs this section binds you exactly as written. When one runs, it owns the watching and the
warning. **You still own the work-at-risk push sweep**, because that is a landing act and lands
nothing otherwise.

**Purpose:** warn before a 5-hour or weekly cutoff so in-flight work is committed and handed off
before a session is cut. It is not budget management. The owner runs four accounts and intentionally
exhausts them weekly, so a high-but-not-near-cutoff reading needs no action.

**The Steward stewards the WORK, not the quota.** It does not ration and cannot slow anyone down. If
one tells you to trim or defer work because a number is high, that is the seat exceeding itself, and
this section is the source of record.

### 10-a0. Your first act: confirm WHICH ACCOUNT you are watching

Owner ruling 2026-08-13, before you take a single reading and again if you resume from a handoff. This
binds you exactly as it binds a Steward: the seat changes, the failure does not.

There are several accounts on this machine. A watch pointed at the wrong one is not a partial watch.
**It is a confident, fluent, continuously wrong watch**, with well-formed readings, a believable burn
rate and **no symptom until the cutoff**, and the sessions trusting you lose work.

| Item | Rule |
| --- | --- |
| Ask, in words | Put the question to the owner through the Manager. |
| Never infer it | Not from a hook line, a config file, a session title, or which account you are signed in as. **Inference is what produces the fluent wrong answer.** |
| What the tooling can and cannot tell you | `python ~/.claude/mefor-usage/usage-now.py` names every account and prints the 5-hour and weekly bands per account. |
| Its limit | **It reads the POOLS. It does not tell you which account is YOURS**, and it can return UNKNOWN for an account when a refresh errors. |
| So | It informs the question and the owner settles it. |
| Name what you believe when you ask | "I read the account as X; confirm before I start", so the owner checks a claim rather than answering an open question. |
| Label every reading | Say which account and pool it came from, so a recipient can catch a mis-set watch you cannot see yourself. |
| No confirmation | Watch anyway, and say the account is UNCONFIRMED, loudly and repeatedly. An unconfirmed watch beats none; an unconfirmed watch presented as confirmed is worse than none. |

### 10-a1. The one thing you must not do unasked: a new Workflow above 90 percent

| Item | Rule |
| --- | --- |
| The rule | Over 90 percent, do not create a new Workflow without asking the owner first. |
| Everything else | Continues at FULL SPEED. The owner's standing rule is never to ration, slow down, or decline work because a number is high. |
| Why it is the rule most likely to be broken | Nothing else in this playbook mentions it. |
| Which window | The gate is `max(5-hour, weekly)`, not weekly alone. |
| The evidence | Across 4,577 samples the 5-hour field was at or above 92 in **303** samples and the weekly in **466**, so the windows fire at genuinely different times. |
| If you restate this rule | Restate the `max`. |
| Concurrency, not the number | One Workflow moved the weekly pool by several points on its own. |
| What that means | With several in flight the pool moves faster than the cache refreshes, so the margin must cover what is committed but not yet visible. |

### 10-a2. The gate is PER-POOL; the work-at-risk sweep is ACCOUNT-WIDE

| Item | Rule |
| --- | --- |
| Work-at-risk | Account-wide. A cutoff takes every session on that account, so sweep them all. |
| The 90 gate | Per-pool. It binds only sessions billing *that* pool. |
| The failure | Relaying one pool's percentage to a session on a different pool is how you stop work that had headroom. **A percentage is meaningless without naming its pool.** |

On WARN or CRIT, do not assert "nothing to lose" from your local state:

```bash
for w in $(git worktree list --porcelain | awk '/^worktree/{print $2}'); do
  echo "== $w =="; git -C "$w" status --porcelain | head; \
  git -C "$w" rev-list --count origin/main..HEAD 2>/dev/null   # unpushed (origin/main.., NOT @{u})
done
```

Then secure committed-but-unpushed work by pushing it, which is protective and non-destructive, and
tell live sessions to commit in-progress work.

**Held commits are not lost when a session dies.** All worktrees share one object store, so
`git show <sha>` works from any worktree and the Lander can push them without that session. **But a
pruned worktree can take its branch REF with it.** Reference the **SHA**, not the branch name, and
record the tip **before** any cleanup.

### 10a. The recoverability ladder -- establish the rung PER WORKTREE before you clean anything

*"It is in the shared object store, so it is recoverable by SHA"* is true only on some rungs, and the
sentence is dangerous precisely because it sounds like a blanket guarantee.

| rung | state | survives a worktree removal? |
| --- | --- | --- |
| 1 | **pushed** to a remote | Yes, unconditionally. |
| 2 | committed, local ref exists | Yes. The ref keeps the objects reachable. |
| 3 | committed, **ref deleted**, not yet collected | Only if you recorded the SHA first. Unreachable objects survive until something collects them, and no ref and no reflog means nothing will point you at them. |
| 4 | committed, ref deleted, **after a `gc` or `prune`** | Gone. |
| 5 | **uncommitted** (modified, staged, or untracked) | Gone. There is no SHA. Removal does not dangle the work, it destroys it. |

| Item | Rule |
| --- | --- |
| Rung 3 is a race, not a safe state | `gc.auto=0` is set deliberately on a clone whose loose-object count already exceeds git's default threshold. |
| What that stops | A routine command silently converting a reversible ref deletion into permanent loss. |
| So | Never unset it while any session holds unpushed work, and never run `gc`, `prune` or `reflog expire` in this repo. |
| Rung 5 is invisible to every commit-based check | A worktree can read as zero commits ahead of `main`, the most reassuring possible signal, while holding staged-but-uncommitted files that exist nowhere else. |
| The only instrument that sees it | `git status --porcelain` in that working tree, run BEFORE the removal. |
| The removal check is a conjunction | Not live, AND `status --porcelain` empty, AND no unique commits. |
| Why all three | Any one alone will happily bless the destruction of real work, and the commit-based half is the weaker half. |

### 10a-bis. PRESERVED is not LANDABLE

The ladder grades work by PRESERVATION, and rung 1 is its most reassuring rung. **It says nothing
about LANDABILITY.**

This clone carries two remotes for two different repositories, so a rescue tag pushed to the
non-`origin` one is rung 1 and **cannot reach `main` at all.** The most reassuring rung on the ladder
is compatible with the work never landing.

| Item | Rule |
| --- | --- |
| Check reachability before writing the plan | `git branch -r --contains <sha>`, filtered to `origin`. It is one command. |
| Measured 2026-08-22 | A post-merge repair plan was written against a defect body reachable only from a rescue-tag ref on a non-`origin` remote, and was withdrawn once reachability was checked. |
| An inert plan must be withdrawn | A plan whose trigger is a merge that cannot happen does not get left standing. |
| Two ledger rows, one landable ref | When one defect carries two rows and only one sits on a landable ref, the landable row is the ONLY live record. |
| What closing it costs | The defect is lost with nothing reporting it: the twin reads as the closure and the surviving row is gone. **Keep the reachable row open.** |
| **EXPIRY** | Rescue tags start pushing to `origin`. Check by reading where the rescue automation pushes, not by finding one tag that happens to be there. |

### 10b. Pin a live peer's work by BRANCH, never by directory name, never by enumeration

| Item | Rule |
| --- | --- |
| The measured failure | A cleanup scoped to hold six peer lanes used the directory glob the peer had *named* them. |
| What went wrong | The workers had called the create script with their own shortened names, so the real directories carried an extra separator and the glob matched **zero** of them. |
| What that looked like | The hold pointed at nothing while looking specific. |
| Why | A worktree directory name is a creation-time label chosen by whoever ran the script. Nothing keeps it current, and it is not the join key. The branch is. |
| Never enumerate a growing fleet | Two of the six lanes had not yet dispatched and would name their own worktrees on arrival. |
| So | Any point-in-time path list goes stale inside the window it is meant to protect. |
| Hold categorically instead | On a branch pattern such as `^w1-l[0-9]-`, which covers arrivals you have not seen yet. An enumeration protects the lanes that already existed when you asked. |

### 10c. A safety check has a FRESHNESS WINDOW, so re-run it at the moment of the mutate

The rule that a check running *after* the destructive action is not a control has a mirror. **A check
running too far BEFORE it is not a control either**, because a live working tree is a moving target.

Measured during one cleanup, inside a few minutes:

| | peer's report | measured at plan time |
| --- | --- | --- |
| HEAD | `origin/main`, 0 commits ahead | 1 commit ahead, a new local sha |
| uncommitted | 5 files | 1 file |
| two named files | staged-added, in no commit anywhere | committed -- 1 commit touches each |

**Nobody was wrong.** The report was accurate when written, and the lane committed in between. The
error runs in **both** directions. Here it moved from more dangerous to less. A tree that was clean
when surveyed can hold an hour of uncommitted work by the time a batch removal reaches it.

| Item | Rule |
| --- | --- |
| What a survey is for | Deciding scope. Never authorising the act. |
| Re-check per removal | Re-run `status --porcelain` and the ref check immediately before each individual removal, not once for the batch. |
| Why | A batch-level pre-flight is a snapshot, and a snapshot cannot see work created after it starts. |
| Movement disqualifies | Any tree that changed between survey and execution drops out of the sweep rather than being re-judged in the moment. |
| Why | Movement is evidence of a live session, which is the one condition never worth racing. |
| So | Remove trees one at a time with a fresh check each. Never a loop that trusts a list computed at the top. |

### 10d. Silence from the monitor is not a clear reading

The hook prints nothing when the band is OK, which is also what a crash, a stale cache, or a parse bug
looks like. **Confirm positively before treating quiet as headroom.**

| Item | Rule |
| --- | --- |
| The measured bug | A regex crossed a line boundary and dropped the **weekly** reading whenever a metric line carried no reset time. |
| What that hid | The affected pool scored band OK and said nothing while sitting at weekly **93 percent**, over the gate. The pool that looked correct was correct only by luck. |
| The corrected trigger | First recorded as "whenever the 5-hour reads 0.0 percent". An adversarial audit refuted it. |
| The refutation | The old pattern loses a metric at 5-hour **93.0 percent** with no zero anywhere. |
| Why the wrong version was believable | The observed pool had both properties at once, so a coincidence read as a cause, on the very fix meant to close it. |
| What inheriting it would have cost | Hunting for a condition that does not exist. |

### 10e. A threshold is not a decision, and it fails in BOTH directions

Read these together. Alone, each trains a habit the other breaks.

| Item | Rule |
| --- | --- |
| The number crossed and meant nothing | A 93 percent pause was fired at two working sessions with **7 minutes** to reset. Abundant, not scarce, and it had to be retracted. |
| A peer's framing | *"You conflated a real loss risk with a usage threshold and used the threshold to carry the priority. The priority survived; the justification did not."* |
| When the same number IS scarce | At 90 percent with 2h47m left. **Evaluate time-to-reset.** |
| The number did not cross, and that was a lie | The silent-weekly bug above. The gate was simply absent, and an absent gate has no red to dismiss and no moment where it looks wrong. |
| Why the pairing is the point | The first alone teaches you to discount the monitor. The second alone teaches you to escalate on silence. |
| The rule that survives both | Establish that the number is REAL, then establish what it MEANS. One wrong call skipped the second step; the other skipped the first. |

### 10f. Usage tooling

| Item | Rule |
| --- | --- |
| Where the readings live | Token files for four accounts under `~/.claude/mefor-usage/`. `python ~/.claude/mefor-usage/usage-now.py` gives the worst band. |
| Auto-injection | A `SessionStart` plus `UserPromptSubmit` hook injects the band, wired in `~/.claude/settings.json` and each per-account settings file. |
| Adding or repointing an account | Do NOT edit `watch.py`. It is a **data** edit to `accounts.json`. |
| The key order | The org uuid keys the row and the account uuid is inside it. It has been inverted before and only a test caught it. |
| The cache | `status.json` IS the cache. After any mapping change, clear its `pools` key. |
| Why | A stale UNKNOWN after a correct fix looks exactly like a failed fix. |
| HTTP 400 on refresh | That token is dead and only the owner can revive it. |

### 11a. Merging to `main` does not make a hook live -- `git pull` in the primary is the activating action

This falsifies a claim the project's own docs once made, that a channel *"becomes live everywhere the
moment the scripts land on main"*. **It is false in the direction that matters, because a merge
notification is exactly when an operator believes it went live.**

| Item | Rule |
| --- | --- |
| The measurement | `scripts/hooks/<file>` PRESENT on `origin/main`, ABSENT in the primary checkout's working tree, primary HEAD 3 commits behind. |
| The result | The channel stayed inert across the whole machine after its PR merged. |
| Why | The shim resolves a WORKING TREE, not a ref, and nothing pulls the primary. |
| Who pulls | `git pull` in the primary is an owner action, not a session action. Dozens of worktrees resolve hooks through it, so one pull changes behaviour for all of them at once. |

### 11b. Single-vantage hook checks lie, so probe from a tree that does not hold the branch

| probed from | primary | fallback | result |
| --- | --- | --- | --- |
| a worktree HOLDING the branch | False | True | resolves -- looks healthy |
| any OTHER worktree | False | False | nothing resolves |

Probing from your own worktree returns green. That is how one hook resolved nothing from the moment
it was wired. **Run every hook-resolution check from a second vantage point that does not hold the
branch under test.**

### 11c. Removing a worktree -- ANCHOR FIRST, REMOVE SECOND

**`git worktree remove` is NOT ATOMIC. Measured.** On a path over Windows MAX_PATH it deregistered the
worktree and deleted `.git/worktrees/<id>`, then failed to delete the directory and exited non-zero.
Final state: admin dir gone, directory still on disk, command reported failure.

For a **detached** worktree that admin dir holds `HEAD` and the per-worktree reflog, which are the only
reachability roots its commits have. **So a failed removal can destroy the anchor while leaving a
directory that looks untouched.** Reading a non-zero exit as "nothing happened" is wrong in the one
direction that loses commits.

| Step | Rule |
| --- | --- |
| 1. Anchor | `git update-ref refs/rescue/<name> <sha>`, with the sha read live from that worktree's HEAD, never transcribed from a report. |
| 2. Remove | Then, and only then, remove. |
| 3. Why it is cheap | A ref costs nothing and is the entire difference between a failed removal being an inconvenience and being a loss. |
| Not hypothetical | In the run that produced this section one rescued tip came out of the deregistration contained by exactly one ref: the rescue ref created minutes earlier. |

**Prefer plain `git worktree remove` with your own fail-closed pre-flight over any wrapper**, until the
wrapper is fixed. Four defects measured in this repo's `remove.ps1`, all confirmed independently:

| Defect | Detail |
| --- | --- |
| Unconditional prune | It runs `git worktree prune`, the exact command `prune-merged.ps1` refuses to run and explains why. Its blast radius exceeds its targeting: it can deregister trees in families it cannot address. |
| Cleanliness guard FAILS OPEN | `$tracked = & git status --porcelain \| Where-Object {...}`. A native exe's non-zero exit is not terminating under `$ErrorActionPreference = "Stop"`. |
| What that means | A failing `git status` (corrupt worktree, locked index, the states you want it to stop on) leaves `$tracked` empty, the guard passes, and removal proceeds under `--force`. |
| The contrast | `prune-merged.ps1` fails closed and pins `$PSNativeCommandUseErrorActionPreference`. That difference is a fact about a CONFIGURATION: a profile change inverts it. |
| No brakes | No dry run, no `-WhatIf`, no occupancy fence, and `--force` deletes untracked files. |
| Capturing recovery information is not providing it | It captures the tip before removal, but the line that PRINTS it sits after the removal and inside `if ($DeleteBranch)`. |
| So | Without `-DeleteBranch` the tip is never captured. On the failure path it throws before printing anything. |
| Its own comment is false in both directions | It claims "the tip is printed either way, so scrollback is the undo", and it is false exactly on the path the non-atomic failure creates. |

### 11d. Select by PROPERTY, never by NAME, and recency is the arm that comes first

Pinning a peer's work by branch rather than directory was still not enough, and the escalation is the
lesson. Across one wave of six worker lanes, three successive name-based rules each failed:

| rule | how it failed |
| --- | --- |
| an enumeration of lane directories | two lanes had not dispatched yet and named themselves on arrival |
| a directory glob from the names the lanes were given | workers called the create script with their own shortened names |
| a branch regex derived from the four names that existed | a later lane used a different separator convention and matched nothing |

Each fix moved one layer up and inherited the same defect, because **a name is chosen by whoever
created the thing and nothing keeps it current.** A rule derived from the names present when you
looked cannot cover the ones that arrive after.

**Match the property that makes the operation dangerous. It needs no name.** For worktree removal,
EXCLUDE any worktree where:

> **(c)** any working-tree file, excluding `.git` and `.venv`, was written within N minutes; OR
> **(a)** `git -C <dir> status --porcelain` is non-empty (uncommitted work, no undo); OR
> **(b)** its branch has commits not reachable from `origin/main` and not present on any remote.

| Item | Rule |
| --- | --- |
| What that catches | Lanes nobody told you about, lanes that do not exist yet, and lanes belonging to other sessions entirely. No naming convention can defeat it. |
| Ordering is the lesson, not the arm | (c) is the LIVENESS fence -- is anyone there. (a) and (b) are the DATA-LOSS fence -- would anything be lost. |
| Why recency gates first | It is the only arm correct at t = 0. A tree being created is itself activity. |
| Why (a) and (b) alone are false-safe | Both measure ACCUMULATED OUTPUT, so a tree that has not written anything YET is byte-identical to one that finished and was cleaned. |
| Measured minutes after dispatch | `w2-l3-gate-emitter`: HEAD == origin/main, dirty=0, unpushed=0, idle=0 min. `w2-l4-ci-margin-asvs`: the same, idle=1 min. |
| What the two arms called them | Inert and sweepable. The most active worktrees on the box. |
| **An empty tree is not an inert tree** | The missing dimension is time, not identity. |
| The symmetry | Name rules fail on ARRIVAL. Output-property rules also fail on ARRIVAL, for unrelated reasons. |
| So | Treating (a) and (b) as primary and recency as a belt-and-braces extra is backwards. In the run that produced this, recency was the only arm that excluded the live lanes. |
| Where property beats name in the other direction | An abandoned lane detached at `origin/main` with zero commits and zero dirty files reads as live under a name rule and correctly as inert under the property rule. |
| Verified on the adversarial case | A live lane whose name matched none of the three patterns was nevertheless held, because the selector measured idle time rather than parsing its name. |
| `occupancy.ps1` is structurally blind to agent-driven siblings | It returns NO VETO for every agent-driven sibling worktree, live ones included. That is documented behaviour, not a defect. |
| What its own header records | A session writing into a worktree by absolute path from elsewhere is invisible to it, and a large share of writes on this repo are exactly that shape. |
| Its own measurement | ZERO `<primary>-<slug>` siblings drew a veto, *"including the one a session was demonstrably building in."* |
| Why that matters here | Workflow sub-agents are exactly that shape, so for them recency is not the first of three arms. It is the **only** arm that works. |
| Occupancy may VETO, never AUTHORISE | Its own header, `:40-41`: *"a DEAD/STALE/absent verdict must never by itself authorise one."* |
| Why reading `veto = False` as permission is the same error | Absence of a positive signal treated as a negative finding, one level up from the output-property rule. |
| It is a DOT-SOURCE LIBRARY, not an executable | Measured: 7 functions, and running it bare emits ZERO lines, byte-identical to "no veto". |
| So | Dot-source it and call the function. Never shell out and test for output. |

### 11e. Split the valuable half of a cleanup from the dangerous half before deferring either

A cleanup request arrives as one task and is usually two, with wildly different risk-to-value ratios.
**Measure both halves before deciding to defer, or you defer the wrong one.** Measured across 47
sibling worktrees:

| operation | recovered | cost of getting it wrong |
| --- | --- | --- |
| deleting `.venv` | ~31 GB | a rebuild |
| removing the worktree | ~100 MB each | orphaned commits, lost uncommitted work |

| Item | Rule |
| --- | --- |
| The asymmetry | About 89 percent of a heavy worktree is its virtualenv. Deleting one touches zero refs, zero commits and zero uncommitted files, and is reversible by re-running the create script. |
| Where the hazards actually sit | Every hazard in the usage and worktree sections attaches to worktree REMOVAL and none of it to venv deletion. Yet the two travel as one job and get deferred together. |
| So defer at the right granularity | Defer the removals, do the venvs now. The original recommendation deferred the whole cleanup, and that instinct was right at the wrong granularity. |
| The one pre-check | Confirm nothing resolves a sibling venv by ABSOLUTE path: a launch config, a hook, a scheduled task. |
| Why | Relative-path consumers fail as "rebuild me" inside that tree. An absolute-path consumer fails differently and elsewhere. |

## 12. Installing hooks and gates

| Item | Rule |
| --- | --- |
| Installers are the owner's | Several refuse to run inside Claude Code by design: *"a session that can install this gate can also remove it"*. |
| What that is | A trust guard about the installer's provenance, not an inconvenience. |
| Source is the INVOCATION DIRECTORY | Run from a worktree, that worktree's content goes machine-global into every config dir. Where a command runs is where the caller is. |

### 12a. Compare against the INSTALLED copy, not against `main`, and establish the DIRECTION by measurement

The documented hazard is *"installing from a stale checkout DOWNGRADES the live copy -- trust the SHA,
not the label."* A guard of "verify my source is byte-identical to `origin/main` before installing"
**passes and is still a downgrade** whenever a fix to a hook is in flight, because the installed copy
can be legitimately AHEAD of `main`.

**And the direction is perishable.** A standing, heavily-repeated instruction read *"DO NOT re-install
-- the installed gate is NEWER than main and re-installing would DELETE a live security fix."*

It was true when written. Some days later the held fix merged, `main` moved dozens of commits and
became a strict SUPERSET, so re-installing would have added a fix and deleted nothing. **The
instruction had inverted and nothing told it.**

| Step | Rule |
| --- | --- |
| 1. Fold line endings first | An installer copies with `Copy-Item`, so the installed file keeps the checkout's CRLF while `git show` yields LF. |
| Why that is not a collision | A git-extracted file is pure LF, so its raw and folded hashes are trivially equal. "Extracted raw == installed folded" is an IDENTITY. |
| So | Raw-byte comparison between an installed and a git-extracted copy is always wrong. |
| 2. Read the DIFF, not the inequality | Ask which side carries content the other lacks, and what that content is. Three separate sessions have read an inequality as a direction. |
| 3. Search EVERY ref before calling a copy unaccounted for | Fold the file at every ref and compare. A copy matching no branch is a different fact from one matching a feature branch. |
| 4. Neither stamp nor hash is authoritative alone | A version stamp has read IDENTICAL across a real content divergence. Compare content, and identify the source by matching against every ref. |
| A red parity test is not a direction either | When `installed != main`, staleness versus fix-in-flight is exactly the question above, and anyone triaging it as staleness reaches for the installer. |
| The rule | When a parity instrument goes red while a fix is genuinely in flight, the fix is to MERGE, never to re-install from an older tree. Only the authoring worktree may install until its PR lands. |

### 12b. "Is `origin/main` ready" and "is the checkout I install from ready" are different questions

| Item | Rule |
| --- | --- |
| Only the second governs disk | Preconditions were verified on `origin/main` and the owner told to install while the primary checkout was 3 commits behind. |
| The result | The installer generated the OLD shim and undid a fail-open fix by the act of installing it. |
| So | Always `git pull --ff-only` in the primary in the same command as the install. |
| Two artifacts, two sources | That same install IMPROVED one file while REGRESSING another, because the installer script itself was stale even though the payload it copies was newer. |
| The lesson | A partial improvement can hide a regression. |
| Verify by MARKERS, never by content equality | A correctly resolved keep-both conflict matches NEITHER branch byte-for-byte, so content comparison reports failure on a correct merge. |
| So | Check the merged file contains both sides' distinctive symbols. That survives squash, merge and rebase, and doubles as proof the resolution kept both sides. |

### 14h. The worst shape: a control weakened, with a new test pinning the weakening as intended

Measured on a worktree-gate change that read as hardening. Its premise, *"a message flag's quoted span
is DATA, not a command"*, is false for exactly the two spellings that matter:

```
"a $(1+1) b"   -> a 2 b          @"..."@ -> a 2 b        <- TEMPLATES, substituted
'a $(1+1) b'   -> a $(1+1) b     @'...'@ -> a $(1+1) b   <- inert
```

Only **single**-quoted spans are literal. Six verdicts moved DENY to ALLOW carrying live `$(...)`
payloads, **and the commit added the executable spelling to the must-ALLOW parametrize.**

Three properties compound. It *reads* as hardening, so it invites less scrutiny. The new test makes
the bypass a **requirement**, so anyone later restoring the deny reds the suite and concludes they
broke something. And nothing downstream can catch it, because the gate **is** the control.

This is worse than a guard that deletes a control by making the existing tests unreachable. Here the
tests are not unreachable. **They are made to assert the hole. The bypass acquires a defender.**

| Rule | Detail |
| --- | --- |
| Process cannot check a premise | That lane's process was excellent: real mutants, byte-identical restores, disclosed residual gaps, no deleted coverage, no false denies. |
| What red-first proves | That a change has the effect it claims, never that the effect is *desirable*. |
| The argument that follows | An adversarial reader as a **separate** stage, rather than a stricter checklist on the same one. |
| Batch result | Three lanes, about 1.5M tokens, **zero landable commits, and that was the batch working.** |
| When a fix replaces an enumeration, ask which other axes are still enumerated | A fix filed to stop hand-typed enumerations replaced the prefix list with a generating rule, then left the **sigil** as a hand-typed two-member class `[-/]`. |
| Measured | `pwsh --command`, `--Com` and `--c` all execute. |
| What its banner then claimed | *"The missing spellings were every prefix from -C to -Command"*, a false completeness claim (SDS-3.6, *prefer "at least" to an enumeration*) that a compensating control then rests on (SDS-3.7, *a compensating control must not rest on a false premise*). |
| "Latent because of an accident of this machine" is not a mitigation | A third lane's rule was defeated entirely by **any whitespace in the repo path**, absolute spelling included, latent only because this box's primary has no space. |
| The second cost | It also broke that report's own control row. **A control that does not hold undermines the evidence it was there to underwrite.** |
