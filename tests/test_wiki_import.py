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
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
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


def set_modified(path: Path, day: str) -> None:
    """Give a note file a chosen last-write day, at noon UTC, as a copy or an old edit leaves it."""
    when = datetime.strptime(day, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc).timestamp()
    os.utime(path, (when, when))


def day_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")


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

    def under(self, prefix: str) -> list[dict]:
        return [e for e in self.inbox() if e["key"].startswith(prefix)]

    def live_on(self, key: str, words: str) -> list[dict]:
        """What a default query returns on one key: the guard's live set, not the raw inbox."""
        return [h for h in self.query(words, "-Limit", "20") if h["key"] == key]

    def lint_conflicts(self) -> list[dict]:
        r = w.run(self.pwsh, w.WIKI / "lint.ps1", "-StateRoot", str(self.state), "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        doc = json.loads(r.stdout)
        self.assertGreater(doc["inputs"]["events"], 0, "lint read no event, so its zero measured nothing")
        return [f for f in doc["findings"] if f["class"] == "conflict"]

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
        self.assertEqual("memory:.claude-account-3/proj/shaped.md", ev["evidence"])
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
        self.assertEqual(["acct-a/proj", "acct-b/proj"], [s["label"] for s in rep["stores"]])
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
        self.assertEqual(["acct/proj/bare.md", "acct/proj/open.md"], rep["no_front_matter"])
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
            "record repo with no log": ["-Store", str(a), "-StateRoot", str(self.state), "-RecordRepo", str(self.root)],
            "a bad seat": ["-Store", str(a), "-StateRoot", str(self.state), "-Seat", "Not A Seat"],
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
                seat="import", summary="already in the log", body="log body", evidence="memory:acct/proj/x.md")
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
        [merge] = self.on_key("memory-merge/shared-lesson/acct-b-proj")
        self.assertEqual("memory:acct-a/proj/n.md", kept["evidence"])
        self.assertEqual("decision", merge["type"])
        self.assertEqual(kept["evidence"], merge["evidence"])
        self.assertIn("acct-a", merge["summary"])
        self.assertIn("acct-b", merge["summary"])
        kept_line, merged_line, text_line = merge["body"].split("\n")
        self.assertEqual("kept: memory:acct-a/proj/n.md", kept_line)
        self.assertEqual("merged: memory:acct-b/proj/n.md", merged_line)
        self.assertRegex(text_line, r"^text: sha256:[0-9a-f]{64}$")
        self.assertEqual((1, 1), (rep["counts"]["imported"], rep["counts"]["merged"]))

    def test_same_name_different_text_is_one_event_and_one_outranked_record(self):
        """Story 4 scenario 2, amended 2026-09-26: one text per key, and the other is recorded."""
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "split-lesson", "store a says this")
        self.note(b, "n.md", "split-lesson", "store b says that")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        [kept] = self.on_key("memory/split-lesson")
        self.assertEqual("memory:acct-a/proj/n.md", kept["evidence"], "one day, so the first store named wins")
        [rec] = self.under("memory-merge/split-lesson/")
        self.assertEqual("memory-merge/split-lesson/acct-b-proj", rec["key"])
        self.assertEqual(f"outranked: acct-a/proj {kept['noted']}", rec["body"].split("\n")[3])
        self.assertIn("different text", rec["summary"])
        self.assertEqual((1, 1, 0), (rep["counts"]["imported"], rep["counts"]["outranked"], rep["counts"]["merged"]))


class TheLeakScanStillDecides(_ImportCase):
    def test_a_planted_credential_is_refused_and_listed_by_class_never_by_value(self):
        a = self.store("acct")
        secret = forge_token()
        self.note(a, "leak.md", "leaky", "has a token", f"token {secret} here")
        self.note(a, "twin.md", "twin", "has a token", "token REDACTED here")
        r, rep = self.run_import(a)
        self.assertEqual(1, r.returncode, r.stderr)
        self.assertNotIn(secret, r.stdout + r.stderr)
        self.assertEqual([{"note": "acct/proj/leak.md", "class": "forge access token"}], rep["refused_notes"])
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
        self.assertEqual({"acct-a/proj/n.md", "acct-b/proj/n.md"}, {x["note"] for x in rep["refused_notes"]})
        self.assertNotIn(secret, r.stdout + r.stderr)


class TheHomeDirectoryBecomesATilde(_ImportCase):
    def test_every_spelling_of_the_home_prefix_is_normalised(self):
        home = fake_home()
        body = "\n".join([
            home + BACKSLASH + "proj" + BACKSLASH + "a.txt",
            "C:/" + "Users/alice/proj/b.txt",
            "/c/" + "Users/alice/proj/c.txt",
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
        self.assertEqual("acct/proj/o.md", rep["refused_notes"][0]["note"])
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


class StoresUnderOneAccountStayApart(_ImportCase):
    def test_two_projects_under_one_root_get_distinct_evidence(self):
        """One account holds a store per project. Labelled by the root alone, both files were `x.md`
        under one label, and the second project's note superseded the first's."""
        p1 = self.root / "roots" / "acct" / "projects" / "one" / "memory"
        p2 = self.root / "roots" / "acct" / "projects" / "two" / "memory"
        p1.mkdir(parents=True)
        p2.mkdir(parents=True)
        self.note(p1, "x.md", "same-name", "text in project one")
        self.note(p2, "x.md", "same-name", "text in project two")
        r, rep = self.run_import(p1, p2)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(["memory:acct/one/x.md"], [e["evidence"] for e in self.on_key("memory/same-name")])
        [rec] = self.under("memory-merge/same-name/")
        self.assertIn("merged: memory:acct/two/x.md", rec["body"])
        self.assertTrue(all("supersedes" not in e for e in self.inbox()))
        _, rep2 = self.run_import(p2)
        self.assertEqual(1, rep2["counts"]["unchanged"], "a later run of one project disturbed the other")

    def test_the_home_directory_in_a_project_folder_becomes_a_tilde(self):
        """A project folder spells its path with dashes, `C--Users-<u>-Code-X`, account name included."""
        folder = "C--Users-alice-Code-Thing"
        d = self.root / "roots" / "acct" / "projects" / folder / "memory"
        d.mkdir(parents=True)
        self.note(d, "x.md", "labelled", "label case")
        r, rep = self.run_import(d, extra=("-HomeDir", fake_home()))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("acct/~-Code-Thing", rep["stores"][0]["label"])
        self.assertEqual("memory:acct/~-Code-Thing/x.md", self.inbox()[0]["evidence"])
        self.assertNotIn("alice", self.inbox()[0]["evidence"])


class AReplacedTextIsNotMergedInto(_ImportCase):
    def test_a_note_matching_only_a_superseded_event_is_not_merged_into_it(self):
        """Step 3 compares with CURRENT events. Matched against a replaced one, the other store's note
        would count as merged into a text the wiki no longer holds."""
        a, b = self.store("acct-a"), self.store("acct-b")
        p = self.note(a, "n.md", "moving", "the first wording", "body")
        self.run_import(a)
        p.write_text(note_text("moving", "the second wording", "body"), encoding="utf-8")
        set_modified(p, day_ago(1))
        self.run_import(a)
        newer = self.note(b, "n.md", "moving", "the first wording", "body")
        set_modified(newer, day_ago(0))
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((1, 0), (rep["counts"]["superseded"], rep["counts"]["merged"]))
        [live] = self.live_on("memory/moving", "first wording")
        self.assertEqual("memory:acct-b/proj/n.md", live["evidence"])

    def test_control_the_same_note_merges_while_the_text_is_current(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "moving", "the first wording", "body")
        self.run_import(a)
        self.note(b, "n.md", "moving", "the first wording", "body")
        _, rep = self.run_import(a, b)
        self.assertEqual((0, 1), (rep["counts"]["imported"], rep["counts"]["merged"]))


class ARerunStaysQuietInTheEdgeCases(_ImportCase):
    def rerun_writes_nothing(self, *stores: Path):
        r, _ = self.run_import(*stores)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        before = sorted(p.name for p in w.inbox_dir(self.state).iterdir())
        self.assertTrue(before, "the first run wrote nothing, so a quiet re-run proves nothing")
        r2, rep2 = self.run_import(*stores)
        self.assertEqual(before, sorted(p.name for p in w.inbox_dir(self.state).iterdir()))
        return rep2

    def test_a_note_named_merge_is_a_note_not_a_merge_record(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "merge.md", "merge", "a note about merging")
        self.note(a, "s.md", "shared", "same", "same")
        self.note(b, "s.md", "shared", "same", "same")
        rep = self.rerun_writes_nothing(a, b)
        self.assertEqual(3, rep["counts"]["unchanged"])
        self.assertEqual(1, len(self.on_key("memory/merge")))

    def test_a_merged_file_name_with_a_space_is_recognised_as_merged(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "my note.md", "spaced", "same", "same")
        self.note(b, "my note.md", "spaced", "same", "same")
        rep = self.rerun_writes_nothing(a, b)
        self.assertEqual(2, rep["counts"]["unchanged"])
        self.assertEqual(1, len(self.under("memory-merge/spaced/")))

    def test_a_description_shaped_like_a_timestamp_is_unchanged_on_a_rerun(self):
        """The shared reader turns such a string into a date, and the date never equals the note."""
        a = self.store("acct")
        self.note(a, "t.md", "stamped", "2026-09-07T03:01:44.051Z", "2026-09-07T03:01:44.051Z")
        rep = self.rerun_writes_nothing(a)
        self.assertEqual(1, rep["counts"]["unchanged"])
        self.assertEqual("2026-09-07T03:01:44.051Z", self.inbox()[0]["summary"])


class TheHomeDirectoryEdges(_ImportCase):
    def test_a_home_path_ending_a_sentence_is_normalised_and_a_sibling_file_is_not(self):
        a = self.store("acct")
        self.note(a, "end.md", "ends", "the home is " + fake_home() + ".", "body")
        self.note(a, "bak.md", "bak", "a sibling", fake_home() + ".bak")
        r, rep = self.run_import(a, extra=("-HomeDir", fake_home()))
        got = {e["key"]: e for e in self.inbox()}
        self.assertEqual("the home is ~.", got["memory/ends"]["summary"])
        # `alice.bak` is another directory, not the home, so it is left as it is and the scan decides.
        self.assertNotIn("memory/bak", got)
        self.assertEqual(["acct/proj/bak.md"], [x["note"] for x in rep["refused_notes"]])


class TheExitCodeSaysWhenToLook(_ImportCase):
    def test_an_unreadable_existing_event_makes_the_run_exit_1(self):
        a = self.store("acct")
        self.note(a, "x.md", "x", "x")
        w.inbox_dir(self.state).mkdir(parents=True)
        (w.inbox_dir(self.state) / "torn.json").write_text("{not json", encoding="utf-8")
        r, rep = self.run_import(a)
        self.assertEqual(1, r.returncode, r.stderr)
        self.assertEqual(1, rep["existing_unreadable"])
        # CONTROL: the same run over a clean inbox exits 0.
        (w.inbox_dir(self.state) / "torn.json").unlink()
        r2, _ = self.run_import(a)
        self.assertEqual(0, r2.returncode, r2.stderr)

    def test_no_record_repo_is_warned_about(self):
        a = self.store("acct")
        self.note(a, "x.md", "x", "x")
        r, _ = self.run_import(a)
        self.assertIn("no -RecordRepo", r.stderr)

    def test_an_empty_seat_falls_back_to_import(self):
        a = self.store("acct")
        self.note(a, "x.md", "x", "x")
        r, _ = self.run_import(a, extra=("-Seat", ""))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(["import"], [e["seat"] for e in self.inbox()])


class APartWrittenBatchIsReportedAsSuch(_ImportCase):
    """write.ps1 exits 2 both when it wrote nothing and when one write failed after others landed.
    Only its stdout tells the two apart. A stub write.ps1 stands in for a disk fault, which a real
    write cannot be made to hit on demand."""

    def stub_tree(self) -> Path:
        tree = self.root / "tree"
        wiki = tree / "scripts" / "wiki"
        wiki.mkdir(parents=True)
        for name in ("import.ps1", "_event.ps1"):
            (wiki / name).write_text((w.WIKI / name).read_text(encoding="utf-8"), encoding="utf-8")
        (wiki / "write.ps1").write_text(
            "param([string]$FromJson, [string]$Seat, [string]$StateRoot, [switch]$CheckOnly)\n"
            "$items = @(Get-Content -Raw -LiteralPath $FromJson | ConvertFrom-Json)\n"
            "if ($env:WIKI_STUB -eq 'nothing') { [Console]::Error.WriteLine('stub: stopped'); exit 2 }\n"
            "$out = for ($i = 0; $i -lt $items.Count; $i++) {\n"
            "  [pscustomobject]@{ index = $i; status = 'failed'; id = $null; code = 2; reason = 'could not write x' } }\n"
            "ConvertTo-Json -InputObject @($out)\n"
            "exit 2\n", encoding="utf-8")
        return wiki / "import.ps1"

    def run_stub(self, mode: str):
        a = self.store("acct")
        self.note(a, "x.md", "x", "x")
        script = self.stub_tree()
        return w.run(self.pwsh, script, "-Store", str(a), "-StateRoot", str(self.state), "-Json",
                     env={"WIKI_STUB": mode})

    def test_per_event_failures_are_listed_not_called_nothing_written(self):
        r = self.run_stub("failed")
        self.assertEqual(1, r.returncode, r.stderr)
        rep = json.loads(r.stdout)
        self.assertEqual(1, rep["counts"]["not_written"])
        self.assertNotIn("Nothing was written", r.stderr)

    def test_control_a_batch_that_stopped_early_is_exit_2(self):
        r = self.run_stub("nothing")
        self.assertEqual(2, r.returncode)
        self.assertIn("Nothing was written", r.stderr)


class WhatTheOwnerWithdrewStaysWithdrawn(_ImportCase):
    """Round-2 review: rule 2 matched only CURRENT events, so a merged copy whose kept event was later
    retired or superseded found no match and was written again, newer than the retire."""

    def owner_write(self, *args: str) -> str:
        r = w.run(self.pwsh, w.WRITE, *args, "-Evidence", "owner ruling 2026-09-23", "-Seat", "manager",
                  "-StateRoot", str(self.state))
        self.assertEqual(0, r.returncode, r.stderr)
        return r.stdout.strip()

    def shared_pair(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "foo.md", "foo", "shared text", "body")
        self.note(b, "foo.md", "foo", "shared text", "body")
        _, rep = self.run_import(a, b)
        self.assertEqual((1, 1), (rep["counts"]["imported"], rep["counts"]["merged"]))
        return a, b

    def test_a_retire_of_the_kept_event_is_not_undone_by_a_rerun(self):
        a, b = self.shared_pair()
        self.owner_write("-Type", "retire", "-Key", "memory/foo", "-Summary", "withdrawn")
        before = len(self.inbox())
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(before, len(self.inbox()), "a re-run wrote over an Owner retire")
        self.assertEqual(2, rep["counts"]["unchanged"])
        # CONTROL: the query shows nothing on the key, so the retire is in force.
        self.assertEqual([], [h for h in self.query("shared text") if h["key"] == "memory/foo"])

    def test_a_supersede_of_the_kept_event_is_not_undone_by_a_rerun(self):
        a, b = self.shared_pair()
        [kept] = self.on_key("memory/foo")
        self.owner_write("-Type", "supersede", "-Key", "memory/foo", "-Summary", "replaced", "-Supersedes", kept["id"])
        before = len(self.inbox())
        _, rep = self.run_import(a, b)
        self.assertEqual(before, len(self.inbox()))
        self.assertEqual(2, rep["counts"]["unchanged"])

    def test_a_merged_note_that_changes_and_is_newest_is_imported_again(self):
        """CONTROL for the two above: the skip is keyed on the notes' text, not on their name."""
        a, b = self.store("acct-a"), self.store("acct-b")
        set_modified(self.note(a, "foo.md", "foo", "shared text", "body"), day_ago(3))
        set_modified(self.note(b, "foo.md", "foo", "shared text", "body"), day_ago(3))
        _, rep = self.run_import(a, b)
        self.assertEqual((1, 1), (rep["counts"]["imported"], rep["counts"]["merged"]))
        self.note(b, "foo.md", "foo", "text b now says", "body")
        _, rep = self.run_import(a, b)
        self.assertEqual(1, rep["counts"]["superseded"])
        self.assertEqual(["text b now says"], [h["summary"] for h in self.live_on("memory/foo", "text now says")])


class ASupersedeInThisRunCountsForThisRun(_ImportCase):
    def test_a_note_holding_the_text_this_run_replaces_is_not_merged_into_it(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        pa = self.note(a, "n.md", "moving", "old text", "body")
        self.run_import(a)
        pa.write_text(note_text("moving", "new text", "body"), encoding="utf-8")
        self.note(b, "n.md", "moving", "old text", "body")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((1, 0, 0, 1), (rep["counts"]["superseded"], rep["counts"]["imported"],
                                        rep["counts"]["merged"], rep["counts"]["outranked"]))
        [rec] = self.under("memory-merge/")
        self.assertIn("outranked: acct-a/proj", rec["body"], "b's old text was recorded as merged into a replaced text")
        _, rep3 = self.run_import(a, b)
        self.assertEqual(2, rep3["counts"]["unchanged"])

    def test_both_stores_start_equal_then_one_edits(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        pa = self.note(a, "n.md", "moving", "old text", "body")
        self.note(b, "n.md", "moving", "old text", "body")
        self.run_import(a, b)
        pa.write_text(note_text("moving", "new text", "body"), encoding="utf-8")
        _, rep2 = self.run_import(a, b)
        # b's record said "merged, same text" into the event this run replaced, so it is recorded again.
        self.assertEqual((1, 1), (rep2["counts"]["superseded"], rep2["counts"]["outranked"]))
        before = len(self.inbox())
        _, rep3 = self.run_import(a, b)
        self.assertEqual(before, len(self.inbox()), "the third run, with nothing changed, wrote an event")
        self.assertEqual(2, rep3["counts"]["unchanged"])


class ARenamedNoteReplacesItsOldImport(_ImportCase):
    def test_a_new_name_supersedes_the_event_on_the_old_key(self):
        a = self.store("acct")
        p = self.note(a, "f.md", "old-name", "the text", "body")
        self.run_import(a)
        [old] = self.inbox()
        p.write_text(note_text("new-name", "the text", "body"), encoding="utf-8")
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        [new] = self.on_key("memory/new-name")
        self.assertEqual([old["id"]], new["supersedes"])
        self.assertEqual(1, rep["counts"]["superseded"])
        self.assertEqual([new["id"]], [h["id"] for h in self.query("the text")])
        _, rep3 = self.run_import(a)
        self.assertEqual(1, rep3["counts"]["unchanged"])


class TheHomeInAProjectFolderWithPunctuation(_ImportCase):
    def test_an_account_name_with_a_dot_is_hidden_in_the_label(self):
        home = "C:" + BACKSLASH + "Users" + BACKSLASH + "john.smith"
        d = self.root / "roots" / "acct" / "projects" / "C--Users-john-smith-Code-X" / "memory"
        d.mkdir(parents=True)
        self.note(d, "x.md", "x", "x")
        r, rep = self.run_import(d, extra=("-HomeDir", home))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("acct/~-Code-X", rep["stores"][0]["label"])
        self.assertNotIn("john", self.inbox()[0]["evidence"])


class ARetiredKeyStaysRetiredUntilANewerNoteChanges(_ImportCase):
    def retire(self, key: str) -> None:
        r = w.run(self.pwsh, w.WRITE, "-Type", "retire", "-Key", key, "-Summary", "withdrawn",
                  "-Evidence", "owner ruling 2026-09-23", "-Seat", "manager", "-StateRoot", str(self.state))
        self.assertEqual(0, r.returncode, r.stderr)

    def test_a_note_that_loses_the_key_does_not_bring_it_back(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "gone", "a says this")
        self.run_import(a)
        self.retire("memory/gone")
        self.note(b, "n.md", "gone", "b says that")
        _, rep = self.run_import(a, b)
        self.assertEqual((0, 1), (rep["counts"]["imported"], rep["counts"]["outranked"]))
        self.assertEqual([], self.live_on("memory/gone", "says"))

    def test_control_a_newer_changed_note_on_a_retired_key_is_written(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        pa = self.note(a, "n.md", "gone", "a says this")
        self.run_import(a)
        self.retire("memory/gone")
        set_modified(pa, day_ago(2))
        self.note(b, "n.md", "gone", "b says that")
        _, rep = self.run_import(a, b)
        self.assertEqual(1, rep["counts"]["imported"])
        self.assertEqual(["b says that"], [h["summary"] for h in self.live_on("memory/gone", "says")])


class EachMergedStoreHasItsOwnRecord(_ImportCase):
    def test_three_stores_give_two_merge_records_on_two_keys(self):
        """On one key, the newer merge record hid the older from a default query."""
        stores = [self.store(f"acct-{c}") for c in "abc"]
        for s in stores:
            self.note(s, "n.md", "trio", "same text", "same body")
        _, rep = self.run_import(*stores)
        self.assertEqual((1, 2), (rep["counts"]["imported"], rep["counts"]["merged"]))
        keys = sorted(e["key"] for e in self.under("memory-merge/trio/"))
        self.assertEqual(["memory-merge/trio/acct-b-proj", "memory-merge/trio/acct-c-proj"], keys)


class EachEventCarriesItsNoteDate(_ImportCase):
    def test_noted_is_the_file_day_and_ts_is_still_the_write(self):
        a = self.store("acct")
        p = self.note(a, "old.md", "old-lesson", "an old lesson about calendars")
        set_modified(p, day_ago(85))
        r, _ = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        [ev] = self.inbox()
        self.assertEqual(day_ago(85), ev["noted"])
        self.assertEqual(day_ago(0), ev["ts"][:10], "ts is the write clock (FR-004), never the note's date")
        [hit] = self.query("old lesson calendars")
        self.assertEqual((day_ago(85), day_ago(85)), (hit["date"], hit["noted"]))

    def test_a_future_file_date_is_read_as_today_and_counted(self):
        a = self.store("acct")
        p = self.note(a, "f.md", "future", "dated ahead of the clock")
        set_modified(p, day_ago(-30))
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(day_ago(0), self.inbox()[0]["noted"])
        self.assertEqual(1, rep["counts"]["future_date_capped"])
        # CONTROL: a past date is not counted.
        set_modified(p, day_ago(3))
        _, rep2 = self.run_import(a)
        self.assertEqual(0, rep2["counts"]["future_date_capped"])


class OneKeyHoldsTheNewestNote(_ImportCase):
    """Two stores holding one name with two texts reconcile to ONE live event, the newer note's."""

    def pair(self, a_day: int, b_day: int):
        a, b = self.store("acct-a"), self.store("acct-b")
        set_modified(self.note(a, "n.md", "split", "store a says the gate reads main"), day_ago(a_day))
        set_modified(self.note(b, "n.md", "split", "store b says the gate reads the merge base"), day_ago(b_day))
        return a, b

    def fresh_state(self, name: str) -> None:
        self.state = self.root / name
        self.state.mkdir()

    def test_the_newer_note_wins_whichever_store_is_named_first(self):
        a, b = self.pair(40, 5)
        for order, state in (((a, b), "state"), ((b, a), "state-reversed")):
            with self.subTest(order=state):
                if state != "state":
                    self.fresh_state(state)
                r, rep = self.run_import(*order)
                self.assertEqual(0, r.returncode, r.stderr)
                [ev] = self.on_key("memory/split")
                self.assertEqual(("memory:acct-b/proj/n.md", day_ago(5)), (ev["evidence"], ev["noted"]))
                [rec] = self.under("memory-merge/split/")
                self.assertIn(f"outranked: acct-b/proj {day_ago(5)}", rec["body"])
                self.assertIn("merged: memory:acct-a/proj/n.md", rec["body"])
                self.assertEqual((1, 1), (rep["counts"]["imported"], rep["counts"]["outranked"]))
                self.assertEqual([], self.lint_conflicts())

    def test_a_tie_goes_to_the_store_named_first(self):
        a, b = self.pair(3, 3)
        self.run_import(a, b)
        self.assertEqual(["memory:acct-a/proj/n.md"], [e["evidence"] for e in self.on_key("memory/split")])
        # CONTROL: the other order, over a fresh inbox, keeps the other note.
        self.fresh_state("state-reversed")
        self.run_import(b, a)
        self.assertEqual(["memory:acct-b/proj/n.md"], [e["evidence"] for e in self.on_key("memory/split")])

    def test_an_older_note_edited_but_still_older_changes_nothing_live(self):
        a, b = self.pair(40, 5)
        self.run_import(a, b)
        [live] = self.on_key("memory/split")
        p = a / "n.md"
        p.write_text(note_text("split", "store a now says something else", "The body."), encoding="utf-8")
        set_modified(p, day_ago(30))
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual([live["id"]], [e["id"] for e in self.on_key("memory/split")])
        self.assertEqual((0, 0, 1), (rep["counts"]["imported"], rep["counts"]["superseded"], rep["counts"]["outranked"]))
        self.assertEqual(2, len(self.under("memory-merge/split/")), "the edited text was not recorded")

    def test_an_older_note_edited_to_be_newest_supersedes(self):
        a, b = self.pair(40, 5)
        self.run_import(a, b)
        [old] = self.on_key("memory/split")
        (a / "n.md").write_text(note_text("split", "store a now says the gate reads the tree", "The body."), encoding="utf-8")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, rep["counts"]["superseded"])
        [new] = [e for e in self.on_key("memory/split") if e["id"] != old["id"]]
        self.assertEqual([old["id"]], new["supersedes"])
        self.assertEqual([new["id"]], [h["id"] for h in self.live_on("memory/split", "store says gate reads")])
        self.assertEqual([], self.lint_conflicts())
        # b's text, now outranked, is recorded once.
        self.assertEqual(1, len([e for e in self.under("memory-merge/split/acct-b") if "outranked" in e["body"]]))

    def test_a_moved_date_alone_writes_nothing(self):
        a, b = self.pair(40, 5)
        self.run_import(a, b)
        before = sorted(p.name for p in w.inbox_dir(self.state).iterdir())
        # The outranked note is now the newest by date, and the winner is touched too.
        set_modified(a / "n.md", day_ago(0))
        set_modified(b / "n.md", day_ago(1))
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(before, sorted(p.name for p in w.inbox_dir(self.state).iterdir()))
        self.assertEqual(2, rep["counts"]["unchanged"])

    def test_every_record_is_written_once(self):
        a, b, c = self.store("acct-a"), self.store("acct-b"), self.store("acct-c")
        set_modified(self.note(a, "n.md", "trio", "a says one thing"), day_ago(30))
        set_modified(self.note(b, "n.md", "trio", "b says another"), day_ago(2))
        set_modified(self.note(c, "n.md", "trio", "b says another"), day_ago(9))
        _, rep = self.run_import(a, b, c)
        self.assertEqual((1, 1, 1), (rep["counts"]["imported"], rep["counts"]["outranked"], rep["counts"]["merged"]))
        before = sorted(p.name for p in w.inbox_dir(self.state).iterdir())
        self.assertEqual(3, len(before))
        _, rep2 = self.run_import(a, b, c)
        self.assertEqual(before, sorted(p.name for p in w.inbox_dir(self.state).iterdir()))
        self.assertEqual(3, rep2["counts"]["unchanged"])


class ASeatsEventIsNotTheImports(_ImportCase):
    def seat_write(self, key: str, summary: str) -> str:
        r = w.run(self.pwsh, w.WRITE, "-Type", "correction", "-Key", key, "-Summary", summary,
                  "-Evidence", "2aec304", "-Seat", "builder", "-StateRoot", str(self.state))
        self.assertEqual(0, r.returncode, r.stderr)
        return r.stdout.strip()

    def test_a_seat_event_newer_than_the_note_is_left_alone(self):
        seat_id = self.seat_write("memory/gate", "the seat measured the gate reading origin")
        a = self.store("acct")
        set_modified(self.note(a, "g.md", "gate", "the note says the gate reads main"), day_ago(10))
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, rep["counts"]["seat_held"])
        self.assertEqual([seat_id], [e["id"] for e in self.on_key("memory/gate")])
        _, rep2 = self.run_import(a)
        self.assertEqual([seat_id], [e["id"] for e in self.on_key("memory/gate")], "a re-run wrote over the seat")

    def test_control_a_note_newer_than_the_seat_event_is_written_and_supersedes_nothing(self):
        seat = w.plant(w.inbox_dir(self.state), when=w.days_ago(20), key="memory/gate", seat="builder",
                       type="correction", summary="the seat measured the gate reading origin")
        a = self.store("acct")
        set_modified(self.note(a, "g.md", "gate", "the note says the gate reads main"), day_ago(2))
        _, rep = self.run_import(a)
        self.assertEqual((1, 1), (rep["counts"]["imported"], rep["counts"]["over_seat"]))
        [mine] = [e for e in self.on_key("memory/gate") if e["seat"] == "import"]
        self.assertNotIn("supersedes", mine, "the import superseded a seat's event")
        self.assertEqual([seat["id"]], [f["events"][0] for f in self.lint_conflicts()], "lint did not file the pair")

    def test_a_seat_event_citing_a_memory_note_is_not_the_imports_to_supersede(self):
        """Its evidence names the note, but a seat wrote it, so it is the seat's word."""
        a = self.store("acct")
        p = self.note(a, "g.md", "gate", "the gate reads main", "The body.")
        set_modified(p, day_ago(2))
        seat = w.plant(w.inbox_dir(self.state), when=w.days_ago(20), key="memory/gate", seat="builder",
                       summary="the seat says the gate reads origin", evidence="memory:acct/proj/g.md")
        _, rep = self.run_import(a)
        self.assertEqual(1, rep["counts"]["imported"])
        [mine] = [e for e in self.on_key("memory/gate") if e["seat"] == "import"]
        self.assertNotIn("supersedes", mine, "a seat's event was taken for the import's own")
        self.assertEqual([seat["id"]], [f["events"][0] for f in self.lint_conflicts()])


class ARenameMovesTheKey(_ImportCase):
    def test_a_shared_old_key_keeps_the_other_stores_note_live(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        pa = self.note(a, "n.md", "old-name", "shared text", "body")
        self.note(b, "n.md", "old-name", "shared text", "body")
        self.run_import(a, b)
        [old] = self.on_key("memory/old-name")
        pa.write_text(note_text("new-name", "shared text", "body"), encoding="utf-8")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        [moved] = self.on_key("memory/new-name")
        self.assertEqual([old["id"]], moved["supersedes"])
        self.assertEqual(["memory:acct-b/proj/n.md"], [h["evidence"] for h in self.live_on("memory/old-name", "shared text")])
        before = len(self.inbox())
        _, rep2 = self.run_import(a, b)
        self.assertEqual(before, len(self.inbox()), "a re-run after the rename wrote again")

    def test_a_rename_onto_a_seat_held_key_retires_the_old_name_with_a_marker(self):
        a = self.store("acct")
        p = self.note(a, "n.md", "old-name", "a lesson", "body")
        set_modified(p, day_ago(10))
        self.run_import(a)
        [old] = self.on_key("memory/old-name")
        r = w.run(self.pwsh, w.WRITE, "-Type", "lesson", "-Key", "memory/new-name", "-Summary", "a seat's lesson",
                  "-Evidence", "2aec304", "-Seat", "builder", "-StateRoot", str(self.state))
        self.assertEqual(0, r.returncode, r.stderr)
        p.write_text(note_text("new-name", "a lesson", "body"), encoding="utf-8")
        set_modified(p, day_ago(10))
        _, rep = self.run_import(a)
        self.assertEqual((1, 1), (rep["counts"]["renamed"], rep["counts"]["seat_held"]))
        [marker] = [e for e in self.on_key("memory/old-name") if e["type"] == "supersede"]
        self.assertEqual([old["id"]], marker["supersedes"])
        self.assertEqual([], self.live_on("memory/old-name", "lesson"))
        before = len(self.inbox())
        self.run_import(a)
        self.assertEqual(before, len(self.inbox()))


class TheReviewCases(_ImportCase):
    """Round-one review of the reconcile, 2026-09-26. Each case failed before its fix."""

    def test_an_older_note_from_a_store_named_later_does_not_replace_a_newer_live_one(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        set_modified(self.note(a, "n.md", "late", "text aye"), day_ago(5))
        self.run_import(a)
        [held] = self.on_key("memory/late")
        set_modified(self.note(b, "n.md", "late", "text bee"), day_ago(30))
        _, rep = self.run_import(b)
        self.assertEqual((0, 0, 1), (rep["counts"]["imported"], rep["counts"]["superseded"], rep["counts"]["outranked"]))
        self.assertEqual([held["id"]], [h["id"] for h in self.live_on("memory/late", "text")])

    def test_a_note_renamed_back_to_its_first_key_is_live_there(self):
        a = self.store("acct")
        p = self.note(a, "n.md", "first", "a lesson that moves", "body")
        self.run_import(a)
        p.write_text(note_text("second", "a lesson that moves", "body"), encoding="utf-8")
        self.run_import(a)
        p.write_text(note_text("first", "a lesson that moves", "body"), encoding="utf-8")
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, rep["counts"]["superseded"])
        self.assertEqual(["memory/first"], [h["key"] for h in self.query("lesson that moves")])

    def test_an_edit_to_the_note_behind_the_kept_event_hands_the_key_to_the_winner(self):
        """Round two: the event had cited a note that no longer says its text."""
        a, b = self.store("acct-a"), self.store("acct-b")
        pa = self.note(a, "n.md", "tee", "text tee", "body")
        set_modified(pa, day_ago(10))
        self.run_import(a)
        set_modified(self.note(b, "n.md", "tee", "text tee", "body"), day_ago(0))
        pa.write_text(note_text("tee", "text tee two", "body"), encoding="utf-8")
        set_modified(pa, day_ago(5))
        _, rep = self.run_import(a, b)
        self.assertEqual((1, 1, 0), (rep["counts"]["superseded"], rep["counts"]["outranked"], rep["counts"]["merged"]))
        [live] = self.live_on("memory/tee", "text tee")
        self.assertEqual("memory:acct-b/proj/n.md", live["evidence"])
        [rec] = [e for e in self.under("memory-merge/tee/acct-a") if "outranked" in e["body"]]
        self.assertIn(f"outranked: acct-b/proj {day_ago(0)}", rec["body"])
        _, rep2 = self.run_import(a, b)
        self.assertEqual(2, rep2["counts"]["unchanged"])
        # A run naming the outranked store alone changes nothing either.
        _, rep3 = self.run_import(a)
        self.assertEqual(1, rep3["counts"]["unchanged"])

    def test_a_merge_into_an_event_this_run_replaces_is_recorded_again(self):
        a, b, c = self.store("acct-a"), self.store("acct-b"), self.store("acct-c")
        set_modified(self.note(a, "n.md", "tee", "text tee", "body"), day_ago(5))
        set_modified(self.note(b, "n.md", "tee", "text tee", "body"), day_ago(9))
        self.run_import(a, b)
        self.note(c, "n.md", "tee", "text cee", "body")
        _, rep = self.run_import(a, b, c)
        self.assertEqual((1, 2), (rep["counts"]["superseded"], rep["counts"]["outranked"]))
        newest_b = [e for e in self.under("memory-merge/tee/acct-b")][-1]
        self.assertIn("outranked: acct-c/proj", newest_b["body"])

class TheRoundTwoCases(_ImportCase):
    """Round-two review of the reconcile, 2026-09-26. Each case failed before its fix."""

    def test_a_rename_into_a_retired_key_does_not_bring_back_the_winners_text(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        set_modified(self.note(a, "w.md", "kay", "wee text retired", "body"), day_ago(3))
        pb = self.note(b, "o.md", "other", "a different lesson", "body")
        set_modified(pb, day_ago(3))
        self.run_import(a, b)
        r = w.run(self.pwsh, w.WRITE, "-Type", "retire", "-Key", "memory/kay", "-Summary", "withdrawn",
                  "-Evidence", "owner ruling 2026-09-23", "-Seat", "manager", "-StateRoot", str(self.state))
        self.assertEqual(0, r.returncode, r.stderr)
        pb.write_text(note_text("kay", "a different lesson", "body"), encoding="utf-8")
        set_modified(pb, day_ago(3))
        self.run_import(a, b)
        self.assertEqual([], self.live_on("memory/kay", "wee text retired"))

    def test_a_tie_with_a_holder_whose_note_moved_on_goes_to_the_first_store(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        pa = self.note(a, "n.md", "tie", "text one", "body")
        self.run_import(a)
        pa.write_text(note_text("tie", "text two", "body"), encoding="utf-8")
        self.note(b, "n.md", "tie", "text bee", "body")
        _, rep = self.run_import(b, a)
        self.assertEqual(1, rep["counts"]["superseded"])
        self.assertEqual(["text bee"], [h["summary"] for h in self.live_on("memory/tie", "text")])

    def test_a_merge_record_naming_a_renamed_holder_is_recorded_again(self):
        a, b, c = self.store("acct-a"), self.store("acct-b"), self.store("acct-c")
        pa = self.note(a, "n.md", "kay", "same text", "body")
        set_modified(pa, day_ago(1))
        set_modified(self.note(b, "n.md", "kay", "same text", "body"), day_ago(5))
        set_modified(self.note(c, "n.md", "kay", "same text", "body"), day_ago(9))
        self.run_import(a, b, c)
        pa.write_text(note_text("kay-two", "same text", "body"), encoding="utf-8")
        set_modified(pa, day_ago(1))
        _, rep = self.run_import(a, b, c)
        self.assertEqual(["memory:acct-b/proj/n.md"], [h["evidence"] for h in self.live_on("memory/kay", "same text")])
        newest_c = self.under("memory-merge/kay/acct-c")[-1]
        self.assertIn("kept: memory:acct-b/proj/n.md", newest_c["body"])

if __name__ == "__main__":
    unittest.main()
