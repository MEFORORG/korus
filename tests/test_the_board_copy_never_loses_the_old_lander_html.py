"""The copy to the owner's lander.html keeps the old file on every failure.

WHAT THIS EXISTS FOR. LANDER-BOARD.md section 9b once carried the copy as 17 lines of PowerShell
inside Markdown, and four review rounds each found a new defect in it. The copy is now
scripts/board/copy-to-dashboard.ps1 and these cases pin its contract: a good run replaces the
file, a failed move keeps the old one and leaves no temp file, the wrong host copies nothing, and
old temp files are swept.
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/board/copy-to-dashboard.ps1"
PWSH = shutil.which("pwsh")


def run(board: Path, dash: Path, host: str) -> subprocess.CompletedProcess[str]:
    cmd = [PWSH, "-NoProfile", "-File", str(SCRIPT), "-BoardHtml", str(board),
           "-DashboardDir", str(dash), "-ExpectedHost", host]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def this_host() -> str:
    out = subprocess.run([PWSH, "-NoProfile", "-Command", "[Environment]::MachineName"],
                         capture_output=True, text=True, timeout=60)
    return out.stdout.strip()


@unittest.skipUnless(PWSH, "PowerShell 7 is not installed")
class CopyToDashboard(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="board-copy-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.board = self.tmp / "board.html"
        self.board.write_text("NEW", encoding="utf-8")
        self.dash = self.tmp / "dash"
        self.dash.mkdir()
        self.host = this_host()

    def old(self) -> Path:
        target = self.dash / "lander.html"
        target.write_text("OLD", encoding="utf-8")
        return target

    def test_a_good_run_replaces_the_file_and_leaves_no_temp_file(self):
        target = self.old()
        r = run(self.board, self.dash, self.host)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "NEW")
        self.assertEqual(list(self.dash.glob("lander.*.tmp")), [])

    def test_the_wrong_host_copies_nothing(self):
        target = self.old()
        r = run(self.board, self.dash, "NOT-" + self.host)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD")

    def test_a_missing_board_copies_nothing_and_keeps_the_old_file(self):
        target = self.old()
        r = run(self.tmp / "absent.html", self.dash, self.host)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD")

    def test_a_target_held_open_keeps_the_old_file_and_leaves_no_temp_file(self):
        target = self.old()
        # Open with no sharing, so the replace cannot succeed. Windows only: POSIX has no such lock.
        hold = (
            f"$f=[IO.File]::Open('{target}','Open','Read','None');"
            f"& pwsh -NoProfile -File '{SCRIPT}' -BoardHtml '{self.board}' "
            f"-DashboardDir '{self.dash}' -ExpectedHost '{self.host}';"
            "$rc=$LASTEXITCODE;$f.Close();exit $rc"
        )
        r = subprocess.run([PWSH, "-NoProfile", "-Command", hold], capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            self.skipTest("this platform does not lock an open file")
        self.assertEqual(target.read_text(encoding="utf-8"), "OLD")
        self.assertEqual(list(self.dash.glob("lander.*.tmp")), [])

    def test_the_folder_is_named_by_the_engine_helper_extracted_from_origin_main(self):
        origin = self.tmp / "origin.git"
        work = self.tmp / "engine"
        want = self.tmp / "named-by-helper"
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
        helper = work / "scripts/dashboard/render_html.py"
        helper.parent.mkdir(parents=True)
        body = ["import sys", "assert '--print-out-dir' in sys.argv", "print(%r)" % str(want), ""]
        helper.write_text("\n".join(body), encoding="utf-8")
        subprocess.run(git + ["-C", str(work), "add", "."], check=True)
        subprocess.run(git + ["-C", str(work), "commit", "-q", "-m", "x"], check=True)
        subprocess.run(["git", "-C", str(work), "remote", "add", "origin", str(origin)], check=True)
        subprocess.run(["git", "-C", str(work), "push", "-q", "origin", "main"], check=True)
        cmd = [PWSH, "-NoProfile", "-File", str(SCRIPT), "-BoardHtml", str(self.board),
               "-EngineCheckout", str(work), "-ExpectedHost", self.host]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((want / "lander.html").read_text(encoding="utf-8"), "NEW")

    def test_old_temp_files_are_swept(self):
        (self.dash / "lander.deadbeef.tmp").write_text("private", encoding="utf-8")
        r = run(self.board, self.dash, self.host)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(list(self.dash.glob("lander.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
