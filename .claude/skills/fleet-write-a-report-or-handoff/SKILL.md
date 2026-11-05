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
rendered eleven times, and a seat cannot lower its own state by working less
(the retired [STEWARD.md](../../../roles/retired/STEWARD.md), section 4).

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

### The handoff write is armed by a rung

**Owner-set 2026-08-28: do not update your handoff until a usage rung fires.** Write it after rung 1
(HOLD NEW WORK) or rung 2 (PROTECT AND WRAP), and not before. When the window resets, go back to not
updating until another rung 1 or rung 2 fires.

The duty is armed by a rung, not by the clock and not by finishing a task.

**ARMING FIX, RETIRED 2026-10-31.** The rule once armed on a 5-hour rung and the weekly meter had no
rungs, so a night where weekly exhausted first left every handoff unwritten (measured 2026-08-29). A
seat widened the trigger to the binding window within a projected hour or two of exhaustion.

The owner ruling of 2026-10-31 gave the weekly window the rungs and removed the five-hour window
([COMMON.md](../../../roles/COMMON.md), usage). Rung 1 now sees the case the widening was written
for, at the shorter lead COMMON's table sets. **Write at rung 1 or rung 2.**

A seat found the widening by breaking the rule deliberately. It said so in its own artifact's first
paragraph, rather than let a reader guess whether it forgot or overrode.

**The shape is a condition that cannot fire on the path that matters most.** Same family as a
warning that says do not bother checking, and a panel comparing projections against an
already-expired instant. The arming condition was not wrong -- it was unreachable in the case it
existed for.

**When you write a trigger, name the case it must fire in and check the trigger can see that case.**
This rule's stated premise was "the usage ladder is the warning": true then of the 5-hour window,
silently false of the weekly one.

**These cadence rows replace "update the episode note at each change of state", which this file
carried until 2026-08-28.** That rule was written when a cutoff gave no warning.

The usage ladder is the warning now, so continuous updating buys nothing and spends the tokens the
handoff exists to protect. **The retracted version is kept because the reasoning changed rather than
being wrong.** Its premise -- no warning before a cutoff -- was true when written and is now false.

A rule whose justification has expired is not one you weaken; it is one you re-derive.

Worked example, against the seat that wrote this rule: on 2026-08-28 it rewrote its own handoff **six
times** across a single session, most of them well below any rung. Only the addendum written at rung 3
was load-bearing.

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
| Cadence | *The handoff write is armed by a rung* arms it on a usage rung. Do not restate it here. |
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
