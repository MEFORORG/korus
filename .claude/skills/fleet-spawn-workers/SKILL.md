---
name: "fleet-spawn-workers"
description: "Spawn workers or create a Workflow. Use before any fan-out, including sizing it."
user-invocable: true
disable-model-invocation: false
---

# fleet-spawn-workers

> Shared fleet rules, split out of [COMMON.md](../../../roles/COMMON.md) on 2026-09-05.
> Prohibitions that bind before this task starts stay in that file. Read it first.

### The workflow gate cannot see aggregate load

**The 90 workflow gate beats "use a workflow by default".** Ultracode instructs a session to author
a Workflow for every substantive task. The 90 gate says no session may create a new Workflow above
90 percent without consulting the owner.

Both are owner-set, and above 90 they point in opposite directions. **The gate wins:** it names a
specific act, it is the later and narrower instruction, and it carries "ask the owner first", which
ultracode's default does not.

It is not a rung and not advice -- HOLD NEW WORK says start nothing; this says a new Workflow needs
the owner. Owner-lowered from 92 to 90 on 2026-08-05, because one measured Workflow moves the pool 5
to 7 points. The margin has to cover what is already committed and not yet visible in the meter.

**The gate cannot see aggregate load, so every launcher gets a correct yes and the sum is wrong.**
Measured across two consecutive windows on 2026-08-29, the same shape both times.

Four fan-outs launched within eight minutes of a reset: 12 agents, about 13, 9, about 15. **Every
one checked the gate and passed honestly at 4 to 6 percent.** Nobody was careless.

The gate answers "is the pool low enough for MY launch", and each answer is right because the other
three costs have not landed yet. **Three or four correct answers summing to a wrong outcome.**

The pool went 2 to 43 percent in twenty minutes and the window was projected to die about four hours
before its reset.

**It is self-synchronising, which is why it is not bad luck twice.** A reset is the one instant when
every seat is simultaneously unblocked, holding queued work, and reading the lowest number it will
see all window.

So the gate is at its most permissive exactly when demand peaks, and a resume broadcast is itself
the synchronising signal. **If you are launching just after a reset, assume others are too and price
against the weekly, which does not reset with the 5-hour.**

**And the blind spot is not only other seats. It is your own later phases. Count your loop.** A
per-launch gate reads the launch instant; a multi-phase fan-out spends most of its cost later.

A seat passed a gate on a workflow whose expensive phase appeared in no number it checked, including
its own report. Its run was **about 42 agents, not the 15 it declared** -- a refuter phase it had
not counted; it killed the run at 4 agents spent.

**And the obvious count under-reports.** `grep -c 'agent('` returned **6 call sites for a run of 9
agents**. The gap was one call site inside a `.map()` over a four-element array. **Read every
`parallel()` and `.map()` and multiply by the array length.**

A phase's cost is fan width times depth and neither appears at the `agent()` call. Sum every phase.

**What predicts the next twenty minutes is agents remaining, not agents launched.** A census of
launches is a census of the past. Measured: a "~59 agents in flight" figure was the wrong instrument
-- three of six runs were at zero remaining and two had cheap tails.

Only the launching seat can see its own remaining count, so it has to be sent.

**Ask for it in the form that prices the risk:** *"remaining, and is your last phase one agent or a
fan-out?"*

5 remaining as one synthesis agent and 5 remaining as four simultaneous verifiers are the same
number and different futures.

**A remaining count is not a forecast:** a phase gated on a guard inside an earlier agent has a real
branch where it spends nothing more. **And it is remaining fan-out agents, which is not what a seat
will spend:** main-loop work appears in no remaining count anyone reports.

Measured -- a seat at zero remaining spent freely afterwards on three pull requests, a ledger row
and five banners. **Seats at zero still burn, and a `0` scanned out of that column also reads as a
dead seat: label the column REMAINING FAN-OUT AGENTS**, not liveness and not spend.

**The gate governs creation, so declare your own exposure rather than leaving peers to find it.**

A seat held a nine-agent Workflow started at pool 80, below the gate when created. It said so in the
same message that announced the gate:

> *"THAT APPLIES TO ME AND I AM DECLARING MY POSITION RATHER THAN LEAVING YOU TO FIND IT."*

A workflow created below the threshold keeps running. The gate binds the next one.

### A fan-out nobody sized was sized by whatever was on the bench

A Manager fans work out two ways. Separate sessions outlive its turn; in-process subagents share its
account and die with it. **What bounds the number differs between them, and the playbook owns that
bound.** These rows are the part that does not.

| Item | Rule |
| --- | --- |
| Write the number and the reason first | One line in your episode note: how many workers, and what about the work makes that the number. A count with no reason cannot be argued down later. |
| The outside ladder is a shape to copy, not a size to adopt | Anthropic's write-up of its multi-agent research system keeps the sizing rule in the orchestrator. It calls the lack of one a common failure mode, and records fifty subagents spawned for one simple query. |
| Its integers do not come with it | The ladder runs from one agent for simple fact-finding, through two to four for a direct comparison, to ten or more for complex research. |
| The condition that stops them transferring | **Those were measured on research tasks, and the same post says coding parallelises worse.** No number in that ladder has been measured on this fleet. |
| What bounds YOUR number is in your own playbook | For a Manager, [MANAGER.md](../../../roles/MANAGER.md), *Brief at full speed*: usage holds bound it, and the merge queue does not (owner ruling 2026-10-26). |
| **CORRECTED 2026-10-26** | The row above cited *"A Manager's fan-out is bounded by one window and by shared runners"*, a MANAGER.md heading that does not exist. |
| The retired bound | [CONSOLE.md](../../../roles/retired/CONSOLE.md) bounded a fan-out by accounts and by what the Lander could land. That is record, not a live bound. |

---
