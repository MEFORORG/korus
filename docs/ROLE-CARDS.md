# Role cards: giving a worktree a seat that outlives its session

<a id="tldrbluf"></a>

A worktree can keep its seat across sessions. Set a one-word marker, and the `SessionStart` hook
loads the matching role card.

A seat assigned in an opening message competes with later chat and may be lost during compaction.
The marker lets the hook restore that instruction.

If you run only one session here, you may not need separate seat cards.

Set the marker once in each worktree:

```powershell
Set-Content .claude\seat.local.txt 'builder'
```

**Since 2026-09-19 you rarely need that command.** Two things now set the marker for you, and both
load the card in the same turn.

```
/seat builder          the command. Declares, loads the card, then verifies all three grades.
builder                a prompt that is EXACTLY a roster label. The hook treats it as a declaration.
```

*Two ways a seat gets set* explains why the second one is a declaration rather than the guess this
page spends most of its length refusing.

---

## The four pieces

| Piece | Where | What it does |
|---|---|---|
| The marker | `.claude/seat.local.txt` | Holds one lowercase word. Git-ignored. |
| The cards | `docs/roles/<seat>.card.md` | One per live seat. Capped at 150 lines and 8 KB. |
| The roster | `docs/roles/seats.json` | Live seats, the alias map, and the retired seats with reasons. |
| The hook | `scripts/hooks/role-card-inject.ps1` | Resolves the seat, injects that card, writes a re-readable copy. |

**Two more arrived 2026-09-19**, and the heading above keeps its old number because a frozen archive
cites it.

| Piece | Where | What it does |
|---|---|---|
| The command | `.claude/skills/seat/SKILL.md` | `/seat <name>` declares, loads the card, then verifies. |
| The prompt hook | `scripts/hooks/seat-declare.ps1` | Turns a prompt that is exactly a roster label into a declaration. |

The marker stays with the worktree through a crash, compaction, account switch, or respawn. A
replacement session can use the same seat.

## Why the marker is named `seat.local.txt`

The filename follows this repository's ignore rules.

`.gitignore` deliberately keeps `.claude/` visible to git. Tracked files there must include
`.example.` in their names; `*.local.*` excludes machine-local files.

Measured with `git check-ignore -v`:

| Path | Ignored? |
|---|---|
| `.claude/seat` | **No.** It would show as untracked. |
| `.claude/seat.local` | **No.** `*.local.*` needs a segment after `.local.` |
| `.claude/seat.local.txt` | Yes, by `.gitignore:18` |
| `.claude/ROLE.local.md` | Yes, by `.gitignore:18` |

The name needs text after `.local.` to match the ignore rule. `TheMarkerCannotRideIntoACommit` in
`tests/test_role_cards.py` checks all four paths.

Check your repository's ignore rules before copying these paths. A sibling project ignores
`.claude/**` but tracks `CLAUDE.local.md`.

A path safe there could appear as untracked here and enter a blanket commit.

## Resolution order, and why it ends in silence

1. `.claude/seat.local.txt` in the worktree root.
2. `$env:KORUS_SEAT`.
3. Nothing. No card, and the hook prints the one command that sets a marker.

The hook never infers a seat from a branch or directory name.

Nothing updates a worktree name after creation. One name here still describes a question its session
answered in the first two minutes.

The design intends a card to carry working-agreement weight. A wrong card could therefore direct a
session to follow another seat's rules.

With no resolved seat, the hook instead prints one line. The later probe section records the
remaining uncertainty about injection weight.

One test runs the hook under `claude/lander-x` and requires no card. Another rejects hook source
containing `rev-parse`, `symbolic-ref`, or `git branch`.

## Two ways a seat gets set

Until 2026-09-19 nothing wrote the marker on its own. The card hook loaded a card when a marker
already existed, `scripts/coord/seat.ps1 -Declare` wrote one, and nothing ran either.

So a harness-created worktree was born seatless. The seat arrived as an ordinary chat turn, and the
card never loaded for the session that had actually been told its seat.

Measured here on 2026-09-19: a session was told `special`, held that seat for its whole run, and no
card was ever injected.

| Route | Trigger | What it writes |
|---|---|---|
| `/seat <name>` | You type it | The registry record, the marker, the card, and the three grades |
| `seat-declare.ps1` | A prompt that is exactly a roster label | The marker and the card |
| `seat.ps1 -Declare` | You run it | The registry record and the marker |
| The card hook | Every `SessionStart` | The card, from a marker that already exists |

**The command is the fuller route, because it writes a goal.** A machine can write the role. No
machine can write why this session exists.

### Why a bare prompt is a declaration and a branch name is not

Owner ruling, 2026-09-19. The rule is exactness, and nothing else.

| Prompt | Result |
|---|---|
| `special` | Declares the Special seat |
| `/seat special` | Declares it, and says so if the label matches nothing |
| `SPECIAL` | Declares it. Case and surrounding whitespace do not matter |
| `adhoc` | Declares it, through the alias map |
| `special seat` | Nothing |
| `claude/special-d4c4b4` | Nothing |
| `I think the special seat should handle this` | Nothing |
| `console` | Refuses, and prints why the seat was retired |

A branch name is a creation-time label that nothing keeps current. A prompt is different in the one
way that matters: the user typed it this turn, on purpose, as the whole of their message.

The hook therefore reads no ref. `TheHookReadsNoRef` fails on source containing `rev-parse`,
`symbolic-ref`, `git branch` or `--show-current`, which is the same ban the card hook carries.

**Refusals outnumber acceptances in `tests/test_seat_declaration.py` on purpose.** The distance
between a declaration and a guess is one exactness test, so that test is what most of the file
measures.

## The three verification grades

`/seat` reports all three. They fail independently, and only the third says whether the session
holds the rules.

| Grade | Question it answers | Instrument |
|---|---|---|
| Marker set | Will the seat survive a restart? | `.claude/seat.local.txt` equals the canonical seat |
| Card emitted | Did the bytes reach the transcript? | The injector exited 0 and printed a card, not a refusal |
| Context set | Does the session hold it? | The readback |

**The readback is the only grade that can fail while the other two pass.** The session states its
seat, what that seat owns, and its hardest prohibition, without reopening the file.

A file on disk is not context. The first two grades pass for a card nobody read.

**The card-emitted grade is paired with a planted control that must fail.** A check that cannot go
red measures nothing, and this tree has twice published a zero from a detector that was not armed.

## The hook never fails a turn

Every path exits 0, like the other hooks here. A missing roster, unknown label, oversized card, or
unwritable copy prints a note.

The hook runs in every worktree. A missing seat should not stop the session's work.

## The roster comes from CLAUDE.md, not from `roles/README.md`

The six registered labels are Manager, Builder, Steward, Lander, Special, and Watchdog.

Regulator retired on 2026-09-19 by Owner instruction, and nothing replaced it. Its label now
resolves to no card and the hook says it was retired.

Watchdog was added on 2026-09-19. It watches another seat work and files what it learns, and it
does not do the work it watches.

It did not inherit the Regulator, retired hours later the same day. That seat returned a
binding verdict on one red check; a Watchdog returns evidence and decides nothing.

Special was added on 2026-09-16 for work outside the other five. Its card tells the session to read
`roles/COMMON.md` and stand by, without announcing itself.

Console was the seventh until 2026-09-10. Its broad oversight did not work, so the Manager took its
work. The label now resolves to no card, and the hook says it was retired.

A sixth seat went on 2026-09-12, unreplaced and deliberately unnamed. Its review gate was retired
on 2026-09-04, so a pull request merges on its two required checks. That label resolves to no card too.

The original design record described `roles/README.md` as a partial list copied from a private
vault. It said Dispatcher, PM, Liaison, Cleaner, Role manager, and Process improvement remained live
there.

[The later roster check](PLAYBOOKS.md#rolesreadmemd-agrees-with-the-roster-and-this-page-said-it-did-not) retracts that claim.

CLAUDE.md's seat table governs, as its note states. A test checks that the card roster agrees with
it.

A retired label returns no card and prints the retirement reason. The reader can tell that the card
was removed on purpose.

## Why the alias map exists

A sibling project had 46 role strings for six seats. Eight strings named one seat, often with
numbers to distinguish concurrent sessions.

The alias map groups those spellings under one seat. An unmapped string returns no card.

## What a card carries, and what it must not

Each card has five sections: ownership, prohibitions, authority, arrival checks, and the full
playbook path.

Keep expiring information out of cards. Put open queues, item numbers, and blockers in dated notes.

A seat folder elsewhere had two failures from stale instructions. A "do not install" rule became
wrong after a fix merged, and sessions twice cited an expired freeze.

Tests enforce the 150-line and 8 KB caps, and the hook checks them again. Oversized cards cannot
load merely because a worktree skipped its tests.

**The byte cap rose from 6 KB on 2026-09-19**, by the Owner's Lander-and-Watchdog pairing ruling,
which gave those two seats five standing blocks the other cards do not carry. The line cap did not
move, and it now binds both: 142 and 146 of 150.

**The hook's `$maxBytes` is the copy that decides**, because it is what refuses to inject. Raising
the test alone ships a card that silently never loads. `test_the_two_copies_of_the_byte_cap_agree`
now binds them, and was proven by desyncing them and watching it fail.

The number lived in five places when it moved: the hook, the test, this page twice, and
`PLAYBOOKS.md`. The two `.old.md` archives keep the 6 KB reading, correctly, as the record of what
was true when they were frozen.

## The leak half is not decoration

The cards came from private-vault playbooks. That transfer had already published six user-home paths
and two private artifact URLs while the gate returned zero both times.

Tests scan every card for artifact URLs, bare UUIDs, and user-home paths. Each scan includes a
planted violation that must trigger it.

The six paths showed why a pattern that matches nothing cannot be trusted.

At the time of this card change, `scripts/security/scan_forbidden.py` had no artifact-URL pattern.
That separately filed gap is now covered in [the leak gate's detector history](LEAK-GATE.md#what-it-catches).

## What this does not do

- It does not make a session obey. It makes the rules present.
- It does not replace a seat declaration. The marker carries the role, which a machine can
  write. It does not carry the goal, which no machine can.
- It does not compete with a nested `CLAUDE.md`. Those scope by directory. A Builder and a
  Watchdog editing one folder need different rules, so directory scoping cannot carry a seat.
- It changes no section of `CLAUDE.md`.

## Rollout

`.claude/settings.example.json` includes both hooks, but the harness loads only `settings.json` and
`settings.local.json`. The example alone does nothing.

Copy the example entries into a real settings file to enable them. There is no automatic update to
existing worktrees; unwired ones keep their prior behavior.

**The `UserPromptSubmit` key in that example was created, not edited.** PR 130 removed the key
entirely on 2026-09-19 when `context-budget.ps1` went, because that hook was its only entry.

**`/seat` needs no wiring at all.** A skill is loaded by the harness from `.claude/skills/`, so the
command works in a checkout where neither hook is installed. That is the route to reach for when a
copier's settings are not set up yet.

## The one thing still unproven

It remains untested whether a project-level `.claude/settings.json` hook can emit
`hookSpecificOutput.additionalContext` at `SessionStart`, or only plain stdout.

That decides whether the card arrives at working-agreement weight or as ordinary hook output.

Every exercised `additionalContext` hook in this repository uses `PreToolUse`:

| Hook | Event | Output shape |
|---|---|---|
| `scripts/hooks/collision_gate.ps1` | `PreToolUse` | `additionalContext` |
| `scripts/hooks/steer-inject.ps1` | `PreToolUse` | `additionalContext` |
| `scripts/hooks/block-blanket-git-stage.ps1` | `PreToolUse` | `additionalContext` |
| `scripts/worktree/session-context.ps1` | `SessionStart` | plain stdout, line 226 |

The repository has exercised `PreToolUse`, but not `SessionStart`, with `additionalContext`. This
role-card hook uses plain stdout, the output already exercised at `SessionStart`.

Test it with one hook, a distinctive token, and a fresh session.

**`/seat` sidesteps the question rather than answering it.** A skill's output is already inside the
turn, so the card does not depend on what a hook may emit.

The readback is what turns that from an assumption into a reading. The probe above stays open for
the two hooks, which still emit plain stdout.

## Verification actually run

Before implementation, the tests produced 23 failures and 16 passes. The passing tests checked
existing git-ignore behavior and the CLAUDE.md roster.

Those checks correctly passed before the new code and must keep passing.

| Check | Result |
|---|---|
| `pytest tests/test_role_cards.py` | 39 passed, 12 subtests passed |
| ASCII gate, CI invocation | exit 0 |
| Hook run by hand, marker set | exit 0, card injected |

**The 2026-09-19 additions, measured at `9a215ff` plus the change:**

| Check | Result |
|---|---|
| `pytest tests/test_seat_declaration.py`, before the hook existed | 50 failed, 6 passed |
| `pytest tests/test_seat_declaration.py`, after | 31 passed, 35 subtests passed |
| `pytest tests/` | 673 passed, 2 skipped, 586 subtests passed |

The red run is quoted because it is the control. The 6 that passed first were the planted controls
and the checks against the existing injector, which is what should pass before any new code.

**The first draft of `seat-declare.ps1` did not parse.** It piped `< $null` into the injector, a
bash redirect, and `<` is a reserved operator in PowerShell. The hook exited 1 on every turn.

That is recorded because the hook's own promise is that it never fails a turn, and a parse error
breaks that promise before any of its logic runs.

The prose gate scans only `docs/`, `README*`, and `INSTALL*`. It excludes `CLAUDE.md` and `roles/`.

A planted banned phrase in `CLAUDE.md` left the gate green, confirming that scope. This page is
inside the checked set.

The [handoff diagram](KORUS-BUILD.md#g04) shows each role alongside the work it receives and passes on.
