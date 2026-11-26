> **RECORD, NOT INSTRUCTION.** This file keeps text moved out of [MANAGER.md](../MANAGER.md),
> verbatim, so the live file carries only live rules. Nothing below binds. Where a passage here and
> the live file disagree, the live file governs.

# MANAGER: text moved out, kept verbatim

Each section names where the text stood and the ref it was copied from. A line here may name a
rule that no longer holds.

Moved 2026-11-25 under the owner's ruling on decision 3 of vault
`docs/RULE-INTAKE-AND-PRUNING-PROPOSAL-2026-11-25.md` (vault PR 3059).

## M3. A correction notice, from *Apply the `qa` label and post the Builder's line*

Copied from korus `origin/main` `42ff0d4`.

**That sentence said "its `code-review` subagent" until 2026-09-22.** *CORRECTED 2026-09-20* in
section 4 retired that word and this copy kept it. A retraction that reaches one of two sites
leaves the other as the version a reader meets first.

## M8. A repair record, from *6. Never Do These*

Copied from korus `origin/main` `42ff0d4`. It opened the section, above its table.

**Two rows in *Standing rules* cited this section by a heading that has never existed here, and
2026-09-18 repointed them.** They named it *Four acts stay outside this seat*.

Measured at `ff11047`, before the repair:

```bash
git show ff11047:roles/MANAGER.md | grep -cE '^#{2,3} .*Four acts'
```

It returns 0. Control, the same pattern over every heading in that file, `'^#{2,3} '`: 10, so the
extraction read the file rather than returning empty.

The name also promised four acts against a table of two. A reader following it found nothing, and
could not tell a missing section from a missing rule.

**Do not measure the phrase's absence in THIS file.** The paragraph you are reading contains it, and
so does the repair's own commit message.
