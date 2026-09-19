---
name: "seat"
description: "Take a seat in this worktree: declare it, load its role card, and verify the card actually reached the session. Use when the user types /seat <name>, or asks this session to take, change or confirm a seat."
user-invocable: true
disable-model-invocation: true
---

# seat

> Shared fleet rules live in [COMMON.md](../../../roles/COMMON.md). Read it first, whichever seat
> you end up holding.

`/seat <name>` binds a seat to this worktree and proves the card arrived.

## What this closes

A seat told to a session in chat is an ordinary user turn. It competes with everything else in the
context, and a compaction drops it.

The marker at `.claude/seat.local.txt` survives all of that. Nothing wrote it automatically until
2026-09-19, and the injector only ran at SessionStart, so a mid-session declaration produced a
correct marker and no card until restart.

This command does both halves in one turn, then checks its own work.

## Run these four steps in order

Do not skip step 4. A declaration nobody verified is the failure this command exists to end.

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

## Why the readback is not ceremony

A file on disk is not context. The first two grades pass for a card nobody read.

`docs/ROLE-CARDS.md` records an open probe: nobody has tested whether a SessionStart hook can emit
`hookSpecificOutput.additionalContext` or only plain stdout. That decides whether a card lands at
working-agreement weight.

A skill sidesteps the question, because its output is already in the turn. The readback is what
turns that from an assumption into a reading.

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
