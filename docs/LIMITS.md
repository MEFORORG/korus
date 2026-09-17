# Limits and requirements

## TLDR/BLUF

KORUS needs the desktop client and separately installed controls. These requirements and limits
moved off the landing page on 2026-08-16; they had appeared above its first command.

Start with [Quickstart](QUICKSTART.md) if you have not installed KORUS. A quiet session alone cannot
tell you whether its controls work.

Check the requirements and [switches for each control](#what-actually-switches-each-control-on). If
sessions share a checkout, check the collision gate limits too.

---

## Requirements

| Need | Without it |
|---|---|
| **Claude Code for Desktop** | KORUS is a desktop framework. A CLI-only or editor-extension setup is not supported, and the coordination layer is shaped around the desktop client. See below. |
| **PowerShell 7.3+** (`pwsh`) | Below 7.3, every installer but one refuses. Read the 7.0-7.2 row in the platform table before you assume that is safe. |
| **git**, recent enough for `rev-parse --path-format=absolute` | Path resolution returns nothing, so the user-scope hooks resolve nothing and stay quiet. Nothing checks or reports your git version. |
| **`python` on `PATH`** (or `CCX_PYTHON`) | The installed git gates are OFF and say so on stderr. Needed by the three git-hook checkers and the leak gate. |
| **The scripts vendored into the target repo** | The three coordination hooks resolve nothing, and the doctor cannot reach exit 0. See below. |
| **Your primary checkout listed in `~/.claude/hooks/ccx-gate.repos.txt`** | The worktree gate and the SessionStart backstop are OFF for that checkout. This file, not `ccx.config.json`, is their switch. |
| **`ccx.config.json` at the target repo root** | Announce stays inert there, and every knob falls back to its default. It is **not** the opt-in for the other three user-scope hooks. |
| **A plain terminal to install from** | All four installers throw when `$env:CLAUDECODE` is `1`. A session that can install these controls can remove them. |

PowerShell 7 runs on Linux and macOS; Windows receives the practical testing. Self-marking and path
case-folding degrade on other platforms.

There is no `ccx` command on `PATH`. Here, `ccx doctor` means
`pwsh -NoProfile -File <this-checkout>/bin/ccx-doctor.ps1`.

The code uses the [MIT license](https://claude-multisession.pages.dev/LICENSE).

The test suite also needs `pandoc`, pinned by version and digest in continuous integration (CI).
Without it, `tests/test_word_copy_tracks_the_markdown.py` fails instead of skipping.

### Why a vendored layout is a requirement

The three coordination hooks install as shims that find their scripts at runtime. They search the
session repository's primary checkout and worktree root, never the separate tooling checkout.

With separate checkouts, the shims find no scripts despite their entries in `settings.json`. The
session gets no banner, collision gate, or announce.

The doctor checks the same two locations and marks each missing script RED. It cannot exit 0 in this
layout.

The worktree gate, both git hooks, and the backstop work with either layout. Follow
[Quickstart](QUICKSTART.md) step 3 to vendor the scripts.

### What actually switches each control on

Each control has its own switch. Deleting `ccx.config.json` leaves three user-scope hooks running.

| Control | Switched on by | Does not read |
|---|---|---|
| Worktree gate (`PreToolUse`, denies) | An entry in the gate allowlist | `ccx.config.json` |
| SessionStart backstop (runs `git checkout`) | The same allowlist | `ccx.config.json`, beyond the `prefix` knob |
| Collision gate (`PreToolUse`, denies) | Its script resolving inside your repo | `ccx.config.json` |
| Session banner (`SessionStart`) | Its script resolving inside your repo | `ccx.config.json` |
| Announce | `ccx.config.json` present at the repo root | The allowlist |
| `commit-msg` and `pre-push` | Installation into that clone's `.git/hooks` | The allowlist |

Delete the allowlist to turn off both controls that act on shared checkouts. This documented kill
switch affects every listed checkout at once.

Announce checks only the repository root for its config; other consumers search upward from the
current directory. A config above the root satisfies git-hook checkers and the doctor, but leaves
announce off.

## Platform support

The CI matrix in `.github/workflows/gates.yml` names two operating systems.

| Platform | Status | What degrades |
|---|---|---|
| **Windows, PowerShell 7.3+** | The exercised path. In CI as `windows-latest` | Nothing known. This is the platform the defaults assume |
| **Linux, PowerShell 7.3+** | In CI as `ubuntu-latest` | Path comparison stops folding case, and roster self-marking degrades. Both are named in the note under Requirements above |
| **macOS** | **Not tested.** It is not in the CI matrix | `ccx doctor` prints its non-Windows blind spot there, but nothing in CI covers macOS. Treat it as unmeasured rather than working |
| **PowerShell 7.0-7.2** | **Worse than unsupported** | Only `install-selfheal.ps1` declares `-Version 7`, so it installs while every other installer refuses. You get the hook that runs `git checkout` on your shared primary, and none of the gates |
| **Windows PowerShell 5.1** | Unsupported | 26 scripts carry `#Requires -Version 7.3` and refuse to start. Three carry no `#Requires` at all, and those fail quietly instead |

On PowerShell 5.1, `announce-session.ps1` and `steer-inject.ps1` have no version guard. Both fail
open: dot-sourcing fails, the hook stops, and exit 0 allows work to continue.

CI installs pinned, digest-verified `pandoc`, runs the ASCII and leak gates, parses every shipped
`.ps1`, and runs the tests. It never runs `ccx doctor`, whose checks can need a live second
session and peer worktree.

The CI leak scan checks structural patterns unless the `CCX_FORBIDDEN_TOKENS` repository secret is
set. Without it, private-name detectors are empty.

A green run therefore clears no private names. The workflow prints that limit in capitals on every
run.

A green Linux run proves that scripts parse and tests pass there. It does not establish how hooks,
gates, or the roster behave in a real Linux session.

The pandoc install step accepts only Linux and Windows runners. It refuses an unverified install on
other platforms, leaving macOS outside the matrix.

## Session discovery rests on a vendor surface this project does not own

Session discovery reads `<config-root>/sessions/<pid>.json`. The client controls these records'
format, location, and lifetime.

Announce asks the model to deliver through the desktop-only `ccd_session_mgmt` Model Context
Protocol (MCP) server. A plain CLI install lacks that server, so delivery fails and the model
reports it.

KORUS depends on desktop coordination, session discovery, and the automatic worktree created for
each new desktop session.

Some scripts can run anywhere `pwsh` runs. Their use without the desktop app is unmeasured and falls
outside the supported KORUS setup.

`list_sessions` lists only sessions the desktop app spawned. Editor-extension sessions never
register there and cannot receive messages.

Use that list to find message recipients and the on-disk records to find existing sessions.

A renamed field or changed `startedAt` unit makes the liveness fence report "cannot tell". That
answer vetoes work; `scripts/coord/session-registry.ps1` keeps the gates refusing.

Moving the records directory drops the doctor's census to zero. Renaming fields or changing units
leaves the count unchanged because the records still parse and match worktrees.

A healthy count does not prove that the record format still matches.

An empty registry leaves the collision gate with no liveness verdicts to veto edits. It allows every
edit silently, just as when no peers exist.

The doctor's census exposes that zero count. Nothing inside a session detects the moved directory.

## What the collision gate does not see

<a id="g11"></a>
<figure class="explain-figure">
  <picture>
    <source media="(max-width: 1100px)" srcset="/assets/diagrams/g11-observation-scope-mobile.svg">
    <img src="/assets/diagrams/g11-observation-scope.svg" alt="Collision observation covers peer worktrees and specific edit triggers." loading="lazy" width="799" height="1054">
  </picture>
  <figcaption>These controls prevent accidents within one clone. Unknown state is not an empty scan, and allowed edits do not prove safety. <a href="/assets/diagrams/g11-observation-scope.drawio">Editable diagram</a>.</figcaption>
</figure>

The collision gate refuses edits when a live peer worktree holds uncommitted changes to the same
file. Its checks exclude the cases below.

`overlap.ps1` skips your own worktree before comparing paths. Two sessions in that checkout can
collide silently; this control requires one worktree per session.

The overlap map stays cached for 60 seconds, and the gate never requests a refresh. A peer who
starts touching your file during that minute remains unseen.

The gate reads peer changes from `git status --porcelain`. Three file states do not appear as
matching paths:

- A new file inside a new directory. Git reports the directory, not the file.
- A rename. Porcelain prints `R old -> new`, which matches neither path.
- Anything git-ignored, including the `.env` named further down this page.

Staged, unstaged and ordinary untracked files do count.

The gate converts targets to repo-relative paths only inside your own worktree. Absolute paths into
another worktree cannot match its repo-relative entries, so those writes go unchecked.

The gate does not resolve symlinks. Different paths to the same file therefore compare as different
files.

A dormant peer produces exit 0 with no output, even when it holds uncommitted changes to your file.
The header's claim that it "is reported and allowed" does not match that behavior.

Four cases allow the edit without entering the notice code:

| Path | Why nothing is printed |
|---|---|
| The dormant-peer case above | The gate exits before it composes a message |
| The 20-second hook timeout | A killed hook writes no decision, and the edit proceeds |
| The shim resolving no script | Unlike announce, this shim prints no missing-script notice |
| PowerShell below 7.3 | `#Requires` fires before the body runs, so its own error handling never gets a turn |

One function handles fail-open notices and suppresses repeated reasons in the same worktree for 30
minutes. If overlap stays broken, only the first edit warns; later edits look clear.

Run the doctor to check the control. In-session warnings deliberately stop repeating during that
cooldown.

## Shared runtime state is out of scope

Worktrees separate files, but running programs can still share resources. These include listening
ports, development databases, Redis keyspaces, local services, package caches, generated build
output, git-ignored `.env` files, and the machine's own processors and disk.

Tests running in separate worktrees can collide on those shared resources. Neither the gates nor the
doctor checks ports or database names.

The result can look like a flaky test or damaged fixture, hiding the cause in concurrent work.

This project has no control for shared runtime resources. Apply these two practices yourself:

- Give each worktree its own environment. `scripts/worktree/new.ps1` runs the per-checkout bootstrap
  named by `setupHook` in `ccx.config.json`, and warns when it cannot find that file.
  [Worktrees](WORKTREES.md) gives the contract the hook receives.
- Choose ports and database names per worktree, by hand. Nothing derives them for you. A setup hook
  that writes one port into every checkout has moved the collision, not removed it.

### A tool call that times out can leave its child running

Windows has no process groups. When a tool call hits its timeout, the wrapper shell dies and the
grandchild it started keeps running. Reaping the tree needs a Job Object with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, or `taskkill /T /F`.

Measured on the development host across two sessions, 2026-09-16 and 2026-09-17: seven runaway
processes, 126.2 CPU-hours between them, each pinned near a full core.

Five were whole-filesystem `find /` scans. Two were `post-commit` hooks that had been running 53
hours.

Killing them treats the symptom. Three fresh ones appeared within nine minutes of that sweep, started
by a different session.

An A/B on the same grandchild binary, with the same timeout and only the calling tool differing: the
Bash-style tool reported exit 143 while its child kept running orphaned.

The PowerShell-style tool's child kept a live parent and died with the tree. In an independent
census, all nine orphans came from `C:\Program Files\Git\` and none from `pwsh.exe`.

Two predicates a reader will otherwise get wrong:

- **A dead parent alone over-flags.** The assistant's shell wrapper exits before its child, so every
  live tool call shows a dead parent for its whole duration. One census found four dead-parent
  processes, all of them in-flight children of live agents, age zero.
- **Liveness is the wrong check after a kill.** A killed `find /` still read alive on two
  independent process instruments ten seconds later. Measure accrued CPU over a window instead,
  against a control process that does accrue.

Anything keyed on a missing parent kills live work first. The usable discriminator is binary path
AND age AND sustained core fraction, together.

On this host the assistant's own processes ran 0.00 to 0.06 of a core, and the runaways sat at 0.74
to 0.98. The band between was empty in two independent censuses.

Your absolute numbers will differ. The empty band is the part that transfers, so measure your own
fleet normal before you pick a threshold.

### An unattended output file has no size limit

A malformed shell heredoc left `python` at its interactive prompt. The background task looped one
traceback into its output file until that file reached 5,374,980,595 bytes.

Sampled at five offsets, a 2 MB window held 25,623 lines and 19 distinct ones. The file's first line
named the cause: `warning: here-document at line 12 delimited by end-of-file`.

Nothing bounds that file. One malformed command becomes gigabytes days later, and the session that
wrote it has long exited.

## Guardrails against accidents, not security boundaries

`PreToolUse` gates inspect tool arguments. They cannot see files written by shell commands, and
agent-written scripts can bypass command-string rules.

Every control runs under the agent's operating-system identity. That identity can edit the hooks,
`~/.claude/hooks/ccx-gate.repos.txt`, and the user settings that invoke them.

The agent already has permission to change those controls. It can also use two documented bypasses
without editing files:

- `--no-verify` on a commit or a push skips both git hooks. No CI-side enforcement ships.
- `CCX_ALLOW_DIRECT_PUSH=1` turns the push guard off. This separate bypass stays searchable in shell
  history. The guard prints `direct push ALLOWED` on stderr when used.

The doctor reports `CCX_ALLOW_DIRECT_PUSH=1` only if its own environment contains it. Setting it for
a single `git push` leaves no value for a later doctor run to find.

Pair local controls with rules enforced outside the agent's writable environment:

| Pair with | Why it holds |
|---|---|
| Protected branches on the remote | The rule lives on the server. Editing a local hook does not reach it |
| Required status checks | A merge that waits on a check is not waved through by a flag on the pushing machine |
| Agent credentials with no bypass permission | Bypass is a permission. Withhold it from the token the agent pushes with |

Configure these rules through your hosting provider; this repository does not set them or inspect
them with `bin/ccx-doctor.ps1`. Its own `gates` check is advisory and is not required before merge.

## Everything here fails the same way it succeeds

A broken control can produce exactly the same output as a working one. An uninstalled gate and a
working gate with no objection both allow an edit.

Run `bin/ccx-doctor.ps1` before and after installing. It prints WHAT WAS SCANNED and BLIND SPOTS ON
THIS RUN; skipped checks produce exit 2, never a pass.

The collision refusal needs a live peer with uncommitted changes to the same file, so the doctor
cannot stage that test. It checks the failure notice and names the untested refusal on every run.

## Related

| For | Read |
|---|---|
| Installing, and proving each control is live | [Quickstart](QUICKSTART.md) |
| Every control's event and its fail-open or fail-closed posture | [Hooks](HOOKS.md) |
| Proving the controls are actually running, as a method | [Drift audit case study](CASE-STUDY-drift-audit.md) |
| One desktop instance per Claude account | [Desktop accounts](DESKTOP-ACCOUNTS.md) |
