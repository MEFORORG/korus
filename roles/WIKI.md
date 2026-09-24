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
| `scripts/wiki/query.ps1` | Searches the pages, the index and the uncompiled inbox. Every result passes the guard that hides superseded and retired events. |

**Run both from a worktree of the repository the fleet coordinates in**, the engine repository on
the reference fleet. Each clone has its own inbox, so a write from another clone lands where no
query looks. COMMON, *Your cwd, not your seat, decides which coordination record you touch*.

**If a script is missing from your tree, carry on without it and say so in your report.** A memory
that cannot be reached never blocks work.

**Compile, import and lint are not a seat's to run.** A scheduled Claude Code job runs
`compile.ps1`, the weekly `import.ps1` and `lint.ps1` (Owner ruling 2026-09-23).
[The plan](../specs/002-fleet-wiki/plan.md) orders their build.

The job opens pull requests and never merges them. The Lander lands the compile and import pull
requests in the record repository. A playbook change lint drafts merges only with the Owner, so
the Lander does not land it.

---

## Query before you act on anything you remember

```powershell
pwsh -NoProfile -File scripts/wiki/query.ps1 -Text "ascii gate exit code on windows"
pwsh -NoProfile -File scripts/wiki/query.ps1 -Text "exit code" -Path scripts/quality/check-ascii.ps1
```

| Flag | Use |
| --- | --- |
| `-Text <words>` | The subject, in plain words. |
| `-Path <file>` | Search by the file an event is about. Use it before you edit that file. |
| `-History` | Also return superseded and retired events, labelled `historical`. A superseded event points at its replacement; a retired one has none. |
| `-Limit <n>` | Cap the result count. |
| `-Json` | Machine-readable output. |
| `-StateRoot <dir>` | Read an inbox other than the default coordination directory. Tests use it. |
| `-RecordRepo <dir>` | Read pages from a record repository clone other than the default. |

Every result carries an id, a date, the writing seat, its evidence and one label.

| Label | Means | Before you act on it |
| --- | --- | --- |
| `inbox` | Written, not yet compiled | Judge its age by its date, as for the rows below. It can wait days for compile. |
| `fresh` | Under 14 days old | Act, and cite the id. |
| `aging` | 14 to 45 days old | Check the evidence still holds. |
| `stale` | 46 days or older | Re-measure against the tree first. |
| `historical` | Superseded or retired. Shown only with `-History` | Never act on it. |

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

```powershell
pwsh -NoProfile -File scripts/wiki/write.ps1 -Type gotcha -Key git/show/msys-dotpath `
  -Summary "git show ref:.dotpath returns empty under MSYS" -Evidence "<commit, PR, path@ref>" `
  -Seat <your seat>
```

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
| `-Trust generated\|verified` | `generated` by default. `verified` only when a person or a second seat confirmed it, never your own check. |
| `-Seat <seat>` | The seat writing the event. Pass it, because every event must record one. |
| `-StateRoot <dir>` | Write to an inbox other than the default. Tests use it. |

**A refused write blocks nothing.** Fix the cause it names, or name the refusal in your report and
carry on. Never reword an event to slip past the leak scan.

**A write is a shared write.** The Special seat runs its announce test before its first one.

---

## What never goes in an event

- **No PHI and no message bodies**, real or synthetic. Describe the shape, never paste the payload.
- **No secrets**: tokens, keys, passwords, connection strings.

The leak scan refuses a hit and names the class, never the value. It is a backstop, not the rule.

## The content lives in the record repository, never in korus

Events, pages and the index live in the adopter's private record repository. On the reference
fleet that is `MessageFoundry-vault`. korus holds the schema and the scripts only.

korus is public, and the events name accounts, branches and internal detail. Never paste an event,
a page or a query result into a korus file, pull request or issue. Cite an event id there only if
the id itself carries no private detail.
