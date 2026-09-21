---
name: "lander-triage-a-red-check"
description: "Triage a failed required check on a pull request you are landing. Use when a CI leg is red, before re-running anything, to attribute the failure and decide fix, route or re-run."
user-invocable: true
disable-model-invocation: false
---

# lander-triage-a-red-check

> Task rules for the Lander seat, split out of [LANDER.md](../../../roles/LANDER.md) on 2026-09-05.
> The prohibitions that bind before this task starts stay in that file. Read it first.

### 2a. Every post-push failure lands on you by default, so the question is what you FIX and what you ROUTE

A Builder's process exits when its PR opens. Nothing it authored is watched by the session that wrote
it: not a conflict, not a red, not an eviction, not a stripped label.

**There is no "send it back to the author" -- the author is gone and unrecoverable.** Routing to the
Manager means a *different* session reads the PR cold, and so does a subagent. The choice is never
"who understands this work". It is latency, state, and who signs the change.

**THE LINE: fix anything the REPO'S MECHANICS determine. Route the moment a fix needs to know what
the PR MEANT TO DO.**

| Work | Who | Why |
| --- | --- | --- |
| Reruns, labels, enqueue and dequeue, pacing | **Lander, locally** | Mechanics plus global state. Queue depth and CI load exist in no other seat. |
| Content conflicts, `docs/BACKLOG.md` rows included | **Lander, locally** | Owner ruling 2026-09-21, widened from ledger rows alone. `LANDER.md` *4c-quinquies*. Latency decides the ledger rows. See below. |
| Flake triage | **Lander, locally** | Needs the known-flake list and the job log, both of which sit with you. |
| A code change beyond conflict resolution | **Route to the Manager** | You would be authoring on someone else's subject. |
| A design decision on someone's PR | **Route to the Manager** | Same line, and this is the one that feels most like helping. |

**LATENCY IS WHY CONFLICTS STAY WITH YOU, AND IT IS A MEASUREMENT, NOT A PREFERENCE.** Measured
2026-09-04, with the queue held shallow: `main` moved every **~26 minutes**, nine merges in 3.9
hours.

A `BACKLOG.md` conflict routed out through a Manager poll, a spawn, a brief and a cold context read
will routinely re-conflict before it lands. Nine were resolved that day. Round-tripping them would
have been a treadmill.

**Compare the round-trip against the current merge cadence before routing anything whose fix decays.**
If the cadence is slow the calculus changes, so re-measure rather than quoting this number.

**SUBAGENTS ARE FOR DIAGNOSIS, NOT AUTHORSHIP.** A read-only, bounded question you cannot settle
yourself is the right shape. On 2026-09-04 an adversarial review decided whether a defect filed twice
under two numbers should be renumbered on the landed side or the unlanded one.

**A subagent that WRITES on someone's PR is worse than doing it yourself.** It holds your context,
not the author's, so it does not supply the missing understanding. It only moves your judgment into a
process you supervise less closely. When you do the work, you sign it.

**NARROWED 2026-09-21, by Owner ruling, and only where the work is already YOURS.** Two kinds of
authorship are the seat's own, so a subagent may write them. One is resolving a content conflict.
The other is the `code-review` pass, and its fixes, on a pull request with no QA line.

`roles/LANDER.md` *4c-quinquies* and *4a-quinquies* hold both. A RED CHECK is not among them, and
the rule above is unchanged for one. You still sign what the subagent writes, so read the commit,
not its report.

**THE FAILURE MODE IS DOING IT WELL.** Measured 2026-09-04, and both were the lander's own.

On one PR the merge pulled in a test from `main` whose control asserted the *opposite* of what that
branch had just made true. It would have gone green while pinning a retired premise, so the lander
rewrote it.

On another, landing a prerequisite exposed one notification site reading the wrong address, and the
lander changed it.

Both were mutation-verified. Both were flagged on the PR asking the author to check. **Both should
have routed.** Each was defensible on the night and neither is defensible as the standing rule,
because "I understood the mechanism" is how a Lander ends up authoring half the tree.

- **The tell:** if you are about to write a sentence on the PR beginning *"the mechanism is measured
  but the design is yours"*, you have already crossed the line. Post the finding and route it.
- **What routing costs you is a merge, and that is the correct price.** A PR held with a named,
  reproduced finding is worth more than one merged on your guess about someone's intent.

### 4d. Distinguish "retry in flight" from "suppressed"

A rollup keeps reporting the PREVIOUS attempt's FAILURE until the new attempt reports. So a watcher
restarted after you trigger a re-run wakes on that PR immediately and forever.

| Item | Rule |
| --- | --- |
| The wrong fix | A skip list. That is permanent blindness bought to solve a temporary condition. |
| The right fix | A LIVE-STATE test: look up the failing check's run and ask whether an attempt is `queued` or `in_progress`. If so, stay quiet. |
| Why it is better | When the attempt reports it either clears or wakes for real. Nothing is permanently hidden and no cleanup is needed later. |
| Failure direction | An unreadable run status must WAKE. |
| Confirm a re-run started | Read `run_attempt` back. `gh run rerun` prints nothing on success, and that silent-success shape has hidden a failed auto-merge arming. |

## 5. CI knowledge

| Item | Rule |
| --- | --- |
| Green local is not green CI | Some guards are CI-only. The leak and secret gate FAILS CLOSED without a token source, so a red there may be environmental. Check what it scanned before concluding. |
| Local pytest skips legs silently | It skips the webconsole package and the SQL Server and Postgres store legs. Name both paths: `pytest tests packaging/messagefoundry-webconsole/tests`. |
| Never infer absence from a scoped grep | The scope is the answer you get, not the answer you asked for. |
| Security scanners | CodeQL, Trivy, Scorecard and zizmor run in the mirror. Default-setup must stay OFF, and zizmor is not merge-blocking. |
| "CI checks unavailable" | An undiagnosed catch-all fallback, not a diagnosis. If `gh` auth is the cause, re-auth only with `--insecure-storage`. |
| `pytest -x` is not a full suite | It stops at the first failure. "Full local suite: 9,754 passed" was reported in two PR bodies while roughly 500 tests never ran. If you use `-x`, say so. |

### 5a. A timeout with single-digit headroom reads as a flake

| Item | Rule |
| --- | --- |
| Read the cap first | When a suite habitually finishes near its cap, any PR adding test time is a coin flip, and the failure presents as a flake. |
| How | Read the configured `step_timeout` and compare it against measured wall times before believing anything about the change. |
| Do not raise `step_timeout` | It is deliberately held under `job_timeout` so a process-level deadlock below pytest surfaces as a STEP failure rather than a job kill. |
| What raising it buys | It trades a real diagnostic for a green tick. |
| The tell that it is the cap | The change's content and the failure's location do not line up, such as a `pwsh` or `git` subprocess change dying in a TLS test. |
| The second half of that tell | The same leg is green on many other open PRs. The first rules out a defect in the change; the second rules out the environment. |
| The tell runs one way only | When content and location DO line up, the flake reading is unsafe. Content is live and runner load is live at once, and they may not be separable. |
| Measured 2026-08-22 | A `subprocess.TimeoutExpired` on a gate script at 60 seconds, on a PR that modified that script plus five of its test files. |
| Report the non-separation | Write "content live, load live, not separated" as the verdict. That stops the reflex re-run; calling it a flake buys a coin flip and an unattributed red. |

### 5b. Attribution -- prove a CI failure is not the change's, without hand-waving "flake"

Prove a failure is timing-dependent **before** calling it one. The two previously-famous "flakes"
here turned out to be a livelock and a test that was right.

| Step | Check |
| --- | --- |
| 1. Decisive | Did a SUPERSET of this content pass the same leg? A subset cannot introduce a failure the superset did not have. If you have a superset run, nothing else is needed. |
| 2. Concurrency | Check the OTHER concurrent runs. Runner contention was the obvious hypothesis and was wrong once: two other runs passed the same leg in the same window. |
| 3. Blast radius | `git diff --name-only origin/main...HEAD \| grep -iE '<subsystem>'`. |
| 4. Chronic leg | `gh run list --workflow ci.yml --limit 25`. |
| 5. Retry harness | "not a native crash -- not retrying" means nothing was papered over. |

**Step 3 cuts both ways, and both verdicts bind.** An empty intersection between the PR's changed
paths and the failing test's dependency closure EXONERATES. A non-empty one CONDEMNS, and it blocks
the reflex re-run even when the failing test is not one the PR changed.

Measured 2026-08-22, both directions in one night. Zero overlap correctly cleared a PR touching twelve
files, none under the failing subsystem. Six overlapping files, the script under test plus five of its
test files, correctly condemned another.

Run it before every re-run and accept both verdicts. The mechanical form is step 3's command
intersected against the failing test's import and subprocess dependencies. A non-empty result is a
stop. It is gate-shaped, so route it to whoever builds gates.

| Item | Rule |
| --- | --- |
| Native-crash exit 139 on a docs-only PR | Not a test failure. A documentation edit cannot segfault the suite. |
| Generalise that | A failure observed on a commit that CANNOT REACH the code under test is not a property of the tree. This holds for any failure, a measured bound included. |
| Getting that control, passive route | Search the leg's recent history for a commit that cannot reach the code and failed anyway. Free, one `gh run list`. Found this way 2026-08-22. |
| Getting that control, active route | Push a null-change commit to the SAME arm. Costs a cycle, and is the only route when the history holds nothing suitable. |
| Say which route you used | Reach for the passive route first. The two are not equally strong evidence and a reader cannot tell them apart from the verdict alone. |
| Record the residue | A once-in-25 query timeout on a lock-holding statement is a latent contention signal, not noise. If it recurs it gets a number, not another re-run. |

### 5b-bis. "Timing-dependent" and "wrong" are not alternatives -- a test can be both

Establishing that a failure is timing-dependent explains *why the result varies*. It says nothing
about whether the test is right to pass on the other side of the coin flip.

Worked example, measured end to end. A test spawned a child process and polled a process walk for it:

```
_BURN                  = a BOUNDED loop            -> child lifetime ~11.8s, exits naturally
_RESOLUTION_DEADLINE_S = max(30.0, 6 * timeout)    -> poll loop runs 30s
```

The fixture child is dead for roughly the last 18 seconds of the loop. The test passes only when the
walk catches the child inside its ~12s life. **A longer deadline strictly increases the chance the
child is gone before the loop ends, so the retry loop is anti-correlated with success.** The mechanism
that looks like patience is the mechanism that manufactures the failure.

| Item | Rule |
| --- | --- |
| A green re-run is not counter-evidence | It is consistent with this diagnosis. The race resolves either way depending on load. |
| So pre-register it | Predict the re-run's outcome BEFORE running it, so a green is a confirmed prediction rather than a rationalisation reached afterwards. |
| Read the fixture's exit status, not its absence | `returncode: 0` in the assertion repr was the whole diagnosis. It proves the child exited naturally. |
| The discriminator | A killed child on Windows renders `1`, because `Popen.kill()` is `TerminateProcess(handle, 1)`. |
| So | Absence plus a clean exit code is a lifetime problem. Absence plus a kill code is a teardown problem. Different bugs. |
| Fix the lifetime, not the window | Make the child outlive the observation window, and bound the poll on the fixture still being alive so it stops the moment the child dies and says so. |
| A flake note covers only its own mode | The test carried an accurate comment describing a DIFFERENT failure on the same platform: an enumeration timeout yielding an empty list. |
| What separated them | The observed assertion said the walk SUCCEEDED, with a non-empty result. **The better the note, the more readily it is over-applied.** |
| A local quartet, green OR red, can be a venv artifact | Measured in opposite directions on the same commits: one session reported 21 mypy errors from missing optional extras, another a metadata-version failure from a venv installed off a stale tree. |
| So | Do not inherit a peer's "known pre-existing failures" and do not hand yours on. CI on the PR tree is the authority. |

### 5b-ter. Three questions that end a triage before it starts, each saving a runner cycle

| Question | Rule |
| --- | --- |
| Is the red deterministic across every leg, and does it name the file to change? | Then it is a ROUTING decision, not a triage one. There is nothing to re-run and nothing to attribute. |
| The measured case | 2026-08-22: four legs, one identical assertion naming the file to change, and the required rollup context merely reporting it. Route the fix to the seat that owns the file. |
| Is the PR a draft or unarmed? | Do not spend a required-context re-run on it. A green buys nothing: it cannot merge, and the head will move first. |
| How to refuse it | Read `gh pr view <N> --json isDraft,autoMergeRequest` before `gh run rerun`, and refuse the re-run when the PR is draft and unarmed. |
| **EXPIRY** | Runner capacity stops being scarce, or drafts start gating merges. |
| Does the branch have a prior head at all? | Step 4 asks whether the LEG is chronically red. Nothing asks whether the BRANCH has history. |
| Why it matters | On a branch with exactly one run, often the one your own push triggered, the "did it fail this way before" discriminator does not exist. |
| The command | `gh run list --branch <b> --limit 5`. **Declare the discriminator unavailable rather than assuming its answer**, which is how an unresolved red gets written up as attributed. |

### 5b-quater. Read the ASSERTION and its history -- shape, node id, and magnitude

| Property | Rule |
| --- | --- |
| Shape | An assertion whose right-hand side is a FRACTION of a prior run's recorded number is environmentally sensitive by construction on a shared runner. |
| Why | It measures the difference between two runner loads. Observed 2026-08-22 as a throughput-monotonicity bound comparing a run against 75 percent of a prior run's recorded figure. |
| So | Classify it once from its shape and stop re-arguing it at every incident. |
| Gate available | Grep the suite for assertions reading a prior run's recorded value, and require each to carry a runner-load caveat or move off the required-context set. |
| **EXPIRY** | The assertion is rewritten to a fixed floor, or the leg moves to pinned hardware. |
| Node id | Census a recurring red by pytest node id, never by assertion text. One test wearing several assertions reads as several unrelated bugs. |
| Measured 2026-08-22 | One required-context test blocked three PRs in a single evening and presented as TWO different failing assertions. The test asserts at least six separate properties under one name. |
| The same instrument | Diff a baseline node id by node id, never by count. |
| It runs opposite to the flake-note rule | That one guards against OVER-collating; this guards against UNDER-collating. Both are true. |
| Magnitude | Record the magnitude of every occurrence, not just the count. |
| Measured 2026-08-22 on one recurring intake assertion | One occurrence lost **1 of 36** messages, another lost **17 of 36**. Losing 1 and losing 17 are not the same event wearing one name. |
| What the spread says | An order-of-magnitude spread says the arm scales with runner load rather than tripping at a fixed boundary, and it falsifies any fix built on a fixed off-by-one. |
| Gate available | Make the assertion print both counts, so every occurrence carries its own magnitude. |

### 5b-quinquies. Before you re-run a failed leg, read the test NAMES, then pre-register what each outcome means

| Item | Rule |
| --- | --- |
| Name what failed | Read the failing test names first and decide whether a re-run is legitimate at all. **If you cannot name what failed, you are not entitled to re-run it.** |
| Which names are re-runnable | Measured 2026-08-26: `connscale` is a genuine flake at 19% per run. |
| Which are not | `tooling_partition` and `licence_header_gate` are NOT flakes and must never be re-run past. A re-run past a deterministic failure lands a defect on purpose. |
| Pre-register the reading | Write down what each outcome will mean BEFORE you trigger the run. |
| The form | This outcome means flake and I proceed; that outcome means real and I stop. |
| Why | A re-run decided after seeing the result is not a test. Explanation and evidence arrive together and any outcome fits any story. |
| Put it where the result lands | State the rule in the channel the result will land in, so the two sit side by side and nobody has to take your word for which came first. |
| The usual discriminator | Two failures UNLIKE each other are evidence of flakiness. Two IDENTICAL ones are evidence against it. |
| Worked example | A third queue attempt on one PR: "a third DIFFERENT SQL-dependent job failing means runner flakiness and it lands; the SAME test failing again means deterministic and I stop." |
| The outcome | It passed, and the reading was already fixed. |
| Why this earns a section | On the night it was written, every re-run decision across the fleet was made after seeing the result. |
| The shared shape of the two worst broadcasts | The measurement and the interpretation arrived in the same breath, so the interpretation borrowed the measurement's credibility. |

### 5e. Log every CI failure you diagnose -- `docs/CI-FAILURE-LOG.md`, one row per observation

**Owner-set 2026-08-26.** A running record in the repo, so trends become visible and a recurring cause
gets fixed once instead of re-diagnosed by whoever next trips over it.

| Item | Rule |
| --- | --- |
| When to add a row | When you DIAGNOSE a failure, not when you see one. A red check with no cause established is a task, not a row. |
| When you cannot establish a cause | Write `unestablished` in the cause column rather than guessing. A wrong cause there is worse than a blank one, because the next reader builds on it. |
| The `verdict` column is the point | Everything else is transcription. "Test X failed on PR Y" is noise. |
| What the reader actually wants | Whose fault it was, and if not the PR's, what class of thing. |
| Fixed vocabulary | `pr-defect`, `pr-ordering`, `flake`, `infra`, `gate-artifact`, `instrument`, `advisory-noise`. |
| If none fits | Define a new one in the file BEFORE using it. An undefined category is how two readers reach opposite conclusions from one row and neither notices. |
| `instrument` rows matter most | That is CI being RIGHT and a person reading it wrong. |
| Why | A misread leaves no artifact: a confident wrong conclusion and nothing red to find later. Three of the eleven seed rows are misreadings. |
| Correct in place | Fix a wrong row where it stands and say so on the row. Do not add a second row. |
| Why | A log carrying both a wrong answer and a right one, without saying which is which, is worse than either alone. |
| Do not strengthen its stated limits | Rows are observation-selected, so a count taken from it counts LOGGED failures, not failures that happened. |
| What it is good for | "This keeps happening". It cannot find what nobody noticed. Any trend names its window and says the sample is selected. |
| **EXPIRY** | The owner retires the practice, or a job starts generating the rows. At that point the selection-bias paragraph in the file becomes wrong and must be rewritten rather than deleted. |

### 6a-quater. A source-scanning test is coupled to code shape, not to behaviour

This repo leans on scan-the-source heavily -- the leak gate, the doc-drift guards, the mirror and
parity tests -- so this is a standing exposure, not a curiosity.

| refactor | behaviour | the scan |
| --- | --- | --- |
| moves the scanned expression somewhere the scan still reads | preserved | REDS anyway, a false alarm on correct code |
| moves it behind an indirection the scan cannot follow | preserved | stays GREEN while checking nothing |

| Item | Rule |
| --- | --- |
| Measured end to end | A test asserted a render path pipes a live buffer to a CLI over stdin and never re-reads from disk. A refactor moved the call behind a named helper in a second file. |
| The result | The property held perfectly (same buffer, same stdin, no disk read) and the scan, reading only the first file, went red. **The instrument went blind; the behaviour did not change.** |
| The cheap fix is the wrong one | Loosening the pattern until it passes buys a green by discarding the invariant. The check still exists, still runs, and now asserts nothing. |
| The honest fix | The property now spans two files, so the scan follows the chain, with a negative control on each link. |
| Prove the rewritten scan can still fail | A disk read was planted into the source: 600 passing, 1 failing, the right one. Then reverted, and the file verified byte-identical at 601 passing. |
| Why | A guard you have just rewritten is a claim until you have watched it red. |
| The first question on a red | Did the behaviour change, or did the scan lose sight of it? The answer decides whether you fix the code or extend the scan. |
| Getting it backwards | Discards a real invariant while feeling like a fix. |

### 14o. A path-gated CI leg's last green can be arbitrarily old, so "does it fail on main too" may have no answer

The SQL Server and Postgres store legs run only on
`schedule || workflow_dispatch || needs.changes.outputs.serverdb == 'true'`.

When a PR touching `store/*.py` reddens one, the natural attribution check of comparing against `main`
is **vacuous**: the job is `skipped` there and has been for every recent run.

**The honest verdict is UNKNOWN**, not "new in this PR" and not "pre-existing". For a real baseline,
force the leg with `workflow_dispatch` on the base commit. The gate is not lying; it answers *"did the
relevant paths change"*, which is a narrower question than *"is this test healthy"*.
