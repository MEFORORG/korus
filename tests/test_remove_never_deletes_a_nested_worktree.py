"""`remove.ps1` refuses a worktree that contains another registered worktree.

THE FAILURE THIS EXISTS FOR. `remove.ps1` runs `git worktree remove --force`, which deletes the
whole directory tree. Its only guard reads the parent's `git status` and drops every `??` line, and
a nested checkout shows there as `?? .claude/`, or not at all where it is ignored. So nothing stopped
it. Measured 2026-09-22 with git 2.55.0.windows.5, under the `sibling` layout, with no ignore rule:
removing `P-work` also deleted `P-work/.claude/worktrees/h`, exited 0, and left `h` registered as
prunable. A session started inside a sibling worktree creates its own worktrees there, so the
checkout deleted can be a live session's. CLAUDE.md sends every session through this script.

RETRACTED 2026-09-22, the same day: this paragraph said "A nested checkout is git-ignored inside its
parent, so the parent reads clean". This file's fixture has no ignore rule, the parent read
`?? .claude/`, and the loss happened anyway. Ignoring was never the cause.

WHAT THESE CASES PROVE, AND HOW. They RUN the real script against throwaway repositories. Against
an export of `05eb4a7` this file returns `10 failed, 3 passed, 2 subtests passed`. Every case fails
there except the two controls and the two `sibling` subtests of the `.` and `..` case. They cover
both layouts, a nested path not under `.claude/worktrees/`, and `-Force`.

Four of them hold the REMEDY the refusal prints, which must not be a step that deletes work
`git status` can see. What it cannot see -- ignored files, untracked files hidden by
`status.showUntrackedFiles=no`, a detached HEAD's commits -- is not covered:

  * Commands come deepest first. `git worktree remove` without `--force` deletes ignored files, so
    a parent removed before an ignored child takes the child with it.
  * A nested worktree holding changed or untracked files gets no command. Plain `git worktree
    remove` exits 128 on it, and `--force` is the loss this file exists for.
  * Nor does a parent whose ignored child holds work, because the parent reads clean.
  * A locked worktree comes with its unlock step.

AND ONE HAZARD THE FIX ITSELF OPENED. `-Name`'s pattern accepts `.` and `..`. Under the `nested`
layout those resolve to `.claude/worktrees` and `.claude`, which hold every harness worktree, and the
first cut of the refusal listed them all with commands to delete them. The target must be a
registered worktree before the nested check runs.

TWO CONTROLS, because "refuse everything" passes every refusal case here:

  * A plain sibling with nothing nested is still removed.
  * Under the `nested` layout, `.claude/worktrees/x` is still removed, and a neighbour called `x-2`
    is not mistaken for a child of it. The rule is containment, never path shape: under that layout
    every worktree these scripts create lives under `.claude/worktrees/`.

WHAT THIS DOES NOT PROVE. It sees only worktrees registered to the fixture repository. A checkout of
another repository inside the target is not in `git worktree list`, and the script still deletes it.

Run: python -m pytest tests -q     (or: python -m unittest discover -s tests -v)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120

# Identity and signing per invocation, so the fixture does not depend on the machine's git config.
GIT_ID = (
    "-c", "user.email=ccx@test",
    "-c", "user.name=ccx test",
    "-c", "commit.gpgsign=false",
    "-c", "advice.detachedHead=false",
)


def git(*args: str, cwd: Path) -> str:
    r = subprocess.run(
        ["git", *GIT_ID, *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
    )
    if r.returncode != 0:
        raise AssertionError(f"fixture setup failed: git {' '.join(args)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def fold(path: str | Path) -> str:
    """One spelling for a path, so git's `C:/x` and Python's `C:\\x` compare equal."""
    return str(path).replace("\\", "/").rstrip("/").lower()


class RemoveNeverDeletesANestedWorktree(unittest.TestCase):
    def setUp(self):
        self.pwsh = t.find_pwsh()
        if not self.pwsh:
            self.skipTest("pwsh is not on PATH, so remove.ps1 cannot be executed here")
        if not shutil.which("git"):
            self.skipTest("git is not on PATH, so the fixture repository cannot be built")
        # ignore_cleanup_errors: git leaves read-only pack files behind on Windows.
        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-nested-", ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        # resolve() expands a short 8.3 temp path, so the fixture's paths match the ones git prints.
        self.base = Path(self.tmp.name).resolve()

    # --- fixture ---------------------------------------------------------------------------------

    def primary(self, layout: str = "sibling") -> Path:
        repo = self.base / "P"
        repo.mkdir()
        git("init", "-q", "-b", "main", cwd=repo)
        (repo / "ccx.config.json").write_text(
            '{ "prefix": "ccx", "trunk": "main", "worktreeLayout": "%s" }' % layout, encoding="utf-8"
        )
        (repo / "a.txt").write_text("original\n", encoding="utf-8")
        git("add", "-A", cwd=repo)
        git("commit", "-qm", "init", cwd=repo)
        return repo

    def worktree(self, owner: Path, path: Path, branch: str) -> Path:
        """Add a worktree FROM `owner`, the way a session standing in `owner` creates one."""
        git("worktree", "add", "-q", str(path), "-b", branch, cwd=owner)
        return path

    def registered(self, primary: Path) -> dict[str, bool]:
        """Every registered worktree, folded path -> whether git calls it prunable."""
        out: dict[str, bool] = {}
        current = None
        for line in git("worktree", "list", "--porcelain", cwd=primary).splitlines():
            if line.startswith("worktree "):
                current = fold(line[len("worktree "):])
                out[current] = False
            elif line.startswith("prunable") and current:
                out[current] = True
        return out

    def remove(self, primary: Path, name: str, *flags: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        # The developer's own settings must not reach the fixture.
        for leak in ("CCX_CONFIG", "CCX_TRUNK"):
            env.pop(leak, None)
        # cwd is the primary: remove.ps1 refuses to remove the checkout it is standing in.
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(t.WORKTREE_REMOVE), "-Name", name, *flags],
            capture_output=True, text=True, env=env, cwd=str(primary), timeout=TIMEOUT_SECONDS,
        )

    def exclude(self, primary: Path, pattern: str) -> None:
        """Ignore `pattern` in every worktree of the fixture, through the shared `info/exclude`."""
        common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=primary).strip())
        # `git init` writes info/ from a template, and a machine can be configured without one.
        (common / "info").mkdir(exist_ok=True)
        with open(common / "info" / "exclude", "a", encoding="utf-8") as f:
            f.write(f"\n{pattern}\n")

    def ignore_nested(self, primary: Path) -> None:
        """Ignore `.claude/worktrees/` in every worktree of the fixture, as a real clone may."""
        self.exclude(primary, "**/.claude/worktrees/")

    def sibling_holding_a_live_nested_worktree(self) -> tuple[Path, Path, Path]:
        """P, then P-work, then P-work/.claude/worktrees/h with a file only h holds."""
        primary = self.primary()
        work = self.worktree(primary, self.base / "P-work", "work")
        h = self.worktree(work, work / ".claude" / "worktrees" / "h", "h")
        (h / "live.txt").write_text("a session is writing here\n", encoding="utf-8")
        return primary, work, h

    def assert_untouched(self, primary: Path, work: Path, *nested: Path) -> None:
        """The nested worktrees first, so a red run names the loss rather than the symptom."""
        now = self.registered(primary)
        for n in nested:
            self.assertTrue(
                n.is_dir(),
                f"{n} is gone. remove.ps1 deleted a registered worktree nested inside its target, "
                "which is the silent loss this file exists for.",
            )
            self.assertIn(fold(n), now, f"{n} is no longer registered")
            self.assertFalse(now[fold(n)], f"{n} is registered with no directory (prunable)")
        self.assertTrue(work.is_dir(), "the refused target was removed anyway")

    # --- the defect ------------------------------------------------------------------------------

    def test_a_sibling_holding_a_nested_worktree_is_refused_and_nothing_is_lost(self):
        primary, work, h = self.sibling_holding_a_live_nested_worktree()

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/")

        self.assert_untouched(primary, work, h)
        self.assertTrue((h / "live.txt").is_file(), "the nested worktree's own file is gone")
        self.assertNotEqual(
            0, r.returncode,
            "remove.ps1 exited 0 on a worktree that contains another registered worktree.\n" + said,
        )
        self.assertIn(fold(h), said.lower(), "the refusal does not name the nested worktree")

    def test_force_and_delete_branch_do_not_override_the_refusal(self):
        """-Force means "discard uncommitted tracked changes". It must not also mean this."""
        primary, work, h = self.sibling_holding_a_live_nested_worktree()

        r = self.remove(primary, "work", "-Force", "-DeleteBranch")

        self.assert_untouched(primary, work, h)
        self.assertNotEqual(0, r.returncode, "-Force overrode the refusal\n" + r.stdout + r.stderr)
        self.assertIn("work", git("branch", "--format=%(refname:short)", cwd=primary).split())
        refs = git("for-each-ref", "--format=%(refname)", "refs/ccx/removed/", cwd=primary)
        self.assertEqual(
            "", refs.strip(),
            "a keep-ref was written, so the refusal came after the first write rather than first",
        )

    def test_every_nested_worktree_is_named_whatever_its_path_looks_like(self):
        """Two nested worktrees, and only one of them under `.claude/worktrees/`."""
        primary = self.primary()
        work = self.worktree(primary, self.base / "P-work", "work")
        harness = self.worktree(work, work / ".claude" / "worktrees" / "h1", "h1")
        plain = self.worktree(primary, work / "sub" / "h2", "h2")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()

        self.assert_untouched(primary, work, harness, plain)
        self.assertNotEqual(0, r.returncode, said)
        for n in (harness, plain):
            with self.subTest(nested=n.name):
                self.assertIn(fold(n), said, f"the refusal does not name {n}")

    def test_under_the_nested_layout_a_worktree_holding_another_is_refused(self):
        """The same loss one level down: a session in `.claude/worktrees/x` creates its own there."""
        primary = self.primary("nested")
        x = self.worktree(primary, primary / ".claude" / "worktrees" / "x", "x")
        y = self.worktree(x, x / ".claude" / "worktrees" / "y", "y")

        r = self.remove(primary, "x")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()

        self.assert_untouched(primary, x, y)
        self.assertNotEqual(0, r.returncode, said)
        self.assertIn(fold(y), said, "the refusal does not name the nested worktree")

    # --- the remedy it prints must not cause the loss it refuses ----------------------------------

    def remove_lines(self, said: str) -> list[str]:
        """The `git -C "..." worktree remove "..."` commands the refusal prints, and nothing else.

        Anchored on the printed shape, so git's own error text or a throw naming the command is not
        mistaken for a command the operator is told to run.
        """
        return [
            line.strip() for line in said.splitlines()
            if line.strip().startswith('git -c "') and '" worktree remove "' in line
        ]

    PRINTED = re.compile(r'^git -C "([^"]+)" worktree (remove|unlock) "([^"]+)"$')

    def run_printed(self, r: subprocess.CompletedProcess) -> str:
        """Run every command the refusal printed, in order, as an operator following it would.

        Read from the output in its own case, because the fixture paths are case-sensitive off
        Windows. Returns a log of what ran, for the failure message.
        """
        log = []
        for line in (r.stdout + r.stderr).splitlines():
            m = self.PRINTED.match(line.strip())
            if not m:
                continue
            ran = subprocess.run(
                ["git", "-C", m.group(1), "worktree", m.group(2), m.group(3)],
                capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
            )
            log.append(f"ran: {line.strip()} -> exit {ran.returncode} {ran.stderr.strip()}")
        return "\n".join(log) or "(no command was printed)"

    def printed_for(self, said: str, n: Path) -> list[str]:
        """The remove commands printed for `n`. `said` is the folded, lower-cased output."""
        return [line for line in self.remove_lines(said) if line.endswith(fold(n) + '"')]

    def pointer_for(self, said: str, n: Path) -> list[str]:
        """The `git -C "<n>" ...` lines the refusal prints for the operator to look with."""
        return [line.strip() for line in said.splitlines() if line.strip().startswith(f'git -c "{fold(n)}" ')]

    def test_the_printed_commands_remove_the_deepest_worktree_first(self):
        """A parent removed before its child deletes the child when the child is ignored in it.

        `git worktree list` sorts by path, so `alpha` comes before `zeta`, which sits inside it. The
        commands must come out the other way round. The ignore rule makes `alpha` read clean, which
        is the case where running its command first would delete `zeta`.
        """
        primary = self.primary()
        self.ignore_nested(primary)
        work = self.worktree(primary, self.base / "P-work", "work")
        alpha = self.worktree(work, work / ".claude" / "worktrees" / "alpha", "alpha")
        zeta = self.worktree(alpha, alpha / ".claude" / "worktrees" / "zeta", "zeta")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()

        self.assert_untouched(primary, work, alpha, zeta)
        self.assertNotEqual(0, r.returncode, said)
        order = [
            next((i for i, line in enumerate(self.remove_lines(said)) if fold(n) + '"' in line), None)
            for n in (zeta, alpha)
        ]
        self.assertNotIn(None, order, "a nested worktree has no remove command:\n" + said)
        self.assertLess(order[0], order[1], "the parent's command comes before its child's:\n" + said)

    def test_a_locked_nested_worktree_is_named_with_its_unlock_step(self):
        primary = self.primary()
        work = self.worktree(primary, self.base / "P-work", "work")
        head = git("rev-parse", "HEAD", cwd=primary).strip()
        held = work / ".claude" / "worktrees" / "held"
        git("worktree", "add", "-q", "--detach", str(held), head, cwd=work)
        git("worktree", "lock", "--reason", "harness", str(held), cwd=primary)

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()

        self.assert_untouched(primary, work, held)
        self.assertNotEqual(0, r.returncode, said)
        self.assertIn("locked: harness", said)
        self.assertIn(f'worktree unlock "{fold(held)}"', said, "no unlock step for a locked worktree")
        self.assertNotIn("branch (detached)", said, "a detached worktree is labelled as a branch")

    def test_a_nested_worktree_holding_work_gets_no_remove_command(self):
        """Plain `git worktree remove` exits 128 on untracked files, and `--force` is the loss."""
        primary, work, h = self.sibling_holding_a_live_nested_worktree()

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()

        self.assert_untouched(primary, work, h)
        self.assertNotEqual(0, r.returncode, said)
        self.assertEqual(
            [], [line for line in self.remove_lines(said) if fold(h) + '"' in line],
            "the refusal prints a remove command for a worktree holding untracked work. git refuses "
            "it with exit 128, and the next thing an operator tries is --force.\n" + said,
        )
        self.assertEqual(
            [], [line for line in said.splitlines() if line.strip().startswith("git ") and "--force" in line],
            "--force is printed as a step to run\n" + said,
        )
        self.assertIn(f'git -c "{fold(h)}" status', said, "no pointer to look at the work first")

    def test_a_parent_gets_no_command_while_an_ignored_child_holds_work(self):
        """`alpha` reads clean because `zeta` is ignored inside it, and removing it deletes `zeta`."""
        primary = self.primary()
        self.ignore_nested(primary)
        work = self.worktree(primary, self.base / "P-work", "work")
        alpha = self.worktree(work, work / ".claude" / "worktrees" / "alpha", "alpha")
        zeta = self.worktree(alpha, alpha / ".claude" / "worktrees" / "zeta", "zeta")
        (zeta / "live.txt").write_text("a session is writing here\n", encoding="utf-8")
        self.assertEqual("", git("status", "--porcelain", cwd=alpha).strip(), "precondition: alpha reads clean")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()

        self.assert_untouched(primary, work, alpha, zeta)
        self.assertNotEqual(0, r.returncode, said)
        printed = self.remove_lines(said)
        for n in (alpha, zeta):
            with self.subTest(nested=n.name):
                self.assertEqual(
                    [], [line for line in printed if fold(n) + '"' in line],
                    f"a remove command is printed for {n.name}, and running it deletes zeta's work\n" + said,
                )

    # --- what plain `git status` does not show ----------------------------------------------------
    #
    # Each case builds a nested worktree that plain `git status --porcelain` calls clean, asserts
    # that as a precondition, then RUNS whatever the refusal printed. The loss is the assertion, so
    # a red run names the work that went, not a missing line of text.

    def nested_in_work(self, detach: bool = False) -> tuple[Path, Path, Path]:
        """P, then P-work, then P-work/.claude/worktrees/h, clean and on its own branch or detached."""
        primary = self.primary()
        work = self.worktree(primary, self.base / "P-work", "work")
        h = work / ".claude" / "worktrees" / "h"
        if detach:
            git("worktree", "add", "-q", "--detach", str(h), "HEAD", cwd=work)
        else:
            self.worktree(work, h, "h")
        return primary, work, h

    def test_an_untracked_file_a_local_setting_hides_gets_no_command(self):
        """`status.showUntrackedFiles=no` hides it, and `git worktree remove` then deletes it."""
        primary, work, h = self.nested_in_work()
        (h / "notes.txt").write_text("a session wrote this and never added it\n", encoding="utf-8")
        git("config", "status.showUntrackedFiles", "no", cwd=primary)
        self.assertEqual("", git("status", "--porcelain", cwd=h).strip(), "precondition: the setting hides it")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertTrue(
            (h / "notes.txt").is_file(),
            "following the printed commands deleted an untracked file that status.showUntrackedFiles=no "
            f"hid from the clean check\n{ran}\n{said}",
        )
        self.assertEqual([], self.printed_for(said, h), said)
        self.assertTrue(
            any("--untracked-files=all" in p for p in self.pointer_for(said, h)),
            "the pointer is plain `git status`, which the same setting blinds\n" + said,
        )

    def test_a_detached_nested_worktree_holding_commits_no_ref_holds_gets_no_command(self):
        """Its commits are on no branch, tag or other ref, so removing it leaves them to gc."""
        primary, work, h = self.nested_in_work(detach=True)
        (h / "b.txt").write_text("committed on a detached HEAD\n", encoding="utf-8")
        git("add", "b.txt", cwd=h)
        git("commit", "-qm", "detached work", cwd=h)
        sha = git("rev-parse", "HEAD", cwd=h).strip()
        self.assertEqual("", git("status", "--porcelain", cwd=h).strip(), "precondition: it reads clean")
        self.assertEqual("", git("for-each-ref", "--contains", sha, cwd=primary).strip(), "precondition: no ref")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        held = git("for-each-ref", "--contains", sha, cwd=primary).strip()
        still_there = fold(h) in self.registered(primary) and git("rev-parse", "HEAD", cwd=h).strip() == sha
        self.assertTrue(
            held or still_there,
            f"following the printed commands left commit {sha} on no ref and in no worktree, so the "
            f"next gc can delete it\n{ran}\n{said}",
        )
        self.assertEqual([], self.printed_for(said, h), said)
        self.assertIn(sha[:12], said, "the refusal does not name the commit at risk")

    def test_control_a_detached_nested_worktree_whose_commit_a_ref_holds_gets_its_command(self):
        """Every ref type counts. `git branch --contains` cannot see a tag, so a check built on it fails here."""
        top = self.base
        for ref in ("refs/tags/keep", "refs/ccx/removed/keep", "refs/remotes/origin/keep"):
            with self.subTest(ref=ref):
                # A fresh repository per ref, so one case's removal cannot pass the next.
                self.base = top / ref.split("/")[1]
                self.base.mkdir()
                primary, work, h = self.nested_in_work(detach=True)
                (h / "b.txt").write_text("committed on a detached HEAD\n", encoding="utf-8")
                git("add", "b.txt", cwd=h)
                git("commit", "-qm", "detached work", cwd=h)
                sha = git("rev-parse", "HEAD", cwd=h).strip()
                git("update-ref", ref, sha, cwd=primary)

                r = self.remove(primary, "work")
                said = (r.stdout + r.stderr).replace("\\", "/").lower()
                ran = self.run_printed(r)

                self.assertNotEqual(0, r.returncode, said)
                self.assertEqual(1, len(self.printed_for(said, h)), f"{ref} holds the commit, so a command is due\n{said}")
                self.assertFalse(h.exists(), f"the printed command did not remove it\n{ran}")
                self.assertIn(ref, git("for-each-ref", "--contains", sha, "--format=%(refname)", cwd=primary))

    def test_an_ignored_file_in_a_nested_worktree_gets_no_command(self):
        """`git worktree remove` deletes ignored files without asking. This repo ignores `*.local.*`."""
        primary, work, h = self.nested_in_work()
        self.exclude(primary, "*.local.*")
        (h / ".claude").mkdir(exist_ok=True)
        (h / ".claude" / "seat.local.txt").write_text("builder", encoding="utf-8")
        self.assertEqual("", git("status", "--porcelain", cwd=h).strip(), "precondition: git status hides it")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertTrue(
            (h / ".claude" / "seat.local.txt").is_file(),
            f"following the printed commands deleted an ignored file\n{ran}\n{said}",
        )
        self.assertEqual([], self.printed_for(said, h), said)
        self.assertTrue(
            any("--ignored" in p for p in self.pointer_for(said, h)),
            "the pointer does not say to look with --ignored, and plain `git status` hides the file\n" + said,
        )

    def test_control_a_clean_nested_worktree_gets_a_command_that_works(self):
        """A fix that prints NO COMMAND for everything fails here. So does a command that does not run."""
        primary, work, h = self.nested_in_work()

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        self.assertNotEqual(0, r.returncode, said)
        self.assertEqual(1, len(self.printed_for(said, h)), "a clean nested worktree got no command\n" + said)

        ran = self.run_printed(r)
        self.assertFalse(h.exists(), f"the printed command did not remove it\n{ran}")
        self.assertNotIn(fold(h), self.registered(primary), ran)

        again = self.remove(primary, "work")
        self.assertEqual(0, again.returncode, "the re-run the refusal asks for failed\n" + again.stdout + again.stderr)
        self.assertFalse(work.exists())

    # --- a name that is not a registered worktree ---------------------------------------------------

    def test_dot_and_dot_dot_are_refused_before_the_nested_check(self):
        """`-Name .` and `-Name ..` pass the pattern. Under `nested` they reach every worktree."""
        top = self.base
        for layout in ("sibling", "nested"):
            for name in (".", ".."):
                with self.subTest(layout=layout, name=name):
                    # A fresh repository per case, so one case's removal cannot pass the next.
                    self.base = top / f"{layout}-{len(name)}"
                    self.base.mkdir()
                    primary = self.primary(layout)
                    root = primary / ".claude" / "worktrees" if layout == "nested" else self.base
                    prefix = "" if layout == "nested" else "P-"
                    a = self.worktree(primary, root / f"{prefix}a", "a")
                    b = self.worktree(primary, root / f"{prefix}b", "b")
                    (b / "live.txt").write_text("a session is writing here\n", encoding="utf-8")

                    r = self.remove(primary, name)
                    said = (r.stdout + r.stderr).replace("\\", "/").lower()

                    now = self.registered(primary)
                    for n in (a, b):
                        self.assertTrue(n.is_dir(), f"{n} is gone after remove.ps1 -Name {name}")
                        self.assertIn(fold(n), now)
                    self.assertTrue((b / "live.txt").is_file())
                    self.assertNotEqual(0, r.returncode, said)
                    self.assertEqual(
                        [], self.remove_lines(said),
                        f"remove.ps1 -Name {name} printed commands to delete other worktrees\n" + said,
                    )
                    self.assertNotIn("registered worktree(s)", said, "the nested check ran on a non-worktree")
                    if layout == "nested":
                        # The path exists here, so this refusal is the one that must answer.
                        self.assertIn("not a registered worktree", said, said)

    # --- the controls: a fix that refuses everything fails these ----------------------------------

    def test_control_a_sibling_with_nothing_nested_is_removed(self):
        primary = self.primary()
        work = self.worktree(primary, self.base / "P-work", "work")

        r = self.remove(primary, "work")

        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertFalse(work.exists(), "a plain removal left the directory behind")
        self.assertNotIn(fold(work), self.registered(primary))

    def test_control_a_nested_layout_worktree_is_removed_and_its_neighbour_survives(self):
        """Refusing `.claude/worktrees/` by shape would leave the `nested` layout no teardown.

        The neighbour `x-2` shares the prefix `x`, so a containment test without the trailing
        separator would count it as nested inside `x` and refuse.
        """
        primary = self.primary("nested")
        x = self.worktree(primary, primary / ".claude" / "worktrees" / "x", "x")
        neighbour = self.worktree(primary, primary / ".claude" / "worktrees" / "x-2", "x-2")

        r = self.remove(primary, "x")

        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertFalse(x.exists(), "the named nested-layout worktree was not removed")
        now = self.registered(primary)
        self.assertNotIn(fold(x), now)
        self.assertTrue(neighbour.is_dir(), "removing x took its neighbour x-2 with it")
        self.assertIn(fold(neighbour), now)
        self.assertFalse(now[fold(neighbour)])


if __name__ == "__main__":
    unittest.main()
