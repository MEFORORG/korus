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

Nothing here calls GitHub. `subprocess` is replaced inside the module under test only.
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

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("board_collect", ROOT / "scripts/board/collect.py")
collect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = collect
SPEC.loader.exec_module(collect)

REQUIRED = {"CI gate", "test (ubuntu-latest)"}


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


if __name__ == "__main__":
    unittest.main()
