"""The Lander Board shows every open nightly-failure issue, and how long each has been open.

WHAT THIS EXISTS FOR. A scheduled run has no pull request, so no required check, merge state or
queue entry ever carries its red. The engine's `nightly-notice.yml` opens one issue per watched
workflow instead, titled `Nightly <workflow> is failing`, and nothing read it. Engine issue 288,
*Nightly Security is failing*, stayed open from 2026-08-08 to 2026-09-25 with 49 comments while
the released line pinned a vulnerable dependency (vault BACKLOG #1800). The owner ruled on
2026-09-26 that the Lander owns these reds and that they reach it through this board.

THE MATCH IS PINNED TO THE WRITER, and both arms run on one fixture. The workflow finds the issue
it comments on by three things: OPEN, labelled `bug`, and a title exactly `Nightly $WF_NAME is
failing`. An issue carrying all three must show. An issue missing any one must not, and neither
may a pull request, which the REST issues list returns beside issues.

A ZERO IS ONLY A ZERO WHERE SOMETHING WAS READ. The vault and korus carry no such workflow, so the
collector does not read them, and the page must say "not read" there rather than "none open". A
data.json written before this read existed is the same case, and so is a failed read, which
refuses the run and leaves the last good file in place.

Nothing here calls GitHub. `subprocess` is replaced inside the collector, and `build.py` is run as
a subprocess over a fixture, which is the real rendering path.
"""
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from test_the_person_card_decomposes_without_double_counting import render, repo

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("board_collect_nightly",
                                              ROOT / "scripts/board/collect.py")
collect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = collect
SPEC.loader.exec_module(collect)

ENGINE = "MEFORORG/MessageFoundry"

# The engine's watch list, read at engine origin/main on 2026-09-30 from the `workflows:` line of
# `nightly-notice.yml`. It is a READING, not a contract: the collector deliberately leaves the
# name free so a workflow joining that list shows up here without an edit.
WATCHED = ["CI", "Security", "DAST", "Stalled PRs", "Required workflow state",
           "security.txt renewal"]


def done(stdout="", code=0, stderr=""):
    return types.SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def row(n, title, kind="issue", opened="2026-09-30T12:00:01Z", updated=None, comments=0):
    """One line in the shape the collector's own `--jq` program prints."""
    return "\t".join([str(n), kind, opened, updated or opened, str(comments), title])


def read(*lines, code=0):
    """Run nightly_reds over a faked `gh`, returning (result, the argv it passed)."""
    calls = []

    def run_(args, **_):
        calls.append(args)
        return done("\n".join(lines) + "\n", code=code, stderr="HTTP 502" if code else "")
    with mock.patch.object(collect, "subprocess", types.SimpleNamespace(run=run_)):
        got = collect.nightly_reds(ENGINE)
    return got, calls


class TheCollectorReadsWhatTheWorkflowWrites(unittest.TestCase):

    def test_an_issue_the_workflow_would_adopt_is_shown(self):
        """The positive control. Every absence below is read against this presence."""
        got, _ = read(row(1830, "Nightly Security is failing", comments=3))
        self.assertEqual([(i["n"], i["workflow"], i["comments"]) for i in got],
                         [(1830, "Security", 3)])
        self.assertEqual(got[0]["url"], "https://github.com/%s/issues/1830" % ENGINE)
        self.assertEqual(got[0]["opened"], "2026-09-30T12:00:01Z")

    def test_every_watched_workflow_name_matches_including_spaces_and_dots(self):
        for name in WATCHED:
            with self.subTest(name=name):
                got, _ = read(row(1, "Nightly %s is failing" % name))
                self.assertEqual([i["workflow"] for i in got], [name])

    def test_a_near_miss_title_or_a_pull_request_is_not_shown(self):
        """The negative control, one variable changed from the positive one each time."""
        misses = [row(2, "Nightly Security is failing", kind="pr"),
                  row(3, "Nightly Security failed"),
                  row(4, "Re: Nightly Security is failing"),
                  row(5, "Nightly Security is failing again"),
                  row(6, "nightly Security is failing"),
                  row(7, "Nightly  is failing")]
        got, _ = read(*misses)
        self.assertEqual(got, [])
        # The same batch with the positive row added returns exactly that row, so the empty
        # answer above came from the filter and not from a read that returned nothing.
        got, _ = read(*(misses + [row(8, "Nightly DAST is failing")]))
        self.assertEqual([i["n"] for i in got], [8])

    def test_the_read_asks_for_the_workflows_own_label_open_only_and_every_page(self):
        _, calls = read(row(1, "Nightly CI is failing"))
        args = calls[0]
        self.assertIn("repos/%s/issues" % ENGINE, args)
        self.assertIn("state=open", args)
        self.assertIn("labels=bug", args)
        self.assertIn("--paginate", args)
        self.assertEqual(collect.NIGHTLY_LABEL, "bug")

    def test_the_oldest_issue_comes_first(self):
        got, _ = read(row(9, "Nightly CI is failing", opened="2026-09-29T06:00:00Z"),
                      row(4, "Nightly DAST is failing", opened="2026-09-01T06:00:00Z"))
        self.assertEqual([i["n"] for i in got], [4, 9])

    def test_a_title_holding_a_tab_is_kept_whole(self):
        got, _ = read(row(1, "Nightly Odd\tName is failing"))
        self.assertEqual([i["workflow"] for i in got], ["Odd\tName"])

    def test_a_failed_read_refuses_rather_than_reading_clean(self):
        with self.assertRaises(SystemExit):
            read(code=1)

    def test_a_row_it_cannot_parse_refuses(self):
        with self.assertRaises(SystemExit):
            read("1830\tissue\t2026-09-30T12:00:01Z")

    def test_every_repository_read_for_these_is_one_the_board_reads(self):
        boards = {full for full, _short in collect.REPOS}
        self.assertTrue(set(collect.NIGHTLY_NOTICE_REPOS) <= boards)
        self.assertIn(ENGINE, collect.NIGHTLY_NOTICE_REPOS)


def pr_page():
    return done(json.dumps({"data": {"repository": {"pullRequests": {
        "totalCount": 0, "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": []}}}}))


NO_QUEUE = done(json.dumps({"data": {"repository": {"mergeQueue": None}}}))


class TheCollectorWritesItPerRepository(unittest.TestCase):
    """main() runs end to end over a faked `gh`, one engine-named repository and one other."""

    def run_main(self, nightly_answer, out):
        calls = []

        def run_(args, **_):
            calls.append(args)
            joined = " ".join(args)
            if "/protection/" in joined:
                return done("gates\n")
            if "pullRequests" in joined:
                return pr_page()
            if "mergeQueue" in joined:
                return NO_QUEUE
            if "/pulls" in joined:
                return done("")
            if "/issues" in joined:
                return nightly_answer
            raise AssertionError("unexpected call: %s" % joined)
        with mock.patch.object(collect, "OUT", out), \
                mock.patch.object(collect, "REPOS", [(ENGINE, "engine"), ("o/r", "r")]), \
                mock.patch.object(collect, "subprocess", types.SimpleNamespace(run=run_)):
            collect.main()
        return calls

    def test_the_engine_carries_its_issues_and_the_other_carries_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = self.run_main(done(row(1830, "Nightly Security is failing") + "\n"), tmp)
            got = json.loads(Path(tmp, "data.json").read_text(encoding="utf-8"))
        by = {r["short"]: r for r in got["repos"]}
        self.assertEqual([i["n"] for i in by["engine"]["nightly"]], [1830])
        self.assertIsNone(by["r"]["nightly"])
        issue_reads = [a for a in calls if any("/issues" in x for x in a)]
        self.assertEqual(len(issue_reads), 1)
        self.assertIn("repos/%s/issues" % ENGINE, issue_reads[0])

    def test_a_failed_issue_read_leaves_the_last_good_data_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "data.json").write_text("LAST GOOD", encoding="utf-8")
            with self.assertRaises(SystemExit):
                self.run_main(done(code=1, stderr="HTTP 502"), tmp)
            self.assertEqual(Path(tmp, "data.json").read_text(encoding="utf-8"), "LAST GOOD")


def issue(n, workflow, opened, comments=0):
    return {"n": n, "workflow": workflow, "title": "Nightly %s is failing" % workflow,
            "opened": opened, "updated": opened, "comments": comments,
            "url": "https://github.com/%s/issues/%d" % (ENGINE, n)}


def board(engine, korus=None, vault=None, drop_key=False):
    """Render the real board. The fixture clock is 2026-09-20T18:00:00Z, set by render()."""
    repos = [repo("engine", []), repo("korus", []), repo("vault", [])]
    if not drop_key:
        for r, v in zip(repos, (engine, korus, vault)):
            r["nightly"] = v
    return render(repos)


def panel(html):
    """The scheduled-run panel alone, so a match elsewhere on the page cannot satisfy a case."""
    start = html.index("<h3>Scheduled runs failing</h3>")
    return html[start:html.index("</article>", start)]


class TheBoardShowsThemAndHowLongEachHasBeenOpen(unittest.TestCase):

    def test_an_open_issue_is_shown_with_its_link_workflow_and_span(self):
        """The positive control for every rendering case below."""
        p = panel(board([issue(1830, "Security", "2026-09-18T18:00:00Z", comments=2)]))
        self.assertIn('href="https://github.com/%s/issues/1830">#1830</a>' % ENGINE, p)
        self.assertIn("<td>Security</td>", p)
        self.assertIn("<td>2d 0h</td>", p)
        self.assertIn("<td>2</td>", p)
        self.assertIn("<b>1</b> open", p)
        self.assertIn("The oldest has been open <b>2d 0h</b>", p)

    def test_the_span_is_anchored_to_the_board_clock(self):
        # An unanchored age freezes at render. The header names the instant the span is read at.
        p = panel(board([issue(1, "CI", "2026-09-20T15:30:00Z")]))
        self.assertIn("<td>2h 30m</td>", p)
        self.assertIn("Open, as of 1:00 PM CT", p)

    def test_the_oldest_leads_and_the_count_covers_every_issue(self):
        p = panel(board([issue(9, "CI", "2026-09-20T12:00:00Z"),
                         issue(4, "DAST", "2026-09-10T12:00:00Z")]))
        self.assertLess(p.index("#4</a>"), p.index("#9</a>"))
        self.assertIn("<b>2</b> open", p)
        self.assertIn("The oldest has been open <b>10d 6h</b>", p)

    def test_no_open_issue_reads_as_none_and_names_what_was_read(self):
        p = panel(board([]))
        self.assertIn("No scheduled run is red in <b>Engine</b>.", p)
        self.assertNotIn("<table", p)

    def test_a_repository_that_was_not_read_never_counts_as_clear(self):
        p = panel(board([]))
        self.assertIn("Vault: not read: this repository carries no nightly-notice workflow.", p)
        self.assertIn("KORUS: not read: this repository carries no nightly-notice workflow.", p)
        self.assertNotIn("Vault</b>", p)

    def test_a_data_json_from_before_this_read_says_nothing_was_read(self):
        p = panel(board(None, drop_key=True))
        self.assertIn("<b>Nothing was read</b>", p)
        self.assertNotIn("No scheduled run is red", p)
        self.assertIn("Engine: not read: data.json predates this read", p)


if __name__ == "__main__":
    unittest.main()
