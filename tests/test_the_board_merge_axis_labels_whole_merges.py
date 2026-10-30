"""The board's merge axis labels whole merges, each at the height that value really sits.

WHAT THIS EXISTS FOR. The left axis labelled 0, half the peak and the peak. On a peak of 6 the owner
could not read 1, 2, 4 or 5 off the bars. On an odd peak it was wrong as well as sparse: a peak of 5
printed a rounded "2" at the height of 2.5. Owner instruction 2026-10-30: "fix the left hand scale".

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
ALL = ("engine", "korus", "vault")
PADT, IH = 24, 240  # build.py's chart frame: H 300, PADT 24, PADB 36.


def repo(short):
    return {"repo": "MEFORORG/" + short, "short": short, "open": 0, "unresolved": 0, "draft": 0,
            "clean": 0, "buckets": {}, "required": [], "person": 0, "ci": 0, "ready": 0,
            "enqueued": 0, "entries": [], "merged": [], "created": [], "closed": [], "prs": []}


def render(merged):
    n = len(merged)
    zeros = [0] * n
    series = {
        "generated_ct": "1:00 PM CT", "generated_utc": NOW.isoformat(),
        "window_h": 48, "chart_hours": n, "merged_window": 0, "best_hour": 0,
        "idle_hours": 0, "idle_runs": 0, "idle_run_min_h": 3, "longest_idle_run_h": 0,
        "hours_ct": ["1p"] * n, "hours_iso": [NOW.isoformat()] * n,
        "total_merged_per_hour": merged, "total_open_per_hour": [12] * n,
        "repos": {s: {"merged_per_hour": zeros, "open_per_hour": zeros, "merged_60m": 0,
                      "merged_24h": 0, "last_merge": None} for s in ALL},
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


def labels(html):
    """The left axis as {value: y of its gridline}, undoing the 4 units of text offset."""
    return {int(v): float(y) - 4 for y, v in re.findall(
        r'<text class="ax lyl" x="\d+" y="([\d.]+)">(\d+)</text>', html)}


def grid(html):
    return sorted(float(y) for y in re.findall(r'<line class="gl"[^>]* y1="([\d.]+)"', html))


class MergeAxisLabelsWholeMerges(unittest.TestCase):

    def test_a_peak_of_six_labels_every_merge_count(self):
        """The chart the owner sent."""
        self.assertEqual(sorted(labels(render([6, 1, 0]))), [0, 1, 2, 3, 4, 5, 6])

    def test_an_odd_peak_never_prints_a_rounded_half(self):
        self.assertEqual(sorted(labels(render([5, 0]))), [0, 1, 2, 3, 4, 5])

    def test_every_label_sits_where_its_value_is(self):
        for peak in (1, 2, 5, 6, 7, 8, 9, 13, 17, 23):
            got = labels(render([peak, 0]))
            top = max(got)
            self.assertGreaterEqual(top, peak)
            for value, y in got.items():
                self.assertAlmostEqual(y, PADT + IH * (1 - value / top), delta=0.1, msg=(peak, value))

    def test_every_label_has_a_gridline_and_no_gridline_lacks_one(self):
        for peak in (5, 6, 9, 23):
            html = render([peak, 0])
            self.assertEqual(sorted(labels(html).values()), grid(html))

    def test_a_tall_bar_reaches_its_own_label(self):
        html = render([9, 0])
        heights = re.findall(r'<rect class="bar" x="[\d.]+" y="([\d.]+)"', html)
        self.assertAlmostEqual(float(heights[0]), labels(html)[10] + IH * 0.1, delta=0.1)

    def test_a_large_peak_keeps_the_labels_readable(self):
        self.assertLessEqual(len(labels(render([23, 0]))), 9)

    def test_no_peak_crowds_the_axis(self):
        """Hold on PR 258: a fixed top step of 5 overlapped its labels above a peak of 85."""
        for peak in (40, 41, 80, 81, 86, 160, 161, 400, 401, 999, 12345):
            got = labels(render([peak, 0]))
            self.assertLessEqual(len(got), 9, peak)
            self.assertGreaterEqual(max(got), peak)

    def test_the_right_axis_never_prints_one_label_twice(self):
        """Hold on PR 258: an idle chart's two-line axis printed its bottom right label twice."""
        for merged in ([0, 0], [1, 0], [2, 0], [5, 0]):
            ys = re.findall(r'<text class="ax ryl" x="\d+" y="([\d.]+)">', render(merged))
            self.assertEqual(len(ys), len(set(ys)), merged)

    def test_no_merges_at_all_still_draws_an_axis(self):
        self.assertEqual(sorted(labels(render([0, 0]))), [0, 1])


if __name__ == "__main__":
    unittest.main()
