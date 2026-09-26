---
name: "fleet-use-the-wiki"
description: "Query or write the fleet wiki. Use before acting on remembered facts and after a decision, fix, lesson or correction."
user-invocable: true
disable-model-invocation: false
---

# fleet-use-the-wiki

> The procedure for the fleet wiki. [WIKI.md](../../../roles/WIKI.md) is the schema and owns every
> rule this file applies. Prohibitions that bind before this task starts stay in
> [COMMON.md](../../../roles/COMMON.md). Read it first.

Run both scripts by path from a korus checkout at `origin/main`. Pass `-StateRoot <coord>`, the
engine clone's coordination directory on the reference fleet, every time, and `-RecordRepo <vault>` on a query. The default
state root is the wrong inbox or none.

WIKI.md, *Run them from korus by path, and name both stores*, names each placeholder.

### Query before you act on a fact you remember or were told

1. Name the subject in plain words, and the file if you are about to edit one.
2. Run the query:

   ```powershell
   pwsh -NoProfile -File <korus>/scripts/wiki/query.ps1 -StateRoot <coord> -RecordRepo <vault> `
     -Text "<subject words>" -Seat <your seat>
   pwsh -NoProfile -File <korus>/scripts/wiki/query.ps1 -StateRoot <coord> -RecordRepo <vault> `
     -Text "<subject words>" -Path <file> -Seat <your seat>
   ```

3. Act on each result as its label says. WIKI.md, *Query before you act on anything you remember*,
   holds the label table and the four reading rules.
4. Cite the id of every event you act on, as that section says.

### Write one event after a decision, a fix, a lesson or a correction

1. Query the subject first. Reuse the key you find, or name a new one by the rules in
   [WIKI.md](../../../roles/WIKI.md), *Name the key for the thing, never for the finding*.
2. Pick the type from WIKI.md, *Pick the type by what happened*.
3. Name the evidence by WIKI.md, *Evidence that counts, and what does not*.
4. Run the write. Add `-Supersedes <id>` when the event replaces or corrects one:

   ```powershell
   pwsh -NoProfile -File <korus>/scripts/wiki/write.ps1 -StateRoot <coord> -Type <type> `
     -Key <key> -Summary "<one line>" -Evidence "<evidence>" -Seat <your seat>
   ```

5. Record the id it prints in your report. On a refusal, follow WIKI.md, *The optional flags*.

**Never put PHI, a message body or a secret in an event.** WIKI.md, *What never goes in an event*,
holds the full list.
