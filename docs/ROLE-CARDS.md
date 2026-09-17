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

---

## The four pieces

| Piece | Where | What it does |
|---|---|---|
| The marker | `.claude/seat.local.txt` | Holds one lowercase word. Git-ignored. |
| The cards | `docs/roles/<seat>.card.md` | One per live seat. Capped at 150 lines and 6 KB. |
| The roster | `docs/roles/seats.json` | Live seats, the alias map, and the retired seats with reasons. |
| The hook | `scripts/hooks/role-card-inject.ps1` | Resolves the seat, injects that card, writes a re-readable copy. |

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

## The hook never fails a turn

Every path exits 0, like the other hooks here. A missing roster, unknown label, oversized card, or
unwritable copy prints a note.

The hook runs in every worktree. A missing seat should not stop the session's work.

## The roster comes from CLAUDE.md, not from `roles/README.md`

The six registered labels are Manager, Builder, Regulator, Steward, Lander, and Special.

Special was added on 2026-09-16 for work outside the other five. Its card tells the session to read
`roles/COMMON.md` and stand by, without announcing itself.

Console was the seventh until 2026-09-10. Its broad oversight did not work, so the Manager took its
work. The label now resolves to no card, and the hook says it was retired.

Reviewer was the sixth until 2026-09-12, and nothing replaced it. The review gate it fed was retired
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

Tests enforce the 150-line and 6 KB caps, and the hook checks them again. Oversized cards cannot
load merely because a worktree skipped its tests.

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
  Regulator editing one folder need different rules, so directory scoping cannot carry a seat.
- It changes no section of `CLAUDE.md`.

## Rollout

`.claude/settings.example.json` includes the hook, but the harness loads only `settings.json` and
`settings.local.json`. The example alone does nothing.

Copy the example entry into a real settings file to enable it. There is no automatic update to
existing worktrees; unwired ones keep their prior behavior.

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

## Verification actually run

Before implementation, the tests produced 23 failures and 16 passes. The passing tests checked
existing git-ignore behavior and the CLAUDE.md roster.

Those checks correctly passed before the new code and must keep passing.

| Check | Result |
|---|---|
| `pytest tests/test_role_cards.py` | 39 passed, 12 subtests passed |
| ASCII gate, CI invocation | exit 0 |
| Hook run by hand, marker set | exit 0, card injected |

The prose gate scans only `docs/`, `README*`, and `INSTALL*`. It excludes `CLAUDE.md` and `roles/`.

A planted banned phrase in `CLAUDE.md` left the gate green, confirming that scope. This page is
inside the checked set.

The [handoff diagram](KORUS-BUILD.md#g04) shows each role alongside the work it receives and passes on.
