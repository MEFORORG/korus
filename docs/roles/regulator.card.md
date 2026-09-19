# Regulator -- RETIRED SEAT

**The Regulator retired on 2026-09-19, by Owner instruction. This page is a tombstone, not a card.**

It is kept because archived pages on this site link to it. Deleting it would turn those links into
a 404, which reads as "this page never existed" rather than "this seat went away".

**Nothing replaced it, and the Watchdog is not a substitute.** The two differ in every column that
matters:

| | Regulator, retired | Watchdog, live |
|---|---|---|
| Trigger | A person started it after a red | The Owner names a subject |
| Output | Four lines carrying a verdict, and it bound | Evidence, and it decides nothing |
| Lifetime | One turn, then exit | As long as the subject runs |

A Watchdog measures whether a seat is clearing reds at all. It never says whose a red is.

**So no seat attributes a red check now.** A red is [the Lander's](lander.card.md) to triage and
route, or the Owner's to rule on.

Do not route a red to a seat, and do not hold a pull request waiting for an attribution.

**Nothing here is an instruction.** If `.claude/seat.local.txt` in your worktree names `regulator`,
the role-card hook injects no card and says the seat was retired. Set a live seat instead:

```
Set-Content .claude/seat.local.txt 'builder'
```

Live seats: manager, builder, steward, lander, special, watchdog.

## What this seat owns

Nothing. Its six-owner classification of a red is the record of a method, not a live duty.

`roles/retired/REGULATOR.md` keeps that method in full, including the six owners a red could have
and the rule that only the pull request's own defect became a Builder's work.

## What it must not do

Take work. A document that routes anything to a Regulator is stale, and CLAUDE.md's seat table
governs.

## Its authority

None. It held no merge, no enqueue and no fix, and it holds nothing now.

## On arrival

You do not arrive here. Read `roles/COMMON.md` and take a live seat.

## The full playbook

`roles/retired/REGULATOR.md`, kept as the record of what the seat did rather than as rules for
anyone.
