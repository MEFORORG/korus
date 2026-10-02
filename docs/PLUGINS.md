# Plugins

## TLDR/BLUF

**What this is.** This repository is a Claude Code plugin marketplace. Its one plugin,
`korus-fleet`, shows your seat and usage on the status line and opens a fleet board pane.

**Who it is for.** Anyone running KORUS seats who wants the seat and the fleet in view without
running a script by hand.

**The one thing to get right.** The plugin is read-only, and CI cannot run its tests. Run
`claude plugin test` yourself before you push a change to it.

---

## What the plugin shows

| Where | What it shows |
|---|---|
| Status line | `seat <x> \| ctx N% \| <limit> N%`, with one `<limit>` part per rate limit the session reports, for example `seat manager \| ctx 26% \| 5h 6% \| 7d 0%`. The seat comes from `.claude/seat.local.txt`, which `scripts/coord/seat.ps1 -Declare` writes. Usage comes from the session. `5h` is its `five_hour` limit and `7d` its `seven_day` limit; any other limit shows under the name the session gives it. |
| `/fleet` | Opens a pane that runs the fleet script with `-Json` and lists every record whose `State` is `RUNNING`, newest first. |

The status line says `no seat marker` when the marker file is missing, and `undeclared` when it is
empty. It refreshes every minute and after each turn.

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
