# Plugins

## TLDR/BLUF

**What this is.** This repository is a Claude Code plugin marketplace with three plugins.

| Plugin | What it does |
|---|---|
| `korus-fleet` | Opens a fleet board pane, and can show your seat and usage on the status line. Read-only. |
| `korus-card` | Runs the repository's own role-card hook at session start, and its reprime after a compaction. |
| `korus-inbox` | Gathers what waits on the owner from every session: open questions and refused commands. |

**Who it is for.** Anyone running KORUS seats who wants the seat, the fleet and the owner's queue
in view without running a script by hand.

**The one thing to get right.** CI cannot run the plugin tests. Run `claude plugin test` yourself
before you push a change to a plugin.

---

## What the plugin shows

| Where | What it shows |
|---|---|
| Status line | **Off by default.** Turn it on with the `statusLine` option, below. When on: `seat <x> \| ctx N% \| <limit> N%`, with one `<limit>` part per rate limit the session reports, for example `seat manager \| ctx 26% \| 5h 6% \| 7d 0%`. The seat comes from `.claude/seat.local.txt`, which `scripts/coord/seat.ps1 -Declare` writes. Usage comes from the session. `5h` is its `five_hour` limit and `7d` its `seven_day` limit; any other limit shows under the name the session gives it. |
| `/fleet` | Opens a pane that runs the fleet script with `-Json` and lists every record whose `State` is `RUNNING`, newest first. |

The status line says `no seat marker` when the marker file is missing, and `undeclared` when it is
empty. When on, it refreshes every minute and after each turn. When off, it draws nothing and reads
no usage.

The pane refreshes every five minutes while it is open, and on its Refresh button. The pilot this
plugin came from timed one run of the MessageFoundry fleet script at about 26 seconds. That reading
was not repeated here, and it is why the pane does not poll faster.

**It writes nothing.** It reads one file and runs one script, and writes to no file and no peer.

`tests/test_the_plugin_marketplace_resolves.py` fails on a source that reaches for `fs.write` by a
plain spelling. It is a token scan, so an alias built another way gets past it.

## Install it

Run these inside a Claude Code session, from any config root.

```
/plugin marketplace add MEFORORG/korus
/plugin install korus-fleet@korus
```

A local clone works as the marketplace too. Pass its path to `/plugin marketplace add` in place of
`MEFORORG/korus`.

## The status line is an option

Set `statusLine` to true in `/config` to draw the status line. It defaults to false, so a fresh
install shows nothing there. Like every option, it is stored under `pluginConfigs` in settings,
keyed by the plugin's name. The `/fleet` pane works either way.

## The fleet script is an option

The pane runs `scripts/coord/fleet.ps1` by default. The path is relative to the session's working
directory, so it resolves inside whichever repository the session is in.

Set the `fleetScript` option in `/config` to point it elsewhere. It is stored under
`pluginConfigs` in settings, keyed by the plugin's name.

**Where the script is missing, the pane says so and names the path.** It runs nothing in that case.
The message reads `fleet script not found: <path>`.

## The JSON contract

The pane reads this shape from the script's standard output, and nothing else.

```
{
  "receipt": {
    "renderedAtUtc": "<string>",
    "liveSessionsInRepo": <number>,
    "stopConditions": "<string>" | ["<string>", ...] | null      (optional)
  },
  "rows": [
    { "Seat": "<string>" | null, "Box": "<string>", "Branch": "<string>" | null,
      "State": "<string>", "AgeHours": <number> | null }
  ]
}
```

`plugins/korus-fleet/types/index.d.ts` declares the same contract as `FleetJson`. Change both in one
commit, or the page and the code disagree.

**Two fields take more than one shape, because the MessageFoundry fleet script prints them that
way.** Its `stopConditions` is a list, empty when nothing is wrong. Its `AgeHours` is null for a
record whose age it could not read.

An empty list or string means no stop condition. A row with no age draws `?` and sorts last.

| Output | What the pane shows |
|---|---|
| The shape above | The receipt line, any stop condition in yellow, and every `RUNNING` row. The pane scrolls when they do not fit. |
| The shape above and a non-zero exit | The same, under a yellow line: `WARNING: <path> exited <code>; the rows below may be incomplete` |
| Not JSON | `<path> output was not JSON` |
| JSON of another shape | `<path> output does not match the fleet JSON contract` |
| No output and a non-zero exit | `<path> exited <code> with no output` |

## What CI checks, and what it cannot

| Check | Where it runs |
|---|---|
| `claude plugin validate .` and `claude plugin validate plugins/korus-fleet` | **Your machine only.** |
| `claude plugin test plugins/korus-fleet` | **Your machine only.** Neither `gates` runner has the `claude` CLI. |
| The marketplace parses, every listed source exists, each plugin names itself as listed, its hooks modules exist, every file is ASCII, and no source reaches for `fs.write` | CI, through `tests/test_the_plugin_marketplace_resolves.py`. |

**The two option tests need Claude Code 2.1.284 or later.** Measured 2026-10-02 with `claude plugin
test plugins/korus-fleet`, on the commit that added this sentence.

Under 2.1.283 the kit passes the plugin its manifest defaults, not the test's options. So 17 pass
and the 2 option tests fail. Under 2.1.284 all 19 pass.

Run the plugin tests from the repository root:

```
claude plugin test plugins/korus-fleet
```

## korus-card: the role card and the reprime, with no paths to edit

`korus-card` runs two of this repository's own hooks at every session start. The role card comes
back at each start, including after a compaction. The reprime speaks only after a compaction.

It is the documented route for both. The rows in `.claude/settings.example.json` are the fallback,
for a config root that cannot take a plugin. Those rows need an absolute path typed in by hand, and
a row with the placeholder left in runs nothing and says nothing.

### Install it

Run these inside a Claude Code session, from any config root.

```
/plugin marketplace add MEFORORG/korus
/plugin install korus-card@korus
```

### What it runs, and where it stays silent

Both rows call one shim, `plugins/korus-card/hooks/run-project-hook.ps1`. The shim runs the copy of
the script in the repository the session is in. The plugin carries no copy of either script,
because a copy drifts from the scripts it was taken from.

The shim prints nothing, and runs nothing, in any of these cases.

| Case | Why |
|---|---|
| The repository has no `ccx.config.json` at its root | A user-scope install fires in every repository on the machine. [Hooks](HOOKS.md) says to gate on that file. |
| The repository has no `scripts/hooks/<script>` of its own | There is nothing to run. |
| A settings file already runs that script at `SessionStart` | The project's own wiring wins, so the card is not injected twice. |

The third case reads at least the project's `.claude/settings.json` and `.claude/settings.local.json`,
and the user `settings.json`. Each script is checked on its own.

A `SessionStart` command counts as wiring when it names the script by a path that exists, through a
variable, or with no directory at all. A row that runs nothing does not count, so the plugin still
speaks. That covers a row with the example's placeholder left in, and a path to a deleted checkout.

**The shim adds no compaction guard.** `precompact-reprime.ps1` decides for itself, and a second
guard could disagree with it. The reprime used to run on `PreCompact`, whose context output the
harness refuses. It now runs at `SessionStart` and checks `source` itself.

### What it needs

`pwsh` on `PATH`, because both rows start it by name. On a machine without it, each row fails as a
hook error, and the session goes on without a card.

### What CI checks for it, and what it cannot

| Check | Where it runs |
|---|---|
| `claude plugin validate plugins/korus-card` | **Your machine only.** |
| `claude plugin test plugins/korus-card` | Nothing to run. The plugin has no hooks module, and the test kit runs no settings-style hook. |
| Each row runs a shim that exists, and every file is ASCII | CI, through `tests/test_the_plugin_marketplace_resolves.py`. |
| The card arrives where nothing wires it, is silent where something does, and the reprime keeps its own guard | CI, through `tests/test_the_korus_card_plugin_runs_the_projects_own_hooks.py`, which drives the real rows over a throwaway repository. |

## korus-inbox: what waits on the owner in every session

`korus-inbox` collects two kinds of entry from every session on the machine, and shows them in one
place.

| Entry | Where it comes from | It stops waiting when |
|---|---|---|
| A pending question | An open `AskUserQuestion` call | The question is answered, or Dismiss is pressed |
| A refused command | A Bash or PowerShell call that a settings `PreToolUse` hook refused | A Run ends with an exit code of any value, or Dismiss is pressed |

A Run that could not start leaves its entry waiting. A Run that ended leaves its row in the pane
with the output's last lines, out of the count, until Dismiss is pressed.

The plugin reads a refusal through `classic.PreToolUse`. A tool result that starts with
`PreToolUse:Bash hook` or `PreToolUse:PowerShell hook` is the fallback.

| Where | What it shows |
|---|---|
| Status line | `inbox N`, the count across every session. Nothing when there is nothing. |
| `/inbox` | Opens a pane listing every entry, newest first, with its session, age and buttons. |

### Install it

Run these inside a Claude Code session, from any config root.

```
/plugin marketplace add MEFORORG/korus
/plugin install korus-inbox@korus
```

### Every session writes one file and reads the 200 newest

Each session writes `<session id>.json` into `.korus-inbox` in the home folder. The home folder is
`USERPROFILE`, or `HOME` where that is unset. So the inbox spans sessions and Claude accounts on one
machine.

Each five seconds, every pane reads at most the 200 most recently written files of 256 KB or less.
It skips its own file, and any file not written for 24 hours. A larger file is never read, nor one
older than the 200 newest. It reads at most 50 entries from each file.

A file holds only what waits on the owner: the entries, and the keys of entries the owner
dismissed. Run output is never written.

**This is the one plugin here that writes.** `WRITERS` in
`tests/test_the_plugin_marketplace_resolves.py` names it, and the scan refuses a write anywhere else.

**A Dismiss lives only in the file of the session that pressed it.** Other panes read it there and
hide the entry too. When the dismissing session ends, its file holds no dismissals, so the Dismiss
lapses and an entry that still waits shows again in every pane.

A Dismiss also lapses after 24 hours, and when its file drops out of the 200 that panes read.

One case outlasts the lapse. The session that raised the entry removes it from its own list when its
pane sees the Dismiss, and it does not bring it back.

### Run is offered only for this session's own refusals

| Entry | Buttons |
|---|---|
| A refused command this session's main loop raised, in a folder known as a full path | Run, Copy, Dismiss |
| A refused command a subagent raised | Copy and Dismiss. The subagent's folder is not known. |
| Anything read from another session's file | Copy and Dismiss. Never Run. |
| A question | Copy and Dismiss |

Run takes two presses. The first arms it and shows `Run now`, and the second runs it. The arm lapses
after 60 seconds, and two quick presses run the command once.

**`Run now` ignores a press less than 600 ms after the last press.** Each ignored press starts the
600 ms again, so a double click, a held Enter or a run of clicks cannot reach the command. The pane
states the rule, and a toast says when a press was ignored.

The arm stays through ignored presses, and still lapses 60 seconds after the Run press.

The command comes from the session's own state at the moment of the press. It never comes from the
screen or the disk. Text the pane cannot show exactly is Copy only, so what runs is what the owner
read; the rules are below.

Run needs the folder the session was in, as a full path. Where the session could not report its
folder, or reported an empty or relative one, the entry is Copy only. Otherwise the command would run
in whatever folder the Claude Code process happens to be in.

On Windows only a drive path counts. A share path such as `\\server\share` is Copy only everywhere.

The arming press works out the exact command line, and the pane shows every argv element before
`Run now`. The result shows it again. `Run now` works it out once more and runs nothing if it
changed, for example when `pwsh.exe` was removed in between.

The pane draws the folder and each element itself, at most 40 characters to a row. A row is cut at
the pane's edge, never wrapped, and starts with a mark, so text cannot draw a fake element:

| Row start | Row |
|---|---|
| `folder: ` | The first row of the folder |
| `argv[3]: ` | The first row of an element |
| `  + ` | A row cut from the same line |
| `  \| ` | A row after a newline |
| `out: ` or `error: ` | One line of what the run printed, or why it failed |

A row never ends in a space. The space starts the next row, where it shows. While Run is offered,
the command line above the folder is drawn the same way.

A pane narrower than 52 columns would cut a row short, so it offers Copy only and says why. Widen
the pane and Run comes back.

PowerShell runs as `pwsh -NoProfile -Command`, in the folder the session was in. Where
`<ProgramFiles>\PowerShell\7\pwsh.exe` exists, it runs that, and the pane shows the full path as
`argv[0]`. Otherwise it runs a bare `pwsh`, and the process runner finds it by name.

**A bare `pwsh` is not always the one on `PATH`.** On Windows the lookup can try the run folder
first, so the pane shows `argv[0]: pwsh (by name: PATH, and on Windows the run folder first)`.

Bash runs through Git Bash by its full path, and the pane shows that path as `argv[0]`. It never runs
as a bare `bash`, which on Windows can be WSL. Where no Git Bash is found, the pane says `Run now`
runs nothing, and pressing it records the failure.

### Run is offered only for text the pane can show exactly

A refused command is Copy only, with the reason on screen, when any of these holds:

| The command | Why |
|---|---|
| Is over 400 characters | It would not fit on one screen beside `Run now`. |
| Is over 6 lines | The same. Read a longer script in an editor. |
| Holds a run of 4 or more spaces | Padding is how text lines itself up to look like something else. |
| Holds a tab, or any character outside plain ASCII | Only plain ASCII is one cell wide on every surface, so only it lines up as counted. |
| Has a line that ends in a space | The space would not show. |
| Holds `argv` anywhere, or `folder:` | The cut falls at the same place on every pane, so text placed there could read as a new row. |
| Holds a character the screen strips | What runs would not be what the owner read. |

The folder must pass the same rules, on one line. The pane, the Run press and the `Run now` press
all ask one check, so they always agree. Copy still works for every one of these.

### Everything read from disk is untrusted text

Any process on the machine can write into the folder. So each field read from another session's
file is checked for type and cut to a length. Control characters, zero-width marks and
bidirectional marks are stripped, so a file cannot repaint the terminal or hide text.

### A command that looks like a secret is never stored

The check looks for a token, a password, a key, a URL credential or a long random string. A refused
command that matches is stored as a placeholder: `command withheld: it looked like it carried a
secret`. That entry offers no Run and no Copy. The check errs toward withholding.

Question text gets a narrower check, on value shapes such as `password=...` only. In prose, words
like "token" and "key" are ordinary.

### Ended files pile up, and inbox-prune clears them

The plugin's file API has no delete and no rename. So a session that ends overwrites its file with
`ended: true`, and the file stays.

`scripts/coord/inbox-prune.ps1` clears them. It lists what it would delete, and deletes only when
`-Apply` is passed.

```
pwsh -NoProfile -File scripts/coord/inbox-prune.ps1
pwsh -NoProfile -File scripts/coord/inbox-prune.ps1 -Apply
```

It deletes a file named `<session id>.json` that is `ended: true` or was not written for 24 hours.
It reads no subfolder and follows no link. It refuses a `-Folder` whose last segment is not
`.korus-inbox`, with or without `-Apply`.

### What CI checks for it, and what it cannot

| Check | Where it runs |
|---|---|
| `claude plugin validate plugins/korus-inbox` | **Your machine only.** |
| `claude plugin test plugins/korus-inbox` | **Your machine only.** 68 tests, all passing under Claude Code 2.1.286 on 2026-10-02. |
| The marketplace lists it, its files are ASCII, and `WRITERS` names it as a writer that still writes | CI, through `tests/test_the_plugin_marketplace_resolves.py`. |
| The prune deletes the spent files and keeps everything else | CI, through `tests/test_the_inbox_prune_deletes_only_spent_files.py`. |
