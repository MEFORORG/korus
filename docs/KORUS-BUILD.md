# Run a KORUS build

<a id="tldrbluf"></a>

Run a KORUS build with a manager and one or more builders. Builders may be subagents or separate sessions. This procedure follows
[The KORUS framework](KORUS.md), one operator's account of months using Claude Code.

Distinct jobs reduce the chance that two sessions decide the same thing. Complete [Quickstart](QUICKSTART.md)
first; this procedure assumes installed and proven gates.

The console seat was meant to oversee many parts of the build. That did not work, so the manager replaced it and the console retired on 2026-09-10.

The manager assigns work to its builders, reads their results, and opens the pull request for each. A builder can run as a subagent or in its own session.

Name that choice in each brief. Subagents return results to the manager; separate sessions need an explicit message route.

Fourteen steps run from the owner's assignment to a closed item. [The build-to-land flow](#the-build-to-land-flow) lists them.

---

## The shape

Give each job a seat. No script, role flag, or routing implements these roles; you establish them in
opening prompts and `CLAUDE.md`.

<a id="g04"></a>

<figure class="explain-figure">
<picture>
<source media="(max-width: 1100px)" srcset="/assets/diagrams/g04-build-handoffs-mobile.svg">
<img src="/assets/diagrams/g04-build-handoffs.svg" alt="A Manager runs one or more Builders as subagents or separate sessions. Pull requests go to the authorized Lander, then the merge queue. A Watchdog reads the drain without acting on it. No seat attributes a failed check: the Lander triages and routes it, and everything else is the Owner's to rule on." loading="lazy" width="797" height="887">
</picture>
<figcaption>The Manager runs one or more Builders, with one brief per task. Each Builder can be a subagent or a separate session. The authorized Lander sets queue order; the queue merges. The Watchdog reads the drain and never drains. A failed check goes to no seat: the Lander triages and routes it, and the rest is the Owner's. <a href="/assets/diagrams/g04-build-handoffs.drawio">Editable diagram</a>.</figcaption>
</figure>

The Builder uses its own worktree and branch, with the collision gate checking covered edits.
Findings stay on the pull request for correction, and nobody waits for them.

The Builder reviews its own diff before it pushes, at the effort level its brief names. Two rounds,
then it ships whatever the second round says.

A role name grants no merge permission. The operator must give the Lander authority through the
[documented route](RUNNING-MULTIPLE-SESSIONS.md); the retired review label enforces nothing.

| Session | Owns | Must not |
|---|---|---|
| **Manager** | Its builders, their briefs, their results, and the pull request it opens for each | Write application code, or check the pool before opening |
| **Builder** | The change, the review, the commit, and the push for one brief | Guess at what the brief left open, wait for an answer, or open the pull request |
| **Lander** | A handed-over pull request, from the handover to the merge, the ledger and the claim | Hold a pull request waiting for a review step that no longer exists |

The review seat retired on 2026-09-12 and nothing replaced it. The owner had already removed the
required `gate` check on 2026-09-04; it read the `reviewed` label, which blocks nothing.

Earlier instructions told that seat to apply the label and landers to wait for it. Following those
instructions now wastes a turn on an inactive check and an empty seat.

The ASVS monitor retired on 2026-09-01. It had been a fifth session updating the security register
as builders completed work.

This setup helps divide work larger than one context. An OWASP ASVS 5.0 assessment has several
hundred requirements; separate sessions need common rules to keep their verdicts consistent.

[Large assessments](https://secure-development-standards.pages.dev/ASVS-ASSESSMENT.html) is the method for that case.

## The build-to-land flow

Fourteen steps run from the owner's assignment to a closed item. Owner-set 2026-09-18. Steps 8
and 9 gained the QA line on 2026-09-20; the fourteen and their order did not change.

| # | Seat | Step |
|---|---|---|
| 1 | Manager | Receives the assignment. |
| 2 | Manager | Briefs one or more builders. Each brief names the backlog number, the worktree, and the code-review effort level. |
| 3 | Builder | Takes the claim before its first commit: `claim.ps1 -Take <N>`. |
| 4 | Builder | Codes what the brief names. |
| 5 | Builder | Runs the `/code-review` skill at xhigh effort, and keeps its first line for the report. |
| 6 | Builder | Applies confirmed fixes and reviews again. Two rounds maximum. |
| 7 | Builder | Commits, pushes its branch, exits. |
| 8 | Builder | Reports to the manager, and writes the QA line for the manager to post. |
| 9 | Manager | Checks the branch is on the remote, opens the pull request, applies the `qa` label and posts the QA line. |
| 10 | Manager | Messages or mails the lander. |
| 11 | Lander | Owns the pull request. Triages a red check and dispatches any repair. |
| 12 | Lander | Enqueues as it judges best. |
| 13 | GitHub | Merges. |
| 14 | Lander | Updates the backlog and releases the claim, in one act. |

**Step 5 read "keeps its first line" until 2026-09-22.** That first line is often prose rather than
a tag, so it is the report that keeps it. `roles/BUILDER.md` 4e holds the reading and the commands.

### Why the steps that look redundant are not

**Step 3 says `-Take`, not `-Claim`.** The gate fires at commit time in the builder's own worktree.
Nobody can take the claim on the builder's behalf.

**Step 6 stops at two rounds.** Adversarial repair is not monotonic. A second round can introduce
what the first accepted, so an unbounded loop oscillates rather than converges.

If round two still reports findings, ship anyway. Attach the critic notes to the pull request body.

**Step 7 requires a self-describing final commit.** Its message carries the proposed pull request
title and the proposed ledger banner text.

That is mandatory, not a nicety. It is what makes the branch usable if the manager dies before step
9.

**Step 8 names what the builder did NOT run.** Each hosted-only leg, by name. A leg nobody names
reads downstream as green.

**Step 9 reads the remote, not the report.** `git ls-remote --heads origin` answers it. A push that
failed after the report was written looks identical to one that worked.

**Step 9 has no pool check.** Five managers independently reading a shared pool all see "clear" and
open together, which manufactures the burst it is meant to prevent.

**Step 11 rules out a capacity artifact first.** A rollup that completed while its own children were
still queued is not a finding.

For a genuine failure the lander dispatches a repair, preferring a spawned session over a subagent
when the fix is non-trivial. A subagent dies with the lander, and this is someone else's branch.

**Step 14 is one act, not two.** An orphaned claim blocks the next session on that row, and nothing
anywhere reports it.

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

Write one complete brief per task. Name the backlog number, the worktree, and the code-review
effort level. Tell the builder to end its report with the QA line you will post.
State whether the builder is a subagent or a separate session. For a subagent,
receive its result directly. For a separate session, name a working message route.
Give each builder its own worktree and branch. Check for overlapping paths before dispatch.
When a builder reports a blocker, read it, update the backlog, and revise the brief.

Read each builder's result. Check the branch reached the remote yourself:
  git ls-remote --heads origin
Then open the pull request. Do not count open pull requests first: every manager reading one
shared pool sees "clear" at the same moment, and they all open together.

Put the builder's report in the pull request body. It cannot post there itself. Read the
builder's last commit message for the proposed title and the proposed ledger banner text.

Label the pull request qa and post the builder's QA line on it, verbatim:
  gh pr edit <N> --add-label qa
  gh pr comment <N> --body "<the builder's QA line>"
The label records that the builder's check ran. It gates nothing: main requires only
gates (ubuntu-latest) and gates (windows-latest). No line means no label.

Message the lander with five fields: pull request number, head SHA, unread legs, known defects,
and any landing-order constraint. The pull request is the lander's from that message on.

Remove your builders' worktrees once their pull requests are open.

Do not build. Do not merge. Do not enqueue.
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
question through the route in your brief and stop. Your manager carries it onto the pull
request. You cannot: it opens after you exit.

Before your first commit, take a claim on the task with a one-line note saying what you build:
  pwsh -NoProfile -File scripts/coord/claim.ps1 -Take "<task>" -Note "<what you are building>"

The flag is -Take, not -Claim. The gate fires at commit time in your own worktree, so nobody
can take the claim for you.

A free-text key like this is ADVISORY: peers can see it, and nothing enforces it. Only a
numbered key is enforced, by the commit-msg gate, and only when your commit subject names it.
A claim can also be refused because somebody holds it -- read the result.

Before editing a file you did not create, check who else is in it. Pass the path -- a bare
run prints the whole-repo roster and never names a file:
  pwsh -NoProfile -File scripts/coord/overlap.ps1 -File <path>

Read the exit code, not just the rows. 0 means the question was answered, including an
answer of nobody. 2 means it could not be, and silence there is not an all-clear.

Before you commit for the last time, review your own diff:
  /code-review at the effort level your brief names, xhigh by default
Apply what you confirm, then review once more. Stop after two rounds. If round two still
reports findings, ship anyway and hand the notes to your manager.

Commit at logical stops. Your LAST commit message carries the proposed pull request title and
the proposed ledger banner text. That is mandatory: it is what makes the branch usable if your
manager dies before it opens the pull request.

Push your own branch, then report: branch name, head SHA, review level and outcome, the
skill's own first line verbatim for each round, what you ran, and what you did NOT run.
Name every hosted-only leg.

End the report with the QA line your manager posts for you, in this shape:
  QA -- korus roles/BUILDER.md step 11
  Level: xhigh, from the brief. Tag: none returned.
  Rounds: 2. Findings: 3 confirmed and fixed, 1 rejected (reason), 0 open.
`Level` is what you passed. `Tag` is the `<level> effort -> ...` line if the skill
returned one, otherwise `none returned`. The QA line never uses the word "review",
so the skill's own opener goes in the report above it. Then exit.

Do not open the pull request; your manager does. Do not merge; the lander does.
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
merge-forward. Builders push their own branches; their managers open the pull requests.

A manager hands you a pull request with five fields: number, head SHA, unread legs, known
defects, and any landing-order constraint. From that message it is yours. Poll anyway:
nothing pushes a pull request to you, and a handover that was never sent strands nothing.

Before you call a red check a failure, rule out a capacity artifact. A rollup that completed
while its own children were still queued reports on legs that never ran.

For a genuine failure, dispatch a repair. Prefer a spawned session over a subagent when the
fix is non-trivial: a subagent dies with you, and this is someone else's branch.

When it merges, update the backlog and release the builder's claim in the same act:
  pwsh -NoProfile -File scripts/coord/claim.ps1 -Release <N>
The claim is another worktree's, so the script refuses and probes the holder. Read that line
before you reach for -Force.

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

The lander reads branch state instead of waiting for messages about it. The manager's handover
adds the four things the queue cannot report, and it replaces nothing.

Builders push their branches and their managers open the pull requests. The lander reads open pull
requests and takes the ones whose checks are green.

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
