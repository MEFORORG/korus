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
import re
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _wikitest as w

IMPORT = w.WIKI / "import.ps1"
LINT = w.WIKI / "lint.ps1"
BACKSLASH = chr(92)
DATE_LINE = re.compile(r"\ASource note last modified: (\d{4}-\d{2}-\d{2})\.(?:\n\n|\Z)")


def set_modified(path: Path, day: str) -> None:
    """Give a note file a chosen last-write date, at noon UTC so no time zone moves the day."""
    when = datetime.strptime(day + " 12:00", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
    os.utime(path, (when, when))


def note_date(event: dict) -> str | None:
    """The date an imported event's body opens with, or None when it carries none."""
    m = DATE_LINE.match(event.get("body", ""))
    return m.group(1) if m else None


def note_body(event: dict) -> str:
    """An imported event's body without its date line: the note's own text."""
    return DATE_LINE.sub("", event.get("body", ""), count=1)


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
             mtype: str | None = "feedback", modified: str | None = None) -> Path:
        p = store / file
        p.write_text(note_text(name, description, body, mtype), encoding="utf-8")
        if modified:
            set_modified(p, modified)
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

    def query(self, text: str, *extra: str) -> list[dict]:
        r = w.run(self.pwsh, w.QUERY, "-Text", text, "-StateRoot", str(self.state), "-Json", *extra)
        self.assertEqual(0, r.returncode, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else []

    def conflict_keys(self) -> list[str]:
        """The keys lint files a conflict on, read from lint's own report."""
        r = w.run(self.pwsh, LINT, "-StateRoot", str(self.state), "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        return sorted(f["id"].split(":", 1)[1] for f in json.loads(r.stdout)["findings"] if f["class"] == "conflict")

    def live_on(self, key: str, words: str) -> list[dict]:
        """What a default query returns on one key: the guard's live set there."""
        return [h for h in self.query(words) if h["key"] == key]


class OneNoteBecomesOneEvent(_ImportCase):
    def test_the_fields_map_as_documented(self):
        a = self.store(".claude-account-3")
        self.note(a, "shaped.md", "Shaped Lesson_One", "Retire by key, never by text", "Why it matters.\n\nDetail.",
                  modified="2026-07-12")
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        [ev] = self.inbox()
        self.assertEqual("memory/shaped-lesson-one", ev["key"])
        self.assertEqual("lesson", ev["type"])
        self.assertEqual("Retire by key, never by text", ev["summary"])
        self.assertEqual("Source note last modified: 2026-07-12.\n\nWhy it matters.\n\nDetail.", ev["body"])
        self.assertEqual("2026-08-26", ev["stale_after"])
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
        self.assertEqual("body", note_body(got["memory/single"]), "a CRLF note kept its carriage returns")
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
        self.assertTrue(note_body(got["memory/long"]).startswith("Description: " + long_desc.strip()))
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
        kept_line, merged_line, text_line, date_line = merge["body"].split("\n")
        self.assertEqual("kept: memory:acct-a/proj/n.md", kept_line)
        self.assertEqual("merged: memory:acct-b/proj/n.md", merged_line)
        self.assertRegex(text_line, r"^text: sha256:[0-9a-f]{64}$")
        self.assertEqual("date: " + note_date(kept), date_line)
        self.assertEqual((1, 1), (rep["counts"]["imported"], rep["counts"]["merged"]))

    def test_same_name_different_text_and_one_date_keeps_both_and_supersedes_neither(self):
        """Story 4 scenario 2: with no date to rank them by, both are kept, and lint files the pair."""
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "split-lesson", "store a says this", modified="2026-08-01")
        self.note(b, "n.md", "split-lesson", "store b says that", modified="2026-08-01")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        both = self.on_key("memory/split-lesson")
        self.assertEqual(2, len(both))
        self.assertTrue(all("supersedes" not in e for e in both), "a different store's note superseded another")
        self.assertEqual([], self.under("memory-merge/split-lesson/"))
        self.assertEqual([], self.under("memory-held/split-lesson/"))
        self.assertEqual(1, rep["counts"]["conflicts"])
        self.assertEqual(["memory/split-lesson"], self.conflict_keys())


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
        self.assertEqual("~" + BACKSLASH + "proj" + BACKSLASH + "a.txt", note_body(ev).splitlines()[0])
        self.assertEqual(["~/proj/b.txt", "~/proj/c.txt", "~"], note_body(ev).splitlines()[1:])
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
        self.assertTrue(note_body(ev).startswith("~"), "the current user's home was not normalised by default")


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
        self.assertEqual({"memory:acct/one/x.md", "memory:acct/two/x.md"},
                         {e["evidence"] for e in self.on_key("memory/same-name")})
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
    def test_a_note_matching_only_a_superseded_event_is_written(self):
        """Rule 2 compares with CURRENT events. Matched against a replaced one, the third store's note
        counted as merged, then as unchanged on every run, and never reached the wiki."""
        a, b = self.store("acct-a"), self.store("acct-b")
        p = self.note(a, "n.md", "moving", "the first wording", "body")
        self.run_import(a)
        p.write_text(note_text("moving", "the second wording", "body"), encoding="utf-8")
        self.run_import(a)
        self.note(b, "n.md", "moving", "the first wording", "body")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((1, 0), (rep["counts"]["imported"], rep["counts"]["merged"]))
        self.assertEqual(["memory:acct-b/proj/n.md"],
                         [e["evidence"] for e in self.on_key("memory/moving") if "supersedes" not in e and
                          e["evidence"].startswith("memory:acct-b")])

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

    def test_a_merged_note_that_changes_is_imported_again(self):
        """CONTROL for the two above: the skip is keyed on the merged note's text, not on its name."""
        a, b = self.shared_pair()
        self.note(b, "foo.md", "foo", "text b now says", "body")
        _, rep = self.run_import(a, b)
        self.assertEqual(1, rep["counts"]["imported"])


class ASupersedeInThisRunCountsForThisRun(_ImportCase):
    def test_a_note_holding_the_text_this_run_replaces_is_not_merged_into_it(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        pa = self.note(a, "n.md", "moving", "old text", "body")
        self.run_import(a)
        pa.write_text(note_text("moving", "new text", "body"), encoding="utf-8")
        self.note(b, "n.md", "moving", "old text", "body")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((1, 1, 0), (rep["counts"]["superseded"], rep["counts"]["imported"], rep["counts"]["merged"]))
        self.assertEqual([], self.under("memory-merge/"), "a merge record points at the text this run replaced")
        _, rep3 = self.run_import(a, b)
        self.assertEqual(2, rep3["counts"]["unchanged"])

    def test_both_stores_start_equal_then_one_edits(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        pa = self.note(a, "n.md", "moving", "old text", "body")
        self.note(b, "n.md", "moving", "old text", "body")
        self.run_import(a, b)
        pa.write_text(note_text("moving", "new text", "body"), encoding="utf-8")
        _, rep2 = self.run_import(a, b)
        self.assertEqual((1, 1), (rep2["counts"]["superseded"], rep2["counts"]["unchanged"]))
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


class ConflictsCountOnlyCurrentText(_ImportCase):
    def test_a_withdrawn_event_is_not_a_conflict(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "gone", "a says this")
        self.run_import(a)
        r = w.run(self.pwsh, w.WRITE, "-Type", "retire", "-Key", "memory/gone", "-Summary", "withdrawn",
                  "-Evidence", "owner ruling 2026-09-23", "-Seat", "manager", "-StateRoot", str(self.state))
        self.assertEqual(0, r.returncode, r.stderr)
        self.note(b, "n.md", "gone", "b says that")
        _, rep = self.run_import(a, b)
        self.assertEqual((1, 0), (rep["counts"]["imported"], rep["counts"]["conflicts"]))

    def test_control_a_current_different_text_is_a_conflict(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "here", "a says this")
        self.run_import(a)
        self.note(b, "n.md", "here", "b says that")
        _, rep = self.run_import(a, b)
        self.assertEqual((1, 1), (rep["counts"]["imported"], rep["counts"]["conflicts"]))


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


class EachEventCarriesItsNotesDate(_ImportCase):
    """`ts` is the write clock (FR-004), so one run stamps every note with one time. The note's own
    date rides in the body's first line and in `stale_after`, which the readers already honour."""

    def test_the_date_line_and_stale_after_come_from_the_file(self):
        a = self.store("acct")
        self.note(a, "old.md", "old-billing", "billing was resolved long ago", modified="2025-01-10")
        self.note(a, "new.md", "new-billing", "billing was resolved just now")
        before = datetime.now(timezone.utc)
        r, _ = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        got = {e["key"]: e for e in self.inbox()}
        old = got["memory/old-billing"]
        self.assertEqual("2025-01-10", note_date(old))
        self.assertEqual("2025-02-24", old["stale_after"])
        # FR-004 holds: ts is still the write clock, not the note's date.
        ts = datetime.strptime(old["ts"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        self.assertGreater(ts, before.replace(microsecond=0) - timedelta(seconds=5))
        labels = {h["key"]: h["label"] for h in self.query("billing resolved")}
        self.assertEqual("stale", labels["memory/old-billing"])
        # CONTROL: a note written today is not stale, so the label above came from the date.
        self.assertEqual("inbox", labels["memory/new-billing"])

    def test_a_note_whose_date_moved_and_text_did_not_is_unchanged(self):
        a = self.store("acct")
        p = self.note(a, "n.md", "touched", "the same words", modified="2026-06-01")
        self.run_import(a)
        before = sorted(x.name for x in w.inbox_dir(self.state).iterdir())
        set_modified(p, "2026-09-01")
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, rep["counts"]["unchanged"])
        self.assertEqual(before, sorted(x.name for x in w.inbox_dir(self.state).iterdir()))
        # CONTROL: an edit of the text is seen, and the new event carries the new date.
        p.write_text(note_text("touched", "other words now", "The body."), encoding="utf-8")
        set_modified(p, "2026-09-02")
        _, rep2 = self.run_import(a)
        self.assertEqual(1, rep2["counts"]["superseded"])
        self.assertEqual({"2026-06-01", "2026-09-02"}, {note_date(e) for e in self.on_key("memory/touched")})


class TheNewestNoteWinsInOneRun(_ImportCase):
    def test_the_newer_note_is_live_whatever_order_the_stores_were_named_in(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "billing", "billing is still broken", modified="2026-07-01")
        self.note(b, "n.md", "billing", "billing was fixed", modified="2026-09-01")
        # acct-b is named FIRST: under read order it would lose to acct-a, read later.
        r, rep = self.run_import(b, a)
        self.assertEqual(0, r.returncode, r.stderr)
        live = self.live_on("memory/billing", "billing")
        self.assertEqual(["memory:acct-b/proj/n.md"], [h["evidence"] for h in live])
        self.assertEqual([], self.conflict_keys())
        self.assertEqual((1, 1, 0), (rep["counts"]["imported"], rep["counts"]["held"], rep["counts"]["conflicts"]))
        self.assertEqual([{"note": "acct-a/proj/n.md", "behind": "acct-b/proj/n.md"}], rep["held_notes"])
        # The older note is not an event on the key; a decision records the hold.
        self.assertEqual(["memory:acct-b/proj/n.md"], [e["evidence"] for e in self.on_key("memory/billing")])
        [held] = self.under("memory-held/billing/")
        self.assertEqual("decision", held["type"])
        self.assertEqual("memory:acct-a/proj/n.md", held["evidence"])
        lines = held["body"].split("\n")
        self.assertEqual(["kept: memory:acct-b/proj/n.md", "held: memory:acct-a/proj/n.md"], lines[:2])
        self.assertEqual("date: 2026-07-01", lines[3])
        # A re-run over unchanged stores writes nothing.
        before = sorted(x.name for x in w.inbox_dir(self.state).iterdir())
        _, rep2 = self.run_import(a, b)
        self.assertEqual(before, sorted(x.name for x in w.inbox_dir(self.state).iterdir()))
        self.assertEqual(2, rep2["counts"]["unchanged"])

    def test_control_one_date_leaves_the_pair_for_lint_and_the_later_label_live(self):
        """The tie keeps both. The later store label is written last, in its own batch, so it is the
        one a reader sees, whichever order -Store named the stores in."""
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "billing", "billing is still broken", modified="2026-09-01")
        self.note(b, "n.md", "billing", "billing was fixed", modified="2026-09-01")
        r, rep = self.run_import(b, a)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(["memory/billing"], self.conflict_keys())
        self.assertEqual(["memory:acct-b/proj/n.md"], [h["evidence"] for h in self.live_on("memory/billing", "billing")])
        self.assertEqual(0, rep["counts"]["held"])


class TheNewestNoteWinsAcrossRuns(_ImportCase):
    def test_an_older_note_arriving_later_is_held_and_never_live(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(b, "n.md", "billing", "billing was fixed", modified="2026-09-01")
        self.run_import(b)
        self.note(a, "n.md", "billing", "billing is still broken", modified="2026-07-01")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((0, 1), (rep["counts"]["imported"], rep["counts"]["held"]))
        self.assertEqual(["memory:acct-b/proj/n.md"], [h["evidence"] for h in self.live_on("memory/billing", "billing")])
        self.assertEqual(["memory:acct-b/proj/n.md"], [e["evidence"] for e in self.on_key("memory/billing")])
        self.assertEqual(1, len(self.under("memory-held/billing/")))
        self.assertEqual([], self.conflict_keys())
        before = len(self.inbox())
        _, rep2 = self.run_import(a, b)
        self.assertEqual(before, len(self.inbox()), "a re-run wrote the held note again")
        self.assertEqual(2, rep2["counts"]["unchanged"])

    def test_a_newer_note_arriving_later_supersedes_the_older_event(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(a, "n.md", "billing", "billing is still broken", modified="2026-07-01")
        self.run_import(a)
        [old] = self.inbox()
        self.note(b, "n.md", "billing", "billing was fixed", modified="2026-09-01")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        [new] = [e for e in self.on_key("memory/billing") if e["id"] != old["id"]]
        self.assertEqual([old["id"]], new["supersedes"])
        self.assertEqual((1, 1, 0), (rep["counts"]["imported"], rep["counts"]["older_superseded"], rep["counts"]["conflicts"]))
        self.assertEqual([new["id"]], [h["id"] for h in self.live_on("memory/billing", "billing")])
        self.assertEqual([], self.conflict_keys())
        _, rep2 = self.run_import(a, b)
        self.assertEqual(2, rep2["counts"]["unchanged"])
        self.assertEqual(2, len(self.inbox()))

    def test_an_event_imported_without_a_date_counts_as_older(self):
        """Events imported before notes carried a date have no date line. Any dated note outranks one."""
        a = self.store("acct-a")
        legacy = w.plant(w.inbox_dir(self.state), type="lesson", key="memory/billing", seat="import",
                         summary="billing is still broken", body="The body.", evidence="memory:acct-b/proj/n.md")
        self.note(a, "n.md", "billing", "billing was fixed", modified="2025-01-01")
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        [new] = [e for e in self.on_key("memory/billing") if e["id"] != legacy["id"]]
        self.assertEqual([legacy["id"]], new["supersedes"])
        self.assertEqual(1, rep["counts"]["older_superseded"])

    def test_a_held_note_edited_to_be_newest_is_written_and_retires_its_hold(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(b, "n.md", "billing", "billing was fixed", modified="2026-09-01")
        pa = self.note(a, "n.md", "billing", "billing is still broken", modified="2026-07-01")
        self.run_import(a, b)
        [held] = self.under("memory-held/billing/")
        [kept] = self.on_key("memory/billing")
        pa.write_text(note_text("billing", "billing broke again", "The body."), encoding="utf-8")
        set_modified(pa, "2026-09-10")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        [new] = [e for e in self.on_key("memory/billing") if e["id"] != kept["id"]]
        self.assertEqual({kept["id"], held["id"]}, set(new["supersedes"]))
        self.assertEqual([new["id"]], [h["id"] for h in self.live_on("memory/billing", "billing")])
        hist = {h["id"]: h["label"] for h in self.query("held memory note billing", "-History")}
        self.assertEqual("historical", hist.get(held["id"]))
        _, rep2 = self.run_import(a, b)
        self.assertEqual(2, rep2["counts"]["unchanged"])


class WhatCountsAsADate(_ImportCase):
    def test_a_seat_event_on_a_memory_key_ranks_by_the_day_it_was_written(self):
        """Only this script's own undated events count as older than every note. An Owner's ruling
        on a memory key is dated by its write, so a two-year-old note cannot withdraw it."""
        a = self.store("acct-a")
        ruling = w.plant(w.inbox_dir(self.state), type="decision", key="memory/billing", seat="manager",
                         summary="billing is owned by finance", evidence="owner ruling 2026-09-20")
        self.note(a, "n.md", "billing", "billing is owned by nobody", modified="2024-01-01")
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((0, 1, 0), (rep["counts"]["imported"], rep["counts"]["held"], rep["counts"]["older_superseded"]))
        self.assertEqual([ruling["id"]], [h["id"] for h in self.live_on("memory/billing", "billing owned")])

    def test_an_unchanged_note_dates_its_own_undated_import(self):
        """An event imported before notes carried a date is dated by its note, when that note is in
        the run and unchanged, so an old note from another store does not outrank it."""
        a, b = self.store("acct-a"), self.store("acct-b")
        legacy = w.plant(w.inbox_dir(self.state), type="lesson", key="memory/billing", seat="import",
                         summary="billing was fixed", body="The body.", evidence="memory:acct-a/proj/n.md")
        self.note(a, "n.md", "billing", "billing was fixed", modified="2026-09-20")
        self.note(b, "n.md", "billing", "billing is still broken", modified="2025-01-01")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((1, 1, 0), (rep["counts"]["unchanged"], rep["counts"]["held"], rep["counts"]["older_superseded"]))
        self.assertEqual([legacy["id"]], [h["id"] for h in self.live_on("memory/billing", "billing")])
        # The CONTROL is TheNewestNoteWinsAcrossRuns.test_an_event_imported_without_a_date_counts_as_older:
        # with the event's own store left out of the run, the same shape of event is replaced.

    def test_a_long_note_imported_before_the_date_line_is_unchanged(self):
        """The date line takes room from the body, so a long note is now cut sooner. Its old cut
        still counts as the same text, or every long note would be imported again once."""
        a = self.store("acct")
        marker = "\n\n[truncated at import; the full note is the evidence file]"
        body = "x" * 25000
        w.plant(w.inbox_dir(self.state), type="lesson", key="memory/huge", seat="import", summary="huge body",
                body=body[:20000 - len(marker)] + marker, evidence="memory:acct/proj/huge.md")
        self.note(a, "huge.md", "huge", "huge body", body)
        r, rep = self.run_import(a)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((1, 0), (rep["counts"]["unchanged"], rep["counts"]["superseded"]))
        # CONTROL: an edit of the same note is still seen.
        self.note(a, "huge.md", "huge", "huge body", "y" * 25000)
        _, rep2 = self.run_import(a)
        self.assertEqual(1, rep2["counts"]["superseded"])


class AHoldFollowsTheNote(_ImportCase):
    def test_a_held_note_touched_to_a_newer_date_is_looked_at_again(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(b, "n.md", "billing", "billing was fixed", modified="2026-09-01")
        pa = self.note(a, "n.md", "billing", "billing is still broken", modified="2026-07-01")
        self.run_import(a, b)
        [kept] = self.on_key("memory/billing")
        set_modified(pa, "2026-09-10")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((1, 1), (rep["counts"]["imported"], rep["counts"]["older_superseded"]))
        [new] = [e for e in self.on_key("memory/billing") if e["id"] != kept["id"]]
        self.assertEqual("memory:acct-a/proj/n.md", new["evidence"])

    def test_a_second_hold_of_one_note_replaces_the_first(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(b, "n.md", "billing", "billing was fixed", modified="2026-09-01")
        pa = self.note(a, "n.md", "billing", "billing is still broken", modified="2026-07-01")
        self.run_import(a, b)
        [first] = self.under("memory-held/billing/")
        pa.write_text(note_text("billing", "billing is still broken today", "The body."), encoding="utf-8")
        set_modified(pa, "2026-08-01")
        r, rep = self.run_import(a, b)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, rep["counts"]["held"])
        [second] = [e for e in self.under("memory-held/billing/") if e["id"] != first["id"]]
        self.assertEqual([first["id"]], second["supersedes"])
        self.assertEqual([], self.conflict_keys())
        _, rep2 = self.run_import(a, b)
        self.assertEqual(2, rep2["counts"]["unchanged"])

    def test_a_rename_that_is_held_retires_the_old_name(self):
        """The file no longer carries the old name, so its import under that name must not stay live."""
        a, c = self.store("acct-a"), self.store("acct-c")
        pa = self.note(a, "n.md", "billing", "billing is monthly", modified="2026-09-05")
        self.note(c, "n.md", "invoicing", "invoicing is weekly", modified="2026-09-15")
        self.run_import(a, c)
        [old] = self.on_key("memory/billing")
        pa.write_text(note_text("invoicing", "invoicing is monthly", "The body."), encoding="utf-8")
        set_modified(pa, "2026-09-12")
        r, rep = self.run_import(a, c)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, rep["counts"]["held"])
        [held] = self.under("memory-held/invoicing/")
        self.assertEqual([old["id"]], held["supersedes"])
        self.assertEqual([], self.live_on("memory/billing", "billing monthly"))
        self.assertEqual(["memory:acct-c/proj/n.md"], [h["evidence"] for h in self.live_on("memory/invoicing", "invoicing")])
        _, rep2 = self.run_import(a, c)
        self.assertEqual(2, rep2["counts"]["unchanged"])


class ANoteThatNeverLandsOutranksNothing(_ImportCase):
    def test_an_older_note_is_written_when_the_newer_one_is_refused(self):
        a, b = self.store("acct-a"), self.store("acct-b")
        self.note(b, "n.md", "billing", "billing was fixed", f"token {forge_token()} here", modified="2026-09-10")
        self.note(a, "n.md", "billing", "billing is still broken", modified="2026-09-01")
        r, rep = self.run_import(a, b)
        self.assertEqual(1, r.returncode, r.stderr)
        self.assertEqual((1, 1, 0), (rep["counts"]["imported"], rep["counts"]["refused"], rep["counts"]["held"]))
        self.assertEqual(["memory:acct-a/proj/n.md"], [e["evidence"] for e in self.on_key("memory/billing")])

    def test_a_copy_of_a_text_this_run_outranks_is_held_not_merged(self):
        a, b, c = self.store("acct-a"), self.store("acct-b"), self.store("acct-c")
        self.note(a, "n.md", "billing", "billing is monthly", modified="2026-09-01")
        self.run_import(a)
        [old] = self.on_key("memory/billing")
        self.note(c, "n.md", "billing", "billing is monthly", modified="2026-09-03")
        self.note(b, "n.md", "billing", "billing is weekly", modified="2026-09-05")
        r, rep = self.run_import(a, b, c)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual((1, 0, 1, 1), (rep["counts"]["imported"], rep["counts"]["merged"], rep["counts"]["held"],
                                        rep["counts"]["older_superseded"]))
        self.assertEqual([], self.under("memory-merge/billing/"))
        [held] = self.under("memory-held/billing/")
        self.assertEqual("memory:acct-c/proj/n.md", held["evidence"])
        [new] = [e for e in self.on_key("memory/billing") if e["id"] != old["id"]]
        self.assertEqual([old["id"]], new["supersedes"])
        _, rep2 = self.run_import(a, b, c)
        self.assertEqual(3, rep2["counts"]["unchanged"])


if __name__ == "__main__":
    unittest.main()
