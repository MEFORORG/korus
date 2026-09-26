# Feature Specification: The fleet wiki, one memory every seat can search

**Feature Branch**: `spec/002-fleet-wiki`

**Created**: 2026-09-22

**Status**: Draft

**Input**: Owner request, 2026-09-22: adopt the "agent memory" pattern from a practitioner's
write-up and from Karpathy's LLM Wiki idea file, and specify the best way to build it for KORUS.

---

## Why this exists

Every seat starts blank. What a seat learns lands in its own account's memory directory, and no
other account can read it.

Measured 2026-09-22 on the reference fleet, with `ls <root>/projects/<project>/memory | wc -l`
over each of the six config roots the Owner runs: 193, 152, 125, 83, 280 and 131 files. That is
964 files in six stores that never meet.

190 file names occur in more than one store. Instrument: `ls` over all six directories, `sort`,
`uniq -c`, rows with a count above 1. So the same lesson is learned, or copied by hand, again and
again.

Control for that count: the index file `MEMORY.md` is present in all six stores and returned a
count of 6, so the pipeline was live.

The memory tool also edits or deletes a note in place when it turns out wrong. A retired fact
leaves no trace, and no test can show that a retired fact stays retired.

### What the outside record says

| Source | Finding this spec uses |
|---|---|
| Karpathy, *LLM Wiki* idea file, 2026-04-04 | Three layers: raw sources that never change, a wiki of pages an LLM keeps current, and a schema that tells it how. Three jobs: ingest, query, lint. An `index.md` suffices to a few hundred pages. |
| *Revoked but Still Authoritative*, arXiv 2609.08258 | Five memory systems tested. None hid a revoked fact by default; the revoked fact often outranked its replacement. Fix: a guard between agent and store that withholds revoked records. |
| *Temporal Validity in Retrieval Memory*, arXiv 2606.26511 | Embedding similarity cannot tell a contradiction from a rewording (AUROC 0.59). A deterministic rule keyed on the fact retired stale values and cut stale answers from 15-40% to about 0. |
| Practitioner write-up, "MEMORYOS", 2026-09 | An append-only log is the truth and any index is a copy. Supersede by appending a marker, because a rebuild from the log resurrected all 17 superseded events when the flag lived only in the index. |

None of these was re-measured here. They are readings from the named sources, and Article II
applies: a reader should check them rather than trust this table.

---

## The shape, in one table

| Layer | Holds | Lives in | Written by |
|---|---|---|---|
| Inbox | New events, one file each, not yet compiled | The shared coordination directory | Any seat, through one script |
| Event log | Every event ever accepted, append-only | The private record repository, `wiki/events/` | The compile job only |
| Pages | One page per topic, rebuilt from the log | The private record repository, `wiki/pages/` | The compile job only |
| Index | One line per page | `wiki/index.md` beside the pages | The compile job only |
| Schema | How to write, compile, query and lint | This repository, `roles/WIKI.md` | A pull request |

**The content never enters this repository.** KORUS is public and the memory names accounts,
branches and internal detail. This repository holds the method and the scripts; each adopter keeps
the content in its own private repository.

**A write never waits on git.** A seat drops one file in the inbox and moves on. The compile job
later folds the inbox into the log and the pages through a pull request, like any other change.

**One file per event is the contention answer.** Article XII says the shared write surface is what
binds. Two seats writing at once create two files, so they cannot conflict.

---

## User Scenarios and Testing *(mandatory)*

### User Story 1 - A seat checks the record before it acts (Priority: P1)

A Builder is about to fix a gate that fails on Windows. It runs one query, and gets back the three
events that name that gate, each with its date, its writing seat, its evidence and an age label.

**Why this priority**: This is the whole return on the feature. Nothing else pays until a seat
can ask and get a cited answer.

**Independent Test**: Seed the log with ten known events, run the query, and check that the
expected three come back in order with every field filled.

**Acceptance Scenarios**:

1. **Given** an event keyed `gate/ascii/windows-exit-code`, **When** a seat queries "ascii gate
   exit code on windows", **Then** that event is returned with id, date, seat, evidence and label.
2. **Given** no event on the subject, **When** a seat queries "best pizza in Atlanta", **Then** the
   query says `no note` and exits 0, and it returns no nearest-match filler.
3. **Given** the record repository is unreachable, **When** a seat queries, **Then** the query says
   so on one line and exits 0, so the seat proceeds.

---

### User Story 2 - A retired fact stays retired, including after a rebuild (Priority: P1)

The Owner replaces a ruling. A seat writes a `supersede` event naming the old event. From then on
no default query returns the old event. A rebuild of every page from the log gives the same result.

**Why this priority**: The research above found this is where memory systems fail, and a
resurrected ruling is worse than no memory. It ships with Story 1 or the feature does not ship.

**Independent Test**: Plant an event, supersede it, delete the pages, rebuild, and query with the
old event's own opening words. The old event must be absent by default and present with `-History`.

**Acceptance Scenarios**:

1. **Given** event A and event B with `supersedes: A`, **When** a seat queries A's own text,
   **Then** A is not returned and B is.
2. **Given** the same pair, **When** the pages are deleted and rebuilt from the log, **Then**
   scenario 1 still holds.
3. **Given** the same pair, **When** a seat queries with `-History`, **Then** A is returned
   labelled `historical`, with a pointer to B.
4. **Given** two live events on one key with no supersede, **When** compile runs, **Then** the
   newer stays live and lint gets a conflict.

---

### User Story 3 - A lesson learned on one account reaches every account (Priority: P1)

A seat on one account finds that `git show ref:.dotpath` returns empty under MSYS. It writes one
event. A seat on another account queries the same subject within the hour and gets that event.

**Why this priority**: The six-store split measured above is the defect this feature exists to
remove.

**Independent Test**: Write an event from one config root, query from a second, and check the
event arrives before any compile has run.

**Acceptance Scenarios**:

1. **Given** an event written to the inbox and not yet compiled, **When** a seat on another account
   queries its subject, **Then** the event is returned, labelled `inbox`.

---

### User Story 4 - The existing memory stores are folded in, and kept in step (Priority: P2)

The Owner names the memory directories to import. A weekly ingest turns each note into an event,
merges notes that share a name and a meaning, and records every merge in the log.

**Why this priority**: The fleet already holds 964 notes. Starting empty throws them away.

**Independent Test**: Ingest two stores holding one shared name. Check that one live event results
and the log carries the merge.

**Acceptance Scenarios**:

1. **Given** the Owner's list of directories, **When** the ingest runs, **Then** it reads those
   directories only and never searches for others.
2. **Given** two notes with the same name and different text, **When** they are ingested, **Then**
   the note with the newer file date is the one live event on the key, the other is recorded as
   outranked, and lint files no conflict. On one date, the store listed first wins, unless the
   other note's event already holds the key.
3. **Given** a note whose text is unchanged since the last ingest, **When** only its file date has
   moved, **Then** the ingest writes nothing.

Scenario 2 amended 2026-09-26: it read "both are kept, and lint files the pair as a possible
conflict". The newer event then won by the order the ingest read the stores, not by which note was
newer. Scenario 3 was added the same day.

---

### User Story 5 - Lint finds conflicts and stale claims, and decides nothing (Priority: P2)

On a schedule, lint reads the log and reports four things. Live events that conflict. Events whose
evidence no longer exists. Pages nothing links to. Lessons written by two or more seats.

**Why this priority**: The gate on compile catches duplicate keys. Only lint catches two keys that
say opposite things.

**Independent Test**: Plant one of each finding. Lint must report all four, and must report zero on
a clean control log.

**Acceptance Scenarios**:

1. **Given** a planted conflict, **When** lint runs, **Then** it reports the pair and changes no
   event.
2. **Given** a lesson written by two or more seats, **When** lint runs, **Then** it drafts a pull
   request against the right playbook for the Owner to approve or close.

---

### User Story 6 - The Owner reads the wiki like a website (Priority: P3)

The Owner opens the vault's `wiki/` folder in Obsidian or any Markdown viewer and follows links
between pages. It opens `wiki/` rather than `wiki/pages/` because `index.md` sits there.

**Why this priority**: Useful and cheap, but no seat depends on it.

**Independent Test**: Every link on every page resolves to a page that exists.

---

### Edge Cases

- **Two seats write the same key in the same second.** Two files arrive. Compile orders by the
  event's clock time, then by id, and files a lint conflict. It never drops either.
- **An event carries a secret or a message body.** The write script refuses it before any file
  exists, and names the class it matched, never the value.
- **An event's evidence names a pull request that later closed unmerged.** Lint labels the event
  `evidence-dead` and does not retire it; a person decides.
- **A seat writes with a clock stamp it guessed.** The write script stamps the time itself. The
  seat cannot supply one.
- **The compile job dies halfway.** The inbox file is removed only after the pull request carrying
  it has merged. A re-run is a no-op for events already in the log.
- **The inbox is not reachable** (the seat runs outside any clone). The write fails loudly with the
  path it tried, and exits non-zero. A silent drop would be worse than no memory.

---

## Requirements *(mandatory)*

### Functional Requirements

**Writing**

- **FR-001**: There MUST be exactly one way to add an event: `scripts/wiki/write.ps1`. Every other
  script reads.
- **FR-002**: An event MUST carry: `id`, `ts`, `type`, `key`, `seat`, `summary`, `evidence`.
  `body`, `supersedes`, `paths` (files the event is about), `stale_after` and `noted` are
  optional. `trust` is `generated` unless a person or a second seat confirmed it, then `verified`.
  `noted` is the day the fact was observed, `yyyy-MM-dd`, and never later than the day of `ts`. The
  ingest sets it from a note's file date. Amended 2026-09-26 to add `noted`.
- **FR-003**: `type` MUST be one of `decision`, `lesson`, `correction`, `gotcha`, `supersede`,
  `retire`. An unknown type is refused.
- **FR-004**: `ts` MUST be read from the system clock by the write script, in UTC.
- **FR-005**: `evidence` MUST name a commit, a pull request, a file path at a ref, or an Owner
  ruling with its date. An event with no evidence is refused.
- **FR-006**: The write script MUST run the existing leak scan over the event before writing it,
  and refuse on any hit.
- **FR-007**: A write MUST complete without a network call and without any git operation that
  writes. Resolving the default state root MAY read git metadata (`git rev-parse`). With
  `-StateRoot` given, a write MUST make no git call at all.

**Retiring**

- **FR-008**: An event MUST never be edited or deleted once it is in the log.
- **FR-009**: A `supersede` event MUST name the event or events it replaces. A `retire` event
  withdraws a key with no replacement.
- **FR-010**: Within one `key`, the newest live event wins. Retirement is decided by key and by
  explicit supersede, never by text similarity.
- **FR-011**: Every read path MUST pass through one guard that withholds superseded and retired
  events unless `-History` is given.
- **FR-012**: Pages MUST be rebuildable from the log alone, and a rebuild MUST give the same live
  set as the pages it replaces.

**Querying**

- **FR-013**: `scripts/wiki/query.ps1` MUST search the event log and the uncompiled inbox, through
  the guard. Pages and the index are for people. Amended 2026-09-24: this read "the pages, the
  index and the uncompiled inbox", but the built query reads events, which the guard can filter.
- **FR-014**: Every result MUST show id, date, seat, evidence and one label: `fresh` (under 14
  days), `aging` (14 to 45), `stale` (46 or more), `historical` (retired), or `inbox`. Age counts
  from `noted` when the event has one, else from `ts`, and the date shown is that day. Amended
  2026-09-26: age counted from `ts` alone, so an imported July note read `fresh` in September.
- **FR-015**: A query with no result above the match floor MUST print `no note` rather than the
  closest miss.
- **FR-016**: A query that cannot reach the store MUST say so and exit 0. A memory miss never
  blocks work.
- **FR-017**: Query MUST work with `git` and PowerShell alone. A search engine such as `qmd` MAY
  be added as an enhancement and MUST NOT be required (Article IX).

**Compiling and linting**

- **FR-018**: Only the compile job writes the log, the pages and the index, and it writes them
  through a pull request in the record repository.
- **FR-019**: Compile MUST be idempotent: running it twice on the same inbox adds nothing the
  second time.
- **FR-020**: Lint MUST report and MUST NOT change an event.
- **FR-021**: Lint MUST find: live conflicts, dead evidence, orphan pages, and lessons written by
  two or more seats.
- **FR-022**: A playbook change drafted by lint MUST arrive as a pull request, and MUST NOT merge
  without the Owner.
- **FR-028**: Compile MUST hold back each pending event that the record repository's own leak
  scanner flags, or that carries an email address. Added 2026-09-24.

  A held event stays in the inbox. It is never filed or rendered, it still answers a local query,
  and each compile scans it again. The report names held ids and counts, never a scanner line.

  The hold fails closed. No scanner at Base, no python, or a scanner result it cannot read stops
  compile with exit 2, and nothing is filed or pushed.

  Why: the vault's publish leak gate held the first compile. Vault BACKLOG #1522 treats a real
  customer name as a leak in any folder, so an event naming one can never land there.

**Importing**

- **FR-023**: The ingest MUST read only directories the Owner lists by path. It MUST NOT discover
  account roots by pattern (Article VIII).
- **FR-024**: Every merge the ingest makes MUST be recorded as an event.
- **FR-027**: The ingest MUST run weekly on the schedule that runs compile, and MUST be idempotent
  over an unchanged store.

**Reading rules for seats**

- **FR-025**: A note that disagrees with the tree, a live instrument or an Owner instruction loses.
  The seat acts on the live reading and writes a `correction` event.
- **FR-026**: A seat MUST cite the event id when it acts on a note.

### Key Entities

- **Event**: One accepted fact, lesson or ruling. Immutable. Identified by `id`.
- **Key**: A stable name for the thing an event is about, such as `gate/ascii/windows-exit-code`.
  Retirement works on keys.
- **Page**: A readable rollup of the live events under one key prefix, with links to related pages.
  Always rebuildable.
- **Guard**: The one filter every read passes through. It hides what is retired.
- **Inbox**: Uncompiled events waiting in the coordination directory.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A rebuild from the log hides 100% of superseded events. The test plants at least
  one, and a control rebuild with the guard disabled MUST show it, so the zero is armed.
- **SC-002**: After the import, zero live keys are held by two events that say the same thing.
  Baseline: 190 duplicated names across six stores.
- **SC-003**: A write returns in under 1 second on the reference machine.
- **SC-004**: A query over the imported corpus returns in under 2 seconds.
- **SC-005**: An event written from one config root is returned to a query from another before
  any compile runs.
- **SC-006**: Over the first 30 days, at least one lint finding leads to a merged playbook pull
  request. If none does, the promotion loop is reviewed.

---

## Assumptions

- The adopter has one private record repository beside its main repository. On the reference fleet
  that is `MessageFoundry-vault`.
- The coordination directory already crosses accounts under one operating-system user.
  `roles/COMMON.md` measured this, and this spec relies on it rather than re-proving it.
- The existing account memory directories stay in place during the import. Retiring them is a
  separate decision.
- No PHI and no message bodies ever enter the wiki. The leak scan is a backstop, not the reason.

---

## Owner rulings, 2026-09-23

1. **A scheduled Claude Code job runs compile and lint.** It opens pull requests in the record
   repository and never merges them; the Lander lands them. No new seat.
2. **The per-account memory tool stays on, and the import re-runs weekly.** So the import MUST be
   idempotent: a note already imported, unchanged, adds no event. A changed note adds a new event
   on the same key, which supersedes the old one.

---

## Considered and not adopted: OKF Agent Memory as the store

`okf-memory/okf-agent-memory` is the closest ready-made tool. It keeps memory as Markdown in git,
searches it with BM25, and serves it over MCP. It is MIT-licensed and ships a Windows binary.

**It fails FR-011, the one requirement the research says matters most.** Read at its default
branch on 2026-09-22, shallow clone: `grep -c -i -E 'status|deprecat' pkg/okf/search.go` returns 0.
Control, same file: `grep -c -i score` returns 27, so the file was read.

So search never looks at a concept's `status`. A concept marked `deprecated` is still returned, and
can outrank its replacement. That is the failure arXiv 2609.08258 measured in five other systems.

**It retires by editing in place.** Its own usage text shows
`okf update decisions/adr-001 --status deprecated`. That breaks FR-008, and a rebuild cannot
recover what the old text said.

**One file per concept, edited by every writer, is the contention shape Article XII warns about.**
Two seats updating one concept conflict at merge.

**It is young and has one main author.** Created 2026-09-05, release v0.4.2 on 2026-09-19. The
contributor list shows one account with 131 commits and no other human above 4. Instrument:
`gh repo view` and `gh api .../contributors`.

**It would add a Go binary as a required dependency.** Article IX allows another tool only as an
enhancement.

**What this spec borrows from it:** the `stale_after` date, and the split between `generated` and
`verified` trust. Also search by file path (`okf search --for-path`), for a seat about to edit one
file.

Pages SHOULD keep front matter close to OKF v0.2, so `okf` could later read them as an option.

**Revisit if** its search starts filtering on `status` and it gains a second active maintainer.

---

## Out of scope

- A vector database or an embedding service. The index plus `git grep` covers a few hundred pages,
  which is where Karpathy's own guidance puts the limit.
- Obsidian as a requirement. It is one possible viewer and nothing depends on it.
- Any change to how the engine repository stores its ledger.
