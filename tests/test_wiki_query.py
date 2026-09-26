"""`scripts/wiki/query.ps1` answers a seat's question, or says `no note`. Pin both halves.

THE `no note` CASE IS ARMED. A query that prints `no note` over a corpus it never read looks exactly
like one that read it and found nothing. So every `no note` below sits beside a control query, over
the same files, that must find the planted event -- and the stderr receipt must count what was read.

STORY 3 IS RUN ACROSS TWO PROCESSES AND TWO WORKTREES. The claim is that an event written in one
place is found from another before any compile runs, so a single process proves nothing about it.
The worktree case also leaves -StateRoot off, so it exercises the default the seats will use.

Run: python -m pytest tests/test_wiki_query.py
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import _wikitest as w


class _QueryCase(unittest.TestCase):
    def setUp(self):
        self.pwsh = w.find_pwsh_or_skip(self)
        tmp = tempfile.TemporaryDirectory(prefix="wiki-query-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / "state"
        self.state.mkdir()
        self.inbox = w.inbox_dir(self.state)

    def query(self, *args: str, state=None, cwd: Path | None = None, env: dict | None = None):
        argv = list(args)
        if state is not False:
            argv += ["-StateRoot", str(state or self.state)]
        r = w.run(self.pwsh, w.QUERY, *argv, cwd=cwd, env=env)
        self.assertEqual(0, r.returncode, f"query exited {r.returncode}: {r.stderr}")
        return r

    def rows(self, *args: str, **kw) -> list[dict]:
        return json.loads(self.query(*args, "-Json", **kw).stdout)


class AnUnrelatedQuerySaysNoNote(_QueryCase):
    def setUp(self):
        super().setUp()
        self.planted = w.plant(self.inbox, key="gate/ascii/windows-exit-code",
                               summary="The ascii gate collapses exit code two to one on windows")

    def test_it_prints_exactly_no_note(self):
        r = self.query("-Text", "best pizza in Atlanta")
        self.assertEqual("no note", r.stdout.strip())
        self.assertIn("searched 1 event(s)", r.stderr, "the receipt must show the corpus was read")

    def test_the_control_query_finds_the_planted_event(self):
        """Same files, same process shape: the event IS findable, so the `no note` above is armed."""
        r = self.query("-Text", "ascii gate exit code on windows")
        self.assertEqual([self.planted["id"]], w.ids_in(r.stdout))
        for field in (self.planted["seat"], self.planted["evidence"], "[inbox]", self.planted["ts"][:10]):
            self.assertIn(field, r.stdout)

    def test_a_partial_overlap_below_the_floor_is_not_filler(self):
        """One word of four in common is the nearest miss, and FR-015 forbids returning it."""
        self.assertEqual("no note", self.query("-Text", "ascii pizza atlanta bagels").stdout.strip())

    def test_json_mode_returns_an_empty_list(self):
        self.assertEqual([], self.rows("-Text", "best pizza in Atlanta"))


class AnEventReachesAnotherProcess(_QueryCase):
    def test_a_write_is_found_by_a_second_process_sharing_the_state_root(self):
        write = w.run(self.pwsh, w.WRITE, "-Type", "gotcha", "-Key", "git/show/dotpath-msys",
                      "-Summary", "git show ref:.dotpath returns empty under MSYS", "-Evidence", "2aec304",
                      "-Seat", "builder", "-StateRoot", str(self.state),
                      env={"CLAUDE_CONFIG_DIR": str(self.root / "account-one")})
        self.assertEqual(0, write.returncode, write.stderr)
        other = self.root / "elsewhere"
        other.mkdir()
        rows = self.rows("-Text", "git show dotpath empty msys", cwd=other,
                         env={"CLAUDE_CONFIG_DIR": str(self.root / "account-two")})
        self.assertEqual([write.stdout.strip()], [r["id"] for r in rows])
        self.assertEqual("inbox", rows[0]["label"])

    def test_the_default_state_root_is_shared_across_worktrees(self):
        """No -StateRoot on either side: both resolve `<git-common-dir>/ccx-coord` themselves."""
        primary = self.root / "primary"
        primary.mkdir()

        def git(cwd, *a):
            r = subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True, timeout=w.TIMEOUT_SECONDS)
            self.assertEqual(0, r.returncode, r.stderr)

        git(primary, "init", "-b", "main")
        git(primary, "config", "user.email", "t@example.com")
        git(primary, "config", "user.name", "t")
        (primary / "ccx.config.json").write_text('{"prefix": "ccx"}\n', encoding="ascii")
        git(primary, "add", "ccx.config.json")
        git(primary, "commit", "-m", "first")
        writer = self.root / "writer"
        reader = self.root / "reader"
        git(primary, "worktree", "add", str(writer), "-b", "writer-branch")
        git(primary, "worktree", "add", str(reader), "-b", "reader-branch")
        (writer / ".claude").mkdir()
        (writer / ".claude" / "seat.local.txt").write_text("builder\n", encoding="ascii")

        write = w.run(self.pwsh, w.WRITE, "-Type", "lesson", "-Key", "coord/state-root/shared",
                      "-Summary", "The coordination directory is shared by every worktree of a clone",
                      "-Evidence", "2aec304", cwd=writer)
        self.assertEqual(0, write.returncode, write.stderr)
        self.assertTrue((primary / ".git" / "ccx-coord" / "wiki" / "inbox" / f"{write.stdout.strip()}.json").is_file())

        r = self.query("-Text", "coordination directory shared worktree", state=False, cwd=reader)
        self.assertEqual([write.stdout.strip()], w.ids_in(r.stdout))


class TheRecordRepository(_QueryCase):
    def test_an_unreachable_record_repo_is_one_line_and_exit_zero(self):
        planted = w.plant(self.inbox, key="k/inbox-only", summary="inbox event still searched")
        missing = self.root / "no-such-vault"
        r = self.query("-Text", "inbox event still searched", "-RecordRepo", str(missing))
        lines = [ln for ln in r.stderr.splitlines() if ln.startswith("record repository unreachable")]
        self.assertEqual(1, len(lines), r.stderr)
        self.assertIn("searched the inbox only", lines[0])
        self.assertNotIn("unreachable", r.stdout, "the notice belongs on stderr; stdout is results only")
        self.assertEqual([planted["id"]], w.ids_in(r.stdout), "the inbox was not searched after the miss")

    def test_a_record_repo_on_a_missing_drive_is_one_line_and_exit_zero(self):
        """FR-016. Resolving a path on a drive that does not exist throws, and that throw once
        escaped the query as exit 1 with nothing said. It is an unreachable store like any other."""
        planted = w.plant(self.inbox, key="k/drive-inbox", summary="missing drive inbox search")
        r = self.query("-Text", "missing drive inbox search", "-RecordRepo", w.missing_drive("vault"))
        lines = [ln for ln in r.stderr.splitlines() if ln.startswith("record repository unreachable")]
        self.assertEqual(1, len(lines), r.stderr)
        self.assertIn("searched the inbox only", lines[0])
        self.assertIn("cannot be resolved", lines[0], "the old does-not-exist branch printed this, not the catch")
        self.assertEqual([planted["id"]], w.ids_in(r.stdout), "the inbox was not searched after the miss")

    def test_a_state_root_on_a_missing_drive_is_one_line_and_the_log_is_still_searched(self):
        vault = self.root / "vault"
        logged = w.plant(w.log_dir(vault, w.days_ago(1)), when=w.days_ago(1), key="k/drive-log",
                         summary="missing drive log search")
        r = self.query("-Text", "missing drive log search", "-RecordRepo", str(vault),
                       state=w.missing_drive("coord"))
        lines = [ln for ln in r.stderr.splitlines() if ln.startswith("state root unreachable")]
        self.assertEqual(1, len(lines), r.stderr)
        self.assertIn("the inbox was not searched", lines[0])
        self.assertIn("cannot be resolved", lines[0])
        self.assertEqual([logged["id"]], w.ids_in(r.stdout), "the log was not searched after the miss")

    def test_both_stores_on_a_missing_drive_is_still_exit_zero_and_no_note(self):
        r = self.query("-Text", "missing drive anything", "-RecordRepo", w.missing_drive("vault"),
                       state=w.missing_drive("coord"))
        self.assertEqual("no note", r.stdout.strip())
        self.assertIn("inbox unreachable, log unreachable", r.stderr)

    def test_log_events_are_read_and_labelled_by_age(self):
        vault = self.root / "vault"
        fresh = w.plant(w.log_dir(vault, w.days_ago(2)), when=w.days_ago(2), key="age/fresh", summary="calendar marker fresh")
        aging = w.plant(w.log_dir(vault, w.days_ago(20)), when=w.days_ago(20), key="age/aging", summary="calendar marker aging")
        stale = w.plant(w.log_dir(vault, w.days_ago(60)), when=w.days_ago(60), key="age/stale", summary="calendar marker stale")
        dated = w.plant(w.log_dir(vault, w.days_ago(2)), when=w.days_ago(2), key="age/dated",
                        summary="calendar marker dated", stale_after="2000-01-01")
        rows = {r["id"]: r["label"] for r in self.rows("-Text", "calendar marker", "-RecordRepo", str(vault), "-Limit", "10")}
        self.assertEqual({fresh["id"]: "fresh", aging["id"]: "aging", stale["id"]: "stale", dated["id"]: "stale"}, rows)

    def test_an_event_in_both_inbox_and_log_is_shown_once_as_log(self):
        """Between compile and merge an event sits in both places (spec, Edge Cases)."""
        vault = self.root / "vault"
        when = w.days_ago(1)
        event_id = w.make_id(when)
        w.plant(self.inbox, when=when, event_id=event_id, key="dup/twice", summary="duplicate copy check")
        w.plant(w.log_dir(vault, when), when=when, event_id=event_id, key="dup/twice", summary="duplicate copy check")
        rows = self.rows("-Text", "duplicate copy check", "-RecordRepo", str(vault))
        self.assertEqual([event_id], [r["id"] for r in rows])
        self.assertEqual("log", rows[0]["source"])
        self.assertEqual("fresh", rows[0]["label"])


class TheRestOfTheSurface(_QueryCase):
    def test_path_matches_an_event_about_that_file(self):
        about = w.plant(self.inbox, key="seat/marker", summary="seat marker notes", paths=["scripts/coord/seat.ps1"])
        w.plant(self.inbox, key="other/file", summary="seat marker notes", paths=["scripts/coord/mail.ps1"])
        rows = self.rows("-Path", str(self.root / "checkout" / "scripts" / "coord" / "seat.ps1"))
        self.assertEqual([about["id"]], [r["id"] for r in rows])

    def test_limit_caps_the_results(self):
        for i in range(4):
            w.plant(self.inbox, key=f"many/k{i}", summary="repeated widget subject")
        self.assertEqual(2, len(self.rows("-Text", "repeated widget subject", "-Limit", "2")))

    def test_an_unreadable_file_is_counted_not_hidden(self):
        w.plant(self.inbox, key="ok/one", summary="readable neighbour event")
        (self.inbox / "20260101T000000000Z-broken.json").write_text("{ not json", encoding="ascii")
        r = self.query("-Text", "readable neighbour event")
        self.assertIn("1 file(s) unreadable", r.stderr)
        self.assertEqual(1, len(w.ids_in(r.stdout)))

    def test_every_result_carries_its_key(self):
        """Seats are told to reuse the key they find, so the key is on every result, both forms."""
        e = w.plant(self.inbox, key="gate/ascii/windows-exit-code", summary="keyed result check")
        self.assertIn("gate/ascii/windows-exit-code", self.query("-Text", "keyed result check").stdout)
        self.assertEqual(e["key"], self.rows("-Text", "keyed result check")[0]["key"])

    def test_a_relative_state_root_resolves_against_the_callers_directory(self):
        w.plant(self.inbox, key="rel/root", summary="relative root lookup")
        r = self.query("-Text", "relative root lookup", "-StateRoot", "state", state=False, cwd=self.root)
        self.assertEqual(1, len(w.ids_in(r.stdout)), r.stdout + r.stderr)

    def test_a_planted_bookkeeping_property_is_ignored(self):
        """A file cannot set the reader's own `_`-named fields: `_hay` once matched every query."""
        w.plant(self.inbox, key="evil/hay", summary="ordinary words", _hay={"Key": " zebra ", "All": " zebra "})
        w.plant(self.inbox, key="evil/bad", summary="ordinary words", _hay="x")
        r = self.query("-Text", "zebra")
        self.assertEqual("no note", r.stdout.strip())
        self.assertIn("searched 2 event(s)", r.stderr, "control: both files were read")

    def test_an_event_whose_stamp_disagrees_with_its_id_or_is_future_is_skipped(self):
        when = w.days_ago(1)
        w.plant(self.inbox, when=when, event_id=w.make_id(w.days_ago(2)), key="bad/stamp", summary="stamp check word")
        w.plant(self.inbox, when=w.days_ago(-30), key="bad/future", summary="stamp check word")
        good = w.plant(self.inbox, when=when, key="good/stamp", summary="stamp check word")
        r = self.query("-Text", "stamp check word")
        self.assertEqual([good["id"]], w.ids_in(r.stdout))
        self.assertIn("2 file(s) unreadable", r.stderr)

    def test_a_query_of_only_stopwords_is_a_usage_error_not_a_miss(self):
        r = w.run(self.pwsh, w.QUERY, "-Text", "is the PR ok", "-StateRoot", str(self.state))
        self.assertEqual(2, r.returncode)
        self.assertNotIn("no note", r.stdout)

    def test_a_miss_with_an_unreachable_store_is_still_exactly_no_note(self):
        r = self.query("-Text", "best pizza in Atlanta", "-RecordRepo", str(self.root / "no-such-vault"))
        self.assertEqual("no note", r.stdout.strip())

    def test_a_zoneless_stamp_is_read_as_utc(self):
        """A stamp with no `Z` is UTC, not the reader's local time, so every reader orders it alike."""
        when = w.days_ago(1)
        e = w.plant(self.inbox, when=when, key="zone/less", summary="zoneless stamp check")
        path = self.inbox / f"{e['id']}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["ts"] = data["ts"].rstrip("Z")
        path.write_text(json.dumps(data), encoding="utf-8")
        rows = self.rows("-Text", "zoneless stamp check")
        self.assertEqual([e["id"]], [r["id"] for r in rows], "the zone-less event was skipped or misread")
        self.assertEqual(e["ts"], rows[0]["ts"])

    def test_a_repeated_word_counts_once(self):
        w.plant(self.inbox, key="stem/once", summary="every commit is signed")
        self.assertEqual("no note", self.query("-Text", "commits commit zebra").stdout.strip())
        self.assertEqual(1, len(w.ids_in(self.query("-Text", "commits signed").stdout)), "control")

    def test_a_short_stem_does_not_match_an_unrelated_word(self):
        w.plant(self.inbox, key="stem/floor", summary="strategy timeline review")
        self.assertEqual("no note", self.query("-Text", "string timing").stdout.strip())

    def test_path_filter_applies_to_a_redirected_replacement(self):
        a = w.plant(self.inbox, when=w.days_ago(3), key="p/a", summary="path redirect check", paths=["scripts/x.ps1"])
        w.plant(self.inbox, when=w.days_ago(1), key="p/b", summary="unrelated words", supersedes=[a["id"]],
                paths=["scripts/y.ps1"])
        self.assertEqual("no note", self.query("-Text", "path redirect check", "-Path", "scripts/x.ps1").stdout.strip())
        self.assertEqual(1, len(w.ids_in(self.query("-Text", "path redirect check").stdout)), "control: redirect fires")

    def test_a_control_character_in_a_planted_event_is_skipped(self):
        w.plant(self.inbox, key="ctl/esc", summary="escape \x1b[31m sequence check")
        r = self.query("-Text", "escape sequence check")
        self.assertEqual("no note", r.stdout.strip())
        self.assertIn("1 file(s) unreadable", r.stderr)

    def test_a_bad_limit_is_a_usage_error(self):
        r = w.run(self.pwsh, w.QUERY, "-Text", "anything here", "-Limit", "abc", "-StateRoot", str(self.state))
        self.assertEqual(2, r.returncode)

    def test_no_text_and_no_path_is_a_usage_error(self):
        r = w.run(self.pwsh, w.QUERY, "-StateRoot", str(self.state))
        self.assertEqual(2, r.returncode)


def long_body(*words: str, filler_words: int = 400) -> str:
    """A long synthetic body with each of `words` once, far apart, among neutral filler.

    The shape of an imported note: thousands of characters, the query's words each mentioned in
    passing and nowhere near each other.
    """
    filler = ("harbour ledger ribbon canvas pebble orchard tunnel violet " * (filler_words // 8 + 1)).split()
    parts: list[str] = []
    for word in words:
        parts.extend(filler[:filler_words])
        parts.append(word)
    parts.extend(filler[:filler_words])
    return " ".join(parts)


class TheFloorWeighsTheHeadAboveTheBody(_QueryCase):
    """A short query must not clear the floor on words scattered through a long body alone.

    The head is the key, the summary and the paths. A word found only in the body counts half, so
    an event whose only matches are in its body is never returned. The controls prove the body is
    still searched, and that the same words in a summary are found.
    """

    def setUp(self):
        super().setUp()
        self.scattered = w.plant(self.inbox, key="noise/long-note", summary="unrelated harbour schedule notes",
                                 body=long_body("quartz", "lantern", "meadow"))

    def test_words_scattered_through_a_long_body_do_not_clear_the_floor(self):
        self.assertGreater(len(self.scattered["body"]), 5000, "the body is not long enough to be the case")
        r = self.query("-Text", "quartz lantern meadow")
        self.assertEqual("no note", r.stdout.strip())
        self.assertIn("searched 1 event(s)", r.stderr, "the receipt must show the event was read")

    def test_the_same_words_in_a_summary_do_clear_it(self):
        about = w.plant(self.inbox, key="lamp/field-note", summary="quartz lantern left in the meadow")
        self.assertEqual([about["id"]], [r["id"] for r in self.rows("-Text", "quartz lantern meadow")])

    def test_the_body_still_counts_beside_a_head_match(self):
        """Control: one word in the summary and two in the body is (1 + 0.5 + 0.5) / 3, over 0.6."""
        mixed = w.plant(self.inbox, key="mixed/note", summary="quartz supplier contact",
                        body=long_body("lantern", "meadow"))
        rows = self.rows("-Text", "quartz lantern meadow")
        self.assertEqual([mixed["id"]], [r["id"] for r in rows])
        self.assertAlmostEqual(0.667, rows[0]["score"], places=3)

    def test_a_single_body_word_is_a_miss_and_a_single_summary_word_is_a_hit(self):
        self.assertEqual("no note", self.query("-Text", "lantern").stdout.strip())
        head = w.plant(self.inbox, key="lamp/one", summary="lantern wick trimming")
        self.assertEqual([head["id"]], w.ids_in(self.query("-Text", "lantern").stdout))

    def test_a_path_counts_as_head(self):
        on_path = w.plant(self.inbox, key="file/note", summary="unrelated words here",
                          paths=["scripts/quartz/lantern.ps1"])
        self.assertEqual([on_path["id"]], [r["id"] for r in self.rows("-Text", "quartz lantern")])


class TiesGoToTheEventTheWordsAreAbout(_QueryCase):
    def test_a_short_focused_event_outranks_a_newer_long_one_that_matches_the_same_words(self):
        """Both carry every query word in the summary, so they tie on rank. Newest-first alone would
        put the long one first; the BM25 weight puts the one the words are about first."""
        focused = w.plant(self.inbox, when=w.days_ago(5), key="rank/first",
                          summary="sprocket calibration drift", body="sprocket calibration drift, measured twice")
        passing = w.plant(self.inbox, when=w.days_ago(1), key="rank/second",
                          summary="sprocket calibration drift", body=long_body("orchard", filler_words=1000))
        self.assertLess(len(passing["body"]), 20000, "over the body limit the event is skipped, not ranked")
        rows = self.rows("-Text", "sprocket calibration drift")
        self.assertEqual([focused["id"], passing["id"]], [r["id"] for r in rows])
        self.assertEqual(rows[0]["score"], rows[1]["score"], "the two must tie on score for this case to test the weight")

    def test_with_equal_text_the_newer_event_still_wins(self):
        """Control: the weight breaks ties only where the texts differ; identical text stays newest first."""
        older = w.plant(self.inbox, when=w.days_ago(5), key="tie/a", summary="gearbox torque limit")
        newer = w.plant(self.inbox, when=w.days_ago(1), key="tie/b", summary="gearbox torque limit")
        self.assertEqual([newer["id"], older["id"]], [r["id"] for r in self.rows("-Text", "gearbox torque limit")])


class ImportMergeRecordsAreHiddenByDefault(_QueryCase):
    def setUp(self):
        super().setUp()
        self.note = w.plant(self.inbox, key="memory/widget-rollout", summary="Widget rollout needs a feature flag")
        self.merge = w.plant(self.inbox, type="decision", key="memory-merge/widget-rollout/store-two",
                             summary="Merged memory note widget-rollout from store two: same name, same text",
                             evidence="memory:store-one/widget-rollout.md",
                             body="kept: memory:store-one/widget-rollout.md\nmerged: memory:store-two/widget-rollout.md")

    def test_a_default_query_does_not_return_a_merge_record(self):
        rows = self.rows("-Text", "widget rollout")
        self.assertEqual([self.note["id"]], [r["id"] for r in rows])

    def test_history_returns_it(self):
        ids = {r["id"] for r in self.rows("-Text", "widget rollout", "-History")}
        self.assertEqual({self.note["id"], self.merge["id"]}, ids)

    def test_a_query_only_the_merge_record_matches_is_no_note(self):
        """Control on the words: `merged store` matches the merge record alone, so the default miss is
        the hiding and not the scoring."""
        self.assertEqual("no note", self.query("-Text", "merged store two").stdout.strip())
        self.assertEqual([self.merge["id"]], [r["id"] for r in self.rows("-Text", "merged store two", "-History")])


class EveryQueryIsLogged(_QueryCase):
    HEADER = ["utc", "seat", "text", "path", "results", "top_score", "no_note"]

    def log_lines(self) -> list[list[str]]:
        files = sorted((self.state / "wiki" / "query-log").glob("*.tsv"))
        self.assertEqual(1, len(files), f"expected one month file, found {files}")
        month = files[0].stem
        self.assertRegex(month, r"^\d{4}-\d{2}$")
        lines = files[0].read_text(encoding="utf-8").split("\n")
        self.assertEqual("", lines[-1], "every line, the last included, ends in a newline")
        rows = [ln.split("\t") for ln in lines[:-1]]
        self.assertEqual(self.HEADER, rows[0])
        for row in rows[1:]:
            self.assertEqual(7, len(row), row)
            self.assertTrue(row[0].startswith(month), "the file is named for the UTC month of its lines")
        return rows[1:]

    def test_a_hit_and_a_miss_are_each_one_line_with_every_field(self):
        e = w.plant(self.inbox, key="log/probe", summary="copper kettle whistle", paths=["scripts/kettle.ps1"])
        hit = self.query("-Text", "copper\tkettle\nwhistle", "-Path", "scripts/kettle.ps1", "-Seat", "builder")
        self.assertEqual([e["id"]], w.ids_in(hit.stdout))
        self.query("-Text", "best pizza in Atlanta")
        rows = self.log_lines()
        self.assertEqual(2, len(rows))
        first, second = rows
        self.assertRegex(first[0], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        self.assertEqual(["builder", "copper kettle whistle", "scripts/kettle.ps1", "1", "1", "no"], first[1:])
        self.assertEqual(["", "best pizza in Atlanta", "", "0", "", "yes"], second[1:])

    def test_json_mode_is_logged_too(self):
        w.plant(self.inbox, key="log/json", summary="brass hinge oil")
        self.rows("-Text", "brass hinge oil", "-Seat", "lander")
        (row,) = self.log_lines()
        self.assertEqual(["lander", "brass hinge oil", "", "1", "1", "no"], row[1:])

    def test_an_unwritable_log_leaves_stdout_and_exit_code_unchanged(self):
        e = w.plant(self.inbox, key="log/blocked", summary="tin whistle tuning")
        blocker = self.state / "wiki" / "query-log"
        blocker.write_text("a file where the log directory should be", encoding="ascii")
        blocked = self.query("-Text", "tin whistle tuning")
        blocked_json = self.query("-Text", "tin whistle tuning", "-Json")
        notes = [ln for ln in blocked.stderr.splitlines() if ln.startswith("wiki query: query log not written")]
        self.assertEqual(1, len(notes), blocked.stderr)
        blocker.unlink()
        control = self.query("-Text", "tin whistle tuning")
        control_json = self.query("-Text", "tin whistle tuning", "-Json")
        self.assertEqual([e["id"]], w.ids_in(control.stdout), "control: the query finds the event")
        self.assertEqual(control.stdout, blocked.stdout)
        self.assertEqual(json.loads(control_json.stdout), json.loads(blocked_json.stdout))
        self.assertNotIn("query log not written", control.stderr)
        self.assertEqual(2, len(self.log_lines()), "control: the unblocked runs did log")

    def test_a_state_root_that_does_not_exist_logs_nothing(self):
        missing = self.root / "no-such-state"
        r = self.query("-Text", "anything at all", state=missing)
        self.assertEqual("no note", r.stdout.strip())
        self.assertFalse(missing.exists(), "the log must not create a state root that was not there")


class AQueryIsQuick(_QueryCase):
    """SC-004: a query over the corpus returns in under two seconds on the reference machine.

    One thousand planted events, about the size of the import. The asserted ceiling is looser than
    the target for the reason `test_wiki_write.AWriteIsQuick` gives: it includes a cold `pwsh`.
    """

    CEILING_SECONDS = 8.0

    def test_a_thousand_events_under_the_ceiling(self):
        words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]
        for i in range(1000):
            w.plant(self.inbox, key=f"perf/{words[i % 10]}/{i}",
                    summary=f"{words[i % 10]} {words[(i * 3) % 10]} measurement event {i}")
        target = w.plant(self.inbox, key="perf/needle", summary="unique zebra quokka needle")
        times = []
        for _ in range(2):
            start = time.perf_counter()
            r = self.query("-Text", "zebra quokka needle")
            times.append(time.perf_counter() - start)
        self.assertEqual([target["id"]], w.ids_in(r.stdout))
        self.assertIn("searched 1001 event(s)", r.stderr)
        self.assertLess(min(times), self.CEILING_SECONDS, f"query wall-clock seconds: {times}")


if __name__ == "__main__":
    unittest.main()
