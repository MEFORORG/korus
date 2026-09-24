"""The guard (`scripts/wiki/_guard.ps1`) is what keeps a retired fact retired. Pin that it does.

THE FAILURE IT EXISTS FOR is measured elsewhere, not here: five memory systems in arXiv 2609.08258
returned a revoked fact by default, often above its replacement. So every case below asks the
question a seat would ask -- through `query.ps1`, the real read path -- and checks what comes back.

THE HIDING IS PROVEN TO BE THE GUARD'S. A test that finds A absent cannot tell "the guard hid A"
from "the search never matched A", and those read identically. So the supersede case runs the same
search over the same files with the guard left out, through the library the query uses, and A must
come back there. Without that control the absence would measure nothing (spec SC-001).

Run: python -m pytest tests/test_wiki_guard.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _wikitest as w


class _GuardCase(unittest.TestCase):
    def setUp(self):
        self.pwsh = w.find_pwsh_or_skip(self)
        tmp = tempfile.TemporaryDirectory(prefix="wiki-guard-")
        self.addCleanup(tmp.cleanup)
        self.state = Path(tmp.name) / "state"
        self.state.mkdir()
        self.inbox = w.inbox_dir(self.state)

    def query(self, text: str, *extra: str):
        r = w.run(self.pwsh, w.QUERY, "-Text", text, "-StateRoot", str(self.state), *extra)
        self.assertEqual(0, r.returncode, r.stderr)
        return r

    def query_json(self, text: str, *extra: str) -> list[dict]:
        return json.loads(self.query(text, "-Json", *extra).stdout)

    def unguarded_ids(self, text: str) -> list[str]:
        """The CONTROL: the same files and the same scorer the query uses, with no guard between."""
        r = w.run_ps(
            self.pwsh,
            f"$r = Read-WikiEventDir -Dir '{self.inbox}' -Source inbox; "
            f"foreach ($h in (Find-WikiMatch -Events $r.Events -Text '{text}')) {{ $h.Event.id }}",
        )
        self.assertEqual(0, r.returncode, r.stderr)
        return r.stdout.split()


class ASupersededEventStaysHidden(_GuardCase):
    def setUp(self):
        super().setUp()
        self.a = w.plant(self.inbox, when=w.days_ago(3), key="ruling/merge-owner",
                         summary="The Owner merges every pull request by hand")
        # A DIFFERENT KEY, so nothing but the `supersedes` list can hide A. On the same key the
        # newest-wins rule would hide it too, and this case could not tell the two rules apart.
        self.b = w.plant(self.inbox, when=w.days_ago(1), type="decision", key="ruling/landing",
                         summary="The Lander lands pull requests after review",
                         supersedes=[self.a["id"]])
        self.a_text = "Owner merges every pull request by hand"

    def test_a_query_for_a_old_text_returns_b_and_not_a(self):
        rows = self.query_json(self.a_text)
        ids = [r["id"] for r in rows]
        self.assertNotIn(self.a["id"], ids, "the superseded event came back from a default query")
        self.assertEqual([self.b["id"]], ids, "the replacement did not come back for the old wording")
        self.assertEqual(self.a["id"], rows[0]["found_via"])

    def test_b_is_reached_only_through_a(self):
        """B's own text matches too few of A's words to be a hit, so B above came through A."""
        self.assertNotIn(self.b["id"], self.unguarded_ids(self.a_text))

    def test_the_hiding_is_the_guards(self):
        """CONTROL. With the guard left out, the same search over the same files returns A."""
        self.assertIn(self.a["id"], self.unguarded_ids(self.a_text))

    def test_history_returns_a_labelled_historical_with_a_pointer_to_b(self):
        rows = {r["id"]: r for r in self.query_json(self.a_text, "-History")}
        self.assertIn(self.a["id"], rows)
        self.assertEqual("historical", rows[self.a["id"]]["label"])
        self.assertEqual(self.b["id"], rows[self.a["id"]]["replaced_by"])

    def test_the_text_output_carries_the_pointer_too(self):
        out = self.query(self.a_text, "-History").stdout
        self.assertIn("[historical]", out)
        self.assertIn(f"replaced by: {self.b['id']}", out)


class TheNewestEventOnAKeyWins(_GuardCase):
    def test_two_live_events_on_one_key_return_the_newer(self):
        old = w.plant(self.inbox, when=w.days_ago(5), key="gate/ascii/exit", summary="ascii gate exits one on windows")
        new = w.plant(self.inbox, when=w.days_ago(2), key="gate/ascii/exit", summary="ascii gate exits two on windows")
        ids = [r["id"] for r in self.query_json("ascii gate windows")]
        self.assertIn(new["id"], ids)
        self.assertNotIn(old["id"], ids)
        # Control: both match the text, so the absence of the older one is the ordering rule.
        self.assertEqual({old["id"], new["id"]}, set(self.unguarded_ids("ascii gate windows")))

    def test_superseding_the_newest_does_not_revive_the_older(self):
        """A1 was hidden only because A2 was newer. Superseding A2 must not hand the key back to A1."""
        a1 = w.plant(self.inbox, when=w.days_ago(5), key="ruling/merge", summary="merge rule version one")
        a2 = w.plant(self.inbox, when=w.days_ago(3), key="ruling/merge", summary="merge rule version two")
        w.plant(self.inbox, when=w.days_ago(1), type="supersede", key="ruling/merge",
                summary="withdrawn outright", supersedes=[a2["id"]])
        self.assertEqual("no note", self.query("merge rule version").stdout.strip())
        self.assertEqual({a1["id"], a2["id"]}, set(self.unguarded_ids("merge rule version")), "control")
        rows = {r["id"]: r for r in self.query_json("merge rule version", "-History")}
        self.assertEqual(("historical", a2["id"]), (rows[a1["id"]]["label"], rows[a1["id"]]["replaced_by"]))

    def test_a_correction_is_not_hidden_by_its_later_stamped_target(self):
        """Clock skew: the target carries a LATER stamp than the correction that supersedes it."""
        a = w.plant(self.inbox, when=w.days_ago(1), key="ruling/x", summary="skewed original claim")
        c = w.plant(self.inbox, when=w.days_ago(2), type="correction", key="ruling/x",
                    summary="skewed corrected claim", supersedes=[a["id"]])
        self.assertEqual([c["id"]], [r["id"] for r in self.query_json("skewed corrected claim")])
        self.assertEqual([c["id"]], [r["id"] for r in self.query_json("skewed original claim")])

    def test_a_skewed_correction_never_leaves_its_key_empty(self):
        """A at ts 1 supersedes C, B at ts 2, C at ts 3, all on one key. Rule 1 hides C, C hides B
        and B hides A, so rule 3 alone once left the key with nothing live at all. The newest event
        rule 3 alone hid, B, stays live."""
        c = w.plant(self.inbox, when=w.days_ago(1), key="ruling/skew", summary="skew floor original")
        b = w.plant(self.inbox, when=w.days_ago(2), key="ruling/skew", summary="skew floor between")
        a = w.plant(self.inbox, when=w.days_ago(3), type="correction", key="ruling/skew",
                    summary="skew floor corrected", supersedes=[c["id"]])
        self.assertEqual({a["id"], b["id"], c["id"]}, set(self.unguarded_ids("skew floor")), "control")
        self.assertEqual([b["id"]], [r["id"] for r in self.query_json("skew floor")])
        rows = {r["id"]: r for r in self.query_json("skew floor", "-History")}
        self.assertEqual(("historical", a["id"]), (rows[c["id"]]["label"], rows[c["id"]]["replaced_by"]))
        self.assertEqual(("historical", b["id"]), (rows[a["id"]]["label"], rows[a["id"]]["replaced_by"]))

    def test_the_floor_reaches_a_correction_of_a_correction(self):
        """A at ts 1 corrects C, B at ts 2 corrects A, C at ts 3. B is the lost correction."""
        c = w.plant(self.inbox, when=w.days_ago(1), key="ruling/chain", summary="chain floor original")
        a = w.plant(self.inbox, when=w.days_ago(3), type="correction", key="ruling/chain",
                    summary="chain floor first", supersedes=[c["id"]])
        b = w.plant(self.inbox, when=w.days_ago(2), type="correction", key="ruling/chain",
                    summary="chain floor second", supersedes=[a["id"]])
        self.assertEqual(3, len(self.unguarded_ids("chain floor")), "control")
        self.assertEqual([b["id"]], [r["id"] for r in self.query_json("chain floor")])

    def test_the_floor_never_reaches_back_past_a_withdrawal(self):
        """A at ts 1 corrects D; B at ts 2; C at ts 3; D at ts 4; a marker withdraws C. C had
        outranked A and B, so bringing either back would undo the marker. The key stays empty,
        where without the marker C would be live."""
        d = w.plant(self.inbox, when=w.days_ago(1), key="ruling/bar", summary="bar floor fourth")
        c = w.plant(self.inbox, when=w.days_ago(2), key="ruling/bar", summary="bar floor third")
        w.plant(self.inbox, when=w.days_ago(3), key="ruling/bar", summary="bar floor second")
        w.plant(self.inbox, when=w.days_ago(4), type="correction", key="ruling/bar",
                summary="bar floor first", supersedes=[d["id"]])
        self.assertEqual([c["id"]], [r["id"] for r in self.query_json("bar floor")], "control: no marker yet")
        w.plant(self.inbox, when=w.days_ago(0.5), type="supersede", key="ruling/bar",
                summary="withdrawn outright", supersedes=[c["id"]])
        self.assertEqual("no note", self.query("bar floor").stdout.strip())

    def test_the_floor_does_not_revive_a_key_a_marker_emptied(self):
        """The same three events, but a MARKER withdraws the correction. Nothing is lost to rule 3
        alone there, so the key stays empty, as superseding its newest event leaves it."""
        c = w.plant(self.inbox, when=w.days_ago(1), key="ruling/skew2", summary="skew marker original")
        a = w.plant(self.inbox, when=w.days_ago(3), type="correction", key="ruling/skew2",
                    summary="skew marker corrected", supersedes=[c["id"]])
        w.plant(self.inbox, when=w.days_ago(2), key="ruling/skew2", summary="skew marker between")
        w.plant(self.inbox, when=w.days_ago(0.5), type="supersede", key="ruling/skew2",
                summary="withdrawn outright", supersedes=[a["id"]])
        self.assertEqual("no note", self.query("skew marker").stdout.strip())
        self.assertEqual(3, len(self.unguarded_ids("skew marker")), "control: all three match unguarded")

    def test_a_later_marker_does_not_strand_a_live_correction(self):
        a = w.plant(self.inbox, when=w.days_ago(3), key="r/a", summary="stranded original wording")
        c = w.plant(self.inbox, when=w.days_ago(2), type="correction", key="r/c",
                    summary="different replacement text", supersedes=[a["id"]])
        w.plant(self.inbox, when=w.days_ago(1), type="supersede", key="r/a", summary="cleanup marker",
                supersedes=[a["id"]])
        self.assertEqual([c["id"]], [r["id"] for r in self.query_json("stranded original wording")])

    def test_the_answer_does_not_depend_on_the_order_the_events_arrive_in(self):
        """Windows lists files in name order, which is stamp order, so a guard that never sorted
        passed every case there and failed at random on Linux. Hand it both orders explicitly.

        One inbox exercises all three order-dependent rules: the newest content on a key wins
        (rule 3), the NEWEST of two superseders is the pointer (rule 1), and a retire hides what
        sorts before it (rule 2). Each printed line is `id status replaced_by`."""
        old = w.plant(self.inbox, when=w.days_ago(5), key="k/order", summary="arrival order one")
        mid = w.plant(self.inbox, when=w.days_ago(3), key="k/order", summary="arrival order two")
        new = w.plant(self.inbox, when=w.days_ago(1), key="k/order", summary="arrival order three")
        a = w.plant(self.inbox, when=w.days_ago(5), key="k/sup", summary="superseded twice")
        w.plant(self.inbox, when=w.days_ago(4), type="supersede", key="k/sup", summary="first marker",
                supersedes=[a["id"]])
        s2 = w.plant(self.inbox, when=w.days_ago(3), type="supersede", key="k/sup", summary="second marker",
                     supersedes=[a["id"]])
        # Two retires with content between them. A single retire comes out right in any order even
        # on the old guard, so only this shape tests that the NEWEST retire is the one applied.
        w.plant(self.inbox, when=w.days_ago(5), type="retire", key="k/ret", summary="earlier withdrawal")
        cc = w.plant(self.inbox, when=w.days_ago(4), key="k/ret", summary="retired content")
        ret = w.plant(self.inbox, when=w.days_ago(2), type="retire", key="k/ret", summary="withdrawn")
        show = "ForEach-Object { '{0} {1} {2}' -f $_.id, $_._status, $_._replacedBy }"
        r = w.run_ps(
            self.pwsh,
            f"$r = Read-WikiEventDir -Dir '{self.inbox}' -Source inbox; "
            "$asc = @($r.Events | Sort-Object { $_._tsKey }); "
            "$desc = @($r.Events | Sort-Object { $_._tsKey } -Descending); "
            f"(Select-WikiLiveEvent -Events $asc -History) | {show}; '---'; "
            f"(Select-WikiLiveEvent -Events $desc -History) | {show}",
        )
        self.assertEqual(0, r.returncode, r.stderr)
        for label, block in zip(("oldest-first input", "newest-first input"), r.stdout.split("---")):
            rows = {parts[0]: parts[1:] for parts in (ln.split() for ln in block.strip().splitlines())}
            self.assertEqual(9, len(rows), f"{label}: every planted event is in the history")
            self.assertEqual(["live"], rows[new["id"]], f"{label}: rule 3 newest on the key")
            self.assertEqual(["historical", new["id"]], rows[old["id"]], f"{label}: rule 3 oldest")
            self.assertEqual(["historical", new["id"]], rows[mid["id"]], f"{label}: rule 3 middle")
            self.assertEqual(["historical", s2["id"]], rows[a["id"]], f"{label}: rule 1 pointer")
            self.assertEqual(["historical", ret["id"]], rows[cc["id"]], f"{label}: rule 2 retire")

    def test_the_same_stamp_is_broken_by_id(self):
        when = w.days_ago(1)
        low = w.plant(self.inbox, when=when, event_id=w.stamp_id(when, "aaaaaa"), key="k/tie", summary="tie breaker case")
        high = w.plant(self.inbox, when=when, event_id=w.stamp_id(when, "zzzzzz"), key="k/tie", summary="tie breaker case")
        ids = [r["id"] for r in self.query_json("tie breaker case")]
        self.assertEqual([high["id"]], ids)
        self.assertNotEqual(low["id"], high["id"])


class ARetireWithdrawsAKey(_GuardCase):
    def setUp(self):
        super().setUp()
        self.a = w.plant(self.inbox, when=w.days_ago(4), key="tool/okf/search", summary="okf search ignores status fields")
        self.r = w.plant(self.inbox, when=w.days_ago(2), type="retire", key="tool/okf/search",
                         summary="okf search ignores status fields no longer applies")

    def test_the_key_is_withdrawn(self):
        self.assertEqual("no note", self.query("okf search status fields").stdout.strip())
        self.assertIn(self.a["id"], self.unguarded_ids("okf search status fields"), "control: A matches unguarded")

    def test_history_points_at_the_retire(self):
        rows = {r["id"]: r for r in self.query_json("okf search status fields", "-History")}
        self.assertEqual("historical", rows[self.a["id"]]["label"])
        self.assertEqual(self.r["id"], rows[self.a["id"]]["replaced_by"])

    def test_a_later_event_on_the_key_is_live_again(self):
        c = w.plant(self.inbox, when=w.days_ago(1), key="tool/okf/search", summary="okf search filters status fields now")
        ids = [r["id"] for r in self.query_json("okf search status fields")]
        self.assertEqual([c["id"]], ids)


class AMarkerIsNeverDroppedSilently(_GuardCase):
    """FR-011. A reader once skipped any event failing the schema, markers included, so a skipped
    `retire` or `supersede` never reached the guard and what it hid came back live. One torn file
    did it, and so would a later tightening of a pattern such as evidence."""

    WARNING = "warning: 1 event file(s) unreadable; a retirement may be missing"

    def setUp(self):
        super().setUp()
        self.target = w.plant(self.inbox, when=w.days_ago(3), key="tool/drop/marker",
                              summary="dropped marker target claim")

    def test_a_retire_failing_only_the_evidence_pattern_still_withdraws_its_key(self):
        w.plant(self.inbox, when=w.days_ago(1), type="retire", key="tool/drop/marker",
                summary="withdrawn", evidence="trust me")
        r = self.query("dropped marker target claim")
        self.assertEqual("no note", r.stdout.strip(), "the retire was dropped and its target came back")
        self.assertIn("1 marker(s) honoured on the loose check", r.stderr)
        self.assertIn(self.target["id"], self.unguarded_ids("dropped marker target claim"), "control")

    def test_a_supersede_failing_only_the_evidence_pattern_still_hides_its_target(self):
        w.plant(self.inbox, when=w.days_ago(1), type="supersede", key="tool/drop/other",
                summary="withdrawn", evidence="trust me", supersedes=[self.target["id"]])
        self.assertEqual("no note", self.query("dropped marker target claim").stdout.strip())

    def test_a_torn_marker_file_warns_on_stdout_and_in_json(self):
        when = w.days_ago(1)
        marker = {"id": w.make_id(when), "ts": w.stamp(when), "type": "retire", "key": "tool/drop/marker",
                  "seat": "builder", "summary": "withdrawn", "evidence": "2aec304", "trust": "generated"}
        text = json.dumps(marker)
        (self.inbox / f"{marker['id']}.json").write_text(text[: len(text) // 2], encoding="utf-8")
        r = self.query("dropped marker target claim")
        out = r.stdout.splitlines()
        self.assertEqual(self.WARNING, out[0], "a torn marker read as a clean result")
        self.assertIn(self.target["id"], r.stdout, "control: the target shows, which is why the warning must")
        doc = json.loads(self.query("dropped marker target claim", "-Json").stdout)
        self.assertEqual((self.WARNING, 1), (doc["warning"], doc["unreadable"]))
        self.assertEqual([self.target["id"]], [row["id"] for row in doc["results"]])

    def test_each_loose_check_refusal_warns(self):
        """Every refusal in the loose check, one at a time. Each marker below would withdraw the
        target if it were honoured, or has nothing to withdraw, so a missing warning means the
        check let it through."""
        future = datetime.now(timezone.utc) + timedelta(days=30)
        cases = {
            "supersedes names no id": dict(type="supersede", supersedes=["not-an-id"]),
            "id dated ahead of the clock": dict(when=future),
            "key not a key": dict(key="Tool/Drop/Marker"),
            "control character": dict(summary="with" + chr(27) + "[31m escape"),
            "stale_after not a date": dict(stale_after="tomorrow"),
            "id is not the file name": dict(rename=True),
            "supersede names nothing": dict(type="supersede", supersedes=[]),
            "supersedes holds a non-string": dict(type="supersede", supersedes=[12345]),
            "key too long": dict(key="tool/" + "k" * 200),
            "id not in id form": dict(event_id="not-an-id"),
        }
        for n, (name, over) in enumerate(cases.items()):
            with self.subTest(case=name):
                state = self.state.parent / f"case-{n}"
                inbox = w.inbox_dir(state)
                target = w.plant(inbox, when=w.days_ago(3), key="tool/drop/marker", summary="dropped marker target claim")
                over = dict(over)
                rename = over.pop("rename", False)
                fields = dict(when=over.pop("when", w.days_ago(1)), type="retire", key="tool/drop/marker",
                              summary="withdrawn")
                fields.update(over)
                m = w.plant(inbox, **fields)
                if rename:
                    (inbox / f"{m['id']}.json").rename(inbox / f"{w.make_id(w.days_ago(1))}.json")
                r = w.run(self.pwsh, w.QUERY, "-Text", "dropped marker target claim", "-StateRoot", str(state))
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertEqual(self.WARNING, r.stdout.splitlines()[0], r.stdout + r.stderr)
                self.assertIn(target["id"], r.stdout)

    def test_a_loosely_honoured_marker_is_marked_in_history(self):
        m = w.plant(self.inbox, when=w.days_ago(1), type="retire", key="tool/drop/marker",
                    summary="dropped marker target claim withdrawn", evidence="trust me")
        rows = {r["id"]: r for r in self.query_json("dropped marker target claim", "-History")}
        self.assertTrue(rows[m["id"]]["loose"], "a loosely honoured marker read like a valid one")
        self.assertFalse(rows[self.target["id"]]["loose"], "control: a valid event is not marked")

    def test_a_marker_with_a_bad_ts_is_ordered_by_the_stamp_in_its_id(self):
        """A retire withdraws what sorts BEFORE it. With its `ts` unreadable, the id's stamp decides."""
        m = w.plant(self.inbox, when=w.days_ago(1), type="retire", key="tool/drop/marker", summary="withdrawn")
        path = self.inbox / f"{m['id']}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["ts"] = "not a time"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual("no note", self.query("dropped marker target claim").stdout.strip())
        # Control: the same broken marker stamped BEFORE the target withdraws nothing.
        path.unlink()
        early = w.plant(self.inbox, when=w.days_ago(5), type="retire", key="tool/drop/marker", summary="withdrawn")
        early_path = self.inbox / f"{early['id']}.json"
        data = json.loads(early_path.read_text(encoding="utf-8"))
        data["ts"] = "not a time"
        early_path.write_text(json.dumps(data), encoding="utf-8")
        r = self.query("dropped marker target claim")
        self.assertEqual([self.target["id"]], w.ids_in(r.stdout))
        self.assertIn("1 marker(s) honoured on the loose check", r.stderr)

    def test_a_bad_correction_that_names_supersedes_warns(self):
        """Content is never honoured loosely, because it would be shown. But its target comes back,
        so the reader must say so."""
        w.plant(self.inbox, when=w.days_ago(1), type="correction", key="tool/drop/other", summary="unrelated",
                evidence="trust me", supersedes=[self.target["id"]])
        r = self.query("dropped marker target claim")
        self.assertEqual(self.WARNING, r.stdout.splitlines()[0])
        self.assertIn(self.target["id"], r.stdout)

    def test_a_bad_content_event_does_not_warn(self):
        """Only a file that could have been a marker warns. A malformed lesson is counted, not shouted."""
        w.plant(self.inbox, when=w.days_ago(1), key="tool/drop/other", summary="unrelated", evidence="trust me")
        r = self.query("dropped marker target claim")
        self.assertNotIn("warning:", r.stdout)
        self.assertIn("1 file(s) unreadable", r.stderr)
        self.assertIsInstance(json.loads(self.query("dropped marker target claim", "-Json").stdout), list)


class AMarkerIsNeverAResult(_GuardCase):
    def test_a_supersede_marker_hides_its_target_and_is_not_returned(self):
        a = w.plant(self.inbox, when=w.days_ago(3), key="lesson/pwsh/nested", summary="pwsh tool refuses nested pwsh")
        m = w.plant(self.inbox, when=w.days_ago(1), type="supersede", key="lesson/pwsh/nested",
                    summary="pwsh tool refuses nested pwsh was wrong", supersedes=[a["id"]])
        self.assertEqual("no note", self.query("pwsh tool refuses nested pwsh").stdout.strip())
        control = set(self.unguarded_ids("pwsh tool refuses nested pwsh"))
        self.assertEqual({a["id"], m["id"]}, control, "control: both match when unguarded")

    def test_the_guard_library_alone_returns_no_marker(self):
        """Straight at `Select-WikiLiveEvent`, without the query's scoring in the way."""
        w.plant(self.inbox, when=w.days_ago(2), key="k/one", summary="content")
        w.plant(self.inbox, when=w.days_ago(1), type="retire", key="k/two", summary="withdrawn")
        r = w.run_ps(
            self.pwsh,
            f"$r = Read-WikiEventDir -Dir '{self.inbox}' -Source inbox; "
            "(Select-WikiLiveEvent -Events $r.Events) | ForEach-Object { $_.type }; '---'; "
            "(Select-WikiLiveEvent -Events $r.Events -History) | ForEach-Object { $_.type }",
        )
        self.assertEqual(0, r.returncode, r.stderr)
        live, history = r.stdout.split("---")
        self.assertEqual(["lesson"], live.split())
        self.assertEqual(sorted(["lesson", "retire"]), sorted(history.split()))


if __name__ == "__main__":
    unittest.main()
