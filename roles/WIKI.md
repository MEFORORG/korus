# Fleet wiki schema: How every seat reads and writes shared memory

> **Read [COMMON.md](COMMON.md) first.** This file binds every seat, and it is not a seat of its
> own. The reasons, the research and the requirements are in
> [the fleet wiki spec](../specs/002-fleet-wiki/spec.md).
> [The mental model](../specs/002-fleet-wiki/mental-model.md) is the one-page picture.

The fleet wiki is one memory that every seat on every account can search. This file is its schema.

---

## Two scripts are the whole interface a seat touches

| Script | What it does |
| --- | --- |
| `scripts/wiki/write.ps1` | The only write path. Checks the fields, runs the leak scan, stamps the UTC time itself, drops one file in the inbox, and prints the new id. No git, no network. |
| `scripts/wiki/query.ps1` | Searches the uncompiled inbox and, with `-RecordRepo`, the compiled log. Every result passes the guard that hides superseded and retired events. |

### Run them from korus by path, and name both stores

The scripts exist only in korus. The engine repository has no `ccx.config.json`, so the default
state root does not resolve there: a write exits 2, and a query reports the state root unreachable.

With a korus cwd and no `-StateRoot`, a script uses korus's own coordination directory, which is
not the shared inbox. So pass every path yourself:

| Placeholder | What it names |
| --- | --- |
| `<korus>` | A korus checkout at `origin/main`. |
| `<coord>` | `<engine clone>/.git/mefor-coord` on the reference fleet: the engine clone's coordination directory, which holds the one inbox every account shares. In any engine worktree, `git rev-parse --path-format=absolute --git-common-dir` prints the `.git` part. |
| `<vault>` | A checkout of the record repository at `origin/main`, `MessageFoundry-vault` on the reference fleet. A query reads the compiled log from it; a write does not use it. |

```powershell
pwsh -NoProfile -File <korus>/scripts/wiki/write.ps1 -StateRoot <coord> -Type gotcha `
  -Key git/show/msys-dotpath -Summary "git show ref:.dotpath returns empty under MSYS" `
  -Evidence "<commit, PR, path@ref>" -Seat <your seat>
pwsh -NoProfile -File <korus>/scripts/wiki/query.ps1 -StateRoot <coord> -RecordRepo <vault> `
  -Text "ascii gate exit code on windows" -Seat <your seat>
```

Each clone has its own coordination directory, so its own inbox. `Get-CcxStateRoot` in
`scripts/coord/_common.ps1` says why.

**If a script is missing from your korus checkout, carry on without it and say so in your report.** A memory
that cannot be reached never blocks work.

**Compile, import and lint are not a seat's to run.** The operating system's scheduler runs
`scripts/wiki/cycle.ps1` once a day (Owner ruling 2026-09-26). The cycle compiles and lints daily
and imports weekly. It makes no model call and needs no app to be open.
[The plan](../specs/002-fleet-wiki/plan.md) orders their build.

**That paragraph read "A scheduled Claude Code job runs them" until 2026-09-26** (Owner ruling
2026-09-23). That job ran only while one desktop app was open, so the Owner moved the three plain
scripts to the operating system.

**Lint's promotion step is not part of the cycle.** Drafting a playbook pull request needs a model.
It stays a Claude Code job or a manual step, and it reads the report the cycle leaves in its lint
directory.

The cycle opens pull requests only through `compile.ps1`, and never merges one. The Lander lands the
compile pull requests in the record repository. A playbook change the promotion step drafts merges
only with the Owner, so the Lander does not land it.

Register the cycle once per machine with `scripts/wiki/register-cycle-task.ps1`. Pass `-WhatIf`
first: it prints exactly what it would register. `-Status` shows the task and the last log line.

**Register an old task again.** The first registrar left priority 7 and a one-hour limit; this one
sets 4 and two hours. `-Status` says OUT OF DATE until you do.

```powershell
pwsh -NoProfile -File <korus>/scripts/wiki/register-cycle-task.ps1 -KorusCheckout <korus> `
  -StateRoot <coord> -RecordRepo <vault> -ReaderRepo <vault reader> `
  -Store <store 1>,<store 2> -EvidenceRepo <engine>,<korus>,<vault> -LintOut <lint dir> -WhatIf
```

| Placeholder | What it names here |
| --- | --- |
| `<korus>` | A korus checkout used only by the task, on a detached `origin/main`. Each run moves it there. |
| `<vault reader>` | A second checkout of the record repository, on a detached `origin/main`. Import and lint read the log from it. |
| `<store N>` | Each account's memory directory the Owner listed. Name every one. |

The cycle refuses a checkout that is on a branch or has local changes. A machine that was off on the
import day imports at its next run. Each run appends a JSON line under `<coord>/wiki-cycle/`, a
refused run included. `cycle.ps1`'s header lists the exceptions and its exit codes.

---

## Query before you act on anything you remember

```powershell
pwsh -NoProfile -File <korus>/scripts/wiki/query.ps1 -StateRoot <coord> -RecordRepo <vault> `
  -Text "exit code" -Path scripts/quality/check-ascii.ps1 -Seat <your seat>
```

| Flag | Use |
| --- | --- |
| `-Text <words>` | The subject, in plain words. |
| `-Path <file>` | Search by the file an event is about. Use it before you edit that file. |
| `-History` | Also return superseded and retired events, labelled `historical`, and the import's `memory-merge/` records. A superseded event points at its replacement; a retired one has none. |
| `-Limit <n>` | Cap the result count. |
| `-Json` | Machine-readable output. |
| `-StateRoot <dir>` | The coordination directory that holds `wiki/inbox/`. Pass `<coord>`, never the inbox itself. |
| `-RecordRepo <dir>` | The record repository whose compiled log to search. Pass `<vault>`. Without it, only the inbox is searched. |
| `-Seat <seat>` | Your seat. It goes only into the query log. Without it the log takes your declared seat, then `$env:KORUS_SEAT`. |

Every result carries an id, a date, the writing seat, its evidence and one label.

**A word found only in an event's body counts half toward the match floor.** A word in the key,
summary or paths counts whole. So when you write, put the words a seat would search for in the key
or the summary.

A word in the key, summary or paths of more than half the events searched also counts half. It
tells one event from another no better than a body word does. The `memory` that starts every
imported key is one.

**Every query appends one line to a local log.** It goes to `<coord>/wiki/query-log/<yyyy-MM>.jsonl`,
by UTC month, as one JSON object per line. The line holds the time, the seat, the query text and
path, the result count, the top score, and whether it printed `no note`.

It also says whether the inbox and the log were reached, how many events were searched, and how
many import records a default query hid. So a `no note` over a store the query could not read does
not look like a real miss.

It shows whether seats query at all and what they miss. It stays on the machine: nothing compiles,
commits or sends it. A log that cannot be written is one line on stderr, and the query carries on.

| Label | Means | Before you act on it |
| --- | --- | --- |
| `inbox` | Written, not yet compiled | Judge its age by its date, as for the rows below. It can wait days for compile. |
| `fresh` | Under 14 days old | Act, and cite the id. |
| `aging` | 14 to 45 days old | Check the evidence still holds. |
| `stale` | 46 days or older | Re-measure against the tree first. |
| `historical` | Superseded or retired. Shown only with `-History` | Never act on it. |

Age counts from the day a fact was observed when the event records one, as an imported memory note
does. Such a result shows that day marked `(noted)`.

### Four reading rules

1. **Recall is advice, and the tree wins.** A note that disagrees with the tree, a live instrument
   or an Owner instruction loses. Act on the live reading, then write a `correction` that
   supersedes the note.
2. **`no note` means no note.** The query found nothing above its match floor. It is not a near
   miss, and it is not evidence that the thing is false. Proceed on your own reading.
3. **A memory miss never blocks work.** An unreachable store, a missing script and `no note` all
   mean the same thing: carry on.
4. **One way in.** Only `write.ps1` adds an event. Never create, edit or delete a file in the inbox,
   the log, the pages or the index by hand.

**Cite the event id whenever you act on a note.** Put it in the commit message, the pull request
body or the report, so a reader can check what you relied on.

---

## Write after a decision, a fix, a lesson or a correction

The write command is under *Run them from korus by path, and name both stores*. This section picks
its fields.

### Pick the type by what happened

| Type | Write it when | Evidence it usually carries |
| --- | --- | --- |
| `decision` | The Owner ruled, or a seat decided something later work must follow. | Owner ruling with its date, or the pull request. |
| `lesson` | You measured how something behaves. | The commit or `path@ref` where the reading was taken. |
| `gotcha` | A trap cost you time and will cost the next seat the same: a silent failure, a false zero. | The commit that shows it, or the fix. |
| `correction` | A note disagreed with the tree, and the tree won. Name the note in `-Supersedes`. | The commit or `path@ref` you read instead. |
| `supersede` | A new event replaces one or more older events, named in `-Supersedes`. | Whatever justifies the replacement. |
| `retire` | The thing a key describes is gone, and nothing replaces it. | The commit or ruling that removed it. |

**Do not write live state.** Current `main`, open pull request numbers and who is running now
belong in a dated episode note. An event should still be true next month, or carry `-StaleAfter`.

**Do not write what a playbook already says.** Search `roles/` and `.claude/skills/` first. A rule
already there needs no event.

### Name the key for the thing, never for the finding

A key is the stable name of what an event is about, such as `gate/ascii/windows-exit-code`.
Retirement works on keys, so the key decides which events compete.

- Lowercase, slash-separated, general to specific: `area/thing/aspect`.
- Letters, digits and hyphens between the slashes, and nothing else.
- Name the thing, not the verdict: `gate/ascii/windows-exit-code`, not
  `gate/ascii/exit-code-is-wrong`.
- One key per thing. Query before inventing one, and reuse the key you find.

**Two keys for one thing leave both live.** Within one key the newest live event wins. Across keys
nothing competes, and only lint will find the pair.

### Supersede, retire, or write fresh

| Situation | Do |
| --- | --- |
| Same thing, and the old event is now wrong | Write on the same key, a `correction` or a `decision`, and name the old id in `-Supersedes`. |
| One event replaces events under other keys, or merges several | `-Type supersede -Supersedes <id,...>`. |
| The thing is gone, and nothing replaces it | `-Type retire` on its key. |
| A different thing | A fresh key. |

Forgetting is done by adding an event, never by removing one. Two events on one key with no
`-Supersedes` between them still resolve to the newer, but lint files the pair as a conflict.

### Evidence that counts, and what does not

The write script refuses an event with no evidence. Evidence is one of four things:

- a commit SHA;
- a pull request, with its repository, because one number can name a pull request in several;
- a file path at a ref, written `path@ref`;
- an Owner ruling with its date.

A peer's message, a handoff and your own recollection are not evidence. Re-derive the fact from the
tree or an instrument, and cite what you read.

### The optional flags

| Flag | Use |
| --- | --- |
| `-Body <text>` | Detail the summary cannot hold. |
| `-Supersedes <id,...>` | The events this one replaces. Required for a `supersede`, and expected on a `correction`. |
| `-Paths <file,...>` | Files the event is about, so a query by `-Path` finds it. |
| `-StaleAfter yyyy-MM-dd` | The date after which the fact must be re-checked. A reader past it treats the event as `stale`, whatever its label. |
| `-Noted yyyy-MM-dd` | The day you observed the fact, when that was before today. Readers age the event from it. A future date is refused. |
| `-Trust generated\|verified` | `generated` by default. `verified` only when a person or a second seat confirmed it, never your own check. |
| `-Seat <seat>` | The seat writing the event. Pass it, because every event must record one. |
| `-StateRoot <dir>` | The coordination directory that holds `wiki/inbox/`. Pass `<coord>`, never the inbox itself. |

**A refused write blocks nothing.** Fix the cause it names, or name the refusal in your report and
carry on. Never reword an event to slip past the leak scan.

**A write is a shared write.** The Special seat runs its announce test before its first one.

---

## What never goes in an event

- **No PHI and no message bodies**, real or synthetic. Describe the shape, never paste the payload.
- **No secrets**: tokens, keys, passwords, connection strings.

The leak scan refuses a hit and names the class, never the value. It is a backstop, not the rule.

### Some events stay in your inbox and never reach the record repository

An event that names a customer, a site, a partner, a vendor or a worktree slug stays in the local
inbox. So does one that carries an email address, a user-home path or a routable IP address.
Compile holds it back (spec FR-028).

Writing one is still fine. It still answers a local query, labelled `inbox`, and it never reaches
the record repository. Compile scans it again on every run and reports only its id.

The record repository's own leak scanner decides the names. Its patterns are private, so korus
cannot list them. To make the lesson part of the compiled log, write it again without the name.

**A held `supersede` or `retire` withdraws nothing in the record.** The event it names stays live on
the pages, and compile warns. Write the marker again without the name.

## Optional readers sit beside `query.ps1`, never in its place

**Obsidian is a viewer, and no seat depends on it.** Open the `wiki/` directory of a `<vault>`
checkout as an Obsidian vault. It holds `wiki/pages/` and, beside them, the `index.md` that lists
every page.

Read there, never edit. A hand edit breaks reading rule 4, and compile replaces the page from the
log the next time it renders.

Obsidian writes its settings to `wiki/.obsidian/`. Open a checkout of your own rather than a shared
one, and never commit that folder.

**`qmd` or `okf` may add a search, and a seat still acts only on `query.ps1`** (FR-017). Only
`query.ps1` passes every read through the guard that hides superseded and retired events (FR-011).

A search over the pages misses the inbox, so a correction written today stays hidden from it until
compile lands. A search over `wiki/events/` returns what the guard would hide.

`okf`'s own search ignores status. [The spec](../specs/002-fleet-wiki/spec.md) records the reading,
under *Considered and not adopted: OKF Agent Memory as the store*.

## The content lives in the record repository, never in korus

Events, pages and the index live in the adopter's private record repository. On the reference
fleet that is `MessageFoundry-vault`. korus holds the schema and the scripts only.

korus is public, and the events name accounts, branches and internal detail. Never paste an event,
a page or a query result into a korus file, pull request or issue. Cite an event id there only if
the id itself carries no private detail.
