# The Lander Board

## TLDR/BLUF

**What this is.** The specification for a status board showing whether the Lander is draining the
merge queue, across every repository it lands. Enough to rebuild it from nothing.

**Who it is for.** A session asked to build or refresh the board. The Watchdog seat built the first
one on 2026-09-19 and this page is its record.

**The one thing to get right.** Every number on it is a reading, and several of the obvious
instruments lie. [Six traps](#7-six-traps-that-cost-the-first-build-time) names each one.

---

## 1. What the board answers

One question: **is merge-ready work reaching `main`, or piling up?**

That is not the same as "is the queue busy". A queue can run all day and still lose ground, because
new pull requests arrive while it drains. The board shows both sides so the reader can tell.

The owner's chart that prompted it showed a flat open-count line and read as a stall. The count was
flat because arrivals matched merges, which is a different problem with a different fix.

---

## 2. The repositories

Three, and the board totals across them:

| Name on the board | Repository |
| --- | --- |
| Engine | `MEFORORG/MessageFoundry` |
| KORUS | `wshallwshall/korus` |
| Vault | `wshallwshall/MessageFoundry-vault` |

**Order them Engine, Vault, KORUS in every strip.** The vault is usually empty, so putting it second
makes a clear vault visible without reading numbers.

---

## 3. Masthead

Three things, left to right.

**The name and one line of subtitle.** Say which seat watches it, so a reader who did not ask for it
knows who to talk to.

**A status pill with a signal colour**, driven by minutes since the last merge in any repository:

| Minutes | Label | Colour |
| --- | --- | --- |
| 60 or fewer | `DRAINING` | good |
| 61 to 180 | `SLOW` | warning |
| over 180 | `STALLED` | critical |
| no merge on record | `NO DATA` | warning |

The pill carries `last merge <duration> ago` in small type beside it. The label alone is a bucket;
the duration is the reading behind it.

**A timestamp in Central time**, with the UTC instant under it and the refresh cadence.

Central is UTC-5 in daylight saving and UTC-6 outside it. Windows `strftime` rejects `%-I`, so
format the hour by arithmetic rather than a format string. See
[Six traps](#7-six-traps-that-cost-the-first-build-time).

---

## 4. The eight data cards

Each card carries a hero number, a per-repository strip, and one sentence saying what the number
means. The sentence is the part a reader acts on.

| Card | Hero | Sentence says |
| --- | --- | --- |
| PRs open | total open | whether the vault is clear |
| Ready and waiting | open minus not-ready | that queue throughput is the only thing in the way |
| Not ready to merge | needs a person | draft, conflicted, or failing a required check |
| Enqueued now | queue entries | whether anything is moving |
| Merged, last 60 min | merges in the hour | the best hour in the window, for contrast |
| Avg merged per hour | mean over 24h | the total landed across the full window |
| Idle periods | runs of 3h or more | the longest run |
| Time since last merge | duration | the same figure the pill buckets |

### 4a. BEHIND is not "not ready", and the split matters

**A pull request that is only BEHIND needs nobody.** The merge queue rebases it. Counting it as
blocked inflates the scary number and hides the real one.

Split on whether a person must act:

```python
NEEDS_PERSON = {"DIRTY", "BLOCKED", "UNSTABLE"}
notready = sum(1 for p in open_prs
               if p["isDraft"] or p["mergeStateStatus"] in NEEDS_PERSON)
ready = len(open_prs) - notready
```

Measured 2026-09-19 on the engine: the wrong split reported 56 blocked. The right one reported 17,
and moved 35 pull requests out of a column that implied they were broken.

### 4b. Count idle RUNS, not idle hours

A scattered idle hour is a turn boundary. A run of hours is the failure the board exists to catch.

Count runs of three hours or more with no merge in any repository, and report the longest. Over a
48-hour window on 2026-09-19 that gave 3 runs with a longest of 14 hours.

**The window changes the answer.** The same day read over 24 hours gave a longest run of 9 hours,
because the worst stall was half outside the window. Use 48.

---

## 5. The chart

One frame, two series, 48 hours:

- Bars, left axis: total merges per hour across all repositories.
- Line, right axis: total pull requests open at the top of each hour.
- Shaded bands behind both: stretches of two hours or more with no merge.

### 5a. This is a dual-axis chart, which is normally a mistake

Two y-scales exaggerate every crossing point, and the crossings mean nothing. The `dataviz` guidance
bans them for that reason.

**The owner asked for this one and already reads that form.** Keep it, and put the caveat in the
chart footer so a second reader is not misled: read each series against its own axis.

### 5b. The open-count line is reconstructed, not sampled

GitHub does not report a historical open count. Derive it backwards from the live count:

```
open(t - 1h) = open(t) - created_in[t-1h, t) + closed_in[t-1h, t)
```

That is exact at each hour boundary, given every create and close timestamp in the window. Fetch
those with the search filters in [section 6](#6-the-queries).

The last point sits at the top of the current hour, so it can differ from the live figure on the
cards. Say so in the footer rather than forcing them to agree.

---

## 6. The queries

**`jq` is not on the path.** `gh --jq` works, because `gh` embeds it. Do the rest in Python.

Open pull requests, per repository:

```bash
gh pr list --repo <owner/name> --state open --limit 300 \
  --json number,mergeStateStatus,isDraft,createdAt
```

The merge queue, which is the only true reading of what is enqueued:

```bash
gh api graphql -f query='{repository(owner:"<owner>",name:"<name>"){mergeQueue(branch:"main")
{entries(first:50){nodes{position state pullRequest{number}}}}}}'
```

Merges, creates and closes across the window. Use the search filters, because `--limit` sorts by
pull request number rather than date and truncates the wrong end:

```bash
gh pr list --repo <owner/name> --state merged --search "merged:>=<YYYY-MM-DD>" --limit 400 \
  --json number,mergedAt
gh pr list --repo <owner/name> --state all    --search "created:>=<YYYY-MM-DD>" --limit 400 \
  --json number,createdAt
gh pr list --repo <owner/name> --state closed --search "closed:>=<YYYY-MM-DD>" --limit 400 \
  --json number,closedAt
```

---

## 7. Six traps that cost the first build time

Every one returned something that looked like a clean result.

| Trap | What happens | What to do |
| --- | --- | --- |
| A count read just after a merge | GitHub recomputes mergeability lazily. A poll 195 seconds after a merge reported 1 CLEAN; a re-read 14 seconds later returned 14 | Read twice, use the second. See [TIPS-AND-TRICKS.md](TIPS-AND-TRICKS.md) |
| `autoMergeRequest` as "armed" | Reads null for a genuinely enqueued pull request, so an armed count reports zero while the queue works | Read the queue entry, never the pull request |
| `refs/remotes/origin` for seat activity | Includes `origin/HEAD` and `origin/main`, which track the trunk and sort first after any merge | Exclude those two, and `dependabot`, and `gh-readonly-queue` |
| `gh pr list --limit N` with a date filter | Sorts by number, so recent merges fall outside the page and the filter returns nothing | Use `--search` with a date qualifier |
| `%-I` in `strftime` | Raises `ValueError` on Windows | Compute the 12-hour value with arithmetic |
| A pytest path typo | Prints `no tests ran` and runs none of the other files named | Read the pass count, never the absence of failures |

**Publish no zero without a control that fired.** Every trap above produced a plausible zero or a
plausible small number. A control is the only thing that separates them from a real reading.

---

## 8. Design

**Palette, validated rather than chosen.** Run `scripts/validate_palette.js` from the `dataviz`
skill against the surface each theme actually uses. These pass all six checks:

| Theme | Surface | Merges (bars) | Open PRs (line) |
| --- | --- | --- | --- |
| dark | `#16202B` | `#2FA89E` | `#D4772E` |
| light | `#FBF8F3` | `#00968A` | `#B05C18` |

Teal and amber carry over from the owner's own chart. A reader who knows that chart reads this one
without relearning it.

**Status colours are separate from the series colours** and never reused for data. Good, warning and
critical belong to the pill, the accent rails and the queue chips.

**Type.** Saira Condensed for headings, IBM Plex Sans for prose, IBM Plex Mono for every number.
Tabular figures everywhere digits line up.

**Cards.** A three-pixel accent rail coloured by meaning, not decoration: amber for backlog, teal for
throughput, warning for work needing a person, critical for failures.

**Layout.** Four cards across on a wide screen. Going from five across to four made each card
shorter, because the sentence wraps to fewer lines.

**Both themes.** Define the light palette on bare `:root`, redefine the tokens under
`@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and again under
`:root[data-theme="dark"]`. Paint `body` from a token.

---

## 9. Refresh

Three steps, in order, then republish to the same artifact URL:

```
collect  -> data.json     one pass of the queries above
derive   -> series.json   hourly series, idle runs, per-repo rates
render   -> board.html    template plus computed values
```

Keep them separate. A failed collect then leaves the last good `data.json` in place, and the render
still produces a board rather than an error.

### 9a. A session cron does not fire while the session is busy

**Measured 2026-09-19.** A 15-minute refresh scheduled with `CronCreate` did not fire once, because
the session worked continuously and cron jobs only run while it is idle. The gap showed up when the
owner asked where the board was.

A session cron also dies with the session. For a board anyone relies on, use a cloud schedule.

State the cadence on the board itself, so a stale page is visible as stale.

---

## Related

- [TIPS-AND-TRICKS.md](TIPS-AND-TRICKS.md) -- the merge queue findings the traps table points at
- [roles/LANDER.md](../roles/LANDER.md) -- the seat the board watches, and its own queue rules
- [CI-RED-WATCH.md](CI-RED-WATCH.md) -- noticing a red without a session watching for it
