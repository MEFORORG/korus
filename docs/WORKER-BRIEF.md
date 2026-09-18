# Brief a worker session

A worker brief tells a new session what to do and when to ask for help. The coordinating session
writes it as the worker's opening prompt.

[Run a KORUS build](KORUS-BUILD.md) describes the manager, its builders, and each role's prompt. Use the template below to
write one worker's brief.

---

## What a worker does today when its brief runs out

A worker with an incomplete brief may guess or wait.

A guess can reach a pull request without any sign that the worker lacked an answer. A reviewer may
then treat it as a decision.

Waiting avoids that guess, but a waiting worker still spends metered tokens.

Workers already had a channel for questions. They needed a rule telling them to use it.

---

## The rule a brief must carry

```text
If the brief does not answer something you must know to proceed:
do not guess and do not wait. Send the question through the route named in this brief,
and stop. The coordinating session carries it onto the pull request.
```

The manager writes the brief and chooses how the builder runs. It reads the result and resolves questions before assigning more work.

| Builder mode | Route for questions and results |
|---|---|
| Subagent | Return them to the manager through the subagent result |
| Separate session | Use the explicit route in the brief, such as session mail or another tested session channel |

A separate session cannot return a subagent result. Name a reachable recipient and check the channel before assigning work.

Paste the template with its closing rule block unchanged.

### Why a prohibition rather than "ask if you are unsure"

On the fleet behind this rule, prohibitions failed between 0.07 and 0.6 percent of the time.
Obligations decayed between 22 and 97 percent.

"Ask if you are unsure" requires a worker to notice uncertainty. Under load, it may miss that cue.

A prohibition points to an act the worker can check: whether it is about to guess.

Set up both channels before pasting the rule. Otherwise the prohibition can remove the worker's only
way to ask ([Drift audit](CASE-STUDY-drift-audit.md#4-evaluate-prohibitions-as-a-set-never-one-at-a-time)).

---

## Stopping is free, waiting is not

A worker that ends its turn costs nothing at all.

| What the worker does | Metered cost |
|---|---|
| Ends its turn and stops | zero tokens |
| Waits on a three-minute heartbeat | 2,108 tokens per waiting minute |
| Waits in a ten-minute sleep loop | 22,275 tokens per waiting minute |

The rule requires the worker to stop. [Token accounting](TOKEN-ACCOUNTING.md) relates those costs to a weekly window.

## The answer arrives as a new spawn

The coordinator puts the answer in a new brief and spawns a fresh worker. It does not wake the
stopped session to reply.

The new worker continues on the existing branch and worktree ([Worktrees](WORKTREES.md)). Both survive the
session that created them.

Stopping loses the session's context, but preserves its work.

## The question goes to two places on purpose

| Where | What only it does |
|---|---|
| Mail to the coordinating session | Crosses the account boundary. Nothing else here reaches a session under a second login |
| A comment on the pull request | Sits beside the work, outlives the session, and a later reader finds it |

Delivery consumes the mail; the pull request comment remains for later readers. Both channels are
still needed, and since 2026-09-18 one worker cannot reach both.

### The worker writes to one place; the manager writes to the other

Pull request creation moved to the manager on 2026-09-18. A builder exits before its pull request
exists, so it cannot comment on one.

Earlier contracts assigned creation to the lander, then to the builder. Both are retired
([Run a KORUS build](KORUS-BUILD.md)).

So the worker sends the question through its route and stops. The manager carries it into the pull
request body, which is what keeps the question beside the work.

Name the mail target in the brief. A pull request number only belongs there when the worker is
adding to a pull request that already exists.

## Sending the question

Mail was unshipped when this brief was written. The current [Session mail](SESSION-MAIL.md) guide names the shipped
sender and drain and explains their setup.

Send a question with:

```powershell
mail.ps1 -Send -To <coordinator worktree> -Body "<the question>"
```

The recipient gets the question at its next drain, when `Stop` consumes it at a turn
boundary. Sending alone does not deliver it ([Session mail](SESSION-MAIL.md#step-5-split-show-from-consume-across-two-hook-events)).

On 2026-08-31, two sessions on different Claude accounts sent five messages each way. All arrived;
one box recorded 396 consumed messages.

Until mail works, a subagent returns its question in its result and a separate session has no route
at all. Test the route before you brief.

---

## What a brief must carry

Include all five slots. A missing slot may force the worker to ask and stop.

| Slot | What goes in it |
|---|---|
| Scope | The branch, the worktree, the backlog number, and the one thing this worker owns |
| The items | The work, in order, sized for a single session |
| Done | An end state somebody else can check |
| Out of scope | What it must not touch, named rather than implied |
| Review | The code-review effort level. Name it; a bare call inherits whatever the harness was set to |
| The rule | The block above, plus the address to ask at |

### A brief only has to hold for one turn

A brief needs enough detail for the worker to finish one turn without guessing.

When the brief no longer answers what the worker needs, it asks and stops. The next spawn carries
the answer, so an incomplete brief costs one spawn.

A guess can enter a pull request disguised as a decision. Write what you know in the brief, and use
the rule to catch unanswered questions.

## The template

```text
You are a build session on branch <BRANCH>, in worktree <WORKTREE>.

SCOPE. <the one thing you own>
OUT OF SCOPE. <what you must not touch>

ITEMS, in order:
  1. <item>
  2. <item>

DONE. <the end state somebody else can check>

Commit at logical stops, one coherent layer each. <YOUR PUSH RULE>
Your LAST commit message carries the proposed pull request title and the proposed ledger
banner text. Push your branch, report, and exit. You do not open the pull request.

RUN AS. <subagent OR separate session>.

ASK AT. <For a subagent: return questions in your result. For a separate session:
name the recipient and a tested message route, such as mail.ps1 -Send -To <worktree>.>

If the brief does not answer something you must know to proceed:
do not guess and do not wait. Send the question through the route named in this brief,
comment it on the pull request, and stop.
```

Keep the last block identical in every brief. Changing the prohibition creates a different rule that
the measurements above do not support.

---

## Related

| For | Read |
|---|---|
| The four-session shape, and the prompt for each role | [Run a KORUS build](KORUS-BUILD.md) |
| Building the mail lane this rule sends through | [Session mail](SESSION-MAIL.md) |
| Which channel reaches which peer, and when | [Running multiple sessions](RUNNING-MULTIPLE-SESSIONS.md) |
| The working agreement every session reads | [CLAUDE.md.template](https://claude-multisession.pages.dev/CLAUDE.md.template) |
| Judging a prohibition against the paths it closes | [Drift audit](CASE-STUDY-drift-audit.md) |

The [handoff diagram](KORUS-BUILD.md#g04) places the brief between the Manager and Builder.
