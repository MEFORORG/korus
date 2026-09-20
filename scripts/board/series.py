"""Derive the hourly series and headline metrics from data.json."""
import json, datetime as dt
import os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("LANDER_BOARD_OUT", HERE)

CT = dt.timezone(dt.timedelta(hours=-5), "CDT")   # Sept 2026 is CDT
HOURS = 48          # the MEASUREMENT window: idle runs and the window rate are read over this
CHART_HOURS = 24    # the CHART window, owner-set 2026-09-19. A slice of the above, never a re-read
IDLE_RUN_MIN = 3

def parse(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

def fmt_ct(u):
    t = u.astimezone(CT)
    return "%s %d %s %d, %d:%02d %s CT" % (t.strftime("%a"), t.day, t.strftime("%b"),
        t.year, (t.hour % 12) or 12, t.minute, "AM" if t.hour < 12 else "PM")

def hr_ct(u):
    t = u.astimezone(CT)
    return "%d%s" % ((t.hour % 12) or 12, "a" if t.hour < 12 else "p")

d = json.load(open(os.path.join(OUT, "data.json"), encoding="utf-8"))
now = parse(d["generated_utc"])
top = now.replace(minute=0, second=0, microsecond=0)
hours = [top - dt.timedelta(hours=i) for i in range(HOURS - 1, -1, -1)]

series, repo_metrics = [], {}
for r in d["repos"]:
    merged = [parse(x) for x in r["merged"]]
    created = [parse(x) for x in r["created"]]
    closed = [parse(x) for x in r["closed"]]
    # walk backwards from the known current open count
    opens, cur = {}, r["open"]
    for h in reversed(hours + [top + dt.timedelta(hours=1)]):
        opens[h] = cur
        lo = h - dt.timedelta(hours=1)
        cur = cur - sum(1 for c in created if lo <= c < h) + sum(1 for c in closed if lo <= c < h)
    per_hour = [sum(1 for m in merged if h <= m < h + dt.timedelta(hours=1)) for h in hours]
    repo_metrics[r["short"]] = {
        "merged_per_hour": per_hour,
        "open_per_hour": [opens[h] for h in hours],
        "merged_60m": sum(1 for m in merged if m >= now - dt.timedelta(hours=1)),
        "merged_24h": sum(1 for m in merged if m >= now - dt.timedelta(hours=24)),
        "last_merge": max(merged).isoformat() if merged else None,
    }

tot_merge = [sum(repo_metrics[r]["merged_per_hour"][i] for r in repo_metrics) for i in range(HOURS)]
tot_open = [sum(repo_metrics[r]["open_per_hour"][i] for r in repo_metrics) for i in range(HOURS)]
idle = sum(1 for v in tot_merge if v == 0)

# idle RUNS of IDLE_RUN_MIN hours or more, and the longest
runs, run, best = [], 0, 0
for v in tot_merge + [1]:
    if v == 0:
        run += 1
    else:
        if run >= IDLE_RUN_MIN:
            runs.append(run)
        best = max(best, run)
        run = 0

out = {
    "generated_utc": d["generated_utc"],
    "generated_ct": fmt_ct(parse(d["generated_utc"])),
    # The chart keys are SLICED to the chart window. Everything below them -- idle runs, the
    # longest run, merged_window -- is still computed over the full HOURS above.
    "hours_ct": [hr_ct(h) for h in hours][-CHART_HOURS:],
    "hours_iso": [h.isoformat() for h in hours][-CHART_HOURS:],
    "total_merged_per_hour": tot_merge[-CHART_HOURS:],
    "total_open_per_hour": tot_open[-CHART_HOURS:],
    "chart_hours": CHART_HOURS,
    "idle_hours": idle,
    "window_h": HOURS,
    "idle_runs": len(runs),
    "idle_run_min_h": IDLE_RUN_MIN,
    "longest_idle_run_h": best,
    "merged_window": sum(tot_merge),
    "best_hour": max(tot_merge[-CHART_HOURS:]) if tot_merge else 0,
    "repos": repo_metrics,
}
json.dump(out, open(os.path.join(OUT, "series.json"), "w", encoding="utf-8"), indent=1)
print("hours:", out["hours_ct"][0], "->", out["hours_ct"][-1])
print("merges/h:", tot_merge)
print("open/h  :", tot_open)
print("measured %dh | charted %dh | idle hours %d | runs>=%dh: %d | longest %dh | merged %d"
      % (HOURS, CHART_HOURS, idle, IDLE_RUN_MIN, len(runs), best, sum(tot_merge)))
