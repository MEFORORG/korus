"""The board counts a green pull request parked on its author as HELD, not ready.

WHAT THIS EXISTS FOR. The required set says whether GitHub would merge a pull request. It cannot
say whether the Lander has parked it on its author, or still owes a re-read of a hold. Measured
2026-11-03: the "Ready and waiting" card read 9 and said "Queue throughput is the only thing
between these and main" while the engine's `scripts/coord/held_pr_turns.py` put 5 of the 9 on the
author's turn and 4 more on a hold the Lander had not cleared. The Lander caught it, not the board.

The collector reads that script's --json output from the file LANDER_BOARD_TURNS names. These
cases pin the split, the "not read" arm, the refusals, that the four readiness cards still sum to
the open count on a partial read, and that the throughput sentence appears only when every hold on
the ready rows was read and none is left.

Nothing here calls GitHub. build.py runs as a subprocess over a fixture, the real rendering path.
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from test_the_person_card_decomposes_without_double_counting import pr, render, repo

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("board_collect_turns",
                                              ROOT / "scripts/board/collect.py")
collect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = collect
SPEC.loader.exec_module(collect)

THROUGHPUT = "Queue throughput is the only thing"
CARDS = ("Ready and waiting", "Held on author", "Waiting on CI", "Needs a fix")


def row(turn, n=1, flags=("no-hold",), repo_name="R"):
    return {"repo": repo_name, "number": n, "turn": turn, "flags": list(flags)}


class CollectorReadsTheTurns(unittest.TestCase):

    def turns_file(self, rows, age_s=0, text=None):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = os.path.join(d.name, "turns.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(rows) if text is None else text)
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))
        return path

    def counts(self, rows, prs):
        # The default is the one collect.main uses for a repository the file does not name.
        turns = collect.read_turns(self.turns_file(rows), time.time())
        return collect.apply_turns(prs, turns.get("R", {"read": False, "rows": {}}))

    def test_unset_is_not_read_and_marks_nothing_held(self):
        self.assertIsNone(collect.read_turns(None, time.time()))
        self.assertEqual(collect.apply_turns([pr(1, "ready")], None),
                         {"held": 0, "review": 0, "read": False})

    def test_an_author_turn_is_held(self):
        got = self.counts([row("AUTHOR", 1, ["held"]), row("LANDER", 2)],
                          [pr(1, "ready"), pr(2, "ready")])
        self.assertEqual(got, {"held": 1, "review": 0, "read": True})

    def test_a_lander_turn_with_an_uncleared_hold_is_review_not_queue_work(self):
        """new-commit, replied and no-new-commit all mean a hold is still on the PR."""
        for flags in (["new-commit"], ["replied"], ["new-commit", "replied"], ["no-new-commit"]):
            got = self.counts([row("LANDER", 1, flags)], [pr(1, "ready")])
            self.assertEqual(got, {"held": 0, "review": 1, "read": True}, flags)

    def test_a_lander_turn_with_no_hold_is_plain_ready(self):
        """The positive control for the case above."""
        self.assertEqual(self.counts([row("LANDER", 1)], [pr(1, "ready")]),
                         {"held": 0, "review": 0, "read": True})

    def test_a_non_ready_row_is_never_counted(self):
        self.assertEqual(self.counts([row("AUTHOR", 1, ["held"])], [pr(1, "person")]),
                         {"held": 0, "review": 0, "read": True})

    def test_a_repository_error_row_leaves_its_holds_unread(self):
        got = self.counts([{"repo": "R", "number": None, "turn": "ERROR", "error": "502"}],
                          [pr(1, "ready")])
        self.assertEqual(got["read"], False)

    def test_a_repository_with_no_ready_row_is_a_complete_read_even_if_unnamed(self):
        """korus with no open PR is absent from the turns file; that is not "not read"."""
        rec = {"read": False, "rows": {}}
        self.assertTrue(collect.apply_turns([pr(1, "ci")], rec)["read"])
        self.assertTrue(collect.apply_turns([], rec)["read"])

    def test_a_ready_pr_missing_from_the_file_is_not_held_and_not_a_clean_read(self):
        self.assertEqual(self.counts([], [pr(7, "ready")]),
                         {"held": 0, "review": 0, "read": False})

    def test_a_pr_error_row_is_not_held_and_not_a_clean_read(self):
        self.assertEqual(self.counts([row("ERROR", 1, [])], [pr(1, "ready")]),
                         {"held": 0, "review": 0, "read": False})

    def test_a_stale_file_is_refused(self):
        path = self.turns_file([], age_s=collect.TURNS_MAX_AGE_S + 60)
        with self.assertRaises(SystemExit):
            collect.read_turns(path, time.time())

    def test_a_file_stamped_in_the_future_is_refused(self):
        path = self.turns_file([], age_s=-(collect.TURNS_MAX_SKEW_S + 60))
        with self.assertRaises(SystemExit):
            collect.read_turns(path, time.time())

    def test_a_set_but_empty_variable_is_refused_not_read_as_unset(self):
        with self.assertRaises(SystemExit):
            collect.read_turns("", time.time())

    def test_a_missing_file_is_refused_not_read_as_empty(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        with self.assertRaises(SystemExit):
            collect.read_turns(os.path.join(d.name, "absent.json"), time.time())

    def test_a_malformed_file_is_refused(self):
        with self.assertRaises(SystemExit):
            collect.read_turns(self.turns_file(None, text="{not json"), time.time())

    def test_a_row_with_no_number_is_refused_not_a_traceback(self):
        with self.assertRaises(SystemExit):
            collect.read_turns(self.turns_file([{"repo": "R", "turn": "AUTHOR"}]), time.time())


def board_repo(short, ready=0, held=None, review=0, ci=0):
    """A collector row with `ready` green PRs; `held` None means its holds were not read."""
    prs = [pr(i, "ready") for i in range(ready)] + [pr(100 + i, "ci") for i in range(ci)]
    r = repo(short, prs)
    r["ready"], r["ci"] = ready, ci
    if held is not None:
        r["held"], r["review"], r["holds_read"] = held, review, True
    return r


def hero(html, title):
    head = "<h3>%s</h3><p class=\"hero\"><b>" % title
    i = html.index(head) + len(head)
    return html[i:html.index("</b>", i)]


class BoardRendersTheSplit(unittest.TestCase):

    def test_held_rows_leave_the_ready_card_for_their_own(self):
        html = render([board_repo("engine", 4, 4), board_repo("vault", 5, 1),
                       board_repo("korus", 0, 0)])
        self.assertEqual(hero(html, "Ready and waiting"), "4")
        self.assertEqual(hero(html, "Held on author"), "5")

    def test_an_uncleared_hold_withholds_the_claim_with_nothing_held(self):
        html = render([board_repo("engine", 0, 0), board_repo("vault", 4, 0, review=3),
                       board_repo("korus", 0, 0)])
        self.assertEqual(hero(html, "Held on author"), "0")
        self.assertIn("3 still carry a hold the Lander has not cleared", html)
        self.assertNotIn(THROUGHPUT, html)

    def test_throughput_is_claimed_when_every_hold_was_read_and_none_is_left(self):
        """The positive control: the sentence still renders in the one case it is true."""
        html = render([board_repo("engine", 2, 0), board_repo("vault", 1, 0),
                       board_repo("korus", 0, 0)])
        self.assertEqual(hero(html, "Ready and waiting"), "3")
        self.assertIn(THROUGHPUT, html)

    def test_the_ready_sentence_ignores_held_rows_elsewhere(self):
        """A held vault PR says nothing about whether the engine's ready rows are queue work."""
        html = render([board_repo("engine", 2, 0), board_repo("vault", 1, 1),
                       board_repo("korus", 0, 0)])
        self.assertIn(THROUGHPUT, html)

    def test_unread_holds_say_not_read_and_claim_no_throughput(self):
        html = render([board_repo("engine", 2), board_repo("vault", 1), board_repo("korus", 0)])
        self.assertEqual(hero(html, "Ready and waiting"), "3")
        self.assertEqual(hero(html, "Held on author"), "not read")
        self.assertNotIn(THROUGHPUT, html)

    def test_a_partial_read_shows_its_count_and_keeps_the_partition(self):
        """One repository unread: the held count still shows, and the four cards sum to open."""
        reps = [board_repo("engine", 4, 4, ci=1), board_repo("vault", 2), board_repo("korus", 0, 0)]
        html = render(reps)
        self.assertEqual(hero(html, "Held on author"), "4")
        self.assertIn("Not read</b> for Vault", html)
        self.assertNotIn(THROUGHPUT, html)
        total = sum(int(hero(html, c)) for c in CARDS)
        self.assertEqual(total, sum(r["open"] for r in reps))


if __name__ == "__main__":
    unittest.main()
