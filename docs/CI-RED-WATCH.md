# Noticing a red without a session watching for it

<a id="tldrbluf"></a>

The cron watcher polls for pull requests labelled red and starts one session per failure to identify
its cause. The script makes no model calls.

Without a watcher, a failure waits for a long-lived session to notice it. That session may already
be busy with the operator.

Your repository must label failing pull requests first. Add `ciRed` to `ccx.config.json`,
then schedule [`scripts/cron/watch-ci-red.ps1`](https://claude-multisession.pages.dev/scripts/cron/watch-ci-red.ps1); test with `-DryRun`.

---

## Nothing tells a session that a check went red

GitHub cannot directly notify a session. No event subscription reaches a seat.

Previously, one long-lived session had to poll, notice a failure, and spawn a seat to investigate.
That made the operator's session a single point of failure.

Autofix wakes only live sessions, while workers here stop when done. When it does run, it tells a
builder what failed without identifying who owns the failure.

## Your repository sends the signal by labelling

The repository labels a pull request when a required check fails. The watcher polls for that label
without reading check results.

One list call can find labelled requests across all open pull requests. Fetching each request's
checks costs too much for a poll every minute.

The label reduces polling cost; GitHub still cannot push a message into a session.

Set the label with `ciRed.label`, or use the `ci-red` fallback. Every receipt identifies
which source supplied the name.

## What a tick costs

A quiet repository uses no model tokens; the script still makes API calls.

| Watcher | Cost per waiting minute |
|---|---|
| A resident session on a three-minute heartbeat | 2,108 metered tokens |
| A resident session on a ten-minute sleep loop | 22,275 metered tokens |
| This script | Zero model tokens, plus three API calls |

A model starts only after the watcher finds a failure. Using a model to decide whether to spawn
would restore the resident-session cost.

## Set it up

Add the block to `ccx.config.json`. Every key is optional and every one has a default.

```json
"ciRed": {
  "label": "ci-red",
  "repo": "you/your-repo",
  "claimPrefix": "ci-red-pr",
  "spawn": { "command": "claude", "args": ["-p"] }
}
```

| Key | Default | Controls |
|---|---|---|
| `label` | `ci-red` | The label your repository applies when a required check fails |
| `repo` | the `origin` remote | Which repository to poll, as `owner/name` |
| `claimPrefix` | `ci-red-pr` | The claim key stem, so one clone can watch two repositories |
| `spawn.command` | `claude` | What starts a seat. Give a full path if a shim resolves it |
| `spawn.args` | `["-p"]` | Fixed arguments. The generated prompt is appended after them |

Then schedule it. On Windows, one line registers a task that ticks every five minutes:

```
schtasks /Create /TN ccx-ci-red /SC MINUTE /MO 5 /TR "pwsh -NoProfile -File C:\path\scripts\cron\watch-ci-red.ps1"
```

Run it by hand first, with `-DryRun`, and read the receipt.

## It will not start two seats on one red

Two seats investigating one failure may each assume nobody else has done the work.

The watcher uses the existing [`scripts/coord/claim.ps1`](COORDINATION.md) registry. It adds two guards because the registry
alone does not cover repeated ticks:

1. Across sessions, the claim's exclusive file create is the mutual exclusion. A peer holding the
   key makes the take fail, and the watcher skips that red.
2. Across ticks, it is not. Re-taking a key you already hold is a success on purpose, so a session
   can re-assert its own claim. Every tick runs from the same worktree, so every tick would re-take
   its own claim and start a second seat.

The watcher locks the whole pass and checks for an existing claim file before taking the key.

After taking the claim, it checks that the expected file exists. The watcher repeats
`claim.ps1`'s path formula, so a missing file may reveal drift between them.

If the expected claim file is missing, the watcher refuses to start a seat and reports why. The seat
must release its own claim when done; its briefing supplies the command.

## A held claim does not mean anyone is still working the red

A held claim alone cannot establish whether the dispatched seat is still alive.

Claims never expire and name the watcher's checkout as holder. Existing liveness probes see that
checkout, which remains present for cron ticks.

A seat that died one second after spawning therefore looks like one still investigating. The claim
can block later ticks indefinitely without anyone handling the failure.

Each spawn writes a dispatch record beside the journal. It records the seat's process id, process
start time to detect id reuse, and journal length at briefing time.

Later ticks use the record to report one of these states:

| The tick finds | It says | Exit |
|---|---|---|
| The seat process is still running | `ALREADY-CLAIMED` | 0 |
| The process is gone, or its id now belongs to something else | `SEAT-GONE` | 1 |
| No dispatch record, or a start time it cannot read | `SEAT-UNKNOWN` | 1 |
| The claim file itself cannot be read | `SEAT-UNKNOWN` | 1 |
| The key is held by another worktree | `ALREADY-CLAIMED` | 0 |

Start times use a one-second comparison window. On Linux, .NET derives start time from a derived
boot instant, so separate calls need not return exactly equal values.

An equality check marked a live seat gone on the ubuntu leg. That false report could lead someone to
release a working seat's claim.

The window can err toward `ALREADY-CLAIMED`, costing a tick. Seats run for minutes, so reuse of the
same id within one second is outside this case.

`SEAT-GONE` reports whether the journal grew. No new entry means the failure remains
unattributed; a new entry means the seat left a verdict but did not release its key.

The watcher never releases or respawns based on this reading. A seat may have finished before
exiting without a release.

Releasing that key could duplicate a completed investigation. Automatic respawn could start another
session every tick while the label remains.

The run reports the evidence, fails, and prints the release command for you.

## A missing label is not an all clear

Measured 2026-08-31: a nonexistent `CLAUDE_CONFIG_DIR` makes `claude agents --json` return an empty list and
exit 0. A mistyped root looks exactly like an empty fleet.

The watcher checks three similar failure cases and requires a confirming response:

| Check | The reading that must come back |
|---|---|
| The repository is reachable | The API echoes the same full name back |
| The label exists on your repository | The API echoes the same label name back |
| The open pull request list is readable | A list, of which zero is a valid length |

A query for a nonexistent label returns an empty list and exit 0. Without checking the label itself,
missing setup would look like no failures.

The watcher fetches open pull requests separately and requires each finding to appear there. It
reports and skips any finding absent from that list.

The open list uses `-Limit`. If the list fills that limit, it may omit more open requests.

A labelled request missing from a capped list may be closed or merely beyond the cap. The watcher
cannot distinguish those cases.

It reports `NOT-OPEN-UNVERIFIABLE`, starts no seat, and ends `INCOMPLETE`. Raise `-Limit` above
the open pull request count.

A check with no confirming reading ends the run with `CANNOT-LOOK`, exit 2. Every run names the
repository, label, their sources, and open pull request count scanned.

## The seat does not inherit your account

By default, a child inherits its parent's full environment. On 2026-09-04, this watcher passed down
all 96 parent variables.

Account and billing variables can silently redirect a child's usage:

| Variable | What it does to a seat that inherits it | What the watcher does |
|---|---|---|
| `CLAUDE_CONFIG_DIR` | Names the account the child bills, so every seat bills the watcher's account instead of its own | Removed |
| `ANTHROPIC_API_KEY` | Switches Claude Code onto pay-as-you-go API billing, announcing nothing | Removed |
| `ANTHROPIC_AUTH_TOKEN` | The same switch under a second name | Removed |
| `ANTHROPIC_BASE_URL` | Points the child at a different host | Passed through, and named in a warning |

This machine sets `ANTHROPIC_BASE_URL`, possibly for an intentional proxy. The watcher preserves it to
avoid breaking a working spawn, and warns so you can decide.

Every run prints what it removed, even when the answer is nothing:

```
           child env: removed CLAUDE_CONFIG_DIR
           WARNING: ANTHROPIC_BASE_URL is set in this process and is passed through to every child
```

The receipt also appears when there are no results. This distinguishes no account variable being set
from the removal step never running.

To select an account, pass a `-ChildEnv` hashtable to `Start-Child`. The watcher applies
these deliberate settings after removing inherited account variables.

### The three exit codes

| Code | Status | What it means |
|---|---|---|
| 0 | `OK` | It looked, and every red it found reached a seat |
| 1 | `INCOMPLETE` | It looked, and at least one red did not reach a seat |
| 2 | `CANNOT-LOOK` | It could not establish what it was looking at |

Exit 2 means the watcher could not inspect the state. Taking a claim then failing to find it is an
action failure: exit 1, with drift named as the reason.

A tick blocked by a sibling's pass lock exits 2. It examined nothing and cannot report a scan count.

## The seat starts fresh and keeps a journal

Workers exit after completing their turns. The reference fleet had 740 session records and 2 live
sessions, so there was usually no worker to wake.

The watcher starts a fresh session on the surviving branch and worktree, allowing it to continue the
existing work.

The new session lacks the previous failure's context. Each spawn appends to `<state-root>/ci-red/pr-<number>.md`; the
prompt requires reading it first and writing it last.

The seat identifies whether the failure belongs to the pull request, trunk, flake, or merge queue.
Only the pull request's own failure goes back to the builder.

## What it does not do

Your repository owns labelling. The watcher reads that contract without defining or applying labels.

The seat decides who owns each failure; the script cannot make that judgment.

A failing request without the label is invisible to the watcher. Its coverage depends on your
labelling setup.

## Related

- [Coordination](COORDINATION.md) -- the claim registry the watcher takes a key from
- [Usage awareness](USAGE-AWARENESS.md) -- why an unproven reading has to refuse rather than report
- [CI for leaders](CI-FOR-LEADERS.md) -- what done means when the author cannot vouch for the change
- [Every script](SCRIPTS.md) -- the full inventory, including this one

The [handoff diagram](KORUS-BUILD.md#g04) still shows a Regulator receiving a failed check. That
seat retired on 2026-09-19 and the diagram has not been redrawn.
