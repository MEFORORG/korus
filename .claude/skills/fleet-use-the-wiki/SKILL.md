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

Stand in a worktree of the repository your fleet coordinates in before either command. Each clone
has its own inbox. WIKI.md, *Two scripts are the whole interface a seat touches*, says why.

### Query before you act on a fact you remember or were told

1. Name the subject in plain words, and the file if you are about to edit one.
2. Run the query:

   ```powershell
   pwsh -NoProfile -File scripts/wiki/query.ps1 -Text "<subject words>"
   pwsh -NoProfile -File scripts/wiki/query.ps1 -Text "<subject words>" -Path <file>
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
   pwsh -NoProfile -File scripts/wiki/write.ps1 -Type <type> -Key <key> `
     -Summary "<one line>" -Evidence "<evidence>" -Seat <your seat>
   ```

5. Record the id it prints in your report. On a refusal, follow WIKI.md, *The optional flags*.

**Never put PHI, a message body or a secret in an event.** WIKI.md, *What never goes in an event*,
holds the full list.
