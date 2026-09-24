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
        self.assertRegex(lines[0], r"^- \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z: 3 event\(s\) added, 2 page\(s\) written, 0 conflict\(s\)$")

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
