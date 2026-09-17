# Run a KORUS build

<a id="tldrbluf"></a>

Run a KORUS build with a manager and one or more builders. Builders may be subagents or separate sessions. This procedure follows
[The KORUS framework](KORUS.md), one operator's account of months using Claude Code.

Distinct jobs reduce the chance that two sessions decide the same thing. Complete [Quickstart](QUICKSTART.md)
first; this procedure assumes installed and proven gates.

The console seat was meant to oversee many parts of the build. That did not work, so the manager replaced it and the console retired on 2026-09-10.

The manager assigns work to its builders and reads their results. A builder can run as a subagent or in its own session.

Name that choice in each brief. Subagents return results to the manager; separate sessions need an explicit message route.

---

## The shape

Give each job a seat. No script, role flag, or routing implements these roles; you establish them in
opening prompts and `CLAUDE.md`.

<a id="g04"></a>

<figure class="explain-figure">
<picture>
<source media="(max-width: 1100px)" srcset="/assets/diagrams/g04-build-handoffs-mobile.svg">
<img src="/assets/diagrams/g04-build-handoffs.svg" alt="A Manager runs one or more Builders as subagents or separate sessions. Pull requests go to the authorized Lander; failed checks reach Regulator." loading="lazy" width="797" height="887">
</picture>
<figcaption>The Manager runs one or more Builders, with one brief per task. Each Builder can be a subagent or a separate session. The authorized Lander sets queue order; the queue merges. Failed checks take the separate Regulator path. <a href="/assets/diagrams/g04-build-handoffs.drawio">Editable diagram</a>.</figcaption>
</figure>

The Builder uses its own worktree and branch, with the collision gate checking covered edits.
Findings stay on the pull request for correction, and nobody waits for them.

A role name grants no merge permission. The operator must give the Lander authority through the
[documented route](RUNNING-MULTIPLE-SESSIONS.md); the retired review label enforces nothing.

| Session | Owns | Must not |
|---|---|---|
| **Manager** | Its builders, their briefs, and their results | Write application code |
| **Builder** | The change, the commit, the push, and the pull request for one brief | Guess at what the brief left open, or wait for an answer |
| **Regulator** | Deciding whose failure a red is: the pull request's, the trunk's, a flake's, or the queue's | Assume it remembers an earlier red |
| **Lander** | What enters the merge queue and in what order | Hold a pull request waiting for a review step that no longer exists |

The review seat retired on 2026-09-12 and nothing replaced it. The owner had already removed the
required `gate` check on 2026-09-04; it read the `reviewed` label, which blocks nothing.

Earlier instructions told that seat to apply the label and landers to wait for it. Following those
instructions now wastes a turn on an inactive check and an empty seat.

The ASVS monitor retired on 2026-09-01. It had been a fifth session updating the security register
as builders completed work.

This setup helps divide work larger than one context. An OWASP ASVS 5.0 assessment has several
hundred requirements; separate sessions need common rules to keep their verdicts consistent.

[Large assessments](https://secure-development-standards.pages.dev/ASVS-ASSESSMENT.html) is the method for that case.

## Before you open any session

| Do this | Why | Where |
|---|---|---|
| Install and prove the gates | Roles are advisory; the gates are not | [Quickstart](QUICKSTART.md) |
| Run one task end to end, by hand | You cannot size the queue until you know how long one task takes to land | [Coordination](COORDINATION.md#a-clean-merge-is-not-evidence-that-nobody-duplicated-your-work) |
| Give each session its own worktree | Two sessions in one tree overwrite each other | [Worktrees](WORKTREES.md) |
| Choose how each builder runs | Subagents use the manager's account and return results directly. Separate sessions need a message route | [Worker brief](WORKER-BRIEF.md) |
| Check the spawn grant when launching a separate session | The grant applies to the launching config root. Subagents do not need it | [Desktop accounts](DESKTOP-ACCOUNTS.md) |
| Wire the steering hook | It only takes effect in sessions started afterwards | [Steering](STEERING.md) |
| Write the working agreement | It only reaches sessions that start later | [CLAUDE.md.template](https://claude-multisession.pages.dev/CLAUDE.md.template) |
| Turn on Ultracode and pick Opus 5 in every session | The build shape assumes workflows and adversarial review | [The KORUS framework](KORUS.md) |
| Be on Max 20x, and expect to need more than one account | This shape spends a weekly window in about two days. Check current plan terms yourself; that page dates from 2026-08 | [The KORUS framework](KORUS.md) |

The manual-trial row reflects the Every team's experience, not a measurement here. They ran the flow
until predictable; automating sooner produced duplicate issues and PRs for finished work.

Repeat the manual trial until you can predict the flow. Set up extra accounts before starting, with
one desktop instance each ([Desktop accounts](DESKTOP-ACCOUNTS.md)); installers must reach every config root.

## 1. Open the manager

The manager holds its work plan and runs one or more builders. It can use subagents, separate sessions, or both.
Each builder gets a bounded task and its own worktree.

Paste this prompt:

```text
You are the manager for this build. You plan and track; you do not write application code.

Read the backlog. Produce a build plan that breaks it into tasks sized for one session each,
and write an ADR for any decision that outlives the task that made it.

Write one complete brief per task. State whether the builder is a subagent or a separate session.
For a subagent, receive its result directly. For a separate session, name a working message route.
Give each builder its own worktree and branch. Check for overlapping paths before dispatch.
When a builder reports a blocker, read it, update the backlog, and revise the brief.

Read each builder's result before assigning its next task. Confirm that finished work is pushed
before closing the manager. Coordinate pull requests with the lander.

Do not build. Do not merge.
```

The manager returns a plan and task breakdown. Have it save the backlog in a tracked file before
briefing workers, so the plan survives a lost context.

## 2. Give each builder one brief

The manager starts each builder in the mode named in its brief. Give each builder its own worktree and branch.

Subagents share the manager's process and account. They stop when the manager exits, so confirm that work is pushed before closing it.

Paste this prompt:

```text
You are a builder. Your brief names whether you run as a subagent or a separate session.
Build the task in your brief as a workflow, then report through the route it names.

If the brief leaves something open, do not guess and do not wait for an answer. Write the
question through the route in your brief, comment it on the pull request, and stop.

Before starting a task, take a claim on it with a one-line note saying what you are building:
  pwsh -NoProfile -File scripts/coord/claim.ps1 -Take "<task>" -Note "<what you are building>"

A free-text key like this is ADVISORY: peers can see it, and nothing enforces it. Only a
numbered key is enforced, by the commit-msg gate, and only when your commit subject names it.
A claim can also be refused because somebody holds it -- read the result.

Before editing a file you did not create, check who else is in it. Pass the path -- a bare
run prints the whole-repo roster and never names a file:
  pwsh -NoProfile -File scripts/coord/overlap.ps1 -File <path>

Read the exit code, not just the rows. 0 means the question was answered, including an
answer of nobody. 2 means it could not be, and silence there is not an all-clear.

Commit at logical stops. Push your own branch and open your own pull request. Do not merge:
the lander decides what enters the merge queue.
```

Use [Brief a worker session](WORKER-BRIEF.md) to fill out each prompt. Its rule requires a worker to ask when the brief
leaves a needed answer open.

Each builder claims its work and checks for file overlap before editing. The collision
gate normally refuses a second session's edit to a held file ([Coordination](COORDINATION.md)).

The refusal requires a live peer worktree with uncommitted changes to that exact path. A peer that
committed and went clean is reported but does not block the edit.

The gate also fails open. Check its [blind spots](LIMITS.md#what-the-collision-gate-does-not-see) before relying on it.

A worker that stops after one brief spends nothing waiting. A session kept open to poll pays for its
full context on every pass.

This setup exhausts a weekly window in about two days, before the five-hour cap becomes the main
constraint ([The KORUS framework](KORUS.md)). That is why the framework expects multiple accounts.

[Token accounting](TOKEN-ACCOUNTING.md) measures the value of one percent of a weekly window. It also estimates a month's
cost at published API rates.

## 3. Open the lander

The lander owns merge-order decisions so one session controls how the trunk advances.

Paste this prompt:

```text
You are the lander. You decide what enters the merge queue and in what order, and you
merge-forward. Builders push their own branches and open their own pull requests.

No review step sits in front of you. That seat retired on 2026-09-12 and the
required check that read a reviewed label was removed on 2026-09-04, so the label blocks
nothing. Merge on the required checks and do not wait for a review. Keep one
ledger-appending pull request in the queue at a time.

Read state rather than being told it:
  pwsh -NoProfile -File scripts/coord/presence.ps1   # who is live
  pwsh -NoProfile -File scripts/coord/overlap.ps1    # what is in flight

Decide which of two branches on the same ground lands first, and who re-syncs after.
You arbitrate and land. You do not build.
```

The lander reads branch state instead of waiting for messages about it.

Builders push their branches. The lander reads open pull requests and takes the ones whose checks
are green.

Read any comments already on the pull request. The required checks, `gates (ubuntu-latest)` and
`gates (windows-latest)`, cannot establish that anyone read the diff, and since 2026-09-12 no seat
is assigned to.

[Running multiple sessions](RUNNING-MULTIPLE-SESSIONS.md) defines the lander's authority and route. Authority cannot transfer; a worker
unable to reach the lander remains blocked from merging.

## The daily loop

1. Ask the manager what is in flight. It answers from the backlog, not from memory.
2. Check the builders have not collided. A bare `overlap.ps1` gives the roster; `-File <path>`
   answers who is in one file.
3. Steer rather than wait. A session deep in the wrong approach does not see your typing until its
   turn ends ([Steering](STEERING.md)).
4. Let the lander land. It decides the order. You approve the merge in words, once, and that
   approval does not carry to the next branch.
5. **Prune what merged**, from the primary checkout. `prune-merged.ps1` refuses to run from a linked
   worktree, and every session here is in one. It removes worktrees that are merged **and** clean
   **and** unoccupied ([Pruning](PRUNING.md)).
6. Re-prove the gates when something surprises you. They fail byte-identically to succeeding, so a
   quiet week is not evidence: `pwsh -NoProfile -File <tooling>/bin/ccx-doctor.ps1 -Repo <target>` ([Troubleshooting](TROUBLESHOOTING.md)).

## When it goes wrong

| Symptom | What it actually is | Go to |
|---|---|---|
| Two branches built the same feature | Effort overlap. No gate can compute it | [Coordination](COORDINATION.md) |
| Two records took the same number | The collision git cannot see | [Sequence allocation](SEQUENCE-ALLOC.md) |
| A session is deep in the wrong approach | Your typing queues until the turn ends | [Steering](STEERING.md) |
| Branches will not land | Four states with three different fixes | [PRs and merges](PR-AND-MERGE.md) |
| A peer cannot be reached at all | Extension session, or another login | [Session mail](SESSION-MAIL.md), including its delivery limits |
| Everything is green and you cannot tell if any of it runs | Every failure here looks like success | [Limits and requirements](LIMITS.md) |

## What this shape does not decide for you

The earlier version described mail as an unshipped design. The sender and drain now ship;
[Session mail](SESSION-MAIL.md) explains which clients have been tested.

Gates refuse collisions but do not review quality. Continuous integration establishes whether checks
passed ([CI for leaders](CI-FOR-LEADERS.md)).

Usage-limit awareness remains a design, with no shipped hook ([Usage awareness](USAGE-AWARENESS.md)).

Assign one writer for project memory and shared notes. Those stores use last-write-wins outside git,
with no gate to enforce ownership.

## Related

| For | Read |
|---|---|
| The template for one worker's prompt, and the rule that stops it guessing | [Brief a worker session](WORKER-BRIEF.md) |
| The account of why this shape, in its author's words | [The KORUS framework](KORUS.md) |
| Which surface to run the sessions on, and the channels between them | [Running multiple sessions](RUNNING-MULTIPLE-SESSIONS.md) |
| The model every page here applies | [Concepts](CONCEPTS.md) |
| The things that bite, in the order they bite | [Tips and tricks](TIPS-AND-TRICKS.md) |
