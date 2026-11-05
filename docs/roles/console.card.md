# Console -- RETIRED SEAT

**The Console retired on 2026-09-10. This page is a tombstone, not a card.**

It is kept because archived pages on this site link to it. Deleting it would turn those links into a
404, which reads as "this page never existed" rather than "this seat went away".

[The Manager](manager.card.md) replaced it, and **is not a renamed Console.** A Console reached
across every account and oversaw the whole build. That breadth is the part that did not work.

A Manager sits inside ONE account, several run at once, and its workers can be subagents in its own
process -- for which it needs no spawn grant. Do not carry a Console rule over by swapping the word.

**Nothing here is an instruction.** If `.claude/seat.local.txt` in your worktree names `console`, the
role-card hook injects no card and says the seat was retired. Set a live seat instead:

```
Set-Content .claude/seat.local.txt 'manager'
```

Live seats: manager, builder, lander, special, watchdog.

## What this seat owns

Nothing. Read [the Manager's card](manager.card.md) and `roles/MANAGER.md` instead.

## What it must not do

Take work. A document that routes anything to a Console is stale, and CLAUDE.md's seat table governs.

## Its authority

None. It holds no grant and no standing permission.

## On arrival

You cannot arrive here. The hook resolves `console` to the retired message, never to this page.

## The full playbook

The record of what this seat did is `roles/retired/CONSOLE.md`. Read it as history. The version of
this page from before the retirement is at [console.card.old.md](console.card.old.md).
