# Watchdog episode note, 2026-09-19

**Live state for the seat, written at handoff.** [WATCHDOG.md](../../roles/WATCHDOG.md) holds what
never expires. This holds what was true when this session ended, and it expires.

**The session that wrote this is transferring to another account.** Nothing below is a rule.

---

## What the seat was doing

Watching the Lander drain the merge queue across three repositories, and keeping a status board.

The board is published and its link is the one the owner holds. Republish to that same URL rather
than making a second board. [LANDER-BOARD.md](../LANDER-BOARD.md) section 9b has the resume steps.

## What is running that will not survive this session

| Thing | Dies with the session | Replace it with |
| --- | --- | --- |
| The board refresh clock | yes, it was a background monitor | a monitor calling `scripts/board/refresh.sh`, per section 9b |
| The publish-lag alarm | yes | the same monitor, stamping build and publish separately |
| The Lander state check | yes | `scripts/board/seatstate.py` in that monitor |
| The scratchpad working files | yes, and they are all regenerable | one `refresh.sh` run |

**A session cron cannot replace the monitor.** It fires only while the session is idle, and a
session that is working is never idle. Measured: a 15-minute cron fired zero times across about
25 opportunities.

## Open work, at handoff

| Item | State |
| --- | --- |
| korus, the board's clock time and status colours | pull request open, gates green, not merged |
| korus, the Lander and Watchdog pairing rules | pull request open, written by another seat, this seat checked it |
| korus, the two same-instance channels are not interchangeable | pull request open, not merged |
| engine, removing the context-budget hook | pull request open, not merged |

The merge is the Lander's on every one of them. This seat opened them and merged nothing.

## What was measured, and cost the most to learn

**Nine instrument failures in one shift, every one looking clean.** The shape was identical each
time: a filter that did not match what the reading claimed to check.

[WATCHDOG.md](../../roles/WATCHDOG.md) section 4 lists them. Two reached the owner as published
findings before a control caught them.

**A seat suspended on its own question looks exactly like an idle one.** The Lander sat on an
`AskUserQuestion` for 10h37m while this seat reported a capacity stall.

A suspended session does not drain its queue, so four peer messages sat unread behind it. Only the
owner could clear it, and this seat never said so.

**Cross-session `SendMessage` enqueues; it does not wake.** The CCD session transport arrives as a
user turn and does. This seat held the working channel all night and used the other one.

**A repository transfer makes a board lie quietly.** korus and the vault moved to `MEFORORG`.

The old slug still resolved for `gh repo view` while every `--search` under it returned zero, so 24
and 57 merges rendered as "never" on a board that read healthy.

---

## For the next Watchdog

Read [WATCHDOG.md](../../roles/WATCHDOG.md) and its card first. Then, before your first reading:

1. Establish the Lander is alive from **two** surfaces. One is a guess, and a false "missing"
   spawns a second Lander onto one queue.
2. Read its transcript, not only its output. Working, idle and blocked-on-a-person are three
   states and only the transcript separates them.
3. Arm a control on any detector you intend to publish from. A zero beside a control that fired is
   a measurement; a zero alone is a guess wearing a number.

**Delete this note once its contents are stale.** A dated note that nobody retires becomes the
thing a later session trusts.
