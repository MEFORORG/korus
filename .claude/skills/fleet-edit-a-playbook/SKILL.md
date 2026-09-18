---
name: "fleet-edit-a-playbook"
description: "Read, edit or cite a file under roles/. Use before quoting a section, changing a playbook, or relying on a checkout of it."
user-invocable: true
disable-model-invocation: false
---

# fleet-edit-a-playbook

> Shared fleet rules, split out of [COMMON.md](../../../roles/COMMON.md) on 2026-09-05.
> Prohibitions that bind before this task starts stay in that file. Read it first.

### Korus is authoritative, and any checkout of it can still be stale

**Owner ruling 2026-09-17: `roles/` in `wshallwshall/korus` is the folder of record.** Read
`roles/<SEAT>.md` from there. Say in your output which copy you read.

    git -C <korus> show origin/main:roles/<SEAT>.md

**RETIRED 2026-09-17: this section named the VAULT's `roles/` folder.** It cited an owner ruling
(vault `5e361756`, restated in the engine `CLAUDE.md` 2026-08-28).

The playbooks moved to korus on 2026-09-04, at korus `5728484`. That move overtook the ruling. This
section did not follow it.

The vault copy last changed 2026-09-02. It now opens with its own banner: *"STOP. THIS COPY IS
STALE AND IS NOT THE ONE TO READ ... You were probably sent here by a stale pointer."*

**This section was one of those pointers.**

Naming korus does not certify that a korus checkout is current. One measurably is not.

**Measured 2026-09-17 on `C:\Users\Scott\Code\korus`.** The working checkout sits on branch
`fix/strip-account-vars-from-child-env`: 15 commits ahead of `origin/main`, and 46 behind. A seat
reading `roles/LANDER.md` there reads a file 46 commits stale. A directory listing cannot show it.

Check any copy with `git -C <korus> diff --stat origin/main HEAD -- roles/`. Empty means it matches
the ref. Non-empty is something to read, never a reason to switch copies blind.

**The earlier vault measurement is kept, because its shape still holds.** Measured 2026-09-01 from a
worktree sharing the vault primary's git directory: HEAD 39 commits behind `origin/main` and 4
ahead, `roles/` differing across 13 files.

`REVIEWER.md` was absent there and present on `origin/main`. That seat retired 2026-09-12, so its
card now sits under `roles/retired/`. `INSTRUMENTS.md` was present there and deleted on
`origin/main`.

**Two repositories, two checkouts, one failure.** The repository of record changes. The habit of
reading a working tree does not.

Fetch first, because `origin/main` is itself a cached ref, and `git worktree list` reports a
recorded HEAD rather than a working tree, so it cannot see uncommitted edits.

**RETIRED 2026-09-01.** This row previously read: *"Run `git show origin/main:roles/<SEAT>.md`
inside the `MessageFoundry-vault` clone, and never read that working tree."* It is recorded rather
than deleted. Seats still quote it, and its reasoning was correct.

The narrow scope survives: the ruling covers `roles/` and nothing else in that checkout.

### Quote a heading, never a position, and pin the ref before a long rewrite

**Never write a positional cross-reference in a file that grows by insertion.** A rule here once
said *"the consumer qualifier two rows up"*. It was true when written.

Twenty rows were then inserted above it, and "two rows up" came to point at a different row. That
row prints `grep -q` in monospace, so a reader obeying the pointer concludes the qualifier endorses
the consumer it forbids. **It punishes only the diligent reader; skimmers never follow it.**

Worse, while fixing that, the same seat wrote *"see the row below"* for a row it had not yet added.
That is a dangling pointer created in the act of repairing dangling pointers. **Quote the target's
heading. A heading survives insertion; an offset does not.**

**ASD-STE100 does not shorten a document. It makes sentences shorter and there are more of them.** Measured
2026-08-29 on a full STE rewrite of `roles/LANDER.md`:

| Metric | Before | After |
| --- | --- | --- |
| Lines | 4024 | 4110 (+2.1%) |
| Words | -- | +0.4% |
| Mean sentence length | 23.5 words | 16.5 words (-30%) |
| Sentences over 25 words | 599 (37.3%) | 381 (16.6%) |
| Semicolons | 223 | 15 |
| `has been` / `have been` | 9 | 0 |
| `would` | 82 | 14 |

**The file got longer. STE buys clarity, not brevity** -- it trades one long sentence for two short ones. If
the goal is a shorter file, STE is the wrong instrument and you must cut content instead. In this folder the
content is measurements, which is exactly what must not be cut.

**And a rewrite run against a ref that moves under it ships a retired rule.** The same run extracted
from `08438b2c`, and `aab88804` landed six minutes later, mid-run. Two of the eight parts were
written after that commit and still from the older extraction.

**Result: the output carried a retired routing rule and contained zero of the owner's new route.** A
governing rule, set that same day, silently reverted by a job that started before it. It was not
landed.

**Pin the ref at the start of a long multi-agent rewrite and re-check it at the end.** If
`origin/main` moved, the parts written after the move are not what they appear to be.

## Retired files, and citations that no longer resolve

**Where OUTPUT-STYLE.md went.** The output style had its own file in this folder until 2026-08-28.
Its text is now *Run in the Proactive output style*, carried over unchanged apart from its own
pointers, and `roles/OUTPUT-STYLE.md` is gone.

Every citation to it in `roles/` was repointed in the same commit. Read the retired file with `git
show b4ae252f:roles/OUTPUT-STYLE.md`.

**Where the old COMMON numbers went.** Role files on `origin/main` cite this document 61 times by
number, in 11 files. This document has no numbered headings that match them, so those citations no
longer resolve.

Read the retired text with `git show 236b1204:roles/COMMON.md`, the last version that carried the
numbering.

| Old number | Where the rule is now |
| --- | --- |
| `COMMON 4.x` | **The file is gone as of 2026-08-29.** Nine such citations remain live across this folder and are correct as written. Do not "fix" them by deleting them. |
| `COMMON 2.1` | *Coordinate before you write*, the push and merge rules. |
| `COMMON 2.2` | *Coordinate before you write*, the inherited claim and quoted doctrine rows. |
| `COMMON 2.10` | *The owner reads by sampling*, the Manager row. |
| `COMMON 2.11` | *The owner reads by sampling*, the recommendations row. |
| `COMMON 3.3` | *Coordinate before you write*, the match on the directory row. |
| `COMMON 3.4` | *One-line rules*, the past statement row. |
| `COMMON 5.3` | *This file holds only what never expires*, the *State it once* row. |
| `COMMON 5.7` | *Hand off so your successor can resume*, the derivation row. |
| `COMMON 5.9a` | *A usage number warns about lost work*, the report a stop row. |
| `COMMON 5.10` | *A usage number warns about lost work*, the whole section. |

**Where a `COMMON 4.x` or `INSTRUMENTS 4.x` citation resolves.** The instruments section moved to
`INSTRUMENTS.md` on 2026-08-22 and kept its numbering. That file was deleted on the owner's
instruction.

Such a citation still names a real entry, but it resolves to blob
`9a2f7a64a8802dab6d281665b4c9b05d5cf8eda2`, not to any file in this folder:

```
git -C <vault> cat-file -p 9a2f7a64a8802dab6d281665b4c9b05d5cf8eda2
```

**These are not carried, and the compression dropped them deliberately:** `2.1b`, `2.1y`, `2.12`,
`3.1`, `3.2`, `3.5`, `3.7` and `3.8`. A citation to any of them is dangling. Read it at `236b1204`,
then either restate the rule where it belongs or drop the citation.

Do not leave it pointing at a number this document does not define.

---

### Never assert a string's global absence in a document whose job is to discuss that string

Found by the Role Manager, with the general form from the Dispatcher, 2026-08-30.

These files quote the wrong citation, the retired command and the withdrawn wording. That is what makes
them useful. A probe of the form "the bad string is not in this file" is unsatisfiable in exactly the
files worth checking.

It also hides itself. Writing the correction adds occurrences of the string. A second seat running the
same grep gets a different number, and both counts are correct. Measured: 0 and 4 became 2 and 5, and
both new hits sat inside the block that recorded the zero.

Scope the control to the site, not the file. Assert on the citation you repaired. Or count occurrences
and expect the number you left behind. Or check that the enclosing heading resolves. **Read the matches
rather than quoting the count.**

---
