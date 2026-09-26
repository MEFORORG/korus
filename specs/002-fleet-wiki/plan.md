# Implementation Plan: The fleet wiki

**Branch**: `spec/002-fleet-wiki` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

**Input**: `specs/002-fleet-wiki/spec.md`

## Summary

Build one memory that every seat on every account can search, in six pull requests. The first
two deliver the P1 stories: write, guard, query, compile and the rebuild test. The rest add the
playbook, the weekly import, lint and optional viewers.

The method and scripts land in this repository. The content lands in the adopter's private record
repository, which is `MessageFoundry-vault` on the reference fleet.

## Technical Context

**Language**: PowerShell 7.3+ for the scripts. Python with `pytest` for the tests. Markdown for
pages and the playbook.

**Dependencies**: `git` and `pwsh` only. `scripts/security/scan_forbidden.py` is reused for the
leak check. No new package.

**Storage**: One JSON file per event. The inbox is `<coord>/wiki/inbox/`. The log is
`wiki/events/<yyyy>/<mm>/<id>.json` in the record repository. Pages are `wiki/pages/<key-prefix>.md`.

**Testing**: `pytest`, calling each script through `pwsh`, in the shape `tests/test_seat.py` uses.
Every test that can return zero carries a planted control.

**Target platform**: Windows 11 first, which is the reference fleet. Linux on the `gates` matrix.

**Scale**: About 964 notes to import, falling after merges. The index-and-grep design is sized
for a few hundred pages.

**Performance goals**: Write under 1 second (SC-003). Query under 2 seconds (SC-004).

## Constitution Check

| Article | How this plan meets it |
|---|---|
| II. Readings, not conclusions | Every query result carries its evidence and date. |
| IV. Name the condition not varied | The import reads only the Owner's list, and the report says which stores it read. |
| V. No rule manufactures its own evidence | The rebuild test and every lint check are proven by a planted control that must fire. |
| VI. A number names its instrument | The spec's counts each carry the command that produced them. |
| VIII. The roster is the Owner's | The import takes paths from the Owner and never globs for account roots. |
| IX. Claude Code first | `git` and `pwsh` only. `qmd` and Obsidian stay optional. |
| XI. A seat writes something down | The wiki is the artefact. No new relay seat. |
| XII. The shared write surface binds | One file per event, and one writer (compile) for pages. |
| XIII. Work goes through Claude Code | The scheduled cycle calls no model at all. Lint's promotion step, which needs one, runs as a Claude Code job, never as an API call. |

No violation needs justifying. Both Owner questions were answered 2026-09-23; the spec records them.

Amended 2026-09-26 by Owner ruling: the XIII row read "Compile and lint run as Claude Code jobs,
never as API calls". The operating system's scheduler now runs compile, lint and import through
`cycle.ps1`, with no model. Article IX still holds: the Windows task is one way to schedule the
cycle, and any scheduler that starts `pwsh` runs it.

## Project Structure

```text
specs/002-fleet-wiki/
  spec.md
  plan.md                 this file

roles/
  WIKI.md                 the schema: how to write, compile, query, lint (PR 3)

scripts/wiki/
  _event.ps1              shared: schema check, id, clock stamp, paths
  _guard.ps1              the one filter every read passes through
  write.ps1               the only write path (PR 1)
  query.ps1               search pages, index and inbox (PR 1)
  compile.ps1             inbox to log to pages to index (PR 2)
  import.ps1              weekly ingest of Owner-listed stores (PR 4)
  lint.ps1                report-only health check (PR 5)
  cycle.ps1               one scheduled run: import on its day, compile, lint (2026-09-26)
  register-cycle-task.ps1 registers the cycle with Windows Task Scheduler (2026-09-26)

tests/
  test_wiki_write.py
  test_wiki_guard_and_rebuild.py
  test_wiki_query.py
  test_wiki_import.py
  test_wiki_lint.py

docs/
  SCRIPTS.md              gains a row per new script, or its inventory test fails
```

In the record repository, one pull request per phase that needs it:

```text
wiki/
  events/<yyyy>/<mm>/<id>.json
  pages/<key-prefix>.md
  index.md
  log.md
```

## Build plan

Each step is one pull request and one Builder brief. A step starts only when the one before it
has merged.

### PR 1 - Write, guard and query (Stories 1 and 3, P1)

1. Write `_event.ps1`: the field list from FR-002, the type list from FR-003, the id format, and
   the UTC clock stamp.
2. Write `write.ps1`. Validate, run the leak scan, then write one file to the inbox. No git, no
   network.
3. Write `_guard.ps1`. Given a set of events, return the live set: newest per key, minus anything
   superseded or retired.
4. Write `query.ps1`. Search the inbox and any compiled pages, pass results through the guard,
   print each with id, date, seat, evidence and label. Print `no note` below the match floor.
5. Tests. A write lands in under 1 second. A secret is refused with the class named and no value
   printed. A missing evidence field is refused. A query from a second config root finds an inbox
   event. An unrelated query prints `no note`.
6. Controls. Plant a known secret and confirm the scan fires. Query a planted event and confirm it
   is found, so a later `no note` is armed.
7. Add rows to `docs/SCRIPTS.md`. Run `tests/test_prose_rules_hold.py` and the ASCII gate.

### PR 2 - Compile and the rebuild test (Story 2, P1)

1. Write `compile.ps1`. Move inbox events into `wiki/events/`, rebuild every page from the log,
   rebuild `index.md`, append one line to `log.md`, and open one pull request in the record
   repository.
2. Remove an inbox file only after the pull request carrying it has merged. A re-run adds nothing.
3. Test the rebuild. Plant A, supersede it with B, delete all pages, rebuild. Query A's own opening
   words: A absent, B present. With `-History`, A present and labelled `historical`.
4. Control for that test: run the same rebuild with the guard switched off. A MUST appear, or the
   test is not measuring anything.
5. Test two live events on one key: newer wins, and a conflict is recorded for lint.
6. Wire compile as a scheduled Claude Code job (Owner ruling 2026-09-23). It opens pull requests
   and never merges; the Lander lands them.

   Amended 2026-09-26 by Owner ruling: `scripts/wiki/cycle.ps1` runs compile, lint and the weekly
   import under the operating system's scheduler, with no model. `register-cycle-task.ps1`
   registers it on Windows. It still never merges.

### PR 3 - The schema playbook (all stories)

1. Write `roles/WIKI.md`: when to write, which type to pick, how to name a key, when to supersede,
   and the rule that a note loses to the tree.
2. Add one section to `roles/COMMON.md`: query before you act, write after, cite the id.
3. Add a `fleet-use-the-wiki` skill under `.claude/skills/`, in the shape of the other fleet
   skills.
4. Update the role cards that list arrival steps, so a query is one of them.

### PR 4 - Import the existing stores (Story 4, P2)

1. Write `import.ps1`. It takes an explicit list of directories and reads nothing else.
2. Turn each note into an event: `type` from the note's front matter, `key` from its name,
   `evidence` pointing at the source file.
3. Where two stores hold one name with the same text, keep one and write a merge event. Where the
   text differs, keep both and leave the pair for lint.
4. Test with two small planted stores. Control: a third store not on the list MUST NOT be read.
5. The Owner supplies the list. The import runs weekly on the compile schedule (Owner ruling
   2026-09-23), so re-running over an unchanged store MUST add nothing. Test that with a control.
6. A note changed since the last run adds a new event on the same key, superseding the old one.
7. The first pull request records the counts it printed and the command that printed them.

### PR 5 - Lint and promotion (Story 5, P2)

1. Write `lint.ps1`. Report live conflicts, dead evidence, orphan pages, stale events and lessons
   written by two or more seats.
2. It changes no event. It writes one report file and exits.
3. For a lesson seen by two or more seats, draft a pull request against the matching playbook. It
   never merges; the Owner decides.
4. Test each finding with a planted case, and a clean control log that MUST report zero.

### PR 6 - Optional readers (Story 6, P3)

1. Test that every link on every page resolves.
2. Write a short note in `roles/WIKI.md` on opening the vault's `wiki/` folder in Obsidian.
3. Write a note on adding `qmd` or `okf` as an optional search, with the rule that `query.ps1`
   stays the default and the guard still applies.

## What would stop this plan

- **The leak scan cannot read a JSON event.** Then PR 1 adds a thin adapter and says so.
- **The import finds far more conflicts than expected.** Then PR 4 lands the import and a lint
  pass is run by hand before PR 5.

## Complexity Tracking

None. The plan adds no service, no database and no new dependency.
