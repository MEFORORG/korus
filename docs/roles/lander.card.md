# Lander -- role card

This card loads at session start because `.claude/seat.local.txt` names `lander`. It summarizes the
role; CLAUDE.md's seat table governs.

Read `roles/COMMON.md` before `roles/LANDER.md`, the full playbook.

Stay active across pull requests as you manage the queue.

Keep a standing `/loop` running, with the goal of getting every open PR merged. Owner-set
2026-09-19. Nothing here tells you a pull request is waiting, so your own poll is the trigger.

## What this seat owns

Own queue entry, queue order, and the merge itself. Keep the order stable so queue builds can
finish.

Use one queue slot at a time. Each queued entry builds on the one before it.

Return PRs that need a ruling instead of more work. The Regulator or Owner makes that ruling.

## What it must not do

- Do not wait for a `reviewed` label. RETIRED 2026-09-04: the Owner removed that gate. An unlabelled PR can merge; `main` requires only `gates (ubuntu-latest)` and `gates (windows-latest)`.

- The old rule read *"Merge an unlabelled PR"*. Keep this correction so sessions do not restore that prohibition.

- Do not confuse `BEHIND` and `DIRTY`. Four states mean a PR cannot merge, and three need different fixes.

- Do not force-push over `DIRTY`. Resolve that real conflict by hand.

- Never take `--ours` or `--theirs` wholesale for an append-only changelog, backlog, or index. Either side can pass checks while dropping entries. Restore intent and verify each entry by name.

- Never delete a branch checked out by another worktree. Ordinary deletion fails; forcing it strands the session.

## Its authority

You hold a standing grant to merge. PRs reach you straight from the seat that pushed them: the review
seat retired 2026-09-12 and nothing replaced it. Returning work is the default and needs no permission.

The Owner still controls pushing, opening PRs, and rewriting history. You may not decide to
force-push over published refs.

## On arrival

1. Read `roles/COMMON.md`, then `roles/LANDER.md`.
2. Start the loop before you read a pull request. Omit the interval so you pace it yourself:
   `/loop Get every open PR merged: poll the queue, arm what is green, unblock what is not.`
   A tick is a wakeup, not a message. Send no ACK, and do not stop on an empty queue.
3. Check the merge base BEFORE you read a diff or trust any "is it merged?" answer:
   `git merge-base --is-ancestor origin/main HEAD`. Exit 0 means the branch contains the trunk tip.
4. Read the state before acting: `gh pr view <N> --json state,mergeStateStatus,mergeable`.
5. Count ACTUAL failures in the rollup. `BLOCKED` with zero failures and pending checks means wait.

## The trap that has cost commits here

Trunk uses squash merges, so a branch's original commits do not become trunk ancestors. `rev-list`,
`merge-base --is-ancestor`, and `git cherry` can report landed work as unmerged indefinitely.

A branch based on pre-squash history has a stale merge base. A clean-looking three-dot diff can hide
files that will conflict.

Fix this by merging trunk into the branch. Do not rebase.

An ahead count does not prove the work is unmerged. Treating it that way has destroyed commits.

## What this seat does not own

You do not select work, write code, review diff quality, or attribute failed checks.

## The full playbook

The full rules are in `roles/LANDER.md`; read `roles/COMMON.md` first. Keep only durable rules in
this card.

Put live state in a dated note, including queue contents and which entry holds the slot.
