# KORUS Constitution

KORUS runs several AI coding sessions against one codebase. These are the rules a
session, a seat, a gate or a later spec may not break.

**Every article below traces to something measured.** The evidence is named inline so a
reader can check it instead of trusting it. An article with no evidence behind it does
not belong here, and adding one is an amendment rather than an edit.

## Core Principles

### I. No session is the only reader of its own work

Every piece of work has a second observer that did not produce it. Not a second pass by
the same session, and not a subagent that session briefed. A different session.

**Evidence.** On 2026-09-02, four substantive errors were made across two paired
sessions. All four were caught. **None was caught by its author.** Each was found by the
other session, and one by a worker whose report both sessions had overruled.

This is why the method has two long-lived seats rather than one. A single session with
better screens is not a substitute, because the errors it makes are the ones its screens
do not model.

### II. Publish readings, not conclusions

A session tells its peers what it ran and what came back: the command, the timestamp, the
ref, the raw output. **Never a conclusion without the reading that produced it.**

A verdict is welcome. A verdict alone is not. A peer who receives only a conclusion can
agree or doubt; a peer who receives the reading can run it and disagree with evidence.

**This does not forbid stating a verdict, and Article III requires one.** A refusal is a
conclusion, and it is the only signal a process gate carries that cannot be faked. So a
report says what it decided and shows what it read. The failure this article names is a
conclusion travelling alone, not a conclusion existing.

**Evidence.** On 2026-09-02 a worker reported a refusal string verbatim, beside a
conclusion it had been handed. Two senior sessions agreed the conclusion was wrong. **The
string was right and both sessions were wrong.** It survived because its brief said "do
not paraphrase the refusal; quote it".

So quote refusals, errors and rulings **character for character**. A paraphrase changes
scope silently, and the changed version is what later work encodes.

### III. A gate that cannot check identity must make refusal legible

Every session pushes as one account, so the platform's own protection against an author
approving their own change is unavailable. Any review gate built on top of that is therefore
**a process gate, not an identity gate**, and it is that by necessity rather than by choice.

**A process gate can be satisfied by the party it is meant to check.** So the only signal
it carries that cannot be faked is a **refusal**. Refusal must therefore be recorded, and
it must be as legible as approval. A gate that can only record approval is measuring
whether a step happened, which is the one thing it did not need to know.

**Evidence.** On 2026-09-02 a pull request drew two reviews eight minutes apart. The first
found four defects and deliberately withheld its approval. The second found nothing and
applied the label, which enqueued the change. **The gate recorded the review that found
nothing.** The careful reviewer's signal was its refusal, and the gate had no way to see
one: a reviewer that declines to pass looks exactly like one that never ran.

This article does not require a human to judge. A reviewer may be a process that runs
checks and applies a label when they pass, which is what the Owner specified for the gate
described above. The requirement is narrower and it survives either design: **whatever
refuses must leave a mark the gate can read.**

**The gate this article was written about was removed on 2026-09-04.** The Owner dropped it
as a required check on `main`, leaving `gates (ubuntu-latest)` and `gates (windows-latest)`,
and `.github/workflows/review-gate.yml` was deleted. **The evidence above is kept because the
incident happened and the reasoning drawn from it did not depend on that gate's design.**

**The article stands, and its subject is now any future gate.** Nothing that produced it
changed: every session still pushes as one account, so no process gate KORUS can build is
able to tell an author from a reviewer. **KORUS has no gate meeting this requirement today**,
and anything proposed to replace one must record refusal as legibly as approval before it is
worth building.

**That paragraph left open, until 2026-09-12, whether the seat that fed this gate would
decision and is not settled here" until 2026-09-12.** The Owner settled it on 2026-09-12:
the seat retired and nothing replaced it. The article is unchanged, because it binds a
gate rather than a seat.

### IV. Every claim names the condition it did not vary

Independence is relative to what was varied. Two observers who differ in everything they
thought to change, and match in something neither thought to change, produce corroboration
worth one observation.

**Evidence.** On 2026-09-02 two workers on different accounts, running different tasks,
each ran both arms of a controlled comparison and reported the same result. The conclusion
was wrong. Both were headless, and **a headless session cannot vary its own
headlessness**. The confound was invisible from inside, and no care by either worker could
have surfaced it. An observer in a different mode running the same command settled it in
minutes.

So a finding states what was held constant, not only what was changed. When two sessions
agree, the question is not what instrument they shared. It is **what is true of every run
either of them has ever made**.

### V. No rule may manufacture its own evidence

A rule that tells a session it cannot do something stops it trying. The absence of an
attempt then reads as confirmation.

**Evidence.** Two shipped files told every session it could not declare its own seat. It
could. Two workers on the same config root, 33 minutes apart, differed in what their brief
said, and only the one told it could, did. The other rendered undeclared, which is exactly
what the false rule predicted. **A rule that suppresses the action which would disprove it
generates its own supporting evidence.**

Before a rule forbids something, someone must have tried it and recorded what happened.

### VI. A number without its instrument is not a measurement

Report the command beside the count. Print the needle beside every zero. Run a control
that would fail if the search were broken.

**Evidence, repeatedly.** A zero from a hyphenated spelling, while the spaced spelling sat
in the same file. A count of 240 against a true 274, because two tools resolved one path
string to two different files with no error anywhere. A clean scanner result that was
really the exit code of the command it had been piped into. **A plausible result is not
evidence the instrument worked, and the plausible one gets checked least.**

### VII. Waiting is a design cost and it is measured

Seat lifetimes are chosen against measured spend, not preference.

**Evidence, this fleet, and the surprise is the point.** Tokens a minute: actively working
10,041; waiting on a three-minute heartbeat 2,108; **waiting in a ten-minute sleep loop
22,275, which is more than working**; turn over and idle, **zero**. Recorded in issue #9.

Waiting is not cheaper than working. It is roughly twice the price, because a session that
wakes re-reads its whole context to do nothing.

**The costly state is waiting, not existing.** A session that finished its turn and was
never reaped spends nothing in tokens. It costs disk and worktree clutter, which is a
different budget with a different owner. So the rule is **not** "end rather than idle". It
is **never tell a worker to poll, to sleep, or to wait for a reply**. A worker ends because
its worktree is worth reclaiming, not because idling is expensive.

This is also the cost a design must pay back when it needs a worker to persist, and that
trade is stated in the spec rather than assumed.

### VIII. The account roster is assigned by the Owner, and no design may infer it

KORUS runs across several accounts. **Which accounts are in play is the Owner's
assignment**, not a fact about the machine. The number changes as accounts are added or
retired. Nothing may hard-code it, and nothing may infer it by looking at what happens to
be on disk.

This is the same rule that stops a hook inventing a session's goal. **A roster is intent.**
A machine that derives one from the filesystem produces something that looks authoritative
and says nothing about what the Owner wants used: it will happily enlist a config root that
exists but is not meant to be spent, or one that shares an account with another.

Reading the roots is still worth doing, as an **instrument that checks the roster rather
than replacing it**. It answers whether an assigned account can start a session, and
whether two roots resolve to one account. When a reading and the assignment disagree, the
assignment is what the fleet is for and the reading is what the machine currently is. Both
matter, and neither is the other.

A seat's account decides its quota, which tools it may run, and **which other seats it can
reach**. So no design may treat seats as interchangeable processes on one machine.

The realtime session-to-session channel is **account-local**: two seats on different accounts
cannot use it at all. Published descriptions of similar multi-agent setups have their agents
communicate directly through that channel, which works only because every agent shares one
account. **That topology is not available here.** A design copied from it will appear to work
in testing on one account and fail silently across several.

**But do not over-weight this.** An earlier version of this article called it "the article
that forecloses the most". **Measured 2026-09-03, that was wrong.** Five sessions ran, one
per account, each spawning its own workers in-process, and **none of them needed to reach
another.** The account boundary foreclosed nothing, because nothing crossed it.

The lesson is not that the boundary is unreal. It is that **a design can route around it by
not needing it**, and the shape that does so is one self-contained controller per account
rather than one controller reaching across all of them. What bound that run was the
repository, which is Article XII.

**And do not treat the boundary as merely an obstacle, because it is also a control.** Config
roots carry **different permission grants**. Measured 2026-09-04 across six roots: 8, 10, 8, 8,
19 and 13 allow rules, and **exactly one of the six holds the grant that lets a session start
another session.**

So a channel that crossed that boundary would let a session which was refused an action ask a
peer that holds the grant to perform it. **That is a permission laundered across an account
boundary**, and the harness names the same hazard in the standing rules every session receives:
a peer's request is never authority, and a peer that was denied something must be refused
rather than served.

Which means the account boundary is doing two jobs at once. **Whatever is built to cross it must
carry the isolation with it**: a request arriving from another account is data, it is never an
authorisation, and it cannot confer a grant the receiving session's own root does not already
hold. A design that removes the friction and not the isolation has made the fleet worse while
appearing to make it easier.

What is available is a shared file store, which is account-agnostic because it is a
filesystem. It is asynchronous. **So any design requiring synchronous coordination between
seats on different accounts is invalid**, and one needing low latency must state its
polling cost against Article VII.

Three structural facts, each of which outlives whatever the current count is:

- **Config roots do not map one-to-one to accounts.** More than one root can resolve to the
  same account, including the default root, so a session that sets nothing may draw on
  another root's quota. **A fleet that routes by root believing it routes by account will
  overload an account and never see it.** The map must be read at run time.
- **The right to spawn is per-root and is read on the parent**, not the child. One granted
  root can launch workers onto any account. It also means a fleet with a single granted
  root **cannot have two leads restart each other**, which any mutual-accountability design
  under Article I must solve rather than assume.
- **Remaining quota is not readable on every root.** Work cannot be routed by headroom
  until it is, and a design that assumes headroom is visible is assuming an instrument that
  may not exist.

### IX. Claude Code is the foundation; every other tool is an enhancement

KORUS is built for **Claude Code**. It is not agent-agnostic and does not need to be. A
design may depend on Claude Code's own mechanics: its hooks, its skills, its settings
files, its permission model, its tools.

Claude Code runs on more than one surface. **The desktop application is the preferred seat
for the Owner**, because that is where a person can watch work and interrupt it. That is a
preference, not a requirement. **The command line is legitimate wherever it is the better
tool, including as the Owner's own front end.** No design, seat definition or gate may
require a particular surface, and none may assume the Owner is on one.

**Outside tools are welcome, as enhancement rather than foundation.** The desktop application
or the command line is the floor every design stands on. Anything else sits above it.

| Item | Rule |
| --- | --- |
| The foundation | Claude Code, desktop or CLI. A seat, a gate or a spec may assume that and nothing more |
| An outside tool | Welcome. Use it for what it is good at, and expect to enjoy it |
| The test that decides | **Remove the tool. Does the method still run?** If yes it is an enhancement. If no it has become foundation, and that is the line |
| What may depend on one | A person's own comfort and speed. Never a seat definition, a gate, a spec, or a rule another session must follow |
| Where a tool earns its place | A harness that spawns sessions, watches a fleet, reads quota or annotates a diff is doing work KORUS has not built and need not build |

**Why the line sits there rather than at "no outside tools".** A tool the Owner enjoys using is
worth having, and refusing one on principle costs real convenience for no gain. The cost only
arrives when a rule cannot be followed without it. At that point every session lacking the tool
is locked out of the method, and the method has silently narrowed to whoever installed it.

**This is Article XII's reasoning applied to tooling.** The shared write surface binds because
everyone touches it. A rule that needs a particular tool creates a second such surface, with a
smaller membership and no measurement of who is inside it.

**How to tell the difference in practice.** An enhancement makes the same work faster or nicer
for whoever runs it. A foundation is something a later reader must install before a written rule
makes sense to them.

**But the surfaces are not equivalent, and a capability measured on one does not transfer
to another.** This is Article IV applied to a standing condition rather than to a single
finding, and it has already cost real work.

**Evidence.** Three differences, each of a different kind:

- **What a session can see.** The desktop application's session tooling enumerates an
  in-memory map of sessions **the desktop app itself spawned**, so a session started any
  other way "is never entered into it -- not filtered, never registered -- and cannot be
  listed or messaged by it". A design that reaches peers through that channel silently
  loses every peer it did not spawn.
- **What a session can do.** A desktop session cannot directly start another session.
  A command-line session can. So the seat that spawns workers is constrained by its
  surface, not only by its permissions.
- **How a tool behaves.** On 2026-09-02 an identical command, on one account, in one
  session, succeeded through a tool interactively and was refused headlessly. **The
  refusal named a cause that was not the real one**, and two sessions built a wrong
  mechanism on it before an observer on the other surface settled it in one command.

So a finding states the surface it was measured on, and a claim measured on one surface is
not carried to another without re-measuring. Article IV already requires this; it is stated
again here because the surface is the condition observers are least likely to think of
varying, for the same reason Article IV gives: it is usually the only one they have.

### X. A seat that cannot be measured cannot be steered

Every seat's **cost** is attributed to that seat, and every seat's **conduct** is checkable
against what its playbook told it to do. Both, separately. A fleet total answers neither
question.

Three things must be answerable about any seat, at any time:

- **What has it spent**, on which account, and how much of that account is left.
- **Did it do what it was told**, or something adjacent that looked like it.
- **What came out**, in work that landed rather than in activity.

**A design may not assume any of these is available.** Where an instrument does not exist,
the spec says so and treats it as a gap to close, not a fact to rely on.

**Evidence, and this article has now been wrong twice about its own fleet.**

Read 2026-09-03 by running the fleet's own usage reader: **four of five accounts returned live,
account-verified five-hour and weekly utilisation with reset times, and the tool ranked them and
named the account with the most headroom.** The fifth failed with an authentication error that
printed its own remedy beside it. Weekly utilisation across the four was 0, 1, 2 and 9 per cent.

**So the fleet has a headroom meter. It works, it ranks, and it says when it cannot read an
account.** What is broken is one hook, which reads a filename nothing writes, while a script that
answers sits three directories away.

Two earlier versions of this article were wrong, and the sequence is the lesson:

1. It said the fleet spent a night **without a meter**. False: a collector was writing.
2. Corrected to say the meter existed but **nothing read it**. Also false: a reader existed too.
3. What is true is narrower and duller. **One hook is misconfigured.**

Each correction was published confidently and each was still wrong. The error survived two passes
because the evidence was about **this document's own session**, which is the evidence a writer
checks least, and because each fix was a smaller version of the same mistake rather than a fresh
reading. **Ask what the instrument would say if you ran it, and then run it.**

**Scarcity was absent when this was written and is no longer.** At the time, weekly utilisation
sat between 0 and 9 per cent. After the 2026-09-03 run it read 5, 9, 17, 7 and 49 per cent,
and
shortly after that **every account began failing the read with HTTP 429**, which is rate limiting
rather than expiry: the instrument goes blind exactly when load makes it worth reading. Do not
carry either figure forward. Re-read it. Article VIII still requires the roster; it does not
require rationing. **A design that
rations an abundant resource is spending on a constraint it invented.**

What survives, and it is the part worth keeping: **a design may not assume a measurement is
available, and where an instrument exists a design must be pointed at the one that answers.** The
failure here was never absence. It was three layers of aim.

**Absence and zero must be distinguishable.** A seat with no commits may be scoping, may be
running a long serialised suite, or may be dead. From outside those render identically, and
a fleet that cannot tell them apart will reap a working seat or wait on a dead one. An
instrument that returns nothing must say whether it found nothing or failed to look, which
is Article VI applied to the fleet's own telemetry.

**A measure nobody reads is not a measure.** Publishing a number that no seat consults is
the same as not measuring, and it is worse than not measuring because it looks like
diligence.

### XI. A seat's job is to write something down

If a proposed role's product is a message to another role, it is not a seat.

This is the rule that produced the current roster, and it is quoted from the design note
that recorded the decision:

> **The rule that generated all of it.** Every seat that survived does its job by WRITING
> SOMETHING DOWN. Every seat that went away did its job by TALKING TO ANOTHER SEAT.

**Evidence.** Seven seats were retired on 2026-09-01 and six kept. Every retained seat had
an artefact: the Console wrote briefs, the Builder writes a pull request, another seat wrote
a label, the Regulator writes an attribution log, the Steward writes files other
seats read, the Lander writes a merge order. Every retired seat existed to relay, route or
represent, and produced nothing a later reader could open.

**The roster moved again on 2026-09-10 and this article held.** The Owner retired the
Console. The Manager replaced it and writes the same artefact, a brief, so the seat that
went away was not one this article would have kept out. The retirement turned on breadth,
not on output: a Console reached across every account, and a Manager sits inside one.

**It moved a third time on 2026-09-12, and this is the case the article does not cover.**
The Owner retired a seat, deliberately unnamed here, and nothing replaced it. That seat wrote an artefact, a label
and findings on a pull request, so writing something down did not save it.

**So the rule is necessary and not sufficient, and it always was.** A seat whose product is
a message is not a seat. A seat whose product is an artefact nobody is required to read can
still be retired for that, which is what happened here: the gate that made the label binding
went on 2026-09-04 and the seat followed eight days later.

**Why this is constitutional and not merely tidy.** A seat whose output is a message
disappears when its session ends, so its work cannot be checked by Article I, cannot be
republished as a reading under Article II, and cannot be measured under Article X. A relay
seat is invisible to three other articles at once.

It also matches the cost model. Article VII says an ended session spends nothing and a
waiting one spends the most. A seat that must stay awake to relay is the expensive shape;
a seat that writes and exits is the cheap one.

**Written down is measured. Read is not, and the first reading is thin.** This method
accumulates context on an assumption nobody here has stated: that a fuller playbook makes the
next seat better. Nothing bounds how large one may grow. In this repository at commit
`1b6b7fc`, `roles/COMMON.md` is 145,758 bytes and the largest, `roles/LANDER.md`, is 288,883.

**Evidence, 2026-09-04, and it is a floor rather than a rate.** Across 401 session transcripts
on this machine, **25 issued a Read against any role playbook**. Reads of `COMMON.md` numbered
**84: five whole-file, and 79 with an explicit offset or limit.** A transcript records every
Read with its `file_path`, `offset` and `limit`, so read depth is recoverable afterwards.

```powershell
$roots = "$env:USERPROFILE\.claude\projects", "$env:USERPROFILE\.claude-account-1\projects"
$t = Get-ChildItem $roots -Recurse -Depth 1 -Filter *.jsonl -File
$t.Count
($t | Select-String -Pattern '"name":"Read","input":\{"file_path":"[^"]*roles..[A-Z][A-Z]' -List).Count
$m = ($t | Select-String -Pattern '"name":"Read","input":\{"file_path":"[^"]*roles..COMMON\.md"(,"(offset|limit)")?' -AllMatches).Matches
$m.Count
($m | Where-Object { $_.Value -notmatch 'offset|limit' }).Count

# The two sizes, from this repository.
git cat-file -s HEAD:roles/COMMON.md; git cat-file -s HEAD:roles/LANDER.md
```

**What this instrument cannot say.** Each line is a way the number is too low, or the wrong
shape:

- **It is not a compliance rate.** The 401 transcripts include many sessions that were never
  seats, so 25 is a floor over a mixed population.
- **It counts one tool.** A playbook reached by Grep, by a Bash `cat`, or injected by a hook is
  invisible to it.
- **It counts two config roots.** Four more exist on this machine and are outside the corpus.
- **An earlier hand count of the same corpus read 22 sessions**, and split the same 84 as six
  and 78. The command above returns 25, five and 79. I could not recover the definition behind
  the smaller figures, and neither reading moves the finding.

**So playbooks are read rarely, and read in pieces when they are read.** That is one
measurement on one machine. It settles nothing about whether a larger playbook helps, and it is
why **no rule here caps playbook size**: Article V forbids a prohibition nobody has tried and
recorded. Testing the hypothesis is what would earn one.

**Numbering is not priority.** This article was added after the first ten and appended
rather than inserted, because renumbering would break every reference made to the document
in between.

### XII. The shared write surface is the boundary that binds, not the account

Workers scale with accounts. **Landing does not.** Every worker writing to one repository
contends for it, and the contention is set by which files they touch, not by how many of them
there are.

**Evidence, 2026-09-03 to 09-04, and it is the largest run this method has had.** Five
controllers ran, one per account, each spawning its own workers. They produced 46 pull
requests in about three and a half hours and landed 34 over the following day, at a sustained
two to five an hour.

**Thirty-three of those thirty-four merged commits touched the same file.** The item ledger.
Not by accident and not by carelessness: **every item's pull request updates the ledger by
construction**, so the contention is a property of the design rather than of any worker's
behaviour.

**The instrument, because Article VI binds this article too.** The four figures above were
counted by hand during the run and carried a date but no command, which is the shape this
document discounts when an outside source does it. These are the commands, and what they
return now:

```powershell
# Pull requests opened, and landed, in the window. Both return a SUPERSET of the run.
gh pr list --repo MEFORORG/MessageFoundry --state all --limit 300 --search "created:2026-09-03" --json number,createdAt
gh pr list --repo MEFORORG/MessageFoundry --state merged --limit 300 --search "created:2026-09-03" --json number,mergedAt

# The merge rate, bucketed by the hour of mergedAt.
gh pr list --repo MEFORORG/MessageFoundry --state merged --limit 300 --search "created:2026-09-03" --json mergedAt --jq '.[].mergedAt' | ForEach-Object { $_.Substring(0,13) } | Group-Object | Sort-Object Name

# Which file the landed commits contended for. This NAMES the file rather than assuming it.
# Run it inside the MessageFoundry checkout, after a fetch.
git log origin/main --since=2026-09-03 --until=2026-09-05 --format= --name-only | Where-Object { $_ } | Group-Object | Sort-Object Count -Descending | Select-Object -First 5 Count,Name
```

**Run 2026-09-04, and the gap is the finding.** The day window returns **74 opened and 53
merged**, against the 46 and 34 recorded during the run. The commands are right and the window
is wider than the run. **The run's own subset cannot be recovered.** Every seat pushes as one
account, so no author filter separates the five controllers from the rest of that day's work.
Article III names the same missing distinction for review.

**The two figures the article rests on do reproduce.** Merges bucketed by hour read two to six
an hour across the drain on 2026-09-04, against the two to five recorded at the time. And **51
of the 53 commits in that window touched `docs/BACKLOG.md`**, against 33 of 34: a different
count over a wider window, and the same ratio.

So **46, 34 and three and a half hours were recorded by hand and are not now reproducible.**
Treat them as an anecdote about one evening. What is measured is the ratio, and the ratio is
what the three consequences below need.

The merge queue rebases and revalidates each entry against the branch the previous entry just
changed. So the queue is serial in exactly the dimension the fleet was parallel in, and
**adding a controller adds arrivals without adding service.**

Three consequences a spec must honour:

- **Partition the write surface, not the workers.** Where a shared file is touched by every
  unit of work, that file is the throughput limit and no amount of parallelism upstream moves
  it. Split it, or batch the updates to it separately from the work.
- **A claim on an item is not a claim on a path.** Two controllers can legitimately hold
  different items and still collide, because the paths their work touches were never claimed.
- **Serialising the merge is a real control and it has a real cost.** It is what made this run
  survivable. It also makes one seat both the throughput ceiling and the single point of
  failure, and **that seat can only be correct about a queue whose arrivals it does not
  control.** It is also **the seat with the least ability to reduce its own load, because every
  fix it applies is another push into the same queue.**

**The multiplier is jobs per entry, not queue depth.** Measured by the seat doing the merging,
not by me: eighteen entries queued produced **zero merges in an hour**, because five concurrent
groups of about twenty-two jobs each is roughly a hundred and ten jobs against about twenty
runners. A two-deep queue then merged both entries in twenty minutes. It changed the depth and
watched throughput invert, which is a better instrument than any count of open work.

So a design that limits **how many changes are in flight** has tuned the wrong number. What
binds is how many CI jobs each change drags behind it.

**And a uniform remedy applied across a batch manufactures its own conflicts.** The same seat
patched eight pull requests the same way to fix one problem, which made a second file contended
that had not been before, and two of the eight then conflicted with each other in the queue. The
ledger is contended **by design**; that file became contended **by a fix**. A batch remedy is a
write to every member of the batch.

**A correction belongs in this article rather than beside it.** Reading this run 3.6 hours in,
I reported 46 open against 3 landed and called it a structural throughput ceiling. It was a
burst measured at its worst moment. The queue drained. **The contention was real and my
conclusion from it was wrong**, and the difference between those two is the difference between
a snapshot and a rate.

### XIII. Work reaches the model through Claude Code, never through the API

Every seat, every harness and every orchestrator reaches the model by running **Claude Code** --
the CLI or the desktop application. **No design may call the Anthropic API directly.**

This is not Article IX restated. Article IX governs the **surface** a design may require. This
one governs the **path to the model**, and the two fail differently: a design that requires a
GUI is visibly narrow, while a design that reaches the API is invisibly expensive.

**The reason is the roster.** Article VIII establishes that the accounts are assigned by the
Owner. Those accounts are **subscriptions**. An API call does not touch them. It bills
pay-as-you-go credits against a different balance, so the roster the Owner assigned goes unspent
while a bill accrues somewhere nobody is reading.

| Item | Rule |
| --- | --- |
| What is permitted | Anything that runs `claude`, or drives the desktop application. A harness that spawns a terminal agent inherits Claude Code's own subscription authentication by construction |
| What is forbidden | An orchestrator that holds an API key and calls the model itself. The SDK-based category is the one this rules out, not the terminal-harness category |
| The failure mode | Not a design choosing the API. **A permitted design silently becoming a forbidden one through the environment it inherits** |
| What to check | Whether `ANTHROPIC_API_KEY` is set in the environment a session inherits, and what `ANTHROPIC_BASE_URL` points at |
| Who is responsible | The seat that spawns. A parent passes its whole environment down, so a clean parent is the only control that reaches every child |

**The mechanism, and it is the part worth knowing.** Claude Code will use `ANTHROPIC_API_KEY` if
it finds one. Nothing announces the switch. So the risk is never a tool deciding to use the API;
it is a correct tool inheriting an environment that has already decided.

**Evidence, measured 2026-09-04 on this machine.** `ANTHROPIC_API_KEY` is unset, and
`ANTHROPIC_BASE_URL` is set. Command:

```
python -c "import os; print({k: bool(os.environ.get(k)) for k in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL')})"
```

**What was not varied:** one machine, one session's inherited environment, one moment. A spawned
child was not probed, and a settings root may pin a value this command cannot see. So this is a
reading about the parent, not a proof about the fleet.

**KORUS's own spawn inherits everything, and this is the measured gap.**
`scripts/cron/watch-ci-red.ps1` is the fleet's only agent spawn. It sets
`$psi.UseShellExecute = $false` and never touches `$psi.Environment`, so the child receives the
parent's whole environment. Commands:

```
grep -nE 'UseShellExecute|\$psi\.Environment' scripts/cron/watch-ci-red.ps1
git grep -c 'ANTHROPIC_API_KEY|env_remove|Environment.Remove' -- scripts/
python -c "import os; print(len(os.environ))"
```

The first shows the assignment and no filter, the second returns **nothing anywhere in
`scripts/`**, and the third returned **96** variables in the parent at the time of writing.
**What was not varied:** one script, one machine, one moment. No spawned child was probed to
confirm what it actually received.

**CLOSED at that one site, 2026-09-04.** The reading above is kept because it is what the gap
looked like, and because the commands still reproduce the shape anywhere else. `Start-Child` now
removes `CLAUDE_CONFIG_DIR`, `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from every child before
`Process.Start`, with no parameter to skip it -- that function is the only spawn in the file, so a
name on the list cannot reach a child by any route the script has. `ANTHROPIC_BASE_URL` is passed
through and **warned about** rather than stripped, because it is set on this machine and may be a
proxy somebody chose; removing a deliberate setting to fix a hazard that may not be there is the
worse trade, and a broken spawn is the loud failure.

**The child was probed this time, which the reading above could not claim.** A stub seat reports
its own environment from inside the spawned process, so the evidence is what the child received
rather than what the parent's source says it does. Both arms are pinned and they red on different
mutations: deleting the removal loop reds the three must-not-inherit cases and leaves the control
green, while adding one variable too many to the list reds only the control. The receipt names what
it removed on every run, because a strip nobody can see is a behaviour change that reads as no
change at all.

**The gate is owed for the REST of the fleet, and this does not discharge it.** One spawn site is
guarded. Nothing stops the next one from being written without the strip, and
`bin/ccx-doctor.ps1`'s `Invoke-Probe` -- the repository's other `ProcessStartInfo` caller -- takes
an `-Environment` parameter but strips nothing by default. **Unmeasured:** whether any probe it
runs is affected, and whether a `claude -p` child with no `CLAUDE_CONFIG_DIR` authenticates against
the default root on this machine.

**One outside tool implements this rule, which is how the mechanism was found.** Vibe Kanban
reads `apiKeySource` out of Claude Code's own init message and warns *"ANTHROPIC_API_KEY env
variable detected, your Anthropic subscription is not being used"*, with a toggle that removes
the variable before spawning. It is the only tool in a ten-tool survey that checks.

**Do not copy its coverage, only its idea.** A search of all 3,284 lines of its
`claude.rs` returns zero matches for `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` or any
`CLAUDE_CODE_*`. It guards one variable.

**This article had no gate behind it at all** -- exactly the shape *Playbook size and format* says
decays. It now has one at the fleet's only agent spawn, and prose everywhere else. That split is
the point rather than an oversight: measured 2026-09-04 across this fleet, the same house rule held
at **0** violations where a gate refuses and **93** where it was prose alone. The rule stands
because the Owner set it. The remaining gates are owed.

**Expiry.** This stops being right if the Owner moves billing to the API deliberately, or if
subscription authentication becomes reachable without running Claude Code. Either would be an
Owner decision, and neither has happened.

## The execution environment

These are conditions, not principles, and **every number here is a reading with a date**.
They bound every spec, and a spec written without them will be wrong in ways that appear
only at scale.

**Read on 2026-09-02, and expected to change.** Six config roots resolved to five distinct
accounts, with two roots sharing one, and one of those two was the default root. All six
started a session. Cross-account messaging is a shared file store: reading a box directly
took about 46 milliseconds, against about 17.5 seconds through the documented listing
command, which also returns every box on the machine.

**That is a reading of the machine, and it is not the roster.** The Owner assigns which
accounts are in play. The reading is useful only as a check against that assignment, and
the two disagreeing is a finding rather than an error. Re-read it; do not cite it.

**Not established.** Whether the account boundary affects anything beyond messaging, quota
and grants. Whether the shared file store sustains a correction loop at the pace Article I
needs: the result in Article I was measured on the **account-local realtime channel**, and
that channel does not exist between accounts. **Carrying that result across the channel
change would be exactly the substitution Article IV forbids.** Testing it is the first
thing any multi-account design must do.

**One project, not many.** Every seat works on one codebase, so seats converge on one merge
point. Adding accounts adds capacity that this convergence may not let the system spend.
That is a hypothesis from a single evening, not a measurement, and it is written here so a
later spec tests it rather than inherits it.

## What the record must contain

**Findings live where the work happens.** A finding filed against a published copy, in a
repository where nobody builds, is a finding nobody will act on.

**Numbers carry their date and their source.** A measurement without a date cannot be
told from one the code has since invalidated.

**Measured and asserted are marked apart.** This distinction is load-bearing, and it is
the first thing lost when a document is summarised.

**A retraction sits at the claim, not below it.** A correction posted after a wrong claim
never reaches the reader who lands on the claim.

**No glyphs or emoji anywhere.** A glyph's meaning is positional, and that is invisible to
anyone who learns it from examples rather than from a definition. Words carry their scope
in the sentence around them. Say the word.

## How a change lands

**One coherent change per commit**, with a message saying what was measured and what it
changes.

**Nothing merges on its author's own approval.** See Article III. **No gate has enforced this
since 2026-09-04**, when the review gate was removed, so it is a standing norm and not a check.

**The operational sequence lives in one place and this is not it.** It is
`roles/COMMON.md`, section "Your pull request has to survive your own exit", at commit
`3143b0ec`. Read it there rather than from a summary here, because a second copy drifts and
the drift is invisible until someone follows the wrong one.

One step from that sequence is repeated here, and **on 2026-09-04 it stopped being an
instruction and became a finding.** The label it names belonged to the review gate, which was
removed that day, so there is now nothing to label and no run to wait for. **Do not do this,
and do not delete it**: the finding generalises to any gate with the same property.

The retired instruction read: wait for the branch's gate run to complete before applying the
label, then read the label back. The gate stripped the label when its run executed, which is
after the push command returns, so labelling immediately after a push was a race you lost
silently. Measured by the seat that lost it: **fifteen of sixteen pull requests ended with no
label while every command reported success.**

**The general shape, which outlives that gate.** When a check invalidates on an event, the
event is **the gate's own run**, not your command returning. So wait for the run, then read
the result back. A step that reports success either way has not been measured until something
reads it back, which is Article VI applied to a write.

That `roles/COMMON.md` section reached a commit only on 2026-09-04. Before that it, and two
others beside it,
**existed in no commit anywhere** -- one uncommitted file in a checkout fifty-two commits
behind. The fleet's merge procedure had no durable home while being the procedure whose
missing step cost those fifteen labels.

**A number is allocated before it is cited.** Never search for the next free identifier.
Two sessions that both search pick the same one, create differently named files, merge
cleanly, and corrupt the ledger with nothing reporting a problem.

**Never cite an identifier nobody has allocated.** While it is unissued the citation
resolves to nothing, which is honest. The day someone allocates it, that citation starts
resolving to unrelated work, and it reads as a working cross-reference forever.

**A gate is never bypassed.** If a gate is wrong, fix the gate in its own reviewed change,
and prove it still catches what it was built to catch before trusting it.

## Governance

This constitution supersedes other practice in this repository. Where a spec, a plan or a
playbook conflicts with it, the constitution wins and the other document is amended.

**Amendments require evidence.** An article is added, changed or removed by naming what
was measured and when. A principle that cannot be traced to a measurement is a preference,
and preferences belong in a style guide.

**Articles may be proven wrong.** Every article here rests on a small number of
observations, several from a single night of operation. When a later measurement
contradicts one, the article changes and the old text stays with the reason, because a
reader who remembers the old rule needs to see it named as retired rather than find it
silently absent.

**Version**: 1.16.0 | **Ratified**: 2026-09-02 | **Last Amended**: 2026-09-12

<!--
Amendment log. Kept because Governance requires retired text to stay with its reason.

1.16.0 2026-09-12  The Owner retired a seat, deliberately unnamed here, and nothing replaced
       it. Two articles described that seat in the present tense.
       ARTICLE III IS UNCHANGED and its evidence is untouched. Its closing sentence read
       "Whether the Reviewer seat outlives the gate it fed is an Owner decision and is not settled
       here". That question is now answered, so the sentence is kept with the answer beside it. The
       article binds any future gate rather than any seat, which is why the retirement costs it
       nothing.
       ARTICLE XI GAINS THE CASE IT DID NOT COVER. Its evidence listed that seat among the
       retained seats because it wrote a label. That seat has now retired while still writing one,
       so writing something down is NECESSARY and not SUFFICIENT. The article's prohibition is
       unchanged: a seat whose product is a message is still not a seat. What is added is that an
       artefact nobody must read does not keep a seat alive. The reading is kept in the past tense
       and the later change appended, per Governance.
       Instrument: docs/roles/seats.json at this commit lists five live seats and carries reviewer
       plus five of its spellings in its retired map, each with a reason. Control: the same file's
       retired map already carried console and its three spellings, so the map was live rather
       than empty.

1.15.0 2026-09-10  Article XI's evidence named the Console as a retained seat in the present
       tense, and the Owner retired that seat on 2026-09-10. The 2026-09-01 reading is kept in
       the past tense, which is what it always was, and the later change is appended beside it.
       The article itself is unchanged: the Manager that replaced the Console writes a brief, the
       same artefact, so the retirement turned on breadth rather than on output.
       Instrument: docs/roles/seats.json at this commit lists six live seats and carries console
       in its retired map with the reason. Control: the same file's retired map already carried
       dispatcher and liaison, so the map was live rather than empty.

1.14.0 2026-09-04  The review gate was removed by the Owner, and this document described it as
       live in three places. Verified against the live GitHub API: the review check is no longer
       required on main, which now requires gates (ubuntu-latest) and gates (windows-latest), and
       .github/workflows/review-gate.yml is deleted.

       ARTICLE III IS NOT RETIRED and its evidence is untouched. The 2026-09-02 incident happened:
       a pull request drew two reviews eight minutes apart, the first found four defects and
       withheld its approval, the second found nothing and labelled it, and the change merged on
       the commit the first reviewer had refused. What changed is only that the article's worked
       example describes a gate that no longer runs. The condition underneath it did not change --
       every session still pushes as one account, so no process gate KORUS can build can tell an
       author from a reviewer -- so the article now states a requirement for ANY such gate, and it
       records that KORUS has none meeting it today. The opening sentence's "The review gate is
       therefore" became "Any review gate built on top of that is therefore", which is the same
       claim without asserting a live gate.

Whether the SEAT that fed that gate survives its removal is an Owner decision. It is not
       answered here, and the article says so rather than leaving the question implied.

       HOW A CHANGE LANDS: the wait-then-label-then-read-back step is now marked as a retired
       INSTRUCTION and kept as a FINDING. A seat following it today would wait on a run that will
       never come. The measurement stays verbatim -- fifteen of sixteen pull requests ended with no
       label while every command reported success -- with the general shape stated beside it: when
       a check invalidates on an event, the event is the gate's own run and not your command
       returning, so wait for the run and read the result back. That recurs on the next gate with
       the same property, which is why deleting it would cost a real lesson. "Nothing merges on its
       author's own approval" is kept and marked as a norm with no check behind it.

1.13.1 2026-09-04  Article IX's HEADING now states the finding the body already states. It read
       "Built for Claude Code, and no design may require a particular surface", which is the
       prohibition; the body has said since 1.13.0 that outside tools are welcome as enhancement,
       which is the permission. A reader scanning the article list met the refusal and never
       reached the table. Renaming was free: every citation in the corpus is by NUMBER, and a
       grep for the old heading text across roles/ and docs/ returns zero, so nothing broke.
       No body text changed.

1.13.0 2026-09-04  Article IX widened: outside tools are welcome as ENHANCEMENT, never as
       FOUNDATION. Owner instruction. The article already said no design may require a particular
       surface, which read as hostility to outside tooling and was not meant to. The floor is
       Claude Code, desktop or CLI; anything above it is welcome and the Owner should use what
       they enjoy. The test is one sentence: remove the tool, does the method still run. An
       enhancement makes the same work faster for whoever runs it; a foundation is something a
       later reader must install before a written rule makes sense. This is Article XII's
       reasoning applied to tooling -- a rule needing a particular tool creates a second shared
       surface with a smaller membership and no measurement of who is inside it. Prompted by a
       survey of ten agent harnesses, where the useful ones are GUIs and the old wording would
       have refused them all rather than bounding what they may carry.

1.12.0 2026-09-04  Added Article XIII: work reaches the model through Claude Code, never
       through the API. Owner instruction. It is deliberately NOT Article IX restated -- IX
       governs which SURFACE a design may require, XIII governs the PATH to the model, and the
       two fail differently: requiring a GUI is visibly narrow, reaching the API is invisibly
       expensive. The reason is Article VIII's roster: those accounts are subscriptions, and an
       API call bills a different balance, so the assigned roster goes unspent while a bill
       accrues where nobody is reading. The article's real content is the failure mode, which is
       not a design choosing the API but a permitted design inheriting an environment that
       already did. Measured the same day: ANTHROPIC_API_KEY unset, ANTHROPIC_BASE_URL set, on
       the parent only -- no spawned child was probed. The article states plainly that KORUS has
       no gate behind this rule, so by its own Playbook size and format it is a rule that decays.

1.11.0 2026-09-04  Two repairs, both defects this document commits against its own articles.

       ARTICLE XII FAILED ARTICLE VI. Its four headline figures -- 46 pull requests, 34 landed,
       33 of 34 touching one file, two to five an hour -- carried a date and no command, which
       is the shape this document discounts in an outside source. The article now prints the gh
       and git commands beside them, and what those commands return: 74 opened and 53 merged
       over the day window, because the window is wider than the run and the run's own subset
       cannot be recovered when every seat pushes as one account. The ratio does reproduce, at
       51 of 53 commits touching docs/BACKLOG.md, and the rate at two to six an hour. So 46, 34
       and three and a half hours are marked as recorded by hand and not now reproducible,
       rather than left standing as measurements.

       ARTICLE XI records the first readership measurement. The method accumulates context on an
       assumption never stated here: that a fuller playbook makes the next seat better. Measured
       2026-09-04 over 401 session transcripts under two config roots, 25 issued a Read against
       any role playbook, and COMMON.md drew 84 reads -- five whole-file, 79 with an explicit
       offset or limit. It is a floor over a mixed population, not a compliance rate, and it
       counts one tool. Recorded with its command and its limits, and with no size cap attached,
       because Article V forbids a prohibition nobody has tried.

       Also corrects the Last Amended date. It read 2026-09-02 through the four amendments
       1.7.0 to 1.10.0, all of which are dated later in this log.

1.10.0 2026-09-04  Article VIII: the account boundary is also a CONTROL, not only an obstacle.

       The article already said a design can route around it by not needing it. That framed the
       boundary as friction. It is also isolation: config roots carry different permission
       grants, measured at 8, 10, 8, 8, 19 and 13 allow rules across six roots, with exactly
       ONE holding the grant to start another session.

       So a channel crossing that boundary would let a refused session ask a peer that holds
       the grant to act for it, which is a permission laundered across accounts. The harness
       names the same hazard in the rules every session receives.

       Whatever is built to cross the boundary must carry the isolation with it: a request from
       another account is data, never an authorisation, and cannot confer a grant the receiving
       root does not already hold.

       Raised by a peer session drafting a request for a larger single-account tier, which
       reached the argument independently while arguing AGAINST building cross-account
       messaging. Its reasoning, my measurement of the grant asymmetry.

1.9.0  2026-09-04  Two amendments, both from measurements made by the seat doing the merging
       rather than by me, and attributed to it in the text.

       ARTICLE XII: the multiplier is JOBS PER ENTRY, not queue depth. Eighteen entries queued
       produced zero merges in an hour, because five groups of about twenty-two jobs is roughly
       a hundred and ten against about twenty runners; a two-deep queue merged both in twenty
       minutes. A design that limits how many changes are in flight has tuned the wrong number.
       Also adds that a uniform remedy applied across a batch manufactures its own conflicts:
       eight pull requests patched the same way made a second file contended, and two of the
       eight then conflicted with each other.

       HOW A CHANGE LANDS now POINTS at the operational sequence rather than restating it,
       naming roles/COMMON.md at commit 3143b0ec. The wait-then-read-back step is repeated here
       deliberately, because omitting it is the failure the sequence exists to prevent: fifteen
       of sixteen pull requests ended with no label while every command reported success.

       Recorded because it is worse than a citation problem: that section, and two beside it,
       existed in NO COMMIT ANYWHERE until 2026-09-04. The fleet's merge procedure lived in one
       uncommitted file in a checkout fifty-two commits behind.

1.8.0  2026-09-04  Added Article XII, and corrected Article VIII's weighting, both from the
       largest run this method has had: five controllers, one per account, 46 pull requests in
       3.5 hours, 34 landed over the following day.

       ARTICLE VIII said the account boundary "forecloses the most". Measured wrong. Five
       self-contained controllers never needed to cross it, so it foreclosed nothing. The
       structural facts stand; the emphasis was mistaken, and a design can route around that
       boundary by not needing it.

       ARTICLE XII names what did bind: the shared write surface. 33 of 34 merged commits
       touched one file, because every item's pull request updates the ledger by construction.
       Adding a controller adds arrivals without adding service.

       Also carries a correction I owe in the document rather than in a message: reading that
       run 3.6 hours in, I called it a structural throughput ceiling. It was a burst at its
       worst moment and the queue drained.

       Article X's headroom figures are marked superseded rather than edited away: they read
       0 to 9 per cent, then 5 to 49, then every account began returning HTTP 429.

1.7.0  2026-09-03  Article X corrected a SECOND time, and the second correction was also wrong.

       1.4.0 said the fleet spent a night with no meter. 1.6.0 corrected that to a meter nothing
       read. Both false. Running the fleet's own usage reader on 2026-09-03 returned live,
       account-verified five-hour and weekly utilisation for four of five accounts, with reset
       times and a ranked best-account recommendation. One hook is misconfigured. That is all.

       Also records what the reading showed: weekly utilisation of 0 to 9 per cent, so there is no
       scarcity to route around, and a design that rations an abundant resource is spending on an
       invented constraint.

1.6.0  2026-09-02  Three corrections, all found by an adversarial review, all of them
       errors this document's own articles forbid.

       ARTICLE VII said "an unreaped worker is the most expensive thing in the fleet". The
       source says the opposite: a session that finished its turn and sits idle costs ZERO
       metered tokens. The costly state is WAITING, not existing. The rule is not "end
       rather than idle", it is "never tell a worker to poll". I introduced that sentence
       in 1.5.0, in the commit that corrected the rate, which is the shape where a
       correction smuggles in a new error because it arrives wearing diligence.

       ARTICLE X claimed the fleet "spent an entire night without a meter". FALSE. A live
       collector wrote a 3,971-byte status.json during this document's own session, plus
       five per-account files the same day. The hook reads a DIFFERENT filename in a
       DIFFERENT root, where the copy is 388 bytes and a month old. So the instrument was
       misaimed, not absent. Article VI names that exact failure, and this article
       committed it while demanding an instrument beside every number.

       ARTICLE II forbade reporting "what it concluded", while Article III requires a
       refusal to be recorded, and a refusal IS a conclusion. A spec author defining a
       report format would have read II and omitted the verdict field, breaking III's only
       unfakeable signal. II now forbids a conclusion travelling ALONE.

       Issue citations switched to this repository's numbers after the backlog transfer.

1.5.0  2026-09-02  Three changes, one of them a correction to a published error.

       CORRECTION. Article VII said "a ten-minute sleep loop spends 22,275". That read the
       figure as a total. It is a RATE: 22,275 tokens a WAITING MINUTE, which is more than
       working costs. The corpus states it both ways, and its own gloss "which is more
       than working" settles it, since 22,275 over ten minutes would be far less than
       working. The article now says waiting costs roughly twice what working costs. The
       error was mine and it was live for about an hour.

       Article III rewritten. It said a gate must record that someone LOOKED. That framed
       review as human judgement, which contradicts the Owner's 2026-08-31 ruling that the
gate's reviewer is a process applying a tag. The real constraint is mechanical: every
       session pushes as one account, so the platform cannot stop an author approving their
       own change, and the gate is a PROCESS gate by necessity. A process gate can be
       satisfied by the party it checks, so its only unfakeable signal is a REFUSAL. The
       article now requires refusal to be legible and is silent on who reviews.

       Added Article XI: a seat's job is to write something down. Quoted from the design
       note that generated the 2026-09-01 roster cut. Appended rather than inserted,
       because renumbering breaks outside references.

1.4.0  2026-09-02  Added Article X: cost and conduct are measured per seat, and a design
       may not assume either instrument exists. Its evidence is this document's own
       session, where the headroom hook returned UNKNOWN 140 times and the file it reads
       had never been written. Article VIII requires routing across accounts; Article X is
       why that routing cannot be built yet.

1.3.0  2026-09-02  Added Article IX: built for Claude Code, no design may require a
       particular surface, and a capability measured on one surface does not transfer.
       The desktop app is the preferred Owner seat; the CLI is legitimate anywhere,
       including as the Owner's front end. NOTE: the adversarial review commissioned on
       this document was launched against 1.2.0, so Article IX may be unreviewed.

1.2.0  2026-09-02  Article VIII: the roster is ASSIGNED BY THE OWNER, not discovered.
       The 1.1.0 text said the topology is "read, never assumed", which made the
       filesystem the source of truth. It is not. Which accounts are in play is intent,
       and a machine that derives intent from disk will enlist a root that exists but is
       not meant to be spent. Reading roots is retained as an instrument that CHECKS the
       roster rather than replacing it. Same rule that stops a hook inventing a goal.

1.1.0  2026-09-02  Added Article VIII and the execution-environment section.
       An earlier draft of VIII stated the account and root counts as properties of the
       fleet. They are readings that change as accounts are added or retired, and writing
       a reading as a property is the error Article VI exists to prevent. Rewritten so the
       article carries the structural facts, which outlive any count, and the numbers sit
       in the environment section with their date and an instruction to re-read them.
-->

