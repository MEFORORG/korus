"""`scripts/coord/inbox-prune.ps1` deletes the korus-inbox plugin's spent files, and nothing else.

WHAT IT EXISTS FOR. The plugin's file API has no delete, so every ended session leaves its file in
`~/.korus-inbox` for good. The script is the cleanup. It deletes, so the property worth most is
what it leaves alone: a live file, a file of another name, anything in a subfolder, anything beside
the folder, and every file at all when it runs without -Apply.

ARTICLE V. Each case plants spent files beside files that must survive, and the survivors are the
control. A script that deleted nothing would pass a "kept everything" check, so the apply case also
requires the two spent files to be gone. A script that deleted everything fails on the survivors.

EVERY CASE RUNS THE REAL SCRIPT over a throwaway folder, passed by -Folder. It never reads or writes
the real home folder.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import _ccxtest as t

SCRIPT = t.REPO_ROOT / "scripts" / "coord" / "inbox-prune.ps1"
TIMEOUT_SECONDS = 120
DAY = 24 * 60 * 60


def _inbox(session: str, *, ended: bool) -> str:
    return json.dumps(
        {"format": "korus-inbox/1", "sessionId": session, "label": "w", "updatedAt": 0,
         "ended": ended, "entries": [], "dismissed": []}
    )


class ThePruneDeletesOnlySpentFiles(unittest.TestCase):
    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so inbox-prune.ps1 cannot be executed here")
        self.pwsh: str = pwsh
        tmp = tempfile.TemporaryDirectory(prefix="ccx-inbox-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.inbox = self.root / ".korus-inbox"
        (self.inbox / "sub").mkdir(parents=True)
        old = time.time() - DAY - 3600
        self.plant("live-1.json", _inbox("live-1", ended=False))
        self.plant("ended-2.json", _inbox("ended-2", ended=True))
        self.plant("stale-3.json", _inbox("stale-3", ended=False), mtime=old)
        self.plant("half-4.json", '{"format":"korus-inbox/1","ended":tr')
        self.plant("other-format-5.json", json.dumps({"format": "x/1", "ended": True}))
        self.plant("notes.txt", "keep me", mtime=old)
        self.plant("has space.json", _inbox("x", ended=True))
        # Shapes the plugin never reads as ended: an empty object, a one-item array, a key in the
        # wrong case. Each must survive, and the empty object must not stop the run.
        self.plant("aa-empty-8.json", "{}")
        self.plant("array-9.json", "[" + _inbox("array-9", ended=True) + "]")
        self.plant("upper-10.json", '{"format":"korus-inbox/1","ENDED":true}')
        self.plant("sub/ended-6.json", _inbox("ended-6", ended=True), mtime=old)
        # Beside the folder, not in it: spent by both rules, and out of reach.
        self.outside = self.root / "ended-7.json"
        self.outside.write_text(_inbox("ended-7", ended=True), encoding="ascii")
        os.utime(self.outside, (old, old))

    def plant(self, name: str, text: str, mtime: float | None = None) -> None:
        path = self.inbox / name
        path.write_text(text, encoding="ascii")
        if mtime is not None:
            os.utime(path, (mtime, mtime))

    def run_prune(self, *args: str, folder: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(SCRIPT), "-Folder", str(folder or self.inbox), *args],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False,
        )

    def survivors(self) -> set[str]:
        return {p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()}

    ALL = {
        ".korus-inbox/live-1.json", ".korus-inbox/ended-2.json", ".korus-inbox/stale-3.json",
        ".korus-inbox/half-4.json", ".korus-inbox/other-format-5.json", ".korus-inbox/notes.txt",
        ".korus-inbox/has space.json", ".korus-inbox/sub/ended-6.json", "ended-7.json",
        ".korus-inbox/aa-empty-8.json", ".korus-inbox/array-9.json", ".korus-inbox/upper-10.json",
    }

    def test_a_dry_run_names_the_spent_files_and_deletes_nothing(self):
        ran = self.run_prune()
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("would delete ended-2.json: ended", ran.stdout)
        self.assertIn("would delete stale-3.json: not written for 24 hours", ran.stdout)
        self.assertEqual(ran.stdout.count("would delete"), 2, ran.stdout)
        self.assertIn("Dry run", ran.stdout)
        self.assertEqual(self.survivors(), self.ALL)

    def test_apply_deletes_exactly_the_spent_files(self):
        ran = self.run_prune("-Apply")
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(
            self.survivors(), self.ALL - {".korus-inbox/ended-2.json", ".korus-inbox/stale-3.json"}, ran.stdout
        )
        self.assertIn("2 deleted, 0 failed", ran.stdout)

    def test_a_folder_of_another_name_is_refused_even_with_apply(self):
        ran = self.run_prune("-Apply", folder=self.root)
        self.assertEqual(ran.returncode, 2, ran.stdout)
        self.assertIn("refused", ran.stderr)
        self.assertEqual(self.survivors(), self.ALL)

    def test_a_missing_folder_is_nothing_to_do(self):
        ran = self.run_prune("-Apply", folder=self.root / "gone" / ".korus-inbox")
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("does not exist", ran.stdout)
        self.assertEqual(self.survivors(), self.ALL)


if __name__ == "__main__":
    unittest.main()
