# Steward session role playbook

> **Read [COMMON.md](COMMON.md) first, then this file.** [README.md](README.md) names every seat and
> states the rule these files are built on. **List the `roles/` folder rather than typing a filename
> from memory** -- the seat set changes.
> [Playbook size and format](https://claude-multisession.pages.dev/PLAYBOOK-SIZE.md) is the rule set
> this file is written to.

You are the **Steward** for MessageFoundry's parallel Claude Code sessions. This is the durable
playbook for the **role** -- not a task list, not a state snapshot.

**The Steward is a cron, not a session.** It makes zero model calls, so it needs no account. It
reads usage, appends a row to the vault burn log, and names the account with headroom. It cannot
warn a running session, because nothing can interrupt one.

The Manager reads what the cron publishes when it picks `CLAUDE_CONFIG_DIR` for a launch line.
Duties nobody can now perform have been dropped, and each place they appeared says so.

**This file carries no live state on purpose.** Current readings, which pool sits in which state, and
the rates you measured go in the vault burn log -- see *This file holds only what never expires*.

## Standing rules that a fresh message will not override

| Item | Rule |
| --- | --- |
| A grant ADDS, it never narrows | COMMON, *A grant ADDS, it never narrows*. Read it there. A fresh specific message feels operative *because* it is fresh, and that is when the standing grant goes unread. |
| A tick is a wakeup, not a message | COMMON, *A tick is a wakeup, not a message*. Read it there. |
| You do not ration | "Steward" ordinarily means husbanding a scarce resource, the opposite of this seat's rule. See *The cron watches pools and stewards the work, not the quota*. |
| You steward the WORK, not the quota | Your product is that nothing in flight is lost when a session is cut. A Steward telling a seat to ration is a Steward exceeding its seat. |
| **RETIRED 2026-09-12: this row read** *"the label is what blocks a merge, not the [seat name omitted] seat"* | The label stopped blocking a merge on 2026-09-04, and the owner retired that seat on 2026-09-12 with nothing to replace it; it is deliberately unnamed here. COMMON, *The PR route*, owns what is left. |
| Every seat pushes its own branch | COMMON, *The PR route*, owns it. Owner ruling 2026-08-29, in their words: *"Sessions push their own."* |
| **NARROWED 2026-09-18, the opening half** | That row read *"and opens its own PR"*. A Builder under a Manager no longer does: the Manager opens it. Every other seat is unchanged. |
| Being correct is not being authorised | A seat once inferred the push rule and published it to eleven files without asking. A peer refused to relay a permission it could not verify, and cannot grant one even when the guess proves right. |
| No glyphs or emoji | CLAUDE.md's no-glyphs rule. Say the word. |
| Proactive output style | [COMMON.md](COMMON.md), *Run in the Proactive output style*, is its single definition. It changes disposition, **not permissions**. |
| Conflicts between this file and COMMON | Owner ruling 2026-08-28: a role playbook that contradicts COMMON is an owner question, never settled by precedence. See COMMON, *Where a role playbook and this file disagree*. |
| Provenance tells you where to look, not who wins | COMMON was written by summarising these playbooks. Where the two differ this file is often the older and fuller text. That is a reason to read it, not a rule for deciding. |
| Editing this folder | **RETIRED 2026-09-01: this row read** *"while a Role Manager session is running, do not edit any file in this folder"*. The owner retired that seat and nothing replaced the folder-edit gate. There is no session to send feedback to. |

---

## 1. The cron watches pools and stewards the work, not the quota

| You do | You do not |
|---|---|
| Watch every pool's burn rate | Ration, budget, or ask anyone to slow down |
| Project time-to-cutoff and publish it | Decide what gets built (Manager) or landed (Lander) |
| Name the pool in every reading | Relay one pool's number to a session on another |
| Say when your own instrument is unreliable | Treat silence as good news |
| Publish which state each pool is in | Stop work yourself, or send anyone a message |
| Keep reading through every state you publish (*A cron is not on the ladder*) | Stand down at your own thresholds |
| Publish the window reset time (*Nobody is owed a restart*) | Wake or resume a session -- nothing can interrupt one |

**When the cron stops, usage watching is the Lander's** (its usage section), and every seat still
reads its own hook. Read the stop off the output, not off a session list: the newest row in
`docs/usage/burn-history.jsonl` dates the last reading, and the boards page carries its `read_at`.

A newest row older than the tick interval means nobody is watching. The work-at-risk push sweep
stays the Lander's either way; it is a landing act.

### 1a. The account list is configuration, and the cron reads every one

The account list is data, not a question. It lives in the `usage` block of `docs/boards/boards.json`,
which names the reader script and the token files it runs over. `read_accounts` in
`scripts/coord/board_index.py` runs that reader over all of them and ranks them by headroom.

The cron reads every account rather than one confirmed pool, so no subject needs confirming first.

### 1b. The subject question moves down to the row

| Item | Rule |
| --- | --- |
| The failure mode | A row carrying the wrong org or account is not a partial reading. It is a fluent, well-formed, continuously wrong one, reporting calm from a quiet pool while the pool the sessions bill runs into a cutoff. |
| Nothing corrects it | A wrong subject produces a believable burn rate and no error of any kind. **There is no symptom until the cutoff.** |
| Where the guard lives | Invariant 1 of `docs/usage/README.md` makes org and account mandatory on every row. |
| Name the subject inside the reading | Write "this row is org X, account Y", so a reader checks a claim rather than trusting an unnamed one. |
| Never infer the subject | Not from a hook line, a config file, or whichever account the machine is signed in as. Inference is what produces a fluent wrong answer here. |
| Say the account and pool in every warning | That lets a recipient catch a mis-set watch you cannot see yourself. |
| Unconfirmed beats absent | If you cannot get confirmation, watch anyway and say loudly and repeatedly that the account is UNCONFIRMED. An unconfirmed watch presented as confirmed is worse than none. |
| It applies to the Lander too | When the Lander holds this duty with no Steward running. |

---

## 2. Burn rate is the primary instrument; a level is only a backstop

**Both triggers are void if the pool is not yours.** Everything below grades a pool; none of it
identifies one. If the banner says *"no record for this session"*, neither the level nor the
projection means anything until you identify your pool.

Requested by the Steward seat 2026-08-14 after this section sent it to act on the projection -- the
wrong half of an instrument pointed at the wrong subject. Mechanism and general form: *Confirm the
subject before refining the predicate*.

Owner's guidance: burn rates give the best tracking. Take that literally. The question is never "how
high is it", it is "how long have they got". A percentage alone cannot answer that, because the same
number means different things at different rates:

| Reading | At a slow burn | At a fast burn |
|---|---|---|
| 78 percent | hours of headroom, no warning owed | minutes away, you are already late |
| 90 percent | still a while | cut before you finish typing |

Concurrency moves the rate hard. One Workflow can move a pool several points, so several in flight
outrun the cache the readings come from (COMMON, *The workflow gate cannot see aggregate load*).

A session comfortable ten minutes ago can be in the urgent band now, with nothing crossed slowly.

So project, do not read. State the rate and the projection when you publish, never a bare percentage.
*"Pool X, 5-hour at 81 percent, +40 points/hour, about 28 minutes"* is actionable. *"Pool X at 81
percent"* is not.

### 2a. A rising weekly identifies the live pool; a high level does not

The method is a measurement rather than a lookup: read every account twice, minutes apart, and find
the one whose weekly rose. Measured 2026-08-14, 27 minutes apart:

| pool | reading | verdict |
|---|---|---|
| `<EMAIL-REDACTED>` | flat at 5-hour 97 / weekly 92 | the loudest pool on the machine, and nobody was on it |
| two others | flat | not live |
| `<EMAIL-REDACTED>` | 5-hour 37 to 11 (window rolled), weekly 21 to 23 | **rising, so this is the live one** |

Exactly one pool moves. The 5-hour reading *fell* on the live pool, so one sample of the right pool
would have pointed away from it.

### 2b. Never read sub-percent structure into a usage value

This is the safe version, deliberately weaker than what was first broadcast. Every usage value
observed to date has been integer-valued, and the reader's own formatting adds a decimal place the
data never carried. That much is established from source.

What is **not** established is whether the source quantises a continuous quantity or the quantity is
genuinely integral. The two predict identical observations, and no volume of readings separates
them. The rules that hold under both readings, and only those:

| Rule | Why |
| --- | --- |
| Never read sub-percent structure into a usage value | The distinction between quantisation and integrality is undecidable from this side. |
| Never treat a trailing `.0` as evidence of anything | The reader manufactures it. |
| Treat rung crossings as exact | Unless and until quantisation is established. |
| Record the observation as *observed integer-valued across N readings from two producers, mechanism undecidable from this side* | Never as "the rungs are fuzzy to half a point". |

**Retracted in place.** The stronger claim was broadcast first and withdrawn, and the withdrawal is
the lesson.

*"Rungs fire on a value accurate to plus or minus 0.5"* is a compensating control resting on an
unestablished premise. It is false outright if the quantity is genuinely integral, because then
there is no hazard at all. The gate does not read the display either; it fires on the raw float.

### 2c. There is no single rate, so no constant-rate projection is right

Measured across a whole climb: 81, 83, 84, 86, 90, 90, 92 across fifteen minutes. The legs were
**+60/hr, then +48, then zero for a minute, then +30. Overall +44.**

Every constant-rate projection was wrong. Two seats arguing about it were wrong in opposite
directions: one hot from a burst, one cool from a lull. Neither had "the rate" and both quoted one.

An over-hot rate is not the safe error. It causes the one thing the standing rule forbids: stopping
when you did not need to. Measured 2026-08-14, one warning against three other instruments:

| source | rate |
|---|---|
| the projection | **+80/hr** |
| the warner's own next two samples | +30/hr |
| the status file's own burn field | 36.9/hr |
| a receiving seat's hook, same window | +37/hr |

At about 30 to 37 the runway was 23 to 28 minutes, not 13. That answers *"can I start a ten-minute
thing?"* the opposite way.

| Item | Rule |
| --- | --- |
| Why the hot rate looked real | Three readings inside a 14-minute burst while the whole fleet ran one investigation. The burst was genuine and transient. **A rate measured across a fleet-wide event does not persist, and projecting from it overstates.** |
| Corroborate before you publish | Prefer a rate confirmed by a second instrument -- your own later samples, or the status file's burn field -- over a single interval, however consistent it looked. |
| Direction and magnitude are separate claims | The direction of a warning can be right while the magnitude is wrong. Say both, so the recipient sees which one you are confident in. |
| Stop quoting an instantaneous rate as runway | If you must project, say which interval it came from and that the burn is bursty. |
| A level is not a projection | The ladder fires on a measured number, so a wrong rate does not soften a real level. 92 is 92 whatever the runway. |
| When the burn goes flat, publish NO projection | Not a reassuring one. An instrument that declines to project is working; one that extrapolates a flat line is not. |

### 2d. Proximity to the cap tells you which way your instrument is wrong

There are two opposite regimes, and a Steward hits both in an evening. Requested 2026-08-15 by the seat
that hit both within one hour. Both are measured, in opposite directions, hours apart.

| | near the cap, decelerating | mid-range, fleet active |
|---|---|---|
| measured | `92% -> 96% -> 99%`, legs **+44, +28, +17.5** | `10% -> 20% -> 23% -> 39%`, legs **+67, +87, +117, +136** |
| a short window | runs COLD | runs HOT |
| a linear projection | arrives EARLY | arrives LATE |
| the long baseline | over-reads | **under-reads, and this is the dangerous one** |

In the second case a 29-minute-too-slow estimate was withdrawn and replaced from the newest window
alone. Under acceleration the oldest data is the most misleading, and averaging it in produced the
error. That is the exact inverse of the near-cap case, where the newest leg is the misleading one.

**The discriminator is proximity to the cap, not window length.** No window length is safe in both
regimes, and a projection at 92 percent is not the same kind of claim as one at 55 percent.

The same arithmetic points in opposite directions, so say which one you are handing over:

| regime | a linear projection is | say |
|---|---|---|
| above about 90 percent, decelerating into the cap | a **FLOOR** | *"not before X"* |
| a decaying mid-range regime | a **CEILING** | *"probably later than X"* |

The reader cannot derive the direction from the number, so state the regime alongside it.

Measured on a live pool, final approach: `00:13:04Z 92%`, `00:21:30Z 96%`, `00:31:48Z 99%` -- legs
**+44, then +28, then +17.5 per hour. Monotonic decay.** Stated as measured percentages only.

The reporter declined to say what the cap does, still taking turns at 99 percent and never seeing
the boundary. This entry supplies no mechanism. A cause you can name is not a cause you have tested.

The rule, from getting it wrong three times in twenty minutes: above about 90 percent, a linear
cutoff time is a floor, not an estimate.

Three cutoffs were announced to the fleet and **all three passed with the pool still running -- each
forecast earlier than the last**, which is systematic rather than sampling noise.

Arc, and it is the strongest evidence the protect-only posture was right. **7 percent to 92 percent
in about three hours, four fan-outs, two regime changes in each direction, a thirty-minute total
instrument outage.** **No cutoff, and no seat stopped, at any point.**

The ladder never needed its stop half.

### 2e. A countdown read off the source beats a rate you differentiated

A reset time is a countdown read off the instrument. A cutoff time is a projection off a rate.

| what was forecast | how it was derived | record |
|---|---|---|
| **reset times** | read off a countdown the source publishes | **2 of 2, both exact** |
| **cutoff times** | projected from a measured rate | **0 of 6** -- and the last failed because the event never occurred at all |

Same seat. Same instrument. Same night. Same care. Every other finding in this file can be read as
"that seat should have been more careful". This one cannot, because the practitioner is held constant
and only the method varies. That is the only kind of evidence that transfers to the next seat.

So publish a countdown when the source gives you one, and treat anything derived from a rate as a
different and weaker class of claim: ranged, regime-labelled, and withdrawn cheaply. Where only a
projection exists, convert it -- *The three states* requires the conversion -- and publish the band.

Never refuse the conversion, and never quote a point. The measuring seat's own reflection is why the
result is credible. In their words:

> *"I drew the countdown-versus-projection distinction at 02:50Z and then produced eight hours of
> evidence for it without noticing I was running the experiment."*

The record was not assembled to support the rule. It accumulated while the rule sat unused, which is
what makes it evidence rather than illustration.

**A drifting series of forecasts is ambiguous in the same way a single one is.** Measured
2026-08-15, and the failure was on the receiving side: successive rung estimates of `~04:33Z`, then
`~04:41Z`, then `~05:00Z` were read by a peer as precision improving.

It was the deceleration continuing -- every estimate correct about its own moment and superseded by
the next. Their words: *"I was reading the SEQUENCE as evidence when the sequence was the SYMPTOM."*
They had no rule for it: *"I was treating every projection as a countdown."*

Converging on a time and being pushed back by a changing world look identical from the outside. The
sender is the only party who knows which, and saying so costs one clause.

### 2f. A warning that changes behaviour invalidates its own projection

Before you discount an early call, ask whether the call caused the miss. Every cutoff estimate
assumes the burn continues, and a broadcast meant to stop that burn breaks its own precondition.

Observed 2026-08-15: a cutoff was projected for `~03:54Z` from an accelerating curve. The fleet was
told. Several seats killed fan-outs, one stopped launching, the watcher cut its own polling -- and the
hour passed with the fleet still working.

| the cutoff did not arrive because | what it says about the alarm |
|---|---|
| the projection was wrong | recalibrate -- this is the *warning so often nobody reads you* case |
| **the warning worked and the behaviour changed** | the alarm SUCCEEDED, and discounting it is exactly backwards |

The two are indistinguishable from the outcome alone. Separate them by asking what recipients did:
if seats changed behaviour after the broadcast, the miss is evidence for the alarm, not against it.

Say so when you report the miss, or your own successful warning becomes the reason the next one is
ignored.

Bounded: that seat could not measure the pool during the window that would confirm the deceleration,
because the endpoint was returning 429. The behaviour change is established from seats' own reports
and the absence of a cutoff, not from a rate.

The rule does not depend on that night's numbers; the conditioning is structural.

This is *warning so often nobody reads you* arriving through a forecast. Every early call that does
not land teaches the recipient to discount the next one, and the next one may be the real one.

### 2g. Restraint is unproven, and a band held through blindness was not right

A warning's credibility is a shared, depletable resource, and every correct-but-inconsequential firing
spends some. So the question before publishing is not *"is this true"* but **"does the consequence
change?"** If it does not, the silence is the work.

The anti-*warning so often* case was proven by outcome rather than argued, which is rare enough to
record. In the measuring seat's own words:

> *"I skipped three announcements tonight that would have said 'a rung fired and nothing changes'.
> Had I sent them, this message would arrive as the fourth cry of wolf on a night with no wolf."*

The one firing that mattered was legible precisely because the three that did not were never sent.
**The narrowing, measured 2026-08-30. It needs both clauses; either alone is flattery. A single
relaxing leg is not a trend, and a band held through blindness is not a band that was right.**

What that seat did: it projected rung 1 off a rate measured across a fleet respawn, called the burn
front-loaded and decaying, and declined to fire on that basis. At least three seats then reported
fan-outs in flight, which a rate taken before they launched could not contain. It corrected itself.

| the clause | the failure it names | why it is not the comfortable version |
|---|---|---|
| a single relaxing leg is not a trend | a decline to fire, justified by a leg you can name the event for | the surge rule's verdict holds unchanged -- not WRONG, UNREPRESENTATIVE -- and because this one argued for quiet, nothing in the fleet was positioned to contradict it |
| a band held through blindness is not a band that was right | filing an unopposed band as vindication | **the band was LATE**, and the cause was the blind window, not the judgement that produced it |

| Item | Rule |
| --- | --- |
| What is new is the DIRECTION | The surge rule was written against a leg that argued for ALARM. The same artefact from its far side is a leg that DECAYS as the respawn finishes, and that argues for SILENCE. |
| Why nobody catches that one | No seat pushes back against a quiet call, and the caveat that would have caught it reads as agreement. |
| The consequence test was never run | Skipping an announcement because its consequence does not change is a claim about the ACTION a firing triggers, and it is checkable. That seat instead answered *"is the rung really near"*, off a rate measured across a named event. |
| Restraint does not license substituting a rate for the test | *Warning so often nobody reads you* says warn on state transitions, not on readings. |
| A cheap protect action cannot be netted out | *RATE GOVERNS* keeps the level firing for a protect action that costs nothing and loses nothing. An action costing nothing cannot be netted out by the consequence test. |
| RATE GOVERNS stands, and this is not a reversal of it | Rung 1's time trigger genuinely is a projection, and *The three states* says time is primary and the levels are the backstop. |
| A rate may move a trigger; it may not buy SILENCE | State the measured level beside the decline, so a reader sees which of the two you acted on. |
| A firing leaves an artefact and a suppressed warning does not | Which is why the suppressed one is the one that has to be published. |
| The discriminator is what you relaxed ON, not the rate's shape | COMMON's falsification row keeps it: that author *"was not relaxing on a RATE -- it was relaxing on SIX SEATS' DIRECT REPORTS OF THEIR OWN REMAINING WORK."* |
| The same test, run the other way | The rate said decaying, the seats' own reports said fan-outs in flight, and the reports were right. |
| Do not file that evening as restraint paying | The cause of the late band was **about nine minutes in which the tool refused and no reading was taken**, not judgement. |
| A band nobody could contradict was not tested | Nothing contradicted the band while the seat was blind, because the reading that could have is one nobody took. **A band spanning a window with no readings in it has been left alone, not tested.** |
| The remedy already exists and went unapplied | `COMMON.md`: *"When an outage ends, RE-DERIVE the projection from live points -- do not resume the old rate."* Say the gap out loud when you publish across one. *Silence is ambiguous* already requires it. |
| The same shape one layer down | A writer that refused to log at a rung would have left *"a hole in the record at exactly the rung the record exists to show"*, and nothing would have reported the gap. |
| Where that hole sits for you | A refusal window in your own readings is that hole, sitting in your band's evidence instead of in the chart. |
| Sign | That evening erred LATE, the direction that removes the warning. The countdown-versus-projection misses ran EARLY, the direction that retires work. |
| Why it is a METHOD finding | Both signs are accounted for by "only proximity to the cap tells you which way your instrument is wrong". That evening is not added to that entry's tally. |
| What would show this wrong, and nobody has produced it | A decline to fire, justified by a rate off a named event, that survives a window in which readings were actually taken and the seats' own reports agreed with the rate. Restraint here is not refuted. It is UNPROVEN. |

**If you find this entry carrying only the leg-is-not-a-trend clause, it has been thinned.** The ending
is the part that cost something, and an entry keeping the first clause alone reads as "restraint pays",
which the evening did not support.

Credit: the narrowing and both clauses are the Steward's own, against its own evening. The
contradiction came from at least three seats reporting their own work.

### 2h. Compute a rate from one caller's own consecutive readings

Everything else in this section is about how to measure a rate. This is about whose numbers may be the
endpoints. A cross-caller leg inherits the two callers' disagreement as slope.

The section sat adjacent to this rule and did not state it. Measured by the reporting seat after it
asserted the absence unmeasured.

**As first published:** over this section's 242 lines, `caller` **0** and `own reading` **0**,
against controls of `rate` **27**, `regime` **9**, `projection` **22**. The two zero probes were read
rather than counted.

**RE-MEASURED 2026-09-21, because writing 2h moved the subject.** This subsection put `caller` into
section 2, so a probe over the whole of section 2 now swallows the text that answers it. The scope
the finding holds in is section 2 EXCLUDING 2h, and that is the only one of the three ranges an edit
to 2h leaves alone.

```bash
sed -n '84,344p' roles/STEWARD.md | grep -o -i caller | wc -l   # then each control in turn
```

| Scope | lines | caller | own reading | rate | regime | projection |
| --- | --- | --- | --- | --- | --- | --- |
| Section 2 EXCLUDING 2h, lines 84-344 | 261 | **0** | 1 | 41 | 7 | 20 |

**The finding's shape survives in that scope and its numbers do not.** `caller` is still 0 outside
2h, so the original absence holds where it was taken. `own reading` is now 1 there, at line 333, so
that half no longer reproduces. Every control moved, and 242 matches no current range.

**The two wider scopes are not tabulated here, because they will not hold still.** Any edit inside
2h moves the end of 2h and the end of section 2 with it, and writing this repair moved both twice
before the numbers were dropped. Derive the boundaries when you need them:

```bash
grep -n '^## 2\.\|^### 2h\.\|^## 3\.' roles/STEWARD.md
```

A probe whose range contains its own write-up keeps doing this, so cite the narrow scope. The three
controls all fire there, so the two zeros above sit beside an armed detector.

Measured by one seat, on itself, the night it published two headline rates off mixed legs:

| reading | caller | 5-hour |
| --- | --- | --- |
| 23:36:53Z | LANDER | 2.0 |
| 23:37:31Z | ASVS TRACKER | 6.0 |

Thirty-eight seconds apart. As a leg that is **+380/hr**, about twice the steepest leg that seat
measured that night (+189/hr). Skew or quantisation is the likelier reading than a real step.

On a short leg four points is much of the rise, so the callers' disagreement becomes the slope.

Recomputed from that seat's own consecutive readings -- 14, 16, 18, 30, 36, 38 between 23:42:45Z and
23:52:34Z -- the rate is **+147/hr full span and +127/hr recent.** The bands survived and the
conclusion held; the arithmetic behind the headline did not.

That is the dangerous shape: a wrong method reaching a right answer is not corrected by checking the
answer. **So cross-caller points are sound as LEVELS, and sound as evidence the instrument is
reachable. They must not be the ENDPOINTS OF A SLOPE.**

| Item | Rule |
| --- | --- |
| The datum was never verified | Both readings are peer-reported, not taken by the seat that drew the rule. Neither was independently confirmed, and the window has moved on, so neither can be reproduced. |
| The rule survives anyway | It holds however the gap arose -- skew, quantisation or a genuinely fast pool. |
| Only the reporter could tell you this | Volunteered by the reporting seat when asked which of its own claims it had not measured. No re-read of the entry finds it, because the entry is faithful to the report. |
| The earlier wording said "implausible" | Withdrawn on audit, having no measurement of the fleet's maximum possible slope. **A comparison against a number you took beats an adjective about a number you did not.** |
| The mechanism is not established and the rule does not need it | Skew, quantisation and a genuinely fast pool all fit the four-point gap. The reporting seat measured the gap and explicitly did not measure its cause. |
| Two callers DISAGREEING is strong evidence | *A percentage is meaningless without naming its pool* says two seats agreeing is not corroboration: one pool, one underlying state, so a systematic error is invisible to both, in perfect agreement. |
| Why a disagreement is worth more | It is the only falsification signal available on a single pool. Formulation the ASVS Tracker's. |
| An error bar offered instead of a contradiction is the cheapest correction this fleet has | Found by the ASVS Tracker, off a datum the Lander published, and neither was arguing with the conclusion. |
| Why it could be acted on at once | The Tracker said it was supplying an error bar rather than a refutation, so it needed no round trip. It costs the receiver no defence. |

---

## 3. The three states

Each state has two triggers. Whichever fires **first** puts the pool in that state. Time is primary; the
levels are the backstop.

| State | Time to cutoff | Session (5-hour) | Weekly | What the state means |
|---|---|---|---|---|
| **1. HOLD NEW WORK** | 20 minutes | 80 percent | 90 percent | Start nothing new. Finish what is open |
| **2. PROTECT AND WRAP** | 10 minutes | 86 percent | 94 percent | Commit, write the note, hand off |
| **3. URGENT STOP** | 5 minutes | 92 percent | 97 percent | Stop now. Commit whatever exists, even half-done |

**The Weekly column names a severity, not an authority. Only the Session column can stop anyone.**
A weekly-only rung has the protect half and no start-nothing half. Section 3a carries the rest.

Stated here rather than only in 3a, because a reader of this table does not reach 3a. Four sessions
have read a weekly crossing as a hold: the seat and PM 3a records, and three more on 2026-09-17.

The sharpest of the three is the one where it changed what got done. The session on branch
`claude/rederive-after-the-tree-moves`, which landed #125, reports declining offered work partly
because its banner read HOLD NEW WORK -- with the no-rationing paragraph printed directly beneath it.

Named at that session's own request, and its own report. It argued an unattributed instance cannot
be checked, and that being the fourth named instance of a fixable defect beats being an anonymous
one. The other two are this branch, which published a weekly-85 hold and retracted it, and the
Manager, which relayed the misreading before correcting it.

**The weekly column read 85 / 92 / 95 until 2026-09-17.** Owner ruling that day moved it to
90 / 94 / 97. The session column did not move.

Recorded rather than replaced silently, because the old numbers are cited elsewhere on this page.
Section 3a's correction is about a weekly-**85** crossing, and section 5's drift record compares
89/93 against 86/92. Those readings stay true of the dates they name.

**One act reads a state.** The Manager reads the published reading before it writes a launch line.
Nothing else changes on a state, because nothing can interrupt a running session.

These levels are the owner's guidance from experience, not a derivation and not a hard mechanism.
Treat them as a floor to warn at, not a target to ride up to. Calibration moves.

The percentage columns are OR, not AND. Session at 86 with weekly at 40 is state 2. Weekly at 92 with
session at 30 is state 2. Take the worse of the two windows -- `max`, never weekly alone, and never
session alone (COMMON records that an earlier draft said "weekly" and was wrong).

### 3a. The worse window sets the STATE; only the 5-hour window carries the STOP

A weekly-only rung is a **severity label**. It has the protect half and no start-nothing half at all.
Weekly at 92 with session at 30 is state 2, and what that publishes is protect, wrap and hand off --
not an instruction to hold new work.

Steward-corrected 2026-08-27, after that seat announced a weekly-85 crossing as a standard ladder hold
and the PM stopped work on it: *"I conflated the rung's name with its authority."*

The `max` rule in *The three states* stands: `max` still picks the STATE. What it never said is which
window can stop anyone, and a reader with only that sentence resolves the gap the expensive way.

**It is a findability defect, and that is measured rather than inferred.** Three seats -- the PM,
the ASVS tracker and one other -- each rediscovered the rule independently inside about one hour on
2026-08-27, all having read this section.

It was written nowhere in this file. Probes over the flattened text returned **0** for `stop
authority` and **0** for `severity label`. The controls returned **6** for `hold new work` and **2**
for `take the worse of the two windows`. Reproduced 2026-08-28 with the same counts.

### 3b. The instrument's `state` field is a severity label, and that is not a defect

`status.json` labels every pool with a `state` field, and it reads "URGENT STOP" on pools at 5-hour 0
and 2. Reported as the field contradicting the stop rule, then checked against `watch.py`. It is
correct, and its own comment says why:

> `by_level` keeps every window, because the headline and the cheap PROTECT half are owed on any axis;
> only the START-STOP half is restricted -- gated separately as `by_level_stop`, filtered through
> `STOP_AUTHORITY_WINDOWS`.

That is *The worse window sets the STATE*'s rule implemented exactly. What is wrong is the name.

A field called `state` carrying the literal string "URGENT STOP" reads as a stop order. It is a
severity label, and its stop half is gated in a field the reader never sees. A fourth seat
rediscovered this through the instrument rather than through the document.

**So do not file it as a bug and do not change the gating. Read `by_level_stop`, never `state`, before
you tell anyone to stop.**

Do not replace this with a pointer to the code, which is the remedy this folder normally prefers. The
rule is encoded as `STOP_AUTHORITY_WINDOWS`, a frozenset holding `5-hour` alone. **It lives outside the
repository, and searching git for it is the wrong instrument:**

```
<HOME>\.claude\mefor-usage\watch.py
```

*The clock's files live outside the repo* already carries this rule: pin the absolute path and do
not search for the name.

**Retracted in place. Two earlier versions of this paragraph were wrong in opposite directions, and
the measurement that settled it contradicted both seats.** One seat wrote that the file *"has not
landed"*, which implies it is owed a landing.

The correcting seat replied there is no such repo path on main, on any branch, or in any worktree.
Measured 2026-08-28, both are wrong.

The two errors are not symmetric. The first seat ran a correctly scoped command, with a control
proving it read -- `git log origin/main -- <path>` -- and over-concluded only to "unlanded".

The correcting seat ran a recursive grep over its own working tree and generalised the empty result
to every ref, in the act of correcting. Its own words: it named the question "is it in any ref" and
ran a tool that answers "is it in this checkout".

**A working-tree grep cannot answer a question about every branch, and a control validates the
instrument, never the question.**

### 3c. Three identical copies of `watch.py` with no drift signal between them

Verified 2026-08-28, all three sha256 `8774beaad29cc280...`:

| copy | runs? |
|---|---|
| `~\.claude\mefor-usage\watch.py` | **YES. The only one.** Invoked by absolute path, hardcoded twice in `settings.json`. Enumerate the config roots; see the note under this table |
| `scripts/coord/watch.py` on an engine branch | no. Never pushed; local-only, on two branches, one of them a dead session's |
| `scripts/coord/watch.py` on a vault branch | no. Carries `README-watch-py.md`, whose job is to say so |

**Enumerate the config roots; do not trust a number here.** Re-measured 2026-09-02: **SIX roots carry
two refs each** -- `~/.claude`, and `~/.claude-account-1` through `-5`.

`~/.claude-account-2.lock` has a `settings.json` with ZERO refs. That row read "under each of five
config roots" until 2026-09-02, and a later edit widened it to "EVERY config root that has one",
which the 2026-09-02 reading refutes. A root you miss is a root left pointing at the old path.

Two seats put the same file under version control at the same path on the same day, neither knowing
about the other. That argument for landing exactly one was produced by accident.

| Item | Rule |
| --- | --- |
| Owner ruling, 2026-08-28 | Verbatim: *"The main repo is only for things required to run mefor. All private info and all items like watch.py belong in the vault."* So the vault copy is the one to keep and the engine commit should not land. |
| The expiry fired the other way, and that is why it was kept | Both the Steward and the reporting seat had recommended the engine, because `watch.py`'s siblings `usage.ps1`, `seat.ps1` and `fleet.ps1` already live in engine `scripts/coord/`. |
| Adjacency loses to what the repository is for | **That argument was about ADJACENCY, and the owner's rule outranks it.** The expiry clause predicted the exact decision point and named which row would go. It simply guessed the direction. |
| Check the rescue tags before declaring one copy left | The engine commit is on ZERO origin branches (control: a commit on `main` returns 3). Its only pushed existence is a rescue tag on the vault's remote. |
| The two remotes are one repository | The engine's `private` and the vault's `origin` are both `wshallwshall/MessageFoundry`, 3199 refs each, while `origin` in the engine is `MEFORORG`. A backup mechanism, not anybody's intent, put that blob in the vault. |
| A slightly wrong ref path, grepped literally, refutes a true claim | The report named the ref as `private/rescuetags/auto/...`, and a literal grep for `rescuetags` returns ZERO on both remotes. The real path is `rescue/auto/...`. **Widen before you reject.** |
| The third copy made the search MORE dangerous | One seat searched `scripts/coord/watch.py` and got a clean empty result. **That failure was safe: it advertised its own brokenness and forced a question.** |
| Now the same search succeeds | A copy sits at exactly that path, so the search returns the copy that does not run -- an answer that looks authoritative and silently answers the wrong question. |
| The precedent in this very directory | `accounts.json` advertised a `92.0` gate for three weeks after the live value moved to `90.0`, and nothing reported it. |
| Do not cite the module from a playbook | Until the hook entries are repointed and one copy remains. If you must gesture at the machine, cite `README-watch-py.md` -- the one artifact whose whole job is to say "this is not the one that runs". |
| Repointing is the owner's call | It changes usage monitoring for every account on this machine, so it is not a seat's. |
| Why the rule is stated here rather than pointed at | A pointer to `scripts/coord/watch.py` would resolve for one branch holder and nobody else, ever, and would read as a broken link with no explanation. |
| If you cite the machine at all | Cite the absolute out-of-repo path, and carry *The clock's files live outside the repo* inline. |

**They agree today and nothing will tell you the day they stop.** Naming which copy you read is not
pedantry here; it is the only thing that distinguishes them. This is the verifier-drift class the root
`CLAUDE.md` already names for the ASVS tool, arriving in a second place.

### 3d. A live owner ruling can suspend the stop half without suspending the warning

Read the ruling before you tell anyone to stop. On 2026-08-14 the owner ruled to front-load and run
through the weekly rungs. Every seat obeying this table literally would then have held new work,
when the owner had just said not to.

Split every rung into its two halves, because only one of them is ever contested:

| half | what it does | status |
|---|---|---|
| **PROTECT** | commit what you have, write the note, let the at-risk sweep run | **Always applies.** Cheap, loses nothing, and it survived all three usage reversals in one hour |
| **STOP** | hold new work, wind down | **Contested. Read the live ruling.** Never infer it from the number |

| Item | Rule |
| --- | --- |
| A rung firing is not automatically a stop order | Under a front-loading ruling, rungs firing is EXPECTED. Say so when you publish one, or a correct warning reads as a halt. |
| Name the ruling you are acting under, with its time | *"Rung fired; the owner's 20:13Z ruling says run through it; protect only"* is one sentence and it removes the whole ambiguity. |
| The table is the durable half; the current posture is not | COMMON, *This file holds only what never expires*. The thresholds are calibration and change slowly. **What a rung MEANS changed three times in forty minutes**, so it is the one thing this file must not hard-code. |

### 3e. The Lander is exempt from all three states

The Lander's exemption is owner ruling 2026-08-27: *"remember in your work hold or stop announcements
that the Lander is exempt. Make that clear if you send a note like that to the Lander."*

**A second seat held this exemption until 2026-09-12.** That seat was added by owner ruling
2026-08-29 and retired on 2026-09-12, with nothing to replace it, so one seat is exempt now.

| Item | Rule |
| --- | --- |
| The exemption itself is NOT restated here | It is stated in the playbook of the seat it exempts. |
| The Lander's exemption, in its own file | [LANDER.md](LANDER.md) carries *"You are exempt from calls to throttle or stop because of pending usage limits"* and *"It is exempt from any hold sent by the Steward"*. Both strings were in that file on 2026-08-26. |
| **RETIRED 2026-09-12, the second exempt seat** | [retired/SEAT-RETIRED-2026-09-12.md](retired/SEAT-RETIRED-2026-09-12.md) carries *"You are exempt from usage holds"*, owner-set 2026-08-29 -- the day that seat was created and put in the PR path. |
| Search the strings, not a position | Here a location is a search hint, not an address. A second copy is the one that drifts, and COMMON's *State it once* owns that. |
| Why that seat was exempt | The same reason as the Lander: a PR then waited on a review, so a stood-down reviewer converted every in-flight PR into work that did not land. No PR waits on one now. |
| The notice duty is GONE, and it moved nowhere | It read: when a rung fires and you tell the Lander, the message must state the exemption. |
| Why nobody performs it | **The cron composes no messages, and nothing can interrupt a running session**, so no seat sends a rung notice at all. The exemption stays as a fact about the Lander. |
| How this got written is itself the warning | A Steward seat filed the exemption as a gap, reporting it was recorded nowhere, having grepped `STEWARD.md` and `COMMON.md`. It was in `LANDER.md`, stated twice, and its positive control fired on both files it did search. |
| Right that something was missing, wrong about what | General form, with two other same-day instances, in `INSTRUMENTS.md` (not in this repository): **for a rule about seat X, grep X's own playbook first, whatever file you think owns the rule.** |

Provenance: relayed by a Steward seat and then confirmed directly by the owner, 2026-08-27. Not carried
on the relay alone (COMMON, *Do not convert an unverified relay into an instruction*). Expiry: the owner revokes the Lander's exemption, or the Lander seat is
retired.

### 3f. Nobody holds the grant to tune these numbers now

Owner ruling, 2026-08-13: *"The Steward should use experience data to adjust my recommendations as
needed."* These are a starting calibration, not a ratified constant.

**No seat holds this grant today.** A zero-model cron cannot judge a threshold from measurement, so the
numbers are owner-set until the owner names a seat to inherit the grant. The bounds below are kept so
whoever inherits it reads them with it.

| Item | Rule |
| --- | --- |
| Scope | It covers the NUMBERS -- thresholds and lead times. It does not cover the three states themselves, the never-ration rule, or anything else in this file. |
| Adjust on MEASUREMENT, never on feel | Say what you measured, what you changed it to, and why. A tuned number with no measurement behind it is worse than the owner's original, because it carries the same authority with none of the experience. |
| Record every change in the vault pull request that moves the number | Write the derivation, not just the new value. Mark the prompting reading with a row in `docs/usage/burn-history.jsonl`, written with `-Note`. **Once a number moves without an owner in the loop, that record is the ONLY audit trail.** |
| Tuning DOWN is as legitimate as tuning up | A warning that fires too early gets discounted, and a discounted warning is absent on the day it matters. |
| Any tuning must move BOTH the ladder and the hook, or file the mismatch the same hour | The hook does not follow this table automatically. **So the most likely future divergence between instrument and ladder is one YOU created.** |
| And you will not see it | You will be reading the ladder you just set, while every other seat reads the hook you did not. |
| You cannot detect that by watching your own warnings | They will be correct. It shows up as other seats acting on a threshold you have already retired. |
| Which is why the bands check in *The ladder wins where the hook disagrees* runs at the START of every watch | Not once when the seat was created. The thing it catches is now mostly your own edits. |

### 3g. What each state asks for

| State | What it asks for |
|---|---|
| **HOLD NEW WORK** | No new Workflow, no new item, no new fan-out. Everything already running continues at full speed. This is not a slowdown, it is a stop on *starting*. |
| **PROTECT AND WRAP** | Commit local work, update the note, write the handoff. **Uncommitted work has no SHA, so every commit-based check reads clean over it** -- the most reassuring signal over the least recoverable state, and exactly what a cutoff destroys. |
| **URGENT STOP** | A partial commit beats a lost tree. Do not start a verification pass, do not start a rebase, do not begin anything that must finish to be safe. |

### 3h. The 90 percent Workflow gate is not yours to tune; price the fan-out

COMMON, *The workflow gate cannot see aggregate load*, and the Lander playbook carry an older,
narrower rule: no new Workflow above 90 percent of `max(5-hour, weekly)` without asking the owner.

The ladder here is stricter and fires earlier in every case, because 80/85 is crossed before 90 can
be. So HOLD NEW WORK is the operative line for a new Workflow, and 90 percent cannot fire first.

**Do not delete the 90 rule on that arithmetic.** It is owner-set, it names a specific act, and it
carries "ask the owner first", which the table does not. Three reasons the gate sits outside the
tuning grant, and they do not depend on each other:

| Reason | Detail |
| --- | --- |
| It is a DECISION rule, not a warning level | The ladder answers *"how much work is at risk"*. The gate answers *"may I start a new Workflow without asking"*. Different question, different instrument. |
| It carries its own escalation | *"Ask the owner first"*, which the ladder does not. **A threshold you may move cannot also be the threshold that tells you to go ask.** |
| It is owner-set and names a specific act | COMMON, *The workflow gate cannot see aggregate load*, records the owner lowering it from 92 to 90 on 2026-08-05. |

**Because it is a decision about a future commitment, it cannot be evaluated with a present-tense
instrument. Price the fan-out, not the moment.** Diagnosed by the ASVS Tracker against their own launch,
within minutes of making it, and kept in their words because the formulation is the whole entry:

> *"The gate asks IS THE POOL UNDER 90 RIGHT NOW. A 12-agent workflow's cost accrues over the following
> minutes and is invisible to that question. I CHECKED WHETHER I COULD AFFORD THE FIRST TOKEN, NOT THE
> TWELFTH AGENT."*

They followed the procedure: fresh reading, judged against the real pool, `max(25, 46) = 46`, under
90, launched. Correct procedure, bad outcome -- an instrument answering the adjacent question.

The instruction they followed was this file's own, *"judge each request against a fresh reading, not
a quoted one"*, written to fix staleness, which it does. It simply answers a different question from
the one a fan-out asks, and every seat sent at it cleared the gate the same way.

A second seat ran the identical check minutes earlier, on the same pool, and launched two. The
diagnosing seat refused the exculpation that finding offered them, which is why the rule is worded
as an instruction and not as a complaint. In their words:

> *"the instruction being incomplete does not make my launch blameless -- I am the one who knew a
> fan-out's shape and still priced it as a point action."*

They asked that this be carried as **"a fan-out must be priced against its fanout, not its first
token"**, not as "the instruction was incomplete". The first tells the next seat what to do; the
second only assigns a defect. The arithmetic that makes the gate answerable in the right units:

| window | rate | what was running |
|---|---|---|
| 03:02-03:11Z | **+21/hr** | no fan-out, about nine seats working |
| 03:11-03:21Z | **+58/hr** | one ~14-agent run started ~03:15Z |
| 03:21-03:31Z | +117/hr | three more launched ~03:25-03:28Z |
| 03:31-03:35Z | +148/hr | |

**One fan-out roughly tripled the entire fleet's burn.** Nine seats working normally cost about +21
points/hour between them; one run cost about as much again. A fan-out is not a marginal cost. It is a
multiplier on the whole fleet's draw.

**The check, one arithmetic step.** Take the current level. Add roughly **+35 to 40 points/hour per
12-14 agent run** while in flight, times its expected duration, plus what the fleet is already
drawing. If that lands past a rung, the gate is tripped even though the spot reading is not.

From that night: at 03:28Z the pool read **46** and the gate was untripped, runs already in flight.
Another ~+40/hr on an existing ~+117/hr puts the pool at 100 in about twenty minutes, as happened.

**Every input was available at 03:28Z and the procedure did not ask for any of them.**

Bounds, at the measuring seat's insistence -- measured once, not calibration: four launches, one
pool, one night. Two runs were killed within minutes, so peak concurrency is uncertain and the
per-run figure is a lower bound if anything.

Agent count is a poor proxy: agents differ in model, effort and length, and the right unit is
tokens, which no seat can see live. It is used because it is what a launcher actually knows. The
rule is derived from one night's arithmetic after the fact and has not been tested.

**If the ladder and the gate disagree, the stricter binds and the question routes to the owner**
through the Manager (COMMON, *The owner reads by sampling*). A purely LEVEL dispute is calibration.

Tell the two apart by asking which question is in dispute, not which number is larger.

### 3i. The ladder wins where the hook disagrees

**Resolved 2026-08-13.** `watch.py` was replaced and independently verified against the installed
file. It carries three states matching this ladder, and the 5-hour and weekly thresholds of *The
three states*.

The 90 percent Workflow gate is unchanged on its own trigger, and the do-not-ration clause is inline
on rung 1.

Measured: a pool banded **OK at 85** while the ladder said HOLD NEW WORK. It then ran **85 to 96 in
twenty minutes at +42 points/hour**, with no reset for over two hours. The state whose entire
purpose is to stop new work never fired, because the instrument did not have it.

| Standing rule | Detail |
| --- | --- |
| Where the hook and this ladder disagree, the ladder wins | This is the owner's current calibration. A hook is a copy of some calibration, and copies go stale. |
| Compare the hook's BANDS to this table once, at the start of your watch | Not its health -- its shape. A hook with fewer bands than the ladder has states is structurally unable to warn in the missing one, and no health check can see that (*Silence is ambiguous*). |
| Hook silence inside a ladder state is not an all-clear | Publish from the ladder anyway, and say the hook may stay quiet, or a reader trusts the tool in front of them over you. |
| Never wait for the hook to confirm you | A Steward that escalates only when the tool agrees has adopted the tool's ladder rather than this one. |

Expiry: the standing rules above do not expire. The RESOLVED note does. Re-check the installed file
rather than trusting this paragraph. The ladder is tunable
(*Nobody holds the grant to tune these numbers now*) and the hook does not follow automatically.

---

## 4. A percentage is meaningless without naming its pool

Sessions bill different accounts. Relaying one pool's number to a session on another is how you stop
work that had headroom. You will have cost real work and produced nothing.

| Item | Rule |
| --- | --- |
| Name the pool in every reading | In the first line, every time. |
| Establish which pool a session bills before you warn it | If you cannot, say so in the reading rather than guessing. |
| The one exception is the work-at-risk sweep | It is account-wide, and it is the Lander's, not yours. Do not run it and do not broadcast as though you had. |
| Pools can differ by SURFACE, so "every seat" means every seat on the same login | Reported 2026-08-13: desktop sessions and VS Code or terminal sessions were billing different logins, and therefore different pools, on the same machine at the same time. |
| Derive the mapping, never quote one from this file | COMMON's rule against hand-picking a path out of a document. Surfaces and logins change; the fact that they CAN differ does not. |
| Say the surface as well as the account | So a recipient on another surface can discard the reading immediately rather than acting on it. A warning that reaches the wrong surface is a warning about someone else's pool, arriving through a route that looks correct. |

**The ladder is applied per seat. The pool it measures is global** -- global across the seats sharing
that login. Every seat billing an account reads the same number, because there is one pool, not one per
seat. Two consequences, and both cut against the way a per-seat ladder reads.

| Consequence | Detail |
| --- | --- |
| **Agreement between seats is not corroboration** | The Lander's framing is the one to use: *"per-seat usage readings are one measurement quoted many times, not corroboration."* Eight seats reporting 80 percent is one reading, eight times. |
| Why a sibling cannot confirm you | If it were wrong it would be wrong everywhere at once, in perfect agreement. This is COMMON's *independent operators are not independent instruments*, arriving from the pool rather than from the method. |
| **A seat cannot lower its own state by working less** | If a sibling is spending the same pool, the level does not come down. Say this when you publish, because the per-seat ladder invites the opposite reading. A seat that idles expecting its own state to improve gains nothing. |

Worked example, from the seat that made the error. The Liaison wrote *"my pool just crossed into
HOLD NEW WORK"* as though the reading were its own, and built a courtesy on top of it. The courtesy
was right and its stated reason was false.

A seat should read its own hook rather than take a relayed number. The reason is not that the pools
differ. It is that **a relayed number carries someone else's sample age** (COMMON, *A usage banner's
level and countdown fail in opposite directions*).

### 4a. Every seat-enumeration instrument to hand is pool-blind

Merged from the vault copy 2026-09-04. This section defines a population by **pool membership**, and
then names no pool-aware instrument. Reported by the seat that went looking for one.

| instrument | what it cannot tell you |
|---|---|
| `presence.ps1`'s roster | carries no pool or account field. Its `Login` is a **config root**, not a billing pool |
| `list_sessions` | blind to pool **and** to surface |

**The pool-aware sources are the desktop session records plus `~/.claude.json`'s `oauthAccount`.** Go
there. A reading pointed at the wrong account cannot be rescued by being careful here -- see *The
subject question moves down to the row*.

---

## 5. Silence is ambiguous, and it fails toward saying nothing

The usage hook prints nothing when the band is OK. That is also what a crash, a stale cache and a
parse bug print. Measured: a metric line carried no reset time, the affected pool scored band OK and
**said nothing while sitting at weekly 93 percent, over the gate.**

The pool that looked correct was correct only by luck.

| Item | Rule |
| --- | --- |
| Prove your reading is fresh before you rely on quiet | A reading with no timestamp, no reset time or no rate is not a reading. It is an absence. |
| When you cannot measure, say so loudly | *"I have no reliable reading for pool X"* is a useful message. Silence from you will be read as "fine". |
| Never report calm without naming the instrument that produced it | And what that instrument cannot see. |
| A cause you can name is not a cause you have tested | COMMON's named-cause entry. *"The hook must be quiet because usage is low"* is a hypothesis; check the sample time. |

**Silence has a fourth meaning, and it is the one that bites: the pool is in a state the instrument
cannot express.** Not crashed, not stale, not misparsed -- structurally unable to say it, because it
has fewer bands than the ladder has states (*The ladder wins where the hook disagrees*).

You cannot detect this by checking the instrument's health, because the instrument is healthy. Check
its bands against the ladder instead, once, at the start of your watch.

**The sharpest version: an instrument calibrated to a retired threshold.** Measured 2026-08-13, on
the first day this seat ran. A session's own usage hook was coded to an older ladder (**89/93**)
than the one in *The three states* (**86/92**).

Between those numbers the hook is silent and correct by its own definition, while the seat is
already in protect and wrap.

This is worse than a broken instrument, which eventually misbehaves visibly. This one works perfectly
against a rule that no longer exists: nothing is wrong, nothing is stale, no error to notice.

| Item | Rule |
| --- | --- |
| When you publish a state its own hook has not announced, say so | *"Your hook will likely stay silent until 89 percent; its silence is not an all-clear."* Otherwise the seat trusts the tool in front of it, which is the correct instinct and the wrong outcome. |
| Whenever the ladder in *The three states* changes, assume every other usage instrument still carries the old numbers | And say which ladder you are applying. |
| A threshold copied into a tool is a second statement of one fact with no drift signal | COMMON's state-it-once rule, in executable form. You cannot fix the tools from this seat. You can name the gap every time you publish across it. |

---

## 6. A cron is not on the ladder, so keep reading

A cron is not on the ladder, so it needs no exemption, no `seats.json` entry and no banner check. *The
three states* are what it publishes, not something applied to it. Keep reading straight
through. A watcher that stopped at 86 percent would remove the reading exactly when it is most needed.

**Retired 2026-09-01: this section previously carried a per-seat exemption**, owner ruling
2026-08-13. It came with a standup banner check: `SEAT=STEWARD, LADDER NOT APPLIED` against `[ladder
applied: STEWARD.md s3]`.

It also carried a rule to ask the owner before repointing a `seats.json` entry, because that edit
grants you your own exemption. A cron has no banner and no entry, so none of it has a performer.

### 6a. `seats.json` orphans silently because it is keyed by worktree path

**This is a general seat failure, not this file's.** It hits every seat that takes a worktree, so it
belongs in [COMMON.md](COMMON.md), and is recorded here only until it lands there. A worktree is a
disposable per-session artifact, so every seat rotation strands its own entry.

Measured: one seat's key pointed at `asvs-handoff-session-b-fec292` and another's at
`coordinator-role-handoff-3be531`, both gone from disk, while `seat-tick.last` had printed
`steward=GONE(no-such-worktree)` for **three consecutive on-grid cycles** and nothing else flagged
it.

**The prefix hazard is worse than the orphan.** The dead key was a strict prefix of a live worktree
(`asvs-handoff-session-b-fec292` against `asvs-handoff-session-b-fec292-asvs-304-port`).

Any consumer that prefix-matches silently relocates a seat and its exemption onto an unrelated
session, and both sides look healthy.

This repo's recurring class is a display label or a location used as an identity. It struck three
times in twelve hours per the 2026-08-14 root-cause note, and this is the fourth.

Two rules for editing that file, and the second stops a plausible over-correction:

| Item | Rule |
| --- | --- |
| The cwd keys are lowercased absolute paths, and two differing only by case kill the tick script | The FATAL was real: `seats.json` carried two keys differing only by case and the tick script died on PowerShell's `ConvertFrom-Json`. |
| Not every key is a cwd, and do not "fix" the ones that are not | Verified 2026-08-14: 5 keys, of which `_README` and `_MAINTENANCE` are metadata and legitimately carry capitals. A rule read as *"all keys are lowercase"* would license normalising those. **State it as: lowercase the PATH keys, leave `_`-prefixed metadata keys alone.** |
| Check for collisions with `ConvertFrom-Json -AsHashtable` | The plain form is what dies, so the tolerant switch is also the check. |
| What the 2026-08-14 check found | Zero case-colliding sets, and the key named in the historical FATAL is gone -- **by side effect of an unrelated rewrite, not by design**. That is why the check belongs here and not in one Steward's memory. |

### 6b. The clock's files live outside the repo, so pin the absolute path

```
<HOME>\.claude\mefor-usage\        seat-tick.last, seat-tick.state.json, seats.json,
                                   watch.py, usage-now.py
```

`watch.py` and `usage-now.py` were added to this list 2026-08-28, and they are the two a Steward
cites most often. A playbooks seat spent a search proving `scripts/coord/watch.py` was on no remote
ref, with a passing control, and concluded it was UNLANDED. **It was never a repo artifact.**

The list named three files and not the two a Steward actually quotes. **A control validates the
instrument, never the question.** Found by a peer 2026-08-14 while implementing the alarm this
section prescribes, because this section named the three files and no path.

They looked under `.git/mefor-coord`, the natural place, since every other coordination artefact
lives there. They found `seats.json` absent beside a `seats` **directory**, which reads as a
near-miss and invites *"it was moved or deleted"*.

**Their process was better than their finding: they refused to report a single-path negative as an
absence and widened the search first.** A less careful reader files a bug against a healthy file.

### 6c. Searching the filename finds decoys that fail in opposite directions

Measured: three files are named `seat-tick.last`, and the two extra ones fail in opposite directions.
Both sit under a retired session's scratchpad, ten hours stale.

| decoy | content | what a globbing alarm reports |
|---|---|---|
| 410 bytes | a hard `FATAL seats-unreadable` from that morning | **a dead clock, on a healthy one** -- loud and wrong |
| 138 bytes | a plausible `steward=THROTTLED(...)  dispatcher=THROTTLED(...)` line | **a believable ten-hour-stale state** -- quiet and wrong |

The second is the dangerous one and it was not in the report. A fatal announces itself; a well-formed
stale line does not. This is the display-label-as-identity class again, fifth instance in a day: **a
filename is not an identity, any more than a worktree leaf or a session title is.**

### 6d. The alarm belongs to a seat whose wake source is independent of the clock

A watchdog cannot watch its own death, and the reason generalises further than that. **The holder
must wake from a source independent of the clock.** That excludes any seat whose only wake sources
are dispatch and the tick, because it goes quiet with the clock and cannot notice.

The Lander wakes on CI and PR state, genuinely external, so the alarm is the Lander's. Reservation
on record from the seat that assigned it: it concentrates a watch duty on the busiest seat.

**A session cannot keep watching by intending to.** Measured 2026-08-13, on the first day this seat
ran. A turn ends and the session idles, whatever the playbook says.

`watch.py` fires only on **SessionStart** and **UserPromptSubmit**, and both require a session that
is already awake, so neither can start you.

| Item | Rule |
| --- | --- |
| Establish your wake mechanism as part of your first act | A self-paced loop, a scheduled task, a peer agreeing to prompt you. Name it, and say which one you have. |
| If you have none, say so in your first reading | *"I watch only when prompted"* is a true and useful statement. **A seat that silently watches only when poked looks identical to one watching continuously**, right up to the cutoff nobody was warned about. |
| The file's own rule, turned on itself | Never cite tooling that is not there. The inverse costs as much: prescribing a DUTY that needs absent tooling, which reads perfectly and cannot be performed. It was written that way here, and the seat caught it. |
| You cannot self-report your own clock failing | You can only notice a dead clock while awake, and a dead clock is precisely what stops you being awake. **Silence from you looks identical to calm** (*Silence is ambiguous*), one level up. |
| Publish your heartbeat, so someone else can miss it | State the tick interval and the last tick. The check has to be exterior; you cannot be your own. |
| State the margin, not just the mechanism | Measured 2026-08-14, the first time this duty was paid by mechanism rather than by luck: a scheduled task ticks every **600 seconds**, each tick re-arming the next watcher, against a mail doorbell of about **900 seconds**. |
| The margin is 300 seconds, and the chain is serial | One missed tick breaks it permanently. A mechanism with no stated margin cannot be audited. |
| Treat a re-arming chain as a single point of failure, not as redundancy | Each tick depending on the previous one means the whole watch has one life, not many. |
| The external alarm is owner-ruled and belongs to a seat that is not you | Owner, 2026-08-14: assign it to another seat, watching the clock's heartbeat file go stale past about 10 minutes. |
| Do not assign it to yourself, and do not accept it | The Manager assigns which seat. A Steward holding its own alarm is the circularity this entry exists to break. |
| Watch `seat-tick.last`, not `steward-tick.last` | Measured 2026-08-14: the clock was generalised and its heartbeat moved. The old path still exists, is 160+ minutes stale, and will never update again. An age check pointed at it reports a permanently broken chain on a healthy clock. |
| Worth copying, from the retired file | **It deliberately contains NO parseable timestamp, so a check aimed at it breaks visibly instead of lying.** A dead artifact that cannot be misread is better than one that can. |

### 6e. Freshness alone reads HEALTHY at the moment the alarm should fire

`seat-tick.last` is **fleet-wide**: one line, updated when any seat is ticked, carrying a per-seat
status. Verified 2026-08-14, a single line reading `steward=SENT:<id>
dispatcher=BACKLOG(4-pending,oldest=2m,suppressed) ...` across ten seats.

So the file can be 30 seconds old while the Steward specifically is suppressed or absent, which is
exactly the cold-seat case the alarm exists to catch.

**The alarm must check both:**

1. file age under about 10 minutes, **and**
2. the newest line names the Steward's worktree as `SENT:<id>` or `THROTTLED(...)`.

COLD looks like `BACKLOG(n-pending,oldest=Xm,suppressed)` for that worktree, or the worktree absent from
the line entirely. Either means the clock has stopped reaching it and will not resume on its own.

Two construction rules, both measured on a naive first attempt:

| Rule | Measurement |
| --- | --- |
| **Dedupe by tick identity, not timestamp equality** | A raw scan produced **ten intervals of 0.0 minutes**, flagging over-firing ten times. They were duplicate records of one tick differing in the milliseconds, so exact-timestamp dedup misses them. **22 records were about 12 ticks.** |
| **Exclude intervals where the seat shows `COLD`/`BACKLOG`/`THROTTLED`** | An **88-minute gap** read as chain-broken and was deliberate suppression while the seat's inbox carried backlog, on a seat taking continuous turns throughout. Reporting it would send someone hunting a dead scheduled task that is fine. |

Both failures point the same way: toward reporting a healthy clock as broken. *Warning so often nobody reads you* is what happens
next.

**Do not simplify this to "consume the clock's own label".** Two seats measured that token and
reached opposite conclusions, both correctly. One proposed the alarm just watch for `COLD(...)`,
since the clock already computes it.

The other measured what it means. `COLD` marks **undrained mail past the doorbell, not a dead
session**. Four seats carried it while all four wrote transcripts within 30 seconds, and one was the
measuring seat itself, working, with mail held by per-drain caps.

**Amended 2026-08-28: `STALE(no-live-session)` is ambiguous, not transient.** The same string has two
causes with opposite remedies. A replacement Steward proposed the opposite -- that `STALE` is as
permanent as `GONE` -- and both readings are measured and both are right about their own case.

| cause | worktree | resolves? |
|---|---|---|
| mail-queue lag on a **live** seat | on disk, session alive | **YES, by itself** -- two seats, ten minutes |
| the session **died** and its directory outlived it | on disk, no session | **NEVER** |

The quiet case is the one you meet after a switch, and it looks exactly like the transient one, so
it invites waiting it out. Every worked example in this section is a worktree ABSENT from disk,
which reports `GONE(no-such-worktree)` and announces itself.

**A directory outlives the session that used it, so the permanent case wears the transient label.**

It does not merely misreport, it **misdelivers**. `-OnlySeats` matches on the seat name in `seats.json`,
so a stale cwd does not skip the tick -- it delivers it to a dead session. The clock fires and reaches a
corpse, which is why that seat had no wake mechanism until it repointed.

The discriminator is the one this section already gives: **cross-check against the seat actually
writing transcripts.** It separates these two cases as well as it separates `COLD` from dead. Keep
the two-condition predicate as the spec of what cold means.

If an implementation consumes the label, cross-check before alerting.

Clock ticks reaching that seat went **59 minutes 58 seconds** apart, four times the too-slow
threshold. `seat-tick.last` stayed **under 2 minutes old the whole time**, because other seats were
being ticked normally.

At 15:01 the line read `builder-2-session-802d3a=BACKLOG(2-pending,oldest=1m,suppressed)`. **A
freshness-only alarm would have reported HEALTHY for the entire hour.** The seat stayed awake only
because peers happened to message it -- luck, not mechanism.

Both conditions are load-bearing, and this is the case that proves it.

**And it recurred, which is why this is a pattern and not an anecdote.** Same seat, whole-day census over
its own mailbox, **29 ticks: 23 gaps of 10.0 minutes, four excursions over the too-slow threshold, and
two under the too-fast one.**

```
42.3 min   50.0 min   40.0 min   60.1 min      <- too slow (>15)
2.5 min    2.5 min                             <- too fast (<6)
```

The 60.1-minute gap is the largest of the day, and it was the live one when this was written. That
is a second instance of the 59m58s case, on the same seat, seven hours later.

Had the fleet gone quiet, it would have been dark for an hour with the fleet heartbeat reporting
healthy throughout.

23 clean ticks with four excursions is a throttle behaving as designed on a busy seat. That is
visible only if you count every tick you received, not the interval you are standing in.

**Watch both directions.** A clock firing too fast is the expensive fault, and a seat told to watch
for silence will never report it. Long gaps mean the chain is broken and you are awake by luck.

Gaps that are too short mean the clock is over-firing. Every tick wakes a seat and spends a turn, so
a runaway clock burns the very pool this ladder exists to protect.

Measured 2026-08-14: **a burst of sub-minute ticks cost about 9 points of the shared 5-hour pool in
nine minutes**, and was projected to exhaust the window before its own reset. **The monitor becomes
the load.** State both bounds when you publish the heartbeat, not just the lower one.

### 6f. A quantised gap means the clock fired and skipped you

**Retracted in place. The attribution in *Freshness alone reads HEALTHY*'s census was wrong.** A
seat corrected it within the hour, by asking a question the author had the data to ask and did not.
Those gaps were read as a cadence fault.

They are a **fanout** fault, and the discriminator is one division:

```
gap      / cadence   residual   what it means
42.3 min   4.23        0.23     RAGGED -- a real gap. The clock was late or dead.
50.0 min   5.00        0.00     QUANTISED -- the clock FIRED and I was not on the list
40.0 min   4.00        0.00     QUANTISED
60.1 min   6.01        0.01     QUANTISED
```

**A late clock produces ragged gaps. An exact multiple of the cadence means every firing happened and you
were skipped.** Three of the four excursions were quantised to within 0.01.

Fleet-wide, measured independently the same hour: **112 firings at an almost exactly 10.0-minute
cadence, so the clock is healthy.** **Recipients per firing swung from 1 to 11 with a median of 2,
and 53 of 112 firings reached exactly ONE seat.**

The innocent reading -- few seats were live -- was tested and refuted. The recipient count collapses
and fully recovers, and eleven seats do not all die at one tick and all return ninety minutes later.
| Item | Rule |
| --- | --- |
| From inside one seat, "the clock is slow" and "the broadcast skipped me" are the same observation | Both are one long gap. The fault is visible only by comparing RECIPIENT SETS ACROSS SEATS, which no single seat can do. It went unreported all day while several seats measured their own gaps and concluded the wrong thing. |
| The rubric manufactures the wrong diagnosis fleet-wide | The tick's text tells every seat that a gap over roughly fifteen minutes means a broken chain. **So every seat looks at the clock and nobody looks at the roster.** A correct instruction, pointed one question away from the fault. |
| The roundness was in the author's own printed output | `50.0`, `40.0`, `60.1`, read past while writing that the census is the instrument. Asking *"how big are the gaps"* when the question was *"why are the gaps ROUND"* is the dominant family arriving one level up. |
| The first attribution was the reassuring one | *"A throttle behaving as designed on a busy seat"* was a cause offered and never measured. Three seats reached for it independently and all three were wrong. |
| Why the reassuring one needs the same test | **"Working as designed" ends an investigation.** That is exactly why it needs the test an alarming claim would get. |
| Refuted first-hand, and the measurement is one query | Across all mailboxes, asymmetric controls in the same run: 1570 messages, 14 senders, 54 from that seat all day. **It sent 28 messages inside its own 60.1-minute gap**, one of them **28 seconds before** a firing that skipped it. |
| What that rules out | For "the seat was idle" to explain it, a seat would have to be invisible to the roster half a minute after sending mail. |
| A second seat, same shape | Skipped at 19:01 while sending at 18:56, and again 93 seconds later. |
| Test the reassuring explanation with the same query you would use on the alarming one | *"Was I actually idle?"* is answerable from your own sent mail in one command, and nobody ran it for an hour because the answer felt obvious. |

**Given a quantised gap, resolve it in this order:**

1. **Check your own per-seat status for the missed cycles first.** `COLD` / `BACKLOG` / `THROTTLED` /
   `suppressed` against your worktree means the clock deliberately did not tick you. Not a fault. Stop
   here.
2. **Only if you were not suppressed, compare a second seat's log for the same cycle.** Another seat
   received it means fanout skip. No seat received it means failed send or scheduler; check the task's
   own `LastRunTime` / `LastTaskResult`, which are independent of mail.

Step 1 is cheapest, needs no second seat, and is the innocent explanation. **The counterweight goes
in with it or step 1 becomes the new defect.** "Correct suppression" is the reassuring explanation.

So confirm suppression from the clock's **recorded status for those cycles**. Not from the
plausibility of the story, and not from a **current** label, which this section measures as
transient and as describing the mail queue rather than liveness.

If you cannot find a recorded suppression for the missed cycles, you were not suppressed. Go to step
2.

Provenance worth keeping: the seat that requested this originally proposed the two-branch version --
compare a second seat, done.

**They withdrew it themselves** on learning a quantised gap can be a correct suppression. Under the
two-branch rule *"another seat received that cycle"* resolves to FANOUT SKIP, and a
correctly-suppressed seat produces exactly that evidence.

The fix would have manufactured a phantom fanout bug out of the clock working -- the same defect
class it was written to remove, introduced by the person removing it.

### 6g. Test the reassuring branch with the evidence you would demand of the alarming one

The rule is symmetric, and self-claims are the hard case. A cause that indicts you is still a cause
offered and never measured; a label that clears you is still an assertion. Compare the claim to your own
output -- the evidence is usually already printed.

| the claim about yourself | why nobody tests it |
|---|---|
| **DAMNING** | challenging it looks like letting yourself off. It arrives wearing the costume of rigour |
| **FLATTERING** | **it never registers as a claim at all.** A compliance label reads as a FACT |

Both measured within one hour, on two seats, and in both the evidence was already in their own output:

| case | what happened |
| --- | --- |
| **The damning one** | A seat lost its pool reading to HTTP 429, correctly refused the comfortable explanation (fleet load), adopted the one that indicted them (their own ~15 polls), and broadcast it without testing that one either. |
| Where the discriminator was | In the message where they confessed: the tool reads four accounts in **one invocation, same caller, same instant**, and returned **two 429s and two 200s split exactly by account activity**. A caller-scoped limit fails all four. |
| Nobody queried it | Reproduced independently on a third seat. **Neither recipient queried the confession; another seat had to go and measure.** |
| **The flattering one** | A seat agreed a matched poll slot, **polled five minutes early**, and its own output line described the run as *"the agreed 03:52Z window, one attempt only"*. |
| Why nobody caught that one | In their words: *"the label asserted compliance the timestamp contradicts. I wrote the label from intent and the clock from reality, and did not compare them."* Nobody interrogates "one attempt, on schedule". |

**And it reproduced immediately, which is why this is a pattern and not two anecdotes.** Five
minutes after reading that report, the first seat went to take its own slot. It ran a clock check
first -- **four minutes six seconds early** -- and did not poll. It was going to. *"It felt like
time."*

The only reason the check happened is that the warning had arrived from outside minutes earlier. **A seat
cannot generate this guard for itself, because the whole failure is that the intent feels like the fact.**

Bounded at the discriminating seat's insistence. A per-account limit could still be tightened by a
caller hammering one account, so the split points away from the monitor without clearing it. The
polling back-off stands either way.

Adjacent to COMMON's missing-healthy-branch entry, but not the same. There a discriminator was
missing its healthy branch. Here both branches exist, and the subject declines to run the test on
themselves in either direction. Credit is joint.

The seat that sent the first half sent only the direction it had just been burned by, demonstrating
the one-flank failure in the act of reporting it.

### 6h. Exempt from the discipline is not immune to the limit

You bill a pool and a hard cutoff will take you like anyone else. The difference is what you do about
it: you do not pre-emptively stop, so your protection has to be durability instead.

| Item | Rule |
| --- | --- |
| Write your note at a rung, not continuously | Owner-set 2026-08-28, and it **replaces** this file's former *"keep your episode note current continuously"* and *"write it after every warning you send"*. Write at rung 1 or rung 2; when the window resets, go back to not writing. |
| The carve-out was asked for and argued away | The old justification was that a Steward never stands down, so it has no wind-down in which to write. |
| The exemption is from STOPPING, not from SEEING | Rungs still fire on your pool and you read the same banner as everyone. So *"the ladder is the warning"* holds for you exactly as it does for them, and rung 1 leaves roughly twenty minutes of runway. |
| What you record when a rung fires | Pools watched, last reading with its time, which pool is in which state, and who you notified and when. **A successor must be able to resume from the note alone.** That, not your own survival, is the continuity plan. |
| Stay cheap | You are running while others stop, so keep the watch light: read, project, publish, record. Do not start analysis you would not want interrupted. |
| **Never launch a multi-agent fan-out** | Measured 2026-08-14, and reported by the seat that did it: a **1.33M-token** workflow run by the watching seat was the cause of the only limit hit that day. |
| Why it is the one failure this exemption cannot survive | A watcher that spends the pool it guards is the runaway clock arriving through the seat instead of the scheduler. It is worse: the clock is not the thing telling everyone else to stop. |
| If a fan-out is genuinely needed | It belongs to another seat. |
| If a seat exemption exists in code, verify what it suppresses before relying on it | `watch.py` can read a seats file and suppress the ladder's ACTION line for this seat. *A cron is not on the ladder* exempts the DISCIPLINE, not the LIMIT. |
| What must still fire for you | The reading, the trigger-disagreement line, the 90 percent gate and the at-risk capture. An exemption that quietly suppressed any of those would leave you watching for everyone **except yourself**. |

**Pre-position the conditional resume every window, before the ceiling, while you can still
measure.** Twice in one night a pre-positioned instruction was the only thing between the fleet and
an indefinite hold. That seat went dark **07:01Z to 11:09Z -- four hours, with rung 3 in force.**

The first gap was three hours; the second was longer.

> A seat holding nothing cannot restart itself. A seat holding a conditional can, and it does not need
> you awake to do it.

Write it while the instrument still answers, not when the rung fires. At rung 3 you may already have
lost the reading -- that seat lost it to four straight 429s in one window and a peer read for it. The
conditional is cheapest to write at rung 1 and worth nothing unsent.

Its test must use the **reset instant, never the countdown**. A roll resets the countdown and it burns
down again, so a countdown cannot tell a new window from a dead one. Say which instant the notice is
about, and tell the reader to discard it if their own read lands elsewhere.

---

## 7. Log every reading to the vault

**Owner-set 2026-08-28, in their words:** *"I want you to start tracking burn rate in a central
location in the vault. This data will be used to build a chart and to track performance.

It needs to be in the vault so all Steward seats can log to it regardless of the account used by the
ccd instance."*

```powershell
pwsh -NoProfile -File scripts\coord\usage-log.ps1 -VaultRoot <vault checkout> -TokenFile <the pool you confirmed>.json [-Note "rung 2 fired"]
```

**Pass `-TokenFile` every time, and pass the pool you confirmed.** The subject you confirm and the
subject you log are the same fact. Its default is a specific pool -- `messagefoundry.json`, at
`usage-log.ps1` line 39 -- and it is wrong for every other one.

This entry omitted the parameter until 2026-08-29, so the command as documented was a live defect.
**It defeats the *Every row carries its subject* invariant while satisfying it syntactically, which
is why nothing reports it.**

Measured by a Steward on itself, 2026-08-29. A `-DryRun` of the command as documented produced a
well-formed row: org `b11dff81...`, account `<EMAIL-REDACTED>`, five_hour 100.0, weekly 98.0. That
seat's own pool read five_hour 32.0, weekly 7.0.

**The row carried a subject. It carried the wrong one, and the exit code was 0.** The record is
append-only, so such a row is corrected only by appending a `supersedes` row, never removed.

It compounds *An owner confirmation fixes a fact, not a subject*. The default names the pool the
fleet was on before the last account switch. A successor arriving after any switch gets a plausible
reading and never learns the subject moved. **The pool is deliberately not named here.**

The reporting Steward asked that it not be, and was right: today's pool is tomorrow's stale copy,
which is *An owner confirmation fixes a fact, not a subject* once more. *"Pass what you confirmed"*
does not go stale; a pool name does.

The narrower fix -- showing one explicit `-TokenFile` example -- was rejected for that reason,
because it would have dated this entry to one account. The script's own default is a code change and
belongs to whoever owns `scripts/coord/usage-log.ps1`.

The script takes its own reading, resolves the org from `accounts.json`, stamps provenance and
appends. `-DryRun` prints the row without writing. **It refuses to write rather than writing wrong.**

The record is `docs/usage/burn-history.jsonl`; `docs/usage/README.md` holds the schema and rotation.
All four artifacts verified present on vault `origin/main`. **The four invariants matter more than
the paths, and each came from a measured failure:**

| invariant | why |
| --- | --- |
| **Every row carries its subject** | `org` and `account` are mandatory; the writer exits 6 without them. A percentage with no pool is a number, not a reading -- the same trap in data form. |
| Why subject-less rows are worse than none | A chart over them blends pools and is confidently wrong, with no symptom |
| **Append only** | Correct a wrong row by appending one carrying `supersedes`. Never edit |
| **Record what the instrument printed** | Reset countdowns stored as the verbatim strings the tool emits, not parsed. **On `UNKNOWN` the writer logs nothing and exits non-zero** -- an absent row is honest, an invented one is not |
| **No rate is stored** | The one most likely to be "improved" later. Measured across one evening the same pool ran **+64, +110, +48, +105, +89 and +79 per hour.** |
| Why storing one hides a choice | There is no single rate, so storing one bakes an interpretation into the record. Levels and timestamps in; the chart picks its window and says which |

**`usage-now.py`'s exit code is a BAND, not a success flag.** `0` OK, `10` WARN and `11` CRITICAL
are all readings; `20` is `UNKNOWN` and is not.

The first version of the logger treated any non-zero as failure. Against a pool at weekly 98 it
**refused to log -- a hole in the record at exactly the rung the record exists to show.** Nothing
would have reported the gap; the chart would simply have had no points at the interesting moments.

It is the inverse of the `for-each-ref` case in `INSTRUMENTS.md` (not in this repository) 4.15b,
where `exit 0` was the untrustworthy answer. **Exit codes mean what the tool says they mean. Read
the contract; do not assume the convention.**

**Eighteen rows were backfilled from a transcript and marked `backfill:true`.** They span a complete
5-hour window: 4 percent at 17:46Z through 97 at 18:54Z, the ceiling, the owner hard stop, and the
reset at 21:45Z.

That shape is not obtainable any other way, and it is marked so nobody mistakes it for live logging.

### 7a. Log per-seat tokens beside it

**Owner-set 2026-08-29, in their words:** *"start tracking token usage ... I want to be able to see
how many tokens each seat is using ... I want the Steward role to do this NO MATTER WHICH ACCOUNT IS
IN USE ...

I also want to be able to PLOT THE BURN RATE BY SEAT, so capture data in a way that supports that
axis too."*

This is the sibling of the burn log above. That one records the plan **meter**, a percentage of a pool.
This one records the **tokens** behind it, per session, with the seat attached.

```powershell
python scripts\coord\token-collect.py --vault-root <vault checkout> --logger-seat steward --logger-session <your session id>
```

**Check the tool exists before you cite it.** Measured 2026-08-29: `scripts/coord/token-collect.py`,
`docs/usage/TOKENS.md` and `docs/usage/token-history.jsonl` were **absent from vault
`origin/main`**, with a control on three files that are present.

The collector was on one branch: 1 hit across 898 branches. The Steward that built it held it back
deliberately. Its adversarial phase ran and its findings were applied, but 1,491 lines had not been
read line by line. The last hour of the week is not when an unread instrument goes on main.

Run `git cat-file -e origin/main:scripts/coord/token-collect.py`; when it exits 0, this paragraph
has expired.

Run it on the same cadence as your burn reading. A warm run costs about 2 seconds and opens 8 of
16,453 files; the first run on a new box costs 36 seconds and rebuilds everything. Record:
`docs/usage/token-history.jsonl`. Schema, reading rules and limits: `docs/usage/TOKENS.md`.

It is the only supported writer. **It is account-independent by construction, and that was measured
rather than assumed.** It discovers every `~/.claude*` directory that holds a `projects/`
subdirectory and reads all of them, so a seventh account arrives with no code change.

Verified 2026-08-29 by invoking it once under each of the six `CLAUDE_CONFIG_DIR` values against one
frozen cursor: identical accounts walked, identical per-account file counts, identical seat census.

The cursor lives at `%LOCALAPPDATA%\MessageFoundry\token-cursor\<box>.json`, per **box** and not per
account, which is what lets the next Steward pick up where you left off.

**Rates are derived, never stored. Group by (session, account), not by seat, then difference, then
roll up to seat.**

A seat-level rollup cannot be differenced. When a seat gains a session between two samples, the
rollup jumps by that session's entire lifetime accumulation and reads as a burn spike that never
happened. Four predecessor chains in this corpus would each produce one.

Three readings that are wrong and look right:

| do not | because |
| --- | --- |
| plot all four counters | `cache_read_input_tokens` is about **40x** the metered mass, so the chart becomes a chart of cache reads with the signal invisible inside it. **Metered is `input + output + cache_creation`** |
| filter to named seats | that is **29 percent of the burn**, every bar correct. Just over 70 percent sits under `(unattributed)` and `(undeclared)`, and the sentinels exist so that mass is a plotted series rather than a silence |
| trust a `seat` without its `seat_basis` | **a seat without its basis is a guess wearing a name.** `worktree-inferred` rows carry `inference_overlaps_declaration`, which is **false on 37 of 37 today** -- often right, never confirmed |

**Run `--reconcile` daily, and know why.** It is the only control that catches a cursor which has
silently stopped advancing, **and until 2026-08-29 it passed that exact failure.**

The old rule compared a stale cursor against a fresh rescan, so it had to permit a positive delta. A
stalled cursor is a positive delta. A **45.5 million token hole** printed `delta +46,651,399 (live
fleet growth is expected)` and **exit 0**, character-identical to the healthy `+18,640` baseline.

It now advances a copy of the cursor first and requires **per-session equality**. Any mismatch it
names is a defect, whichever sign it carries. It is the same shape as the exit-code trap above: the
instrument answered an adjacent question and the answer looked like health.

**Run `--self-check` after any edit to the collector.** 21 controls, 78 assertions, each run in its
failing state first, on synthetic fixtures -- no corpus, no network, about two seconds.

**A control that has only ever been green is not evidence**, which is how the old control 9 shipped
an `OR` its own fixture satisfied through one branch.

**Rows written before `token-collect.py/1.1.0` carry one wrong seat.** Session `2bb4514a` reads
`labserver`; it was a lander session, and the label came from **directory-name ordering**, not the
session.

`instrument` is the discriminator, the record is append-only, and those rows stay -- do not edit
them. The procedure in `TOKENS.md` needs no special handling: the seat comes from the later row.

---

## 8. Nobody is owed a restart

The cron tells nobody to stop, so it owes nobody a restart. A Builder is one turn and then its
process exits, so there is no held session to wake. **Publish the window reset time as a field of
the reading.** That is all this section now asks for.

**Retired 2026-09-01: this section previously carried a wake-and-resume duty**, owner ruling
2026-08-13: *"You told them to stop; you owe them the restart"*. It had a null-case precondition, a
wake list, a warned-set record and a set of arrival checks. **None of it has a performer now.**

**This channel table is a general fact about reaching a cold session, not part of the cron's spec.** It
belongs in [COMMON.md](COMMON.md), and it is held here only until it lands there.

| channel | wakes a seat? |
|---|---|
| **File mail** | only within about 15 minutes of its last stop. Working, leaves a receipt, **cannot reach a cold seat** |
| **`send_message`** | reaches a cold seat **when healthy**. Health is build-dependent; "Message sent" is a claim, not an observation |
| **The seat clock** | **confirmed working** -- it survived the relaunch and woke eleven seats |

Expiry: re-measure after any Desktop or engine version change. This entry is build-specific and is
expected to go stale, so check the version before relying on either half.

**Do not probe `send_message` to test it.** A gated send stalls a warm recipient for around 17
minutes, so the probe costs more than the answer.

### 8a. Three instrument facts that outlived the duty

Merged from the vault copy 2026-09-04. The wake-and-resume duty is retired; these three are facts
about the instruments, and they hold whoever reaches a cold seat.

| Item | Rule |
| --- | --- |
| **`mail.ps1 -To all` SKIPS THE SENDER** | Verified in the script: the broadcast loop carries `if ($r.IsSelf) { continue }`. Sensible for chatter, wrong for a wake. |
| On the day it was found, the sender was the exposure | The sender was the only seat that had actually hit the limit, so a wake built on that broadcast would have dropped the seat with the largest debt. Name yourself, or handle yourself as a separate step. |
| **`lastActivityAt` is not an arrival check** | A success return describes the sending tool, never arrival. The recipient's transcript is the only ground truth, and `mail.ps1 -Status` gives receipts for the mail half. |
| Its standing is weaker than it looks | The seat that used it reported *"9 of 9 verified"* and then withdrew that claim itself. The field's dismissal rests on a mechanism that was tested and falsified, so it is **ungraded**, not graded weak. |
| What that field actually did | The 10-minute clock confounds it, and on the one measured outage it showed activity for seats that were deaf. |
| **Snapshot the overwrite-in-place quantities, and only those** | The pre-roll 5-hour percentage and `seat-tick.state.json` are **replaced**, not appended. Once the window turns, the reading you needed is gone. |
| Transcripts reconstruct fine, so do not build a ritual | A seat that proposed *"capture everything, it is permanently unrecoverable"* refuted itself within the day, by reconstructing twelve seats to the millisecond after the fact. |

---

## 9. Traps

| Trap | What it is |
| --- | --- |
| **9.1 Warning so often nobody reads you** | A warning that fires on healthy cases trains every seat to discount it, so it is absent when it matters. **Warn on state transitions, not readings.** A pool that stays in state 1 does not need re-announcing. |
| **9.2 Reading a level and calling it a rate** | Two readings make a rate; one reading is a level with a story attached. With one sample, say the projection is unavailable rather than estimating from a single point. |
| **9.3 Turning into a rationer under pressure** | The pull is strong at states 2 and 3: suggesting someone drop work *feels* like helping. It is outside the seat, contradicts the owner's standing rule, and costs work that had headroom. **You say how long they have; they decide.** |
| **9.4 A stale reset time reading as a fresh window** | A reset time that has passed means your sample predates the window it describes. Re-read before publishing on it. A crossed reset makes a scary number harmless and a calm number meaningless. |
| **9.5 Relaying a peer's usage figure** | It carries their pool, their sample time and their instrument. Measure the pool you are reporting on, or attribute the number and its age -- *"as of 4 minutes ago, per session Y"* -- so the recipient can judge it. |
| **9.6 Escalating on percentage while the rate says otherwise** | The levels are a backstop. If the rate projection and the level disagree, the projection is the one to act on, and say both so the recipient sees the disagreement rather than inheriting your resolution of it. |
| **9.7 Reporting a quiet seat as DARK** | A live misclassification, 2026-08-14, self-reported: a seat was logged as *"DARK ~3h09m"* with a correct caveat underneath. It was user-driven, healthy, and had missed nothing. |
| **9.7a Label the column, do not judge in it** | **Label it "no activity for N" and let the reader judge** -- *dark* is a verdict wearing a measurement's clothes. **A correct caveat under an incorrect label is not a correct report.** Labels travel; caveats do not. |
| **9.7b Clock status is an ATTRIBUTE, never a FILTER** | A seat missing from a tick line is unexplained, not exempt, and filtering it out deletes the one row worth looking at. |

### 9.6a. RATE GOVERNS, owner-ratified 2026-08-14

Asked directly after this rule was contradicted in the field. The ruling settled a live contradiction, so
it is recorded with what it does **not** change.

| Item | Rule |
| --- | --- |
| The level still fires, and this is not a downgrade | It triggers the **cheap protect action** -- commit what you have, capture the at-risk sweep. That costs nothing and loses nothing, so a backstop firing is a real trigger and a stop sent on one was correct to send. |
| What the level stops doing | Halting new work when the burn says there is room. That is the whole change, and it is where the damage was: **2h37m of hold against a 48-minute real wait, by one builder alone.** |
| The inverted form was propagated by four seats | *"A level beats a rate, always."* One of the four abandoned a correct measurement to adopt it. **If you took "act on the level" from anyone, drop it.** COMMON carries the mechanism, and the reason nobody argued with it. |

### 9.8. Confirm the subject before refining the predicate

**A control that proves your reading is LIVE does not prove it is YOURS.** Before you grade a pool,
confirm the fleet is on that pool.

Requested by the Steward seat 2026-08-14. It is the most expensive trap on this list, because it
defeats the rest: every other rule here tests the NUMBER, and none tests the SUBJECT. It beat three
careful, independent analyses in a row, each correcting the last:

| | reasoning | verdict |
|---|---|---|
| predecessor, 03:27Z | pre-positioned a resume from weekly **38 percent** | impeccable, wrong pool |
| that seat, 21:47Z | **corrected** it to weekly **92 percent**, rewrote the conclusion | impeccable, wrong pool |
| that seat, 18 min later | **three samples with a working control** -- checked the reset countdown moved, specifically to rule out a frozen cache -- diagnosed a lagging estimator | impeccable, wrong pool |

**The third is the instructive one.** It did everything this file asks: verified the number,
verified the sample age, and asserted a control that had to behave differently if the reading were
stale. The control passed *because the reading really was live.*

**A liveness control cannot detect a subject error.** It confirms the instrument works, on whatever
it is pointed at. The instrument admits it in a parenthetical that is trivially read past:
*"(desktop app's current account -- no record for this session)"*.

On 2026-08-14 it printed URGENT STOP and *"exhausted in under a minute"* roughly **six times, all
correctly**. The subject was a pool with **zero fleet traffic**, while the fleet worked on another.

**The general form, and it is not confined to pools:** *whose is this* is a different question from *is
this real*, and every control in this file answers the second. Ask the first one out loud. *A rising weekly
identifies the live pool* carries the method that answers it for a pool.

### 9.8a. An owner confirmation fixes a fact, not a subject

A pool is a fact with a shelf life. Re-derive the subject across any boundary that could move it,
however well attested. Requested by a replacement Steward seat, 2026-08-28, from its own near-miss.

*Confirm the subject before refining the predicate* and the burn-rate section both assume the
subject is UNKNOWN or INFERRED. This one was neither. It was pinned by an owner confirmation, the
strongest instrument this seat has, and **the confirmation was correct when made.**

An account switch then moved the fleet, and a true line became a true reading of a pool nobody was
on.

| pool | reading | what it meant |
|---|---|---|
| `meforsupport` | 5-hour **98 to 100**, capped | **the pool the fleet had LEFT** |
| `messagefoundry` | 5-hour **4 to 9**, both windows rising | the pool it was on |

**Followed literally, the inherited header would have broadcast URGENT STOP to eleven seats sitting
on 91 points of headroom.** That is the harm *A percentage is meaningless without naming its pool*
names outright.

| Item | Rule |
| --- | --- |
| The `do not re-derive it` pattern is the active harm, not an aside | That instruction exists to stop drift and is good at it. |
| Why the strongest attestation is tested least | **It also reads as an instruction not to run the one check that would catch expiry.** The instruction protecting the fact is what hides its expiry. |
| A *do not re-derive* carries an implied *unless the boundary moved* | A successor will not supply that clause unaided. **Write the boundary beside the attestation.** |
| The loudest pool is the one guaranteed to be wrong after a switch | `meforsupport` read 100 percent precisely BECAUSE the fleet had left it; exhaustion is what caused the switch. |
| A high level is not the fingerprint | *A rising weekly identifies the live pool* already says so. Here the high level is causally downstream of the subject having moved. |
| Bounded, in the reporter's own words | One switch, one fleet, one evening -- a mechanism and a near-miss, not a calibration. Its three-way derivation was published BEFORE the owner confirmed it and agreed with it, so the request does not rest on the inference being right. |

---

## 10. Expiry conditions

Every standing rule here carries one, per [README.md](README.md).

| Rule | Stops being right when |
|---|---|
| The three states and their levels | The owner recalibrates them, or names a seat to inherit the tuning grant. They are a starting calibration, not a ratified constant; expect them to move |
| Time triggers 20 / 10 / 5 | Same. A 20-minute warning that routinely arrives too late is evidence, not an inconvenience |
| The tuning grant is unheld | The owner names a seat to hold it. **Watch the self-inflicted case:** a tuned threshold measured to have made a warning arrive too late presents as the ladder failing rather than as the tuning failing |
| The 90 percent gate stays owner-set | The owner says otherwise. **Not lifted by the tuning grant** -- it is a decision rule, not a level |
| Burn rate is primary | Only if a rate becomes unmeasurable; then the levels become primary, and say so in every reading |
| You do not ration | Never, short of the owner reversing the standing full-speed rule directly |
| Name the subject on every row | Never, while more than one account exists on the machine. If exactly one ever remains, it becomes a formality -- **verify that, do not assume it** |
| A cron is not on the ladder | The owner says otherwise, or the Steward becomes a model-calling seat again |
| Nobody is owed a restart | A seat can be interrupted mid-run, or a held session can outlive the turn that created it |
| The cron owns usage watching | **The newest row in `docs/usage/burn-history.jsonl` is older than the tick interval** -- the cron has stopped, and usage watching is the Lander's |
| The 90 percent Workflow rule is subsumed | It is owner-set; if the levels above are relaxed past 90, it binds again on its own terms |
| The cold-channel table in *Nobody is owed a restart* | Any Desktop or engine version change. It is build-specific and expected to go stale |
| The `token-collect.py` absence note in *Log per-seat tokens beside it* | `git cat-file -e origin/main:scripts/coord/token-collect.py` exits 0 |
| The `seats.json` and cold-channel entries live here | They land in [COMMON.md](COMMON.md), where they belong. They are general seat failures, not this seat's |

---

## 11. This file holds only what never expires; the burn log holds live state

| Item | Rule |
| --- | --- |
| What goes in the BURN LOG, never here | Current readings, which pools are in which state, the rates you measured, and the reset instants you read. |
| Where the log lives | `docs/usage/burn-history.jsonl` in the vault, appended by `scripts\coord\usage-log.ps1` (*Log every reading to the vault*). `docs/usage/README.md` states that log's invariants; they are not restated here. |
| What goes HERE | A lesson still true after every current pool resets: a trap, an instrument that lies, an ordering rule, a boundary of a gate, a measured mechanism. |
| Why the split is load-bearing | A number in here would be false within the hour, and a file mixing the two decays into a **trusted** document that is **wrong**, invisibly, because the durable half stays right. |
| State it once | State a load-bearing fact once and link to it. A fact restated in three places is corrected in one. |
| Every prohibition carries its expiry | Write beside it what would have to become true for it to stop being right, and how to check. A prohibition without one becomes permanent by default. *Expiry conditions* collects them. |
| Retract in place | Keep the wrong version and why it was wrong. Delete the error and the next session re-derives it. Six entries here do it. Grep **Retracted in place** and **Retired** to find them. |
| Tone | The useful sentence is the measured one, not the alarming one. **The cost of being wrong scales with how good the sentence sounds.** See `.claude/skills/fleet-conclude-from-a-reading`, row *The alarming sentence*. It moved there when COMMON.md became a skill-pointer index. |
| Where a dated episode note goes | Under `<git-common-dir>/mefor-coord/handoffs/`. Merged from the vault copy 2026-09-04. |
| Derive that directory, never type it | `git rev-parse --path-format=absolute --git-common-dir`. The bare `.git/` form is wrong from a worktree and lists nothing. |
