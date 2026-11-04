---
name: "fleet-ledger-row"
description: "Allocate, claim, file or act on a backlog row. Use before touching docs/BACKLOG.md or an allocation."
user-invocable: true
disable-model-invocation: false
---

# fleet-ledger-row

> Shared fleet rules, split out of [COMMON.md](../../../roles/COMMON.md) on 2026-09-05.
> Prohibitions that bind before this task starts stay in that file. Read it first.

### Before you allocate, grep the ALLOC TITLES for your subject, not the ledger

`alloc.ps1` prevents two sessions taking the same number for different subjects. That is its one job
and it does it. **It cannot know that two titles describe one defect.**

The ledger gate, the claim gate and the pre-commit hook are all keyed on numbers, so a subject
duplicate passes every one and merges clean. Measured 2026-08-29: `#1303` and `#1360` carried
character-identical titles, five days and two worktrees apart.

`#1303` never filed a row, so it is invisible to any search of `docs/BACKLOG.md`. An unfiled
allocation exists only in the alloc records, which is why those are the thing to search.

### A filed row does not learn

A backlog row is a snapshot of what was true when it was written, and every screen reads it as
current. A ruling made after a row is filed never touches the row.

| Item | Rule |
| --- | --- |
| What to check | Before you act on filed work, ask whether a later ruling touches its subject. Start from the row's own filed date and match by subject, because no ruling cites a backlog number. |
| The ruling may live in another repository | For publishing or moving material, the decision lives where the material lives. Grep the vault's `docs/security/` for a decision naming the row's subject. |
| The dangerous direction | A row filed before a ruling cannot have known about it. A row filed after probably did. So the gap to check runs backwards from the row, not forwards. |
| Do not over-trigger | Default to NOT BLOCKED when unsure. Check whether the ruling was scoped to a pass or a batch that has since concluded. |

**Why the engine repo can look clean and still be wrong.** Nothing there need record that a vault
ruling exists.

**Why over-triggering is the expensive error.** A false collision takes a real row away from a
builder, and supply is this fleet's binding constraint.

## A row needs a diff. Otherwise write a rule

**A backlog row implies a change to the repository. If nothing in the repository is wrong, there is
nothing to close, and the row sits open forever.**

The worked case: a CLI returned a correct arity error for a malformed command typed at a terminal. The
CLI is right, the error is right, and the fault is in what a human typed. There is no diff. A rule
prevents the next one; a row would never close.

| Ask | Then |
| --- | --- |
| Is there a file whose contents are wrong? | File a row. |
| Is the code correct and the READING of it wrong? | Write a rule. |

**A future audit's findings are filed only once verified against the tree.** That covers an
external or an automated audit. An unverified finding stays in the audit's own record.

Ledger ruling R1, owner-signed 2026-11-04 (vault `docs/LEDGER-INFLOW-RULINGS.md`, PR 2818).
The audit rows already filed are not affected.

**A low-value row is filed deferred.** Ledger ruling R3, owner-signed 2026-11-04
(vault `docs/LEDGER-INFLOW-RULINGS.md`, PR 2818). It covers a row filed at value 2/10 or less that
describes no effect on a first deployment.

It must also touch no security record, register, control statement or ASVS content, hold no owner
question, and not be tied to an open build row. File it as `Verdict: demand-gate`, with the trigger
*"a change touches this row's code"*.

It stays open and numbered: deferring is not declining. A first-deployment defect is never deferred
under this rule, and "not yet deployed" is never the reason for a deferral.

---

## The backlog banner alphabet is the one holdout

Source of record: `docs/LEDGER-GATE.md`, the open-count control section.

| Item | Rule |
| --- | --- |
| Where it lives | Put a banner character only in `docs/BACKLOG.md` and `docs/archive/backlog/BACKLOG-CLOSED.md`. |
| Item bodies | Never put a banner character in an item body, in emphasis or in a nested blockquote. |
| Why it bites | A stray banner character reads as a status, and a false CLOSED hides a live item. |
| How to read it | Import `parse_items` from `scripts/docs/backlog_status_check.py`. Never write your own scan. |
| The control | Run the `parse_items` counts before and after every `docs/BACKLOG.md` edit, and diff them. |
| Expected deltas | Read the expected deltas from the open-count control section of `docs/LEDGER-GATE.md`. |

---
