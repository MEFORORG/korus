"""The "Needs a fix" card is decomposed into a table whose rows SUM to a labelled total.

WHAT THIS EXISTS FOR. `classify()` puts a pull request in the person bucket on
`draft or DIRTY or failing`. Those three arms overlap: the engine on 2026-09-20 held pull
requests that were a draft AND conflicted AND carried a red required check. Counting each arm
independently is therefore not a decomposition, it is three overlapping populations, and a reader
who adds them up gets a number larger than the card. The only thing that teaches them is that one
of the two numbers is wrong, and nothing on the page says which.

The table walks the arms in the collector's own short-circuit order, so each row counts only the
FIRST reason that applies. That is what makes the column total equal the card.

THE DRIFT TRAP, pinned below rather than described. PERSON_REASONS lives in build.py and the
bucket it explains is computed in collect.py. Two copies of one rule in two files is the shape
CLAUDE.md names for verifier drift. If they ever disagree, a silent skip would shrink the table
while the card stayed right, and the page would look consistent. The Unattributed row exists so
that failure is loud, and the test below forces it rather than trusting it.

THE FOOTER TRAP, added after the owner hit it. The total row first carried the card's own name,
so it read as a FOURTH reason sitting under three others, and the owner had to ask whether it was
a total. A row that has to be explained is not labelled. It now says "Total", and a case below
pins that it is never spelled as one of the reasons.

THE NAMING, corrected by the owner on 2026-09-20. The card was "Needs a person", which names an
actor that none of the three requires: a draft needs its author to finish it, a conflict needs a
rebase, and a red needs diagnosing. All three are fixes the fleet does and the Lander drives. The
rows now say what CLEARS each one rather than why it is there.

Nothing here calls GitHub. build.py is run as a subprocess over a fixture, which is the real
rendering path rather than a re-implementation of it.
"""
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

HOURS = [0] * 48


def repo(short, prs, person=None):
    """A collector row. `person` defaults to the honest count so the fixture cannot lie to itself."""
    if person is None:
        person = sum(1 for p in prs if p["bucket"] == "person")
    return {
        "repo": "MEFORORG/" + short, "short": short, "open": len(prs), "unresolved": 0,
        "draft": sum(1 for p in prs if p["draft"]), "clean": 0, "buckets": {}, "required": [],
        "person": person, "ci": 0, "ready": 0, "enqueued": 0, "entries": [],
        "merged": [], "created": [], "closed": [], "prs": prs,
    }


def pr(n, bucket="person", draft=False, merge="BEHIND", failing=()):
    return {"n": n, "bucket": bucket, "merge": merge, "draft": draft,
            "failing": list(failing), "pending": []}


def series_for(shorts):
    return {
        "generated_ct": "1:00 PM CT", "generated_utc": "2026-09-20T18:00:00+00:00",
        "window_h": 48, "chart_hours": 24, "merged_window": 0, "best_hour": 0,
        "idle_hours": 0, "idle_runs": 0, "idle_run_min_h": 3, "longest_idle_run_h": 0,
        "hours_ct": ["1p"] * 48, "hours_iso": ["2026-09-20T18:00:00+00:00"] * 48,
        "total_merged_per_hour": HOURS, "total_open_per_hour": HOURS,
        "repos": {s: {"merged_per_hour": HOURS, "open_per_hour": HOURS,
                      "merged_60m": 0, "merged_24h": 0, "last_merge": None} for s in shorts},
    }


ALL = ("engine", "korus", "vault")


def render(repos):
    """Run the real build.py over a fixture and return the rendered page.

    build.py walks a FIXED three-repo order, so a fixture naming fewer raises KeyError rather
    than rendering a smaller board. Padding here keeps every case at the board's real shape
    instead of bending the code to the fixture.
    """
    named = {r["short"] for r in repos}
    repos = list(repos) + [repo(s, []) for s in ALL if s not in named]
    out = tempfile.mkdtemp()
    data = {"generated_utc": "2026-09-20T18:00:00+00:00", "repos": repos}
    (Path(out) / "data.json").write_text(json.dumps(data), encoding="utf-8")
    (Path(out) / "series.json").write_text(
        json.dumps(series_for([r["short"] for r in repos])), encoding="utf-8")
    env = dict(os.environ, LANDER_BOARD_OUT=out)
    r = subprocess.run([sys.executable, str(BUILD)], capture_output=True,
                       encoding="utf-8", errors="replace", env=env)
    if r.returncode:
        raise AssertionError("build.py exited %d: %s" % (r.returncode, r.stderr[-800:]))
    return (Path(out) / "board.html").read_text(encoding="utf-8")


def table(html):
    """The panel's rows as {reason: [ints]}, read out of the rendered HTML."""
    m = re.search(r"<h3>What needs fixing</h3>(.*?)</article>", html, re.S)
    assert m, "the panel did not render at all"
    rows = {}
    for tr in re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        if not cells:
            continue
        name = re.sub(r'<span class="why">.*?</span>', "", cells[0], flags=re.S)
        name = re.sub(r"<[^>]+>", "", name).strip()
        nums = [int(c) for c in cells[1:]
                if re.fullmatch(r"\d+", re.sub(r"<[^>]+>", "", c).strip())]
        if nums:
            rows[name] = nums
    return rows


class PersonCardDecomposition(unittest.TestCase):

    def test_the_panel_renders_at_all(self):
        """The positive control. Every assertion below reads this panel, so a suite that passed
        while the panel was absent would be measuring its own regex and nothing else."""
        html = render([repo("engine", [pr(1, draft=True)])])
        self.assertIn("What needs fixing", html)
        self.assertIn("Draft", table(html))

    def test_a_pull_request_with_every_reason_is_counted_once(self):
        """Draft AND conflicted AND red. Three arms fire; the table must show one."""
        html = render([repo("engine", [pr(1, draft=True, merge="DIRTY", failing=["CI gate"])])])
        t = table(html)
        self.assertEqual(t["Draft"][-1], 1)
        self.assertEqual(t["Conflicts with main"][-1], 0)
        self.assertEqual(t["Red required check"][-1], 0)

    def test_precedence_is_the_collectors_own_order(self):
        """Conflicted beats red, because a conflict makes the check result underneath it moot."""
        html = render([repo("engine", [pr(1, merge="DIRTY", failing=["CI gate"])])])
        t = table(html)
        self.assertEqual(t["Conflicts with main"][-1], 1)
        self.assertEqual(t["Red required check"][-1], 0)

    def test_the_rows_sum_to_the_card(self):
        """The property the whole panel exists to have, over a mixed population."""
        prs = [pr(1, draft=True), pr(2, merge="DIRTY"), pr(3, failing=["CI gate"]),
               pr(4, draft=True, merge="DIRTY"), pr(5, merge="DIRTY", failing=["x"]),
               pr(6, bucket="ready", merge="CLEAN"), pr(7, bucket="ci")]
        html = render([repo("engine", prs)])
        t = table(html)
        reasons = sum(t[k][-1] for k in
                      ("Draft", "Conflicts with main", "Red required check"))
        self.assertEqual(reasons, 5, "five of the seven are in the person bucket")
        self.assertEqual(t["Total"][-1], 5, "the footer is the card")

    def test_only_person_bucket_rows_are_counted(self):
        """A ready pull request can still be BEHIND with an advisory red. It is not a person's."""
        html = render([repo("engine", [pr(1, bucket="ready", failing=["advisory"])])])
        self.assertEqual(table(html)["Total"][-1], 0)

    def test_drift_between_the_two_files_is_loud(self):
        """FORCED, not trusted. A person-bucket row with no arm firing can only mean build.py's
        copy of the rule has drifted from collect.py's. It must surface, not vanish."""
        html = render([repo("engine", [pr(1, bucket="person", merge="CLEAN")], person=1)])
        t = table(html)
        self.assertIn("Unattributed", t)
        self.assertEqual(t["Unattributed"][-1], 1)
        self.assertIn("one of the two is wrong", html)

    def test_no_unattributed_row_when_the_files_agree(self):
        """The control for the row above: it must be absent in the ordinary case, or it is
        decoration rather than a detector."""
        html = render([repo("engine", [pr(1, merge="DIRTY")])])
        self.assertNotIn("Unattributed", table(html))

    def test_every_repo_gets_a_column_and_a_total(self):
        html = render([repo("engine", [pr(1, merge="DIRTY")]),
                       repo("vault", [pr(2, draft=True), pr(3, draft=True)]),
                       repo("korus", [])])
        t = table(html)
        self.assertEqual(t["Total"], [1, 2, 0, 3], "three repos then the total")

    def test_the_total_row_is_labelled_a_total_and_not_a_reason(self):
        """The owner read the footer as a fourth reason and had to ask. A total that needs
        explaining is not labelled, and repeating the card's name there is what caused it."""
        html = render([repo("engine", [pr(1, merge="DIRTY")])])
        t = table(html)
        self.assertIn("Total", t)
        for reason in ("Draft", "Conflicts with main", "Red required check"):
            self.assertNotEqual(reason, "Total")
        self.assertNotIn("Needs a fix", t, "the card's name must not reappear as a row")

    def test_no_row_names_an_actor(self):
        """The correction itself. None of the three waits on a human, so nothing in the panel
        may say one does -- that is the wording the owner rejected."""
        html = render([repo("engine", [pr(1, draft=True), pr(2, merge="DIRTY"),
                                       pr(3, failing=["CI gate"])])])
        self.assertNotIn("needs a person", html.lower())

    def test_each_row_says_what_clears_it(self):
        """A taxonomy names the state. This panel has to name the work, or it explains a number
        without telling anyone what to do about it."""
        html = render([repo("engine", [pr(1, draft=True), pr(2, merge="DIRTY"),
                                       pr(3, failing=["CI gate"])])])
        self.assertIn("its author marks it ready", html)
        self.assertIn("a rebase", html)
        self.assertIn("refresh the branch first", html)

    def test_the_most_common_red_context_is_named(self):
        """The one actionable line: which check to look at first."""
        html = render([repo("engine", [pr(1, failing=["CI gate", "test (windows-2025)"]),
                                       pr(2, failing=["CI gate"])])])
        self.assertIn("Most common red context", html)
        self.assertIn("CI gate", html)

    def test_it_says_so_when_nothing_is_red(self):
        html = render([repo("engine", [pr(1, merge="DIRTY")])])
        self.assertIn("No required check is red anywhere.", html)


if __name__ == "__main__":
    unittest.main()
