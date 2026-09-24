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
an export of `05eb4a7`, this file as it stood at `a58981d` returns `10 failed, 3 passed, 2 subtests
passed`. Every case fails there except the two controls and the two `sibling` subtests of the `.`
and `..` case. They cover both layouts, a nested path not under `.claude/worktrees/`, and `-Force`.

Most of the rest hold the REMEDY the refusal prints, which must not be a step that deletes work:

  * Commands come deepest first. `git worktree remove` without `--force` deletes ignored files, so
    a parent removed before an ignored child takes the child with it.
  * A nested worktree holding changed or untracked files gets no command. Plain `git worktree
    remove` exits 128 on it, and `--force` is the loss this file exists for.
  * Nor does a parent whose ignored child holds work, because the parent reads clean.
  * A locked worktree comes with its unlock step.
  * Nor does a nested worktree holding what plain `git status` does not show: an untracked file
    `status.showUntrackedFiles=no` hides, an ignored file, or commits on a detached HEAD that no ref
    holds. Those three cases RUN the printed commands and assert the work survived. Against an
    export of `a58981d`, this file as it stood at `3d778a0` returns `3 failed, 13 passed, 11
    subtests passed`, and those three are the failures. The file as it stood at `8f2e366` returns
    `6 failed, 17 passed, 11 subtests passed` there, as docs/WORKTREES.md publishes.
  * Nor does one holding a commit only its HEAD reflog keeps, or an edit to a skip-worktree file.
    The first review of the fix found both. Against an export of `fd7028f` those two cases fail,
    and so does the target guard's case below; nothing else in this file does.
  * A changed tracked file, another repository's checkout, and a parent's own file beside a clean
    child each withhold the command where they should, and only there.

RETRACTED 2026-09-23: the paragraph above said the remedy covered only what `git status` can see,
and that ignored files, hidden untracked files and a detached HEAD's commits were "not covered".
`remove.ps1`'s Get-RemovalLoss now withholds the command in each case.

THE TARGET'S OWN GUARD. It read `git status` and ignored the exit code, so a status that failed read
as no changes and the `--force` removal deleted uncommitted edits. One case corrupts the index and
requires a refusal.

AND ONE HAZARD THE FIX ITSELF OPENED. `-Name`'s pattern accepts `.` and `..`. Under the `nested`
layout those resolve to `.claude/worktrees` and `.claude`, which hold every harness worktree, and the
first cut of the refusal listed them all with commands to delete them. The target must be a
registered worktree before the nested check runs.

CONTROLS, because "refuse everything" passes every refusal case here, and "print no command"
passes every remedy case:

  * A plain sibling with nothing nested is still removed.
  * Under the `nested` layout, `.claude/worktrees/x` is still removed, and a neighbour called `x-2`
    is not mistaken for a child of it. The rule is containment, never path shape: under that layout
    every worktree these scripts create lives under `.claude/worktrees/`.
  * A clean nested worktree gets a command, the command runs, and the re-run then removes the target.
  * A detached nested worktree whose commit a tag, a keep-ref or a remote-tracking ref holds gets its
    command. `git branch --contains` sees no tag, so a check built on it fails here.
  * A nested worktree whose commit was amended away on its branch gets its command. The branch's own
    reflog keeps the original, so a reflog read that does not subtract it fails here.

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

    def remove(self, primary: Path, name: str, *flags: str, decode_as: str = "") -> subprocess.CompletedProcess:
        """Run remove.ps1. `decode_as` names the encoding pwsh reads git's output in, where a case
        depends on it: otherwise it is whatever console the test runner has, which differs by host."""
        env = dict(os.environ)
        # The developer's own settings must not reach the fixture.
        for leak in ("CCX_CONFIG", "CCX_TRUNK"):
            env.pop(leak, None)
        argv = [self.pwsh, "-NoProfile", "-File", str(t.WORKTREE_REMOVE), "-Name", name, *flags]
        if decode_as:
            argv = [self.pwsh, "-NoProfile", "-Command",
                    f"[Console]::OutputEncoding = [Text.Encoding]::{decode_as}; "
                    f"& '{t.WORKTREE_REMOVE}' -Name {name} {' '.join(flags)}; exit $LASTEXITCODE"]
        # cwd is the primary: remove.ps1 refuses to remove the checkout it is standing in.
        return subprocess.run(
            argv, capture_output=True, text=True, env=env, cwd=str(primary), timeout=TIMEOUT_SECONDS,
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

    # One printed argument. The script prints single quotes since the `$` fix and printed double
    # quotes before it. Both are read, so a red run against an older script names the loss and not
    # the quoting.
    ARG = r"""(?:"[^"]*"|'(?:[^']|'')*')"""
    ARGS = re.compile(r""""([^"]*)"|'((?:[^']|'')*)'""")

    def args_of(self, line: str) -> list[str]:
        """The quoted arguments of a printed line, unquoted."""
        return [d if d is not None else s.replace("''", "'") for d, s in
                ((m.group(1), m.group(2)) for m in self.ARGS.finditer(line))]

    def remove_lines(self, said: str) -> list[str]:
        """The `git -C <path> worktree remove <path>` commands the refusal prints, and nothing else.

        Anchored on the printed shape, so git's own error text or a throw naming the command is not
        mistaken for a command the operator is told to run.
        """
        return [
            line.strip() for line in said.splitlines()
            if re.match(rf"^git -c {self.ARG} worktree remove {self.ARG}$", line.strip())
        ]

    def run_printed(self, r: subprocess.CompletedProcess) -> str:
        """Run every command the refusal printed, in order, as an operator following it would.

        Each line runs in pwsh, as typed, so its quoting is part of what is tested. Read from the
        output in its own case, because the fixture paths are case-sensitive off Windows. Returns a
        log of what ran, for the failure message.
        """
        log = []
        printed = re.compile(rf"^git -C {self.ARG} worktree (remove|unlock) {self.ARG}$")
        for line in (r.stdout + r.stderr).splitlines():
            if not printed.match(line.strip()):
                continue
            ran = subprocess.run(
                [self.pwsh, "-NoProfile", "-NonInteractive", "-Command", line.strip()],
                capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
            )
            log.append(f"ran: {line.strip()} -> exit {ran.returncode} {ran.stderr.strip()}")
        return "\n".join(log) or "(no command was printed)"

    def printed_for(self, said: str, n: Path) -> list[str]:
        """The remove commands printed for `n`. `said` is the folded, lower-cased output."""
        return [line for line in self.remove_lines(said) if self.args_of(line)[-1:] == [fold(n)]]

    def pointer_for(self, said: str, n: Path) -> list[str]:
        """The `git -C <n> ...` lines the refusal prints for the operator to look with."""
        return [
            line.strip() for line in said.splitlines()
            if line.strip().startswith("git -c ") and self.args_of(line)[:1] == [fold(n)]
        ]

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
            next((i for i, line in enumerate(self.remove_lines(said)) if self.args_of(line)[-1:] == [fold(n)]), None)
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
        unlocks = [line for line in said.splitlines() if " worktree unlock " in line]
        self.assertTrue(
            any(self.args_of(line)[-1:] == [fold(held)] for line in unlocks),
            "no unlock step for a locked worktree\n" + said,
        )
        self.assertNotIn("branch (detached)", said, "a detached worktree is labelled as a branch")

    def test_a_nested_worktree_holding_work_gets_no_remove_command(self):
        """Plain `git worktree remove` exits 128 on untracked files, and `--force` is the loss."""
        primary, work, h = self.sibling_holding_a_live_nested_worktree()

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()

        self.assert_untouched(primary, work, h)
        self.assertNotEqual(0, r.returncode, said)
        self.assertEqual(
            [], self.printed_for(said, h),
            "the refusal prints a remove command for a worktree holding untracked work. git refuses "
            "it with exit 128, and the next thing an operator tries is --force.\n" + said,
        )
        self.assertEqual(
            [], [line for line in said.splitlines() if line.strip().startswith("git ") and "--force" in line],
            "--force is printed as a step to run\n" + said,
        )
        self.assertTrue(
            any(" status " in p for p in self.pointer_for(said, h)), "no pointer to look at the work first\n" + said
        )

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
        for n in (alpha, zeta):
            with self.subTest(nested=n.name):
                self.assertEqual(
                    [], self.printed_for(said, n),
                    f"a remove command is printed for {n.name}, and running it deletes zeta's work\n" + said,
                )

    def test_a_dollar_sign_in_a_path_does_not_send_a_printed_command_elsewhere(self):
        """Double quotes let PowerShell expand `$name`, so a printed command ran on another path.

        A decoy clone sits where `d$ccx165` lands once `$ccx165` expands to nothing. At 06e8ca3 the
        printed command, run in pwsh, removed the decoy's worktree and left the named one.
        """
        top = self.base
        self.base = top / "d"
        self.base.mkdir()
        _, _, decoy = self.nested_in_work()
        self.base = top / "d$ccx165"
        self.base.mkdir()
        primary, work, h = self.nested_in_work()

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertEqual(1, len(self.printed_for(said, h)), "a clean nested worktree got no command\n" + said)
        self.assertTrue(decoy.is_dir(), f"the printed command removed another clone's worktree\n{ran}\n{said}")
        self.assertFalse(h.exists(), f"the printed command did not remove the worktree it names\n{ran}")

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
            any(re.search(r"--untracked-files=(all|normal)\b", p) for p in self.pointer_for(said, h)),
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

    def test_a_commit_only_the_nested_worktrees_reflog_holds_gets_no_command(self):
        """Committed on a detached HEAD, then back on its branch: only this worktree's HEAD reflog holds it."""
        primary, work, h = self.nested_in_work()
        git("checkout", "-q", "--detach", cwd=h)
        (h / "b.txt").write_text("left behind on a detached HEAD\n", encoding="utf-8")
        git("add", "b.txt", cwd=h)
        git("commit", "-qm", "left behind", cwd=h)
        sha = git("rev-parse", "HEAD", cwd=h).strip()
        git("switch", "-q", "h", cwd=h)
        self.assertEqual("", git("for-each-ref", "--contains", sha, cwd=primary).strip(), "precondition: no ref")
        self.assertEqual("", git("status", "--porcelain", cwd=h).strip(), "precondition: it reads clean")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertIn(
            sha, git("reflog", "--format=%H", cwd=h) if h.is_dir() else "",
            f"following the printed commands deleted the only reflog holding commit {sha}\n{ran}\n{said}",
        )
        self.assertEqual([], self.printed_for(said, h), said)
        self.assertTrue(any(p.endswith(" reflog") for p in self.pointer_for(said, h)), "no reflog pointer\n" + said)

    def test_control_a_commit_amended_away_on_a_branch_still_gets_a_command(self):
        """The branch's own reflog keeps the original, and it outlives the worktree. A plain reflog read fails here."""
        primary, work, h = self.nested_in_work()
        (h / "b.txt").write_text("first try\n", encoding="utf-8")
        git("add", "b.txt", cwd=h)
        git("commit", "-qm", "first try", cwd=h)
        git("commit", "-q", "--amend", "-m", "second try", cwd=h)

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()

        self.assertNotEqual(0, r.returncode, said)
        self.assertEqual(1, len(self.printed_for(said, h)), "an amend on a branch withheld the command\n" + said)

    def test_an_edit_a_skip_worktree_flag_hides_gets_no_command(self):
        """`git status` does not check a skip-worktree file, so a local override reads as clean."""
        primary, work, h = self.nested_in_work()
        git("update-index", "--skip-worktree", "a.txt", cwd=h)
        (h / "a.txt").write_text("a local override\n", encoding="utf-8")
        self.assertEqual("", git("status", "--porcelain", cwd=h).strip(), "precondition: git status hides it")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertTrue(
            (h / "a.txt").is_file() and "override" in (h / "a.txt").read_text(encoding="utf-8"),
            f"following the printed commands deleted an edit a skip-worktree flag hid\n{ran}\n{said}",
        )
        self.assertEqual([], self.printed_for(said, h), said)

    def test_a_skip_worktree_edit_to_a_non_ascii_name_gets_no_command_under_quote_path_false(self):
        """`core.quotePath=false` makes git print the name raw, and pwsh decodes it in the console's
        code page. Where that is not UTF-8 the name came out wrong, the file read as absent, and the
        flag did not count. Measured 2026-09-23 at 06e8ca3: red under code page 437, green under
        65001. So this case pins the decoding to Latin-1 rather than trust the runner's console."""
        primary = self.primary()
        name = "\u00e9.txt"
        (primary / name).write_text("tracked\n", encoding="utf-8")
        git("add", "-A", cwd=primary)
        git("commit", "-qm", "a non-ASCII name", cwd=primary)
        work = self.worktree(primary, self.base / "P-work", "work")
        h = self.worktree(work, work / ".claude" / "worktrees" / "h", "h")
        git("update-index", "--skip-worktree", name, cwd=h)
        (h / name).write_text("a local override\n", encoding="utf-8")
        git("config", "core.quotePath", "false", cwd=primary)
        self.assertEqual("", git("status", "--porcelain", cwd=h).strip(), "precondition: git status hides it")

        r = self.remove(primary, "work", decode_as="Latin1")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertTrue(
            (h / name).is_file() and "override" in (h / name).read_text(encoding="utf-8"),
            f"following the printed commands deleted an edit a skip-worktree flag hid\n{ran}\n{said}",
        )
        self.assertEqual([], self.printed_for(said, h), said)

    def test_a_nested_worktree_with_a_changed_tracked_file_gets_no_command(self):
        primary, work, h = self.nested_in_work()
        (h / "a.txt").write_text("edited and not committed\n", encoding="utf-8")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertIn("edited", (h / "a.txt").read_text(encoding="utf-8"), ran)
        self.assertEqual([], self.printed_for(said, h), said)

    def test_another_repository_inside_a_nested_worktree_gets_no_command(self):
        """It shows as one `<dir>/` entry, as a nested worktree does, but no command of ours removes it first."""
        primary, work, h = self.nested_in_work()
        other = h / "vendor" / "lib"
        other.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=other)
        (other / "x.txt").write_text("another repository's file\n", encoding="utf-8")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertTrue((other / "x.txt").is_file(), f"the other repository went with its parent\n{ran}\n{said}")
        self.assertEqual([], self.printed_for(said, h), said)

    def test_a_parent_holding_its_own_file_is_withheld_while_its_clean_child_is_not(self):
        """Only the child's own `<dir>/` entry is excused from the parent's count, not the parent's files."""
        primary = self.primary()
        self.ignore_nested(primary)
        work = self.worktree(primary, self.base / "P-work", "work")
        alpha = self.worktree(work, work / ".claude" / "worktrees" / "alpha", "alpha")
        zeta = self.worktree(alpha, alpha / ".claude" / "worktrees" / "zeta", "zeta")
        (alpha / "notes.txt").write_text("alpha's own work\n", encoding="utf-8")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        self.assertEqual(1, len(self.printed_for(said, zeta)), "the clean child got no command\n" + said)
        self.assertEqual([], self.printed_for(said, alpha), "the parent's own file did not withhold it\n" + said)

        ran = self.run_printed(r)
        self.assertFalse(zeta.exists(), ran)
        self.assertTrue((alpha / "notes.txt").is_file(), ran)

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

    # --- where plain `git worktree remove` exits 128 whatever the worktree holds -------------------

    def with_a_submodule(self, check_out: bool) -> tuple[Path, Path, Path]:
        """P with a submodule `sub`, then P-work, then P-work/.claude/worktrees/h, clean."""
        src = self.base / "subsrc"
        src.mkdir()
        git("init", "-q", "-b", "main", cwd=src)
        (src / "s.txt").write_text("the submodule's file\n", encoding="utf-8")
        git("add", "-A", cwd=src)
        git("commit", "-qm", "sub init", cwd=src)
        primary = self.primary()
        # A local path is a `file` transport, which git refuses for a submodule by default.
        git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(src), "sub", cwd=primary)
        git("commit", "-qm", "add sub", cwd=primary)
        work = self.worktree(primary, self.base / "P-work", "work")
        h = self.worktree(work, work / ".claude" / "worktrees" / "h", "h")
        if check_out:
            git("-c", "protocol.file.allow=always", "submodule", "update", "--init", "-q", cwd=h)
        self.assertEqual("", git("status", "--porcelain", cwd=h).strip(), "precondition: it reads clean")
        return primary, work, h

    def test_a_nested_worktree_holding_a_submodule_gets_no_command(self):
        """git refuses to remove a worktree holding a submodule, clean or not, and forcing it deletes
        the submodule's repository. Red at 06e8ca3: a command was printed, and it exited 128."""
        primary, work, h = self.with_a_submodule(check_out=True)

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertTrue((h / "sub" / "s.txt").is_file(), ran)
        self.assertEqual(
            [], self.printed_for(said, h),
            "a command is printed that git refuses for a worktree holding a submodule, and the next "
            f"try is --force\n{ran}\n{said}",
        )
        self.assertTrue(any(" submodule " in p for p in self.pointer_for(said, h)), "no pointer into the submodule\n" + said)

    def test_control_a_nested_worktree_whose_submodule_is_not_checked_out_gets_its_command(self):
        """An uninitialised submodule is an empty directory, and git removes the worktree."""
        primary, work, h = self.with_a_submodule(check_out=False)

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        self.assertEqual(1, len(self.printed_for(said, h)), "an empty submodule directory withheld the command\n" + said)

        ran = self.run_printed(r)
        self.assertFalse(h.exists(), f"the printed command did not remove it\n{ran}")

    def test_a_prunable_nested_worktree_whose_directory_holds_files_gets_no_command(self):
        """Its `.git` file is gone, so git calls it prunable while its files are still there.

        Red at 06e8ca3: the refusal called the directory "already missing" and printed a command
        that exits 128 with or without --force. `git worktree prune` gets past that, and the next
        removal of the parent then deletes the files. The repair step it prints now deletes nothing,
        and the re-run then reads the file.
        """
        primary, work, h = self.nested_in_work()
        (h / "notes.txt").write_text("a session wrote this\n", encoding="utf-8")
        (h / ".git").unlink()
        self.assertTrue(self.registered(primary)[fold(h)], "precondition: git calls it prunable")

        r = self.remove(primary, "work")
        said = (r.stdout + r.stderr).replace("\\", "/").lower()
        ran = self.run_printed(r)

        self.assertNotEqual(0, r.returncode, said)
        self.assertTrue((h / "notes.txt").is_file(), ran)
        self.assertEqual([], self.printed_for(said, h), f"a command is printed that git refuses\n{ran}\n{said}")
        self.assertNotIn("directory already missing", said, "the refusal calls a directory holding files missing")
        repair = [line.strip() for line in said.splitlines() if line.strip().endswith(" worktree repair")]
        self.assertEqual(1, len(repair), "no repair step\n" + said)

        subprocess.run(
            [self.pwsh, "-NoProfile", "-NonInteractive", "-Command",
             next(line.strip() for line in (r.stdout + r.stderr).splitlines() if line.strip().lower() == repair[0])],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        )
        again = self.remove(primary, "work")
        said = (again.stdout + again.stderr).replace("\\", "/").lower()
        self.assertFalse(self.registered(primary)[fold(h)], "the printed repair step did not restore the link")
        self.assertEqual([], self.printed_for(said, h), said)
        self.assertIn("untracked", said, "after the repair the re-run does not read the file\n" + said)

    # --- the target's own guard ---------------------------------------------------------------------

    def test_a_target_whose_status_fails_is_refused_without_force(self):
        """The old guard ignored git's exit code, so a failed status read as no changes and --force ran."""
        primary = self.primary()
        work = self.worktree(primary, self.base / "P-work", "work")
        (work / "a.txt").write_text("edited and not committed\n", encoding="utf-8")
        index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index", cwd=work).strip())
        index.write_bytes(b"not an index")

        r = self.remove(primary, "work")

        self.assertTrue(work.is_dir(), "the worktree was removed although its status could not be read\n" + r.stdout + r.stderr)
        self.assertIn("edited", (work / "a.txt").read_text(encoding="utf-8"))
        self.assertNotEqual(0, r.returncode, r.stdout + r.stderr)

    def test_force_on_a_target_whose_status_fails_says_so(self):
        """-Force still discards what git status could not read. Red at 06e8ca3: it said nothing."""
        primary = self.primary()
        work = self.worktree(primary, self.base / "P-work", "work")
        index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index", cwd=work).strip())
        index.write_bytes(b"not an index")

        r = self.remove(primary, "work", "-Force")
        said = (r.stdout + r.stderr).lower()

        self.assertEqual(0, r.returncode, said)
        self.assertIn("git status failed", said, "-Force skipped a failed status without a word")

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

    def test_a_trailing_dot_does_not_resolve_to_another_worktree(self):
        """Windows drops a trailing dot, so `-Name a.` read as worktree `a` and removed it, exit 0.

        Red at 06e8ca3 on Windows. Elsewhere `P-a.` is its own path and does not exist here, so this
        case passes there before and after the fix.
        """
        top = self.base
        for layout in ("sibling", "nested"):
            with self.subTest(layout=layout):
                self.base = top / layout
                self.base.mkdir()
                primary = self.primary(layout)
                a = (primary / ".claude" / "worktrees" / "a") if layout == "nested" else (self.base / "P-a")
                self.worktree(primary, a, "a")
                (a / "live.txt").write_text("a session is writing here\n", encoding="utf-8")

                r = self.remove(primary, "a.", "-DeleteBranch")
                said = r.stdout + r.stderr

                self.assertTrue((a / "live.txt").is_file(), f"-Name a. removed worktree a\n{said}")
                self.assertIn(fold(a), self.registered(primary), said)
                self.assertNotEqual(0, r.returncode, said)
                self.assertIn("a", git("branch", "--format=%(refname:short)", cwd=primary).split())

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
