# Plugins

## TLDR/BLUF

**What this is.** This repository is a Claude Code plugin marketplace with three plugins.

| Plugin | What it does |
|---|---|
| `korus-fleet` | Opens a fleet board pane, and can show your seat and usage on the status line. Read-only. |
| `korus-card` | Runs the repository's own role-card hook at session start, and its reprime after a compaction. |
| `korus-inbox` | Gathers what only the owner can act on from every session, each with the recommended action. |

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

`korus-inbox` shows the owner only what the owner can act on, from every session on the machine.
Each entry says what to do, in one step.

| Entry | Where it comes from | It stops waiting when |
|---|---|---|
| A question | An open `AskUserQuestion` call | The question is answered, or Dismiss is pressed |
| A refused command | A Bash or PowerShell call a settings `PreToolUse` hook refused, whose refusal hands the act to the person | A Run of it exits 0, the same part later runs fine, or Dismiss is pressed |
| An owner signal | A session called the `owner_action` tool | A Run of its command exits 0, the session calls `owner_action_done`, or Dismiss is pressed |

| Where | What it shows |
|---|---|
| Above the prompt | A band with one Button, `inbox N`, hotkey `i`, that opens the pane. Nothing when nothing waits, or while a survey shows. Beside another plugin's band, the Button comes first. |
| `/inbox` | Opens the same pane, and says how many wait. |
| The pane | One card per waiting entry, newest first, then a collapsed Done section. Cards from other sessions stop at the newest 40, and a line says how many more wait. |

**One count feeds the band, the pane's header, its list of cards and `/inbox`.** So the four always
agree. An entry counts while it waits, and a done one does not. An entry from another session counts
even when its card is not drawn.

### The pane draws at most 40 cards from other sessions

The engine refuses a whole pane that holds over 100000 characters of text, and draws its own in its
place. About 150 cards from other sessions passed that bound in version 0.2.0 and blanked the pane.

So the pane draws only the 40 newest cards from other sessions. A card runs about 670 characters,
so 40 come to about 27000. That leaves room for this session's own cards, which stop at 50.

A card can run much longer: a question up to 6000 characters, or more with Details open. So those
cards also stop once they reach 50000 characters of text, even short of 40.

Whether a card fits is measured with its Details closed, so opening Details never hides the card.
Open Details draw only if they fit in what is left. If they do not, the card says so and keeps its
`Hide details` button.

**The 50000 covers cards from other sessions only.** This session's own cards are not counted
against it, so many long own cards could still pass the engine's bound.

When cards are left out, one line under the header says so, for example:
`160 more waiting from other sessions are not shown. /inbox shows the newest 40.`

The plugin also keeps only those 40 entries in its saved state, plus a count of all of them. Saving
about 800 entries, about 4 MB, failed in 0.2.0, and every card from other sessions vanished.

The plugin never sets the status line. Version 0.1.0 showed `inbox N` there, so each session start
clears the status line once.

### Only what the driver rules leave for the owner reaches the inbox

The rule is the one the `driver` skill gives a session. A session that has a strong recommendation
acts on it. One that has none puts the choice through adversarial review and follows a clear answer.
Only what review cannot decide goes to the owner.

So each kind of entry reaches the inbox only on terms that rule allows.

| Kind | What lets it in |
|---|---|
| A question | The session asked. A question is the last step of the ladder. |
| A refused command | The refusal's own words hand the act to the person, by one of the phrases below. |
| An owner signal | The session filed it, naming what only the owner has, and why review could not decide. |

A refusal that matches none of the phrases is a guard the session routes around itself. Staging
everything is one: the guard says to name the paths instead. **It is not recorded at all.**

The match reads the whole refusal, cleaned. The entry keeps three things from it:

| Field | What it holds |
|---|---|
| `detail` | The whole refusal, cut to 8000 characters here, and to 1500 in the shared file |
| `ask` | The refusal's sentence that holds the matching phrase |
| `viaOutput` | True when the refusal was read from the call's result text rather than from the hook's decision |

A reader drops a refused entry from another session's file when its `ask` matches no phrase. So an
entry no rule would keep never shows, whoever wrote it.

**A refused entry kept by version 0.1.0 has no `ask`, and is deleted when the session starts.**
Under these rules it would never have been recorded.

### Each card leads with the one step to take

A card draws its lines in this order:

| Line | What it says |
|---|---|
| Headline | `Blocked: <the blocked part>` for a refusal whose part is first on its line, and `Blocked: <the command's first line>` for any other refusal. The title for a signal, `Question: <header>` for a question. |
| `Do this:` | The recommended action, one step, never blank |
| `Needs you for:` | `<category> \| confidence: <x>` |
| `Why:` | The refusal's first sentence, or the signal's reason |
| `For you:` | The refusal's sentence that hands the act over |
| `From:` | This session, a subagent of it, or another session by name, with the age |
| `Folder:` | The folder Run would use |

A note, the Run views and the buttons follow. Details opens the whole command, the whole refusal and
the review outcome, and closes again.

`Do this:` comes from the phrase the refusal matched. The first matching row decides:

| The refusal says | Do this |
|---|---|
| `I need you to confirm ...` | Confirm what it names, then run the part |
| `from a PLAIN terminal`, or `governs agents, not you` | Run the part in a plain terminal |
| `the user's call` | Decide, and if you agree, run it yourself |
| `a human act` | Do it yourself, from a plain terminal |
| `only the owner` | Only you can do this; if you agree, run it yourself |
| `let the user decide`, `ask the user`, or `I need you to` | Do or answer what `For you:` asks |

"The part" here is the blocked part, and only when it is first on its line. Otherwise the step names
the whole command, and Copy gives the same.

For example: `Run the whole command in a plain terminal: cd C:\other && git switch x`. The bare part
never reaches the owner alone, because alone it could run in a different folder or context.

The step shows a command only when it fits exactly: one line of 160 characters or fewer. Otherwise
it names `the command Copy gives`, rather than show a joined or cut text the owner might retype.

For a question, `Do this:` names the option whose label says `(Recommended)`, where there is one.
Otherwise it says where the question waits. For a signal it is the filed `recommendedAction`.

`Needs you for:` names one of four categories: `preference`, `authority`, `private-context` or
`cost`.

| Kind | Category | Confidence |
|---|---|---|
| A refusal from the hook's decision | `authority` | `high` |
| A refusal read from the result text | `authority` | `medium (gate not verified)` |
| A question | `preference`, unless its words name a cost, an approval or private context | `not stated` |
| A signal | What the session filed | What the session filed |

### The owner_action tool files a signal and returns at once

Each session start registers two tools. The model calls them as `mcp__korus-inbox__owner_action` and
`mcp__korus-inbox__owner_action_done`. The plugin matches the names the engine returns when it
registers them.

The `owner_action` description states the driver ladder, so the model reads the rule before it
files. These are its fields:

| Field | Required | What it holds |
|---|---|---|
| `title` | Yes | One line: what needs the owner. Cut to 200 characters. |
| `why` | Yes | Why it needs the owner. Cut to 600. |
| `recommendedAction` | Yes | What the owner should do, as one step. Cut to 400. |
| `needsOwnerBecause` | Yes | One of `preference`, `authority`, `private-context` or `cost` |
| `reviewOutcome` | Yes | Why review could not decide, or `not applicable: <reason>`. Cut to 300. |
| `confidence` | Yes | How sure, and what reading would change the session's mind. Cut to 120. |
| `command` | No | A PowerShell command for the owner to run. Only PowerShell. |
| `cwd` | No | The full path the command runs in. The session's folder when absent. |

The tool refuses a filing with no category or one outside the four, and one with an empty
`reviewOutcome`. It also refuses one where a required field is empty. Nothing is filed then, and the
refusal restates the rule.

Each field is cleaned like text from disk, and held to one line, so filed text cannot draw a row of
its own. A command that looks like a secret is withheld, as below. So is any of the five prose
fields, one field at a time, and the tool's reply names the fields it withheld.

The call returns an entry id straight away and does not wait for the owner. When the matter settles
without the owner, `owner_action_done` takes that `id` and an optional one-line `note`. The entry
moves to Done.

Only the loop that filed it can resolve it: a subagent cannot resolve the main loop's entry.

The tool's input and the engine's own fields arrive in one record. So any `agentId` the input
carries, `null` included, reads as a subagent, and the entry is Copy only.

### Done entries collapse into one section

An entry is done once a Run of it exits 0, or it resolved without one. Done entries leave the count
and sit under one Button, `Done (N)`, collapsed until it is pressed. Each one says how it ended, and
Dismiss removes it.

A refused entry resolves itself when a later call succeeds with the same part. Every one of these
must hold:

| Condition | What it rules out |
|---|---|
| The entry's blocked part was first on its line | An entry whose part ran after other commands, which a bare success says nothing about |
| The entry came from the main loop | An entry a subagent raised, whose folder is not known |
| The later call came from the main loop | A subagent's success |
| The later call ran in the foreground and finished without error | A `run_in_background` launch, or a result that reads as a launch |
| It ran in the same shell and the same folder | A Bash success settling a PowerShell refusal, or one in another folder |
| Its command starts with the part, then has nothing or `&&` alone | A later `\|\| true`, `;` or pipe, which could hide the part's failure, and anything before the part |
| The part itself is joined by nothing or `&&` alone | A part such as `git push \|\| true`, which exits 0 when the push fails |

A copy of the part inside a quoted string or a comment resolves nothing.

A Run that exits non-zero leaves the entry waiting, with the output's last lines.

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

A session's own entries age out at 24 hours too, so every pane counts the same set. An entry with a
Run still going is kept until the Run ends.

A file holds only what waits on the owner: the waiting entries, and the keys of entries the owner
dismissed. Run output is never written.

**This is the one plugin here that writes.** `WRITERS` in
`tests/test_the_plugin_marketplace_resolves.py` names it, and the scan refuses a write anywhere else.

**A Dismiss lives only in the file of the session that pressed it.** Other panes read it there and
hide the entry too. When the dismissing session ends, its file holds no dismissals, so the Dismiss
lapses and an entry that still waits shows again in every pane.

A Dismiss also lapses after 24 hours, and when its file drops out of the 200 that panes read.

One case outlasts the lapse. The session that raised the entry removes it from its own list when its
pane sees the Dismiss, and it does not bring it back.

### A card names its session by the title the app shows

A card's `From:` line names the session by its title in the app's session list, such as
`Manager: #2861 separators`. The owner cannot match a folder name or a session id to a session.

A session with no title falls back to its folder name and the first 8 characters of its id. So does
a title holding a secret-shaped value, such as `token=...`, since every session's cards show it.

A title is drawn as one line and cut once, at 60 characters.

The engine hands a plugin the title on session start and on each prompt, and on no other event. A
hook beneath may set a new title in its result, and that one wins, unless the event is blocked.

The inbox also catches a session renaming itself with `set_session_title` and `session_id: "self"`.
A rename made any other way, such as by the owner in the sidebar, shows from that session's next
prompt.

### Go to session brings the asking session forward in its own app window

Each instance of the desktop app runs with its own data folder: `%APPDATA%\Claude` for the default
one, `%USERPROFILE%\.claude-desktop-N` for the others. A launch naming a running instance's folder
hands a `claude://claude.ai/epitaxy/local_...` link to it, which brings that session forward.

A desktop session writes its folder and its app session id (`local_...`) to its inbox file. It does
so only when the app's own record of that session names it, so a process it starts cannot claim it.

A remote card offers **Go to session** while the asking session's file is under 12 minutes old. The
pane redraws when one goes stale, and a file dated in the future offers none.

The place is another session's data, so it is never launched as written. The reader rebuilds the
folder from its own environment and launches only if the two match, and only while that instance
holds a `lockfile`, so it is running. A lockfile a power loss left behind is the one gap.

It runs the app's own launcher, `%LOCALAPPDATA%\AnthropicClaude\claude.exe`, which outlives app
updates and exits in under a second. Each value is one argument, with no shell. It works in the
desktop app on Windows only.

### Run is offered only for this session's own entries

| Entry | Buttons |
|---|---|
| A PowerShell refusal, or a signal's command, this session's main loop raised, in a folder known as a full path | Run, Copy, Details, Dismiss |
| A Bash refusal on Windows | Copy, Details and Dismiss. Git Bash can expand a command differently from what the card shows. |
| One a subagent raised | Copy, Details and Dismiss. The subagent's folder is not known. |
| Anything read from another session's file | Copy, Details and Dismiss, plus Go to session while that session is alive. Never Run. |
| A question | Copy and Dismiss |

**For a refusal, Run is offered only when the blocked part is the first command on the line.** The
blocked part is the first span the refusal quotes in single quotes. It must start the command, with
nothing at all before it, not even a space.

It must also end where the shell would end a command. That is the line's end, or just before `;`,
`&&`, `||`, `|` or a line break. Then Run and Copy act on the part alone.

Every other position is Copy only, with one reason:

```
Copy only: other commands come before this part, so it could run in a different context.
```

Copy and `Do this:` then give the whole command, and the headline shows its first line.

**This is an allow-list.** Version 0.2.0 ran a part in any position unless an earlier part matched a
list of words, such as `cd`, `export` or a test before `&&`. Each review found words it missed.

Those included PowerShell's `D:`, `iex`, `Set-Alias` and `Import-Module`, Bash's `name+=`, and
`grep -q` before `&&`. So the list is gone, and position alone decides.

**That reverses one earlier rule. A part after a plain `&&` chain is now Copy only.** In `npm test &&
npm publish`, Run of `npm publish` alone would skip the tests. In `git switch other && git push
--force`, it would force-push whatever branch is checked out now.

Run is not offered either when the part, though first, is not one the shell reads plainly:

| The quoted span is not used when | For example |
|---|---|
| It is only the start of a longer word | `rm -rf /tmp` in `rm -rf /tmp/build` |
| A redirect or a background operator follows it | `git switch x 2>&1` |
| It holds a comment, a quoted string left open, a here-doc, a script block or an escape | `echo "x` |
| It holds a character outside plain ASCII, or PowerShell's `--%` | Typographic quotes |

With no part to use, the headline is the command's first line and Copy takes the whole line. Run is
not offered, and the card says why.

For a signal, Run acts on the filed command. Any label below, such as `argv[` or `Run now`,
anywhere in the signal's filed fields makes it Copy only.

Run takes two presses. The first arms it and shows `Run now`, and the second runs it. The arm lapses
after 60 seconds, and two quick presses run the command once.

**`Run now` ignores a press less than 600 ms after the last press.** Each ignored press starts the
600 ms again, so a double click, a held Enter or a run of clicks cannot reach the command. The pane
states the rule, and a toast says when a press was ignored.

The arm stays through ignored presses, and still lapses 60 seconds after the Run press.

A lapsed or cancelled arm is cleared from the entry, not only hidden. An entry counts as busy only
while it runs, or while its arm is inside its minute.

A busy entry is never the one dropped when the list of 50 is full. So a lapsed arm cannot keep its
entry forever and push out a newer one. A session start clears every arm, since the timer that
would clear it died with the old module.

The text comes from the session's own state at the moment of the press. It never comes from the
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
| `  line 2: ` | The first row of the text's second line, and so on. No mark uses `\|`, the shell pipe. |
| `out: ` or `error: ` | One line of what the run printed, or why it failed |

A row never ends in a space. The space starts the next row, where it shows. While Run is offered,
the headline and a signal's `Command:` line are drawn the same way.

A pane narrower than 52 columns would cut a row short, so it offers Copy only and says why. Widen
the pane and Run comes back.

Each shell runs by its full path, in the entry's folder:

| Shell | Where | What runs |
|---|---|---|
| PowerShell | Windows | `<ProgramFiles>\PowerShell\7\pwsh.exe -NoProfile -Command`. A lookup by name can try the run folder first, and a signal's folder is the model's choice. |
| PowerShell | Elsewhere | `pwsh -NoProfile -Command` |
| Bash | Windows | Nothing. The entry is Copy only. |
| Bash | Elsewhere | `/bin/bash -c`, or `/usr/bin/bash -c` |

**On Windows, Run is offered only for PowerShell.** Git Bash's runtime can glob-expand or
`@file`-expand an argument that the confirm view showed plainly, so what ran would not be what the
owner read. A bare `bash` there can also be WSL's.

A `pwsh.exe` under `LOCALAPPDATA` is not used. The user can write there, so a planted file would look
legitimate on the confirm view. Where no shell is found, `Run now` runs nothing and records why.

A reload of the plugin drops the wait on a Run in progress. So the session start marks such a Run
failed, saying its result is not known. It also drops a question open across the reload, since the
hook that would clear it is gone.

### Run is offered only for text the pane can show exactly

The text Run would execute is Copy only, with the reason on screen, when any of these holds:

| The text | Why |
|---|---|
| Is over 400 characters | It would not fit on one screen beside `Run now`. |
| Is over 6 lines | The same. Read a longer script in an editor. |
| Holds a run of 4 or more spaces | Padding is how text lines itself up to look like something else. |
| Holds a tab, or any character outside plain ASCII | Only plain ASCII is one cell wide on every surface, so only it lines up as counted. |
| Has a line that ends in a space | The space would not show. |
| Holds a label the pane or the card draws, anywhere | Text placed where a row is cut could read as a new row. So `stdout:` is Copy only too. |
| Holds a character the screen strips | What runs would not be what the owner read. |

| Labels | Which |
|---|---|
| The views' own | `argv[`, `argv:`, `folder:`, `out:`, `error:`, `bash:`, `shell:`, `line 2:` |
| The card's | `blocked:`, `why:`, `from:`, `command:`, `do this:`, `for you:`, `copy only:`, `needs you for:`, `confidence:`, `review:`, `question:` |
| A Run's headers | `running:`, `ran, exit`, `could not run:`, `done:`, `run now`, `resolved` |

Case does not matter.

The folder must pass the same rules, on one line. A refusal's `Do this:`, `Why:` and `For you:`
lines, and a signal's filed fields, must hold none of the labels, since the card draws them above
the confirm view.

The pane, the Run press and the `Run now` press all ask one check, so they always agree. Copy still
works for every one of these, and it puts the cleaned text on the clipboard.

### Everything read from disk is untrusted text

Any process on the machine can write into the folder. So each field read from another session's
file is checked for type and cut to a length. Control characters, zero-width marks and
bidirectional marks are stripped, so a file cannot repaint the terminal or hide text.

### A command that looks like a secret is never stored

The check looks for a token, a password, a key, a URL credential or a long random string. A refused
or filed command that matches is stored as a placeholder: `command withheld: it looked like it
carried a secret`. That entry offers no Run and no Copy. The check errs toward withholding.

A refusal's text gets the same check. So does each of a signal's five prose fields: `title`, `why`,
`recommendedAction`, `reviewOutcome` and `confidence`. The check runs when the signal is filed and
again when it is read from disk.

A recommended action can carry `curl -u admin:pw` or `sshpass -p` as easily as a command can. A
field that matches is stored as a placeholder, and only that field.

Question text gets a narrower check, on value shapes such as `password=...` only. In a question,
words like "token" and "key" are ordinary.

A refusal's `ask` gets both checks, when it is recorded and when it is read from disk. It is a
sentence of the refusal, so it can carry what the refusal carried.

A withheld `ask` keeps its kind and the row that let it in. The placeholder names that row, such as
`The gate handed it over as: from a PLAIN terminal`.

A reader applies the handover rule to the `ask` as written, before it withholds anything. So a
secret-looking `ask` gets no pass around the rule.

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
| `claude plugin test plugins/korus-inbox` | **Your machine only.** 312 tests, all passing under Claude Code 2.1.286 on 2026-10-05. Run the binary the app runs (`CLAUDE_CODE_EXECPATH`): under an older `claude` on PATH, 2.1.283, four tests fail that pass under 2.1.286. |
| The marketplace lists it, its files are ASCII, and `WRITERS` names it as a writer that still writes | CI, through `tests/test_the_plugin_marketplace_resolves.py`. |
| The prune deletes the spent files and keeps everything else | CI, through `tests/test_the_inbox_prune_deletes_only_spent_files.py`. |
