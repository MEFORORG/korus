---
name: "fleet-write-a-report-or-handoff"
description: "Write a status panel, cycle report, handoff or episode note. Use before rendering anything the owner or a successor reads."
user-invocable: true
disable-model-invocation: false
---

# fleet-write-a-report-or-handoff

> Shared fleet rules, split out of [COMMON.md](../../../roles/COMMON.md) on 2026-09-05.
> Prohibitions that bind before this task starts stay in that file. Read it first.

### One standing column: "Are you spending my tokens well?"

**Owner-set for the Dispatcher 2026-08-28 and generalised here**, because every seat spends the
owner's tokens. The routing exception in *The owner reads by sampling* is about routing only. The
standing column binds the Manager too.

| Item | Rule |
| --- | --- |
| The useful answer | "No" or "Mixed", with a reason. A standing "yes" means the column has stopped working -- the same failure as a gate that cannot report its own absence. |
| The real health test | A column has stopped working when its cells stop being contradictable, not when they stop saying "no". |
| Keep it to ten words | A verdict plus one load-bearing fact. Owner correction 2026-08-28: those cells become text walls. The reasoning goes in the prose beside the table. A dashboard that has to be read is not a dashboard. |
| Report concurrency, not occupancy | [BUILDER.md](../../../roles/BUILDER.md) owns the rule. Name what is running right now. |
| What does not generalise | A per-builder relay layout, and "are you maximizing the weekly allocation". |
| What DOES generalise, and an earlier version of this row wrongly excluded it | A seat reporting its own concurrency. |

**Why a valence test is not enough.** A model reading its own transcript will always find a plausible
inefficiency, so "Mixed, `<fresh-sounding reason>`" passes forever.

Require the fact to name something another artifact could disagree with: a claim list, a git log, a
lane level, a timestamp. Never a self-assessment of effort.

**Why a slot count is not concurrency.** [BUILDER.md](../../../roles/BUILDER.md): *"Report concurrency, not
occupancy. 'Idle 0, 4 held' counts slots and is blind to this."* A lane running one thing at a time
reports four held.

**Why the relay layout does not travel.** Most seats have no builders to enumerate.

**Why the weekly question does not travel.** The pool is global, so eleven such cells are one reading
rendered eleven times, and a seat cannot lower its own state by working less. See
[STEWARD.md](../../../roles/retired/STEWARD.md), *A percentage is meaningless without naming its
pool*.

**Why the concurrency exclusion was wrong.** It once read "the count presupposes lanes you supply",
which describes the layout and was written as a property of the quantity.

`scripts/coord/lane.ps1` is first-person by construction: *"Record THIS lane's own free-slot
count... THERE IS NO -Lane AND NO -BoxKey PARAMETER, AND ADDING ONE DEFEATS THE WHOLE DESIGN."*

## Hand off so your successor can resume

| Item | Rule |
| --- | --- |
| The split | The role file holds only what stays true. A dated episode note holds live state. *This file holds only what never expires*. |
| Filenames | Name every handoff file `<SEAT>-<YYYY-MM-DD>-HANDOFF-<KIND>[-<slug>].md`. |
| Builder numbers | A builder handoff carries its number, because two builders write the same name without one. |
| Resumable kind | Only the `SEAT` kind is resumable, so write your state there. |
| Header block | Start a seat file with the update time, session, worktree, branch, status and tip. |
| Renames | Do not rename a file that predates the convention. A rename breaks a citation with no error. |
| Derivation | Write the procedure that finds the value, never the value. |
| Stating once, expiry, retraction | *This file holds only what never expires* owns those three. Do not restate them here. |
| Your own ruling expires in a message | Put it in the artifact a reader consults, or expect to contradict yourself within the hour. |
| A do-not-check note | A warning that says "do not bother checking" has no way to self-correct. |

**Why a ruling in a message is not durable.** The seat that made the decision is the one who forgets
it. Put it in the queue file, the item body or the playbook.

Measured: a seat ruled two rows unavailable, then quoted its own stale queue back at a lane as
"AVAILABLE NOW".

**Why a do-not-check note is the worst kind of stale.** Every other stale claim is found by the next
person who checks. This kind disarms the checker.

If you write one -- "not on main yet", "that tool is broken", "the queue is empty" -- attach the
condition that ends it. Re-run it yourself before repeating it.

### When to write a handoff

Write or REPLACE your `SEAT` handoff at these four triggers and at no other time. They were written
under the owner's request of 2026-11-17, "optimize the handoff creation rules". Trigger 1 keeps the
rung from the owner-set rule of 2026-08-28.

| Trigger | The case it must fire in |
| --- | --- |
| 1. Rung 1 (HOLD NEW WORK) or rung 2 (PROTECT AND WRAP) fires | A session that can read its usage, before the window cuts it off. [COMMON.md](../../../roles/COMMON.md), *The three usage states*, sets the rungs. |
| 2. Seat end | Before the session is archived or closed, before an account switch, and before you hand the seat over. No rung warns of any of these. |
| 3. The owner asks, as with `/handoff` | Whatever the rung. |
| 4. Your usage reading is UNKNOWN: once per completed wave, when its pull requests go to the Lander | The case no rung can see. Not once per event. |

A reading is UNKNOWN only after you ran the reader yourself, as `fleet-read-usage` says; a hook
banner alone is not one. A desktop-app session can be one, because the statusLine executor never
runs there. A seat that runs no waves has triggers 1 to 3 only.

**A Builder report, a pull request comment, a decision-log entry or a mail is not a trigger.** A
Builder report belongs on the pull request its Manager opens; the other three already live where a
successor reads them.

**One Manager session rewrote its handoff 19 times** (2026-11-17, carried from its Manager's brief),
each a dated append of state already on pull requests. The rule lived only in this skill, loaded
once a seat is already writing. An UNKNOWN reading had no trigger, so seats wrote at every event.

**RETRACTED 2026-11-17, as the only trigger: "do not update your handoff until a usage rung fires"
(owner-set 2026-08-28).** Its rung is trigger 1, and constant updating does waste tokens. But a seat
can end with no rung, and an UNKNOWN reading never shows one.

**When you write a trigger, name the case it must fire in and check the trigger can see that case.**

The rung rule failed that test once before. Its premise, "the usage ladder is the warning", was true
of the 5-hour window and false of the weekly one. A night when the weekly window ran out first left
every handoff unwritten (measured 2026-08-29).

A seat then widened the trigger to the binding window. The owner ruling of 2026-10-31 retired that
fix by giving the weekly window the rungs.

The rung rule itself retracted "update the episode note at each change of state", written when a
cutoff gave no warning.

Worked example: on 2026-08-28 the seat that wrote the rung rule rewrote its own handoff **six
times** in one session, most of them below any rung. Only the addendum written at rung 3 was
load-bearing.

### Write pointers, and replace the file

Write the whole current state, never a dated append. Draft it in your own worktree, then copy it in
with engine `scripts/coord/handoff.ps1 -Write <name> -From <draft> -Replace`. Use `-Replace` only on
your own file; for another seat's name, the script's refusal names the `-<slug>` fix.

| Part | What it holds |
| --- | --- |
| Header block | As *Hand off so your successor can resume* sets it. |
| One row per work item | Item, branch, pull request, head SHA, next action, and who can move it. A row that needs more than two lines means the detail belongs on the pull request, so link it. |
| Owner decisions pending | Verbatim. A pointer into a session dies with the session. |
| Judgment holds | Labelled as judgment, as *This file holds only what never expires* asks. |

Do not copy review findings, QA lines, test counts or history; they are on the pull request. This
shape is for a `SEAT` handoff. A Builder's handoff carries what [BUILDER.md](../../../roles/BUILDER.md),
*A skill owns the handoff format; five things are builder-only*, lists instead.

**The test: a successor can act on it after one read.**

### Retire what is done

At seat end, retire your own `SEAT` file once every row in it is merged or closed, with engine
`scripts/coord/handoff.ps1 -Retire <name>`. It moves the file to a `_retired-<date>` directory and
never deletes.

A seat that takes over retires its predecessor's file once its own `SEAT` file is written. **Never
retire a live seat's file.**

`-Retire` refuses on any hold and names it, and `-Force` names what it overrode. Read each hold
before you force past it.

**Why.** Carried from the same brief of 2026-11-17: the handoffs directory held 79 files, 2.8 MB,
dead ones among them. The harm is not disk: a stale file reads as a live instruction to an arriving seat.

### Every panel earns its space at the steady state, not at the exception

Owner-set 2026-08-29, to the PM seat, after the owner read two blocks that each spent about 300 words
saying nothing was wrong.

A panel whose common case is "nothing to report" renders three things. A headline, one sentence, and
the command that would prove it. The long form belongs on the arm where the news is real.

The steady state is the arm a reader reads most, so padding costs most there. The test is what a
reader would do with the text. That test is `SDS-3.4` in the engine repo.

This rule borrows it rather than claiming to be covered by it, because SDS-3.4 governs security
prose and a status block is not that.

This binds any recurring output, not only a status board. A cycle summary, a report table and a
standing block in a brief all sit under it.

## This file holds only what never expires; a dated episode note holds live state

| Item | Rule |
| --- | --- |
| What goes in the EPISODE note, never here | Current `main`, the open queue, which pull requests are armed, held or conflicted, held branches and unpushed SHAs, who is blocked on whom, "pick up here" lists, open item numbers, and anything with a session name in it. |
| What goes HERE | A lesson still true after the queue drains: a trap, an instrument that lies, an ordering rule, a boundary of a gate, a measured mechanism. |
| Why the split is load-bearing | A mixed document decays into a TRUSTED document that is WRONG, and the durable half hides it. |
| State it once | State a load-bearing fact once and link to it. A fact restated in three places is corrected in one. |
| Every prohibition carries its expiry | Write beside it what would have to become true for it to stop being right, and how to check. A prohibition without one becomes permanent by default. |
| Retract in place | Keep the wrong version and why it was wrong. Delete the error and the next session re-derives it. |
| Label the KIND of a hold when you hand one over | A mechanical hold and a hold resting on your own judgment inherit differently. Say which yours is. |
| A deliberate hold carries the deferred content verbatim | Not a pointer to it. A pointer into a session's context does not survive the session, and a release condition alone will not reconstruct the text. |
| An open-blocker list names the party that can move each item | Without that column, a blocker only one idle seat can move renders the same as one any seat can pick up. |
| Cadence | *When to write a handoff* sets it. Do not restate it here. |
| Before every handoff, not just every commit | Committing clean and handing off clean are different checks, because `main` moves in between. |
| Tone | The useful handoff sentence is the measured one, not the alarming one. **The cost of being wrong scales with how good the sentence sounds.** |

**Two mixed documents that inverted.** A standing "DO NOT INSTALL" instruction inverted when the
held fix merged. A "no new lanes" freeze was cited back twice as an owner directive that had never
been issued.

**Why a judgment hold needs its label.** In a table beside mechanical rows -- a missing push, an
unowned rebase -- an unlabelled judgment call reads as mechanical and stops being examined.

Write *"this is a judgment I made and should be re-examined, not inherited"* on the ones that are. A
blocker recorded only in a handoff is lost when the handoff ages.

**Why the alarming sentence wins.** *"A silent corruption that passes its own gate"* is a better
story than *"a loud failure you would catch"*, which is why the false version gets written and quoted
onward.
