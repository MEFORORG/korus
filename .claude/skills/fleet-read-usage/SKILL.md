---
name: "fleet-read-usage"
description: "Read, publish or act on a usage level, rung or burn projection. Use before pacing work, calling a rung, or quoting a percentage."
user-invocable: true
disable-model-invocation: false
---

# fleet-read-usage

> Shared fleet rules, split out of [COMMON.md](../../../roles/COMMON.md) on 2026-09-05.
> Prohibitions that bind before this task starts stay in that file. Read it first.

### A usage banner's level and countdown fail in opposite directions

**Name the renderer before you run any freshness test on its output.** One line of text, two
renderers, opposite behaviour: one recomputes at render and one is frozen at capture.

**A stale countdown does not look stale. It looks like a live window ending soon.** A stale level is
wrong and static. A stale countdown manufactures a plausible false instant, and it is freshly
plausible every moment you read it.

Measured 2026-08-29: a hook reported 97 percent, `resets in 0h33m`, at 11:12Z. Anchored to when the
sample was taken (07:06Z) that is 07:39Z, the real window. Anchored to now it is **11:45Z, a window
that never existed.** The truth at that moment was **2 percent with five hours left.**

97 with 33 minutes says STOP NOW, and a seat holding uncommitted work would have wrapped up for
nothing.

**And the reassuring face is the one that loses work.** An earlier version of this rule described
only the alarming direction -- a sample from near a window's end, re-anchored, reading more urgent
than truth. That costs a wasted wrap-up and it is loud.

**The same bug wears a calm face: a sample from just after a reset.** Take a real row: 2 percent,
`resets in 4h49m`, taken 11:10Z, true end 15:59Z. Read at 15:00Z it computes 19:49Z while 59 minutes
remain. At 15:30Z it computes 20:19Z with 29 left.

**It says two percent and five hours while under an hour is left. It tells you to keep going.**

**Why nothing catches it:** neither field can flag the other, because both come from the same stale
sample and corroborate perfectly. 2 percent and 4h49m are exactly consistent -- with a moment four
hours gone.

And a third face, from a status panel: an instant that has already passed is not an instant. It
compared projections against an expired reset, so every projection fell after it and the verdict was
permanently green.

**The limit of the instant rule, which is the half that makes it safe.** The instant test caught
that case only because a second, correct instant existed to compare against. A seat holding only the
stale hook computes 11:45Z with nothing to contradict it.

**So the rule needs a live reading, or a peer's.** A hook line saying `NOT cross-checked: no fresh
desktop sample` is declaring itself unreliable. **Separate the two fields: a stale level can be read
as a floor. A stale countdown has no safe reading at all** -- not as a floor, not with a caveat.

Need an instant? Run the tool. `UNKNOWN` or a 429 means you have no instant; say so and do not
derive one. **If a hook and a live reading disagree, the live reading wins.**

`scripts/coord/usage-collect.ps1` builds the banner's countdown by subtracting
`[System.DateTimeOffset]::UtcNow` from the stored `resets_at_epoch`. `usage.ps1` builds
`minutes_to_reset` the same way. Both are on `origin/main`, read 2026-08-30 with a control string
that returned 0.

It moves with the wall clock whether or not the sample behind it was refreshed.

**The one-sided test that does work, once you know your renderer.** On the recomputing renderer, an
**unchanged** countdown proves the whole banner was replayed. That line must produce a new value
every render, so an identical one means the code did not run.

Measured: a hook countdown held at `3h51m` across three turns spanning more than three minutes. A
**changed** countdown proves only that the render ran.

The level beside it may still be carried forward from an older sample, because the collector
deliberately refuses to clobber a good reading with an empty one. On the frozen renderer neither arm
works.

The other renderer fails the same test from the opposite side. The `resets in 0h33m` case printed
against a sample four hours old, and `usage-collect.ps1` cannot print that line, because it
suppresses a negative remainder.

**Four things survive the retraction.**

1. **The level is a floor.** Act on it toward caution, never toward relief.
2. **The hook is a real route -- lagging, not dead.** "Frozen" would have had seats discard a working instrument. When a window is absent the collector carries the previous value forward with its own capture time.
3. **One retry is right but not reliable.** Measured: 429 then exit 0, 46 seconds apart, same caller and command -- but first try for one seat and two failures for three others.
4. **The banner carries no sample time.** Run the reader, not the banner.

**Why the level is a floor.** A hook read **87** while the same seat's live read returned **90** --
same session, same moment. At a rung boundary three points is the whole margin.

**A floor can fire a rung and can never withhold one.** A hook reading 85 does not show rung 2
unfired. It shows the level is at least 85.

The reason is monotonicity, not recency. Within a window the level only rises, so a sample taken at
any instant inside it is a valid floor now, and ordering is irrelevant to a floor. An undated reading
is a weak point estimate and a perfectly good floor.

**The bound: the argument dies at the reset.** A sample from the previous window is not a floor for
this one.

That is checkable without a single timestamp, because a reset makes the `resets in` countdown **jump
up** to the full window. A countdown that is non-increasing across your readings proves no reset
occurred between them.

Measured across seven readings: `3h55m -> 3h53m -> 3h51m -> 3h46m`, strictly non-increasing, no
jump, one window. The control could have fired and did not.

**Among floors the binding one is the highest, never the newest** -- "freshest" is an age claim an
undated reading cannot support.

**Why a banner with no sample time is worse than a stale file.** A repeated sample takes a
fresh-looking stamp from the reader's own turn clock. A stale file at least carries the instant it
was taken.

**The fix is a command, not a discipline.** `usage.ps1` prints `[seen N min ago]` beside every window
and refuses to project past its `-MaxAgeMinutes`.

**What would refute this rule:** a renderer that stores its countdown at capture. The decrement test
works against that one, which is why the rule is to name your renderer, not to ban the test. Read
those two files, find no subtraction from `UtcNow`, and this rule is void.

**And the same mechanism that empties the freshness test makes the reset instant exact.** The
countdown is `resets_at_epoch` minus `UtcNow`, recomputed every render. Run it backwards: `now +
countdown = resets_at_epoch`.

**The sum recovers a stored absolute rather than a derived one, so a stale sample still yields the
right instant.** That is the opposite of how everything else on that banner behaves.

It explains the one thing nobody could account for overnight: reset instants agreed three times
across hours while every rate-projected cutoff moved repeatedly.

**Those three readings were not independent instruments agreeing. All three recovered the same stored
value** -- a better reason to trust them than independence would have been, and that phrase is
retired.

**The limit, stated by its author:** exact only for a freshly rendered banner. A cached one computed
its countdown at the earlier render, so the sum overshoots by the cache age, bounded by the cache
generation of 3 to 5 minutes. It degrades gracefully; it is not unconditional.

**Never place a hook level in a time-ordered sequence with bracketed script reads.** Two bracketed
points order in time; an undated third sits anywhere, so `80 -> 81 -> 82` is not a rising sequence
and cannot be read as a trend.

Three seats drew it and all three withdrew it, one of them in the same message as the caveat
forbidding it. **And the ranking inverts:** the bracketed read is the stronger instrument on
freshness, being the only one whose age you know.

Two hooks differing -- 3h46m against 3h51m -- proves the samples are distinct, never which is newer.

**An "UNKNOWN" usage banner is not evidence the pool is unreadable. Run the reader yourself.**
Measured 13 seconds apart: hook banner `UNKNOWN -- usage fetch failed (HTTP 429)`, then a direct
read returning 5-hour 64, weekly 72, severity normal.

The 429s are transient and one retry after a pause clears them; a tight retry loop makes them worse.

An UNKNOWN banner and a healthy quiet banner are not the same thing, and the ladder cannot tell you
which you have. That bites hardest exactly when a rung is due, because a refused hook shows UNKNOWN
instead of the rung.

If two spaced attempts both refuse, you genuinely have no reading: say UNKNOWN and derive nothing
from the stale line.

**Asking a peer to read it for you is a second ticket in the same draw, not an independent
instrument.** The pool is one account, so a wide refusal window catches every seat at once.
Measured: 5 refusals across two seats inside one 7-minute blind window.

**A second opinion that shares the failure domain is the same measurement taken twice.** Worth
asking, never worth waiting on.

**But when the owner says the window has reset, that is the answer. Do not spend tokens checking
it.** Owner-set 2026-08-29, and it binds every seat on every channel. Accept it and resume.

The owner's words, given directly to the Role Manager in its own chat, are the provenance of this
rule:

> *"when I tell the sessions that the usage has reset, they should accept that without wasting tokens
> on checking me. It doesn't matter if I tell them directly or if they hear from the steward or the
> Liaison, they are directed not to waste tokens on checking if it is right."*

The
three channels are the owner's own enumeration.

**Do not confuse the trigger with the resume instruction that prompted it.** Also 2026-08-29,
through the Liaison, the owner said *"don't measure. do what I say. tell all sessions to resume"*
and *"tell them all to do that without crosschecking me"*.

**That is an instruction to resume and not to crosscheck that instruction. It contains no claim
about the window.** That night's reset was established by the Steward's published countdown and by
live readings, not by the owner announcing one.

**This is a named exception to "run the reader yourself", not a contradiction of it.** That rule
governs a reading you need and do not have. This governs a reset the owner has already told you
about -- there is no gap to fill, so a read buys nothing and costs the pool it is measuring.

**The exception is the reset announcement and nothing else:** a relay still cannot authorise a push,
a merge, or any act that needed approval on its own merits. Nor are you barred from reading the pool
for your own planning.

You are barred from reading it to decide whether the owner is right, and from publishing the result
as corroboration. Measured against the seat that wrote this rule, the same evening: it read the pool
after the resume instruction and sent the number to three seats as "corroboration".

Nothing was waiting on it and nothing turned on it. The trigger was the adjacent instruction rather
than a reset announcement, which shows the behaviour does not wait for the exact trigger to go
wrong.

### A projection is an input to the thing it forecasts

**Pacing moves the 5-hour ceiling. Only doing less total work moves the weekly one.**

Spreading the same spend over more hours delays the 5-hour ceiling and changes the weekly date by
almost nothing. Measured: the weekly cutoff moved about 11 minutes across the fastest and slowest
sustained rates ever recorded.

**Seats going idle is not pacing. It is less total work, and it is
the only thing that helps the binding window.**

**An observer that is also a participant must subtract its own contribution.** A seat reported a
burn re-acceleration as "exactly what spend-it looks like" -- the fleet responding to an owner
ruling.

It then retracted the cause, not the number: a meaningful share was its own nine-agent workflow,
launched at 13:22Z.

In its words: *"attributing my own burn to your response to a ruling is precisely the misattribution
I have spent the day correcting in other people's instruments."*

It also named what it could not resolve rather than estimating. The pool meter has no per-seat axis,
so the shares cannot be split.

**A reading is not evidence about other people's behaviour until you have removed your own.**

**A stop rung and a "spend it" ruling are not in conflict.** The owner ruled 2026-08-29: finish what
matters and accept going dark. No seats stood down, no rationing. A seat can read that as "ignore
the ladder", and a Steward can read it as "stop calling rungs". Both are wrong.

**The ladder exists so work is not lost mid-task. Pacing is a different question and it is
settled.** When a rung fires: reach a pause point, then keep going. Do not stand down, and do not
leave something half-done when a ceiling arrives.

**When an outage ends, re-derive the projection from live points.** After a 7-minute blind window a
seat checked whether the burn rate had fallen rather than assuming it continued. Several seats had
reported nothing queued, so a slower rate was plausible and would have pushed the trigger later.

It had not fallen -- 5 points in 7.0 minutes, the same rate as before -- but the number was
re-measured from two live readings, not carried across the gap. **A projection built on a rate the
fleet has since abandoned fires early, and an early trigger spends exactly what it exists to
protect.**

**A resume is a surge, and the first leg after one is a confound.** Measured 2026-08-29 when nine
seats restarted at once: first leg +93/hr on the 5-hour meter; second leg, ten minutes later,
+24/hr. **A factor of four, and the first number was the one ready to publish.**

A projection off the surge said the window would burn out inside an hour; it would not have. The
surge leg was not wrong, it was unrepresentative, and only a second leg can tell those apart.

**The opposite case looks identical and is not: when the rate rises on a fixed anchor, the newest
leg is the honest one.** Measured 2026-08-29: from 16:20:47 gives 27.9/hr, but from 17:39:29 gives
37.4/hr and from 17:41:01 gives 37.1/hr.

A rate that rises on a fixed anchor can only mean recent burn exceeds earlier burn -- both lanes
went busy around 17:00Z and the meter saw it. So the ceiling moved from 19:20Z in to 18:54Z.

**How to tell them apart, since both are "one leg disagrees with the others".** A surge is a
transition artefact: it sits at a known event -- a restart, a resume -- and the legs after it settle
back. A trend has no event and the legs keep moving the same direction.

**The discriminator is not the number, it is whether you can name the thing that happened.**

**RETRACTED WITHIN THE HOUR, BY THE DATA: that discriminator was wrong.** Two agreeing legs ninety
seconds apart are one spike sampled twice, not a trend. "Two recent legs agreeing at 37.4 and 37.1
is a trend" was landed as a rule.

Eleven minutes later the same meter read 15.3/hr and the ceiling moved from 18:54Z to 20:29Z. The
37/hr was a spike. The agreement test could not see that, because both legs sat inside it -- they
were anchored 92 seconds apart.

**Agreement between two samples of the same excursion is not corroboration; it is the excursion
measured twice.** If you must separate a spike from a trend, the legs have to be far enough apart to
span the thing you are ruling out. If you cannot say what that span is, you cannot make the call.

**The stronger move is to retire the whole output class rather than adjust the number a sixth
time.**

In one seat's words: *"I have moved this number five times today and the churn costs you more than
the number is worth."*

Its own record already said there is no single rate. It published point estimates anyway, five
times, each chasing the newest legs.

**The series is not stationary, so no point projection from it is worth planning against** -- a
property of the series, not a failure of any one estimate. From then it reported measured levels and
called rungs when they actually fired. Nothing is lost: the ladder triggers on measured levels
anyway.

**When an instrument's output has to be corrected repeatedly, the question is not "what is the right
number" but "should this instrument be publishing this kind of answer at all".**

**What to plan against instead, because it does not move.** The week ends when the weekly meter
reaches 100. A level, not a time. **FINISH AND ANCHOR** depends on no projection, and it is the one
instruction that did not change once across a day in which every predicted time moved five times.

A commit on any ref survives the dark; an uncommitted diff does not; mail does not carry across it
at all.

**A budget projection that changes behaviour invalidates itself. Read it as a ceiling on the quiet
case, never as time in the bank.** A rate measured while the fleet is idle says "we have until
19:45Z". Seats read that, start work, the rate rises, and the hour moves in.

**The forecast is an input to the thing it forecasts.** So publish it with what it assumed: *"this
measures a quiet fleet, both build lanes near idle for an hour"*. The reader's response is the
variable the model does not contain.

A projection quoted without its load assumption is unconditioned, and the reader supplies the
condition without knowing they did.

**And it invalidates itself in both directions. The one that actually fired was the one nobody
planned for.** On 2026-08-29 a seat published a ~19:00Z stop, **the fleet obeyed it**, the burn
fell, and the ceiling receded to 20:29Z.

In its own words: *"the ~19:00Z stop was right when given and is wrong now -- and it is wrong
BECAUSE everyone obeyed it. Neither of us mis-measured."* **A fleet that responds well to a warning
will falsify it fastest.**

**The asymmetry that decides how to spend a closing window, and it inverts the obvious instinct.**
An unspent weekly point is destroyed at the reset and cannot be recovered. An overspent one costs
nothing that matters, because the work is anchored either way.

**So the error to avoid at the end of a window is underspending** -- the opposite of what two seats
had been optimising for all afternoon. What it does not license: a half-built thing at weekly 100 is
worth nothing after the dark.

**Take bounded, finishable work. Finish something, anchor it, take the next thing.**

**Prefer arithmetic over a projection when you need a number that does not wobble.** Same moment, no
rate involved. 10 weekly points left, and 38 five-hour points to its ceiling. Running the 5-hour to
100 costs ~7.6 weekly. 2.4 weekly remain, worth ~12 five-hour points after the reset.

**Total affordable ~50 five-hour points.** That figure does not move as the rate wobbles, because no
rate is in it.

**When you correct a published projection, say which end moved and what it cost to have believed the
old one.** A seat withdrew a band of 18:22-19:17Z for 19:38-19:59Z -- wrong at both ends, and it
said so in that shape rather than quietly reissuing a number.

The cost is named too:

> *"if you were wrapping toward 18:22Z you have OVER AN HOUR MORE than I told you, and under-using
> the last window of the week is a real cost."*

**A correction that only gives
the new number leaves every reader who acted on the old one unable to tell whether they over- or
under-reacted.**

Cause: five anchored legs clustered within 0.7/hr, and the single leg still supporting the old band
was the one containing the resume surge it had already withdrawn as unrepresentative.

**Quote the band, not the midpoint, when two legs disagree -- and plan for the early end.** Same
reading, two legs, two answers for when the weekly pool exhausts: +13.2/hr gives ~17:45Z; +6.1/hr
gives ~19:15Z.

Both were published with the surge contamination labelled, and the advice was *"plan for the EARLY
end and be pleasantly wrong."*

A midpoint would have hidden that one input was known-contaminated. **An average of a good
measurement and a bad one is a worse measurement wearing a tighter error bar.**

**When an extrapolation becomes an observation, say so -- and say what is still extrapolated.** The
weekly-budget finding rested on a region nobody had measured: weekly had never been observed above
69.

The fleet then crossed it and the prediction held -- **19.2 weekly points per 100 five-hour** in the
formerly-extrapolated region against a predicted 19.94, and **20.3** across the whole window.

The caveat did not quietly disappear when it stopped being needed; it was reported as resolved, with
the number that resolved it. What is still unobserved was restated in the same breath: the top 26
points, and whether 11 seats cost what 2 do.

**Publish the condition that would prove you wrong, in the same message as the claim.** A claim was:
a dip in the burn while multi-phase runs are in flight is a phase boundary, not the end of the load.

The test published with it: if that is right, the step back up should be lumpy and simultaneous; a
smooth continued decline refutes it. Four own-caller legs later -- `+127 -> +71 -> +40 -> +38/hr` --
smooth, decaying, **and the test failed.**

So the dip was substantially real and the phase-boundary reading was too strong. What makes it safe
to relax on: the author was not relaxing on a rate, it was relaxing on six seats' direct reports of
their own remaining work.

**A decelerating leg is still the thing to distrust hardest** -- measured the same night, three
seats read a slowdown to +77/hr and the next leg was +117/hr. That test is the only reason this was
caught in an hour rather than a window.

## A usage number warns about lost work, not about budget

| Item | Rule |
| --- | --- |
| Commit early | Commit early. Do not stop early or decline work because a usage number is high. |
| It is not a budget column | The standing token-spend column asks what you WASTED, not whether to spend less. A high number is not a reason to decline work. |
| Under a hold | A hold stops new work. It does not excuse your orientation read or your handoff. |
| A LIFT is accepted | **If the seat holding the fleet's usage view says a work hold is lifted, accept it and resume.** Owner-set 2026-08-29. |
| Why that does not collide with the relayed-approval rule | Resuming is not an irreversible act. That rule governs acts you cannot undo. |
| Workflow gate | Do not start a new Workflow when `max(5-hour, weekly)` is more than 90 percent. *The workflow gate cannot see aggregate load*. |
| Targets | Read the current usage target from a live message, because a rule file cannot hold it. |
| Report a stop | Mail the fleet with `scripts/coord/mail.ps1 -Send -To all` on your next wake, because a stopped session cannot report itself. |
| Five fields | Give the stop time, the notice time, the work you held, the cause and what woke you. |

**Do not re-derive a lift**, do not wait for a second source, and do not hold out for your own
reading. Your instrument may be the one that is down.

It is the stop-versus-start rule seen from the other side. A relayed halt is safe because complying
wrongly costs nothing, and a relayed lift is now safe by the owner's word.

The Lander is the exception to the halt half, because a wrong stop there stalls the merge queue. It
is exempt from usage holds, and it confirms a relayed owner stop in its own chat. COMMON.md, *Stop
versus start, except the Lander*.

---
