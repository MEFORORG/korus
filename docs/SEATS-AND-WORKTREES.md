# Seats and worktrees

<a id="tldrbluf"></a>

Give each session its own worktree and role card. The worktree separates files; the card supplies
the rules for that session's seat.

New worktrees contain every role card but select none. The seat marker is git-ignored, so you must
set it in each worktree.

Run these two commands once per worktree:

```powershell
pwsh -NoProfile -File scripts/worktree/new.ps1 -Name <short-name>
Set-Content .claude\seat.local.txt 'builder'
```

**Since 2026-09-19 the second line is rarely needed.** Type `/seat builder` in the new session, or
send a prompt that is exactly `builder`. Both write the marker and load the card in the same turn.

The command also writes the fleet registry record, which the bare prompt cannot, because that
record needs a goal. See [Role cards](ROLE-CARDS.md), *Two ways a seat gets set*.

This setup applies when more than one session works in a repository.

---

## The two halves solve different failures

| Half | Failure it removes | Where it is documented |
|---|---|---|
| The worktree | Two sessions editing one checkout, each overwriting the other. | [Worktrees](WORKTREES.md) |
| The role card | A session told its seat in a first message that a compaction then drops. | [Role cards](ROLE-CARDS.md) |

Separate worktrees without seat markers prevent file collisions, but leave sessions guessing which
rules apply. Each part covers a different failure.

---

## A new worktree has every card and no seat

Git tracks the cards and roster, but excludes the marker and live wiring:

| Piece | Tracked? | Reaches a new worktree |
|---|---|---|
| The cards, `docs/roles/*.card.md` | Tracked | Yes |
| The roster, `docs/roles/seats.json` | Tracked | Yes |
| The marker, `.claude/seat.local.txt` | Ignored by `.gitignore:18` | No |
| Live hook wiring, `.claude/settings.json` | Untracked | No |
| Example wiring, `.claude/settings.example.json` | Tracked, and inert | Yes, and does nothing |

Measured with `git check-ignore -v .claude/seat.local.txt`, which names `.gitignore:18` as the rule.

Every worktree can render any card but must select its own. Tracking the marker would copy the same
seat into every checkout.

The harness loads only `settings.json` and `settings.local.json`. The tracked example wiring cannot
activate a control.

---

## Why the seat belongs to the worktree

A seat named only in the first message competes with other context. Compaction can remove that
message and its rules.

A long session can therefore lose its role instructions when it still needs them.

The worktree survives a crash, compaction, account switch, or respawn. A seat marker there lets the
next session recover the role.

---

## Resolution never reads a branch or directory name

1. `.claude/seat.local.txt` in the worktree root.
2. `$env:KORUS_SEAT`.
3. Nothing. No card, and one printed line naming the command that sets a marker.

A prompt can now set that marker, and it is not an exception to this rule. `seat-declare.ps1` reads
the text the user typed this turn, never a name attached to the checkout.

The test that bans `rev-parse`, `symbolic-ref` and `git branch` from the card hook's source applies
to that hook too.

Do not infer a seat from a worktree name. That creation-time label can become stale; one worktree
here still names a question answered in its first two minutes.

A card has the weight of the working agreement, so a wrong card can override the right document. An
unset seat costs one printed line; a wrong seat can misdirect a whole session.

Two tests enforce this behavior. One runs the hook from `claude/lander-x` and requires no card; the
other rejects `rev-parse`, `symbolic-ref` or `git branch` in the source.

---

## Where the two halves disagree

| State | What happens | The tell |
|---|---|---|
| Worktree, no marker | The session runs on whatever it was told. Correct until the first compaction, then silently not. | The hook prints one line at session start. |
| Marker, but two sessions in one checkout | Both get the right rules and overwrite each other's files. | Nothing reports it. The card cannot see a second session. |
| A copied worktree directory | It carries the source's marker, so two directories claim one seat. | Two sessions answer to the same seat name. |
| A renamed worktree | Nothing changes, because no rung reads the name. | None needed. This one is safe by design. |

A card gives the session its rules, but cannot tell it who else edits the same checkout.

---

## What neither half isolates

A worktree separates files, branch, and index; a card separates rules. [Worktrees](WORKTREES.md) lists the
five things shared across a clone's worktrees.

The assistant's project memory is per machine. All worktrees may read it, but writes need one owner
because the last write wins.

Coordination state is shared and survives its worktree. Release a claim only after proving that the
directory is gone and deregistered, never because a timer expired.

---

## Setting it up

1. Create the worktree.

   ```powershell
   pwsh -NoProfile -File scripts/worktree/new.ps1 -Name <short-name>
   ```

2. Set the marker to one lowercase seat name from [`docs/roles/seats.json`](roles/seats.json).

   ```powershell
   Set-Content .claude\seat.local.txt 'builder'
   ```

3. Wire the hook once per checkout, by copying `.claude/settings.example.json` into a real settings file. Nothing
   backfills, and an unwired worktree behaves as it did before.

`*.local.*` requires a segment after `.local.`. A file named `.claude/seat.local` would be
tracked and could enter a commit through blanket staging.

---

## What this does not do

- The card supplies rules but cannot force a session to follow them.
- The marker holds the role, which a machine can write. It cannot supply the session's goal.
- Neither detects another session in the checkout. Create a worktree to separate the files.

---

## Related

- [Worktrees](WORKTREES.md) -- the commands and the isolation boundary.
- [Role cards](ROLE-CARDS.md) -- the card format and the design record.
- [The playbooks](PLAYBOOKS.md) -- the five live seats.
- [Running multiple sessions](RUNNING-MULTIPLE-SESSIONS.md) -- surfaces and channels.

The [shared-state map](CONCEPTS.md#g01) shows which files belong to one worktree and which belong to the clone.
