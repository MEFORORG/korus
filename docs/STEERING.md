# Steering a running session

<a id="tldrbluf"></a>

Send a running session a message from a second terminal. It receives the note at its next tool call,
before the current turn ends.

Typing at a busy session's prompt queues your message until its turn ends. Use steering when a
long-running session needs a correction sooner.

Wire delivery in each worktree's `settings.local.json` before starting the session. [Wiring it](#wiring-it)
supplies the JSON; no installer sets it up.

---

The feature uses two files, about a hundred lines total, with no dependency on other repository
code:

| File | Role | Kind |
|---|---|---|
| `bin/ccx-steer.ps1` | writes the note | user-facing command |
| `scripts/hooks/steer-inject.ps1` | delivers the note | opt-in `PreToolUse` hook: the harness runs it before every tool call |

The directories identify each script's caller. The harness invokes scripts in `scripts/hooks/`; you
invoke commands in `bin/`.

## The problem it works around

Claude Code cross-session messages arrive between tool calls during an active turn. They never
interrupt a running tool; native Windows documents this from v2.1.224 and v2.1.234.

`SendMessage` requires a session name from its roster. That roster stops at the config root, so
it cannot name a session on another Claude account ([Session mail](SESSION-MAIL.md#who-actually-needs-this)).

Claude Code documents an inbox socket for scripts and hooks. It publishes the auth line but omits
the message format, so the docs cannot support an implementation today.

This hook addresses the project directory. At each tool call, the harness runs `PreToolUse`,
whose `additionalContext` reaches the model without a session name or undocumented format.

## How it works

Send one sentence to the active session.

Run this from a second terminal in that session's worktree:

```powershell
# terminal 2, while the session in that worktree is mid-task
pwsh -NoProfile -File bin/ccx-steer.ps1 "stop refactoring the parser; just fix the failing test"

# or, from anywhere
pwsh -NoProfile -File bin/ccx-steer.ps1 "..." -ProjectDir <path to the worktree>
```

The note follows these steps:

1. The command writes your message to `<worktree>/.claude/steer.txt`.
2. At the session's next tool call, `scripts/hooks/steer-inject.ps1` fires, finds the file, reads it, **deletes
   it**, and re-emits the text wrapped in an envelope.
3. The session sees the note before that tool call is executed.

The envelope identifies a side-channel message for the model to act on immediately.

The hook's output shape is fixed by the event:

<!-- no-copy -->
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"[STEERING NOTE ...]: ..."}}
```

The `hookSpecificOutput` wrapper is required. Top-level `additionalContext` silently fails to deliver: the
hook exits 0 and the note is lost.

## Wiring it

Enable delivery for one worktree. No installer in this repository wires the hook.

Add this to the worktree's `.claude/settings.local.json`:

<!-- no-copy -->
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "pwsh -NoProfile -File \"<absolute path to this repo>/scripts/hooks/steer-inject.ps1\"",
            "timeout": 5,
            "statusMessage": "Checking for steering notes"
          }
        ]
      }
    ]
  }
}
```

Keep the escaped quotes around the path. A space in an unquoted checkout path makes `pwsh`
treat only its first word as `-File`.

This affects two-word account names, redirected OneDrive profiles, and directories such as
`My Projects`.

Measured: that error exits 64, prints usage on stderr, and leaves stdout empty. The hook fails open,
so it looks exactly like no queued note ([fail-open section](#it-fails-open-and-what-that-costs-you)).

The wiring takes effect only in newly started sessions. Enable it before starting the session you
want to steer.

The hook is local and opt-in for two reasons:

- It costs a process spawn before every tool call. Measurements here found roughly 366 ms per tool
  call. Bare PowerShell startup accounts for about 267 ms that cannot be optimized away. A standing
  tax in every session, paid for a feature you use occasionally.
- **`*.local.*` is git-ignored** by this repo's `.gitignore`. A `.local.` filename
  belongs to one checkout on one machine. Wiring it there opts in that worktree without changing
  every clone.

## Why a file, and not an environment variable

A running process keeps the environment it received at startup. Hook wiring also resolves at session
start, so later changes reach only future sessions.

The hook rereads the file on every run. That lets the note reach a live session:

| Channel | Reaches a session that is already running | Why |
|---|---|---|
| Environment variable | no | read once, at process start |
| Settings edit | no | hook wiring is resolved at session start |
| File checked by a hook | **yes** | re-read on every tool call |

The announce off-switch uses `<state-root>/announce/OFF` for the same reason. `CCX_ANNOUNCE_DISABLE` affects only
sessions started after you set it.

A control for an active session must use a file the hook checks on every run. This includes steering
notes and emergency off-switches; environment and settings changes affect future sessions.

Shared filesystem access is enough: writing sends the note, and deleting acknowledges it. The
scripts need no port, daemon, process identity, shared code, or interprocess communication service.

## The queue is one slot deep

- Writing a second note **replaces** the first. The command warns when it overwrites one that was
  never consumed. Take the warning seriously: the earlier note was not delivered and never will be.
- Delivery is read-then-delete, and the honest bound is **at most once**. The hook checks, reads,
  deletes and emits as separate steps under no lock, and the delete lands before anything confirms
  the note reached the model. There is no history and no re-delivery.
- There is no expiry. A note sits until the session's next tool call, possibly hours later and in
  the middle of an unrelated task. Write any condition into the text so the *recipient* can evaluate
  it: "if you have not started the migration yet, don't". Never write one only you can observe.
- The command's success output is a receipt that the note was **written**, not that it was
  **delivered**. Nothing in this pair reports delivery back to you. To know it landed, see
  [It fails open, and what that costs you](#it-fails-open-and-what-that-costs-you).

## Where the note goes, and why the command refuses to guess

`Resolve-ProjectDir` in `bin/ccx-steer.ps1` resolves the target in this order:

1. `-ProjectDir`, if given,
2. the enclosing worktree root, from `git rev-parse --show-toplevel`,
3. `$env:CLAUDE_PROJECT_DIR`, if set.

**Steps 2 and 3 were the other way round until 2026-10-13.** Run from a desktop worktree session's
own shell, `CLAUDE_PROJECT_DIR` names the primary, so the note went where that session's hook no
longer looks.

The command throws if none resolves to a directory. It also throws if that directory lacks
`.claude`; it never falls back to the current directory.

An earlier version used the working directory and created `.claude` when absent. It could
report "queued" from the wrong directory even though no hook read that note.

The hook reads only `<worktree>/.claude/steer.txt`. It finds the worktree by walking up from the
`cwd` in its JSON input to the nearest `.git`. With no usable `cwd` it falls back to
`CLAUDE_PROJECT_DIR`, and with neither it exits 0 without searching.

**That paragraph read "The hook reads only `<project root>/.claude/steer.txt`" until 2026-10-13.**
The project root was `CLAUDE_PROJECT_DIR`, which the desktop app sets to the PRIMARY checkout for a
worktree session. Measured 2026-10-12. So a note queued from the worktree was never read there.

A note read from the fallback says so in the text the session sees, because it may be another
session's note.

## Encoding

Both scripts use ASCII. They write the note as UTF-8 without a BOM (`-Encoding utf8` in PowerShell
7), independent of either console's code page.

`.editorconfig` pins UTF-8-no-BOM and LF because other controls compare installed and source
hashes. `-NoNewline` preserves the typed message; the hook trims whitespace and skips blank
notes.

## It fails open, and what that costs you

The hook's header states that every error exits 0. A broken steering channel must never block a tool
call or break the session.

Unwired hooks, missing scripts, and immediate exceptions all emit nothing. That matches the output
when no note waits, so silence cannot establish that steering works.

Check the note file outside the hook:

> **The note file is the receipt.** After the session has made at least one tool call, if
> `<worktree>/.claude/steer.txt` still exists, the hook did not run. If it is gone, it was consumed.

`bin/ccx-doctor.ps1` lists settings that wire the injector but does not run it. `OK` means
"wired here"; `--` means no visible wiring, which is allowed for this opt-in feature.

## Proving it end to end

Run the hook to inspect its actual output.

Run from a terminal with no input, the hook falls back to `CLAUDE_PROJECT_DIR`. Drive it directly:

```powershell
pwsh -NoProfile -File bin/ccx-steer.ps1 "throwaway probe, ignore"

$env:CLAUDE_PROJECT_DIR = (git rev-parse --show-toplevel)
pwsh -NoProfile -File scripts/hooks/steer-inject.ps1

Remove-Item Env:\CLAUDE_PROJECT_DIR      # do not skip this -- see below
```

Expect one compact JSON line containing your text, followed by the removal of `.claude/steer.txt`.

Use these precautions:

- **Unset `CLAUDE_PROJECT_DIR` afterwards.** Outside a worktree, `ccx-steer.ps1` falls back to it.
  Left set, it silently aims every later run from outside a checkout at the directory you probed
  from -- including notes you meant for another worktree.
- This consumes the note. Probe with a throwaway message, never with one you actually queued for a
  session.
- Run the copy your settings name, not the repo copy, if the two differ. A control is enforced by
  the file that is wired, and it can drift arbitrarily far from the file you are reading.

An empty result does not prove the note survived. A failure after deletion or a timeout can destroy
the note before the hook emits it.

Treat an empty result as "gone and undelivered", never "still queued".

## The trust boundary

The envelope identifies the note as the operator's words and gives it prompt authority. Anyone able
to write `<worktree>/.claude/steer.txt` can impersonate the operator.

Trust the note only as far as you trust the worktree. Never send peer-session messages through this
channel: peer data must not acquire the user's authority.

## Limits

| Limit | Detail |
|---|---|
| Platform | PowerShell 7, Windows-first. Both scripts are plain PowerShell with no other dependency. |
| Delivery point | Only at a tool call. A session composing a long answer without calling a tool will not see the note until it next calls one. |
| Wiring reach | Enabling the hook affects newly started sessions only. The *note* reaches a running session; the *hook* has to already be there. |
| Depth | One note per worktree. No queue, no history, no re-delivery. |
| Receipt | The command confirms the write, never the delivery. The absence of the file is your only delivery evidence. |
| Failure mode | Fails open and silently by design; a broken hook is indistinguishable from an idle one at the session. |
| Install | No installer wires it. `bin/ccx-doctor.ps1` reports whether it is wired, by receipt, and does not attack it. |

The [mail timeline](SESSION-MAIL.md#g09) shows a different delivery path and its limits.
