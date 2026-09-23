"""The reaper must see an untracked file that `status.showUntrackedFiles=no` hides.

THE FAILURE THIS EXISTS FOR. `prune-merged.ps1` promises to skip a worktree holding untracked files,
because `git worktree remove --force` deletes them and nothing in git can bring them back. Its clean
check read plain `git status --porcelain`, which obeys `status.showUntrackedFiles`. With that set to
`no`, an untracked file read as clean, and `-Apply` deleted it. Measured 2026-09-23 against
`a58981d`: this file's first case removed the worktree and the file with it.

`remove.ps1` had the same hole in the commands its refusal prints, and both scripts now read status
through one function, `Read-WorktreeStatus` in `scripts/coord/occupancy.ps1`, which passes
`--untracked-files=all`. That flag overrides the setting; the precondition below shows the setting
hides the file from plain `git status`, so the case measures the override and not an empty fixture.

A CONTROL IN THE SAME RUN. A clean sibling beside it is still pruned, so a reaper that skips
everything fails here too.

WHAT THIS DOES NOT COVER. The reaper still deletes IGNORED files. That is its stated policy in
docs/PRUNING.md, and this file does not change it.

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


class TheReaperSeesAHiddenUntrackedFile(unittest.TestCase):
    def setUp(self):
        self.pwsh = t.find_pwsh()
        if not self.pwsh:
            self.skipTest("pwsh is not on PATH, so prune-merged.ps1 cannot be executed here")
        if not shutil.which("git"):
            self.skipTest("git is not on PATH, so the fixture repository cannot be built")
        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-hidden-", ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()

    def fixture(self) -> tuple[Path, Path]:
        primary = self.base / "primary"
        primary.mkdir()
        git("init", "-q", "-b", "main", cwd=primary)
        (primary / "ccx.config.json").write_text(
            json.dumps({"prefix": "ccx", "trunk": "main", "worktreeLayout": "sibling"}), encoding="utf-8")
        (primary / "README.md").write_text("fixture\n", encoding="utf-8")
        git("add", "-A", cwd=primary)
        git("commit", "-qm", "init", cwd=primary)
        for name in ("hidden", "clean"):
            git("worktree", "add", "-q", str(self.base / f"primary-{name}"), "-b", f"feature/{name}", cwd=primary)

        # Signal 2 satisfied honestly, as the fence re-read test does: backdate the worktree admin
        # directories rather than switch the activity veto off.
        when = time.time() - 48 * 3600
        for admin in (primary / ".git" / "worktrees").iterdir():
            for f in list(admin.rglob("*")) + [admin]:
                os.utime(f, (when, when))

        # One readable session record outside every worktree, so the fence is available.
        roots = self.base / "roots"
        (roots / "sessions").mkdir(parents=True)
        (roots / "sessions" / "4242.json").write_text(
            json.dumps({"sessionId": "fixture-elsewhere", "pid": 4242, "cwd": str(self.base / "nowhere")}),
            encoding="utf-8",
        )
        return primary, roots

    def reap(self, primary: Path, roots: Path, *args: str) -> dict:
        env = dict(os.environ)
        for leak in ("CCX_CONFIG", "CCX_TRUNK"):
            env.pop(leak, None)
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(REAPER), "-RepoRoot", str(primary),
             "-ConfigRoot", str(roots), "-SkipFetch", "-SkipGh", "-Json", *args],
            capture_output=True, text=True, env=env, cwd=str(primary), timeout=TIMEOUT_SECONDS,
        )
        self.assertTrue(r.stdout.strip(), f"no JSON receipt (exit {r.returncode}):\n{r.stderr}")
        return json.loads(r.stdout)

    def test_an_untracked_file_the_setting_hides_blocks_the_prune(self):
        primary, roots = self.fixture()
        hidden = self.base / "primary-hidden"
        clean = self.base / "primary-clean"
        (hidden / "notes.txt").write_text("a session wrote this and never added it\n", encoding="utf-8")
        git("config", "status.showUntrackedFiles", "no", cwd=primary)
        # --no-optional-locks, or the status refreshes the index and trips the activity veto.
        self.assertEqual(
            "", git("--no-optional-locks", "status", "--porcelain", cwd=hidden).strip(),
            "precondition: the setting hides it",
        )

        result = self.reap(primary, roots, "-Apply")
        rows = {c["Leaf"]: c for c in result["candidates"]}

        self.assertTrue(
            (hidden / "notes.txt").is_file(),
            "the reaper deleted an untracked file that status.showUntrackedFiles=no hid from its clean "
            f"check. Its row: {rows.get('primary-hidden')}",
        )
        self.assertEqual("SKIP", rows["primary-hidden"]["Decision"], rows["primary-hidden"])
        self.assertIn("untracked", " ".join(rows["primary-hidden"]["Reasons"]))

        # The control: the fixture really reaches a removal, so the skip above is a verdict on the file.
        self.assertEqual("PRUNE", rows["primary-clean"]["Decision"], rows["primary-clean"])
        self.assertFalse(clean.exists(), f"the clean sibling was not removed: {rows['primary-clean']}")


if __name__ == "__main__":
    unittest.main()
