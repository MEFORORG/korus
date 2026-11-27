"""The copy to the owner's lander.html keeps the old file on every failure.

WHAT THIS EXISTS FOR. LANDER-BOARD.md section 9b once carried the copy as 17 lines of PowerShell
inside Markdown, and four review rounds each found a new defect in it. The copy is now
scripts/board/copy-to-dashboard.ps1. Every case runs the script for real, against a scratch engine
repository whose origin/main holds a stub render_html.py that names the dashboard folder.

Three mutants each turn a case red, and each was run when the cases were written: a plain
overwrite of lander.html (no temp file and replace), Move-Item -Force in place of File.Move, and a
helper read from the working tree instead of origin/main.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/board/copy-to-dashboard.ps1"
PWSH = shutil.which("pwsh")
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]


def default_host() -> str:
    m = re.search(r"\$ExpectedHost = '([^']+)'", SCRIPT.read_text(encoding="utf-8"))
    assert m, "the script no longer names a default host"
    return m.group(1)


def this_host() -> str:
    out = subprocess.run([PWSH, "-NoProfile", "-Command", "[Environment]::MachineName"],
                         capture_output=True, text=True, timeout=60)
    return out.stdout.strip()


def helper_source(folder: Path) -> str:
    # Written as UTF-8 bytes whatever the console code page, as the real helper is run with -X utf8.
    return "import sys\nassert '--print-out-dir' in sys.argv\nprint(%r)\n" % str(folder)


@unittest.skipUnless(PWSH, "PowerShell 7 is not installed")
class CopyToDashboard(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="board-copy-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.board = self.tmp / "board.html"
        self.board.write_text("NEW", encoding="utf-8")
        self.host = this_host()
        self.dash = self.tmp / "dash"
        self.dash.mkdir()

    def engine(self, folder: Path) -> Path:
        """A scratch engine checkout whose origin/main names `folder`."""
        origin = self.tmp / "origin.git"
        work = self.tmp / "engine"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
        helper = work / "scripts/dashboard/render_html.py"
        helper.parent.mkdir(parents=True)
        helper.write_bytes(helper_source(folder).encode("utf-8"))
        subprocess.run(GIT + ["-C", str(work), "add", "."], check=True)
        subprocess.run(GIT + ["-C", str(work), "commit", "-q", "-m", "x"], check=True)
        subprocess.run(["git", "-C", str(work), "remote", "add", "origin", str(origin)], check=True)
        subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "main"], check=True)
        return work

    def run_script(self, engine: Path, host: str | None = None) -> subprocess.CompletedProcess[str]:
        cmd = [PWSH, "-NoProfile", "-File", str(SCRIPT), "-BoardHtml", str(self.board),
               "-EngineCheckout", str(engine)]
        if host is not None:
            cmd += ["-ExpectedHost", host]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    def old(self) -> Path:
        target = self.dash / "lander.html"
        target.write_text("OLD", encoding="utf-8")
        return target

    def test_a_good_run_replaces_the_file_and_leaves_no_temp_file(self):
        target = self.old()
        r = self.run_script(self.engine(self.dash), self.host)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "NEW")
        self.assertEqual(list(self.dash.glob("lander.*.tmp")), [])

    def test_the_real_default_host_refuses_every_other_machine_by_throwing(self):
        # No -ExpectedHost: the shipped default decides. On any machine but its owner's the script
        # must throw and copy nothing; on the owner's PC it must copy.
        target = self.old()
        r = self.run_script(self.engine(self.dash))
        if self.host == default_host():
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), "NEW")
        else:
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("STOP", r.stdout + r.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), "OLD")

    def test_a_named_wrong_host_throws_and_copies_nothing(self):
        target = self.old()
        r = self.run_script(self.engine(self.dash), "NOT-" + self.host)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("STOP", r.stdout + r.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD")

    def test_a_missing_board_copies_nothing_and_keeps_the_old_file(self):
        target = self.old()
        self.board.unlink()
        r = self.run_script(self.engine(self.dash), self.host)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD")

    def test_a_failed_replace_keeps_the_old_target_and_leaves_no_temp_file(self):
        # lander.html is a directory, so the replace cannot succeed. A plain overwrite or a
        # Move-Item -Force would copy INTO the directory and exit 0; the three-argument File.Move
        # throws. Works on every platform, unlike a held-open file.
        target = self.dash / "lander.html"
        target.mkdir()
        (target / "keep.txt").write_text("OLD", encoding="utf-8")
        r = self.run_script(self.engine(self.dash), self.host)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "OLD")
        self.assertEqual(list(target.iterdir()), [target / "keep.txt"])
        self.assertEqual(list(self.dash.glob("lander.*.tmp")), [])

    def test_a_target_held_open_keeps_the_old_file_and_leaves_no_temp_file(self):
        target = self.old()
        engine = self.engine(self.dash)
        # Open with no sharing, so the replace cannot succeed. Windows only: POSIX has no such lock.
        hold = (
            f"$f=[IO.File]::Open('{target}','Open','Read','None');"
            f"& pwsh -NoProfile -File '{SCRIPT}' -BoardHtml '{self.board}' "
            f"-EngineCheckout '{engine}' -ExpectedHost '{self.host}';"
            "$rc=$LASTEXITCODE;$f.Close();exit $rc"
        )
        r = subprocess.run([PWSH, "-NoProfile", "-Command", hold], capture_output=True, text=True, timeout=180)
        if r.returncode == 0:
            self.skipTest("this platform does not lock an open file")
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD")
        self.assertEqual(list(self.dash.glob("lander.*.tmp")), [])

    def test_the_helper_comes_from_origin_main_never_the_working_tree(self):
        elsewhere = self.tmp / "named-by-working-tree"
        engine = self.engine(self.dash)
        (engine / "scripts/dashboard/render_html.py").write_bytes(helper_source(elsewhere).encode("utf-8"))
        r = self.run_script(engine, self.host)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.dash / "lander.html").exists())
        self.assertFalse(elsewhere.exists())

    def test_a_non_ascii_folder_name_is_read_as_utf_8(self):
        folder = self.tmp / "déjà-vu ☃"
        r = self.run_script(self.engine(folder), self.host)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((folder / "lander.html").read_text(encoding="utf-8"), "NEW")

    def test_old_temp_files_are_swept(self):
        (self.dash / "lander.deadbeef.tmp").write_text("private", encoding="utf-8")
        r = self.run_script(self.engine(self.dash), self.host)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(list(self.dash.glob("lander.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
