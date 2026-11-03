"""The board counts a green pull request parked on its author as HELD, not ready.

WHAT THIS EXISTS FOR. The required set says whether GitHub would merge a pull request. It cannot
say whether the Lander has parked it on its author. Measured 2026-11-03: the "Ready and waiting"
tile read 9 and said "Queue throughput is the only thing between these and main" while the
engine's `scripts/coord/held_pr_turns.py` put 5 of the 9 on the author's turn. The Lander caught
it, not the board.

The collector reads that script's --json output from the file LANDER_BOARD_TURNS names. These
cases pin the split, the "not read" arm, the refusals, and that the throughput sentence appears
only when holds were read and none is held.

Nothing here calls GitHub. build.py runs as a subprocess over a fixture, the real rendering path.
"""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts/board/build.py"
SPEC = importlib.util.spec_from_file_location("board_collect_turns",
                                              ROOT / "scripts/board/collect.py")
collect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = collect
SPEC.loader.exec_module(collect)

NOW = dt.datetime(2026, 11, 3, 14, 0, tzinfo=dt.timezone.utc)
HOURS = [0] * 48
ALL = ("engine", "korus", "vault")
THROUGHPUT = "Queue throughput is the only thing"


def ready_row(n):
    return {"n": n, "bucket": "ready", "merge": "BEHIND", "draft": False,
            "failing": [], "pending": []}


def turns_file(rows, age_s=0):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(rows, f)
    stamp = time.time() - age_s
    os.utime(path, (stamp, stamp))
    return path


class CollectorReadsTheTurns(unittest.TestCase):

    def test_unset_is_not_read_and_marks_nothing_held(self):
        self.assertIsNone(collect.read_turns(None, time.time()))
        prs = [ready_row(1)]
        self.assertEqual(collect.apply_turns(prs, None), (0, False))

    def test_an_author_turn_is_held_and_a_lander_turn_is_not(self):
        path = turns_file([{"repo": "R", "number": 1, "turn": "AUTHOR"},
                           {"repo": "R", "number": 2, "turn": "LANDER"}])
        rec = collect.read_turns(path, time.time())["R"]
        prs = [ready_row(1), ready_row(2)]
        self.assertEqual(collect.apply_turns(prs, rec), (1, True))
        self.assertTrue(prs[0]["held"])
        self.assertFalse(prs[1]["held"])

    def test_a_non_ready_row_is_never_counted_held(self):
        rec = {"read": True, "turn": {1: "AUTHOR"}}
        prs = [dict(ready_row(1), bucket="person")]
        self.assertEqual(collect.apply_turns(prs, rec), (0, True))

    def test_a_repository_error_row_leaves_its_holds_unread(self):
        path = turns_file([{"repo": "R", "number": None, "turn": "ERROR", "error": "502"}])
        rec = collect.read_turns(path, time.time())["R"]
        self.assertEqual(collect.apply_turns([ready_row(1)], rec), (0, False))

    def test_a_repository_with_no_ready_row_is_a_complete_read_even_if_unnamed(self):
        """korus with no open PR is absent from the turns file; that is not "not read"."""
        rec = {"read": False, "turn": {}}
        self.assertEqual(collect.apply_turns([dict(ready_row(1), bucket="ci")], rec), (0, True))
        self.assertEqual(collect.apply_turns([], rec), (0, True))

    def test_a_ready_pr_missing_from_the_file_is_not_held_and_not_a_clean_read(self):
        rec = {"read": True, "turn": {}}
        self.assertEqual(collect.apply_turns([ready_row(7)], rec), (0, False))

    def test_a_pr_error_row_is_not_held_and_not_a_clean_read(self):
        rec = {"read": True, "turn": {1: "ERROR"}}
        self.assertEqual(collect.apply_turns([ready_row(1)], rec), (0, False))

    def test_a_stale_file_is_refused(self):
        path = turns_file([], age_s=collect.TURNS_MAX_AGE_S + 60)
        with self.assertRaises(SystemExit):
            collect.read_turns(path, time.time())

    def test_a_missing_file_is_refused_not_read_as_empty(self):
        with self.assertRaises(SystemExit):
            collect.read_turns(os.path.join(tempfile.mkdtemp(), "absent.json"), time.time())

    def test_a_malformed_file_is_refused(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write("{not json")
        with self.assertRaises(SystemExit):
            collect.read_turns(path, time.time())


def repo(short, ready=0, held=None):
    r = {"repo": "MEFORORG/" + short, "short": short, "open": ready, "unresolved": 0, "draft": 0,
         "clean": 0, "buckets": {}, "required": [], "person": 0, "ci": 0, "ready": ready,
         "enqueued": 0, "entries": [], "merged": [], "created": [], "closed": [], "prs": []}
    if held is not None:
        r["held"], r["holds_read"] = held, True
    return r


def render(repos):
    reps = {s: {"merged_per_hour": HOURS, "open_per_hour": HOURS, "merged_60m": 0,
                "merged_24h": 0, "last_merge": None} for s in ALL}
    series = {
        "generated_ct": "8:00 AM CT", "generated_utc": NOW.isoformat(),
        "window_h": 48, "chart_hours": 24, "merged_window": 0, "best_hour": 0,
        "idle_hours": 0, "idle_runs": 0, "idle_run_min_h": 3, "longest_idle_run_h": 0,
        "hours_ct": ["8a"] * 48, "hours_iso": [NOW.isoformat()] * 48,
        "total_merged_per_hour": HOURS, "total_open_per_hour": HOURS, "repos": reps,
    }
    out = tempfile.mkdtemp()
    data = {"generated_utc": NOW.isoformat(), "repos": repos}
    (Path(out) / "data.json").write_text(json.dumps(data), encoding="utf-8")
    (Path(out) / "series.json").write_text(json.dumps(series), encoding="utf-8")
    r = subprocess.run([sys.executable, str(BUILD)], capture_output=True, encoding="utf-8",
                       errors="replace", env=dict(os.environ, LANDER_BOARD_OUT=out))
    if r.returncode:
        raise AssertionError("build.py exited %d: %s" % (r.returncode, r.stderr[-800:]))
    return (Path(out) / "board.html").read_text(encoding="utf-8")


def hero(html, title):
    head = "<h3>%s</h3><p class=\"hero\"><b>" % title
    i = html.index(head) + len(head)
    return html[i:html.index("</b>", i)]


class BoardRendersTheSplit(unittest.TestCase):

    def test_held_rows_leave_the_ready_tile_and_the_throughput_claim_goes(self):
        html = render([repo("engine", 4, 4), repo("vault", 5, 1), repo("korus", 0, 0)])
        self.assertEqual(hero(html, "Ready and waiting"), "4")
        self.assertEqual(hero(html, "Held on author"), "5")
        self.assertNotIn(THROUGHPUT, html)

    def test_throughput_is_claimed_when_holds_were_read_and_none_is_held(self):
        """The positive control: the sentence still renders in the one case it is true."""
        html = render([repo("engine", 2, 0), repo("vault", 1, 0), repo("korus", 0, 0)])
        self.assertEqual(hero(html, "Ready and waiting"), "3")
        self.assertEqual(hero(html, "Held on author"), "0")
        self.assertIn(THROUGHPUT, html)

    def test_unread_holds_say_not_read_and_claim_no_throughput(self):
        html = render([repo("engine", 2), repo("vault", 1), repo("korus", 0)])
        self.assertEqual(hero(html, "Ready and waiting"), "3")
        self.assertEqual(hero(html, "Held on author"), "not read")
        self.assertNotIn(THROUGHPUT, html)

    def test_one_unread_repository_withholds_the_claim(self):
        html = render([repo("engine", 2, 0), repo("vault", 1), repo("korus", 0, 0)])
        self.assertNotIn(THROUGHPUT, html)


if __name__ == "__main__":
    unittest.main()
