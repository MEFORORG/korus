# KORUS questions, answered plainly

KORUS adds checks for sessions that share a repository. You may only need Claude Code's own
worktrees if your sessions do separate work and a person reviews the results.

KORUS assumes Claude Code for Desktop. For a command to fix an installed setup, use
[Troubleshooting](TROUBLESHOOTING.md).

## Native worktrees may be enough

`claude --worktree <name>` creates a separate checkout under `.claude/worktrees/<name>/`, with its own
branch. The desktop app creates a worktree for each new session automatically.

Claude Code also checks whether an isolated session is reaching into the main checkout. The
following behavior was read from [Claude Code's worktree documentation](https://code.claude.com/docs/en/worktrees)
on 2026-08-16.

| Check | What it blocks | Applies to |
|---|---|---|
| File edits | `Edit`, `Write`, or `NotebookEdit` targeting the main checkout | Any isolated session |
| Command working directory | A command running in the main checkout | Bash, PowerShell, Monitor |
| Git redirects | `git -C`, `--git-dir`, `GIT_DIR`, `GIT_WORK_TREE`, or `cd` into the main checkout | Bash and Monitor |
| Command shape | A command it cannot verify stays inside the worktree; this check cannot be disabled | Bash and Monitor |

These checks apply only while a session is isolated. A session in the primary checkout gets none
of them.

PowerShell gets the working-directory check but neither of the last two command checks. As the
documentation puts it: "For PowerShell commands, Claude Code applies only the working-directory check."

That leaves a gap: `git -C <primary> checkout -B ...` can target the primary while the command still
runs from a worktree. KORUS checks selected Git commands for that target.

## KORUS adds checks between sessions

| Need | What KORUS adds |
|---|---|
| A checkout and branch per session | Nothing beyond native worktrees; use those |
| Block edit tools from writing into the primary | An allowlist-based gate that also applies to sessions running in the primary; it does not judge a command's working directory |
| Keep subagents isolated | Native `isolation: worktree` supplies isolation and the four checks; KORUS also denies `Task`, `Agent`, or `Workflow` dispatch from the primary |
| Block PowerShell commands that swap the primary tree | Checks for an enumerated set of Git verbs in `Bash` and `PowerShell` tool calls |
| Stop two isolated sessions editing the same file | A collision gate that names the live peer holding uncommitted changes; when it cannot check, it allows the edit and says so |
| Avoid duplicate record numbers | Atomic allocation, plus a commit-time gate that you must wire yourself; the doctor reports that gate `OFF` until wired |
| See who is working on what | `presence.ps1` and `overlap.ps1` |
| Check the installation | `bin/ccx-doctor.ps1` tests decision-making controls and names what it could not prove, including the collision gate's refusal |

Native worktrees isolate sessions from the main checkout. They do not check for shared file edits,
duplicate record numbers, or overlapping tasks between sessions.

KORUS cannot see every write either. An agent-written script may contain no visible Git verb, and
`gh pr checkout <n>` contains no `git` token. [Hooks](HOOKS.md) explains those gaps.

Choose based on both the work and the shell. Native worktrees and a human reviewer may be enough
when tasks share no files, numbers, or features.

On PowerShell, the worktree gate also helps when a session runs Git against the primary. A branch
switch can disrupt another session without creating a text conflict for a reviewer to find.

## The controls prevent accidents, not attacks

Every control runs under the same operating-system account as the agent. The agent can edit its
hooks, allowlist, and settings.

| Bypass | Effect |
|---|---|
| `--no-verify` | Skips hooks on a commit or push |
| `CCX_ALLOW_DIRECT_PUSH=1` | Returns before the push guard reads its config |
| An explicitly empty `protectedRefs` | Disables the push guard and reports that on stderr |
| No Python executable available | The two Git hook shims print that the gate is off and exit `0` |

The first three bypasses leave no local record. A one-command environment setting also leaves
nothing for a later check to find.

The Git hooks use `/bin/sh` wrappers to find Python and run their checks. Without Python, the claim
hook prints `THE CLAIM GATE IS OFF for this commit.`; the push hook prints an equivalent message.

The hook files still look installed. Use remote branch protection, required status checks, and
credentials that cannot bypass them. [Limits and requirements](LIMITS.md) has the details.

## Checks in one clone cannot see another developer's work

Claims and allocations sit beside the Git common directory. All worktrees in one clone share them;
a second clone has its own registry.

Two developers can therefore allocate the same number before either change merges. The collision
gate also cannot see a colleague's uncommitted work on another machine.

The push guard applies per clone. The worktree allowlist lives under the user config directory and
applies per machine. The doctor examines one clone and does not combine those scopes.

`scripts/hooks/seq_check.py --ci` checks three of its four rules against a freshly fetched trunk.
It can catch a cross-clone duplicate after the fact, but no installer wires it.

That check omits allocation ownership because the registry is local to each clone. Passing it does
not prove that anyone allocated the number.

Run `git fetch origin --prune` before allocating. The allocator scans remote-tracking refs, so it
can skip numbers another developer has already pushed.

For a team, use KORUS for local coordination and enforce shared rules on the remote.
[Sequence allocation](SEQUENCE-ALLOC.md) explains the setup.

## Windows and Claude Code for Desktop are the supported starting point

You need Claude Code for Desktop, PowerShell (`pwsh`) 7.3 or newer, Git, and `python` on `PATH`.
The repository you govern also needs `ccx.config.json` at its root.

Windows is the exercised path. On Linux, path comparisons are case-sensitive and the roster is
less reliable at marking its own session.

macOS is absent from the continuous integration (CI) test matrix. Its behavior is unmeasured.
[Limits and requirements](LIMITS.md) lists platform details.

A command-line-only or editor-extension setup is unsupported. The desktop dependency comes from
how sessions find and contact each other:

- Announce uses `ccd_session_mgmt`, a Model Context Protocol server provided only by the desktop client.
- `list_sessions` lists only sessions that the app spawned; it cannot message editor-extension sessions.
- The desktop app gives each new session a worktree automatically.
- Concurrent VS Code extension sessions have encountered [worktree hijacking](RUNNING-MULTIPLE-SESSIONS.md).

The worktree gate, collision gate, and Git hooks are ordinary scripts. Some parts run wherever
`pwsh` runs, but the project has not established what protection that setup provides without the desktop app.

## Some checks run in CI; the doctor does not

Run the doctor locally in a plain terminal. It deliberately triggers each control; skipping those
paths in CI would produce a passing result without testing them.

The leak gate runs in CI. `seq_check.py --ci` supports it too, but requires manual wiring.

Claude Code hooks need a session. Under `claude -p`, they run synchronously and can hold a pipeline
step until their timeout expires.

The Git hooks need only Python and a commit or push. They are absent from a fresh CI clone because
hooks are not installed there.

## Registry changes can hide live sessions

The session registry tells the tools who is live. A format change can affect the checks in two
different ways.

| Change | Result |
|---|---|
| A field is renamed or its unit changes, but records still parse and map to worktrees | Counts stay the same; verdicts become `UNVERIFIED`, which still vetoes the action |
| The registry directory moves | Counts fall to zero; the collision gate sees an empty roster and silently allows edits |

The census can reveal missing records in the second case. The session itself cannot distinguish
that empty roster from a real absence of peers.

## More sessions can fill the merge queue faster

The manager runs one or more builders, either as subagents or as separate sessions. It replaced the console seat, retired on 2026-09-10, whose broad oversight did not work.

Builders take
tasks, a regulator investigates failed checks, and a lander merges. A further seat, deliberately unnamed, read pull requests
until it retired on 2026-09-12.

[Run a KORUS build](KORUS-BUILD.md) describes that setup. The roughly fourteen sessions sharing one
directory in the original report did not establish a useful session limit.

The largest reported run used five sessions, one per Claude account, each spawning workers. It ran
from 2026-09-03 to 09-04.

| Record from that run | Reported result |
|---|---|
| New pull requests | 46 in about three and a half hours |
| Pull requests merged over the following day | 34, at a sustained two to five per hour |
| Merged commits touching the shared item ledger | 33 of 34 |
| Queue with eighteen entries and about twenty runners | Zero merges in an hour |
| Queue reduced to two entries | Both merged in twenty minutes |

The operator counted the initial session, pull-request, and elapsed-time figures by hand. No
command was kept with those counts, so they are recorded observations that this repo cannot reproduce.

The merging session reported the queue results. The counts are recorded in the constitution's
Article XII and [MANAGER.md](https://claude-multisession.pages.dev/roles/MANAGER.md), not recalculated here.

Every item's pull request had to update one shared ledger. That limited merging even when more
sessions could produce new work. A sixth session would add arrivals without removing that constraint.

This was one repository, one serial merge queue, one shared ledger, and five accounts. The run did
not repeat the same work with a single session, so it provides no measured speedup.

The site serves `MANAGER.md` through its tracked-source publishing step. Read the constitution in
the repository; the site does not serve it.

### The earlier speed claim was withdrawn

The original FAQ and home page once said: "Several sessions at once is how a build gets dramatically faster."
That claim lacked a comparison with a single session and was withdrawn.

[CI for leaders](CI-FOR-LEADERS.md#what-you-must-never-claim) already prohibited that claim:
"You cannot claim a speed or productivity gain. None is measured in either repository."

To establish a speedup, run the same defined work once with a single session and once with several.
Keep the repository and merge queue the same, and report elapsed time and conditions for both runs.

## Try it or check the limits

| Next step | Guide |
|---|---|
| Install it and test a blocked edit | [Quickstart](QUICKSTART.md) |
| Check requirements and blind spots | [Limits and requirements](LIMITS.md) |
| Diagnose unexpected behavior | [Troubleshooting](TROUBLESHOOTING.md) |
| Read the author's account of the method | [The KORUS framework](KORUS.md) |
