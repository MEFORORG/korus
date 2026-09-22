"""The Lander Board classifies readiness on the REQUIRED contexts, and refuses a read it cannot trust.

WHAT THIS EXISTS FOR. The first board classified on `mergeStateStatus` alone. That field reports
BEHIND in preference to BLOCKED, so a pull request with a failing required check read BEHIND and was
counted ready. Measured on the engine on 2026-09-19: that rule said 13 not ready where 29 had a red
required context, 28 of them reading BEHIND.

THE TWO TRAPS, each pinned below rather than described:

  a. Counting EVERY red check is the mirror error. Advisory legs go red and block nothing, and
     counting them put 28 harmless pull requests in the human column.
  b. The rollup read over 60+ pull requests returned HTTP 504, and a default then yielded zero
     failures for every row. That reads exactly like a clean repository. The collector must stop
     before writing data.json, so the last good file survives.
  c. The SEARCH API does not follow a repository rename. korus and the vault were transferred to
     MEFORORG; REST kept resolving the old owner, so every other call worked, while search answered
     HTTP 422. `gh pr list --search` reports that as an empty list with exit 0. Measured 2026-09-19:
     both read as zero merges while both were merging, and the board under-reported total throughput
     by 24 percent. The window is read off the REST pulls list, which survives a transfer.

Nothing here calls GitHub. `subprocess` is replaced inside the module under test only.
"""
import ast
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("board_collect", ROOT / "scripts/board/collect.py")
collect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = collect
SPEC.loader.exec_module(collect)

REQUIRED = {"CI gate", "test (ubuntu-latest)"}


def _stamp(hours_ago):
    """An ISO stamp `hours_ago` behind the clock `collect.main` reads. See the window test below."""
    when = collect.dt.datetime.now(collect.dt.timezone.utc) - collect.dt.timedelta(hours=hours_ago)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def run(name, conclusion="SUCCESS", status="COMPLETED", started="2026-09-19T10:00:00Z"):
    return {"__typename": "CheckRun", "name": name, "status": status,
            "conclusion": conclusion, "startedAt": started}


def status(context, state):
    return {"__typename": "StatusContext", "context": context, "state": state,
            "createdAt": "2026-09-19T10:00:00Z"}


def pr(checks, merge="BEHIND", draft=False, n=1):
    roll = None if checks is None else {"contexts": {"pageInfo": {"hasNextPage": False},
                                                     "nodes": checks}}
    return {"number": n, "isDraft": draft, "mergeStateStatus": merge, "createdAt": "x",
            "commits": {"nodes": [{"commit": {"statusCheckRollup": roll}}]}}


def bucket(p):
    return collect.classify(p, REQUIRED)["bucket"]


GREEN = [run("CI gate"), run("test (ubuntu-latest)")]


class ReadinessIsReadOffTheRequiredSet(unittest.TestCase):

    def test_behind_over_a_failing_required_check_needs_a_person(self):
        # The defect: the old rule read BEHIND as ready and never saw the red underneath it.
        got = collect.classify(pr([run("CI gate", "FAILURE"), run("test (ubuntu-latest)")]),
                               REQUIRED)
        self.assertEqual(got["bucket"], "person")
        self.assertEqual(got["failing"], ["CI gate"])

    def test_behind_alone_is_ready_because_the_queue_rebases_it(self):
        self.assertEqual(bucket(pr(GREEN, merge="BEHIND")), "ready")

    def test_a_red_advisory_leg_blocks_nothing(self):
        # The mirror error. UNSTABLE means a non-required check failed, which blocks no merge.
        p = pr(GREEN + [run("zizmor", "FAILURE"), run("diff-coverage", "FAILURE")],
               merge="UNSTABLE")
        self.assertEqual(bucket(p), "ready")

    def test_a_pending_required_check_is_waiting_on_ci(self):
        p = pr([run("CI gate"), run("test (ubuntu-latest)", None, status="IN_PROGRESS")],
               merge="BLOCKED")
        self.assertEqual(bucket(p), "ci")

    def test_a_required_check_not_reported_yet_is_never_ready(self):
        self.assertEqual(bucket(pr([run("CI gate")])), "ci")
        self.assertEqual(bucket(pr(None)), "ci")
        self.assertEqual(bucket(pr([])), "ci")

    def test_draft_and_conflict_need_a_person_even_when_green(self):
        self.assertEqual(bucket(pr(GREEN, draft=True)), "person")
        self.assertEqual(bucket(pr(GREEN, merge="DIRTY")), "person")

    def test_a_failure_outranks_a_pending_leg(self):
        p = pr([run("CI gate", "FAILURE"), run("test (ubuntu-latest)", None, status="QUEUED")])
        self.assertEqual(bucket(p), "person")

    def test_the_newest_run_of_a_name_decides(self):
        rerun_passed = [run("CI gate", "FAILURE", started="2026-09-19T09:00:00Z"),
                        run("CI gate", started="2026-09-19T11:00:00Z"),
                        run("test (ubuntu-latest)")]
        self.assertEqual(bucket(pr(rerun_passed)), "ready")
        # A run queued but not started has no timestamp, and is newer than the pass before it.
        rerun_queued = [run("CI gate"), run("CI gate", None, status="QUEUED", started=None),
                        run("test (ubuntu-latest)")]
        self.assertEqual(bucket(pr(rerun_queued)), "ci")

    def test_a_commit_status_counts_the_same_as_a_check_run(self):
        self.assertEqual(bucket(pr([status("CI gate", "ERROR"), run("test (ubuntu-latest)")])),
                         "person")
        self.assertEqual(bucket(pr([status("CI gate", "SUCCESS"), run("test (ubuntu-latest)")])),
                         "ready")

    def test_the_three_buckets_partition_the_open_set(self):
        prs = [pr(GREEN), pr(None), pr([run("CI gate", "FAILURE")]), pr(GREEN, draft=True)]
        got = [bucket(p) for p in prs]
        self.assertEqual(got, ["ready", "ci", "person", "person"])


def done(stdout="", code=0, stderr=""):
    return types.SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def page(nodes, total=None, more=False):
    return done(json.dumps({"data": {"repository": {"pullRequests": {
        "totalCount": len(nodes) if total is None else total,
        "pageInfo": {"hasNextPage": more, "endCursor": "c"}, "nodes": nodes}}}}))


class AReadItCannotTrustStopsTheRun(unittest.TestCase):

    def fake(self, *answers):
        calls = []
        replies = iter(answers)

        def run_(args, **_):
            calls.append(args)
            return next(replies)
        return calls, mock.patch.object(collect, "subprocess", types.SimpleNamespace(run=run_))

    def test_a_504_at_every_page_size_refuses_rather_than_reading_clean(self):
        calls, patch = self.fake(*[done(code=1, stderr="HTTP 504: Gateway Timeout")] * 3)
        with patch, self.assertRaises(SystemExit):
            collect.open_prs("o", "r")
        self.assertEqual([next(x for x in a if x.startswith("first=")) for a in calls],
                         ["first=20", "first=10", "first=5"])

    def test_a_504_then_a_smaller_page_succeeds(self):
        _, patch = self.fake(done(code=1, stderr="HTTP 504"), page([pr(GREEN)]))
        with patch:
            self.assertEqual(len(collect.open_prs("o", "r")), 1)

    def test_partial_graphql_data_is_not_a_reading(self):
        body = json.loads(page([pr(GREEN)]).stdout)
        body["errors"] = [{"message": "timeout"}]
        _, patch = self.fake(*[done(json.dumps(body))] * 3)
        with patch, self.assertRaises(SystemExit):
            collect.open_prs("o", "r")

    def test_a_short_read_refuses(self):
        _, patch = self.fake(page([pr(GREEN)], total=2))
        with patch, self.assertRaises(SystemExit):
            collect.open_prs("o", "r")

    def test_truncated_checks_refuse(self):
        p = pr(GREEN)
        p["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["pageInfo"] = {
            "hasNextPage": True}
        _, patch = self.fake(page([p]))
        with patch, self.assertRaises(SystemExit):
            collect.open_prs("o", "r")

    def test_an_unreadable_or_empty_required_set_refuses(self):
        for answer in (done(code=1, stderr="HTTP 404: Branch not protected"), done("")):
            _, patch = self.fake(answer)
            with self.subTest(answer=answer), patch, self.assertRaises(SystemExit):
                collect.required_contexts("o/r")

    def test_a_refused_collect_leaves_the_last_good_data_json(self):
        def run_(args, **_):
            if "graphql" in args:
                return done(code=1, stderr="HTTP 504")
            return done("CI gate\n")
        with tempfile.TemporaryDirectory() as tmp:
            last_good = os.path.join(tmp, "data.json")
            Path(last_good).write_text("LAST GOOD", encoding="utf-8")
            with mock.patch.object(collect, "OUT", tmp), \
                 mock.patch.object(collect, "subprocess", types.SimpleNamespace(run=run_)), \
                 self.assertRaises(SystemExit):
                collect.main()
            self.assertEqual(Path(last_good).read_text(encoding="utf-8"), "LAST GOOD")


class TheMergeWindowNeverComesFromTheSearchApi(unittest.TestCase):
    """Search does not follow a repository rename, and says so with a 422.

    `gh pr list --search` turns that into `[]` with exit 0, which is indistinguishable from a
    repository that merged nothing. These pin the REST reader that replaced it, the refusal that
    replaced the default, and the canonical repository names.
    """

    def test_every_repo_is_addressed_by_its_canonical_owner(self):
        # The stale owner is why this whole class exists: REST followed the transfer to MEFORORG
        # and search did not. A name that only resolves through a redirect is a reading waiting to
        # break, so none of the three may carry the pre-transfer owner.
        owners = {full.split("/")[0] for full, _short in collect.REPOS}
        self.assertEqual(owners, {"MEFORORG"})

    def rest(self, *pages):
        """Fake `gh api repos/X/pulls`, one answer per page, in the reader's own shape."""
        replies = iter(pages)
        return mock.patch.object(
            collect, "subprocess",
            types.SimpleNamespace(run=lambda args, **_: next(replies)))

    @staticmethod
    def row(merged, closed, created, updated):
        return " ".join([merged, closed, created, updated])

    def test_the_collector_never_shells_out_to_the_search_api(self):
        """A reader reaching for the search API reintroduces the false zero on two repositories.

        The guard reads the ARGUMENTS the module would pass, not its text. A grep over the file
        reddened on the comment that explains the trap, which is the whole failure mode this
        suite is about: a filter that did not match what the reading claimed to check.
        """
        tree = ast.parse((ROOT / "scripts/board/collect.py").read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        literals = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and n.value not in docstrings]
        # The control: the guard must be able to see a real argument in this same file, or an
        # empty result would read identically to a clean one.
        self.assertIn("--jq", literals)
        self.assertNotIn("--search", literals)
        self.assertFalse([x for x in literals if "merged:>=" in x])

    def test_no_defaulting_helper_survives(self):
        # `j(args, default)` existed to turn any failed read into a default. Its removal is the
        # point: a future reader cannot reach for it without writing the defect out longhand.
        self.assertFalse(hasattr(collect, "j"))
        self.assertFalse(hasattr(collect, "sh"))

    def test_merges_in_the_window_are_read_and_an_older_page_stops_the_walk(self):
        page1 = done(self.row("2026-09-19T10:00:00Z", "2026-09-19T10:00:00Z",
                              "2026-09-18T09:00:00Z", "2026-09-19T10:00:00Z") + "\n" +
                     self.row("-", "2026-09-19T09:00:00Z",
                              "2026-09-18T08:00:00Z", "2026-09-17T09:00:00Z") + "\n")
        with self.rest(page1):
            merged, created, closed, exhausted = collect.closed_window(
                "o/r", "2026-09-18T00:00:00Z")
        self.assertEqual(merged, ["2026-09-19T10:00:00Z"])
        self.assertEqual(len(closed), 2)
        self.assertEqual(len(created), 2)
        self.assertTrue(exhausted)

    def test_a_row_older_than_the_window_is_not_counted(self):
        page1 = done(self.row("2026-09-10T10:00:00Z", "2026-09-10T10:00:00Z",
                              "2026-09-09T09:00:00Z", "2026-09-10T10:00:00Z") + "\n")
        with self.rest(page1):
            merged, created, closed, _ = collect.closed_window("o/r", "2026-09-18T00:00:00Z")
        self.assertEqual((merged, created, closed), ([], [], []))

    def test_a_failed_page_refuses_rather_than_reporting_no_merges(self):
        # The whole defect in one assertion. The old reader returned [] here, and the board
        # then said the repository had merged nothing.
        with self.rest(done(code=1, stderr="HTTP 422: cannot be searched")):
            with self.assertRaises(SystemExit):
                collect.closed_window("o/r", "2026-09-18T00:00:00Z")

    def test_an_empty_page_ends_the_walk_without_refusing(self):
        # A repository with no closed pull requests at all is a real answer, not a failed read.
        with self.rest(done("")):
            self.assertEqual(collect.closed_window("o/r", "2026-09-18T00:00:00Z"),
                             ([], [], [], True))

    def test_a_null_merge_queue_is_zero_but_a_failed_read_refuses(self):
        # KORUS and the vault have no merge queue, so null is the truth. A failed call is not,
        # and defaulting it would publish "nothing is enqueued" while the queue runs.
        no_queue = done(json.dumps({"data": {"repository": {"mergeQueue": None}}}))
        cases = [(no_queue, False),
                 (done(code=1, stderr="HTTP 502"), True),
                 (done(json.dumps({"data": None, "errors": [{"message": "x"}]})), True)]
        for queue, expect_exit in cases:
            head = [done("CI gate\ntest (ubuntu-latest)\n"), page([pr(GREEN)]), queue]
            replies = iter(head + [done("")] * 4)
            with self.subTest(expect_exit=expect_exit), tempfile.TemporaryDirectory() as tmp:
                with mock.patch.object(collect, "OUT", tmp), \
                        mock.patch.object(collect, "REPOS", [("o/r", "r")]), \
                        mock.patch.object(collect, "subprocess", types.SimpleNamespace(
                            run=lambda a, **_: next(replies))):
                    if expect_exit:
                        with self.assertRaises(SystemExit):
                            collect.main()
                    else:
                        collect.main()
                if expect_exit:
                    self.assertFalse(os.path.exists(os.path.join(tmp, "data.json")))
                else:
                    got = json.loads(Path(tmp, "data.json").read_text(encoding="utf-8"))
                    self.assertEqual(got["repos"][0]["enqueued"], 0)

    def _created_for(self, stamp):
        """Run the collector over one open pull request created at `stamp`, return its open line."""
        replies = iter([done("CI gate\ntest (ubuntu-latest)\n"),
                        page([dict(pr(GREEN), createdAt=stamp)]),
                        done(json.dumps({"data": {"repository": {"mergeQueue": None}}})),
                        done("")])
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(collect, "OUT", tmp), \
                    mock.patch.object(collect, "REPOS", [("o/r", "r")]), \
                    mock.patch.object(collect, "subprocess", types.SimpleNamespace(
                        run=lambda a, **_: next(replies))):
                collect.main()
            got = json.loads(Path(tmp, "data.json").read_text(encoding="utf-8"))
        return got["repos"][0]["created"]

    def test_a_still_open_pull_request_contributes_its_creation(self):
        # The closed list cannot carry an open pull request. Without this the reconstructed open
        # line loses every arrival that has not closed yet, which is most of a busy window.
        #
        # THE STAMP IS RELATIVE TO THE COLLECTOR'S OWN CLOCK, and that is not tidiness. It read
        # `2026-09-19T12:00:00Z` until 2026-09-22, when the fixture aged out of the three-day
        # window `collect.main` computes from `now`. The test then failed on the calendar, with
        # nothing in the tree changed, and it would have failed every day after.
        inside = _stamp(hours_ago=1)
        self.assertEqual(self._created_for(inside), [inside])

    def test_a_pull_request_older_than_the_window_is_dropped(self):
        """The control. Without it the assertion above passes on a collector that filters nothing."""
        self.assertEqual(self._created_for(_stamp(hours_ago=24 * 4)), [])


class UnknownIsAFactAboutTheReadNotThePullRequest(unittest.TestCase):
    """UNKNOWN means GitHub has not computed mergeability, so the collector re-reads it.

    Every merge to main invalidates mergeability for every open pull request, and it is recomputed
    lazily. Measured 2026-09-19: the board printed UNKNOWN for all 7 vault rows while a live
    re-read returned BEHIND, DIRTY, CLEAN and UNSTABLE, with not one UNKNOWN among them. Section 7
    had carried "read twice, use the second" since the board was specified; the collector did not
    do it.
    """

    @staticmethod
    def answer(state):
        return done(json.dumps(
            {"data": {"repository": {"pullRequest": {"mergeStateStatus": state}}}}))

    def test_an_unknown_row_is_re_read_and_replaced(self):
        prs = [{"number": 1, "mergeStateStatus": "UNKNOWN"},
               {"number": 2, "mergeStateStatus": "CLEAN"}]
        replies = iter([self.answer("BEHIND")])
        with mock.patch.object(collect, "subprocess",
                               types.SimpleNamespace(run=lambda a, **_: next(replies))):
            left = collect.resolve_unknown("o", "r", prs, sleep=lambda _s: None)
        self.assertEqual(left, 0)
        self.assertEqual([p["mergeStateStatus"] for p in prs], ["BEHIND", "CLEAN"])

    def test_a_settled_row_is_never_re_read(self):
        # The control on the test above: if the collector re-read everything, the call count here
        # would be non-zero and the first test would pass for the wrong reason.
        prs = [{"number": 1, "mergeStateStatus": "CLEAN"},
               {"number": 2, "mergeStateStatus": "DIRTY"}]
        calls = []

        def run_(args, **_):
            calls.append(args)
            return self.answer("BEHIND")

        with mock.patch.object(collect, "subprocess", types.SimpleNamespace(run=run_)):
            left = collect.resolve_unknown("o", "r", prs, sleep=lambda _s: None)
        self.assertEqual(calls, [])
        self.assertEqual(left, 0)
        self.assertEqual([p["mergeStateStatus"] for p in prs], ["CLEAN", "DIRTY"])

    def test_a_row_that_never_settles_stays_unknown_and_is_counted(self):
        # The honest outcome. What is NOT honest is reporting the first read as though it were a
        # state, which is what the board did.
        prs = [{"number": 1, "mergeStateStatus": "UNKNOWN"}]
        with mock.patch.object(
                collect, "subprocess",
                types.SimpleNamespace(run=lambda a, **_: self.answer("UNKNOWN"))):
            left = collect.resolve_unknown("o", "r", prs, sleep=lambda _s: None)
        self.assertEqual(left, 1)
        self.assertEqual(prs[0]["mergeStateStatus"], "UNKNOWN")

    def test_it_retries_more_than_once_before_giving_up(self):
        # A single retry would have settled far fewer rows. Third attempt succeeds here.
        prs = [{"number": 1, "mergeStateStatus": "UNKNOWN"}]
        replies = iter([self.answer("UNKNOWN"), self.answer("UNKNOWN"), self.answer("CLEAN")])
        with mock.patch.object(collect, "subprocess",
                               types.SimpleNamespace(run=lambda a, **_: next(replies))):
            left = collect.resolve_unknown("o", "r", prs, sleep=lambda _s: None)
        self.assertEqual(left, 0)
        self.assertEqual(prs[0]["mergeStateStatus"], "CLEAN")

    def test_a_failed_re_read_leaves_the_row_alone_rather_than_refusing(self):
        # Deliberately unlike the other readers in this module. A stale UNKNOWN on one row is a
        # far smaller wrong than no board, and `unresolved` reports how many there were.
        prs = [{"number": 1, "mergeStateStatus": "UNKNOWN"}]
        with mock.patch.object(
                collect, "subprocess",
                types.SimpleNamespace(run=lambda a, **_: done(code=1, stderr="HTTP 502"))):
            left = collect.resolve_unknown("o", "r", prs, sleep=lambda _s: None)
        self.assertEqual(left, 1)
        self.assertEqual(prs[0]["mergeStateStatus"], "UNKNOWN")

    def test_partial_graphql_data_does_not_overwrite_the_row(self):
        prs = [{"number": 1, "mergeStateStatus": "UNKNOWN"}]
        body = {"data": {"repository": {"pullRequest": {"mergeStateStatus": "CLEAN"}}},
                "errors": [{"message": "timeout"}]}
        with mock.patch.object(
                collect, "subprocess",
                types.SimpleNamespace(run=lambda a, **_: done(json.dumps(body)))):
            left = collect.resolve_unknown("o", "r", prs, sleep=lambda _s: None)
        self.assertEqual(left, 1)
        self.assertEqual(prs[0]["mergeStateStatus"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
