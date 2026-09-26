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



class AgeCountsFromNoted(_QueryCase):
    """FR-014, amended 2026-09-26: an event's age is counted from `noted` when it has one."""

    def test_the_label_follows_noted_at_each_boundary_and_falls_back_to_ts(self):
        vault = self.root / "vault"
        when = w.days_ago(1)

        def noted(days: int) -> str:
            return w.days_ago(days).strftime("%Y-%m-%d")

        planted = {
            "fresh": w.plant(w.log_dir(vault, when), when=when, key="n/13", summary="boundary marker thirteen", noted=noted(13)),
            "aging": w.plant(w.log_dir(vault, when), when=when, key="n/14", summary="boundary marker fourteen", noted=noted(14)),
            "aging45": w.plant(w.log_dir(vault, when), when=when, key="n/45", summary="boundary marker fortyfive", noted=noted(45)),
            "stale": w.plant(w.log_dir(vault, when), when=when, key="n/46", summary="boundary marker fortysix", noted=noted(46)),
            "ts": w.plant(w.log_dir(vault, when), when=when, key="n/ts", summary="boundary marker without"),
        }
        rows = {r["id"]: r for r in self.rows("-Text", "boundary marker", "-RecordRepo", str(vault), "-Limit", "10")}
        got = {name: rows[e["id"]]["label"] for name, e in planted.items()}
        self.assertEqual({"fresh": "fresh", "aging": "aging", "aging45": "aging", "stale": "stale", "ts": "fresh"}, got)
        self.assertEqual((noted(46), noted(46)), (rows[planted["stale"]["id"]]["date"], rows[planted["stale"]["id"]]["noted"]))
        self.assertIsNone(rows[planted["ts"]["id"]]["noted"])

    def test_the_result_line_marks_a_noted_date(self):
        vault = self.root / "vault"
        when = w.days_ago(1)
        day = w.days_ago(60).strftime("%Y-%m-%d")
        e = w.plant(w.log_dir(vault, when), when=when, key="n/line", summary="printed noted marker", noted=day)
        r = self.query("-Text", "printed noted marker", "-RecordRepo", str(vault))
        self.assertIn(f"{e['id']}  {day} (noted)  builder  [stale]", r.stdout)

    def test_a_noted_after_its_own_ts_is_not_read(self):
        """A reader holds a planted event to the write's own rule, so it cannot read younger than it is."""
        vault = self.root / "vault"
        when = w.days_ago(30)
        bad = w.plant(w.log_dir(vault, when), when=when, key="n/bad", summary="future noted marker",
                      noted=w.days_ago(1).strftime("%Y-%m-%d"))
        good = w.plant(w.log_dir(vault, when), when=when, key="n/good", summary="future noted marker ok",
                       noted=w.days_ago(40).strftime("%Y-%m-%d"))
        ids = [r["id"] for r in self.rows("-Text", "future noted marker", "-RecordRepo", str(vault))]
        self.assertNotIn(bad["id"], ids)
        self.assertIn(good["id"], ids, "the control, the same shape with a valid noted, was not read either")

if __name__ == "__main__":
    unittest.main()
