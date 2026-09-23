"""`scripts/wiki/lint.ps1` reports five classes of finding and changes nothing. Pin both halves.

THE PLANTED WORLD HOLDS EXACTLY ONE OF EACH CLASS, built on top of a clean world of the same shape.
The clean world run alone is the CONTROL: it must report zero of every class, and its inputs line
must count the events it read. A zero from a lint that read nothing is the false clean Article V
forbids, so the control asserts the read, and asserts that evidence was RESOLVED, not skipped.

LINT IS REPORT-ONLY (spec FR-020). Every file under the state root and the record repository is
hashed before and after a run, and the two maps must be equal: same files, same bytes.

UNCHECKED IS NEITHER PASS NOR DEAD. An Owner ruling, a `memory:` source, or any citation with no
evidence repository given is counted as unchecked, so a zero dead count cannot be read as clean.

Run: python -m pytest tests/test_wiki_lint.py
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import _wikitest as w

LINT = w.WIKI / "lint.ps1"
CLASSES = ("conflict", "dead-evidence", "stale", "orphan-page", "promotion-candidate")
# Hex with a digit, so it reads as a commit, and absent from any throwaway repository.
MISSING_SHA = "0badc0de4242"


def tree_hashes(*roots: Path) -> dict[str, str]:
    out = {}
    for root in roots:
        for f in sorted(root.rglob("*")):
            if f.is_file():
                out[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


class _LintCase(unittest.TestCase):
    def setUp(self):
        self.pwsh = w.find_pwsh_or_skip(self)
        tmp = tempfile.TemporaryDirectory(prefix="wiki-lint-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / "state"
        self.state.mkdir()
        self.inbox = w.inbox_dir(self.state)
        self.vault = self.root / "vault"
        (self.vault / "wiki" / "pages").mkdir(parents=True)
        self.repo = w.make_repo(self.root / "engine", None)
        self.sha = w.git(self.repo, "rev-parse", "HEAD").stdout.strip()[:10]

    def log(self, days: float, **fields) -> dict:
        when = w.days_ago(days)
        fields.setdefault("evidence", self.sha)
        return w.plant(w.log_dir(self.vault, when), when=when, **fields)

    def page(self, name: str, text: str) -> None:
        (self.vault / "wiki" / "pages" / name).write_text(text, encoding="utf-8")

    def index(self, text: str) -> None:
        (self.vault / "wiki" / "index.md").write_text(text, encoding="utf-8")

    def lint(self, *extra: str, repos: bool = True, code: int = 0):
        args = ["-StateRoot", str(self.state), "-RecordRepo", str(self.vault)]
        if repos:
            args += ["-EvidenceRepo", str(self.repo)]
        r = w.run(self.pwsh, LINT, *args, *extra)
        self.assertEqual(code, r.returncode, r.stderr + r.stdout)
        return r

    def lint_json(self, *extra: str, repos: bool = True) -> dict:
        return json.loads(self.lint("-Json", *extra, repos=repos).stdout)

    def by_class(self, doc: dict) -> dict[str, list[dict]]:
        out = {c: [] for c in CLASSES}
        for f in doc["findings"]:
            out[f["class"]].append(f)
        return out

    def build_clean_world(self) -> None:
        """Five events on five keys, one seat per key, fresh, every commit and ref:path resolving;
        three pages, each linked from the index or from another page; a wiki/log.md line."""
        self.clean = [
            self.log(2, key="gate/ascii/exit-code", seat="builder", summary="The ascii gate returns 2 on an empty scan"),
            self.log(3, key="hooks/stash", seat="lander", evidence=f"main:a.txt", summary="Never pop the shared stash"),
            self.log(4, key="coord/mail", seat="manager", type="decision", summary="Mail needs an explicit recipient"),
            self.log(60, key="coord/old-decision", seat="manager", type="decision", summary="An old decision is not stale by age"),
            w.plant(self.inbox, key="wiki/inbox-note", seat="builder", evidence=self.sha, summary="An inbox note counts too"),
        ]
        self.page("gate--ascii.md", "# gate/ascii\n\nSee [the parent](gate.md).\n")
        self.page("gate.md", "# gate\n")
        self.page("hooks.md", "# hooks\n")
        self.index("# Index\n\n- [gate/ascii](pages/gate--ascii.md)\n- [hooks](pages/hooks.md)\n\n## Conflicts\n\nNone.\n")
        (self.vault / "wiki" / "log.md").write_text("- 2026-09-22 compiled 5 events\n", encoding="utf-8")

    def plant_one_of_each(self) -> dict:
        p = {}
        p["conflict"] = [
            self.log(5, key="deploy/window", seat="builder", summary="Deploys run on Tuesday"),
            self.log(4, key="deploy/window", seat="builder", summary="Deploys run on Thursday"),
        ]
        p["dead"] = self.log(3, key="dead/one", seat="builder", evidence=MISSING_SHA, summary="Cites a commit nobody has")
        p["stale"] = self.log(60, key="old/lesson", seat="builder", summary="A lesson from two months ago")
        self.page("orphan.md", "# nobody links here\n\n[The index](../index.md)\n")
        first = self.log(6, key="lesson/twice", seat="builder", summary="Quote the Windows path")
        second = self.log(5, key="lesson/twice", seat="lander", summary="Quote the Windows path, always",
                          supersedes=[first["id"]])
        p["promotion"] = [first, second]
        return p


class TheControl(_LintCase):
    def test_a_clean_world_reports_zero_of_every_class_after_reading_its_events(self):
        self.build_clean_world()
        doc = self.lint_json()
        self.assertEqual({c: 0 for c in CLASSES}, {c: doc["totals"][c] for c in CLASSES}, doc["findings"])
        self.assertEqual([], doc["findings"])
        # ARMED: the zero came from reading five events and resolving their evidence.
        self.assertEqual(5, doc["inputs"]["events"])
        self.assertEqual(1, doc["inputs"]["inbox_events"])
        self.assertEqual(4, doc["inputs"]["log_events"])
        self.assertEqual(3, doc["inputs"]["pages"])
        self.assertEqual(5, doc["evidence"]["resolved"])
        self.assertEqual(0, doc["evidence"]["unchecked"])

    def test_the_markdown_inputs_line_counts_what_was_read(self):
        self.build_clean_world()
        out = self.lint().stdout
        self.assertIn("inputs: 5 event(s) read (inbox 1, log 4)", out)
        self.assertIn("3 page(s)", out)
        self.assertIn("| unchecked | 0 |", out)
        for c in CLASSES:
            self.assertIn(f"| {c} | 0 |", out)


class OneOfEachClass(_LintCase):
    def setUp(self):
        super().setUp()
        self.build_clean_world()
        self.p = self.plant_one_of_each()
        self.doc = self.lint_json()
        self.found = self.by_class(self.doc)

    def test_every_class_is_reported_exactly_once(self):
        self.assertEqual({c: 1 for c in CLASSES}, {c: len(v) for c, v in self.found.items()}, self.doc["findings"])
        self.assertEqual({**{c: 1 for c in CLASSES}, "unchecked": 0}, self.doc["totals"])

    def test_the_conflict_names_both_events(self):
        f = self.found["conflict"][0]
        self.assertEqual("conflict:deploy/window", f["id"])
        self.assertEqual(sorted(e["id"] for e in self.p["conflict"]), f["events"])

    def test_the_dead_evidence_names_the_event_and_the_citation(self):
        f = self.found["dead-evidence"][0]
        self.assertEqual(f"dead-evidence:{self.p['dead']['id']}:{MISSING_SHA}", f["id"])
        self.assertEqual([self.p["dead"]["id"]], f["events"])
        self.assertIn("resolves in none", f["reason"])

    def test_the_stale_lesson_is_named_and_the_old_decision_is_not(self):
        f = self.found["stale"][0]
        self.assertEqual(f"stale:{self.p['stale']['id']}", f["id"])
        self.assertEqual([self.p["stale"]["id"]], f["events"])

    def test_the_orphan_page_is_named(self):
        self.assertEqual("orphan-page:orphan.md", self.found["orphan-page"][0]["id"])

    def test_the_promotion_candidate_names_both_seats(self):
        f = self.found["promotion-candidate"][0]
        self.assertEqual("promotion-candidate:key:lesson/twice", f["id"])
        self.assertEqual(sorted(e["id"] for e in self.p["promotion"]), f["events"])
        self.assertEqual(["builder", "lander"], f["seats"])

    def test_the_markdown_report_names_every_finding_and_says_who_decides(self):
        out = self.lint().stdout
        for f in self.doc["findings"]:
            self.assertIn(f"`{f['id']}`", out)
        for c in CLASSES:
            self.assertIn(f"| {c} | 1 |", out)
        self.assertIn("DRAFT that only the Owner decides", out)


class LintChangesNothing(_LintCase):
    def test_every_file_under_the_state_root_and_record_repo_is_byte_identical(self):
        self.build_clean_world()
        self.plant_one_of_each()
        before = tree_hashes(self.state, self.vault)
        self.assertGreater(len(before), 10)
        self.lint()
        self.lint("-Json")
        report = self.root / "report.md"
        self.lint("-Out", str(report))
        self.assertEqual(before, tree_hashes(self.state, self.vault))
        self.assertIn("## Totals", report.read_text(encoding="utf-8"))

    def test_out_inside_the_inbox_is_refused(self):
        self.build_clean_world()
        r = self.lint("-Out", str(self.inbox / "report.md"), code=2)
        self.assertIn("never writes to", r.stderr)
        self.assertFalse((self.inbox / "report.md").exists())


class Conflicts(_LintCase):
    def test_a_superseded_pair_is_not_a_conflict(self):
        a = self.log(5, key="rule/x", summary="first wording")
        self.log(4, key="rule/x", summary="second wording", supersedes=[a["id"]])
        self.assertEqual(0, self.lint_json()["totals"]["conflict"])

    def test_control_the_same_pair_without_supersedes_is_a_conflict(self):
        self.log(5, key="rule/x", summary="first wording")
        self.log(4, key="rule/x", summary="second wording")
        self.assertEqual(1, self.lint_json()["totals"]["conflict"])

    def test_a_retired_key_is_not_a_conflict(self):
        self.log(5, key="rule/x", summary="first wording")
        self.log(4, key="rule/x", summary="second wording")
        self.log(3, key="rule/x", type="retire", summary="withdrawn")
        self.assertEqual(0, self.lint_json()["totals"]["conflict"])

    def test_an_inbox_and_a_log_event_on_one_key_conflict(self):
        self.log(5, key="rule/y", summary="compiled wording")
        w.plant(self.inbox, key="rule/y", evidence=self.sha, summary="uncompiled wording")
        self.assertEqual(["conflict:rule/y"], [f["id"] for f in self.lint_json()["findings"]])


class Evidence(_LintCase):
    def test_an_owner_ruling_with_no_evidence_repos_is_unchecked_not_dead(self):
        self.log(2, key="ruling/one", evidence="Owner ruling 2026-09-20")
        doc = self.lint_json(repos=False)
        self.assertEqual(1, doc["evidence"]["unchecked"])
        self.assertEqual(1, doc["totals"]["unchecked"])
        self.assertEqual(0, doc["evidence"]["dead"])
        self.assertEqual(0, doc["evidence"]["resolved"])

    def test_a_commit_with_no_evidence_repos_is_unchecked_not_dead(self):
        self.log(2, key="c/one", evidence=MISSING_SHA)
        doc = self.lint_json(repos=False)
        self.assertEqual((0, 1), (doc["evidence"]["dead"], doc["evidence"]["unchecked"]))

    def test_a_commit_in_the_repo_is_not_dead_and_one_absent_is(self):
        ok = self.log(2, key="c/ok", evidence=self.sha)
        bad = self.log(2, key="c/bad", evidence=MISSING_SHA)
        doc = self.lint_json()
        dead = [f["events"] for f in doc["findings"] if f["class"] == "dead-evidence"]
        self.assertEqual([[bad["id"]]], dead)
        self.assertNotIn([ok["id"]], dead)
        self.assertEqual((1, 1), (doc["evidence"]["resolved"], doc["evidence"]["dead"]))

    def test_a_ref_path_absent_at_its_ref_is_dead_and_a_present_one_is_not(self):
        self.log(2, key="p/ok", evidence="main:a.txt")
        bad = self.log(2, key="p/bad", evidence="main:docs/gone.md")
        doc = self.lint_json()
        self.assertEqual([f"dead-evidence:{bad['id']}:main:docs/gone.md"],
                         [f["id"] for f in doc["findings"]])

    def test_a_memory_source_and_a_pr_offline_are_unchecked(self):
        self.log(2, key="memory/a-note", evidence="memory:acct-1/a-note.md")
        self.log(2, key="pr/one", evidence="PR #42")
        doc = self.lint_json()
        self.assertEqual((0, 2), (doc["evidence"]["dead"], doc["evidence"]["unchecked"]))

    def test_an_all_digit_date_is_not_called_a_dead_commit(self):
        self.log(2, key="d/one", evidence="measured 20260921, see " + self.sha)
        doc = self.lint_json()
        self.assertEqual((1, 0, 1), (doc["evidence"]["resolved"], doc["evidence"]["dead"], doc["evidence"]["unchecked"]))


class Staleness(_LintCase):
    def test_past_stale_after_is_stale_whatever_the_type(self):
        e = self.log(2, key="s/dated", type="decision", stale_after="2000-01-01")
        self.assertEqual([f"stale:{e['id']}"], [f["id"] for f in self.lint_json()["findings"]])

    def test_today_moves_the_clock(self):
        self.log(2, key="s/dated", type="decision", stale_after="2099-01-01")
        self.assertEqual(0, self.lint_json()["totals"]["stale"])
        self.assertEqual(1, self.lint_json("-Today", "2099-01-02")["totals"]["stale"])

    def test_a_gotcha_46_days_old_is_stale_and_45_is_not(self):
        # -Today pins the day the ages were planted against, so a run that crosses midnight UTC
        # cannot move either event across the line.
        today = w.days_ago(0).strftime("%Y-%m-%d")
        old = self.log(46, key="s/g46", type="gotcha")
        self.log(45, key="s/g45", type="gotcha")
        found = self.lint_json("-Today", today)["findings"]
        self.assertEqual([f"stale:{old['id']}"], [f["id"] for f in found])


class Pages(_LintCase):
    def test_a_wikilink_from_another_page_counts_and_a_self_link_does_not(self):
        self.page("a.md", "# a\n\n[[b]]\n")
        self.page("b.md", "# b\n")
        self.page("self.md", "# self\n\n[me](self.md) and [[self]]\n")
        self.index("# Index\n\n- [a](pages/a.md)\n")
        self.assertEqual(["orphan-page:self.md"], [f["id"] for f in self.lint_json()["findings"]])

    def test_with_no_index_only_page_links_count(self):
        self.page("a.md", "# a\n\n[b](b.md)\n")
        self.page("b.md", "# b\n")
        doc = self.lint_json()
        self.assertEqual(["orphan-page:a.md"], [f["id"] for f in doc["findings"]])


class Promotion(_LintCase):
    def test_one_memory_summary_under_two_keys_by_two_seats_is_a_candidate(self):
        a = self.log(3, key="memory/quote-paths", seat="builder", evidence="memory:acct-1/quote-paths.md",
                     summary="Quote the Windows path")
        b = self.log(3, key="memory/windows-paths", seat="lander", evidence="memory:acct-2/windows-paths.md",
                     summary="quote the  windows path")
        found = [f for f in self.lint_json()["findings"] if f["class"] == "promotion-candidate"]
        self.assertEqual(1, len(found))
        self.assertTrue(found[0]["id"].startswith("promotion-candidate:summary:"))
        self.assertEqual(sorted([a["id"], b["id"]]), found[0]["events"])

    def test_control_different_summaries_are_not(self):
        self.log(3, key="memory/quote-paths", seat="builder", evidence="memory:acct-1/q.md", summary="Quote the Windows path")
        self.log(3, key="memory/windows-paths", seat="lander", evidence="memory:acct-2/w.md", summary="Escape the Windows path")
        self.assertEqual(0, self.lint_json()["totals"]["promotion-candidate"])

    def test_one_seat_twice_is_not_a_candidate(self):
        a = self.log(5, key="lesson/once", seat="builder")
        self.log(4, key="lesson/once", seat="builder", supersedes=[a["id"]])
        self.assertEqual(0, self.lint_json()["totals"]["promotion-candidate"])


class CannotRun(_LintCase):
    def test_a_missing_state_root_exits_2(self):
        r = w.run(self.pwsh, LINT, "-StateRoot", str(self.root / "nope"), "-RecordRepo", str(self.vault))
        self.assertEqual(2, r.returncode, r.stderr)

    def test_a_bad_today_exits_2(self):
        self.lint("-Today", "yesterday", code=2)

    def test_an_evidence_repo_that_is_not_git_exits_2(self):
        plain = self.root / "plain"
        plain.mkdir()
        r = w.run(self.pwsh, LINT, "-StateRoot", str(self.state), "-RecordRepo", str(self.vault),
                  "-EvidenceRepo", str(plain))
        self.assertEqual(2, r.returncode, r.stderr)
        self.assertIn("not a git repository", r.stderr)

    def test_two_evidence_repos_as_one_comma_string_are_both_read(self):
        other = w.make_repo(self.root / "korus", None)
        other_sha = w.git(other, "rev-parse", "HEAD").stdout.strip()[:10]
        self.log(2, key="c/one", evidence=self.sha)
        self.log(2, key="c/two", evidence=other_sha)
        r = w.run(self.pwsh, LINT, "-StateRoot", str(self.state), "-RecordRepo", str(self.vault),
                  "-EvidenceRepo", f"{self.repo},{other}", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual(2, len(doc["inputs"]["evidence_repos"]))
        self.assertEqual((2, 0), (doc["evidence"]["resolved"], doc["evidence"]["dead"]))


if __name__ == "__main__":
    unittest.main()
