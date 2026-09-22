# The Lander Board

## TLDR/BLUF

**What this is.** The specification for a status board showing whether the Lander is draining the
merge queue, across every repository it lands. Enough to rebuild it from nothing.

**Who it is for.** A session asked to build or refresh the board. The Watchdog seat built the first
one on 2026-09-19 and this page is its record.

**The one thing to get right.** Every number on it is a reading, and several of the obvious
instruments lie. [Seven traps](#7-seven-traps-and-every-one-returned-something-that-looked-clean)
names each one.

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
| KORUS | `MEFORORG/korus` |
| Vault | `MEFORORG/MessageFoundry-vault` |

**Address them by the canonical pair, never a pre-transfer one.** korus and the vault moved to
MEFORORG. REST, GraphQL and `gh pr` follow a rename, so a stale owner works everywhere but the
search index. Section 7 has the cost. `gh api repos/<o>/<n> --jq .full_name` gives the pair.

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

The pill carries **an age with its anchor** in small type beside it -- `last merge 23m ago as of
7:50 PM CT`. The label alone is a bucket; the age is the reading behind it, and the anchor is what
keeps the age honest.

**Never an UNANCHORED relative age.** Owner instruction 2026-09-19, revised the same day. A bare
age freezes at render, so a page read an hour later still says `8m ago` and nothing contradicts
it. Render the instant, or the age with the instant it was taken at.

A **span** -- how long an idle run lasted -- needs no anchor. It does not age as the page sits.

**A timestamp in Central time**, with the UTC instant under it and the refresh cadence.

Central is UTC-5 in daylight saving and UTC-6 outside it. Windows `strftime` rejects `%-I`, so
format the hour by arithmetic rather than a format string. See
[Seven traps](#7-seven-traps-and-every-one-returned-something-that-looked-clean).

---

## 4. The nine data cards

Each card carries a hero number, a per-repository strip, and one sentence saying what the number
means. The sentence is the part a reader acts on.

Below the cards sits the **PR Statuses** strip; section 8a specifies it.

| Card | Hero | Sentence says |
| --- | --- | --- |
| PRs open | total open | whether the vault is clear |
| Ready and waiting | every required check green | that queue throughput is the only thing in the way |
| Waiting on CI | no required check red, one or more still running | that nobody acts yet |
| Needs a fix | draft, conflicted, or a red required check | none of the three waits on a human; the table below it says what clears each |
| Enqueued now | queue entries | whether anything is moving |
| Merged, last 60 min | merges in the hour | the best hour on the chart, for contrast |
| Avg merged per hour | mean over 24h | the total landed across the full window |
| Idle periods | runs of 3h or more | the longest run |
| Last merge | Central clock time | the same instant the pill ages from |

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
| Needs a fix | draft, DIRTY, or a failing required context |
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

A branch refresh clears both, and nobody writes code. So the red row of the "What needs fixing"
table says to refresh the branch before reading a red as broken.

The card used to say "needs a person", which sent readers looking for work that did not exist.
None of the three needs one: a draft needs its author to finish it, a conflict needs a rebase, a
red needs diagnosing. The Lander drives all three. Owner correction, 2026-09-20.

### 4c. Count idle RUNS, not idle hours

A scattered idle hour is a turn boundary. A run of hours is the failure the board exists to catch.

Count runs of three hours or more with no merge in any repository, and report the longest. Over a
48-hour window on 2026-09-19 that gave 3 runs with a longest of 14 hours.

**The window changes the answer.** The same day read over 24 hours gave a longest run of 9 hours,
because the worst stall was half outside the window. Use 48.

---

## 5. The chart

One frame, two series, **24 hours** (owner-set 2026-09-19):

- Bars, left axis: total merges per hour across all repositories.
- Line, right axis: total pull requests open at the top of each hour.
- Shaded bands behind both: stretches of two hours or more with no merge.

**The chart and measurement windows differ, deliberately.** The series is derived over 48 hours;
the chart draws the last 24. Section 4c measured why: over 24 hours the longest idle run read 9
against 14, the worst stall falling half outside. Narrowing both would shrink that figure silently.

**The chart must not need a horizontal scrollbar.** Give the SVG a `viewBox` and `width:100%`
with no `min-width`, so it scales to its panel. A floor sized for 48 bars is what put a scrollbar
under 24. `W` is viewBox units, so it sets the aspect: narrower means wider bars after scaling.

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

Merges, creates and closes across the window. **Not from the search API** -- it does not follow a
repository rename, and section 7 carries the measurement. Page the REST pulls list instead,
newest-updated first, until a page predates the window:

```bash
gh api -X GET repos/<owner/name>/pulls -f state=closed -f sort=updated -f direction=desc \
  -f per_page=100 -f page=<n> \
  --jq '.[] | [(.merged_at // "-"), (.closed_at // "-"), .created_at, .updated_at] | join(" ")'
```

`closed_window` in `scripts/board/collect.py` does this, and refuses on any failed page. A closed
list holds no open pull request, so the open read supplies those creates. Without them the
section 5b open line drops every arrival still open, which is most of a busy window.

---

## 7. Seven traps, and every one returned something that looked clean

Every one returned something that looked like a clean result.

| Trap | What happens | What to do |
| --- | --- | --- |
| A count read just after a merge | GitHub recomputes mergeability lazily. A poll 195 seconds after a merge reported 1 CLEAN; a re-read 14 seconds later returned 14. The same trap printed UNKNOWN for all 7 vault rows on 2026-09-19 | Read twice, use the second -- `resolve_unknown` in `collect.py` now does. See [TIPS-AND-TRICKS.md](TIPS-AND-TRICKS.md) |
| `autoMergeRequest` as "armed" | Reads null for a genuinely enqueued pull request, so an armed count reports zero while the queue works | Read the queue entry, never the pull request |
| `refs/remotes/origin` for seat activity | Includes `origin/HEAD` and `origin/main`, which track the trunk and sort first after any merge | Exclude those two, and `dependabot`, and `gh-readonly-queue` |
| `gh pr list --limit N` with a date filter | Sorts by number, so recent merges fall outside the page and the filter returns nothing | Use `--search` with a date qualifier |
| `%-I` in `strftime` | Raises `ValueError` on Windows | Compute the 12-hour value with arithmetic |
| A pytest path typo | Prints `no tests ran` and runs none of the other files named | Read the pass count, never the absence of failures |
| An artifact link in a tracked file | The leak gate blocks it as a capability, fail-closed, and the branch is already pushed by then. It is access, not a name | Say how to FIND the artifact -- list by title -- and never write the link down |
| The search API after a repository transfer | korus and the vault moved to MEFORORG. REST followed the rename, so every other call worked; search answered HTTP 422, which `gh pr list --search` reported as `[]` with **exit 0**. Both read as zero merges for three days | Address the canonical pair, and page REST as section 6 does |

**Publish no zero without a control that fired.** Every trap above produced a plausible zero or a
plausible small number. A control is the only thing that separates them from a real reading.

**What the seventh one cost, measured 2026-09-19 at 23:37 UTC.** The board read 86 merges, and 0
for both KORUS and the vault. REST over the same 72 hours found 56, 22 and 35 -- **113 merges, a
24 percent under-report** -- and one of the two it showed as dead had merged seven minutes earlier.

**The mechanism was mis-read first.** It said search "cannot see" those repositories, as if access
were missing. The cause is a stale owner: `repos/wshallwshall/korus` resolves because REST follows
the transfer and search does not. The wrong version sends a reader hunting a permissions bug.

The control, which returned five merges from that same day:

```bash
gh pr list --repo wshallwshall/korus --state merged --limit 5 --json number,mergedAt
```

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

### 8a. PR Statuses: six states, and no two may render alike

The strip is titled **PR Statuses** (owner-set 2026-09-19). It breaks each repository's open pull
requests down by `mergeStateStatus`.

**It shipped unreadable.** Six states shared four classes: BEHIND and UNKNOWN were both the wait
colour, UNSTABLE and BLOCKED both the warning colour. Three legend pairs rendered identically, so a
reader seeing slate could not tell "the queue will rebase it" from "GitHub has not computed it".

Six states have to come out of four status hues, because the section above keeps teal and amber for
the series. So each state carries a hue **and** a fill, and the pair is unique:

| State | Hue | Fill | Means |
| --- | --- | --- | --- |
| CLEAN | good | solid | every required check green |
| BEHIND | neutral | solid | behind main; the queue rebases it |
| UNKNOWN | neutral | diagonal hatch | mergeability not computed yet, and a re-read did not settle it |
| UNSTABLE | warning | diagonal hatch | a non-required check is red, which blocks no merge |
| BLOCKED | warning | solid | a required check is red or missing |
| DIRTY | critical | horizontal bars | conflicts with main |

**UNKNOWN is a fact about the READ, not the pull request.** Mergeability is computed lazily, and
every merge to main invalidates it for every open pull request, so one pass at a busy moment
returns UNKNOWN for a whole repository.

Measured 2026-09-19: the board showed all 7 vault rows UNKNOWN while a live re-read returned
BEHIND, DIRTY, CLEAN and UNSTABLE. `resolve_unknown` re-reads each such row up to three times, and
`data.json` carries an `unresolved` count, so a surviving band is a real one.

**The fill is not decoration.** It is the channel that still reads in greyscale and under a
colour-vision deficiency, and it is why adding two more hues was the wrong fix.

Every band and every legend entry carries its meaning in a `title`, because `UNKNOWN` on its own
tells a reader nothing.

**Type.** Saira Condensed for headings, IBM Plex Sans for prose, IBM Plex Mono for every number.
Tabular figures everywhere digits line up.

**Cards.** A three-pixel accent rail coloured by meaning, not decoration: amber for backlog, teal for
throughput, warning for work needing a fix, critical for failures.

**Layout.** Four cards across on a wide screen. Going from five across to four made each card
shorter, because the sentence wraps to fewer lines. The ninth card, the last merge, spans the
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

`scripts/board/refresh.ps1` runs the three in order and stops at the first failure, so a
half-rebuilt board is never published:

```
pwsh -NoProfile -File scripts/board/refresh.ps1 -OutDir <scratch dir>
```

It deliberately does not publish. Publishing needs a Claude session, so it prints the file and
leaves that step to the session.

### 9b. Finding the artifact, and restarting the refresh

**Publish to the board that already exists, never to a new one.** A second board is worse than one
stale board, because nothing on either tells a reader which is current.

**The link is not written here, and must not be.** An artifact URL is a capability, not a name:
holding it is holding access, so the leak gate blocks one in a tracked file. It blocked this
section's first draft.

Find it instead. The Artifact tool's `list` action returns the account's artifacts by title, and
the board is titled **Lander Board**. Ask the owner if the listing does not show it.

A Watchdog taking the seat restarts the refresh in four steps:

1. **Extract all six scripts from `origin/main` into your own scratchpad, every time**, with
   `git -C <korus> fetch origin` then `git -C <korus> show origin/main:scripts/board/<file>`.
   The six are `collect.py`, `series.py`, `build.py`, `template.html`, `refresh.ps1` and
   `seatstate.py`. **Never run the copies in a working tree**, however healthy that tree looks.
2. Run the scratchpad `refresh.ps1` with an `-OutDir` beside it.
3. Find the existing artifact as above, then publish `board.html` to it with the Artifact tool,
   passing its `url`. Read it first if this session has not published it, or the publish is refused.
4. Repeat on your own loop. **There is no daemon**: section 9a is why, and the masthead says
   "refreshed by the Watchdog session" so a reader checks the timestamp rather than trusting a
   cadence nothing enforces.

**This section exists because the first build left its driver in a session scratchpad.** The
scripts were committed and the thing that ran them was not, so the refresh could not be handed on.

#### Step 1 says "every time" because the conditional form already failed

**Measured 2026-09-21.** Step 1 read *"extract the five scripts if the working tree does not carry
them"*, and a Watchdog read that condition correctly: the ordinary korus clone did
carry all six, so it ran them. That clone was **six commits behind `origin/main`**, and the board it
produced had 11px axis labels and an open-count axis starting at 12 -- both already fixed on
`origin/main` by an earlier Watchdog, on a branch named for exactly those two changes.

**Nothing in the output said so.** A board built from stale scripts renders cleanly, carries a
current timestamp, and reports live numbers, because the DATA is fetched fresh by `collect.py` while
only the rendering is old. The owner found it by looking at the chart.

**Present-tense phrasing of the failure:** *the scripts were there, so the condition was false, so
the extract was skipped, so the fix that existed did not reach the board.* A fix landing on
`origin/main` does not reach a session that never reads `origin/main`.

| Do | Not |
| --- | --- |
| Extract from `origin/main` on every refresh, after a `fetch` | Check whether the tree has the files, which is a different question |
| Treat the tree as a clone that went stale silently | Treat "the file is present" as "the file is current" |

This is the seat's own *read the ref, not the tree* rule, which the playbook already states for role
playbooks and the vault's `roles/`. It binds the board scripts for the same reason and was not
written down here until it had cost a refresh.

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
