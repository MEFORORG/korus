---
name: "seat"
description: "Take a seat in this worktree: declare it, load its card, verify the card reached the session, and name the session. Use when the user types /seat <name>, or asks this session to take, change or confirm a seat."
user-invocable: true
disable-model-invocation: true
---

# seat

> Shared fleet rules live in [COMMON.md](../../../roles/COMMON.md). Read it first, whichever seat
> you end up holding.

`/seat <name>` binds a seat to this worktree, proves the card arrived, and names the session after
the seat and its task.

## What this closes

A seat told to a session in chat is an ordinary user turn. It competes with everything else in the
context, and a compaction drops it.

The marker at `.claude/seat.local.txt` survives all of that. Nothing wrote it automatically until
2026-09-19, and the injector only ran at SessionStart, so a mid-session declaration produced a
correct marker and no card until restart.

This command does both halves in one turn, then checks its own work.

## Run these five steps in order

Do not skip step 4. A declaration nobody verified is the failure this command exists to end.

Step 5 waits on the task, so it may land a turn or two later than the rest.

### 1. Resolve the label

```powershell
pwsh -NoProfile -File scripts/coord/seat.ps1 -Declare -Seat <name> -Goal "<one line>"
```

That writes two things at once: the fleet registry record, and the marker at
`.claude/seat.local.txt`.

**The goal is yours to write, and the command needs one.** A machine can write the role. No machine
can write why this session exists.

If the user gave no goal, take it from what they asked for. Ask only if nothing in the conversation
supplies one.

**An unknown label stops here.** Print the live roster and stop. Never pick the nearest spelling.

**A retired label stops here too.** Print the retirement reason from `docs/roles/seats.json`. Do not
substitute the successor seat without saying so.

### 2. Load the card

```powershell
pwsh -NoProfile -File scripts/hooks/role-card-inject.ps1 -WorktreeRoot .
```

Its output is the card. Reading it is the point, so read it now rather than skimming past it.

### 3. Verify, in three grades

Report all three. They fail independently, and only the third answers whether the session holds the
rules.

| Grade | Question | How to check |
|---|---|---|
| **Marker set** | Will the seat survive a restart? | `cat .claude/seat.local.txt` equals the canonical seat |
| **Card emitted** | Did the bytes reach the transcript? | Step 2 exited 0 and its output carried the card, not a refusal |
| **Context set** | Does this session hold it? | The readback below |

### 4. Readback

State these three from the card you just read, without reopening the file:

1. The seat you now hold.
2. What that seat owns.
3. Its single hardest prohibition, in the card's own terms.

**If you have to reopen the file to answer, the context is not set.** Say so plainly, and say the
card arrived as text the session did not absorb. That reading is worth more than a green tick.

### 5. Name the session

Set the session title to the seat and a one or two word summary of what it is here to do.

```
<Seat>: <one or two words>
```

`Lander: queue drain`. `Builder: seat skill`. `Manager: wave 3`. `Watchdog: drain watch`.

Call `mcp__ccd_session_mgmt__set_session_title` with `session_id` set to `"self"` and that title.

**That tool is often deferred, so calling it cold fails.** Load it first, then call it:

```
ToolSearch: select:mcp__ccd_session_mgmt__set_session_title
```

**Wait until you know the task.** The seat is half the title, and the other half comes from the goal
you wrote in step 1, or from the brief that arrives after it.

If the seat is set and nothing has named a task yet, rename on the first turn that supplies one.

**Use the canonical seat, not the alias you were handed.** `adhoc` declares the Special seat, so the
title reads `Special`. The marker at `.claude/seat.local.txt` holds the canonical word.

**Rename again only when the title stops describing the session.** A seat change does that, and so
does work that moves somewhere the old two words do not cover. One item is not a new title.

**No such tool means no title, and that is not a failure.** Say in one line that the tool was
absent, and go on. The marker, the card and the readback are what the seat rests on.

## Why the readback is not ceremony

A file on disk is not context. The first two grades pass for a card nobody read.

`docs/ROLE-CARDS.md` records an open probe: nobody has tested whether a SessionStart hook can emit
`hookSpecificOutput.additionalContext` or only plain stdout. That decides whether a card lands at
working-agreement weight.

A skill sidesteps the question, because its output is already in the turn. The readback is what
turns that from an assumption into a reading.

## A title is a label, never an address

Renaming changes what a person reads in the session list. It changes nothing a tool resolves.

Measured 2026-09-22 in this worktree: `ListAgents` returned `loving-jang-b1eff8-c4` both before the
rename and after it. That name comes from the worktree and a ref, and `SendMessage` takes it.

**So do not resolve a peer by its title.** `fleet.ps1` reads declarations, and a title is not one.
Two sessions answered to "Liaison" on 2026-08-29, one declared and one not, and an owner item
reached the undeclared one.

`.claude/skills/fleet-message-a-peer/SKILL.md` holds that measurement.

**A tidy title makes the wrong route look safer.** That is the cost of step 5, and the reason this
section exists.

## What this command does not do

- It does not make a session obey. It makes the rules present, and says whether they arrived.
- It does not replace an announcement. A seat about to write to a tracked path, push, or hold a
  shared resource still tells its peers. `roles/COMMON.md`, *Coordinate before you write*.
- It does not grant authority. Holding the Lander's card is not holding the merge.
- It does not read a branch or a directory name. Those are creation-time labels that nothing keeps
  current, and a wrong card outranks the document the session should be reading.

## The automatic half

`scripts/hooks/seat-declare.ps1` does the same binding without the command, for a prompt whose
whole text is a roster label. `special` declares. `special seat` and `claude/special-d4c4b4` do
nothing.

That hook writes the marker and loads the card. It never writes a goal, so a session that needs to
be visible to peers still runs step 1 here.

**It cannot rename either.** A hook has no session-title tool. A session seated that way still owes
step 5, and no restart will do it for them.
