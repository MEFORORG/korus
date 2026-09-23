"""`scripts/wiki/import.ps1` folds the per-account memory stores into the wiki once (spec Story 4).

WHAT IT PROMISES. It reads only the directories it is given (FR-023). One note becomes one event,
written through `write.ps1` and nowhere else (FR-001). Every merge is itself an event (FR-024). A
re-run adds nothing it already added (FR-027). A note the leak scan refuses is listed by store,
file and class, and never by value.

EVERY STORE HERE IS A TEMPORARY DIRECTORY built to the shape of a real memory note: YAML front
matter with `name`, `description` and `metadata.type`, then a body. No test reads a real store.

EACH ABSENCE CARRIES A CONTROL THAT FINDS THE SAME THING WHEN IT IS THERE. "The unlisted store was
not read" is only evidence beside "the same note, listed, is found by the same search".

Run: python -m pytest tests/test_wiki_import.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import _wikitest as w

IMPORT = w.WIKI / "import.ps1"
BACKSLASH = chr(92)


def forge_token() -> str:
    """A credential-shaped value, built at run time so this file carries no literal the leak gate
    over the tracked tree would fire on."""
    return "gh" + "p_" + "C" * 36


def fake_home() -> str:
    """A Windows home directory with a plausible account name, built at run time for the same reason."""
    return "C:" + BACKSLASH + "Users" + BACKSLASH + "alice"


def note_text(name: str, description: str | None, body: str, mtype: str | None = "feedback") -> str:
    lines = ["---", f"name: {name}"]
    if description is not None:
        lines.append(f"description: {json.dumps(description)}")
    lines += ["metadata:", "  node_type: memory"]
    if mtype is not None:
        lines.append(f"  type: {mtype}")
    lines += ["---", "", body, ""]
    return "\n".join(lines)


class _ImportCase(unittest.TestCase):
    def setUp(self):
        self.pwsh = w.find_pwsh_or_skip(self)
        tmp = tempfile.TemporaryDirectory(prefix="wiki-import-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / "state"
        self.state.mkdir()

    def store(self, label: str) -> Path:
        """A store at <root>/<label>/projects/proj/memory, the shape of a real config root."""
        d = self.root / "roots" / label / "projects" / "proj" / "memory"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def note(self, store: Path, file: str, name: str, description: str | None = "a lesson", body: str = "The body.",
             mtype: str | None = "feedback") -> Path:
        p = store / file
        p.write_text(note_text(name, description, body, mtype), encoding="utf-8")
        return p

    def run_import(self, *stores: Path, extra: tuple[str, ...] = (), json_out: bool = True):
        argv = ["-Store", ",".join(str(s) for s in stores), "-StateRoot", str(self.state), *extra]
        if json_out:
            argv.append("-Json")
        r = w.run(self.pwsh, IMPORT, *argv)
        report = json.loads(r.stdout) if json_out and r.stdout.strip().startswith("{") else None
        return r, report

    def inbox(self) -> list[dict]:
        d = w.inbox_dir(self.state)
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.is_dir() else []

    def on_key(self, key: str) -> list[dict]:
        return [e for e in self.inbox() if e["key"] == key]

    def query(self, text: str, *extra: str) -> list[dict]:
        r = w.run(self.pwsh, w.QUERY, "-Text", text, "-StateRoot", str(self.state), "-Json", *extra)
        self.assertEqual(0, r.returncode, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else []


class OneNoteBecomesOneEvent(_ImportCase):
    def test_the_fields_map_as_documented(self):
        a = self.store(".claude-account-3")
        self.note(a, "shaped.md", "Shaped Lesson_One", "Retire by key, never by text", "Why it matters.\n\nDetail.")
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        [ev] = self.inbox()
        self.assertEqual("memory/shaped-lesson-one", ev["key"])
        self.assertEqual("lesson", ev["type"])
        self.assertEqual("Retire by key, never by text", ev["summary"])
        self.assertEqual("Why it matters.\n\nDetail.", ev["body"])
        self.assertEqual("memory:.claude-account-3/shaped.md", ev["evidence"])
        self.assertEqual("import", ev["seat"])
        self.assertEqual(1, rep["counts"]["imported"])

    def test_each_type_maps_and_an_unknown_one_defaults_to_lesson(self):
        a = self.store("acct")
        expect = {"feedback": "lesson", "project": "decision", "reference": "gotcha", "user": "decision",
                  "musing": "lesson", None: "lesson"}
        for i, t in enumerate(expect):
            self.note(a, f"t{i}.md", f"type-{i}", f"type case {i}", mtype=t)
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        got = {e["key"]: e["type"] for e in self.inbox()}
        for i, want in enumerate(expect.values()):
            self.assertEqual(want, got[f"memory/type-{i}"])
        self.assertEqual(2, rep["counts"]["type_defaulted"])

    def test_the_front_matter_shapes_real_notes_carry(self):
        a = self.store("acct")
        (a / "folded.md").write_text("---\nname: folded\ndescription: >\n  folded over\n  two lines\n"
                                     "metadata:\n  type: project\n---\nbody\n", encoding="utf-8")
        (a / "plain.md").write_text("---\nname: plain\ndescription:\n  plain on the\n  next lines\n"
                                    "metadata:\n  type: project\n---\nbody\n", encoding="utf-8")
        (a / "escaped.md").write_text('---\nname: escaped\ndescription: "\\"quoted\\" word and a \\\\ slash"\n'
                                      "metadata:\n  type: project\n---\nbody\n", encoding="utf-8")
        (a / "opener.md").write_text('---\nname: opener\ndescription: "done" is not "merged", a plain line\n'
                                     "metadata:\n  type: project\n---\nbody\n", encoding="utf-8")
        (a / "single.md").write_text("---\nname: single\ndescription: 'it''s single'\n"
                                     "metadata:\n  metadata:\n    type: reference\n---\r\nbody\r\n", encoding="utf-8")
        (a / "nodesc.md").write_text("---\nname: nodesc\nmetadata:\n  type: project\n---\n# Heading\n"
                                     "First sentence here. Second one.\n", encoding="utf-8")
        r, _ = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        got = {e["key"]: e for e in self.inbox()}
        self.assertEqual("folded over two lines", got["memory/folded"]["summary"])
        self.assertEqual("plain on the next lines", got["memory/plain"]["summary"])
        self.assertEqual('"quoted" word and a \\ slash', got["memory/escaped"]["summary"])
        self.assertEqual('"done" is not "merged", a plain line', got["memory/opener"]["summary"])
        self.assertEqual("it's single", got["memory/single"]["summary"])
        self.assertEqual("gotcha", got["memory/single"]["type"], "a type nested under metadata.metadata was missed")
        self.assertEqual("body", got["memory/single"]["body"], "a CRLF note kept its carriage returns")
        self.assertEqual("First sentence here.", got["memory/nodesc"]["summary"])

    def test_the_file_stem_names_the_key_when_the_note_has_no_name(self):
        a = self.store("acct")
        (a / "Stem_Name.md").write_text("---\ndescription: d\nmetadata:\n  type: user\n---\nb\n", encoding="utf-8")
        self.run_import(a)
        self.assertEqual(["memory/stem-name"], [e["key"] for e in self.inbox()])

    def test_a_long_description_is_cut_and_kept_whole_in_the_body(self):
        a = self.store("acct")
        long_desc = "word " * 150
        self.note(a, "long.md", "long", long_desc.strip(), "the body")
        self.note(a, "huge.md", "huge", "huge body", "x" * 25000)
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        got = {e["key"]: e for e in self.inbox()}
        s = got["memory/long"]["summary"]
        self.assertLessEqual(len(s), 400)
        self.assertTrue(s.endswith("..."))
        self.assertTrue(got["memory/long"]["body"].startswith("Description: " + long_desc.strip()))
        self.assertTrue(got["memory/long"]["body"].endswith("the body"))
        b = got["memory/huge"]["body"]
        self.assertLessEqual(len(b), 20000)
        self.assertIn("[truncated at import; the full note is the evidence file]", b)
        self.assertEqual((1, 1), (rep["counts"]["summary_truncated"], rep["counts"]["body_truncated"]))


class OnlyTheListedStoresAreRead(_ImportCase):
    def test_a_store_that_is_not_listed_is_never_read(self):
        """FR-023. The unlisted store sits beside the listed ones, where any glob would find it."""
        a, b, c = self.store("acct-a"), self.store("acct-b"), self.store("acct-c")
        self.note(a, "x.md", "x", "in a")
        self.note(b, "y.md", "y", "in b")
        token = "zqxunlistedtoken"
        self.note(c, "z.md", "z", f"planted {token}")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        blob = "".join(p.read_text(encoding="utf-8") for p in w.inbox_dir(self.state).glob("*.json"))
        self.assertNotIn(token, blob + r.stdout + r.stderr)
        self.assertEqual(["acct-a", "acct-b"], [s["label"] for s in rep["stores"]])
        self.assertEqual(2, rep["counts"]["seen"])
        # CONTROL: the same note, listed, is found by the same search, so the absence above is armed.
        r2, _ = self.run_import(a, b, c)
        blob2 = "".join(p.read_text(encoding="utf-8") for p in w.inbox_dir(self.state).glob("*.json"))
        self.assertIn(token, blob2)

    def test_memory_md_is_an_index_and_is_never_imported(self):
        a = self.store("acct")
        body = "index body qqmemoryindex"
        (a / "MEMORY.md").write_text(note_text("the-index", "an index", body), encoding="utf-8")
        r, rep = self.run_import(a)
        self.assertEqual(0, rep["counts"]["seen"])
        self.assertEqual([], self.inbox())
        # CONTROL: the identical text under another file name is imported.
        (a / "other.md").write_text(note_text("the-index", "an index", body), encoding="utf-8")
        self.run_import(a)
        self.assertEqual(["memory/the-index"], [e["key"] for e in self.inbox()])

    def test_a_file_with_no_front_matter_is_skipped_and_named(self):
        a = self.store("acct")
        (a / "bare.md").write_text("just text\n", encoding="utf-8")
        (a / "open.md").write_text("---\nname: never-closed\n", encoding="utf-8")
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(2, rep["counts"]["no_front_matter"])
        self.assertEqual(["acct/bare.md", "acct/open.md"], rep["no_front_matter"])
        self.assertEqual([], self.inbox())

    def test_a_subdirectory_of_a_store_is_not_read(self):
        a = self.store("acct")
        sub = a / "nested"
        sub.mkdir()
        self.note(sub, "deep.md", "deep", "nested note")
        self.note(a, "top.md", "top", "top note")
        self.run_import(a)
        self.assertEqual(["memory/top"], [e["key"] for e in self.inbox()])

    def test_bad_store_arguments_stop_the_run_and_write_nothing(self):
        a = self.store("acct")
        self.note(a, "x.md", "x", "x")
        twin = self.root / "other" / "acct" / "projects" / "proj" / "memory"
        twin.mkdir(parents=True)
        cases = {
            "no store": ["-StateRoot", str(self.state)],
            "missing dir": ["-Store", f"{a},{self.root / 'nope'}", "-StateRoot", str(self.state)],
            "a pattern": ["-Store", str(self.root / "roots" / "*"), "-StateRoot", str(self.state)],
            "one label twice": ["-Store", f"{a},{twin}", "-StateRoot", str(self.state)],
            "missing record repo": ["-Store", str(a), "-StateRoot", str(self.state), "-RecordRepo", str(self.root / "nope")],
        }
        for name, argv in cases.items():
            with self.subTest(case=name):
                r = w.run(self.pwsh, IMPORT, *argv)
                self.assertEqual(2, r.returncode, r.stdout + r.stderr)
                self.assertEqual([], self.inbox())


class ARerunAddsNothingItAlreadyAdded(_ImportCase):
    def test_an_unchanged_rerun_writes_zero_events(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        for i in range(3):
            self.note(a, f"a{i}.md", f"a-{i}", f"note a {i}")
        self.note(b, "same.md", "shared", "same text", "same body")
        self.note(a, "same.md", "shared", "same text", "same body")
        self.note(b, "diff.md", "differs", "text from b")
        self.note(a, "diff.md", "differs", "text from a")
        r, first = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        before = sorted(p.name for p in w.inbox_dir(self.state).iterdir())
        r2, second = self.run_import(a, b)
        self.assertEqual(0, r2.returncode, r2.stderr)
        self.assertEqual(before, sorted(p.name for p in w.inbox_dir(self.state).iterdir()))
        self.assertEqual(7, second["counts"]["unchanged"])
        self.assertEqual(0, second["counts"]["imported"] + second["counts"]["superseded"] + second["counts"]["merged"])
        # CONTROL: the first run did write, so the second run's zero is not a run that writes nothing.
        self.assertEqual(7, len(before))

    def test_an_edited_note_supersedes_its_own_earlier_import(self):
        a = self.store("acct")
        p = self.note(a, "rule.md", "gate-rule", "the gate reads origin main", "old wording of the rule")
        self.run_import(a)
        [old] = self.inbox()
        p.write_text(note_text("gate-rule", "the gate reads the merge base", "new wording of the rule"), encoding="utf-8")
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        new = [e for e in self.inbox() if e["id"] != old["id"]]
        self.assertEqual(1, len(new), "an edit wrote other than exactly one event")
        self.assertEqual([old["id"]], new[0]["supersedes"])
        self.assertEqual(1, rep["counts"]["superseded"])
        hits = self.query("gate rule wording")
        self.assertEqual([new[0]["id"]], [h["id"] for h in hits])
        # CONTROL: the old event is still there, and -History finds it, so the default hid it.
        hist = {h["id"]: h["label"] for h in self.query("gate rule wording", "-History")}
        self.assertEqual("historical", hist.get(old["id"]))
        # A second re-run after the edit is quiet again.
        _, rep3 = self.run_import(a)
        self.assertEqual(1, rep3["counts"]["unchanged"])
        self.assertEqual(2, len(self.inbox()))

    def test_the_record_repository_log_counts_as_already_imported(self):
        a = self.store("acct")
        self.note(a, "x.md", "logged", "already in the log", "log body")
        repo = self.root / "record"
        w.plant(w.log_dir(repo, w.days_ago(3)), when=w.days_ago(3), type="lesson", key="memory/logged",
                seat="import", summary="already in the log", body="log body", evidence="memory:acct/x.md")
        r, rep = self.run_import(a, extra=("-RecordRepo", str(repo)))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, rep["counts"]["unchanged"])
        self.assertEqual([], self.inbox())
        # CONTROL: without -RecordRepo the same note is new.
        _, rep2 = self.run_import(a)
        self.assertEqual(1, rep2["counts"]["imported"])


class NotesThatShareAName(_ImportCase):
    def test_same_name_same_text_is_one_event_and_one_merge_record(self):
        """FR-024: the merge is itself an event."""
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "shared-lesson", "both hold this", "same body")
        self.note(b, "n.md", "shared-lesson", "both hold this", "same body")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        [kept] = self.on_key("memory/shared-lesson")
        [merge] = self.on_key("memory/shared-lesson/merge")
        self.assertEqual("memory:acct-a/n.md", kept["evidence"])
        self.assertEqual("decision", merge["type"])
        self.assertEqual(kept["evidence"], merge["evidence"])
        self.assertIn("acct-a", merge["summary"])
        self.assertIn("acct-b", merge["summary"])
        self.assertEqual("kept: memory:acct-a/n.md\nmerged: memory:acct-b/n.md", merge["body"])
        self.assertEqual((1, 1), (rep["counts"]["imported"], rep["counts"]["merged"]))

    def test_same_name_different_text_keeps_both_and_supersedes_neither(self):
        """Story 4 scenario 2: both are kept, and lint files the pair."""
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "split-lesson", "store a says this")
        self.note(b, "n.md", "split-lesson", "store b says that")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        both = self.on_key("memory/split-lesson")
        self.assertEqual(2, len(both))
        self.assertTrue(all("supersedes" not in e for e in both), "a different store's note superseded another")
        self.assertEqual([], self.on_key("memory/split-lesson/merge"))
        self.assertEqual(1, rep["counts"]["conflicts"])


class TheLeakScanStillDecides(_ImportCase):
    def test_a_planted_credential_is_refused_and_listed_by_class_never_by_value(self):
        a = self.store("acct")
        secret = forge_token()
        self.note(a, "leak.md", "leaky", "has a token", f"token {secret} here")
        self.note(a, "twin.md", "twin", "has a token", "token REDACTED here")
        r, rep = self.run_import(a)
        self.assertEqual(1, r.returncode, r.stderr)
        self.assertNotIn(secret, r.stdout + r.stderr)
        self.assertEqual([{"note": "acct/leak.md", "class": "forge access token"}], rep["refused_notes"])
        # CONTROL: the harmless twin in the same store was written, so the refusal is the scan's.
        self.assertEqual(["memory/twin"], [e["key"] for e in self.inbox()])

    def test_a_merge_into_a_refused_note_is_refused_too(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        secret = forge_token()
        for s in (a, b):
            self.note(s, "n.md", "leaky", "has a token", f"token {secret} here")
        r, rep = self.run_import(a, b)
        self.assertEqual(1, r.returncode)
        self.assertEqual([], self.inbox(), "a merge record pointed at an event that was never written")
        self.assertEqual({"acct-a/n.md", "acct-b/n.md"}, {x["note"] for x in rep["refused_notes"]})
        self.assertNotIn(secret, r.stdout + r.stderr)


class TheHomeDirectoryBecomesATilde(_ImportCase):
    def test_every_spelling_of_the_home_prefix_is_normalised(self):
        home = fake_home()
        body = "\n".join([
            home + BACKSLASH + "proj" + BACKSLASH + "a.txt",
            "C:/Users/alice/proj/b.txt",
            "/c/Users/alice/proj/c.txt",
            "c:" + BACKSLASH + "USERS" + BACKSLASH + "ALICE",
        ])
        a = self.store("acct")
        self.note(a, "h.md", "homey", "paths in " + home, body)
        r, rep = self.run_import(a, extra=("-HomeDir", home))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        [ev] = self.inbox()
        self.assertNotIn("alice", (ev["body"] + ev["summary"]).lower())
        self.assertEqual("~" + BACKSLASH + "proj" + BACKSLASH + "a.txt", ev["body"].splitlines()[0])
        self.assertEqual(["~/proj/b.txt", "~/proj/c.txt", "~"], ev["body"].splitlines()[1:])
        self.assertEqual("paths in ~", ev["summary"])
        self.assertEqual(1, rep["counts"]["home_normalised"])

    def test_without_normalisation_the_scan_refuses_the_same_text(self):
        """The CONTROL for the case above: the text as the note holds it cannot be written."""
        r = w.run(self.pwsh, w.WRITE, "-Type", "lesson", "-Key", "memory/homey", "-Summary", "s",
                  "-Evidence", "memory:acct/h.md", "-Body", fake_home() + BACKSLASH + "proj",
                  "-Seat", "import", "-StateRoot", str(self.state))
        self.assertEqual(1, r.returncode)
        self.assertIn("home path", r.stderr)

    def test_another_account_is_not_normalised_and_is_refused(self):
        """`alice2` shares a prefix with `alice`. Rewriting it would produce `~2`, a path to nowhere."""
        a = self.store("acct")
        self.note(a, "o.md", "other", "other account", "C:" + BACKSLASH + "Users" + BACKSLASH + "alice2" + BACKSLASH + "x")
        r, rep = self.run_import(a, extra=("-HomeDir", fake_home()))
        self.assertEqual(1, r.returncode)
        self.assertEqual("acct/o.md", rep["refused_notes"][0]["note"])
        self.assertIn("home path", rep["refused_notes"][0]["class"])
        self.assertEqual(0, rep["counts"]["home_normalised"])

    def test_the_default_home_is_the_current_users(self):
        a = self.store("acct")
        mine = os.path.expanduser("~")
        self.note(a, "d.md", "default-home", "default", os.path.join(mine, "somewhere"))
        r, _ = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        [ev] = self.inbox()
        self.assertTrue(ev["body"].startswith("~"), "the current user's home was not normalised by default")


class WhatIfWritesNothing(_ImportCase):
    def test_it_reports_the_run_and_leaves_the_state_root_untouched(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "shared", "same", "same")
        self.note(b, "n.md", "shared", "same", "same")
        self.note(a, "leak.md", "leaky", "token", f"token {forge_token()}")
        r, rep = self.run_import(a, b, extra=("-WhatIf",))
        self.assertEqual(1, r.returncode, r.stderr)
        self.assertTrue(rep["what_if"])
        self.assertEqual((1, 1, 1), (rep["counts"]["imported"], rep["counts"]["merged"], rep["counts"]["refused"]))
        self.assertEqual([], list(self.state.iterdir()), "-WhatIf created something under the state root")
        # CONTROL: the same run without -WhatIf writes, and reports the same counts.
        r2, rep2 = self.run_import(a, b)
        self.assertEqual(rep["counts"], rep2["counts"])
        self.assertEqual(2, len(self.inbox()))

    def test_the_text_report_says_nothing_was_written(self):
        a = self.store("acct")
        self.note(a, "n.md", "n", "d")
        r, _ = self.run_import(a, extra=("-WhatIf",), json_out=False)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("NOTHING WAS WRITTEN", r.stdout)
        self.assertIn("imported           1", r.stdout)


class AnImportOfTheReferenceSizeIsQuick(_ImportCase):
    def test_a_thousand_notes_import_inside_a_loose_ceiling(self):
        """The reference corpus is about 960 notes. A process per note took about ten minutes.

        The ceiling is loose on purpose: it includes cold `pwsh` starts on a shared runner, and it
        exists to catch a return to one process per note, not to certify a speed.
        """
        a, b = self.store("acct-a"), self.store("acct-b")
        for s, name in ((a, "a"), (b, "b")):
            for i in range(500):
                self.note(s, f"n{i}.md", f"note-{name}-{i}", f"synthetic lesson {i} from {name}", "body " * 50)
        t0 = time.monotonic()
        r, rep = self.run_import(a, b)
        elapsed = time.monotonic() - t0
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1000, rep["counts"]["imported"])
        self.assertEqual(1000, len(self.inbox()))
        self.assertLess(elapsed, 120, f"1000 notes took {elapsed:.1f}s")


if __name__ == "__main__":
    unittest.main()
