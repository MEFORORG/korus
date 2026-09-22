"""`remove.ps1` refuses a worktree that contains another registered worktree.

THE FAILURE THIS EXISTS FOR. `remove.ps1` runs `git worktree remove --force`, which deletes the
whole directory tree. A nested checkout is git-ignored inside its parent, so the parent reads clean
and nothing stopped it. Measured 2026-09-22 with git 2.55.0.windows.5, under the `sibling` layout:
removing `P-work` also deleted `P-work/.claude/worktrees/h`, exited 0, and left `h` registered as
prunable. A session started inside a sibling worktree creates its own worktrees there, so the
checkout deleted can be a live session's. CLAUDE.md sends every session through this script.

WHAT THESE CASES PROVE, AND HOW. They RUN the real script against throwaway repositories. The six
refusal cases fail on the unfixed script at `05eb4a7`: the removal exits 0 and the nested checkout
is gone. They cover both layouts, a nested path not under `.claude/worktrees/`, and `-Force`.

Two of them hold the REMEDY the refusal prints. Its commands must remove the deepest worktree
first, because `git worktree remove` deletes ignored files and a nested worktree is usually ignored
inside its parent. And a locked worktree must come with its unlock step.

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
        return [line.strip() for line in said.splitlines() if " worktree remove " in line]

    def test_the_printed_commands_remove_the_deepest_worktree_first(self):
        """A parent removed before its child deletes the child: it is ignored inside the parent.

        `alpha` is created first, so `git worktree list` reports it before `zeta`, which sits inside
        it. The commands must come out the other way round.
        """
        primary = self.primary()
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
