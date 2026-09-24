# Every script, and what it does

<a id="tldrbluf"></a>

Find the script for your task, then open its linked reference. The recorded inventory had 39 scripts
on 2026-08-31 and moved off the landing page on 2026-08-16.

Paths are relative to the checkout. This site also serves them directly, including [/scripts/coord/claim.ps1](https://claude-multisession.pages.dev/scripts/coord/claim.ps1).

If you are deciding whether to install, start with [the FAQ](FAQ.md).

[Installed controls](#controls-that-run-without-you) run automatically. Other rows describe commands you run yourself, scheduled work, or
shared helpers.

---

You can also read the source on [GitHub](https://github.com/wshallwshall/korus).

For manual downloads, also fetch `ccx.config.json` and the seven shared modules listed under
[Internals and installers](#internals-and-installers).

Without those dependencies, the PowerShell scripts throw at the start of their bodies. The three
Python hooks exit 1 on import, while the worktree gate exits 0 and enforces nothing.

## Start here

| Script | Does | Doc |
|---|---|---|
| `bin/ccx-doctor.ps1` | Prove -- by receipt and by attack -- that each control is installed, wired, and refuses what it can be made to refuse. It never infers, and a skip is never a pass (exit 2) | [Limits and requirements](LIMITS.md) |

## To run sessions

| Script | Does | Doc |
|---|---|---|
| `scripts/worktree/new.ps1` | Create an isolated worktree on its own branch, off the fetched remote tip, serialised against concurrent adds | [Worktrees](WORKTREES.md) |
| `scripts/worktree/spawn.ps1` | `new.ps1` plus an editor window (`-Editor`, else `CCX_EDITOR`, else `EDITOR`, else `code`) | [Worktrees](WORKTREES.md) |
| `scripts/coord/presence.ps1` | Who is live right now, across every surface. **Scoped to one repo by default**; `-Fleet` covers every repo the registry knows. Read-only | [Coordination](COORDINATION.md) |
| `scripts/coord/overlap.ps1` | What everyone else is changing -- files and stated work. `-File <path>`, `-Json`; cached, so the gate's common case is a cache read | [Coordination](COORDINATION.md) |
| `scripts/coord/claim.ps1` | Take, release or list an atomic claim on a piece of work, so a session finds out before the work rather than at merge. Advisory for free-text keys, enforced at `commit-msg` for numbered ones. Claims do not expire and releasing is manual, on purpose | [Coordination](COORDINATION.md) |
| `scripts/coord/alloc.ps1` | Allocate the next number in a shared sequence atomically, so two sessions can never be handed the same one; `-ShowFloor` inspects without spending one. `seq_check.py` is the other half -- neither is sufficient alone | [Sequence allocation](SEQUENCE-ALLOC.md) |
| `scripts/coord/mail.ps1` | Send, list or inspect the file-drop queue that reaches a peer in another Claude account or editor extension. `-Send -To <worktree path>` or `all`, `-List`, `-Status`. Queued is not delivered; the recipient's drain does that | [Session mail](SESSION-MAIL.md) |
| `scripts/coord/seat.ps1` | Write this session's episode record -- seat, goal, handoff -- so the next session is not guessing. `-Declare` also writes the role-card marker and refuses an unrostered seat; `-Record` never invents a goal | [Role cards](ROLE-CARDS.md) |
| `bin/ccx-steer.ps1` | Queue a steering note from a second terminal while a session is mid-task | [Steering](STEERING.md) |

## The fleet wiki

One memory that every seat on every account can search. [The spec](../specs/002-fleet-wiki/spec.md)
holds the design. These scripts write, guard, query, compile, render, import and lint. `write.ps1`
also takes a batch of events with `-FromJson`, which is how the import writes.

Run them by path from a korus checkout, and pass each store by flag: the default state root does not
resolve in the engine repository. [The wiki schema](../roles/WIKI.md) names the stores for a write
and a query.

| Script | Does | Doc |
|---|---|---|
| `scripts/wiki/write.ps1` | The only way to add an event. Checks the fields, runs the leak scan, then drops one file in the shared inbox. No network, and no git call when `-StateRoot` is given | [Fleet wiki spec](../specs/002-fleet-wiki/spec.md) |
| `scripts/wiki/query.ps1` | Searches the inbox, and the record repository's log with `-RecordRepo`. Prints `no note` below the match floor. Says so when a store is unreachable, and still exits 0. Warns on stdout when an unreadable file may hide a retirement | [Fleet wiki spec](../specs/002-fleet-wiki/spec.md) |
| `scripts/wiki/_event.ps1` | The event schema, the id and clock, the paths, the reader and the scorer. Dot-sourced by `write.ps1`, `query.ps1`, `compile.ps1`, `import.ps1` and `lint.ps1`, never run on its own | [Fleet wiki spec](../specs/002-fleet-wiki/spec.md) |
| `scripts/wiki/_guard.ps1` | The one filter every read passes through. Hides superseded and retired events; `-History` returns them labelled `historical` | [Fleet wiki spec](../specs/002-fleet-wiki/spec.md) |
| `scripts/wiki/compile.ps1` | Folds the inbox into the record repository's log, rebuilds pages and index through the guard, and opens one pull request, never merging. Holds back events the leak scanner there flags or that carry an email. `-RebuildOnly` uses the log alone | [Fleet wiki spec](../specs/002-fleet-wiki/spec.md) |
| `scripts/wiki/_render.ps1` | Renders the pages and the index from a set of events, and lists keys held by two events where neither supersedes the other. Dot-sourced by `compile.ps1`, never run on its own | [Fleet wiki spec](../specs/002-fleet-wiki/spec.md) |
| `scripts/wiki/import.ps1` | Folds the per-account memory stores into the inbox; the scheduled job runs it weekly. Reads only the directories named by `-Store`, records every merge as an event, and writes through `write.ps1 -FromJson`. An unchanged store adds nothing; `-WhatIf` writes nothing | [Fleet wiki spec](../specs/002-fleet-wiki/spec.md) |
| `scripts/wiki/lint.ps1` | Report only; changes no event. Finds conflicts, dead evidence, stale events, orphan pages and lessons two seats wrote. Counts the evidence it could not check, so zero dead is not read as clean | [Fleet wiki spec](../specs/002-fleet-wiki/spec.md) |

## To clean up and recover

| Script | Does | Doc |
|---|---|---|
| `scripts/worktree/remove.ps1` | Remove one worktree, referencing its tip before anything is removed, and writing a keep-ref when `-DeleteBranch` is used or a detached tip is on no ref. Refuses a worktree that contains another registered worktree | [Pruning](PRUNING.md) |
| `scripts/worktree/prune-merged.ps1` | The reaper: prune = merged **and** clean **and** unoccupied. Dry-run by default, `-Apply` to act. Carries a second, non-cwd signal and prints its blind spots | [Pruning](PRUNING.md) |
| `scripts/worktree/rescue.ps1` | Move uncommitted work out of the shared primary into a fresh worktree -- the companion to the gate that stops you writing there | [Worktrees](WORKTREES.md) |
| `scripts/worktree/restore-primary.ps1` | Re-attach the primary to its home branch after a session left it detached or on the wrong branch. Refuses on a dirty tree unless `-Force`, which carries the changes onto the home branch rather than discarding them | [Worktrees](WORKTREES.md) |
| `scripts/worktree/sessions.ps1` | Find sessions for this repo across every login, including ones a relocation made invisible; `-Rehome` puts a transcript back | [Worktrees](WORKTREES.md) |

## Controls that run without you

Once installed, these controls run through client events or git hooks.

| Script | Event | Does | Doc |
|---|---|---|---|
| `scripts/hooks/worktree_gate.ps1` | `PreToolUse` | Denies writes inside a governed primary, dispatch from it, the git verbs that swap or discard its tree, and those that hijack or remove another session's worktree. Fails open: loud on a load failure, silent on an empty allowlist | [Hooks](HOOKS.md) |
| `scripts/hooks/collision_gate.ps1` | `PreToolUse` | Refuses an edit to a file a live peer worktree has uncommitted changes in; your own worktree is skipped. Fails open and says so, but only once per reason per 30 minutes | [Coordination](COORDINATION.md) |
| `scripts/hooks/seat-declare.ps1` | `UserPromptSubmit` | A prompt that is EXACTLY a roster label declares that seat: writes the marker and loads the card in one turn. Anything less exact does nothing. Reads no ref. Always exits 0 | [Role cards](ROLE-CARDS.md) |
| `scripts/hooks/announce-session.ps1` | `UserPromptSubmit` | Tells peers you exist and what you intend, on the first prompt at which a messageable peer exists. Always exits 0; delivery needs the desktop client | [Coordination](COORDINATION.md) |
| `scripts/worktree/session-context.ps1` | `SessionStart` | Banner: your project's working defaults plus a live coordination block. Its stdout is the chat's starting context, so it never fails loudly | [Hooks](HOOKS.md) |
| `scripts/worktree/worktree-selfheal.ps1` | `SessionStart` | Repairs a primary whose HEAD drifted, when the tree is clean -- the most privileged control here, whose only safety property is that it refuses a dirty tree | [Worktrees](WORKTREES.md) |
| `scripts/hooks/claim_check.py` | `commit-msg` | Refuses a code-touching commit whose subject claims an item this worktree does not hold. Fail-closed, but the installed hook is a shim that exits 0 when no python is on PATH | [Coordination](COORDINATION.md) |
| `scripts/hooks/push_guard.py` | `pre-push` | Refuses a direct push, or a deletion, of a protected ref. An explicitly empty `protectedRefs` list disables it on stderr. Same shim: no python on PATH and it exits 0 | [PRs and merges](PR-AND-MERGE.md) |
| `scripts/hooks/seq_check.py` | `pre-commit` | Refuses a colliding, unallocated, or unindexed sequence number; `--ci` re-runs the collision rules against a freshly fetched trunk. No installer wires it | [Sequence allocation](SEQUENCE-ALLOC.md) |
| `scripts/hooks/block-blanket-git-stage.ps1` | `PreToolUse` | Opt-in. Denies `git add -A/--all/-u/.` and `git commit -a/-am/--all`. Fails open | [Hooks](HOOKS.md) |
| `scripts/hooks/steer-inject.ps1` | `PreToolUse` | Opt-in per worktree. Delivers a queued steering note at the next tool-call boundary rather than at the end of the turn | [Steering](STEERING.md) |
| `scripts/hooks/role-card-inject.ps1` | `SessionStart` | Hand-wired. Injects this worktree's role card, resolved from `.claude/seat.local.txt` then `$env:KORUS_SEAT`. Never guesses from a branch or directory name -- it stays silent instead | [Role cards](ROLE-CARDS.md) |
| `scripts/hooks/mail-drain.ps1` | `SessionStart`, `Stop` | Hand-wired, one script on two events. Renders this worktree's session mail at `SessionStart` and leaves it in the inbox; at `Stop` it consumes only what it displayed | [Session mail](SESSION-MAIL.md) |
| `scripts/hooks/precompact-reprime.ps1` | `PreCompact` | Hand-wired. Reads back what a compaction drops: the seat declaration on disk, and the allocations, claims and unpushed work this worktree holds. An unfiled allocation burns | [Hooks](HOOKS.md) |
| `scripts/hooks/block-api-burn.ps1` | `PreToolUse` | Hand-wired. Denies `gh run watch`, any `gh --watch`, and hand-rolled `gh` poll loops. Every seat spends one shared 5000/hr budget, and the seat that pays is not the seat that spent | [Hooks](HOOKS.md) |

## Scheduled jobs

You must register this job with a scheduler. No installer schedules it, and no client or git event
triggers it.

| Script | Does | Doc |
|---|---|---|
| `scripts/cron/watch-ci-red.ps1` | Polls for pull requests your repository labelled red and starts one session per red to attribute it. Zero model calls; a quiet repository is free. Exits non-zero on a zero it cannot establish, or a dead seat. `-DryRun`, `-Json` | [Watching for a red](CI-RED-WATCH.md) |

## Gates you have to run yourself

No installer wires these checks. This repository runs them in `.github/workflows/gates.yml`; add
them to your own continuous integration workflow too.

| Script | Does | Doc |
|---|---|---|
| `scripts/security/scan_forbidden.py` | The leak gate: refuse identifying content before a private repo goes public. `--path DIR`, `--show-context`. With no token source it scans shapes only and still exits 0; `--require-tokens` refuses instead | [Leak gate](LEAK-GATE.md) |
| `scripts/quality/check-ascii.ps1` | The ASCII gate: names every non-ASCII character it finds, and `-Fix` rewrites the safe substitutions. The doctor reports it `OFF (opt-in)`, because nothing installs it | [House style](HOUSE-STYLE.md) |
| `scripts/quality/frozen_citations.py` | Which frozen `.old.md` archives cite a heading. Run it before you rename one: those links are hash-pinned, so they cannot be repaired. CI runs the test behind it, never this script | [House style](HOUSE-STYLE.md) |

## Instruments for a run

These instruments report detected failures. Before running the `scripts/validation/` checks, read
[what broken looks like](https://claude-multisession.pages.dev/scripts/validation/README.md) for
their failure criteria and the run's stopping point.

| Script | Does | Doc |
|---|---|---|
| `scripts/board/refresh.ps1` | Rebuilds the board: collect, series, build, in order, stopping at the first failure so a half-rebuilt board is never published. `-OutDir` writes elsewhere, `-SkipCollect` re-renders without calling GitHub. Does not publish -- that needs a session | [The Lander Board](LANDER-BOARD.md) |
| `scripts/board/collect.py` | Reads the required contexts, the open pull requests with their checks, the merge queue and the create/merge/close timestamps for all three repositories into `data.json`. Refuses to write when a read fails. Needs `gh`; no standalone `jq` | [The Lander Board](LANDER-BOARD.md) |
| `scripts/board/series.py` | Derives the hourly merge and open-count series, the idle runs and the per-repository rates from `data.json` into `series.json` | [The Lander Board](LANDER-BOARD.md) |
| `scripts/board/build.py` | Renders `board.html` from `series.json` and `template.html`. Writes beside the scripts, or into `LANDER_BOARD_OUT` | [The Lander Board](LANDER-BOARD.md) |
| `scripts/board/seatstate.py` | Reads a watched seat's transcript and returns WORKING, IDLE or BLOCKED-ON-A-QUESTION. Output cannot tell the three apart; the last entry can | [The Lander Board](LANDER-BOARD.md) |
| `scripts/validation/run-checks.ps1` | Proves every instrument against a planted broken corpus and a planted clean one, then runs the same checks against this machine. Exits 3 without measuring anything when a control misbehaves | [What broken looks like](https://claude-multisession.pages.dev/scripts/validation/README.md) |
| `scripts/validation/check-message-delivery.ps1` | Messages written against messages rendered. Fires when a message sat past the settle window with no receipt naming it | [Session mail](SESSION-MAIL.md) |
| `scripts/validation/check-message-expiry.ps1` | Receipts against deadlines. Fires when a message passed the ttl its sender set, unshown | [Session mail](SESSION-MAIL.md) |
| `scripts/validation/check-claim-holders.ps1` | Claim holders per item. Fires when two keys naming one item are held by two live worktrees, or one claim's worktree holds two live sessions | [Coordination](COORDINATION.md) |
| `scripts/validation/check-allocation-collisions.ps1` | Every ref, grouped by sequence number. Fires when one number maps to two paths its index row does not declare as companions | [Sequence allocation](SEQUENCE-ALLOC.md) |
| `scripts/validation/check-session-reaping.ps1` | Liveness against last write. Fires when a live record's worktree has seen no commit and no file write for a day | [Pruning](PRUNING.md) |
| `scripts/quality/expiry_audit.py` | Does the artifact a standing rule's expiry clause points at still exist? Reports DANGLING, UNCHECKABLE or LIVE per clause, and never decides a rule expired. Exits 0 unless `--strict` | [House style](HOUSE-STYLE.md) |

These instruments report results without blocking commits or pushes. CANNOT_TELL from a validation
check, and UNCHECKABLE from the expiry audit, mean nothing was examined. Neither means nothing was
wrong.

## Internals and installers

[Quickstart](QUICKSTART.md) gives the four-installer order. [Install](INSTALL.md) explains the flags below.

| Script | Does | Doc |
|---|---|---|
| `scripts/coord/_common.ps1` | Config discovery, the state root, trunk resolution, path folding and git plumbing. Dot-sourced by nearly every PowerShell script here, never run on its own | [Concepts](CONCEPTS.md) |
| `scripts/hooks/_ccxconfig.py` | The Python counterpart, imported by all three git hooks. Copy a hook without it and that hook exits 1 on every commit | [Hooks](HOOKS.md) |
| `scripts/hooks/_command.ps1` | The one command splitter, dot-sourced by the worktree gate and the blanket-stage gate | [Hooks](HOOKS.md) |
| `scripts/hooks/_gittarget.ps1` | Which repository a git command actually acts on. Dot-sourced by the worktree gate, and pulls in `_common.ps1` itself | [Hooks](HOOKS.md) |
| `scripts/coord/_mail.ps1` | Worktree root, mail root, hashed box key and delivery bounds for the mail lane. Dot-sourced by `mail.ps1`, `seat.ps1` and the drain, never run on its own | [Session mail](SESSION-MAIL.md) |
| `scripts/validation/_receipt.ps1` | The receipt shape and the one verdict rule every instrument reads: CLEAN, BROKEN, or CANNOT_TELL when nothing was examined. Dot-sourced by all five checks | [What broken looks like](https://claude-multisession.pages.dev/scripts/validation/README.md) |
| `scripts/validation/_mailbox.ps1` | The schema-tolerant mail-lane reader the two message checks share. It counts a file it cannot parse rather than dropping it, so a broken lane never reads as an empty one | [What broken looks like](https://claude-multisession.pages.dev/scripts/validation/README.md) |
| `scripts/site/publish_sources.py` | Copies everything `git ls-files` tracks into the built site, which is why the paths on this page resolve without a clone | [House style](HOUSE-STYLE.md) |
| `scripts/site/publish_revisions.py` | Validates archive hashes, publishes exact `.old.md` sources, and checks revision links and search exclusion after the Jekyll build | [House style](HOUSE-STYLE.md) |
| `scripts/site/plot_token_meter.py` | Rebuilds the token-meter chart from the published measurement table | [Token accounting](TOKEN-ACCOUNTING.md) |
| `scripts/site/build_redirect.py` | Builds the forwarding site for the old GitHub Pages address, a stub per old URL. It cannot help the reader the move was made for | [House style](HOUSE-STYLE.md) |
| `scripts/coord/session-registry.ps1` | The liveness fence: reads the client's session registry and decides whether a session is alive. Liveness may only VETO, never PERMIT -- DEAD/STALE/absent is the absence of a veto, not a permission | [Concepts](CONCEPTS.md) |
| `scripts/coord/occupancy.ps1` | The one cwd-to-worktree matcher, returning a receipt alongside its rows (roots examined, records examined, records that could not be placed) and setting `Available` only when there was something to examine | [Concepts](CONCEPTS.md) |
| `scripts/coord/lock.ps1` | The short-lived cross-session mutex, dot-sourced rather than run: `. lock.ps1` then `Enter-CcxLock` / `Exit-CcxLock`. No TTLs anywhere: locks retry and never steal, and on timeout fail loudly and name the holder | [Concepts](CONCEPTS.md) |
| `scripts/coord/install-coordination.ps1` | Wires the banner, collision gate and announce at user scope as shims that re-resolve at run time; writes exactly one settings file per run (`-SettingsPath`) | [Install](INSTALL.md) |
| `scripts/coord/install-git-hooks.ps1` | Installs `commit-msg` + `pre-push` into one clone's shared `.git/hooks` (`-RepoRoot`), refuses to overwrite a foreign hook, and never writes `pre-commit`. Both are `/bin/sh` shims that exit 0 when no python is found | [Install](INSTALL.md) |
| `scripts/worktree/install-gate.ps1` | Installs the worktree gate as a copy outside every working tree, into every config root it finds, plus the allowlist that is its kill switch (`-Repo`, `-ConfigDir`) | [Install](INSTALL.md) |
| `scripts/worktree/install-selfheal.ps1` | Wires the SessionStart backstop into ONE config root per run; `-ConfigDir` is mandatory, and it governs whatever the gate's allowlist already names | [Install](INSTALL.md) |
