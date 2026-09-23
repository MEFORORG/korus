"""`scripts/wiki/write.ps1 -FromJson` is the same write path, taken once per event. Pin the parity.

WHY A BATCH MODE EXISTS AT ALL. The one-time import turns about 960 notes into events, and a
process per event cost about 0.6 seconds each. Batch mode starts one process and runs the scanner
once per chunk of events. Everything else must be the single write, step for step.

SO EVERY CASE HERE COMPARES THE BATCH WITH A SINGLE WRITE of the same input. A batch test alone
could not tell "the batch applies the rules" from "the batch applies rules of its own that happen
to agree on this input".

Run: python -m pytest tests/test_wiki_write_batch.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _wikitest as w


def forge_token() -> str:
    """A credential-shaped value, built at run time so this file carries no literal the leak gate
    over the tracked tree would fire on."""
    return "gh" + "p_" + "B" * 36


GOOD = {
    "type": "lesson",
    "key": "gate/ascii/windows-exit-code",
    "summary": "The ascii gate collapses exit code 2 to 1 under -Command",
    "evidence": "9379109",
    "body": "line one\nline two",
    "paths": ["scripts/quality/check-ascii.ps1"],
}


def single_args(event: dict) -> list[str]:
    names = {"type": "-Type", "key": "-Key", "summary": "-Summary", "evidence": "-Evidence", "body": "-Body",
             "stale_after": "-StaleAfter", "trust": "-Trust"}
    out: list[str] = []
    for k, v in event.items():
        if k in ("paths", "supersedes"):
            out += ["-Paths" if k == "paths" else "-Supersedes", ",".join(v)]
        else:
            out += [names[k], v]
    return out


class _BatchCase(unittest.TestCase):
    def setUp(self):
        self.pwsh = w.find_pwsh_or_skip(self)
        tmp = tempfile.TemporaryDirectory(prefix="wiki-batch-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / "state"
        self.state.mkdir()
        self.n = 0

    def batch(self, events: list, *extra: str, state: Path | None = None):
        self.n += 1
        f = self.root / f"batch-{self.n}.json"
        f.write_text(json.dumps(events), encoding="utf-8")
        r = w.run(self.pwsh, w.WRITE, "-FromJson", str(f), "-Seat", "builder",
                  "-StateRoot", str(state or self.state), *extra)
        results = json.loads(r.stdout) if r.stdout.strip().startswith("[") else None
        return r, results

    def single(self, event: dict, state: Path | None = None):
        return w.run(self.pwsh, w.WRITE, *single_args(event), "-Seat", "builder",
                     "-StateRoot", str(state or self.state))

    def inbox(self, state: Path | None = None) -> list[dict]:
        d = w.inbox_dir(state or self.state)
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.is_dir() else []


class ABatchEventIsTheSingleEvent(_BatchCase):
    def test_the_written_file_is_the_same_but_for_id_and_ts(self):
        s_state, b_state = self.root / "s", self.root / "b"
        s_state.mkdir()
        b_state.mkdir()
        r = self.single(GOOD, state=s_state)
        self.assertEqual(0, r.returncode, r.stderr)
        rb, res = self.batch([GOOD], state=b_state)
        self.assertEqual(0, rb.returncode, rb.stderr)
        self.assertEqual("written", res[0]["status"])
        [one] = self.inbox(s_state)
        [two] = self.inbox(b_state)
        self.assertEqual(res[0]["id"], two["id"])
        for e in (one, two):
            del e["id"], e["ts"]
        self.assertEqual(one, two)

    def test_a_date_shaped_summary_is_written_as_given(self):
        """ConvertFrom-Json would turn it into a [datetime] and write it back in another shape."""
        ev = dict(GOOD, summary="2026-09-07T03:01:44.051Z")
        r, res = self.batch([ev])
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("2026-09-07T03:01:44.051Z", json.loads(
            (w.inbox_dir(self.state) / f"{res[0]['id']}.json").read_text(encoding="utf-8"))["summary"])

    def test_each_refusal_matches_the_single_write(self):
        secret = forge_token()
        cases = [
            dict(GOOD, summary=f"token {secret} here"),
            {k: v for k, v in GOOD.items() if k != "evidence"},
            dict(GOOD, type="musing"),
            dict(GOOD, evidence="trust me"),
            dict(GOOD, key="Bad Key"),
            dict(GOOD, summary="a\x01b"),
        ]
        r, res = self.batch(cases)
        self.assertEqual(1, r.returncode, r.stderr)
        self.assertNotIn(secret, r.stdout + r.stderr)
        for ev, got in zip(cases, res):
            s = self.single(ev)
            self.assertEqual(1, s.returncode, f"the single write accepted {ev}")
            self.assertEqual("refused", got["status"])
            self.assertIn(got["reason"], s.stderr, "the batch refused with a different reason than the single write")
        self.assertEqual([], self.inbox())
        self.assertIn("forge access token", res[0]["reason"])

    def test_one_refusal_does_not_stop_the_others_and_results_keep_input_order(self):
        events = [dict(GOOD, key=f"batch/k{i}") for i in range(5)]
        events[2] = dict(events[2], body=f"token {forge_token()}")
        r, res = self.batch(events)
        self.assertEqual(1, r.returncode)
        self.assertEqual([0, 1, 2, 3, 4], [x["index"] for x in res])
        self.assertEqual(["written", "written", "refused", "written", "written"], [x["status"] for x in res])
        self.assertEqual(sorted(x["id"] for x in res if x["id"]), sorted(e["id"] for e in self.inbox()))

    def test_a_hit_is_attributed_to_its_own_event_across_scan_chunks(self):
        """The scanner runs once per 200 events. A hit in the third chunk must refuse that event only."""
        events = [dict(GOOD, key=f"chunk/k{i}", summary=f"chunk event {i}") for i in range(450)]
        events[421] = dict(events[421], body=f"token {forge_token()}")
        r, res = self.batch(events)
        self.assertEqual(1, r.returncode, r.stderr)
        refused = [x["index"] for x in res if x["status"] == "refused"]
        self.assertEqual([421], refused)
        self.assertEqual(449, len(self.inbox()))


class ABatchRefusesWhatASingleWriteCannotCarry(_BatchCase):
    def test_an_event_cannot_carry_its_own_id_ts_or_seat(self):
        for field in ("id", "ts", "seat"):
            with self.subTest(field=field):
                r, res = self.batch([dict(GOOD, **{field: "x"})])
                self.assertEqual("refused", res[0]["status"])
                self.assertIn(f"cannot carry '{field}'", res[0]["reason"])
        self.assertEqual([], self.inbox())

    def test_an_unknown_field_is_refused(self):
        r, res = self.batch([dict(GOOD, colour="blue")])
        self.assertEqual("refused", res[0]["status"])
        self.assertIn("unknown field 'colour'", res[0]["reason"])

    def test_single_event_parameters_beside_from_json_stop_the_run(self):
        f = self.root / "b.json"
        f.write_text(json.dumps([GOOD]), encoding="utf-8")
        r = w.run(self.pwsh, w.WRITE, "-FromJson", str(f), "-Type", "lesson", "-Seat", "builder",
                  "-StateRoot", str(self.state))
        self.assertEqual(2, r.returncode)
        self.assertEqual([], self.inbox())

    def test_a_file_that_is_not_a_json_array_stops_the_run(self):
        for text in ("not json", json.dumps(GOOD)):
            with self.subTest(text=text[:10]):
                f = self.root / "bad.json"
                f.write_text(text, encoding="utf-8")
                r = w.run(self.pwsh, w.WRITE, "-FromJson", str(f), "-Seat", "builder", "-StateRoot", str(self.state))
                self.assertEqual(2, r.returncode)
        self.assertEqual([], self.inbox())


class AMemoryNoteIsEvidence(_BatchCase):
    def test_a_memory_citation_with_a_tilde_label_is_accepted_and_a_bare_one_is_not(self):
        """The import cites `memory:<root>/~-<project>/<file>.md`. The ref:path shape refused the `~`."""
        good = dict(GOOD, evidence="memory:.claude-account-3/~-Code-Thing/a note.md")
        # CONTROLS: a memory citation naming no file, and one naming no store, must still be refused.
        bare = dict(GOOD, evidence="memory:~")
        storeless = dict(GOOD, evidence="memory: see the note")
        # Both passed an unanchored first form of the pattern (round-2 review).
        tilde_root = dict(GOOD, evidence="memory:~/x.md")
        prose = dict(GOOD, evidence="memory:a/ trust me it is fine.md")
        r, res = self.batch([good, bare, storeless, tilde_root, prose])
        self.assertEqual(["written", "refused", "refused", "refused", "refused"], [x["status"] for x in res])
        for x in res[1:]:
            self.assertIn("evidence names no commit", x["reason"])


class CheckOnlyWritesNothing(_BatchCase):
    def test_it_reports_what_a_write_would_do_and_touches_no_state(self):
        events = [GOOD, dict(GOOD, key="check/two", body=f"token {forge_token()}")]
        r, res = self.batch(events, "-CheckOnly")
        self.assertEqual(1, r.returncode, r.stderr)
        self.assertEqual(["passed", "refused"], [x["status"] for x in res])
        self.assertEqual([], list(self.state.iterdir()), "a check created something under the state root")
        # CONTROL: the same batch without -CheckOnly writes the one that passed.
        r2, res2 = self.batch(events)
        self.assertEqual(["written", "refused"], [x["status"] for x in res2])
        self.assertEqual(1, len(self.inbox()))

    def test_check_only_without_from_json_is_refused(self):
        r = w.run(self.pwsh, w.WRITE, *single_args(GOOD), "-CheckOnly", "-Seat", "builder",
                  "-StateRoot", str(self.state))
        self.assertEqual(2, r.returncode)
        self.assertEqual([], self.inbox())


if __name__ == "__main__":
    unittest.main()
