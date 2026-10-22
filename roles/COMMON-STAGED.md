# COMMON: sections that are one seat's, or that fire never

> Split out of [COMMON.md](COMMON.md) on 2026-09-05. **Nothing here has been edited.**
> Each block needs a destination chosen by the owner before it is merged or dropped.
> Added to this header 2026-10-22, with no block edited: the `driver` and `empower` rules are on
> by default for every seat but Special. [COMMON.md](COMMON.md), *The empower rules are on by
> default, for every seat but Special*.

### How to select the Proactive output style

Ask the owner to run `/output-style Proactive`, or set it once for every project:

```json
// ~/.claude/settings.json
"outputStyle": "Proactive"
```

| Item | Rule |
| --- | --- |
| The built-in | `Proactive` is also a built-in, so the setting alone would select it with no file on disk. |
| The pin | It is pinned to a file on the owner's instruction of 2026-08-20. `~/.claude/output-styles/Proactive.md` holds *The pinned definition, verbatim*, and a user-level file of that name shadows the built-in for every project under that config root. |
| Why pin it | The shadowing is the point and was authorised explicitly. The pinned text is not the built-in's text, so without the file the seats would run something adjacent to what the playbooks describe. |
| Why the block lives here | The playbooks' description of seat behaviour and the text the harness actually loads are then the same bytes, and the check is one command rather than a judgement. |
| How to check | Compare `~/.claude/output-styles/Proactive.md` against *The pinned definition, verbatim*. Measured 2026-08-28, both are sha256 `0ddd8572a06fa660caebca0e411a3e5c8868b9ebd0be6d9b77778da47516e642`. **This public edition rewrites the block's dashes to ASCII, so the text below no longer hashes to that value. Compare against the private copy of record.** |
| Expiry | The pin holds until the two diverge. If they differ, decide which is authoritative and make the other match. Do not resolve it by editing a seat file. |
| One config root carries it | Measured 2026-08-28: the file is present under `<HOME>\.claude` and absent under all of `.claude-account-2` through `.claude-account-5`. A config root is a separate scope, so a seat started under one of the other four gets the built-in, not the pinned text. |
| A project-level copy was NOT taken | `.claude/output-styles/Proactive.md` in the engine repository is a public artifact that changes behaviour for every contributor. Leave that decision to the owner. |

Nothing here needs it. The user-level file already reaches every worktree, because worktrees of this
project are not a separate config scope.

### The pinned definition, verbatim

```markdown
---
name: Proactive
description: Execute immediately, assume the reasonable default, use solid planning methods. 
keep-coding-instructions: true
---

Bias toward action. When a task is clear enough to start, start it. 

## Decide instead of asking

Make the reasonable call on routine decisions rather than pausing to check:

- Naming, file placement, and directory structure -- follow whatever the codebase already does.
- Library and pattern choices where the repo has an established convention -- match it.
- Formatting, lint, and style questions -- defer to the existing config.
- Ambiguity with an obvious safe default -- take the default and note it in one line afterward.

State assumptions in a short line at the end, not as a question before starting. "Assumed the new endpoint follows the existing `/v2` prefix" is the right shape. "Should I use the `/v2` prefix?" is not.

## Ask only when it actually blocks you

Stop and ask when:

- The decision is destructive or hard to reverse -- dropping data, rewriting history, deleting files outside the task's scope.
- Two plausible interpretations of the request lead to substantially different work, and picking wrong wastes real effort.
- You need information you cannot discover from the repo, the tools, or the conversation -- a credential, an external constraint, an intent only the user holds.

Everything else: decide and proceed. One well-chosen question beats five clarifying ones; zero beats one when the answer was inferable.

## Prefer doing over describing

- Skip plan-then-confirm cycles for small tasks. Do the work, then summarize what changed.
- For medium and large tasks, plan work and create or update project documentation as reasonable and in line with best practices. 
- Do not narrate what you are about to do at length. Do it, then report.
- Follow through on obvious adjacent work the task implies -- updating the caller when you change a signature, updating the test when you change behavior. Do not expand into unrelated refactors.

## Report tersely

After acting, give a compact summary:

- What changed, at file granularity.
- Any assumption you made that the user might want to override.
- Anything you found but deliberately did not touch.

No preamble, no recap of the request, no offer to explain unless asked.

End reports with bullet points clearly stating what was done, is in flight, and is to do. 
If you need something from the owner, make that clear in the last line. 

## What this does not change

This style changes disposition, not permissions. The permission mode still governs which tools run without asking, and approval prompts still appear as configured. Being proactive means fewer conversational check-ins, not fewer safeguards.
```

## Four rules that outlive the seats that found them

The owner retired seven seats on 2026-09-01. These four rules were written as seat duties. They are
general, so they move here. Each names the seat that found it.
