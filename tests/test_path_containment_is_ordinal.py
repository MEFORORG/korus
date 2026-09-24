"""`Test-CcxPathUnder` compares ordinally, as occupancy.ps1's containment tests have since #158.

THE FAILURE THIS EXISTS FOR. It compared with `-eq` and a culture-aware `StartsWith`. Measured
2026-09-23 at 06e8ca3, pwsh 7.6.6 under en-US: a path whose part below the root starts with U+0301,
a combining mark, read as NOT inside the root. And an `e` with an acute accent written as one
character compared EQUAL to `e` followed by U+0301. NTFS stores those as two different names.

The function answers "is this path inside that tree" for the worktree gate, the occupancy fence,
remove.ps1's check that it is not standing in its target, and four more callers. The gate case
below shows the miss reaching one of them: rule 1 let a Write into the governed primary through.

CONTROLS. An ASCII path inside the root still reads as inside, a sibling that merely shares the
root's prefix still reads as outside, and rule 1 still denies an ASCII write into the primary. A
fix that answers "inside" for everything fails the second; one that answers "outside" fails the
first and the third.

MACOS. Its filesystem treats the two spellings of one accented name as one name, and the old
culture-aware compare had been folding them everywhere by accident. So ConvertTo-CcxComparablePath now
folds to NFC where `$CcxUnicodeFoldingFs` is set, which is macOS. One case sets that flag on this
platform and checks the fold; no macOS run was made. The same case checks the flag off keeps the
two apart.

Run: python -m pytest tests -q     (or: python -m unittest discover -s tests -v)
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120
COMMON = t.REPO_ROOT / "scripts" / "coord" / "_common.ps1"
MARK = "\u0301"
E_ACUTE = "\u00e9"
# A rooted path on this platform, so GetFullPath leaves the rest alone.
ROOT = "c:/x" if os.name == "nt" else "/x"


class PathContainmentIsOrdinal(unittest.TestCase):
    def setUp(self):
        self.pwsh = t.find_pwsh()
        if not self.pwsh:
            self.skipTest("pwsh is not on PATH, so _common.ps1 cannot be loaded here")

    def under(self, path: str, root: str) -> bool:
        """Test-CcxPathUnder, called for real. The paths travel as JSON, so no quoting touches them."""
        script = (
            f". '{COMMON}'; $a = $env:CCX_TEST_ARGS | ConvertFrom-Json; "
            "[Console]::Out.Write([string](Test-CcxPathUnder -Path $a.path -Root $a.root))"
        )
        env = dict(os.environ, CCX_TEST_ARGS=json.dumps({"path": path, "root": root}))
        r = subprocess.run([self.pwsh, "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, env=env, timeout=TIMEOUT_SECONDS)
        self.assertIn(r.stdout.strip(), ("True", "False"), f"no answer from Test-CcxPathUnder\n{r.stdout}\n{r.stderr}")
        return r.stdout.strip() == "True"

    def test_a_path_whose_first_character_below_the_root_is_a_combining_mark_is_inside(self):
        self.assertTrue(self.under(f"c:/x/p/{MARK}abc", "c:/x/p"), "a path inside the root read as outside it")

    def test_two_spellings_of_one_accented_name_are_two_paths(self):
        self.assertFalse(
            self.under(f"c:/x/{E_ACUTE}", f"c:/x/e{MARK}"),
            "an accented name compared equal to its decomposed spelling, which NTFS stores as another name",
        )

    def folded_under(self, path: str, root: str, unicode_folding: bool) -> bool:
        """Both sides through ConvertTo-CcxComparablePath first, as every caller does."""
        flag = "$true" if unicode_folding else "$false"
        script = (
            f". '{COMMON}'; $CcxUnicodeFoldingFs = {flag}; "
            "$a = $env:CCX_TEST_ARGS | ConvertFrom-Json; [Console]::Out.Write([string](Test-CcxPathUnder "
            "-Path (ConvertTo-CcxComparablePath $a.path) -Root (ConvertTo-CcxComparablePath $a.root)))"
        )
        env = dict(os.environ, CCX_TEST_ARGS=json.dumps({"path": path, "root": root}))
        r = subprocess.run([self.pwsh, "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, env=env, timeout=TIMEOUT_SECONDS)
        self.assertIn(r.stdout.strip(), ("True", "False"), f"no answer:\n{r.stdout}\n{r.stderr}")
        return r.stdout.strip() == "True"

    def test_where_the_filesystem_folds_unicode_both_spellings_are_one_path(self):
        root = f"{ROOT}/jos{E_ACUTE}/P"
        path = f"{ROOT}/jose{MARK}/P/x.md"
        self.assertTrue(self.folded_under(path, root, unicode_folding=True),
                        "with the macOS fold on, a path in the decomposed spelling read as outside its root")
        self.assertFalse(self.folded_under(path, root, unicode_folding=False),
                         "with the fold off, two names NTFS stores apart read as one")

    def test_control_an_ascii_path_inside_reads_inside_and_a_prefix_sibling_reads_outside(self):
        self.assertTrue(self.under("c:/x/p/abc", "c:/x/p"))
        self.assertTrue(self.under("c:/x/p", "c:/x/p"))
        self.assertFalse(self.under("c:/x/p-work/abc", "c:/x/p"), "a sibling sharing the prefix read as inside")


class TheGateSeesAWriteBelowACombiningMark(unittest.TestCase):
    """Rule 1 of the worktree gate, which keys on Test-CcxPathUnder."""

    GATE = t.REPO_ROOT / "scripts" / "hooks" / "worktree_gate.ps1"

    def setUp(self):
        self.pwsh = t.find_pwsh()
        if not self.pwsh:
            self.skipTest("pwsh is not on PATH, so the gate cannot be executed here")
        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-ordinal-", ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.primary = base / "P"
        self.primary.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(self.primary), check=True,
                       capture_output=True, timeout=TIMEOUT_SECONDS)
        self.repos = base / "repos.txt"
        self.repos.write_text(str(self.primary) + "\n", encoding="utf-8")

    def denied(self, file_path: Path) -> bool:
        payload = {"tool_name": "Write", "hook_event_name": "PreToolUse", "cwd": str(self.primary),
                   "tool_input": {"file_path": str(file_path), "content": "x"}}
        r = subprocess.run([self.pwsh, "-NoProfile", "-File", str(self.GATE), "-ReposFile", str(self.repos)],
                           input=json.dumps(payload), capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        return '"deny"' in r.stdout

    def test_a_write_below_a_combining_mark_in_the_primary_is_denied(self):
        self.assertTrue(
            self.denied(self.primary / f"{MARK}notes.txt"),
            "rule 1 let a Write into the governed primary through, because the containment test read "
            "the path as outside it",
        )

    def test_control_an_ascii_write_in_the_primary_is_denied(self):
        self.assertTrue(self.denied(self.primary / "notes.txt"), "the fixture does not govern its primary")


if __name__ == "__main__":
    unittest.main()
