"""The reaper must not delete a commit that only the worktree it removes holds.

THE FAILURE THIS EXISTS FOR. `prune-merged.ps1 -Apply` removes a merged, idle sibling with
`git worktree remove --force`. That deletes the worktree's HEAD reflog and its own per-worktree refs
(`refs/worktree/*`, `refs/bisect/*`, `refs/rewritten/*`). A session that committed on a detached HEAD
and then switched back to its branch leaves that commit held by the HEAD reflog alone. Measured
2026-09-23 against 06e8ca3, with git 2.55.0.windows.5: the reaper pruned such a sibling, and after
it `git fsck --unreachable --no-reflogs` listed the commit, which no ref and no reflog held.
Against the same export, both subtests in this file fail on the loss itself.

Both removers now read this through one function, `Get-WorktreeOnlyCommits` in
`scripts/coord/occupancy.ps1`. The reaper's clean check counts what it returns as a reason to skip.

WHICH WAY THE PER-WORKTREE REFS COUNT. A worktree's own `refs/worktree/*` are deleted with it, so they
put a commit at risk and never hold it. The primary's survive, so they hold. Reading the holders from
the worktree itself would count its own refs as holders, which is the unsafe direction. The second
case plants a commit only the sibling's `refs/worktree/keep` holds.

A CONTROL IN THE SAME RUN. A clean sibling beside them is still pruned, so a reaper that skips
everything fails too. And its branch was amended once, so a check that forgot to subtract each
branch's own reflog would skip it.

Run: python -m pytest tests -q     (or: python -m unittest discover -s tests -v)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 180

GIT_ID = (
    "-c", "user.email=ccx@test", "-c", "user.name=ccx test",
    "-c", "commit.gpgsign=false", "-c", "advice.detachedHead=false",
)

REAPER = t.REPO_ROOT / "scripts" / "worktree" / "prune-merged.ps1"


def git(*args: str, cwd: Path) -> str:
    r = subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True,
                       timeout=TIMEOUT_SECONDS)
    if r.returncode != 0:
        raise AssertionError(f"fixture setup failed: git {' '.join(args)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


class TheReaperKeepsCommitsOnlyAWorktreeHolds(unittest.TestCase):
    def setUp(self):
        self.pwsh = t.find_pwsh()
        if not self.pwsh:
            self.skipTest("pwsh is not on PATH, so prune-merged.ps1 cannot be executed here")
        if not shutil.which("git"):
            self.skipTest("git is not on PATH, so the fixture repository cannot be built")
        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-onlyhere-", ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()

    def fixture(self) -> tuple[Path, Path, dict[str, str]]:
        """Three merged siblings. `reflog` and `ownref` each hold one commit nothing else holds."""
        primary = self.base / "primary"
        primary.mkdir()
        git("init", "-q", "-b", "main", cwd=primary)
        (primary / "ccx.config.json").write_text(
            json.dumps({"prefix": "ccx", "trunk": "main", "worktreeLayout": "sibling"}), encoding="utf-8")
        (primary / "README.md").write_text("fixture\n", encoding="utf-8")
        git("add", "-A", cwd=primary)
        git("commit", "-qm", "init", cwd=primary)
        for name in ("reflog", "ownref", "clean"):
            wt = self.base / f"primary-{name}"
            git("worktree", "add", "-q", str(wt), "-b", f"feature/{name}", cwd=primary)
            (wt / f"{name}.txt").write_text("merged work\n", encoding="utf-8")
            git("add", "-A", cwd=wt)
            git("commit", "-qm", f"{name} work", cwd=wt)
            if name == "clean":
                git("commit", "-q", "--amend", "-m", f"{name} work, reworded", cwd=wt)
            git("merge", "-q", "--no-edit", f"feature/{name}", cwd=primary)

        held = {}
        # Committed on a detached HEAD, then back on the branch: only the HEAD reflog holds it.
        r = self.base / "primary-reflog"
        git("checkout", "-q", "--detach", cwd=r)
        (r / "lost.txt").write_text("left behind on a detached HEAD\n", encoding="utf-8")
        git("add", "lost.txt", cwd=r)
        git("commit", "-qm", "left behind", cwd=r)
        held["primary-reflog"] = git("rev-parse", "HEAD", cwd=r).strip()
        git("switch", "-q", "feature/reflog", cwd=r)

        # A commit only this worktree's own refs/worktree/keep holds, in no reflog.
        o = self.base / "primary-ownref"
        tree = git("rev-parse", "HEAD^{tree}", cwd=o).strip()
        parent = git("rev-parse", "HEAD", cwd=o).strip()
        held["primary-ownref"] = git("commit-tree", tree, "-p", parent, "-m", "held by a per-worktree ref", cwd=o).strip()
        git("update-ref", "refs/worktree/keep", held["primary-ownref"], cwd=o)

        for leaf, sha in held.items():
            self.assertEqual("", git("for-each-ref", "--contains", sha, cwd=primary).strip(),
                             f"precondition: no ref the primary sees holds {leaf}'s commit")

        # Signal 2 satisfied honestly: backdate the admin directories, as the other reaper tests do.
        when = time.time() - 48 * 3600
        for admin in (primary / ".git" / "worktrees").iterdir():
            for f in list(admin.rglob("*")) + [admin]:
                os.utime(f, (when, when))

        roots = self.base / "roots"
        (roots / "sessions").mkdir(parents=True)
        (roots / "sessions" / "4242.json").write_text(
            json.dumps({"sessionId": "fixture-elsewhere", "pid": 4242, "cwd": str(self.base / "nowhere")}),
            encoding="utf-8",
        )
        return primary, roots, held

    def reap(self, primary: Path, roots: Path) -> dict:
        env = dict(os.environ)
        for leak in ("CCX_CONFIG", "CCX_TRUNK"):
            env.pop(leak, None)
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(REAPER), "-RepoRoot", str(primary),
             "-ConfigRoot", str(roots), "-SkipFetch", "-SkipGh", "-Json", "-Apply"],
            capture_output=True, text=True, env=env, cwd=str(primary), timeout=TIMEOUT_SECONDS,
        )
        self.assertTrue(r.stdout.strip(), f"no JSON receipt (exit {r.returncode}):\n{r.stderr}")
        return json.loads(r.stdout)

    def test_a_commit_only_the_sibling_holds_survives_the_prune(self):
        primary, roots, held = self.fixture()

        result = self.reap(primary, roots)
        rows = {c["Leaf"]: c for c in result["candidates"]}

        # Read from the sibling itself: `git fsck` in the primary does not count another worktree's
        # own refs as holders, so it lists `primary-ownref`'s commit whether or not the ref survived.
        holder = {"primary-reflog": ("log", "-g", "--format=%H", "HEAD"),
                  "primary-ownref": ("for-each-ref", "--format=%(objectname)", "refs/worktree/")}
        for leaf, sha in held.items():
            with self.subTest(sibling=leaf):
                wt = self.base / leaf
                self.assertIn(
                    sha, git(*holder[leaf], cwd=wt) if wt.is_dir() else "",
                    f"the reaper removed {leaf} and with it the only hold on commit {sha}. "
                    f"Its row: {rows.get(leaf)}",
                )
                self.assertEqual("SKIP", rows[leaf]["Decision"], rows[leaf])
                self.assertIn("commit", " ".join(rows[leaf]["Reasons"]), rows[leaf])

        # The control: the fixture reaches a removal, so each skip above is a verdict on the commit.
        self.assertEqual("PRUNE", rows["primary-clean"]["Decision"], rows["primary-clean"])
        self.assertFalse((self.base / "primary-clean").exists(), f"the clean sibling was not removed: {rows['primary-clean']}")


if __name__ == "__main__":
    unittest.main()
