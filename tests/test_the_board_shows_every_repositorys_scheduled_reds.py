"""The Lander Board shows a red scheduled run in EVERY repository it reads, not only the engine.

WHAT THIS EXISTS FOR. The scheduled-run panel read only the issues the engine's
`nightly-notice.yml` writes. korus and the vault carry no such workflow, so the panel printed "not
read" for both and a red there reached nobody. Measured 2026-10-01: the vault's ASVS scorecard had
failed its last 30 scheduled runs. Owner instruction 2026-10-01: make those visible.

THE READ IS EACH REPOSITORY'S OWN RUN LIST, so a scheduled workflow added later, or a repository
added to REPOS, is covered with no edit. Both arms run on one fixture: a red that must show, and a
green, a cancelled run, a disabled workflow and a dropped cron that must not.

A FAILED READ REFUSES THE COLLECT. Owner instruction 2026-10-01: keep the fail-closed rule. The
refusal leaves the last good data.json, and the page never prints "nothing is red" off a read that
did not happen.

Nothing here calls GitHub. `subprocess` is replaced inside the collector, and `build.py` is run as
a subprocess over a fixture, which is the real rendering path.
"""
import base64
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from test_the_person_card_decomposes_without_double_counting import render, repo

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("board_collect_scheduled",
                                              ROOT / "scripts/board/collect.py")
collect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = collect
SPEC.loader.exec_module(collect)

VAULT = "MEFORORG/MessageFoundry-vault"
SCHEDULED_YAML = "on:\n  schedule:\n    - cron: '17 6 * * *'\n  workflow_dispatch:\n"
NO_CRON_YAML = "on:\n  push:\n    branches: [main]\n"
# The vault's ci.yml dropped its cron and kept a comment naming the old `schedule:` trigger.
COMMENTED_CRON_YAML = "# the nightly `schedule:` trigger was removed\non:\n  push:\n"


def done(stdout="", code=0, stderr=""):
    return types.SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def flow(wid, name, state="active"):
    return json.dumps([wid, state, ".github/workflows/%s.yml" % name.lower(), name])


def run(rid, wid, conclusion, created, status="completed", total=None):
    return [total, rid, wid, status, conclusion, created,
            "https://github.com/%s/actions/runs/%d" % (VAULT, rid)]


def lines(rows, total=None):
    """Runs in the shape the collector's own `--jq` program prints: one JSON array per line."""
    total = len(rows) if total is None else total
    return "\n".join(json.dumps([total] + r[1:]) for r in rows) + "\n"


def fake(flows, runs, yaml=SCHEDULED_YAML, total=None, fail=None):
    """A `gh` that answers the three reads. `fail` names a read to fail: flows, runs, contents."""
    calls = []

    def run_(args, **_):
        calls.append(args)
        joined = " ".join(args)
        for key, answer in (("actions/workflows", "\n".join(flows) + "\n"),
                            ("actions/runs", lines(runs, total)),
                            ("/contents/", json.dumps(base64.b64encode(
                                yaml.encode()).decode()) + "\n")):
            if key in joined:
                if fail and fail in key:
                    return done(code=1, stderr="HTTP 502")
                return done(answer)
        raise AssertionError("unexpected call: %s" % joined)
    return calls, mock.patch.object(collect, "subprocess", types.SimpleNamespace(run=run_))


def read(flows, runs, **kw):
    calls, patch = fake(flows, runs, **kw)
    with patch:
        return collect.scheduled_reds(VAULT, "2026-08-27"), calls


class TheCollectorReadsEachWorkflowsLatestVerdict(unittest.TestCase):

    def test_a_red_after_a_green_is_shown_with_its_streak(self):
        """The positive control for every case below."""
        got, _ = read([flow(1, "ASVS scorecard")],
                      [run(3, 1, "failure", "2026-10-01T13:13:02Z"),
                       run(2, 1, "failure", "2026-09-30T13:13:02Z"),
                       run(1, 1, "success", "2026-09-29T13:13:02Z")])
        self.assertEqual(got["read"], 1)
        [red] = got["reds"]
        self.assertEqual((red["workflow"], red["conclusion"], red["streak"]),
                         ("ASVS scorecard", "failure", 2))
        self.assertEqual(red["since"], "2026-09-30T13:13:02Z")
        self.assertEqual(red["latest"], "2026-10-01T13:13:02Z")
        self.assertEqual(red["last_green"], "2026-09-29T13:13:02Z")
        self.assertFalse(red["floor"])
        self.assertTrue(red["url"].endswith("/runs/3"))

    def test_a_green_latest_run_is_read_and_not_shown(self):
        got, _ = read([flow(1, "CI")], [run(2, 1, "success", "2026-10-01T00:00:00Z"),
                                        run(1, 1, "failure", "2026-09-30T00:00:00Z")])
        self.assertEqual((got["read"], got["reds"]), (1, []))

    def test_a_cancelled_or_unfinished_run_is_stepped_over(self):
        for conclusion, expect in (("failure", 1), ("success", 0)):
            got, _ = read([flow(1, "CI")],
                          [run(4, 1, None, "2026-10-01T02:00:00Z", status="in_progress"),
                           run(3, 1, "cancelled", "2026-10-01T01:00:00Z"),
                           run(2, 1, conclusion, "2026-10-01T00:00:00Z")])
            with self.subTest(conclusion=conclusion):
                self.assertEqual(len(got["reds"]), expect)

    def test_a_conclusion_it_does_not_know_is_red_never_hidden(self):
        for conclusion in ("timed_out", "startup_failure", "a_value_github_adds_later"):
            got, _ = read([flow(1, "CI")], [run(1, 1, conclusion, "2026-10-01T00:00:00Z")])
            with self.subTest(conclusion=conclusion):
                self.assertEqual([r["conclusion"] for r in got["reds"]], [conclusion])

    def test_a_disabled_workflow_is_not_read(self):
        got, _ = read([flow(1, "Security", state="disabled_manually")],
                      [run(1, 1, "failure", "2026-10-01T00:00:00Z")])
        self.assertEqual((got["read"], got["reds"]), (0, []))

    def test_a_red_whose_file_dropped_its_cron_is_named_not_shown(self):
        for yaml in (NO_CRON_YAML, COMMENTED_CRON_YAML):
            got, _ = read([flow(1, "CI")], [run(1, 1, "failure", "2026-09-16T03:30:24Z")],
                          yaml=yaml)
            with self.subTest(yaml=yaml):
                self.assertEqual((got["reds"], got["unscheduled"]), ([], ["CI"]))

    def test_the_schedule_check_asks_only_about_a_red_and_reads_the_default_branch(self):
        _, calls = read([flow(1, "Green"), flow(2, "Red")],
                        [run(2, 2, "failure", "2026-10-01T00:00:00Z"),
                         run(1, 1, "success", "2026-10-01T00:00:00Z")])
        contents = [a for a in calls if any("/contents/" in x for x in a)]
        self.assertEqual(len(contents), 1)
        self.assertIn("repos/%s/contents/.github/workflows/red.yml" % VAULT, contents[0])
        self.assertFalse(any(x.startswith("ref=") for x in contents[0]))

    def test_every_run_in_the_window_red_makes_the_streak_a_floor(self):
        got, _ = read([flow(1, "ASVS scorecard")],
                      [run(2, 1, "failure", "2026-10-01T00:00:00Z"),
                       run(1, 1, "failure", "2026-08-27T09:25:30Z")])
        [red] = got["reds"]
        self.assertEqual((red["streak"], red["floor"], red["last_green"]), (2, True, None))
        self.assertEqual(red["since"], "2026-08-27T09:25:30Z")

    def test_order_comes_from_the_instant_not_the_read_order(self):
        got, _ = read([flow(1, "CI")], [run(1, 1, "success", "2026-09-30T00:00:00Z"),
                                        run(2, 1, "failure", "2026-10-01T00:00:00Z")])
        self.assertEqual([r["conclusion"] for r in got["reds"]], ["failure"])

    def test_a_row_read_twice_counts_once(self):
        r = run(1, 1, "failure", "2026-10-01T00:00:00Z")
        got, _ = read([flow(1, "CI")], [r, r], total=1)
        self.assertEqual(got["reds"][0]["streak"], 1)

    def test_the_read_asks_for_scheduled_runs_in_the_window_and_every_page(self):
        _, calls = read([flow(1, "CI")], [])
        [runs] = [a for a in calls if any("actions/runs" in x for x in a)]
        for want in ("event=schedule", "created=>=2026-08-27", "--paginate"):
            self.assertIn(want, runs)
        [flows] = [a for a in calls if any("actions/workflows" in x for x in a)]
        self.assertIn("--paginate", flows)

    def test_no_scheduled_run_at_all_is_a_zero_with_nothing_read(self):
        got, _ = read([flow(1, "CI")], [])
        self.assertEqual((got["read"], got["reds"], got["window_days"]),
                         (0, [], collect.SCHEDULE_WINDOW_DAYS))


class AReadThatCannotBeTrustedRefuses(unittest.TestCase):

    def assertRefuses(self, *args, **kw):
        with self.assertRaises(SystemExit):
            read(*args, **kw)

    def test_a_failed_read_of_any_of_the_three_refuses(self):
        for which in ("workflows", "runs", "contents"):
            with self.subTest(which=which):
                self.assertRefuses([flow(1, "CI")],
                                   [run(1, 1, "failure", "2026-10-01T00:00:00Z")], fail=which)

    def test_a_row_it_cannot_read_refuses(self):
        bad = run(1, 1, "failure", "2026-10-01")  # no zone: not an instant the board can age
        self.assertRefuses([flow(1, "CI")], [bad])
        self.assertRefuses(['["1", "active", "p", "CI"]'], [])
        with self.assertRaises(SystemExit):
            calls, patch = fake([flow(1, "CI")], [])
            with patch, mock.patch.object(collect, "subprocess", types.SimpleNamespace(
                    run=lambda a, **_: done("not json\n"))):
                collect.scheduled_reds(VAULT, "2026-08-27")

    def test_fewer_runs_than_the_api_reports_refuses(self):
        self.assertRefuses([flow(1, "CI")], [run(1, 1, "success", "2026-10-01T00:00:00Z")],
                           total=2)

    def test_a_window_past_the_api_cap_refuses(self):
        self.assertRefuses([flow(1, "CI")], [run(1, 1, "success", "2026-10-01T00:00:00Z")],
                           total=collect.RUNS_API_CAP + 1)


def pr_page():
    return done(json.dumps({"data": {"repository": {"pullRequests": {
        "totalCount": 0, "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": []}}}}))


class TheCollectorReadsEveryRepository(unittest.TestCase):

    def run_main(self, out, runs_answer):
        calls = []

        def run_(args, **_):
            calls.append(args)
            joined = " ".join(args)
            if "/protection/" in joined:
                return done("gates\n")
            if "pullRequests" in joined:
                return pr_page()
            if "mergeQueue" in joined:
                return done(json.dumps({"data": {"repository": {"mergeQueue": None}}}))
            if "/pulls" in joined or "/issues" in joined:
                return done("")
            if "actions/workflows" in joined:
                return done(flow(1, "CI") + "\n")
            if "actions/runs" in joined:
                return runs_answer
            if "/contents/" in joined:
                return done(json.dumps(base64.b64encode(SCHEDULED_YAML.encode()).decode()))
            raise AssertionError("unexpected call: %s" % joined)
        repos = [("MEFORORG/MessageFoundry", "engine"), ("o/r", "r"), (VAULT, "vault")]
        with mock.patch.object(collect, "OUT", out), \
                mock.patch.object(collect, "REPOS", repos), \
                mock.patch.object(collect, "subprocess", types.SimpleNamespace(run=run_)):
            collect.main()
        return calls

    def test_every_repository_is_read_not_only_the_one_with_a_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = self.run_main(tmp, done(lines([run(1, 1, "failure",
                                                       "2026-10-01T00:00:00Z")])))
            got = json.loads(Path(tmp, "data.json").read_text(encoding="utf-8"))
        for r in got["repos"]:
            with self.subTest(repo=r["short"]):
                self.assertEqual([x["workflow"] for x in r["scheduled"]["reds"]], ["CI"])
        reads = [a for a in calls if any("actions/runs" in x for x in a)]
        self.assertEqual(len(reads), 3)

    def test_a_failed_scheduled_run_read_leaves_the_last_good_data_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "data.json").write_text("LAST GOOD", encoding="utf-8")
            with self.assertRaises(SystemExit):
                self.run_main(tmp, done(code=1, stderr="HTTP 502"))
            self.assertEqual(Path(tmp, "data.json").read_text(encoding="utf-8"), "LAST GOOD")


def red(workflow, since, streak=2, floor=False, green="2026-09-19T06:00:00Z",
        latest="2026-09-20T06:00:00Z"):
    return {"workflow": workflow, "path": ".github/workflows/x.yml", "conclusion": "failure",
            "latest": latest, "url": "https://github.com/%s/actions/runs/7" % VAULT,
            "since": since, "streak": streak, "floor": floor,
            "last_green": None if floor else green}


def sched(reds=(), read=4, unscheduled=()):
    return {"window_days": 35, "read": read, "reds": list(reds),
            "unscheduled": list(unscheduled)}


def board(engine=None, korus=None, vault=None, drop_vault=False):
    """Render the real board. The fixture clock is 2026-09-20T18:00:00Z, set by render()."""
    repos = [repo("engine", []), repo("korus", []), repo("vault", [])]
    for r, v in zip(repos, (engine, korus, vault)):
        r["scheduled"] = sched() if v is None else v
    if drop_vault:
        del repos[2]["scheduled"]
    return render(repos)


def part(html):
    """The scheduled-run half of the panel alone, so the issue half cannot satisfy a case."""
    start = html.index("Latest scheduled run, every repository.")
    return html[start:html.index("Open nightly-failure issues", start)]


class TheBoardShowsEachRedAndHowLongItHasBeenRed(unittest.TestCase):

    def test_a_red_is_shown_with_its_link_and_span(self):
        """The positive control for every rendering case below."""
        p = part(board(vault=sched([red("ASVS scorecard", "2026-09-18T18:00:00Z")])))
        self.assertIn('href="https://github.com/%s/actions/runs/7">ASVS scorecard</a>' % VAULT, p)
        self.assertIn("<td>Vault</td>", p)
        self.assertIn("<td>failure</td>", p)
        self.assertIn("<td>2d 0h</td>", p)
        self.assertIn("<td>2</td>", p)
        self.assertIn("<b>1</b> scheduled workflow red", p)
        self.assertIn("The longest has been red <b>2d 0h</b>", p)

    def test_a_floor_says_so_in_every_cell_it_touches(self):
        p = part(board(vault=sched([red("ASVS scorecard", "2026-08-27T09:25:30Z", streak=30,
                                        floor=True)])))
        for want in ("on or before Aug 27", "<td>at least 24d 8h</td>", "<td>30 or more</td>",
                     "<td>none in the window</td>", "red <b>at least 24d 8h</b>"):
            self.assertIn(want, p)

    def test_the_longest_red_leads_whichever_repository_holds_it(self):
        p = part(board(engine=sched([red("Young", "2026-09-20T12:00:00Z")]),
                       vault=sched([red("Old", "2026-09-10T12:00:00Z")])))
        self.assertLess(p.index(">Old<"), p.index(">Young<"))
        self.assertIn("<b>2</b> scheduled workflows red", p)

    def test_every_repository_read_and_none_red_says_so_and_how_much_was_read(self):
        p = part(board())
        self.assertIn("No scheduled run is red in <b>Engine, Vault, KORUS</b>. 12 workflows", p)
        self.assertIn("last 35 days", p)

    def test_a_repository_not_read_never_counts_as_clear(self):
        p = part(board(drop_vault=True))
        self.assertNotIn("No scheduled run is red in <b>Engine, Vault, KORUS</b>", p)
        self.assertIn("not every repository was read", p)
        self.assertIn("Vault: not read: data.json predates the scheduled-run read", p)

    def test_an_unexpected_value_renders_as_not_read_and_never_raises(self):
        for value in ("garbage", [], {"reds": "x"}, {"reds": [], "read": -1, "window_days": 35}):
            with self.subTest(value=value):
                p = part(board(vault=value))
                self.assertIn("Vault: not read: unrecognised value", p)
                self.assertNotIn("No scheduled run is red in <b>Engine, Vault, KORUS</b>", p)

    def test_a_malformed_red_row_is_reported_and_blocks_the_clear_headline(self):
        for bad in ({"workflow": "x"}, dict(red("x", "2026-09-20T00:00:00"), floor=False),
                    dict(red("x", "2026-09-20T00:00:00Z"), streak=True), "row"):
            with self.subTest(bad=bad):
                p = part(board(vault=sched([bad])))
                self.assertIn("Vault: 1 red row in data.json is malformed and not shown.", p)
                self.assertIn("not every repository was read", p)

    def test_a_dropped_cron_is_named(self):
        p = part(board(vault=sched(unscheduled=["CI"])))
        self.assertIn("Vault: CI last ran red on a schedule, but the workflow file no longer "
                      "declares one", p)

    def test_a_template_token_in_a_workflow_name_stays_text(self):
        p = part(board(vault=sched([red("{{BARS}}", "2026-09-20T00:00:00Z")])))
        self.assertIn("&#123;&#123;BARS}}", p)

    def test_a_red_started_after_the_stamp_reads_zero_not_negative(self):
        p = part(board(vault=sched([red("CI", "2026-09-20T18:05:00Z",
                                        latest="2026-09-20T18:05:00Z")])))
        self.assertIn("<td>0m</td>", p)


if __name__ == "__main__":
    unittest.main()
