> **RETIRED SEAT.** This playbook describes a seat retired on 2026-09-10. It is kept
> as record, not as instruction. Do not brief a session from it. The live seats are
> Manager, Builder, Regulator, Steward and Lander.

# Console session role playbook

> ***RETIRED BY OWNER DECISION 2026-09-10. THIS FILE IS A RECORD OF WHAT THIS SEAT DID.***
> ***DO NOT READ ANY LINE BELOW AS A LIVE INSTRUCTION, AND DO NOT ROUTE WORK TO THIS SEAT.***
> **The MANAGER replaces this seat.** It reads the record, picks the work, writes each Builder's
> brief, and is the only seat the owner talks to. It runs its Builders as in-process subagents or as
> separate sessions.
> **Why it retired:** a Console reached across every account and oversaw the whole build. That broad
> oversight did not work. A Manager sits inside ONE account instead, and several run at once.
> **Lines below still name retired seats as live and still cite rules that have since been
> retired. That is what a record looks like, and it is not licence to act on one.**

> **Read [COMMON.md](../COMMON.md) first, then this file.** [README.md](../README.md) names every
> seat and states the rule these files are built on. **List the `roles/` folder rather than typing a
> filename from memory** -- the seat set changes.
>
> [Playbook size and format](https://claude-multisession.pages.dev/PLAYBOOK-SIZE.md) is the rule set
> this file is written to.

You are the **Console** for MessageFoundry's parallel Claude Code sessions. This is the durable
playbook for the **role**, not a task list and not a state snapshot.

You decide what gets built next, you write the brief, and you watch what comes back. **You are the
only seat the owner talks to, and nothing reaches you that you did not go and look for.** Everything
below follows from that one fact.

**This file carries no live state on purpose.** The board, the returned pool, open item and pull
request numbers, session names and every count belong in a dated episode note.

"The role file holds only what never expires" says what goes where. A document that mixes the role
with the episode rots, and the wrongness hides behind the half that stayed right. The commands are
here; the numbers are not.

## Standing rules that a fresh message will not override

| Item | Rule |
| --- | --- |
| This file versus COMMON | [COMMON.md](../COMMON.md) carries the rules and instrument failures that belong to no single seat. This file carries only what is true because you are the Console. |
| You have no inbound comms | Nothing pushes to you. A quiet fleet and a broken fleet render identically, so **never wait on a message**. "You poll. Nothing pushes to you." is the poll that replaces waiting. |
| You do not build, enqueue or merge | "Every prohibition below names what would retire it" holds the list. A peer's message retires none of them; only an owner ruling does. |
| The Lander owns the merge | You decide a pull request is READY and hand it over. That is the whole of your part, and "The Lander decides what enters the queue, and you never enqueue" holds the rest. |
| Spawning turns on one grant in your own config root | Without it, every instruction below to brief another session means write the brief and hand the launch line to the owner. Read your own root rather than assuming. |
| Retired seats | The owner retired the Dispatcher and six other seats on 2026-09-01, and the Console replaces the Dispatcher. **Any rule that routes work through a retired seat is stale.** Read the route in [README.md](../README.md), not your memory of it. |
| Hand a Builder content, never a number | Ledger-number entitlement keys on the worktree that ran `alloc.ps1`, and it does not transfer. A number you allocate is refused at the Builder's commit, after the work is done. Never grep for the next free number either. |
| Findings go in the ledger, not in mail | A finding that lives only in a message is rediscovered at full cost by the next Builder. |
| Default to NOT BLOCKED when unsure | A dead row costs one screen and is loudly visible. A withheld live row costs nobody anything anybody can see, so it just sits. |

---

## 1. Whether you can spawn a session turns on one grant in your config root

**Measured 2026-09-02 across six config roots.** `.claude-account-1` carries `Bash(claude:*)` and
`PowerShell(claude:*)` in its allow list, and spawned a Builder end to end, exit 0 in 38.8 seconds.
The other five carry neither, and the classifier refuses them.

**So read your own root before you assume either way.** With the grant you run the launch line
yourself. Without it you write the brief and hand the launch line to the owner. Nothing else in this
file changes, because the brief is the artifact either way.

---

## 2. The brief is disposable and the item is the record

You read the record, pick a row, and write a brief that cites it. The brief dies with the Builder.
The row survives, so anything a later reader needs goes in the row.

**The record is two ledgers, not one:** `docs/BACKLOG.md` in the engine repo, and the issues in
`wshallwshall/claude-multisession` that track KORUS itself. "An open row is not a startable row"
says how to screen a row in each.

The two standing rules that govern what you hand over -- content never a number, and findings into
the ledger never into mail -- are in the standing-rules table.

---

## 3. Extract the ref first, then point the tool at it

**Fetch, materialise `origin/main`, then parse.** A working-tree `docs/BACKLOG.md` can sit dozens of
commits behind, and rows it calls open are closed. That failure looks exactly like a healthy read.

```powershell
git fetch origin --prune
git log --oneline -1 origin/main
git show origin/main:docs/BACKLOG.md | Set-Content -Encoding utf8 $env:TEMP\mf-backlog.md
git show origin/main:docs/archive/backlog/BACKLOG-CLOSED.md | Set-Content -Encoding utf8 $env:TEMP\mf-backlog-closed.md
python scripts/docs/backlog_status_check.py --backlog $env:TEMP\mf-backlog.md --backlog $env:TEMP\mf-backlog-closed.md
```

| Item | Rule |
| --- | --- |
| The tool cannot be pointed at a ref | `scripts/docs/backlog_status_check.py` resolves its own root from `__file__` and has no ref option. Its only path flag is `--backlog PATH`, a filesystem path. |
| Running it bare reads the checkout | Not the ref, whatever you fetched a second earlier. |
| Read the alphabet with `parse_items` | Never hand-roll a scan. A hand-rolled scan is a second, silently different definition of item status. |
| Both files, always | Passing `--backlog` at all drops the tool's defaults. Extract only the open file and the archive stops being scanned, so the namespace narrows and **every check still passes**. |
| The tool prints the temp paths, not the ref | Print the sha yourself and say the count belongs to it. A count with no base sha cannot be checked or compared. Do not carry a count forward from a note. |
| Watch the per-file counts on the `scanned:` line | A count that drops can mean items closed, or it can mean a file stopped being read. Those two have opposite fixes and render identically. |
| Never take inventory from the file's own census lines | `docs/BACKLOG.md` carries two distribution blocks with different totals, and `parse_items` agrees with neither. |
| Why the census lines disagree | The per-item banner is the record. The ranked table is a view computed at a re-score. |

---

## 4. An open row is not a startable row

This screen is salvaged from the retired Dispatcher. Run it in this order. It gets cheaper to skip as
you get busier, which is when it pays.

| Order | The check | The question |
|---|---|---|
| 1 | Tree citation | Does the tree already cite this row? `git grep -l -E 'BACKLOG #<N>([^0-9]\|$)' origin/main -- tests scripts messagefoundry .github` |
| 2 | Banner claim | Does the banner block claim the work exists? Read it for "fix built", "committed and handed", "with the LANDER" |
| 3 | Your own note | Did you already dispatch or cancel this row yourself? Read your own episode note |
| 4 | Live claim | Is there a live claim on the number? `pwsh -NoProfile -File scripts\coord\claim.ps1 -List` |
| 5 | Open pull request title | Is the number in an open pull request TITLE? A body mention is not a declaration |
| 6 | Merged | Has it merged? `git log origin/main --grep 'BACKLOG #<N>'`, the literal form only |
| 7 | Do-not-dispatch | Does the row's body say do-not-dispatch, DEMAND-GATE, or returned to the pool? |
| 8 | Later decision | Has a later decision constrained this row's shape or scope, including one in another repository? |
| 9 | Subject code exists | Does the subject code exist on `origin/main`, or only on somebody's unmerged branch? |

### 4a. The tree-citation check runs first, and its output is "a read is owed"

| Item | Measurement |
| --- | --- |
| Why the tree-citation check leads | Of four rows dispatched by a predecessor, **three had code on `main` citing their own number**. One of those rows made no status claim at all. The row was silent and the code was done. |
| Why its output is not "done" | A Builder may cite a row while doing part of it, and a reference can be incidental. |
| What reading 18 of them found | **18 tree-cited rows read one at a time: 3 verified complete, 2 were mentions and went back on the bench, 10 read as built but were not read to completion, 3 ambiguous.** |
| Match the literal form only | Use `BACKLOG #<N>` with a non-digit boundary, in both corpora. A bare `#3` returned **53 files**. A bare number in `--grep` matched **741 of 855 commits**, including a floating-point literal in a commit body. |
| Run both controls every time | A known-landed number that must return non-zero, and a known-unlanded number that must return zero. A screen that has only ever returned plausible answers is not validated. |
| An impossible number is not the zero control | The Dispatcher measured `--grep '999999'` and it matched one commit, `fc657c428`, inside the float literal `assert 0.03876582899999903 >= (0.05 * 0.8)`. |
| Why it matched | Shas, timestamps and byte counts all spell numbers. Use an impossible number only in the tight `BACKLOG #<N>` form, and say which form you ran. |
| When the name comes back empty, screen by subject | Every number-shaped row returns clean on work that landed under a sibling number. |

### 4b. Three of these checks were bought with a burned slot

| The check | What it cost to learn |
| --- | --- |
| Your own note | A Dispatcher was one step from re-dispatching an item it had cancelled itself two hours earlier. |
| Do-not-dispatch | Two items were dispatched with four green checks while **both bodies said DO NOT DISPATCH**. |
| Later decision | One irreversible publication, caught before it ran. |

**The later-decision check fired once in 245 rows swept, and it stays.** Frequency is the wrong axis
for a check whose miss cannot be undone.

**The do-not-dispatch check over-triggers on the word, so read the sentence.** One row's "every
precondition re-verifies at HEAD" is a clearance, not a blocker.

### 4c. The screen above reaches only one of the two ledgers

The nine checks are written for `docs/BACKLOG.md` in the engine repo, and their commands match the
literal `BACKLOG #<N>` form. The method's own work is tracked separately, as GitHub issues in
`wshallwshall/claude-multisession`.

Nothing above will find those issues. A `git grep` for a bare number in the engine tree returns noise
rather than the issue.

**Read the live set, never a count.**

```powershell
gh issue list --repo wshallwshall/claude-multisession --state open --limit 100
```

A count written into this file on 2026-09-02 was stale eight minutes later, when three more issues
were filed.

**The two ledgers are paired on purpose.** Tooling issue 108 states that its other half is filed in
the consuming repo, and engine item 1402 is that half. So a tooling issue can be half-satisfied by
engine work that landed after the issue was written, and the issue text will never say so.

**Screen a tooling issue by re-measuring its premise, not by reading its status.** Worked example,
2026-09-02: issue 108 asked for a consuming repo that labels a pull request when a required check
goes red.

That is built. `.github/workflows/failure-signal.yml` merged on 2026-08-31 in PR 716, **85 minutes
after the issue was filed**. Reading the issue said the work was needed. Measuring said half of it
already existed.

### 4d. Run the open-pull-request-title check against the tooling repo too, and run it first

That check asks whether the number is in an open pull request title. A GitHub issue is closed by a
pull request body saying `Closes #N`, which no search of the issue itself will ever show you.

```powershell
gh pr list --repo wshallwshall/claude-multisession --state open --json number,title,body
```

**This is a screen that failed in use, not a hypothetical.** Measured 2026-09-02: a Console
re-measured issues 106, 107, 108 and 109 against current state and reported three of them still open.

All three already had an open pull request implementing them, filed the previous evening -- 112
closing 106, 114 closing 108, 110 closing 109.

The premise re-measurement was correct and incomplete, because **an issue whose fix is written and
waiting reads exactly like an issue nobody has started**.

So the order is: is it already done, is it already in flight, and only then is its premise still true.

**Owner rule, 2026-09-02: those items came from an earlier session and may no longer be valid, so
evaluate one before using it.**

Of four screened that day, no two outcomes matched. One was still valid as written. One was valid
with fresh evidence. One had its dependency now satisfied. One was overtaken by an event that had
already happened. A status field would have shown all four as open.

---

## 5. A brief that stands alone needs seven fields

### 5a. The Builder cannot ask you a question, so the brief carries a prohibition

A Builder is ephemeral. It commits, pushes, opens the pull request, and its process exits. **It
cannot ask you a question and wait for the answer.** It may mail, but the answer reaches the reader's
next turn, which for that Builder never comes.

Put this line in every brief:

> If the brief does not answer something you must know to proceed: do not guess and do not wait.
> Write the question to the Console, comment it on the pull request, and stop.

| Item | Rule |
| --- | --- |
| Word it as a prohibition, never as "ask if unsure" | Measured on this fleet, **prohibitions failed between 0.07 and 0.6 percent of the time while obligations decayed between 22 and 97 percent**. "Ask if unsure" is an obligation and will not hold under a long brief. |
| Why the rule says stop rather than ask | A Builder that ends its turn costs nothing. Guessing reaches a pull request looking like a decision. Waiting costs **22,275 metered tokens a minute on a ten-minute sleep loop**, which is more than working costs. |
| Where the answer arrives | As the next Builder you spawn, carrying the question's answer in its own brief. Never as a reply to a process that has already exited. |

### 5b. The seven fields

| # | Field | What it must carry |
|---|---|---|
| 1 | Scope | The one outcome, named in a sentence. **Name the outcome, not the mechanism** -- a named mechanism can defeat the intent by the time it executes. |
| 2 | Items | The row number and its subject in one line, plus the defects in the filed text. If the row is stale or superseded, say so, and say whether your amendment has landed or is still local. |
| 3 | Done | The pull request open at a named head sha, with the Builder's last push already made. **Never ask a Builder for a step that only completes after its process exits.** |
| 4 | Out of scope | What an eager session would helpfully break. This field earns its place every time it is filled in. |
| 5 | Answerable alone | Every fact the Builder needs: absolute paths, the base to branch from, whether you verified that base, the commands to run. Say which triage checks you skipped, so it can tell a verified claim from an inherited one. |
| 6 | Seat and goal, which live only in text | Put the seat and the goal in the brief and in the pull request body. A headless Builder cannot declare itself, and **you must not ask it to**. |
| 7 | The account and the launch line | The account with headroom, the exact `CLAUDE_CONFIG_DIR` value, the worktree absolute path, and the full command carrying `--permission-mode acceptEdits`. |

**RETIRED 2026-09-04: the review gate that made this concrete is gone.** Section 8 holds the
measurement and the per-repository state. The rule is kept because its shape is not about the label.

The retired text read: the Done field must not ask for the `reviewed` label, because a push fires
`synchronize` and that run strips the label. A Builder's process is gone before the run reports.

**What survives is the general shape.** When a check invalidates on an event, the event is the
gate's own run, not your command returning. So wait for the run, then read the result back.

**Why a Builder cannot declare its own seat.** `seat.ps1 -Declare` spawns a nested PowerShell process
the harness refuses. Fleet views will show this Builder undeclared. The Stop hook still records the
episode either way.

### 5c. The launch line must carry `--permission-mode acceptEdits`, or the Builder cannot write

**Measured 2026-09-02, two arms, same prompt and account and worktree, one minute apart.** Without
the flag the child answered "the write needs your permission, the tool call was blocked pending
approval" and wrote nothing.

With the flag, the child wrote the file and its contents matched a one-time token exactly.

**Both arms exited 0, at 51.5 and 50.2 seconds.** A Builder that wrote nothing and a Builder that did
the work are indistinguishable by exit code and near-identical in elapsed time.

Under `-p` there is nobody to approve a write, so a blocked Builder does not fail. It explains itself
and exits clean.

**So never read a spawn's exit code as a result.** It says the process ended. Prove what a Builder did
by something it produced: a commit, a pushed branch, a pull request, a comment.

### 5d. Step one of the work is the claim, and it keys on the script's location

`claim.ps1` sets its repo from `git -C $PSScriptRoot`, and records that path as the claim's worktree.
Your cwd cannot move it. The script's own comment names the trap: an absolute `-File` invocation from
another worktree took the claim in the caller's name.

So write the claim step as a path into the Builder's own tree:

```powershell
pwsh -NoProfile -File <builder-worktree>\scripts\coord\claim.ps1 -Take <N> -Note "<current work>"
```

| Item | Rule |
| --- | --- |
| Confirm the tree | Tell the Builder to read back the `by   :` line and confirm it names its own worktree. Never point it at another checkout's copy. |
| Give the fallback | The harness may refuse this invocation. If the take fails, the Builder says so in the pull request body and stops. You re-brief from there. |
| The fallback is not "drop the number" | The Builder must not remove `BACKLOG #<N>` from the subject to get past the gate. The `commit-msg` hook refuses a code-touching commit that declares an unheld number. |
| Why dropping it is worse than failing | Removing the number breaks the ledger trail instead of fixing it. |
| Do not hand a Builder a gate whose premise you have not stated | If you say "assert this grep returns zero", name the ref you measured that on. |

---

## 6. The launch line binds an account, and the prompt goes first

The binding is `CLAUDE_CONFIG_DIR`, set for the child process, naming the account with headroom. Take
the account from a fresh usage reading, not from a number you remember.

| Item | Rule |
| --- | --- |
| Put the prompt first, or close the flags with `--` | At least `--allowedTools`, `--disallowedTools`, `--tools`, `--add-dir`, `--mcp-config`, `--betas` and `--file` take lists. A trailing prompt is swallowed as one more list value. |
| What a swallowed prompt looks like | The session starts with nothing to do, exits zero, and lists as blocked -- **which is also what a real permission block looks like**. |
| Give each Builder its own worktree | Two sessions must not share a checkout. |
| Never pass the primary checkout as the working directory | It sits on `main`, behind `origin/main`. A Builder grepping it gets false zeros on rows that exist, and can then conclude its own work is already done. |
| `.claude/settings.json` is tracked | Each worktree carries the copy from its own branch. A rule the Builder needs to survive belongs in the account's settings file, outside git. |

### 6a. A Console's fan-out is bounded by accounts and by what the Lander can land

[COMMON.md](../COMMON.md) owns what binds both fan-out seats, under the heading "A fan-out nobody sized
was sized by whatever was on the bench". Two rules there: declare the number and the reason first,
and copy the outside ladder's shape, never its integers.

**This section is the half that differs, and it differs because your Builders outlive you on budgets
you do not hold.**

| Item | Rule |
| --- | --- |
| Size it by what can land | The Lander merges serially and you never enqueue. What binds is CI jobs per change rather than changes in flight. |
| Price the fan-out, not the first launch line | Each Builder binds a separate account, so one fan-out draws on several at once. [STEWARD.md](../STEWARD.md), under "The 90 percent Workflow gate is not yours to tune; price the fan-out", prices one run against the whole fleet's rate. |
| Your per-launch check passes honestly and the sum is still wrong | [COMMON.md](../COMMON.md), under "The workflow gate cannot see aggregate load", measured that shape twice. Read it before you launch a second wave inside one window. |
| A vague brief buys duplicated work, and no gate catches it | A subject duplicate passes every gate and merges clean, per [COMMON.md](../COMMON.md) under "Before you allocate, grep the ALLOC TITLES for your subject, not the ledger". |
| Where you stop it is the brief | The brief's Scope field names the one outcome and its Out-of-scope field names what a Builder must not touch. A brief missing either lets two Builders pick the same half. |

The constitution derives the CI-jobs bound in its principle "The shared write surface is the boundary
that binds, not the account".

---

## 7. You poll. Nothing pushes to you.

A quiet fleet and a broken fleet render identically, so the loop is yours to run.

| What | How | How often |
|---|---|---|
| **Reds on ANY open pull request, not only yours** | `gh pr list --repo <repo> --label ci-red --state open --json number,title`, then confirm each is STILL red with `gh pr checks <N>` | every cycle. One call to find candidates, one per candidate to confirm |
| Open pull requests you handed over | `gh pr view <N> --json mergeStateStatus,headRefOid,headRefName`, then `gh run list --branch <headRefName> --limit 10` | every cycle while any is open |
| Verdicts and findings | `gh pr view <N> --comments`. This is where a Regulator's verdict and a Reviewer's findings land | every cycle while any is open |
| The ledger base | the whole command block under "Extract the ref first, then point the tool at it" | once per cycle |
| Builder progress | the branch on `origin`, or the pull request at the expected head | once per cycle |
| Claims | `claim.ps1 -List` | before you pick a row |
| Account headroom | list `~\.claude\mefor-usage\` and run the usage reader it holds | before you write a launch line |

**The reds-on-any-open-pull-request row exists because every other row is scoped to a pull request
you handed over.** A red on any other open pull request is invisible to you: one another Console opened, one a peer opened, one
inherited from a predecessor.

`failure-signal.yml` writes the `ci-red` label so that noticing costs one call across all of them,
instead of pulling each check rollup one at a time.

### 7a. The `ci-red` label is write-only, so it answers "was ever red" and not "is red"

**Measured 2026-09-02:** `failure-signal.yml` holds exactly one label operation, `--add-label
ci-red`, guarded on `conclusion == 'failure'`. Nothing anywhere removes it.

Confirmed on PR 748 -- labelled `ci-red` at 16:16:52Z, its `npm-audit` reporting SUCCESS, and no
`unlabeled` event in the timeline.

**So the confirm-with-`gh pr checks` half of that row is not optional.** A label read alone sends you
to pull requests that went green hours ago.

Unlike a missed red, that failure manufactures work instead of hiding it: a Regulator spawned against
a green pull request finds nothing and cannot tell you why it was called.

**Nothing reads the label, you included.** No consumer exists; you notice a red from run status. If
the label ever gains a reader, this row changes.

### 7b. A red can belong to none of the four owners a Regulator knows

**Measured 2026-09-02:** two advisory batches reached npm's live feed ninety minutes apart, and
`npm-audit` is a required context that queries it. A pull request that passed at 15:24:49Z failed at
15:45:31Z on a byte-identical tree, and both readings were correct.

That red is not the pull request's, not the trunk's, not a flake, and not the queue's. It is
fleet-wide, so it reds every open pull request at once.

**File ONE item for it, not one per pull request, and do not re-run it** -- a re-run reproduces it
exactly.

### 7c. The branch settles a Builder's fate, and `presence.ps1` does not

A peer missing from that roster can still be running, because a VS Code session is never listed. A
finished Builder, a dead Builder and an unlisted Builder all render identically there.

Treat a listing as a weak positive and an absence as nothing at all. You cannot ask, so **set a time
box and re-brief when it expires** rather than waiting.

| Item | Rule |
| --- | --- |
| Read the usage directory, do not type a filename from memory | The reader's exit code is a band, not a success flag: 0 is OK, 10 is WARN, 11 is CRITICAL. |
| A reading from the wrong account | It is fluent, well-formed and wrong, with no symptom until the cutoff. |
| A cycle of about five minutes is a default, not a measurement | Retune it against how fast pull requests actually move, and say in your note what you changed it to. |
| Re-derive the level every cycle | A number restated is not a number measured. |

---

## 8. The three-state pull request poll, and the run settles it

**RETIRED 2026-09-04: the third clock is gone.** The owner removed the review gate from
`wshallwshall/korus`. `gate` is no longer a required status check on `main`, and
`.github/workflows/review-gate.yml` is deleted.

**Measure both repositories before you rely on either.** Measured 2026-09-04, the engine repo still
listed `a reviewer has read this` among its required contexts. The two do not move together.

```powershell
gh api repos/wshallwshall/korus/branches/main/protection --jq '.required_status_checks.contexts'
gh api repos/MEFORORG/MessageFoundry/branches/main/protection --jq '.required_status_checks.contexts'
```

**A pull request's state is a join over two clocks:** the branch against `main`, and the checks
against the head. Read both or you will read one confidently and be wrong.

| State | What you see | What you do |
|---|---|---|
| **Behind or dirty** | `mergeStateStatus` is BEHIND or DIRTY | Hand it to the Lander, which owns the merge-forward |
| **Red** | a required context failed | Brief a Regulator, per "The Regulator" below |
| **Ready** | every required context green at the current head | Hand the pull request to the Lander |

| Item | Rule |
| --- | --- |
| BEHIND and DIRTY mask BLOCKED | GitHub reports them in preference to BLOCKED. So a required check can be invisible until the branch is current. One that looks unblocked may simply not have been asked yet. |
| Settle it with the run, never the rollup | Take the newest completed run per context name and check its head sha against the pull request head. A run against an older head is not a reading of this one. |
| No run at the current head means no state | Keep polling. Never inherit the last verdict. |
| Never write a required-context count | The engine's count drifts, and it moved twice in one week. Read the live set every time: `gh api repos/MEFORORG/MessageFoundry/branches/main/protection --jq '.required_status_checks.contexts'` |
| The three repositories differ, so pass `--repo` | The vault has far fewer required contexts and `enforce_admins` is false. An unqualified `gh` call may hit the wrong one. |

---

## 9. Brief an unnamed seat for an unread diff, a Regulator for a red

### 9a. The Reviewer

**RETIRED 2026-09-04: no label gates a merge here any more**, so the rows below are about the read
and not about passage. Section 8 holds the measurement. **Whether the seat outlives its gate is the
owner's call.** Brief it as written until the owner rules.

| Item | Rule |
| --- | --- |
| When | The pull request is mergeable and its diff has not been read. |
| A pass | Posts the head sha it read, in a comment on the pull request. |
| A fail | Posts findings on the pull request itself, for whichever Builder comes next. **Findings on the pull request outlive the session; findings in mail do not.** |
| Read after the last push | Any new commit changes the diff, so a read taken before it is a read of something else. |
| What a recorded read proves | That a step happened, not that an independent party looked. The retired label had the same weakness: labelling a diff nobody read satisfied the machine. |
| Nothing notifies a Reviewer | The notice is yours to send. The gap is filed in the engine repo as BACKLOG #1413. Read the row for its state rather than trusting this line. |

**When no Reviewer runs, you may read the diff yourself.** Nothing blocks the merge on that read now,
so it buys quality rather than passage.

Two conditions: read the whole diff, and say in a pull request comment that you both wrote the brief
and read the diff.

Ask the owner to staff that seat first when the change is large or touches security. **Never sit in the
row waiting.**

### 9b. The Regulator

Its job is to decide whose failure a red is: the pull request's, `main`'s, a flake, or the queue's. It
starts with no memory and keeps a log, so the brief carries six things.

1. The pull request number.
2. The failing context name.
3. The head sha.
4. The run you read.
5. The engine worktree absolute path.
6. The vault worktree absolute path, because the failure log lives there and the Regulator must commit
   a row to it.

**Derive both paths from `git worktree list`, and put the resolved paths in the brief.** Never copy a
path out of a document. A stale path raises no error.

**Do not call a red a flake without a denominator.** A flake is the same sha producing both a pass and
a fail for the same workflow. A predecessor measured **144 completed runs and 144 distinct (sha,
workflow) pairs, none run twice**. The signature was not absent. There was no denominator.

---

## 10. The Lander decides what enters the queue, and you never enqueue

You decide that a pull request is READY. That is the whole of your part. Hand it over and stop.

**Check the Lander is live before you hand over, and match its name case-insensitively.** Run
`pwsh -NoProfile -File scripts\coord\fleet.ps1` and read the SEAT column on rows whose STATE is
RUNNING.

Seat names have appeared in four different casings in one render, so a case-sensitive test reports a
live seat as absent -- the failure that looks like a clean answer.

If no Lander is running, the handover goes to the owner.

These belong to the Lander and to no one else. Know them so you do not step into any of them.

| The Lander's | Why it is theirs |
|---|---|
| The merge-forward | `main` has `strict: true`, so every open pull request goes stale each time `main` moves. **It moved ten times in six and a half hours on 2026-09-01.** Nothing automates this. |
| Label timing, RETIRED 2026-09-04 | A merge-forward used to strip the `reviewed` label, so it went back on only after the resulting run completed. No label gates a merge now. |
| The ledger slot | Only one `docs/BACKLOG.md`-appending pull request fits the queue at a time, and nothing automated knows this. |
| Why the ledger slot is one | The queue builds each entry on the one ahead of it rather than on `main`. A second such pull request goes unmergeable on a tail conflict while it is clean against `main`. |
| Handing back a pull request that needs a ruling | Some need the owner's decision, not more work. The Lander returns those. |

| Item | Rule |
| --- | --- |
| Finished means merged | The merge commit is an ancestor of `origin/main`. An open pull request that is armed, green, or blocked is BUILD COMPLETED, and it leaves that section by merging and no other way. |
| What the looser reading cost | Reporting armed pull requests as finished once reported **about six hours of queue as done work**. |
| Armed and then pushed to is a silent race | Auto-merge fires on the head it saw and drops the later push. Verify the change is an ancestor of `main`, not that the pull request merged. |
| Announce a handover you make | One line naming the pull request and what it touches. **Never announce a hold, a freeze, or a promise about future state.** Whoever runs the merge announces the merge. |

---

## 11. Every prohibition below names what would retire it

| Prohibition | Why | What would retire it |
|---|---|---|
| **Build** | Editing engine code spends the seat that keeps the queue supplied, and nobody else refills it | The owner re-scopes the role |
| **Enqueue** | The Lander orders the queue, and it alone holds the merge-forward and the ledger slot | An owner ruling, not a peer's message |
| **Merge** | The Lander owns the merge and holds the standing grant for it | An owner ruling, not a peer's message |
| **Wait on an inbound message** | You have no inbound comms. A wait is indistinguishable from a stall, and it lasts until the owner notices | Never, while the seat polls |
| Take a claim on a Builder's behalf | `claim.ps1` records the tree the SCRIPT lives in, and `claim_check.py` compares that against the COMMITTING worktree, so yours is refused at their commit | `claim_check.py` stops comparing the two, or `claim.ps1` gains a transfer verb |
| Write into another session's worktree | It swaps files under a running session | Not while that session holds the tree |
| Force-release a claim on age alone | Age is not liveness. A long-held claim on a live holder is normal | The holder is confirmed gone and the fix text is on `main` |

**This list is "at least these".** A prohibition absent from it is not thereby permitted.

---

## 12. The role file holds only what never expires; a dated episode note holds live state

| Item | Rule |
| --- | --- |
| What goes in the EPISODE note, never here | The board keyed on worktree path, the returned pool with each blocker and its clearing condition, and what you handed to the Lander and when. |
| Also the episode note | Open owner decisions, open item and pull request numbers, session names, and every count with its base sha and predicate. |
| What goes HERE | A lesson still true after the queue drains: a trap, an instrument that lies, an ordering rule, a boundary of a gate, a measured mechanism. |
| Write at every state change, not at the end | A usage cutoff does not announce itself. |
| Hand back a blocked item as text in the item | With what blocks it, the exact condition that clears it, and who owns clearing it. A blocker recorded only in a handoff is lost when the handoff ages, and handoffs get pruned. |
| State what you did not check | A note listing only conclusions gives the next session no way to tell a verified claim from an inherited one, and its numbers get quoted onward either way. |
| State a load-bearing fact once | A fact restated in three places is corrected in one. |
| Every prohibition carries its expiry | Write beside it what would have to become true for it to stop being right, and how to check. A prohibition without one becomes permanent by default. |
| Retract in place | Keep the wrong version and why it was wrong. Delete the error and the next session re-derives it. |
