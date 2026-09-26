"""`scripts/wiki/compile.ps1` folds the inbox into the record repository. Pin what it may and may not do.

EVERY CASE RUNS THE REAL SCRIPT AGAINST THROWAWAY GIT REPOSITORIES: a bare repository as the remote,
and a clone of it as the record repository. Nothing here reaches a real clone or a real remote, and
`-NoPr` keeps `gh` out of it.

THE REBUILD TEST IS THE ONE THE SPEC NAMES (SC-001, Story 2). Plant A, supersede it with B, compile,
delete every page and the index, rebuild from the log alone, and ask for A by its own words: A must
be absent and B present. An absence cannot tell "the guard hid A" from "the renderer never wrote A",
so the same events are rendered with the guard switched off, through the same library, and A MUST
appear there. Without that control the absence would measure nothing.

"SIMULATE THE MERGE" means fast-forwarding the bare remote's `main` to `wiki/compile`, which is what
a merged pull request leaves behind as far as compile can see: the events are in the log at Base.

Run: python -m pytest tests/test_wiki_compile.py
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import _wikitest as w

COMPILE = w.WIKI / "compile.ps1"
RENDER_LIB = w.WIKI / "_render.ps1"

# THE LEAK HOLD'S STAND-IN SCANNER. The record repository's own scanner and its patterns are private,
# so every case gets this stub at the same path instead. It keeps the real one's contract: `--path
# DIR`, exit 0 clean, 1 on a hit and 2 on a usage error, and each hit on stderr as two spaces, the
# path relative to DIR, then `:<line>:`, and a closing `<n> hit(s).`. Like the real one, its hit
# line ECHOES the token it matched, which is what the "never printed" case needs to be able to fail.
# Two more of the real one's rules are kept because the hold must work around them: a file with a NUL
# in its first 4096 bytes is skipped as binary, and a whole line matching the allowlist is skipped.
# The token and the allowlisted phrase are invented.
LEAK_TOKEN = "ZZLEAKTOKEN"
ALLOWED = "ZZALLOWEDPHRASE"
SCANNER_REL = "scripts/publish/scan_forbidden.py"
_STUB_SCANNER = '''\
import os
import sys
from pathlib import Path

TOKEN = "%s"


def main(argv):
    if len(argv) != 2 or argv[0] != "--path" or not Path(argv[1]).is_dir():
        print("scan_forbidden: --path requires a directory", file=sys.stderr)
        return 2
    root = Path(argv[1])
    files = sorted(p for p in root.rglob("*") if p.is_file())
    calls = os.environ.get("WIKI_TEST_SCANNER_CALLS")
    if calls:
        with open(calls, "a", encoding="ascii") as fh:
            fh.write(" ".join(p.relative_to(root).as_posix() for p in files) + "\\n")
    seen = os.environ.get("WIKI_TEST_SCANNER_CWD")
    if seen:
        with open(seen, "a", encoding="utf-8") as fh:
            fh.write(" ".join(sorted(p.name for p in Path.cwd().iterdir())) + "\\n")
    if not files:
        return 2
    hits = []
    for p in files:
        data = p.read_bytes()
        if b"\\x00" in data[:4096]:
            continue
        for n, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
            if "ZZALLOWEDPHRASE" in line:
                continue
            if TOKEN in line:
                hits.append(f"{p.relative_to(root).as_posix()}:{n}: planted name ({TOKEN}): {line.strip()}")
    if hits:
        print("FORBIDDEN CONTENT -- blocked (fail closed):", file=sys.stderr)
        for h in hits:
            print(f"  {h}", file=sys.stderr)
        print(f"\\n{len(hits)} hit(s).", file=sys.stderr)
        return 1
    return 0


raise SystemExit(main(sys.argv[1:]))
'''


def stub_scanner(token: str = LEAK_TOKEN) -> str:
    return _STUB_SCANNER % token


STUB_SCANNER = stub_scanner()


class _CompileCase(unittest.TestCase):
    def setUp(self):
        self.pwsh = w.find_pwsh_or_skip(self)
        tmp = tempfile.TemporaryDirectory(prefix="wiki-compile-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / "state"
        self.state.mkdir()
        self.inbox = w.inbox_dir(self.state)
        self.remote = self.root / "remote.git"
        w.git(self.root, "init", "--bare", "-b", "main", str(self.remote))
        self.seed = seed = w.make_repo(self.root / "seed", None)
        scanner = seed / SCANNER_REL
        scanner.parent.mkdir(parents=True)
        scanner.write_text(STUB_SCANNER, encoding="ascii")
        w.git(seed, "add", SCANNER_REL)
        w.git(seed, "commit", "-m", "the record repository's leak scanner")
        w.git(seed, "remote", "add", "origin", str(self.remote))
        w.git(seed, "push", "origin", "main")
        self.record = self.root / "record"
        w.git(self.root, "clone", str(self.remote), str(self.record))
        w.git(self.record, "config", "user.email", "t@example.com")
        w.git(self.record, "config", "user.name", "t")

    # -------------------------------------------------------------------------------- helpers
    def compile(self, *extra: str, expect: int = 0) -> dict:
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state), "-RecordRepo", str(self.record),
                  "-NoPr", "-Json", *extra)
        self.assertEqual(expect, r.returncode, f"compile exited {r.returncode}: {r.stderr}\n{r.stdout}")
        return json.loads(r.stdout) if expect == 0 else {"stderr": r.stderr, "stdout": r.stdout}

    def remote_git(self, *args: str) -> str:
        return w.git(self.root, f"--git-dir={self.remote}", *args).stdout

    def remote_sha(self, ref: str) -> str:
        return self.remote_git("rev-parse", ref).strip()

    def remote_has(self, ref: str) -> bool:
        r = subprocess.run(["git", f"--git-dir={self.remote}", "rev-parse", "--verify", "--quiet", ref],
                             capture_output=True, text=True, timeout=w.TIMEOUT_SECONDS)
        return r.returncode == 0

    def show(self, ref: str, path: str) -> str:
        return self.remote_git("show", f"{ref}:{path}")

    def files_at(self, ref: str) -> list[str]:
        return self.remote_git("ls-tree", "-r", "--name-only", ref).split()

    def merge(self):
        """What a merged pull request leaves behind: Base now holds the compiled log."""
        self.remote_git("update-ref", "refs/heads/main", "refs/heads/wiki/compile")

    def checkout_of(self, ref: str, name: str) -> Path:
        """A second, separate clone at `ref`. Never the record clone, whose tree must stay put."""
        path = self.root / name
        w.git(self.root, "clone", "--quiet", "--branch", ref, str(self.remote), str(path))
        return path

    def worktree_count(self) -> int:
        out = w.git(self.record, "worktree", "list", "--porcelain").stdout
        return len([ln for ln in out.splitlines() if ln.startswith("worktree ")])

    def set_scanner(self, text: str | None):
        """Replace the record repository's scanner at Base, or remove it with None."""
        path = self.seed / SCANNER_REL
        if text is None:
            w.git(self.seed, "rm", "--quiet", SCANNER_REL)
        else:
            path.write_text(text, encoding="ascii")
            w.git(self.seed, "add", SCANNER_REL)
        w.git(self.seed, "commit", "-m", "the scanner changes")
        w.git(self.seed, "push", "origin", "main")

    def inbox_snapshot(self) -> dict[str, bytes]:
        return {p.name: p.read_bytes() for p in sorted(self.inbox.glob("*"))}


class CompileFoldsTheInboxIntoTheLog(_CompileCase):
    def setUp(self):
        super().setUp()
        self.a = w.plant(self.inbox, when=w.days_ago(2), key="gate/ascii/windows-exit-code",
                         summary="The ascii gate collapses exit code two to one on windows")
        self.b = w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/fix-mode", stale_after="2099-01-01",
                         summary="The fix mode corrupts vendored templates", evidence="Owner ruling 2026-09-17")
        self.c = w.plant(self.inbox, when=w.days_ago(1), key="git/show/dotpath-msys",
                         summary="git show of a dot path returns empty under MSYS")
        self.result = self.compile()

    def test_it_reports_what_it_did(self):
        self.assertEqual("compiled", self.result["result"])
        self.assertEqual(3, self.result["added"])
        self.assertEqual(2, self.result["pages"])
        self.assertEqual(0, self.result["conflicts"])

    def test_every_event_is_filed_in_the_log_by_its_month(self):
        files = self.files_at("wiki/compile")
        for ev in (self.a, self.b, self.c):
            yyyy, mm = ev["ts"][:4], ev["ts"][5:7]
            self.assertIn(f"wiki/events/{yyyy}/{mm}/{ev['id']}.json", files)
            filed = json.loads(self.show("wiki/compile", f"wiki/events/{yyyy}/{mm}/{ev['id']}.json"))
            self.assertEqual(ev, filed, "an event must be filed exactly as written")

    def test_one_page_per_key_prefix_and_an_index(self):
        files = self.files_at("wiki/compile")
        self.assertEqual(["wiki/pages/gate--ascii.md", "wiki/pages/git--show.md"],
                         sorted(f for f in files if f.startswith("wiki/pages/")))
        self.assertIn("wiki/index.md", files)
        index = self.show("wiki/compile", "wiki/index.md")
        self.assertIn("- [gate/ascii](pages/gate--ascii.md) -- 2 live, newest ", index)
        self.assertIn("- [git/show](pages/git--show.md) -- 1 live, newest ", index)

    def test_a_page_carries_front_matter_and_every_field(self):
        page = self.show("wiki/compile", "wiki/pages/gate--ascii.md")
        self.assertTrue(page.startswith("---\ntype: wiki-page\n"), page[:80])
        self.assertIn("status: stable\n", page)
        self.assertIn("stale_after: 2099-01-01\n", page)
        self.assertIn("sources:\n  - 'Owner ruling 2026-09-17'\n  - '2aec304'\n", page)
        for ev in (self.a, self.b):
            for field in ("key", "summary", "seat", "evidence", "trust", "id"):
                self.assertIn(ev[field], page, f"{field} missing from the page")
            self.assertIn(ev["ts"][:10], page)

    def test_pages_sharing_a_first_segment_link_each_other(self):
        """`gate/ascii` and `git/show` share no first segment, so neither links the other. A third
        page under `gate/` must be linked from `gate/ascii`."""
        self.assertNotIn("## Related", self.show("wiki/compile", "wiki/pages/gate--ascii.md"))
        w.plant(self.inbox, when=w.days_ago(0.5), key="gate/leak/home-path", summary="a home path leaks")
        self.compile()
        page = self.show("wiki/compile", "wiki/pages/gate--ascii.md")
        self.assertIn("## Related\n\n- [gate/leak](gate--leak.md)\n", page)

    def test_exactly_one_log_line_is_appended(self):
        log = self.show("wiki/compile", "wiki/log.md")
        lines = [ln for ln in log.splitlines() if ln.startswith("- ")]
        self.assertEqual(1, len(lines), log)
        self.assertRegex(lines[0], r"^- \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z: 3 event\(s\) added, 2 page\(s\) written, "
                                   r"0 conflict\(s\), 0 held back$")

    def test_it_commits_on_wiki_compile_over_base_and_leaves_base_alone(self):
        self.assertEqual(self.remote_sha("main"), self.remote_sha("wiki/compile^1"))
        self.assertEqual("wiki: compile 3 events", self.remote_git("log", "-1", "--format=%s", "wiki/compile").strip())
        self.assertNotIn("wiki/index.md", self.files_at("main"), "compile must never write to Base")

    def test_the_temporary_worktree_is_removed(self):
        self.assertEqual(1, self.worktree_count())


class AnInboxFileLeavesOnlyAfterItsPullRequestMerges(_CompileCase):
    def setUp(self):
        super().setUp()
        self.ev = w.plant(self.inbox, when=w.days_ago(1), key="coord/state-root/shared",
                          summary="The coordination directory is shared by every worktree")
        self.path = self.inbox / f"{self.ev['id']}.json"

    def test_the_file_survives_compile_and_a_re_run_before_the_merge(self):
        self.compile()
        self.assertTrue(self.path.is_file(), "compile deleted an inbox file whose pull request has not merged")
        second = self.compile()
        self.assertTrue(self.path.is_file())
        self.assertEqual(0, second["deleted"])

    def test_after_the_merge_the_next_run_deletes_it(self):
        self.compile()
        self.merge()
        r = self.compile()
        self.assertFalse(self.path.exists(), "the landed event is still in the inbox")
        self.assertEqual(1, r["deleted"])
        self.assertEqual("nothing-pending", r["result"])

    def test_a_squash_merge_clears_it_too(self):
        """The trunk squash-merges: Base then holds the compiled tree in a commit that is not
        `wiki/compile`. The landed check reads the tree at Base, so it must still see the event."""
        self.compile()
        tree = self.remote_sha("wiki/compile^{tree}")
        # An identity on the command line: the bare remote has none, and a runner may have no global one.
        squash = w.git(self.root, "-c", "user.email=t@example.com", "-c", "user.name=t",
                       f"--git-dir={self.remote}", "commit-tree", tree, "-p", "main", "-m", "squash").stdout.strip()
        self.remote_git("update-ref", "refs/heads/main", squash)
        self.assertNotEqual(self.remote_sha("main"), self.remote_sha("wiki/compile"))
        r = self.compile()
        self.assertEqual(1, r["deleted"])
        self.assertFalse(self.path.exists())

    def test_a_record_repo_named_by_a_subdirectory_reads_the_whole_tree(self):
        self.compile()
        self.merge()
        sub = self.record / "sub"
        sub.mkdir()
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state), "-RecordRepo", str(sub), "-NoPr", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, json.loads(r.stdout)["deleted"])

    def test_a_run_with_nothing_pending_exits_0_and_does_nothing(self):
        self.compile()
        self.merge()
        self.compile()
        head = self.remote_sha("wiki/compile")
        r = self.compile()
        self.assertEqual("nothing-pending", r["result"])
        self.assertEqual(0, r["deleted"])
        self.assertEqual(head, self.remote_sha("wiki/compile"))

    def test_an_empty_inbox_exits_0_without_a_branch(self):
        self.path.unlink()
        r = self.compile()
        self.assertEqual("nothing-pending", r["result"])
        self.assertFalse(self.remote_has("refs/heads/wiki/compile"))


class ASecondRunAddsNothing(_CompileCase):
    """FR-019. The tree compared is `content_tree`: the tree each run BUILDS, before the log line,
    computed afresh every time. The pushed tree would not do: a converged run reports the commit it
    left alone, so comparing it with itself cannot fail. The control: one more inbox event DOES move
    the content tree, so an unchanged one is a reading and not a comparison that cannot see a change.
    """

    def setUp(self):
        super().setUp()
        for n, key in enumerate(("gate/ascii/one", "gate/ascii/two")):
            w.plant(self.inbox, when=w.days_ago(2 - n), key=key, summary=f"planted event number {n}")
        self.first = self.compile()

    def test_the_same_inbox_and_base_give_the_same_tree(self):
        commits = self.remote_git("rev-list", "--count", "--all").strip()
        second = self.compile()
        self.assertEqual("converged", second["result"])
        self.assertEqual(self.first["content_tree"], second["content_tree"])
        self.assertEqual(0, second["added"])
        self.assertEqual(self.first["head"], second["head"])
        self.assertEqual(self.first["head"], self.remote_sha("wiki/compile"))
        self.assertEqual(commits, self.remote_git("rev-list", "--count", "--all").strip())

    def test_control_a_new_event_does_move_the_tree(self):
        w.plant(self.inbox, when=w.days_ago(0.5), key="gate/ascii/three", summary="planted event number three")
        third = self.compile()
        self.assertEqual("compiled", third["result"])
        self.assertNotEqual(self.first["content_tree"], third["content_tree"])
        self.assertEqual(self.remote_sha("main"), self.remote_sha("wiki/compile^1"),
                         "the rebuilt branch must sit on Base, not on the previous compile")
        log = self.show("wiki/compile", "wiki/log.md")
        self.assertEqual(1, len([ln for ln in log.splitlines() if ln.startswith("- ")]))


class TheRebuildHidesWhatWasSuperseded(_CompileCase):
    """SC-001 and Story 2. The query half goes through `query.ps1`, the real read path."""

    def setUp(self):
        super().setUp()
        self.a = w.plant(self.inbox, when=w.days_ago(3), key="ruling/merge-owner",
                         summary="The Owner merges every pull request by hand")
        # A different key under the same prefix: one page holds both, and nothing but the
        # `supersedes` list can hide A.
        self.b = w.plant(self.inbox, when=w.days_ago(1), type="decision", key="ruling/landing",
                         summary="The Lander lands each change once its checks are green",
                         supersedes=[self.a["id"]])
        self.compile()
        self.checkout = self.checkout_of("wiki/compile", "rebuild")
        self.wiki = self.checkout / "wiki"
        self.compiled = {p.relative_to(self.wiki).as_posix(): p.read_bytes()
                         for p in [*self.wiki.joinpath("pages").glob("*.md"), self.wiki / "index.md"]}
        for p in self.wiki.joinpath("pages").glob("*.md"):
            p.unlink()
        self.wiki.joinpath("pages").rmdir()
        (self.wiki / "index.md").unlink()
        # The control for the equality check below, read with the same instrument: staged against
        # HEAD, the deletion MUST show. Then unstaged again, so the rebuild starts from the deletion.
        w.git(self.checkout, "add", "--all", "--", "wiki")
        self.deleted_status = w.git(self.checkout, "diff", "--cached", "--name-status", "HEAD").stdout
        w.git(self.checkout, "reset", "--quiet")
        r = w.run(self.pwsh, COMPILE, "-RecordRepo", str(self.checkout), "-RebuildOnly", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        self.rebuilt = json.loads(r.stdout)
        self.empty_state = self.root / "empty-state"
        self.empty_state.mkdir()

    def page_text(self) -> str:
        return "".join(p.read_text(encoding="utf-8") for p in sorted(self.wiki.joinpath("pages").glob("*.md"))) + \
            (self.wiki / "index.md").read_text(encoding="utf-8")

    def query(self, *extra: str) -> list[dict]:
        r = w.run(self.pwsh, w.QUERY, "-Text", "Owner merges every pull request", "-RecordRepo",
                  str(self.checkout), "-StateRoot", str(self.empty_state), "-Json", *extra)
        self.assertEqual(0, r.returncode, r.stderr)
        return json.loads(r.stdout)

    def test_the_rebuild_equals_what_compile_wrote(self):
        """FR-012. The deletion shows in `git status` first, so a clean status after is a reading."""
        self.assertIn("D\twiki/index.md", self.deleted_status)
        self.assertIn("D\twiki/pages/ruling.md", self.deleted_status)
        self.assertEqual("rebuilt", self.rebuilt["result"])
        # Staged, then compared with HEAD: `git add` runs the same line-ending filter the commit ran,
        # so this compares blobs. A bare `git status` can list a file whose only difference is the
        # CRLF a `core.autocrlf=true` checkout wrote, which is not a difference in the page.
        w.git(self.checkout, "add", "--all", "--", "wiki")
        self.assertEqual("", w.git(self.checkout, "diff", "--cached", "--name-status", "HEAD").stdout)
        # Compared with line endings folded: a checkout under `core.autocrlf=true` holds CRLF, and
        # the rebuild writes LF. `git status` above already folds them the same way.
        for rel, data in self.compiled.items():
            self.assertEqual(data.replace(b"\r\n", b"\n"), (self.wiki / rel).read_bytes().replace(b"\r\n", b"\n"), rel)

    def test_a_is_on_no_rebuilt_page_and_b_is(self):
        text = self.page_text()
        self.assertNotIn(self.a["summary"], text)
        self.assertIn(self.b["summary"], text)
        self.assertIn(self.a["id"], text, "A must still be named in the Replaced section")

    def test_the_replaced_section_points_at_b(self):
        page = (self.wiki / "pages" / "ruling.md").read_text(encoding="utf-8")
        replaced = page.split("## Replaced", 1)[1]
        self.assertRegex(replaced, re.escape(self.a["id"]) + r".*replaced by \[" + re.escape(self.b["id"]))

    def test_a_query_for_a_own_words_returns_b_never_a(self):
        rows = self.query()
        ids = [row["id"] for row in rows]
        self.assertEqual([self.b["id"]], ids)
        self.assertNotIn(self.a["id"], ids)
        self.assertEqual(self.a["id"], rows[0]["found_via"])
        self.assertEqual("log", rows[0]["source"], "the answer must come from the rebuilt log, not the inbox")

    def test_history_shows_a_as_historical_with_a_pointer_to_b(self):
        rows = {row["id"]: row for row in self.query("-History")}
        self.assertIn(self.a["id"], rows)
        self.assertEqual("historical", rows[self.a["id"]]["label"])
        self.assertEqual(self.b["id"], rows[self.a["id"]]["replaced_by"])

    def test_control_with_the_guard_off_a_does_appear(self):
        """The same events, the same renderer, one switch. Both arms run in one process, so the
        only difference between them is the guard."""
        events_dir = self.wiki / "events"
        r = w.run_ps(
            self.pwsh,
            f". '{RENDER_LIB}'; "
            f"$on = Build-WikiPageSet -Events @((Read-WikiEventDir -Dir '{events_dir}' -Source log -Recurse).Events); "
            f"$off = Build-WikiPageSet -Events @((Read-WikiEventDir -Dir '{events_dir}' -Source log -Recurse).Events) -NoGuard; "
            "[pscustomobject]@{ on = (@($on.Files.Values) -join ''); off = (@($off.Files.Values) -join '') } | ConvertTo-Json",
        )
        self.assertEqual(0, r.returncode, r.stderr)
        arms = json.loads(r.stdout)
        self.assertIn(self.a["summary"], arms["off"], "with the guard off A must render, or the absence measures nothing")
        self.assertNotIn(self.a["summary"], arms["on"])


class TwoLiveEventsOnOneKeyAreAConflict(_CompileCase):
    def test_the_newer_is_live_and_the_pair_is_listed(self):
        old = w.plant(self.inbox, when=w.days_ago(2), key="gate/ascii/exit-code", summary="the gate exits one")
        new = w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="the gate exits two")
        r = self.compile()
        self.assertEqual(1, r["conflicts"])
        page = self.show("wiki/compile", "wiki/pages/gate--ascii.md")
        live = page.split("## Live", 1)[1].split("## Replaced", 1)[0]
        self.assertIn(new["summary"], live)
        self.assertNotIn(old["summary"], page)
        conflicts = self.show("wiki/compile", "wiki/index.md").split("## Conflicts", 1)[1]
        self.assertIn("`gate/ascii/exit-code`", conflicts)
        self.assertRegex(conflicts, re.escape(f"kept [{new['id']}]") + r".*also: \[" + re.escape(old["id"]))
        self.assertIn("1 conflict(s)", self.show("wiki/compile", "wiki/log.md"))

    def test_control_a_supersede_between_them_is_not_a_conflict(self):
        old = w.plant(self.inbox, when=w.days_ago(2), key="gate/ascii/exit-code", summary="the gate exits one")
        w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="the gate exits two",
                supersedes=[old["id"]])
        r = self.compile()
        self.assertEqual(0, r["conflicts"])
        self.assertIn("## Conflicts\n\nNone.\n", self.show("wiki/compile", "wiki/index.md"))


class AConflictCanHoldNothingLive(_CompileCase):
    def test_the_index_never_names_a_hidden_event_as_kept(self):
        """A, B and C on one key; D on another key supersedes C. C still hides A and B by recency,
        so nothing on the key is live, and A and B are a conflict nobody decided."""
        a = w.plant(self.inbox, when=w.days_ago(4), key="k/x", summary="first take")
        b = w.plant(self.inbox, when=w.days_ago(3), key="k/x", summary="second take")
        c = w.plant(self.inbox, when=w.days_ago(2), key="k/x", summary="third take")
        w.plant(self.inbox, when=w.days_ago(1), key="k/y", summary="the fourth", supersedes=[c["id"]])
        self.compile()
        conflicts = self.show("wiki/compile", "wiki/index.md").split("## Conflicts", 1)[1]
        self.assertIn("- `k/x`: nothing live; also: ", conflicts)
        self.assertIn(a["id"], conflicts)
        self.assertIn(b["id"], conflicts)
        self.assertNotIn("kept", conflicts)


class PageNamesNeverCollideOrGetRefused(_CompileCase):
    def test_a_device_name_prefix_and_a_double_dash_prefix(self):
        w.plant(self.inbox, when=w.days_ago(3), key="aux/thing", summary="a key under a device name")
        w.plant(self.inbox, when=w.days_ago(2), key="a--b/x", summary="a key with a double dash")
        w.plant(self.inbox, when=w.days_ago(1), key="a/b/x", summary="a key with two slashes")
        r = self.compile()
        self.assertEqual(3, r["pages"])
        pages = sorted(f for f in self.files_at("wiki/compile") if f.startswith("wiki/pages/"))
        self.assertEqual(["wiki/pages/_aux.md", "wiki/pages/a--b.md", "wiki/pages/a--b~.md"], pages)
        self.assertIn("a key with a double dash", self.show("wiki/compile", "wiki/pages/a--b~.md"))
        self.assertIn("a key with two slashes", self.show("wiki/compile", "wiki/pages/a--b.md"))

    def test_a_long_key_gets_a_short_stable_name(self):
        key = "/".join(["seg"] * 40) + "/leaf"  # 164 characters, under the 200 limit
        w.plant(self.inbox, when=w.days_ago(1), key=key, summary="a very deep key")
        self.compile()
        pages = [f for f in self.files_at("wiki/compile") if f.startswith("wiki/pages/")]
        self.assertEqual(1, len(pages))
        name = pages[0].rsplit("/", 1)[1]
        self.assertRegex(name, r"^(seg--){16}~h[0-9a-f]{12}\.md$")


class AnUnreadableLogFileIsSaidOutLoud(_CompileCase):
    """A landed file that no longer reads is left out of the pages; were it a marker, what it hid would
    show as live. So both paths count it and warn. The control is the same run over a clean log."""

    def setUp(self):
        super().setUp()
        bad = self.seed / "wiki" / "events" / "2026" / "09" / "20260901T000000000Z-broken.json"
        bad.parent.mkdir(parents=True)
        bad.write_text("{ this is not json", encoding="ascii")
        w.git(self.seed, "add", "wiki")
        w.git(self.seed, "commit", "-m", "a torn event")
        w.git(self.seed, "push", "origin", "main")
        w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="the gate exits two")

    def test_compile_counts_and_warns(self):
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state), "-RecordRepo", str(self.record), "-NoPr", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, json.loads(r.stdout)["log_skipped"])
        self.assertIn("WARNING: 1 file(s) in the log could not be read", r.stderr)

    def test_rebuild_only_counts_and_warns(self):
        r = w.run(self.pwsh, COMPILE, "-RecordRepo", str(self.seed), "-RebuildOnly", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, json.loads(r.stdout)["log_skipped"])
        self.assertIn("WARNING: 1 file(s) in the log could not be read", r.stderr)

    def test_control_a_clean_log_warns_nothing(self):
        (self.seed / "wiki" / "events" / "2026" / "09" / "20260901T000000000Z-broken.json").unlink()
        w.plant(self.seed / "wiki" / "events" / "2026" / "09", when=w.days_ago(1), key="gate/x/y", summary="fine")
        r = w.run(self.pwsh, COMPILE, "-RecordRepo", str(self.seed), "-RebuildOnly", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(0, json.loads(r.stdout)["log_skipped"])
        self.assertNotIn("WARNING", r.stderr)


class AnIdCollisionFailsLoudly(_CompileCase):
    def setUp(self):
        super().setUp()
        self.when = w.days_ago(1)
        self.ev = w.plant(self.inbox, when=self.when, key="gate/ascii/exit-code", summary="the original text")
        self.compile()
        self.merge()

    def test_different_content_under_a_landed_id_is_refused_and_nothing_moves(self):
        w.plant(self.inbox, when=self.when, event_id=self.ev["id"], key="gate/ascii/exit-code",
                summary="a different text under the same id")
        other = w.plant(self.inbox, when=w.days_ago(0.5), key="gate/ascii/other", summary="an innocent bystander")
        head = self.remote_sha("wiki/compile")
        r = self.compile(expect=1)
        self.assertIn("id collision", r["stderr"])
        self.assertIn(self.ev["id"], r["stderr"])
        self.assertTrue((self.inbox / f"{self.ev['id']}.json").is_file(), "the colliding file was deleted")
        self.assertTrue((self.inbox / f"{other['id']}.json").is_file())
        self.assertEqual(head, self.remote_sha("wiki/compile"), "a refused compile pushed")
        self.assertEqual(1, self.worktree_count())

    def test_control_the_same_content_under_that_id_is_simply_cleared(self):
        (self.inbox / f"{self.ev['id']}.json").write_text(json.dumps(self.ev, indent=2), encoding="utf-8")
        r = self.compile()
        self.assertEqual(1, r["deleted"])


class ALandedFileIsClearedByItsObjectId(_CompileCase):
    """Step 1's fast path. A landed inbox file is matched by the object id `ls-tree` already printed,
    so no `git show` runs for it. One `git show` per file cost 208 s for 906 files, 2026-09-26.

    GIT_TRACE2 records every git process the run starts, so the `show` count is read off git itself
    and not off the script's report. The `ls-tree` count shows the trace is armed, so a zero is a
    reading. The control: a copy that differs only in trailing blank lines misses the fast path, is
    read back once, and is still cleared, because the comparison ignores trailing space."""

    SHOW = re.compile(r" start .* show [0-9a-f]{40,64}:wiki/events/")
    LS_TREE = re.compile(r" start .* ls-tree ")

    def setUp(self):
        super().setUp()
        self.events = [w.plant(self.inbox, when=w.days_ago(3 - n), key=f"gate/ascii/n{n}", summary=f"planted event {n}")
                       for n in range(3)]
        self.compile()
        self.merge()
        self.trace = self.root / "trace2.txt"

    def run_traced(self) -> dict:
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state), "-RecordRepo", str(self.record), "-NoPr", "-Json",
                  env={"GIT_TRACE2": str(self.trace)})
        self.assertEqual(0, r.returncode, r.stderr)
        return json.loads(r.stdout)

    def count(self, pattern: re.Pattern[str]) -> int:
        lines = self.trace.read_text(encoding="utf-8", errors="replace").splitlines()
        return len([ln for ln in lines if pattern.search(ln)])

    def test_an_identical_landed_file_is_cleared_with_no_git_show(self):
        r = self.run_traced()
        self.assertEqual(3, r["deleted"])
        self.assertEqual([], list(self.inbox.glob("*.json")))
        self.assertGreater(self.count(self.LS_TREE), 0, "the trace saw the run's git calls")
        self.assertEqual(0, self.count(self.SHOW))

    def test_control_a_copy_with_trailing_blank_lines_is_read_back_once_and_cleared(self):
        path = self.inbox / f"{self.events[0]['id']}.json"
        path.write_bytes(path.read_bytes() + b"\n\n")
        r = self.run_traced()
        self.assertEqual(3, r["deleted"])
        self.assertEqual([], list(self.inbox.glob("*.json")))
        self.assertEqual(1, self.count(self.SHOW))


class TheHoldChecksOutOnlyTheScannersDirectory(_CompileCase):
    """Step 3. The hold needs only the scanner and the files beside it, so a run that files nothing
    never checks out the record's whole tree. The stub scanner lists what it can see from where it
    runs. Base's `a.txt` sits outside the scanner's directory and must be absent during the scan.

    The control: a run that files does check out the whole tree, and its commit still carries every
    file at Base. Without that checkout the commit would drop them, so the control is what shows the
    commit is still Base plus the log."""

    def setUp(self):
        super().setUp()
        self.seen = self.root / "scanner-cwd.txt"
        self.leak = w.plant(self.inbox, when=w.days_ago(2), key="site/one/feed", summary=f"The feed for {LEAK_TOKEN} drops")

    def run_compile(self) -> dict:
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state), "-RecordRepo", str(self.record), "-NoPr", "-Json",
                  env={"WIKI_TEST_SCANNER_CWD": str(self.seen)})
        self.assertEqual(0, r.returncode, r.stderr)
        return json.loads(r.stdout)

    def test_a_run_that_files_nothing_checks_out_only_the_scanner(self):
        self.assertIn("a.txt", self.files_at("main"), "Base holds a file outside the scanner's directory")
        r = self.run_compile()
        self.assertEqual("nothing-pending", r["result"])
        self.assertEqual([self.leak["id"]], r["held_ids"])
        self.assertEqual("scanner", r["checkout"])
        self.assertEqual([".git scripts"], self.seen.read_text(encoding="utf-8").splitlines())
        self.assertFalse(self.remote_has("refs/heads/wiki/compile"))
        self.assertEqual(1, self.worktree_count())

    def test_control_a_run_that_files_checks_out_the_whole_tree(self):
        w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="The gate exits two")
        r = self.run_compile()
        self.assertEqual("compiled", r["result"])
        self.assertEqual("full", r["checkout"])
        files = self.files_at("wiki/compile")
        self.assertEqual(sorted(self.files_at("main")), sorted(f for f in files if not f.startswith("wiki/")))
        self.assertIn("a.txt", files)
        self.assertEqual(1, self.worktree_count())

    def test_nothing_pending_makes_no_worktree(self):
        (self.inbox / f"{self.leak['id']}.json").unlink()
        r = self.run_compile()
        self.assertEqual("nothing-pending", r["result"])
        self.assertIsNone(r["checkout"])
        self.assertFalse(self.seen.exists(), "the scanner ran with nothing pending")


class CompileTimesItsPhasesOnlyWhenAsked(_CompileCase):
    """-Timings prints one stderr line a phase. Without it, stderr carries no timing line at all."""

    def test_timings_name_each_phase_and_a_total(self):
        w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="The gate exits two")
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state), "-RecordRepo", str(self.record), "-NoPr", "-Json",
                  "-Timings")
        self.assertEqual(0, r.returncode, r.stderr)
        phases = re.findall(r"(?m)^wiki compile: timing (\S+) \d+\.\d\d s$", r.stderr)
        for phase in ("setup", "fetch", "clear-landed", "worktree-add", "hold-scan", "checkout-full",
                      "commit-push", "worktree-remove", "total"):
            self.assertIn(phase, phases)
        self.assertEqual("compiled", json.loads(r.stdout)["result"])

    def test_control_no_timing_line_without_the_switch(self):
        w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="The gate exits two")
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state), "-RecordRepo", str(self.record), "-NoPr", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotIn("timing", r.stderr)


class TheRecordClonesWorkingTreeIsUntouched(_CompileCase):
    def test_status_and_head_are_identical_before_and_after(self):
        # Dirt of both kinds, so a compile that cleaned, reset or checked out would change the reading.
        (self.record / "a.txt").write_text("edited by a session\n", encoding="ascii")
        (self.record / "untracked.txt").write_text("a session's scratch\n", encoding="ascii")
        before = w.git(self.record, "status", "--porcelain").stdout
        head = w.git(self.record, "rev-parse", "HEAD").stdout
        branch = w.git(self.record, "branch", "--show-current").stdout
        self.assertIn("a.txt", before)
        self.assertIn("untracked.txt", before)
        w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="the gate exits two")
        self.compile()
        self.merge()
        self.compile()
        self.assertEqual(before, w.git(self.record, "status", "--porcelain").stdout)
        self.assertEqual(head, w.git(self.record, "rev-parse", "HEAD").stdout)
        self.assertEqual(branch, w.git(self.record, "branch", "--show-current").stdout)
        self.assertFalse((self.record / "wiki").exists(), "compile wrote into the clone's working tree")


class TheLeakHoldKeepsAFlaggedEventInTheInbox(_CompileCase):
    """FR-028. An event the record repository's scanner flags, or one carrying an email address, is
    held: never copied, never rendered, left in the inbox where a query still finds it. The clean
    event beside them is the control, so a hold that held everything would fail here."""

    def setUp(self):
        super().setUp()
        self.calls = self.root / "scanner-calls.txt"
        self.leak = w.plant(self.inbox, when=w.days_ago(3), key="site/one/feed",
                            summary=f"The feed for {LEAK_TOKEN} drops a segment")
        self.mail = w.plant(self.inbox, when=w.days_ago(2), key="site/two/contact",
                            summary="The interface has a named contact", body="Write to a.person@example.com first")
        # `path@ref` is documented evidence. An `@` alone must not hold an event.
        # So is a decorator opening a line: in the JSON it follows `\n`, which must not read as an
        # address's last letter.
        self.clean = w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code",
                             summary="The gate exits two", evidence="scripts/wiki/compile.ps1@e3e3410",
                             body="The fixture reads\n@pytest.fixture\ndef gate():")
        self.held = sorted([self.leak["id"], self.mail["id"]])
        self.first = self.run_compile("-Json")
        self.result = json.loads(self.first.stdout)

    def run_compile(self, *extra: str) -> subprocess.CompletedProcess:
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state), "-RecordRepo", str(self.record), "-NoPr",
                  *extra, env={"WIKI_TEST_SCANNER_CALLS": str(self.calls)})
        self.assertEqual(0, r.returncode, f"compile exited {r.returncode}: {r.stderr}\n{r.stdout}")
        return r

    def filed_ids(self) -> list[str]:
        return sorted(Path(f).stem for f in self.files_at("wiki/compile") if f.startswith("wiki/events/"))

    def wiki_text_at(self, ref: str) -> str:
        return "".join(self.show(ref, f) for f in self.files_at(ref) if f.startswith("wiki/"))

    def test_a_flagged_event_is_held_and_stays_in_the_inbox(self):
        self.assertNotIn(self.leak["id"], self.filed_ids())
        self.assertTrue((self.inbox / f"{self.leak['id']}.json").is_file())
        self.assertIn(self.leak["id"], self.result["held_ids"])

    def test_an_email_address_holds_an_event(self):
        self.assertNotIn(self.mail["id"], self.filed_ids())
        self.assertTrue((self.inbox / f"{self.mail['id']}.json").is_file())
        self.assertIn(self.mail["id"], self.result["held_ids"])

    def test_control_the_clean_event_beside_them_is_filed(self):
        self.assertEqual([self.clean["id"]], self.filed_ids())
        self.assertEqual("compiled", self.result["result"])

    def test_the_report_counts_and_names_what_was_held(self):
        self.assertEqual(3, self.result["pending"])
        self.assertEqual(2, self.result["held"])
        self.assertEqual(self.held, self.result["held_ids"])
        self.assertEqual(1, self.result["added"])
        self.assertEqual("wiki: compile 1 events", self.remote_git("log", "-1", "--format=%s", "wiki/compile").strip())

    def test_the_log_line_and_the_commit_body_carry_the_held_count(self):
        log = self.show("wiki/compile", "wiki/log.md")
        self.assertRegex(log, r"(?m)^- \S+: 1 event\(s\) added, 1 page\(s\) written, 0 conflict\(s\), 2 held back$")
        self.assertIn("2 event(s) held back", self.remote_git("log", "-1", "--format=%b", "wiki/compile"))

    def test_held_events_render_nowhere(self):
        text = self.wiki_text_at("wiki/compile")
        self.assertIn(self.clean["summary"], text, "the control: a filed event does render")
        for ev in (self.leak, self.mail):
            self.assertNotIn(ev["summary"], text)
            self.assertNotIn(ev["id"], text)

    def test_the_scanner_runs_once_over_every_pending_event(self):
        """Once, and over each event twice: its bytes, and its text with every escape decoded."""
        runs = self.calls.read_text(encoding="ascii").splitlines()
        self.assertEqual(1, len(runs))
        expected = sorted(f"{ev['id']}{ext}" for ev in (self.leak, self.mail, self.clean)
                          for ext in (".json", ".decoded.txt"))
        self.assertEqual(expected, sorted(runs[0].split()))

    def test_the_token_is_printed_nowhere(self):
        """The real scanner's hit line carries the matched token, and so does the stub's. The held
        count shows the scanner's output WAS read, so its absence here is not a scan that never ran."""
        self.assertEqual(2, self.result["held"])
        text = self.run_compile()
        self.assertIn("2 held back", text.stdout)
        for out in (self.first.stdout, self.first.stderr, text.stdout, text.stderr,
                    self.remote_git("log", "-1", "--format=%B", "wiki/compile")):
            self.assertNotIn(LEAK_TOKEN, out)
            self.assertNotIn("a.person@", out)

    def test_a_held_event_is_scanned_again_and_held_after_the_merge(self):
        second = json.loads(self.run_compile("-Json").stdout)
        self.assertEqual(self.held, second["held_ids"])
        self.merge()
        third = json.loads(self.run_compile("-Json").stdout)
        self.assertEqual(1, third["deleted"], "the filed event lands and leaves the inbox")
        self.assertEqual("nothing-pending", third["result"])
        self.assertEqual(2, third["held"])
        self.assertEqual(self.held, third["held_ids"])
        self.assertEqual(self.held, sorted(p.stem for p in self.inbox.glob("*.json")))
        self.assertEqual(3, len(self.calls.read_text(encoding="ascii").splitlines()))

    def test_a_query_still_finds_a_held_event(self):
        r = w.run(self.pwsh, w.QUERY, "-Text", "feed drops a segment", "-StateRoot", str(self.state), "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn(self.leak["id"], [row["id"] for row in json.loads(r.stdout)])


class TheLeakHoldReadsWhatThePageWillShow(_CompileCase):
    """A page renders an event decoded, so a JSON escape must not hide a name or an address from the
    hold, and a file the scanner would skip as binary must not pass unread. The clean event is the
    control: the same run files it."""

    def test_escaped_names_and_addresses_and_a_utf16_file_are_held(self):
        esc = w.plant(self.inbox, when=w.days_ago(4), key="site/one/feed", summary=f"The feed for {LEAK_TOKEN} drops")
        path = self.inbox / f"{esc['id']}.json"
        path.write_text(path.read_text(encoding="utf-8").replace(LEAK_TOKEN, LEAK_TOKEN[:-1] + "\\u004e"),
                        encoding="utf-8")
        self.assertNotIn(LEAK_TOKEN, path.read_text(encoding="utf-8"), "the plant must hide the token")
        mail = w.plant(self.inbox, when=w.days_ago(3), key="site/two/contact", summary="A contact",
                       body="write to a.person@example.com")
        mpath = self.inbox / f"{mail['id']}.json"
        mpath.write_text(mpath.read_text(encoding="utf-8").replace("@", "\\u0040"), encoding="utf-8")
        wide = w.plant(self.inbox, when=w.days_ago(2), key="site/three/feed", summary="A wide file")
        wpath = self.inbox / f"{wide['id']}.json"
        wpath.write_bytes(wpath.read_text(encoding="utf-8").encode("utf-16"))
        # A NUL in the DECODED text, in a field the schema does not name and so does not check: the
        # raw bytes hold none, and the token is escaped there.
        nul = w.plant(self.inbox, when=w.days_ago(1.8), key="site/four/feed", summary=f"About {LEAK_TOKEN}",
                      note="a\u0000b")
        npath = self.inbox / f"{nul['id']}.json"
        npath.write_text(npath.read_text(encoding="utf-8").replace(LEAK_TOKEN, LEAK_TOKEN[:-1] + "\\u004e"),
                         encoding="utf-8")
        self.assertNotIn(b"\x00", npath.read_bytes())
        # A name beside an allowlisted phrase on one line must not borrow its exemption.
        beside = w.plant(self.inbox, when=w.days_ago(1.6), key="site/five/feed", summary=f"{ALLOWED} {LEAK_TOKEN}")
        # An address split by an invisible character is still an address on the page.
        split = w.plant(self.inbox, when=w.days_ago(1.4), key="site/six/contact", summary="A contact",
                        body="a.person@exa\u200bmple.com")
        clean = w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="The gate exits two")
        r = self.compile()
        self.assertEqual(sorted([esc["id"], mail["id"], wide["id"], nul["id"], beside["id"], split["id"]]),
                         r["held_ids"])
        self.assertEqual(7, r["pending"], "the wide file must still read as a pending event")
        self.assertEqual(1, r["added"])
        filed = [Path(f).stem for f in self.files_at("wiki/compile") if f.startswith("wiki/events/")]
        self.assertEqual([clean["id"]], filed)


class TheLeakHoldSaysWhatItCannotFix(_CompileCase):
    def run_json(self) -> tuple[dict, str]:
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state), "-RecordRepo", str(self.record), "-NoPr", "-Json")
        self.assertEqual(0, r.returncode, r.stderr)
        return json.loads(r.stdout), r.stderr

    def test_a_held_marker_is_named_on_stderr(self):
        old = w.plant(self.inbox, when=w.days_ago(3), key="gate/ascii/exit-code", summary="The gate exits one")
        self.compile()
        self.merge()
        marker = w.plant(self.inbox, when=w.days_ago(1), type="retire", key="gate/ascii/exit-code",
                         summary=f"Withdrawn, see {LEAK_TOKEN}")
        w.plant(self.inbox, when=w.days_ago(0.5), key="gate/ascii/other", summary="Unrelated and clean")
        out, err = self.run_json()
        self.assertEqual([marker["id"]], out["held_ids"])
        self.assertIn("WARNING: 1 held event(s) supersede or retire something: " + marker["id"], err)
        self.assertIn(old["summary"], self.show("wiki/compile", "wiki/pages/gate--ascii.md"),
                      "the withdrawn event is still live, which is what the warning is for")
        self.assertNotIn(LEAK_TOKEN, err)

    def test_control_a_held_content_event_warns_nothing(self):
        w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary=f"About {LEAK_TOKEN}")
        w.plant(self.inbox, when=w.days_ago(0.5), key="gate/ascii/other", summary="Unrelated and clean")
        out, err = self.run_json()
        self.assertEqual(1, out["held"])
        self.assertNotIn("WARNING", err)

    def test_a_standing_branch_carrying_a_now_held_event_is_named(self):
        """Filed while clean, then flagged by a scanner that learned a new name. With nothing left to
        file, the branch is not rebuilt, so its pull request still carries the event."""
        ev = w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="The gate exits LATERNAME")
        self.assertEqual(0, self.compile()["held"])
        self.set_scanner(stub_scanner("LATERNAME"))
        out, err = self.run_json()
        self.assertEqual("nothing-pending", out["result"])
        self.assertEqual([ev["id"]], out["held_ids"])
        self.assertIn("WARNING: wiki/compile still carries 1 event(s) the leak hold now flags", err)

    def test_a_rebuild_that_drops_a_now_held_event_says_so(self):
        ev = w.plant(self.inbox, when=w.days_ago(2), key="gate/ascii/exit-code", summary="The gate exits LATERNAME")
        self.assertEqual(0, self.compile()["held"])
        self.set_scanner(stub_scanner("LATERNAME"))
        other = w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/other", summary="Unrelated and clean")
        out, err = self.run_json()
        self.assertEqual("compiled", out["result"])
        self.assertEqual([ev["id"]], out["held_ids"])
        self.assertIn("WARNING: wiki/compile carried 1 event(s) the leak hold now flags", err)
        filed = [Path(f).stem for f in self.files_at("wiki/compile") if f.startswith("wiki/events/")]
        self.assertEqual([other["id"]], filed)


class TheLeakHoldFailsClosed(_CompileCase):
    """Each way the scan can fail stops the run with exit 2 before anything is copied or pushed. The
    control runs the same events through the working stub, so each exit 2 is the hold's own."""

    def setUp(self):
        super().setUp()
        self.leak = w.plant(self.inbox, when=w.days_ago(2), key="site/one/feed",
                            summary=f"The feed for {LEAK_TOKEN} drops a segment")
        w.plant(self.inbox, when=w.days_ago(1), key="gate/ascii/exit-code", summary="The gate exits two")
        self.before = self.inbox_snapshot()

    def assert_stopped(self, needle: str):
        r = self.compile(expect=2)
        self.assertIn(needle, r["stderr"])
        self.assertEqual("", r["stdout"])
        self.assertNotIn(LEAK_TOKEN, r["stderr"])
        self.assertFalse(self.remote_has("refs/heads/wiki/compile"), "a failed scan pushed")
        self.assertEqual(self.before, self.inbox_snapshot())
        self.assertEqual(1, self.worktree_count())

    def test_control_the_working_scanner_compiles(self):
        r = self.compile()
        self.assertEqual([self.leak["id"]], r["held_ids"])
        self.assertTrue(self.remote_has("refs/heads/wiki/compile"))

    def test_no_scanner_at_base_is_exit_2(self):
        self.set_scanner(None)
        self.assert_stopped("no leak scanner")

    def test_a_scanner_usage_error_is_exit_2(self):
        self.set_scanner(f"import sys\nprint('{LEAK_TOKEN} usage', file=sys.stderr)\nraise SystemExit(2)\n")
        self.assert_stopped("exited 2")

    def test_exit_1_with_no_hit_line_is_exit_2(self):
        self.set_scanner(f"import sys\nprint('{LEAK_TOKEN} went wrong', file=sys.stderr)\nraise SystemExit(1)\n")
        self.assert_stopped("no hit path")

    def test_exit_1_naming_no_staged_file_is_exit_2(self):
        self.set_scanner(f"import sys\nprint('  elsewhere.json:1: planted name ({LEAK_TOKEN})', file=sys.stderr)\n"
                         "raise SystemExit(1)\n")
        self.assert_stopped("names no staged event")

    def test_an_indented_line_that_is_not_a_hit_is_exit_2(self):
        """One hit reads and one does not: the one that does not may be an event that would be filed."""
        self.set_scanner(f"import sys\nprint('  {self.leak['id']}.json:3: planted name ({LEAK_TOKEN})', file=sys.stderr)\n"
                         f"print('  {self.leak['id']}.json (whole file): planted name', file=sys.stderr)\n"
                         "raise SystemExit(1)\n")
        self.assert_stopped("could not be read as a hit")

    def test_a_hit_count_that_disagrees_is_exit_2(self):
        self.set_scanner(f"import sys\nprint('  {self.leak['id']}.json:3: planted name ({LEAK_TOKEN})', file=sys.stderr)\n"
                         "print('\\n2 hit(s).', file=sys.stderr)\nraise SystemExit(1)\n")
        self.assert_stopped("counted 2 hit(s) and 1 could be read")

    def test_a_hit_list_with_no_closing_count_is_exit_2(self):
        """The real scanner always closes with its count. Without it, the list may have been cut off."""
        self.set_scanner(f"import sys\nprint('  {self.leak['id']}.json:3: planted name ({LEAK_TOKEN})', file=sys.stderr)\n"
                         "raise SystemExit(1)\n")
        self.assert_stopped("without its closing hit count")

    def test_a_scanner_that_crashes_after_a_hit_is_exit_2(self):
        """An uncaught exception also exits 1. The hit lines printed before it are not the whole list."""
        self.set_scanner(f"import sys\nprint('  {self.leak['id']}.json:3: planted name ({LEAK_TOKEN})', file=sys.stderr)\n"
                         "raise RuntimeError('the scan died')\n")
        self.assert_stopped("crashed")


_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")
# Two characters or more before the colon, so a drive letter such as `C:` is checked, not skipped.
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")


def check_links(wiki: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """Every relative link in every page and in `index.md`, and those that do not resolve.

    A link resolves when its target is a file that exists INSIDE `wiki/`. The second half matters
    to a viewer: opened on `wiki/`, it cannot follow a link that climbs out, even to a real file.
    Returns (checked, broken): each checked link as (source, target), each broken one as a line.
    """
    root = wiki.resolve()
    checked: list[tuple[str, str]] = []
    broken: list[str] = []
    for page in [*sorted(wiki.joinpath("pages").glob("*.md")), wiki / "index.md"]:
        source = page.relative_to(wiki).as_posix()
        for target in _LINK.findall(page.read_text(encoding="utf-8")):
            if _SCHEME.match(target) or target.startswith("#"):
                continue
            checked.append((source, target))
            resolved = (page.parent / target.split("#", 1)[0]).resolve()
            if not resolved.is_file() or not resolved.is_relative_to(root):
                broken.append(f"{source} -> {target}")
    return checked, broken


class EveryLinkOnEveryPageResolves(_CompileCase):
    """Story 6 and plan PR 6 step 1. The world plants one of every link the renderer writes: a live
    event, `replaced by`, `withdrawn by`, `now live`, a `Related` sibling, an index line, a conflict,
    and page names built by each of `Get-WikiPageFileName`'s rules. The pages are read from a checkout
    of `wiki/compile`, which is what a reader opens.

    Zero broken is armed three ways: each link kind is among the links read, a planted dead link, a
    link that leaves `wiki/` and a drive-letter link are each reported, and a removed event file
    breaks exactly the links to it.
    """

    def setUp(self):
        super().setUp()
        p = self.inbox
        w.plant(p, when=w.days_ago(9), key="gate/ascii/one", summary="a plain live event")
        x = w.plant(p, when=w.days_ago(8), key="gate/ascii/chain", summary="the first take")
        y = w.plant(p, when=w.days_ago(7), type="correction", key="gate/ascii/chain", summary="the second take",
                    supersedes=[x["id"]])
        # The live end of a chain: its own id link, `replaced by` from Y and `now live` from X point here.
        self.z = w.plant(p, when=w.days_ago(6), type="correction", key="gate/ascii/chain", summary="the third take",
                         supersedes=[y["id"]])
        w.plant(p, when=w.days_ago(6), key="gate/leak/home", summary="a key that is later withdrawn")
        w.plant(p, when=w.days_ago(5), type="retire", key="gate/leak/home", summary="withdrawn")
        m = w.plant(p, when=w.days_ago(5), key="ruling/merge-owner", summary="replaced from another key")
        w.plant(p, when=w.days_ago(4), type="supersede", key="ruling/landing", summary="marker", supersedes=[m["id"]])
        w.plant(p, when=w.days_ago(4), key="k/x", summary="one take")
        w.plant(p, when=w.days_ago(3), key="k/x", summary="another take")
        w.plant(p, when=w.days_ago(3), key="aux/thing", summary="a key under a device name")
        w.plant(p, when=w.days_ago(2), key="a--b/x", summary="a key with a double dash")
        w.plant(p, when=w.days_ago(1), key="/".join(["seg"] * 40) + "/leaf", summary="a very deep key")
        self.compile()
        self.wiki = self.checkout_of("wiki/compile", "links") / "wiki"

    def test_every_link_resolves_inside_the_wiki(self):
        checked, broken = check_links(self.wiki)
        self.assertEqual([], broken)
        # Each kind the renderer writes is found on its page AND among the links the checker read, so
        # the empty list above covers it, not a link the pattern skipped.
        for source, kind in (("pages/gate--ascii.md", "replaced by"), ("pages/gate--ascii.md", "now live:"),
                             ("pages/gate--leak.md", "withdrawn by"), ("pages/ruling.md", "replaced by")):
            page = self.wiki.joinpath(source).read_text(encoding="utf-8")
            targets = re.findall(re.escape(kind) + r" \[[^\]]+\]\(([^)]+)\)", page)
            self.assertTrue(targets, f"no `{kind}` link on {source}")
            for target in targets:
                self.assertIn((source, target), checked)
        self.assertIn(("pages/gate--ascii.md", "gate--leak.md"), checked)
        self.assertIn(("index.md", "pages/_aux.md"), checked)
        self.assertIn(("index.md", "pages/a--b~.md"), checked)
        self.assertTrue(any(s == "index.md" and re.fullmatch(r"pages/(seg--){16}~h[0-9a-f]{12}\.md", t)
                            for s, t in checked), "no link to a shortened long-name page")
        self.assertTrue(any(s == "index.md" and t.startswith("events/") for s, t in checked), "no conflict link")
        self.assertTrue(any(s.startswith("pages/") and t.startswith("../events/") for s, t in checked))

    def test_control_a_dead_link_and_a_link_out_of_the_wiki_are_reported(self):
        self.wiki.joinpath("pages", "zz-planted.md").write_text(
            "- [dead](nowhere.md)\n- [out](../../a.txt)\n- [drive](C:/x.md)\n- [site](https://example.com/x)\n",
            encoding="utf-8")
        self.assertTrue(self.wiki.parent.joinpath("a.txt").is_file(), "the out-of-wiki target must exist")
        _, broken = check_links(self.wiki)
        self.assertEqual(["pages/zz-planted.md -> nowhere.md", "pages/zz-planted.md -> ../../a.txt",
                          "pages/zz-planted.md -> C:/x.md"], broken)

    def test_control_a_removed_event_file_breaks_exactly_its_links(self):
        """Three links point at Z, so a checker that reported each dead target once would fail here."""
        ts = self.z["ts"]
        rel = f"events/{ts[:4]}/{ts[5:7]}/{self.z['id']}.json"
        self.wiki.joinpath(rel).unlink()
        _, broken = check_links(self.wiki)
        self.assertEqual(3, len(broken), broken)
        for line in broken:
            self.assertEqual(f"pages/gate--ascii.md -> ../{rel}", line)


class RebuildOnlyNeedsALog(_CompileCase):
    def test_no_events_directory_is_exit_2(self):
        r = w.run(self.pwsh, COMPILE, "-RecordRepo", str(self.record), "-RebuildOnly")
        self.assertEqual(2, r.returncode)
        self.assertIn("no wiki/events", r.stderr)

    def test_no_record_repo_is_exit_2(self):
        r = w.run(self.pwsh, COMPILE, "-StateRoot", str(self.state))
        self.assertEqual(2, r.returncode)
        self.assertIn("-RecordRepo is required", r.stderr)


if __name__ == "__main__":
    unittest.main()
