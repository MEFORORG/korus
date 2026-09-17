# Reviewer -- RETIRED SEAT

**The Reviewer retired on 2026-09-12. This page is a tombstone, not a card.**

It is kept because archived pages on this site link to it. Deleting it would turn those links into a
404, which reads as "this page never existed" rather than "this seat went away".

**Nothing replaced it.** The review gate this seat fed was retired on 2026-09-04: no label blocks a
merge, and the required checks on `main` are `gates (ubuntu-latest)` and `gates (windows-latest)`.

Reading a diff and posting findings nobody is required to act on stopped being a seat's job.
[The Lander](lander.card.md) already merges without waiting for one. Do not add a review step back.

**Nothing here is an instruction.** If `.claude/seat.local.txt` in your worktree names `reviewer`, the
role-card hook injects no card and says the seat was retired. Set a live seat instead:

```
Set-Content .claude/seat.local.txt 'builder'
```

Live seats: manager, builder, regulator, steward, lander.

## What this seat owns

Nothing. A pull request merges on its two required checks, with no review step ahead of it.

## What it must not do

Take work. A document that routes anything to a Reviewer is stale, and CLAUDE.md's seat table governs.

## Its authority

None. It holds no grant and no standing permission.

## On arrival

You cannot arrive here. The hook resolves `reviewer` to the retired message, never to this page.

## The full playbook

The record of what this seat did is `roles/retired/SEAT-RETIRED-2026-09-12.md`. Read it as history.
The version of
this page from before the retirement is at [reviewer.card.old.md](reviewer.card.old.md).
