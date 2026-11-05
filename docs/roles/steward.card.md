# Steward -- RETIRED SEAT

**The Steward is retired as a seat. This page is a tombstone, not a card.** On 2026-11-05 the Owner
said the seat had been retired months earlier. The date of that ruling is not recorded in this
repository.

It is kept because archived pages on this site link to it. Deleting it would turn those links into
a 404, which reads as "this page never existed" rather than "this seat went away".

**Nothing replaced it.** No seat holds its duty of naming the account with headroom.

**The usage mechanism it described still runs.** The user-scope hook `watch.py`, in
`<HOME>\.claude\mefor-usage\`, prints the usage state. `steward-tick.ps1` there still writes
`status.json`. None of them is in this repository.

**The three usage states still bind.** `roles/COMMON.md`, *The usage watch hook's three states*,
holds the triggers, the stop on starting and the lift.

**Nothing here is an instruction.** If `.claude/seat.local.txt` in your worktree names `steward`,
the role-card hook injects no card and says the seat was retired. Set a live seat instead:

```
Set-Content .claude/seat.local.txt 'builder'
```

Live seats: manager, builder, lander, special, watchdog.

## What this seat owns

Nothing. Reading usage is now each seat's own act, from its own hook.

`roles/retired/STEWARD.md` keeps the record of how the levels and rates were measured.

## What it must not do

Take work. A document that routes anything to a Steward is stale, and CLAUDE.md's seat table
governs.

## Its authority

None. It started nothing and stopped nothing, and it holds nothing now.

## On arrival

You do not arrive here. Read `roles/COMMON.md` and take a live seat, such as
[the Builder](builder.card.md) or [the Manager](manager.card.md).

## The full playbook

`roles/retired/STEWARD.md`, kept as the record of what the seat did rather than as rules for
anyone.
