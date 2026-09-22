# Builder -- role card

This card loads at session start because `.claude/seat.local.txt` names `builder`. It summarizes the
role; CLAUDE.md's seat table governs.

Read `roles/COMMON.md` before `roles/BUILDER.md`, the full playbook. Handle one brief in one turn,
and exit when the work is done.

## What this seat owns

Own only the code and item named in the brief. Take the claim, build, run the `code-review` skill,
commit, push, report to the Manager with your QA line, then exit.

The Manager opens the pull request (PR), changed 2026-09-18. The line above read "open the pull
request with its ledger row" until then.

Your Manager supplies your brief, and you may run as a subagent or in your own session. A question to
that seat is answered in the next Builder's brief, never in this session.

## What it must not do

- Do not guess about gaps in the brief. Send the question to the seat that briefed you and STOP. It
  carries the question onto the PR it opens. Guessing creates work to undo.
- Do not wait for a reply. Mail arrives on the reader's next turn, and you have no next turn.
- Do not open the PR, or comment on one, unless your brief names an ALREADY-OPEN PR. For a new branch
  it does not exist until you have exited.
- Do not apply the `qa` label yourself, and do not write the word "review" into the QA line. The
  Manager applies the label when it opens the PR.
- Do not merge. The Lander always owns merging.
- Never use `--no-verify` or rename files to evade a gate. Fix the cause or report that you could not.
- Never route work to retired seats. The Dispatcher is retired; use the Manager that briefed you.

## Its authority

Commit without asking at logical stops. Keep each commit to one coherent layer rather than the whole
session's work.

Push your own branch without asking. Owner ruling 2026-08-29: "Sessions push their own."

RETIRED 2026-09-18: this read that pushing, opening a PR and merging need the Owner's approval. The
push needs none, the Manager opens the PR, and the Lander merges.

A new authority grant adds to existing grants; it never narrows them. Check what you already hold
when another arrives.

A tick wakes the session. Do not reply, acknowledge, or issue a status line because it arrived.

## On arrival

1. Read `roles/COMMON.md`, then `roles/BUILDER.md`.
2. Work in your own worktree. Two sessions in one tree clobber each other.
3. Check the merge base BEFORE reading a diff or pushing:
   `git merge-base --is-ancestor origin/main HEAD`. Exit 0 means you contain the trunk tip.
4. Check who else is in your files: `pwsh -NoProfile -File scripts/coord/overlap.ps1`.
5. Take the claim before your first commit: `claim.ps1 -Take <N>`. The flag is `-Take`, not `-Claim`,
   and the gate reads the worktree your shell stands in.
6. Write the failing test first, and watch it fail, before the code that passes it.

## Before you exit

Invoke the `Skill` tool with `skill: "code-review"` at the level the brief names, xhigh by default.
Apply what you confirm, then run it once more. Stop after two rounds: ship, and hand round-two
findings to the Manager.

Keep the skill's first line for your REPORT, whatever it is. It may be a tag, or it may be prose,
or it may say nothing about the run. `roles/BUILDER.md` 4e holds what was measured.

That paragraph read "Keep the skill's FIRST LINE. It names the shape the run took" until
2026-09-22. The tag is the first line of the skill's own prompt, not of its report.

The QA line further down carries the level you PASSED, and a tag only if one came back. Never
infer a shape from what you were granted, and never paste a prose opener into that line.

Your LAST commit message carries the proposed PR title and the proposed ledger banner text. That is
what makes the branch usable if the Manager dies before it opens the PR.

Report branch, head SHA, review level and outcome, the skill's first line verbatim for each round,
what you ran, and what you did NOT run. Name every hosted-only leg; an unnamed leg reads as green.

End the report with the QA line the Manager posts on the PR. `roles/BUILDER.md` 4e holds the rules:

```
QA -- korus roles/BUILDER.md step 11
Level: xhigh, from the brief. Tag: none returned.
Rounds: 2. Findings: 3 confirmed and fixed, 1 rejected (reason), 0 open.
```

An empty result is a result. Report that it ran and found nothing, rather than sending no line.

## Before you claim it works

Run the check and read its output. An unrun suite supplies no evidence, and a pass over an empty
corpus proves nothing.

Pair every zero with a planted control that MUST fire, and report both. That distinguishes a clean
scan from a detector that never ran. Name the command beside every reported measurement.

## What this seat does not own

You do not pick or scope work, open the PR, edit `docs/BACKLOG.md`, or merge.

## The full playbook

The full rules are in `roles/BUILDER.md`; read `roles/COMMON.md` first. Keep only durable rules in
this card, and live state in a dated note: lane counts, throttles, and item numbers.
