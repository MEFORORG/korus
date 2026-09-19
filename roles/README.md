# Role playbooks for parallel Claude Code sessions

> [Playbook size and format](https://claude-multisession.pages.dev/PLAYBOOK-SIZE.md) is the rule set
> this file is written to. [COMMON.md](COMMON.md) holds the rules that bind every seat, and this file
> names the seats. **List the `roles/` folder rather than typing a filename from memory** -- the seat
> set changes, and the table below is a snapshot of a moving set.

This folder holds one durable playbook per **seat** in MessageFoundry's parallel session setup. A
session in a given seat reads its own file on arrival, **instead of being hand-fed context**. That is
the whole point of the folder: the owner should not have to paste a briefing into a fresh window.

These files name internal process, gates, instruments and their failure modes, because the vault they
were written in is private. They still obey the project's writing rules. No glyphs or emoji, and no
present-tense claim that MessageFoundry is deployed, because it is a not-yet-deployed beta.

**This file carries no live state on purpose.** The open queue, item numbers, which PRs are armed,
who is blocked on whom and session names belong in a dated episode note. *These files carry nothing
that expires* states the split; *Episode notes live outside this folder* says where they go.

## 1. The seat set changed four times, nine seats have retired, and one was added

**Seven seats retired by owner decision on 2026-09-01: Dispatcher, Project Manager, Liaison, Cleaner,
Role manager, Process improvement and ASVS Tracker.** The Console took the Dispatcher's and the
Liaison's work. Nothing replaced the other five.

**The Console then retired on 2026-09-10, and the Manager took all three.** A Console reached across
every account and oversaw the whole build. That breadth did not work.

A Manager sits inside ONE account, and several run at once. So the plan, the brief and the owner's
questions all arrive at the same seat they did before, held by a smaller one.

**A ninth seat retired on 2026-09-12, and nothing replaced it.** Section 3 below was the open
question, and this is the answer to it.

**The owner added the Special seat on 2026-09-16, and it is the first addition rather than a
replacement.** It holds work that falls outside the other six, so no retirement made room for it.

It is also the only seat that stays silent on arrival. Owner-set: it reads [COMMON.md](COMMON.md),
stands by, and announces only when its instruction makes the message worth sending.

**Do not route work to a retired seat, and do not read a retired row as a live instruction.**

### 1a. The live seats

| Seat | File | What it owns |
|---|---|---|
| Manager | [MANAGER.md](MANAGER.md) | The plan and the brief. Reads the ledger, picks the row, writes a brief that holds for one turn, and reads what comes back. **Replaces the Dispatcher, the Liaison and the Console.** |
| | | **Opens the pull request and hands it to the Lander**, added 2026-09-18. Does not build, enqueue or merge. |
| | | Added 2026-09-04. Owner-spawned and bound to ONE account. Its workers are subagents or separate sessions. Several Managers run at once, sharing only the repository. |
| Builder | [BUILDER.md](BUILDER.md) | One brief, one turn. Takes the claim, builds, runs a code-review subagent over its own diff, commits, pushes, reports, then exits. **It no longer opens the PR**, changed 2026-09-18. |
| | | It never guesses at what the brief left open and never waits: it writes the question to the Manager, which carries it onto the PR, then stops. |
| Regulator | [REGULATOR.md](REGULATOR.md) | Decides whose failure a red is: the PR's, `main`'s, a flake, or the queue's. Only the PR's own failure becomes work. **It starts with no memory, so its log is not optional.** |
| Lander | [LANDER.md](LANDER.md) | **What enters the merge queue, and in what order.** Merge-forwards, made continuous by `strict: true` as `main` moves. The one-at-a-time ledger slot, since the queue builds each entry on the one ahead. |
| | | Handing back PRs needing a ruling. **Owns a handed-over PR from the handover on, and closes the item and releases the claim in one act**, added 2026-09-18. |
| Steward | [STEWARD.md](STEWARD.md) | **A cron, not a seat.** Zero model calls, so it needs no account. Reads usage and names the account with headroom. It cannot warn a running session, because nothing can interrupt one. |
| Special | [SPECIAL.md](SPECIAL.md) | **Work the owner wants done outside the other six.** Added 2026-09-16. It has no standing duties, so its instruction is its whole scope. |
| | | **The one seat that does not announce or declare on arrival.** Owner-set. It reads COMMON.md and stands by, then decides whether announcing helps once the instruction lands. |
| Watchdog | [WATCHDOG.md](WATCHDOG.md) | **Watches another seat work and files what it learns.** Added 2026-09-19. It does not do the work it watches, take its claim, or drive its lane. |
| | | **Not a renamed Regulator.** That seat attributes one red check and exits; this one observes over time and writes about the method. Its output is a finding on a shared page. |
| | | Drafted from the record of the first Watchdog session, and not reviewed by a Watchdog. The playbook's last section separates what was measured from what was inferred. |
| Not a seat | [COMMON-STAGED.md](COMMON-STAGED.md) | **Staging, not a playbook.** Sections split out of COMMON.md on 2026-09-05 that belong to one seat or fire never. Unedited, awaiting a destination. |
| Not a seat | [LANDER-ROUTED-OUT.md](LANDER-ROUTED-OUT.md) | **Staging, not a playbook.** Sections split out of LANDER.md on 2026-09-05 that belong to another seat. Unedited, and awaiting a destination. Do not read it as rules for any seat. |
| Every seat | [COMMON.md](COMMON.md) | The rules and instrument failures that belong to no single seat. **Read this first, whichever seat you hold.** |

### 1b. The retired seats keep their files so a reader finds them retired, not absent

| Item | Rule |
| --- | --- |
| Where they live | [retired/DISPATCHER.md](retired/DISPATCHER.md), [retired/PM.md](retired/PM.md), [retired/LIAISON.md](retired/LIAISON.md), [retired/CLEANER.md](retired/CLEANER.md), [retired/ROLE-MANAGER.md](retired/ROLE-MANAGER.md), [retired/PROCESS IMPROVEMENT.md](<retired/PROCESS IMPROVEMENT.md>), [retired/ASVS-TRACKER.md](retired/ASVS-TRACKER.md), [retired/CONSOLE.md](retired/CONSOLE.md), [retired/SEAT-RETIRED-2026-09-12.md](retired/SEAT-RETIRED-2026-09-12.md). Nine seats, nine files. |
| **RETRACTED 2026-09-04** | This table once called `ASVS-TRACKER.md` **absent from this edition**, on a `find . -iname '*asvs*'` returning zero files. True when measured. The file was then imported, and that command now returns the path above. |
| Why the rows survive | So a reader who remembers a seat finds it retired rather than missing. What each one did is in its own file, not summarised here. |
| Where their general rules went | Into [COMMON.md](COMMON.md), rather than lost with the seats. |
| Who answers an owner question now | The Manager. It is the only seat the owner talks to. |

### 1c. `INSTRUMENTS 4.x` and `COMMON 4.x` citations resolve to a blob, not a file

`INSTRUMENTS.md` was deleted 2026-08-29 on the owner's instruction. It held COMMON section 4,
"instruments that lie", **4,408 lines**.

Two ways to read it, both in the vault clone. The blob:
`git -C <vault> cat-file -p 9a2f7a64a8802dab6d281665b4c9b05d5cf8eda2`. Or the file's own history:
`git -C <vault> log -- roles/INSTRUMENTS.md`.

Live seats still cite it, so **do not delete those citations**. [COMMON.md](COMMON.md), *Where the old
COMMON numbers went*, owns the row.

## 2. COMMON owns the rules that bind every seat, and these files point rather than restate

Each row below names the COMMON heading that owns the rule. Cite a heading, never a section number:
COMMON has been renumbered, and a stale number resolves to the wrong rule silently.

| Item | Rule |
| --- | --- |
| A grant ADDS, it never narrows | When one arrives, ask whether you already hold more, not what the message covers. [COMMON.md](COMMON.md), *Standing rules that a fresh message will not override*, owns it. |
| A tick is a wakeup, not a message | It carries no instruction and expects no reply. **No seat sends an ACK for one**, acknowledges one, or produces a status line because one arrived. Same COMMON heading as the row above. |
| Every seat runs in the Proactive output style | [COMMON.md](COMMON.md), *Run in the Proactive output style*, is its single definition. **It changes disposition, not permissions.** Routing, the DEMAND-GATE pause and every approval gate bind as before. |
| A playbook that contradicts COMMON is an owner question | [COMMON.md](COMMON.md), *Where a role playbook and this file disagree*, owns it. No seat resolves the contradiction by picking a winner. |
| Why the seat files point rather than restate | Nine copies of a behaviour contract have no drift signal between them. This project has hit that defect repeatedly. Make a pointer, never a second summary. |

## 3. The review gate retired on 2026-09-04, and the seat it belonged to on 2026-09-12

**Owner decision, 2026-09-04.** `a reviewer has read this` is no longer a required status check on
`main`, and `.github/workflows/review-gate.yml` is deleted. Only `gates (ubuntu-latest)` and
`gates (windows-latest)` remain required. **An unlabelled PR merges.**

**ANSWERED 2026-09-12: the owner retired the seat, and nothing replaced it.** Its playbook is
[retired/SEAT-RETIRED-2026-09-12.md](retired/SEAT-RETIRED-2026-09-12.md). A PR now merges on its two
required gates, with no review step ahead of it.

**This paragraph read "Whether the Reviewer seat survives the loss of its gate is an owner question,
and this file does not answer it" from 2026-09-04 until 2026-09-12.** It was open for eight days, and
the answer closed it rather than the question expiring.

| Item | Rule |
| --- | --- |
| What routes a PR now | Push your own branch, open your own PR, and the Lander merges it. No seat reads the diff first. |
| **NARROWED 2026-09-18** | A Builder under a Manager pushes and reports; the **Manager** opens the PR and hands it to the Lander with five fields. Every other seat still opens its own. |
| So one seat IS notified now | The Lander, by the Manager, as a courtesy. It still polls: nothing pushes a PR to it. |
| The Lander still owns the merge | It holds its standing grant for it. |
| Handing work over needs no permission | It is the default action, and no seat asks. |
| **RETIRED 2026-09-12, the three-step route** | Two rows here read *"Create the PR and notify the Reviewer. It posts findings on the PR, or passes it to the Lander, which merges"* and *"the Reviewer finds waiting PRs itself"*. Owner-set 2026-08-29. No seat to notify now. |
| Findings on a PR are still worth reading | Any seat may post them, and the PR outlives the session that wrote them. What changed is that nobody waits for them. |
| **RETIRED 2026-09-04** | Three rows here told you to work the `reviewed` label: the gate was a required check, only a person adds it, and any seat may apply it. Following one now spends a turn on nothing. |
| **RETIRED 2026-08-31, and now stale from both sides** | Before that, this section read *"if no Reviewer seat is running, hand the PR to the Lander as before"*. Arming the gate killed that fallback. Retiring the gate restored it. Retiring the seat made it the only route. |
| What the retired gate leaves behind | A lesson about a check that invalidates on its own run. [COMMON.md](COMMON.md), *Your pull request has to survive your own exit*, owns it. |

## 4. A rename is scoped to the seat name, and a blanket replace rewrites that name's history

### 4a. The four recorded renames

| Date | Rename | Commit | What it cost |
|---|---|---|---|
| 2026-08-13 | Coordinator becomes **Lander** | -- | Scoped to the seat name. `scripts/coord` paths and the verb "coordinate" were guarded and asserted unchanged. |
| 2026-08-13 | ASVS Monitor becomes **ASVS Tracker** | -- | Same scoping. The ordinary word "monitor" was guarded, because a rename that edits the surrounding English changes meaning silently. |
| 2026-08-26 | `ROLE-PLAYBOOKS.md` becomes `PLAYBOOKS-MANAGER.md` | `604fb623` | **Recorded nowhere until 2026-08-28.** The Process improvement seat noticed the two renames above were recorded and this one was not. |
| 2026-08-29 | `PLAYBOOKS-MANAGER.md` becomes [ROLE-MANAGER.md](retired/ROLE-MANAGER.md) | `befdc79a` | Owner-set, to stop the collision with the Project Manager seat. Both abbreviated to PM and both were being addressed as "the manager". |

### 4b. An `R100` pure rename carries none of its own references

The 2026-08-26 rename moved **zero content**, which is why it could not carry its references.
**Seven citations were left pointing at the retired name**, this file's seats-table row among them.

Every section they cited still existed, so nothing errored and **every grep read clean**. Repaired at
`1f0daff6`, with zero occurrences of the retired name left in this folder.

### 4c. A blanket replace corrupted the history of the name it was renaming

The 2026-08-29 rename updated **35 references across 8 files**. Controls: 35 occurrences of the
retired name before and 0 after, and 0 occurrences of the new name before, so nothing unrelated was
folded into this seat.

It then failed in a way the three earlier renames did not. The pass corrupted the very paragraph
recording the 2026-08-26 rename. That paragraph came to say the third rename produced
`ROLE-MANAGER.md`, which is false.

The error was **unfalsifiable from inside the file**, because by then every name in the sentence was
a real one. The seat that broke it repaired it in the same window.

**A file recording the history of a name must be edited BY HAND during a rename of that name, never
by a global substitution.** The three earlier renames escaped this only because nobody had written
their history down yet.

### 4d. Three kinds of occurrence stay unswept, on purpose

The 2026-08-29 sweep left three things alone. The owner's own rulings of 2026-08-13 and 2026-08-22
and the Steward's, which are quoted verbatim and say "Role playbooks". This file's H1, which names the
**folder** and not the seat. And a quoted table label inside an INSTRUMENTS entry.

**A rename that edits a quoted ruling has changed what the owner said.**

The seat's own name was settled by an owner ruling, 2026-08-28, in one line: *"You are Playbooks
Manager"*. Until then the H1 read "ROLE PLAYBOOKS seat" while the file, the handoffs and `seat.ps1`
all said `role-manager`.

The seat holding the single-editor rule did not settle its own name. It flagged both as live and
asked.

### 4e. The check after any seat rename has two arms

Run both. Arm one: every link in this file resolves, **11 of 11 at `befdc79a`**. Arm two: zero
occurrences of the retired name remain outside a history block.

**Run the second arm with a control token that must return zero**, or a broken grep reads as a clean
folder.

### 4f. Do not reuse a retired seat name for a new seat

The owner-queue seat added later was going to be called the Coordinator. It was named the **Liaison**
instead, precisely to avoid reusing a retired name.

Reuse would have made one word denote two seats sharing no duties, against roughly **182 historical
occurrences** that could not be swept. Those are records of what a session did on a given night.
Rewriting them would falsify the record to tidy a name.

A distinct name costs nothing, and the ambiguity would have been permanent.

**Expiry for the Coordinator note specifically:** delete it once no artifact a session is likely to
read still uses the old name. Until then, if a peer refers to the coordinator, they mean the Lander.

## 5. The single-editor rule retired with its seat, and a folder-wide sweep replaced it

**RETIRED 2026-09-01.** This section once opened *"WHILE A ROLE MANAGER SESSION IS RUNNING, IT IS THE
ONLY SESSION THAT EDITS THESE FILES"*, and sent every fix there instead, however small.

The owner retired the Role Manager seat on 2026-09-01 and **nothing replaced the folder-edit gate**.
No session holds this folder, and there is no seat to send a change request to.

Owner ruling, 2026-08-13, in these words: *"The Role playbooks session should be the only session
currently editing the playbooks. There won't always be a Role playbooks session, so this isn't a
law... just a current rule."*

**That ruling is kept as the record, and its own expiry condition has fired.** The owner wrote it as
conditional on a Role playbooks session running, then retired that seat.

| Item | Rule |
| --- | --- |
| **What survives, and it still binds** | **Do not fix a defect here in only the file you opened.** Sweep the whole folder for the same defect before you commit. **Say in the commit message what you swept for.** |
| Why the sweep is the control now | Concurrent edits to one file conflict loudly and get resolved. An edit that **invalidates a claim in a file you never touched** merges clean, with no marker. |
| What that cost, measured | **Three times in one evening across two repositories.** A single writer was the only thing that reliably caught it, and nothing replaced it. |
| What could restore a folder-edit gate | The owner saying so, or the folder getting a gate that makes concurrent edits safe. The original ruling named both. A peer cannot lift a rule here, and neither can a work assignment from another seat. |
| **RETIRED 2026-09-01** | This section previously said *"So it is conditional. Check whether one is live (`list_sessions`) before concluding you may not fix something."* Do not run that check to settle this. |
| The instrument warning is kept because it generalises | `list_sessions` **cannot see a VS Code session**, so it returns "not found" for a session that is running. Under the retired rule that false negative **lifted a prohibition** rather than merely costing you a question. |
| An absent seat and a retired seat render identically there | So never settle a retirement with `list_sessions`. When a liveness question actually blocks you, the liveness fence is `scripts/coord/session-registry.ps1`; otherwise ask. |
| **RETIRED 2026-09-01** | This section previously ended *"if you still cannot tell, ASSUME ONE IS RUNNING and send a change request."* No standing single editor exists to receive one, so that default would block every edit and reach nobody. |
| A dangling pointer, named rather than repeated | The retired text cited COMMON, *"the liveness check fails dangerously here"*. Measured 2026-09-04: that heading is **not in this edition's COMMON.md**. The finding above stands on its own; the pointer does not resolve. |

## 6. Send the measurement; wording is optional and gets verified anyway

The best material here came from seats reporting what executing a playbook did. The Builder whose
arrival battery found a row that could not answer its own question. The Dispatcher that found COMMON
unreachable by its own rules. The Liaison that found its own seat unreachable from every other file.

**Report the measurement and what it cost you.** You do not have to propose wording.

When you do propose wording, it is a claim like any other. It gets verified before it lands, and
several have not survived that. Send the measurement alongside it so the check is cheap.

Do **not** write a second, thinner summary of a seat somewhere else. Two documents describing one role
have no drift signal between them. If you want a short pointer elsewhere, make it a pointer. A summary
goes stale silently, where a pointer cannot.

## 7. Episode notes live outside this folder, in a directory you derive

Episode notes are deliberately **not** in this folder, because they expire and these files do not.

| Item | Rule |
| --- | --- |
| Where they belong | Wherever the seat holding them keeps them. For any lane, a durable handoff under `<git-common-dir>/mefor-coord/handoffs/` is the better home. That directory is shared across every worktree on the clone and survives any one session's tree. |
| A scratchpad is the wrong place | A session scratchpad does not survive. Never put there anything another session may need. |
| **Derive the directory, never type it** | `git rev-parse --path-format=absolute --git-common-dir`. |
| Why the bare form fails silently | From a worktree `.git` is a **file**, not a directory, so the bare `.git/...` form resolves against your cwd and lists **nothing**. That empty listing is what the failure looks like, not what "no handoffs" looks like. |

## 8. These files carry nothing that expires; a dated episode note carries live state

**A playbook here states what will still be true after the current queue drains.**

| Item | Rule |
| --- | --- |
| What goes in the EPISODE note, never here | The open queue, current item numbers, which PRs are armed or held, unpushed SHAs, who is blocked on whom, "pick up here" lists, and anything with a session name in it. |
| What goes HERE | A lesson still true after the queue drains: a trap, an instrument that lies, an ordering rule, a boundary of a gate, a measured mechanism. |
| Why the split is load-bearing | A mixed document decays into a **trusted** document that is **wrong**, and the durable half hides it. |
| First measured instance | A standing "DO NOT INSTALL" instruction, correct when written and repeated in bold at the top of the file, **inverted** when the held fix merged, with nothing in the document able to tell. |
| Second measured instance | A "no new lanes" freeze, recorded as an owner directive and cited back twice as authority, which had never been issued. |
| State it once | State a load-bearing fact once and link to it. A fact restated in three places is corrected in one. |
| Every prohibition carries its expiry | Write beside it what would have to become true for it to stop being right, and how to check. A prohibition without one becomes permanent by default. |
| Retract in place | Keep the wrong version and why it was wrong. Several sections here are more useful for recording an error than they would be stating only the right answer. Delete the error and the next session re-derives it. |
