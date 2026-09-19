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

The pill carries `last merge <clock time> CT` in small type beside it. The label alone is a bucket;
the time behind it is the reading.

**Give the pill a clock time, not an elapsed one.** Owner ruling 2026-09-19. A board is read hours
after it was built, and `3m ago` is true only at the instant of the build. A clock time stays true,
and a reader can subtract.

Keep the elapsed figure on the *Time since last merge* card, where it sits beside the clock time.
The two answer different questions: how long the drain has been quiet, and when it last ran.

**A timestamp in Central time**, with the UTC instant under it and the refresh cadence.

Central is UTC-5 in daylight saving and UTC-6 outside it. Windows `strftime` rejects `%-I`, so
format the hour by arithmetic. That binds the masthead, the chart ticks and the pill alike. See
[Six traps](#7-six-traps-that-cost-the-first-build-time).

---

## 4. The nine data cards

Each card carries a hero number, a per-repository strip, and one sentence saying what the number
means. The sentence is the part a reader acts on.

| Card | Hero | Sentence says |
| --- | --- | --- |
| PRs open | total open | whether the vault is clear |
| Ready and waiting | every required check green | that queue throughput is the only thing in the way |
| Waiting on CI | no required check red, one or more still running | that nobody acts yet |
| Needs a person | draft, conflicted, or a red required check | refresh the branch before reading a red as broken |
| Enqueued now | queue entries | whether anything is moving |
| Merged, last 60 min | merges in the hour | the best hour in the window, for contrast |
| Avg merged per hour | mean over 24h | the total landed across the full window |
| Idle periods | runs of 3h or more | the longest run |
| Time since last merge | duration | the clock time the pill shows, and how long ago that was |

The three readiness cards partition the open set, so they always sum to the first card.

### 4a. Classify on the required checks, because BEHIND hides a red one

**A pull request that is only BEHIND needs nobody.** The merge queue rebases it. That half of the
first rule was right.

**That holds only where a queue exists.** Read 2026-09-19: the engine has one. KORUS and the vault
have none and require an up-to-date branch. There the Lander updates the branch as part of landing,
so BEHIND alone still counts as ready.

**BEHIND is still not safe to read as ready.** `mergeStateStatus` reports BEHIND in preference to
BLOCKED, so it hides a failing required check. The engine's `CLAUDE.md` records this under "A PR's
merge state is a join over clocks".

So classify on the required contexts themselves. Read the required set live, then intersect each
pull request's check rollup with it:

| Bucket | Rule |
| --- | --- |
| Needs a person | draft, DIRTY, or a failing required context |
| Waiting on CI | no failing required context, one or more still pending |
| Ready | every required context green |

A required context that has not reported yet counts as pending. Missing data can then never read as
ready.

```bash
gh api repos/<owner/name>/branches/main/protection/required_status_checks --jq '.contexts[]'
```

**Never pin the count.** On 2026-09-19 the engine required 8 contexts, KORUS 2 and the vault 2. The
set moves.

**Measured 2026-09-19 at 16:45 UTC, engine, 62 open pull requests.** Classifying on
`mergeStateStatus` said 13 were not ready. The required-context rollup found 29 with a red required
check, and 28 of those read BEHIND. Four of them:

| PR | Merge state | Failing required context |
| --- | --- | --- |
| 1288 | BEHIND | `CI gate` |
| 1271 | BEHIND | `dependency-and-secret-scan (pip-audit, npm-audit, gitleaks)` |
| 1197 | BEHIND | `CI gate`, `test (windows-2025, py3.14)` |
| 1286 | BEHIND | `test (ubuntu-latest, py3.14)`, `test (windows-2022, py3.14)` |

**This section once read BEHIND as ready outright.** Its figure of 17 not ready came from that rule,
so it is withdrawn rather than carried forward.

Two traps, each handled in `scripts/board/collect.py` rather than left to the reader:

| Trap | What happens | What the collector does |
| --- | --- | --- |
| Counting every red check | Advisory legs such as diff-coverage, zizmor, sbom and trivy go red and block nothing. Counting them put 28 harmless pull requests in the human column | Intersects the failing names with the required set, always |
| `gh pr list --json statusCheckRollup` over 60+ pull requests | Returns HTTP 504. A `jq` default then yields zero failures for every row, which reads exactly like a clean repository | Pages a GraphQL query 20 at a time and halves the page on a failure. It writes nothing unless every open pull request came back with all its checks |

`tests/test_the_board_reads_readiness_off_the_required_set.py` pins both, and fails when either
guard is removed.

### 4b. Most red required checks are stale, not broken

On 2026-09-19, 27 of the engine's 29 reds had run against an older `main`:

- 16 were one pip-audit finding, three anyio CVEs. `main` already pinned `anyio==4.14.2`.
- 11 were the CI gate roll-up on repo harness tests, which `main`'s latest run passed.

A branch refresh clears both, and nobody writes code. So the "Needs a person" card says to refresh
the branch before reading a red as broken. A card that said "each needs a person" sent readers
looking for work that did not exist.

### 4c. Count idle RUNS, not idle hours

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

The required set, per repository, is the `gh api` call in
[section 4a](#4a-classify-on-the-required-checks-because-behind-hides-a-red-one).

Open pull requests, per repository, with the check rollup on each head commit. Use the paged GraphQL
query `OPEN_Q` in `scripts/board/collect.py`. **Do not use `gh pr list --json statusCheckRollup`.**
Over 60 or more pull requests it returns HTTP 504, as section 4a records.

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
shorter, because the sentence wraps to fewer lines. The ninth card, time since last merge, spans the
third row on its own.

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
