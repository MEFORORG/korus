# The KORUS framework: Lessons learned the hard way

KORUS is the method I developed while using Claude Code on MessageFoundry.org, a major project I
started in late May, 2026. I'm a senior developer, and this account records what I learned through that work.

The name means Keep One Repo, Unblock Sessions. I use separate coding sessions with clear jobs,
shared records, and checks that stop them disrupting each other's work.

You can [download this Markdown](https://claude-multisession.pages.dev/KORUS.md) or read the
[Word version](https://claude-multisession.pages.dev/word/KORUS.docx).
The [previous Word version](https://claude-multisession.pages.dev/word/KORUS.old.docx) is also available.

<a id="bluftldr"></a>

## Start with the setup that fits your project

[Quickstart](QUICKSTART.md) installs the controls.
[Run a KORUS build](KORUS-BUILD.md) explains the session roles and how to use them each day.

This account's model and pricing advice was last reviewed on 2026-08-16. The recommendations came
from tools used as of 8/12/2026; they are historical observations, not a fresh review of available plans.

Check current Anthropic documentation before choosing models, buying accounts, or relying on
client behavior. Later sections also retain dated changes to the roles.

## KORUS for Multi-session AI-Coding

My setup combined these choices:

- Claude Code with Ultracode mode.
- Claude Code for Desktop for work across sessions, with VS Code available for reading and editing code.
- One or more Claude Max 20x accounts, chosen for their compute cost rather than enterprise management features.
- A manager running one or more builders, as subagents or separate sessions, with a lander handling the merge queue.
- Worktrees and hooks to enforce the rules that prompts alone did not hold.
- The Kynet method for communication between sessions, described in section 8.

The regulator role adds a check around the builders' work. One further role, deliberately unnamed here, did too until it retired on 2026-09-12.
on 2026-09-12. The sections below explain the choices and their limits.

## 1. Use Claude Code with Ultracode Mode and Opus 5

I found [Ultracode mode](https://code.claude.com/docs/en/workflows#let-claude-decide-with-ultracode)
useful because it lets Claude launch workflows. A workflow breaks a task into assignments for subagents.

It also triggers [adversarial validation](https://code.claude.com/docs/en/best-practices#add-an-adversarial-review-step),
which helped catch mistakes in my work.

At the time of this account, I preferred Opus 5 for code. In my experience it produced slightly
better code than Fable 5 at half the price.

Ultracode with Opus 5 was slow, but I spent less time fixing bugs afterward. Running several
sessions gave me other work to review during those waits.

With eight workflows active, there was usually a decision waiting for me. That describes my
workload, not a measured speed advantage over one session.

## 2. Use Claude Code for Desktop

In 8/2026, I found the desktop app better at communication between sessions than the VS Code
extension. Multiple sessions in the extension had caused code collisions.

VS Code made it easier to inspect the code itself. I kept it open alongside the desktop app:
Claude generated changes in the desktop app, and I reviewed or edited them in VS Code.

If you use several Claude accounts, [Desktop accounts](DESKTOP-ACCOUNTS.md) explains how to set up
one desktop instance per account and the config root each instance adds.

## 3. Subscribe to Claude Max 20x, Multiple Accounts: 60x Cheaper

The original account valued a Max 20x plan's compute at about $12,000 at undiscounted API rates,
compared with a $200 monthly subscription. That is the basis for the reported 60x comparison.

[Token accounting](TOKEN-ACCOUNTING.md) explains the calculation and its limits. The comparison
used the undiscounted API rates associated with Teams or Enterprise pricing in that account.

Individual accounts lack enterprise management features. In my workload, their lower compute cost
could save thousands, and more than one account could cover a week of heavy development.

I believed separate accounts with separate email addresses were allowed, with no stated account
count limit. That was my reading, not legal advice or a cited permission; I am not a lawyer.

Check [Anthropic's Usage Policy](https://www.anthropic.com/legal/aup),
[Consumer Terms](https://www.anthropic.com/legal/consumer-terms), and
[Claude Code plan guidance](https://support.anthropic.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan)
before relying on it.

The original guidance prohibited sharing one account between people.

Max 20x applied both five-hour session caps and weekly caps. In my observations, 1% of weekly
usage was roughly 5% of session usage.

About eight build tasks at a time usually stayed under my session limit. That workload used the
weekly allowance in about two days.

Separate sessions require some communication, but an idle session consumes no further compute
after its turn ends. Tasks that launch many agents, especially `/deep-research`, require fewer concurrent tasks.

## 4. Backlog

Ask Claude Code to create a project backlog and add new work as it comes up. Have the manager use
that backlog when it plans the next build tasks.

## 5. Documentation

### 5.1 ADRs: Architecture decision records

Create architecture decision records (ADRs) for significant build decisions. Include that
requirement when you ask the manager to make a plan.

The records give the AI ongoing context. They also give your security lead and auditors a history
of the decisions behind the build.

### 5.2 GitHub Spec Kit

[GitHub Spec Kit](FRAMEWORK-spec-kit.md) helps structure spec-driven development: agree on what to
build, then use that specification to guide implementation.

I use it to reduce the gaps left by open-ended coding prompts.

### 5.3 ASVS register

The Open Worldwide Application Security Project's Application Security Verification Standard
(ASVS) 5 defines security requirements at three levels. Choose the level that fits what your application handles.

Ask Claude to keep a register of ASVS scores against the exact ASVS 5 wording. Summaries from
Claude or another source can change what a requirement asks for.

Use `sym/ctx` anchors to connect scores to code. They identify a symbol and its surrounding
structure, which is more stable than a line number.

A line number shifts when someone adds whitespace, comments, or unrelated code above it. A
symbol-and-context reference changes when the code structure it identifies changes.

## 6. Each Session Does One Job

In the setup described here, each session used Ultracode and Opus 5.
[Run a KORUS build](KORUS-BUILD.md) supplies the opening prompts, daily procedure, and recovery steps.

### 6.1 Manager session

The console seat was meant to oversee many parts of the build. It did not work. The manager replaced it, and the console retired on 2026-09-10.

The manager is the session you talk to. It reads the project record and runs one or more builders as subagents or separate sessions.

Each builder gets a brief and its own worktree. The manager reads the results and resolves missing requirements before assigning more work.

Subagents use the manager's account and return results directly. Separate sessions need an explicit route for questions and results.

Several managers may share the repository, so their assigned paths must not conflict.

### 6.2 Builder sessions

A builder takes one brief through the change, commit, push, and pull request. It then reports to its manager. It does not guess at missing requirements or wait for an answer.

At the time of this account, [Agentic Teams](https://code.claude.com/docs/en/agent-teams) was in beta.
The builders used [dynamic workflows](https://code.claude.com/docs/en/workflows).
See also [Run agents in parallel](https://code.claude.com/docs/en/agents).

### 6.3 Lander session

The lander chooses which changes enter the merge queue and in what order. With authority from the
owner, it also merges newer trunk changes into branches that need them.

This matters when concurrent work keeps moving the repository's head, especially when large
codebases take longer to test.

The original account required a reviewer label before merging. That rule was retired on
2026-09-04; use the current [Lander card](roles/lander.card.md) and repository checks for today's requirement.

### 6.4 A retired session, 2026-09-12

This section once described an ASVS monitor, a role retired on 2026-09-01. It then described a
another role, retired on 2026-09-12 with nothing to replace it.

The retired procedure started one such session per pull request. It read the diff, recorded the head commit
it examined, and posted findings for the next builder. It never merged.

The label-based merge gate it fed was retired on 2026-09-04. Eight days later the seat went too, so
a pull request now merges on its repository checks alone. The [Reviewer card](roles/reviewer.card.md)
is a tombstone.

### 6.5 Regulator session

Start a regulator when a required check fails. It determines whether the cause belongs to the
pull request, trunk, an intermittent test failure, or the queue.

Only a failure caused by the pull request goes back to its builder. The regulator keeps a log
because it does not retain memory of earlier failed runs.

The steward is a scheduled script, not an AI session. It reads account usage and identifies an
account with room left. It makes no model calls and cannot interrupt a running session.

## 7. Worktrees

Give each session its own worktree so it can edit files without changing another session's
checkout. Read [Worktrees](WORKTREES.md) and
[Claude Code's worktree guide](https://code.claude.com/docs/en/worktrees).

## 8. Inter-session Communication & Coordination

Sessions can exchange messages, but the available channels differ between the desktop app and
the VS Code extension. [Coordination](COORDINATION.md) describes the checks around their shared work.

Conflicts still happen. A builder reports an unresolved problem to the manager, which decides
what to do next. See [Claude Code's cross-session messaging guide](https://code.claude.com/docs/en/cross-session-messaging).

## 9. Don't Hit Usage Limits: It Causes Lost Work

After Anthropic rejected requests to make Claude Code aware of usage limits, I worked with Claude
on [usage awareness](USAGE-AWARENESS.md). That page describes the design and what it does and does not ship.

## 10. CI: Continuous Integration for Quality Code

Continuous integration runs automated checks when code changes. With GitHub Actions and required
checks, you can block changes that fail your project's standards.

[CI for leaders](CI-FOR-LEADERS.md) explains how to choose checks and what their results establish.
