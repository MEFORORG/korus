# Hooks

## TLDR/BLUF

Hooks run checks when a session uses a tool, starts, receives a prompt, or commits work. Each
control also defines what happens if its own check fails.

Harness hooks can stop tool calls before they run, but miss shell redirects. Git hooks see every
write at commit time.

These controls support concurrent sessions. Merging their source does not install them.

The event map lists each control and its failure behavior. Run the doctor from the repository you
want checked:

```powershell
pwsh -NoProfile -File <tooling>/bin/ccx-doctor.ps1 -Repo <the-repo-you-govern>
```

---

Harness hooks and git hooks run at different points and use different response formats.

Claude Code runs harness hooks listed in `settings.json` when an event occurs. It sends JSON on
stdin and reads the JSON decision from stdout before allowing a tool call.

Git runs hooks from its shared hooks directory at commit or push time. It supplies arguments or
stdin and reads the exit code.

These checks inspect the tree, covering writes from tools, shell redirects, editors, and subagents.

Each control states its failure posture in its file header: whether work can proceed when the check
fails.

Harness hooks use PowerShell 7 and target Windows first. The three git-hook checkers in the second
table use portable, standard-library Python behind `/bin/sh` shims.

---

## The event map

<a id="g06"></a>
<figure class="explain-figure">
  <picture>
    <source media="(max-width: 1100px)" srcset="/assets/diagrams/g06-events-mobile.svg">
    <img src="/assets/diagrams/g06-events.svg" alt="Controls placed at their client and Git event triggers." loading="lazy" width="799" height="890">
  </picture>
  <figcaption>Controls run only when wired. The doctor verifies installation separately; event spacing does not measure time. <a href="/assets/diagrams/g06-events.drawio">Editable diagram</a>.</figcaption>
</figure>

Four harness events support these controls: `SessionStart` opens a chat, `PreToolUse` precedes a
tool call, `UserPromptSubmit` receives a prompt, and `PreCompact` precedes a summary.

Fail-open controls allow work when their check breaks. Fail-closed controls refuse it.

| Event | Script | Matcher | What it decides | Posture |
|---|---|---|---|---|
| `SessionStart` | `scripts/worktree/session-context.ps1` | -- | Prints the project banner and the live-peer coordination block into the new chat's starting context. Decides nothing. | fail open, silent |
| `SessionStart` | `scripts/worktree/worktree-selfheal.ps1` | -- | Repairs a shared primary checkout whose HEAD drifted, if its tree is clean; if the tree is **dirty** it touches nothing and reports the decline. Injects a heads-up when the session is sitting in a stub worktree. | fail open, silent on **error** |
| `PreToolUse` | `scripts/hooks/worktree_gate.ps1` | `Write\|Edit\|MultiEdit\|NotebookEdit`, `Bash\|PowerShell`, `Task\|Agent\|Workflow`, `EnterWorktree` (opt-in) | Denies a write whose **target path** is inside a governed primary; a write to the gate's own enforcement surface; a subagent dispatch from the primary; a git verb that swaps or discards the primary's tree; a hijack of another session's worktree; a shared-config disarm; a `git worktree remove\|move` aimed at somebody else's checkout. | fail open, **loud** |
| `PreToolUse` | `scripts/hooks/collision_gate.ps1` | `Edit\|Write\|MultiEdit\|NotebookEdit` | Denies an edit to a file a live peer **worktree** has uncommitted changes in -- your own worktree is skipped, so a second session in it is invisible. Reports, without denying, a file already committed on a live peer's branch. | fail open, **loud** |
| `PreToolUse` | `scripts/hooks/block-blanket-git-stage.ps1` | `Bash\|PowerShell` (hand-wired) | Denies `git add -A/--all/-u/.` and `git commit -a/-am/--all`. | fail open, **loud** |
| `PreToolUse` | `scripts/hooks/steer-inject.ps1` | `*` (opt-in, hand-wired) | Delivers a queued steering note as `additionalContext` at the next tool-call boundary. Decides nothing. | fail open, silent |
| `SessionStart` | `scripts/hooks/role-card-inject.ps1` | -- (hand-wired) | Injects this worktree's role card, resolved from `.claude/seat.local.txt` then `$env:KORUS_SEAT`. **Never guesses from a branch or directory name** -- it stays silent instead, because a wrong card outranks the document the session should be reading. Decides nothing. | fail open, silent |
| `UserPromptSubmit` | `scripts/hooks/announce-session.ps1` | -- | Resolves live peers and asks the model to announce itself to them. Decides nothing. | fail open, **loud** |
| `PreCompact` | `scripts/hooks/precompact-reprime.ps1` | -- (hand-wired) | Reads back what a compaction drops: the **declaration** `scripts/coord/seat.ps1` recorded, and the **ledger** of allocations, claims and unpushed work this worktree holds. Never invents a goal, and flags a record from another branch rather than restoring it. Decides nothing. | fail open, silent |
| `PreToolUse` | `scripts/hooks/block-api-burn.ps1` | `Bash\|PowerShell` (hand-wired) | Denies `gh run watch`, any `gh --watch`, and hand-rolled `gh` poll loops. Every seat draws on one shared 5000/hr GitHub budget, and the seat that pays is not the seat that spent. | fail open, **loud** |
| `SessionStart` | `scripts/hooks/mail-drain.ps1` | -- (hand-wired) | **Renders** this worktree's session mail and leaves it in the inbox. Consuming here would lose mail to a phantom: one measured launch fired six `SessionStart` events and only one session ever submitted a prompt. Decides nothing. | fail open, silent |
| `Stop` | `scripts/hooks/mail-drain.ps1` | -- (hand-wired) | **Consumes** the messages this session displayed, and only those: an exclusive open, a receipt, a move out. A discarded session never reaches `Stop`. Speaks only when it filed something, but every fault path still speaks. Decides nothing. | fail open, silent unless it filed |

| Git hook | Checker | What it decides | Posture |
|---|---|---|---|
| `commit-msg` | `scripts/hooks/claim_check.py` | Refuses a code-touching commit whose **subject** declares `<KIND> #N` when this worktree does not hold the claim on N. | **fail closed** |
| `pre-push` | `scripts/hooks/push_guard.py` | Refuses a direct push or deletion of a protected ref. | **fail closed** on config; fail open with no interpreter |
| `pre-commit` | `scripts/hooks/seq_check.py` | Refuses a commit that reuses a number, skips the index for one, duplicates one, or adds one never allocated to this worktree. **No installer wires this** -- see below. | **fail closed** |

Installers:

| Installer | Wires | Scope |
|---|---|---|
| `scripts/coord/install-coordination.ps1` | session banner, collision gate, announce | **one** user `settings.json` per run, as re-resolving shims |
| `scripts/worktree/install-gate.ps1` | worktree gate | every config dir, as an installed **copy** |
| `scripts/worktree/install-selfheal.ps1` | selfheal backstop | one config dir at a time, as an installed **copy** |
| `scripts/coord/install-git-hooks.ps1` | claim gate, push guard | the clone's shared git hooks directory |

You must wire every script marked hand-wired, plus `seq_check.py`. No installer enables them.

To enable a control without an installer, add it to the appropriate live settings or hook file.

Use these three locations:

| Control | Where it goes |
|---|---|
| Blanket-stage guard, API-burn guard, role-card injector, precompact reprime, mail drain | Copy their tracked rows out of `.claude/settings.example.json` into a real `settings.json`, and replace every loud placeholder path |
| Steering injector | A `settings.local.json` row, per worktree. [Steering](STEERING.md) has it |
| Sequence gate | **Not a settings row at all** -- a `pre-commit` hook you own. [Wiring the pre-commit hook](SEQUENCE-ALLOC.md#wiring-the-pre-commit-hook) has the snippet |

Only `settings.json` and `settings.local.json` supply harness settings. Editing an `.example.` file
enables nothing until you copy its rows into a live file.

Keep `_ccxconfig.py` beside the fail-closed sequence checker. Without that imported module, it exits
1 on every commit before checking sequences.

Supply the Python interpreter yourself. Unlike the other two checkers, this one has no shipped
`/bin/sh` shim.

With sequences configured, `install-git-hooks.ps1` warns that their gate remains unwired. Otherwise
an absent check looks like a passing one.

---

## The harness wiring contract

In `settings.json`, put hooks under the `hooks` object, keyed by event and grouped by matcher.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "pwsh -NoProfile -File \"C:/Users/<you>/.claude/hooks/worktree_gate.ps1\"",
            "timeout": 15,
            "statusMessage": "Checking worktree gate"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "# ccx-coord\n$c = (& git rev-parse --path-format=absolute --git-common-dir 2>$null); ...",
            "shell": "powershell",
            "timeout": 30,
            "statusMessage": "Session coordination"
          }
        ]
      }
    ]
  }
}
```

| Field | Meaning |
|---|---|
| `matcher` | Pipe-separated tool names. `PreToolUse` only. `SessionStart` and `UserPromptSubmit` take none. |
| `type` | `command` for everything here. |
| `command` | Either an absolute path to an installed copy, or an inline shim that re-resolves the script at run time. Both patterns ship; see below. |
| `shell` | Which interpreter runs an inline `command`. The coordination installer writes `powershell`; the copy-installers invoke `pwsh -NoProfile -File` inside the command string instead and omit the key. |
| `timeout` | Seconds. The shipped values are 15 for the gates, 15 for announce, 20 for the collision gate, 30 for the two `SessionStart` hooks. Announce's is that hook's **only** time bound. |
| `statusMessage` | What the user sees while it runs. |

The installers use two wiring patterns:

* Installed copy (worktree gate, selfheal): an absolute path outside every worktree. A script inside
  a checkout vanishes on a branch switch, and a missing script does not block, silently.

  Installed copies can age. `install-gate.ps1 -Status` compares SHA-256 hashes and prints
  `* STALE *` when its copy differs.

  `install-selfheal.ps1` has no `-Status`. It takes `-ConfigDir` and `-HookPath` only, and
  re-copies the source unconditionally. Only `bin/ccx-doctor.ps1` reports a stale selfheal copy.
* Re-resolving shim (banner, collision gate, announce): the command re-resolves the script from
  git's common directory, so nothing falls stale. A shim resolving nothing exits silently,
  byte-identical to a healthy hook with no peers. Its installer writes a receipt and `-Status`
  re-resolves live.

The client combines user, project, and local hooks, retaining project guards. These installers use
user scope so hooks reach worktrees without merging project settings from another branch.

`install-coordination.ps1` identifies entries by the command substrings `ccx-coord` and
`ccx-announce`. Neither marker may contain the other, or uninstall can remove both.

Renaming a marker leaves existing installs unrecognized.

On 2026-08-11, tests checked all ordered pairs of four markers in the
[session mail](SESSION-MAIL.md) implementation. Neither direction contained another marker.

Appending a suffix can violate the rule: `ccx-mail-urgent` contains `ccx-mail`. Installing the
second can strip the first's row and disable it.

### Backgrounding is gated, so `asyncRewake` alone can block the session

A waiting hook needs both `async` and `asyncRewake`. Background execution requires
`isInteractive || hasStreamingInput`, so `claude -p` instead blocks synchronously for the timeout.

Add those flags only to hooks designed to wait. An asynchronous `PreToolUse` check cannot block the
pending tool call; keep existing gate rows unchanged.

Give the harness 1200 seconds for a watcher that waits 900 seconds. Killing it at its own deadline
can look like a completed check that found nothing.

This was measured on 2026-08-11 with harness v2.1.221 in the [session mail](SESSION-MAIL.md)
implementation.

---

## The output contract

### The `hookSpecificOutput` wrapper is mandatory

The harness silently ignores bare `{"permissionDecision":"deny"}` and runs the tool. This was
measured in the source project and reported upstream.

All denials here use one helper to preserve the required wrapper.

```powershell
$payload = @{
    hookSpecificOutput = @{
        hookEventName            = "PreToolUse"
        permissionDecision       = "deny"
        permissionDecisionReason = $Reason
    }
}
[Console]::Out.Write(($payload | ConvertTo-Json -Compress -Depth 6))
exit 0
```

For a diagnostic, emit `additionalContext` without `permissionDecision`. Adding a decision can turn
a notice into an unintended block:

```powershell
@{ hookSpecificOutput = @{
      hookEventName     = "PreToolUse"
      additionalContext = "[collision] The collision gate could NOT check this edit ..."
} } | ConvertTo-Json -Compress -Depth 6 | ForEach-Object { [Console]::Out.Write($_) }
```

`SessionStart` uses the same wrapper with `hookEventName = "SessionStart"`. The exception,
`session-context.ps1`, prints plain text directly into starting context.

### Never carry a decision in the exit code

Harness hooks here exit 0 and express decisions in JSON. A nonzero exit other than 2 silently allows
the call, including when a hook script is missing.

* Think hard before adding `#Requires` to a hook whose failure mode matters. It is raised before the
  body runs and exits non-zero, so the file's own error handling never gets a turn.

  `announce-session.ps1` and `steer-inject.ps1` carry none. On `UserPromptSubmit` a failure can
  block the user's prompt outright.

  The three PreToolUse gates require `#Requires -Version 7.3`. Below 7.3, they refuse to start
  rather than risk partially parsed code. The cost is that on PowerShell 7.0-7.2 all three are
  inert, and inert reads as an allow.
* Do not put a throwing expression in a parameter default: defaults bind before line 1, so a throw
  there escapes the script's `try` /`catch`. Shipped twice as `Join-Path $env:USERPROFILE ...`,
  null off Windows. Resolve home null-safely inside `$( ... )`; a guard's parameters get *no*
  default.

In a parameter default, use `$( if (...) {...} else {...} )`, not `( if ... )`. Bare parentheses
make PowerShell treat `if` as a command, failing before the script body.

That broken default shipped despite passing tests. Every test supplied `-ReposFile`, preventing
PowerShell from evaluating the default.

`tests/test_worktree_gate_no_args.py` now invokes the gate without arguments and requires a denial
in a governed root. That checks both default evaluation and the installer's file location.

### A shim ending in `break` discards the one exit code that carries

A hook using exit 2 depends on every wrapper preserving that code. The shared shim ends
`& $s; break` instead of explicitly forwarding it.

A stub-hook test measured these results on 2026-08-11 in the [session mail](SESSION-MAIL.md)
implementation:

| Shim spelling | Stub exits | Process exit code |
|---|---|---|
| `exit $LASTEXITCODE` | 2 | 2 |
| `exit $LASTEXITCODE` | 0 | 0 |
| `& $s; break` | 2 | **1** |
| `exit $LASTEXITCODE` | script absent | 0 |

The third row reports 1 instead of 2. The harness discards the payload and logs a hook error, hiding
the intended signal.

The fourth row checks a missing script outside a repository. Put `exit` inside the `Test-Path`
branch so fall-through exits 0 without forwarding an old code.

### The git-hook contract

`install-git-hooks.ps1` places `/bin/sh` shims beside Python checkers. Each tries `CCX_PYTHON`,
`python`, then `python3`; exit 0 allows and exit 1 refuses.

Use LF endings without a byte-order mark (BOM). A CR shebang makes `/bin/sh` report "bad
interpreter".

Without an interpreter, a shim reports the problem on stderr and exits 0. Both gates then allow that
commit or push.

`-Status` runs the candidate interpreter to detect Windows app-execution aliases that resolve but do
nothing.

Only `commit-msg` receives the commit message. Putting the claim gate in `pre-commit` would leave it
installed but unable to enforce its rule.

`install-git-hooks.ps1` never writes `pre-commit`, which another tool may own. One framework
renamed a foreign hook and dispatched it through a shim that blocked every Windows commit.

Removing that shim restored commits. The sequence gate still needs `pre-commit` and ships unwired.

---

## House rules

### Declare the posture in the header, in one line

A hook header should state `POSTURE: FAILS OPEN` or the fail-closed form, with a reason. Collision,
blanket-stage, and steering hooks do this.

The worktree gate states its posture 30 lines into `.DESCRIPTION`; move it to the opening when
editing that header.

Choose the failure behavior to match the control:

* The collision gate fails open because it prevents rework. It must never be the reason a session
  cannot work.
* The worktree gate fails open too, but for a blunter reason: a guardrail that wedges all work gets
  uninstalled, and then it protects nothing.
* The claim gate and the sequence gate fail closed. A malformed claim reads as unclaimed. A git
  failure refuses the commit rather than being swallowed into "nothing is staged", which reads as a
  pass. Both are recoverable in one command. A false clean is not, because nobody looks.
* The push guard defaults to the strict direction when it cannot read its configuration, and
  announces on stderr when it is configured off.

The header must tell readers what happens when the check breaks.

### Fail open, but never silently

For weeks, collision-gate failures exited 0 with empty stdout. That matched a successful check
finding no peers in the file, so sessions mistook failures for an all-clear.

Give failure a distinct output:

* Emit a named notice on the fault path (`payload-unreadable`, `overlap-empty`, `overlap-failed` ),
  and keep the allow posture. Rate-limit per reason, so a persistently broken dependency does not
  inject a notice into every single edit.
* Fail toward noise. If the rate-limit stamp cannot be read or written, emit the notice anyway.
  Failed throttling must leave the warning visible.
* Bound the throttle in both directions. A stamp dated in the future reads as eternally fresh and
  suppresses the notice forever: the same silence, now self-inflicted.
* Scope the throttle per worktree, not per repository. A repo-wide stamp means the first session to
  hit a broken gate silences it for every other session. Those sessions read that silence as
  "checked, nobody is here", which is precisely the defect the notice exists to remove.
* Where the failure happened before the hook could load its helpers, the notice cannot be JSON.
  Write it to stderr, which is not parsed as a decision, and to the deny log.

  `worktree_gate.ps1` uses both stderr and the deny log. `block-blanket-git-stage.ps1` has no log
  function and prints only `NOT enforcing` on stderr.

  Its different case also means an uppercase search finds only the first gate.

### Every exit from a stateful hook is a state transition

A hook that saves state carries each invocation's result into the next. Every exit, including guards
and the outer catch, can change that state.

List every outcome and route exits through one state writer. Test the outcome table, checking final
state and whether each counter advances.

Both notice-throttle stamps and announce's backoff schedule need those checks.

An August 2026 check of the separate [session mail](SESSION-MAIL.md) implementation found seven
post-guard exits with individual state writes. Four wrote the wrong state:

- One exit left the marker armed. On the third consecutive prompt, the kill ladder fired and began
  repeating a false "lookup did not return" hourly.
- That ladder never advanced the counter its own cap reads, so nothing could bound it.
- One exit never cleared the backoff floor.
- The outer catch left state armed entirely.

A one-line mutant still passed the full 50-test suite.

Three review rounds each found the previous defect and missed the next. They compared branches with
old failures instead of checking the shared state rule.

Single-call tests miss state carried into later calls. Tests asserting only that nothing happened
can pass a hook that does nothing forever.

### `[]` is not the same as nothing, and the fix belongs in the producer

Piping an empty array to `ConvertTo-Json` sends no objects, so the command emits nothing. `-AsArray`
cannot help because it only shapes existing output.

The helper therefore gave the same zero bytes for "no peers" and "no answer".

Always emit a value for completed checks, using `[]` for no hits. Consumers can then treat silence
as failure, as this collision-gate comment requires:

```powershell
$text = (@($raw) -join "`n").Trim()
if (-not $text) {
    Write-Unresolved "overlap-empty" "the overlap script produced no output at all (a resolved 'nobody else' is '[]', not nothing)"
}
```

An empty config list is also an explicit choice. `"protectedRefs": []` disables protection and
reports it on stderr; an absent key uses defaults.

The claim gate applies the same distinction to `docPaths.prefixes: []`.

### The first rule to fire is the only one that speaks

`Write-Deny` exits immediately, so source order decides which rule handles a case. Later matching
rules never run:

* Order rules by cost and blast radius, and say why in a comment. The dispatch rule is checked first
  in the worktree gate because it is the cheapest place to stop a fan-out. Unstopped, that fan-out
  runs for an hour and reports success while writing nothing.
* Never let two rules each assume the other owns a case. It has shipped: one rule resolved the
  target from `-C` or cwd only and declined. The other resolved a `cd`, then declined with a
  comment saying the first rule owned it. A family of tree-swapping commands was allowed.

### Log every deny

Before `Write-GateLog`, gate decisions vanished after stdout and exit 0. Nobody could measure
prevented drift or compare one false refusal per day with one per thousand.

The log adds evidence for those judgments.

Each tab-separated record carries at least:

* the timestamp, the hook version, and the 12-character digest of the gate file that adjudicated;
* the pid, the rule, the tool, and the cwd;
* a short detail each rule composes.

The manually maintained version label has been wrong before. It cannot by itself identify the copy
that ran.

Apply these three log rules:

* Never log the raw command or file contents. Each rule passes a detail it composed (a verb, a
  target path), so an argument carrying a secret cannot reach a plaintext log.
* One record is one line, always. The detail is derived from tool input, so strip `\r`, `\n` and
  `\t` and cap the length before composing. Otherwise a crafted path forges extra records in a log
  whose whole purpose is counting.
* Expect contention. Every session on the machine appends to one file. `Add-Content` silently
  dropped records under load, and a lossy counter is worse than none because it reads as a
  measurement. Retry a bounded number of times, then give up quietly: the deny matters, the receipt
  does not.

Logs also let a parent inspect subagent denials, which do not reliably reach it through tool output.

### False positives are the expensive failure

False denials encourage operators to bypass a gate. The verb scanner incorrectly refused these
commands:

* `git status` followed by a newline and `echo about to merge stuff` -- denied on `merge`, from
  prose on line two.
* `echo "git checkout main"` -- denied.
* `git commit -m "chore: clean up dead code"` -- denied on `clean`.
* `git restore <two files>`, run from a worktree, denied as "would change the working tree of the
  SHARED PRIMARY". A later `cat <primary>/...` in the same compound command had named the primary.

The final example wrongly told the operator that `git restore` threatened the shared primary. False
descriptions make future warnings harder to trust.

The shipped fixes address each parsing error:

* Split into simple commands with a quote-aware walker, not a regex -- `git commit -m "a; b"` must
  not be cut in half.
* Keep raw and scan forms of each segment together. Parse paths from raw text, and verbs from the
  scan form with quoted spans blanked. A verb decided from the raw string produces every false
  positive above; a path parsed from the blanked string is erased.
* Recurse one level into interpreter arguments -- `pwsh -Command "..."`, `bash -c "..."`,
  `cmd /c "..."`. Those are quoted, but they are code that runs. Blanking them turned a
  long-standing deny into an allow when it was tried.
* Require a verb to be a whole subcommand. `\bmerge\b` also matches `merge-base` and `merge-tree`,
  which are read-only and are exactly what a session should be using instead.
* Match a path only at a directory boundary. A sibling worktree named `<primary>-<task>` contains
  the primary's path as a prefix, so a plain substring test flags it.
* Write ALLOW-asserting tests: a multi-line command, an echoed command, a commit message containing
  a blocklisted verb, and a path that merely resembles a governed one.

After structural checks, an uncertain cheap test should deny. State that choice and its reason in a
code comment.

### Enumerated coverage means every hole is silent

Unlisted verbs pass silently. The gate once missed two-token `worktree` actions, including
destructive `git worktree remove`.

It also missed `sparse-checkout`: the pattern needed whitespace before `checkout`, but the token
contains a hyphen.

Settings matchers have the same risk. An unlisted tool never invokes the hook.

* Prefer deny-by-default where you can.
* Where you cannot, assert against an expectation, never a count: "3" informs nobody who cannot say
  whether 3 is right. `install-gate.ps1 -Status` diffs the installed script's rules against wired
  matchers, reporting `UNWIRED` (never fires), `stray` (matched, ignored) and `opt-in` separately.
* Express a rule so the tripwire can see it. Rule 4 is written as `$tool -in @("EnterWorktree")`
  rather than a string comparison, specifically so the wiring test parses it as handled. A rule has
  shipped implemented-with-no-matcher before.

### One splitter, one target resolver

Two gates once used separate command splitters. One missed four cases:

- it cut a quoted `;` in half;
- it did not blank quoted spans;
- it did not look inside interpreter arguments;
- it required a segment to start with a bare `git` token, so `/usr/bin/git add -A` walked past.

Both now dot-source `scripts/hooks/_command.ps1` for splitting and `Test-CcxGitInvocation`, plus
`_gittarget.ps1` for target resolution. After hardening shared syntax, check every sibling parser.

Parse git flags case-sensitively: PowerShell `-match` once confused lowercase `-c name=value` with
uppercase `-C <path>`. Consider `--git-dir`, `--work-tree`, and their environment equivalents as
targets too.

### A command-string gate is a guardrail, not a boundary

An agent-written script can bypass verb matching with `pwsh -File whatever.ps1`, including an
approved repair script. `gh pr checkout <n>` also avoids every `git` token.

State this limit in the header. Do not build a full shell parser into the splitter; use commit-time
tree inspection for shell-written files.

Check that any named backstop enforces the rule you need. One header cited a `pre-commit` dispatcher
whose linters never checked which checkout received writes.

Only the refusal text asked the session to comply.

### State the cost of an always-on hook

Measurements from the source project:

* the coordination shim costs roughly half a second on every user prompt in every repository;
* the peer lookup costs about a second more, where it runs;
* a `PreToolUse` hook on `*` costs a process spawn per tool call, roughly a third of a second.

Those costs led to these shipped choices:

* Order cheap guards before expensive lookups, so the expensive one runs only when it can matter.
* Back off deliberately, and publish the schedule. Announce re-checks for peers at most once a
  minute for its first ten checks, then once every ten minutes, and stops entirely after forty.
* An occasional-use feature does not belong on `*`. `steer-inject.ps1` is deliberately not wired in
  any shared settings file; enable it per worktree in that worktree's local settings when you
  actually want it.
* Gate a user-global hook on the repository having opted in, so it does not fire in unrelated
  projects. Check for `ccx.config.json`. Script presence wrongly includes half-installs and misses
  scripts stored elsewhere.
* Give the harness a `timeout` that comfortably exceeds the hook's measured cost. The hook cannot
  tell whether timeout kills it or only stops waiting. Do not depend on knowing which occurred.

### Test the real pair, not stubs

The first empty-output fix blocked ordinary edits to untouched files. Tests passed because their
stubs returned JSON the real helper never produced.

* Run the real components together at least once before shipping a contract change between them.
* Parameterise the seam so a test can drive the real gate against a fixture, rather than
  re-implementing the rule. `collision_gate.ps1` takes `-OverlapScript`, `-StateDir` and
  `-PathOverride` for exactly this; a test that asserts a copy of the rule proves nothing.
* Isolate shared state per test. A throttle sharing one directory with the suite would make the
  first test's notice suppress the second's.
* When two components share a field, version-lock them and say so. The gate reads overlap's
  `MatchedDirty`; a missing field means dirty. A stale producer therefore causes excess refusals
  rather than allowing real collisions.

---

## Establishing what a hook actually does

Source describes possible behavior. The installed copy, settings matcher, and rule order determine
what actually runs.

One gate in the source project had 85 passing tests while sessions ran a copy days behind. Removing
a source rule can likewise leave stale enforcement active despite green tests.

Check the decisions made by the installed hook.

Run `bin/ccx-doctor.ps1`. It checks installed hashes, live markers, and matcher coverage, then
attacks controls and reports untested paths.

Each control gets a verdict. Where possible, the doctor bases it on a refusal it provoked.

Three paths remain untested: collision refusal needs a live peer, PowerShell cannot prove announce
delivery, and steering has no attack test. The doctor names these each run.

To test a control manually, send crafted input to the installed hook:

```powershell
$payload = @{
    tool_name  = 'Write'
    cwd        = 'C:/path/to/a/governed/primary'
    tool_input = @{ file_path = 'C:/path/to/a/governed/primary/README.md' }
} | ConvertTo-Json -Compress -Depth 6

$payload | pwsh -NoProfile -File "$HOME/.claude/hooks/worktree_gate.ps1"
```

A refusal prints JSON with `hookSpecificOutput.permissionDecision` on stdout. Any other result,
including silence, means the installed copy did not refuse.

Use these four rules for manual probes:

1. Pair every attack with a negative control. A write outside every governed root, and a write into
   a nested worktree, must both be ALLOWED. Without the negative, "refused correctly" and "refused
   because it could not import its own substrate" are the same result.
2. Make the probe itself fail loudly. In `bin/ccx-doctor.ps1`, four attack payloads carried no
   `tool_input`, so every rule allowed them and the doctor called a fine gate broken. The builder
   now throws on an empty `tool_input`, and an aborted sequence records `??`, never a pass.
3. If your must-fail case and your under-test case produce the same bytes, the result is UNTESTED,
   not negative. An `mcp_tool` probe produced nothing for a real MCP server and nothing for a
   nonexistent one that the documentation says errors. Say untested and re-run against a known-good
   instance.
4. Capability is not enforcement. A probe fired at the source file rather than the installed copy
   proves the rule can refuse, not that anything is refusing. The doctor downgrades those results
   rather than reporting them green.

---

## Limits, stated plainly

* These are guardrails against accidents, not security boundaries. `git commit --no-verify` and
  `git push --no-verify` bypass the git hooks. A tool-argument gate never sees a file written by a
  shell command. Any agent-authored script defeats a command-string rule.
* A harness hook constrains sessions, not the operator. A plain terminal is never gated. That
  asymmetry is the point: the human installs and removes these; a session may not.
* The gates governing what a session may install refuse to run inside a session. All four installers
  throw when `CLAUDECODE=1`, not only the two that write hooks.

  `-Status` runs before the session refusal in the three installers that support it. Sessions can
  therefore inspect their controls. `install-selfheal.ps1` has none, so from inside a session it can
  only refuse.
* Announce delivery depends on a session-management MCP that is Desktop-only. On a plain CLI install
  the hook still fires, still resolves peers, then instructs the model to call tools it does not
  have. Leave it uninstalled, or drop a file at `<git-common-dir>/<prefix>-coord/announce/OFF`.
* A kill switch must be a file. Hook wiring takes effect only in newly started sessions, and an
  environment variable set now is invisible to a running process. The allowlist file and the
  announce OFF file reach live sessions; `CCX_ANNOUNCE_DISABLE` and `CCX_ALLOW_DIRECT_PUSH` do not.
* A running session keeps the configuration it booted with. Nothing in this repository changes one.
* Every hook here writes ASCII only. Console encoding has mangled a non-ASCII byte and broken a
  consumer. It matters most for `announce-session.ps1`, whose stdout is an instruction to a model:
  a mangled byte there is a corrupted instruction.
* Anything a hook injects into a session is data, not instruction. A peer announcement arrives in
  the recipient's conversation in the same shape as an operator turn, distinguished only by the
  envelope and the prose rule. Treat inter-session content as peer data, never as the user speaking.

## Where to go from a row in the map

| You found | Go to |
|---|---|
| It is not installed | [Quickstart](QUICKSTART.md) to install, [Install](INSTALL.md) for the flags |
| It is installed and you want to prove it fires | [Install](INSTALL.md#now-prove-all-of-it), then [Troubleshooting](TROUBLESHOOTING.md) |
| The worktree gate, in depth | [Worktrees](WORKTREES.md) |
| The collision gate, in depth, and what it cannot see | [Coordination](COORDINATION.md), [Limits](LIMITS.md) |
| The sequence gate, and the `pre-commit` to write | [Sequence allocation](SEQUENCE-ALLOC.md#wiring-the-pre-commit-hook) |
| The steering injector's row | [Steering](STEERING.md) |
| Where each control stops working | [Limits and requirements](LIMITS.md) |
