"""The board's pill reads DRAINING only on two or more merges in the trailing hour.

WHAT THIS EXISTS FOR. Owner ruling 2026-10-29: fewer than two merges per hour is SLOW. Before it,
the pill read DRAINING on a single merge 52 minutes old while the hourly chart showed zero, so the
label claimed movement the page itself contradicted. PR 253 changed the rule, and a review found
that resetting the threshold to 1, or back to the old "last merge within 60 minutes" rule, still
passed the whole suite: every fixture carried merged_60m=0. These cases pin each boundary.

The pill also prints the count behind the label, so a reader sees the reading and not only the bucket.

Nothing here calls GitHub. build.py is run as a subprocess over a fixture, the real rendering path.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts/board/build.py"
NOW = dt.datetime(2026, 9, 20, 18, 0, tzinfo=dt.timezone.utc)
HOURS = [0] * 48
ALL = ("engine", "korus", "vault")


def repo(short):
    return {"repo": "MEFORORG/" + short, "short": short, "open": 0, "unresolved": 0, "draft": 0,
            "clean": 0, "buckets": {}, "required": [], "person": 0, "ci": 0, "ready": 0,
            "enqueued": 0, "entries": [], "merged": [], "created": [], "closed": [], "prs": []}


def render(merges):
    """`merges` maps a repository to (merged_60m, minutes since its last merge or None)."""
    reps = {}
    for s in ALL:
        m60, ago = merges.get(s, (0, None))
        last = None if ago is None else (NOW - dt.timedelta(minutes=ago)).isoformat()
        reps[s] = {"merged_per_hour": HOURS, "open_per_hour": HOURS, "merged_60m": m60,
                   "merged_24h": m60, "last_merge": last}
    series = {
        "generated_ct": "1:00 PM CT", "generated_utc": NOW.isoformat(),
        "window_h": 48, "chart_hours": 24, "merged_window": 0, "best_hour": 0,
        "idle_hours": 0, "idle_runs": 0, "idle_run_min_h": 3, "longest_idle_run_h": 0,
        "hours_ct": ["1p"] * 48, "hours_iso": [NOW.isoformat()] * 48,
        "total_merged_per_hour": HOURS, "total_open_per_hour": HOURS, "repos": reps,
    }
    out = tempfile.mkdtemp()
    data = {"generated_utc": NOW.isoformat(), "repos": [repo(s) for s in ALL]}
    (Path(out) / "data.json").write_text(json.dumps(data), encoding="utf-8")
    (Path(out) / "series.json").write_text(json.dumps(series), encoding="utf-8")
    r = subprocess.run([sys.executable, str(BUILD)], capture_output=True, encoding="utf-8",
                       errors="replace", env=dict(os.environ, LANDER_BOARD_OUT=out))
    if r.returncode:
        raise AssertionError("build.py exited %d: %s" % (r.returncode, r.stderr[-800:]))
    return (Path(out) / "board.html").read_text(encoding="utf-8")


def pill(html):
    m = re.search(r'<span class="dot"></span>([A-Z ]+)\s*<small>(.*?)</small>', html, re.S)
    assert m, "the pill did not render"
    return m.group(1).strip(), m.group(2)


class PillNeedsTwoMergesAnHour(unittest.TestCase):

    def test_one_recent_merge_is_slow(self):
        """The case the ruling exists for: the old rule called this DRAINING."""
        self.assertEqual(pill(render({"engine": (1, 5)}))[0], "SLOW")

    def test_two_merges_in_one_repository_is_draining(self):
        """The positive control for the case above."""
        self.assertEqual(pill(render({"engine": (2, 5)}))[0], "DRAINING")

    def test_two_merges_across_repositories_is_draining(self):
        self.assertEqual(pill(render({"engine": (1, 5), "vault": (1, 30)}))[0], "DRAINING")

    def test_no_merge_in_the_hour_but_within_180_minutes_is_slow(self):
        self.assertEqual(pill(render({"engine": (0, 120)}))[0], "SLOW")

    def test_last_merge_over_180_minutes_is_stalled(self):
        self.assertEqual(pill(render({"engine": (0, 200)}))[0], "STALLED")

    def test_no_merge_on_record_is_no_data(self):
        self.assertEqual(pill(render({}))[0], "NO DATA")

    def test_the_pill_prints_the_count_behind_the_label(self):
        label, small = pill(render({"engine": (1, 5)}))
        self.assertIn("1 merged in the last 60 min", small)
        self.assertIn("last merge 5m ago as of", small)


if __name__ == "__main__":
    unittest.main()
