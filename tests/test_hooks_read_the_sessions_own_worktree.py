"""Every hook that asks where it is reads the answer from its input's `cwd`, not from its process.

Measured 2026-10-12. The desktop app starts a worktree session's CLI with
`--project-config-root <primary checkout>`. A hook then runs with its working directory,
`CLAUDE_PROJECT_DIR` and git's top-level answer all naming the PRIMARY. Only the `cwd` in the JSON
on stdin names the worktree. korus#220 records the fixture that measured it.

Every case below starts the REAL hook in the primary and names the worktree only in the input, which
is the shape of that launch. Each class carries a control with no `cwd`, which must answer for the
primary. Without it, a pass could mean the fixture never reproduced the fault.

The role-card, seat-declare and pre-compact hooks are fixed in korus#220, with their cases beside
their own tests there.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 180

SESSION_CONTEXT = t.REPO_ROOT / "scripts" / "worktree" / "session-context.ps1"
ANNOUNCE = t.REPO_ROOT / "scripts" / "hooks" / "announce-session.ps1"
COLLISION = t.REPO_ROOT / "scripts" / "hooks" / "collision_gate.ps1"
DRAIN = t.REPO_ROOT / "scripts" / "hooks" / "mail-drain.ps1"
MAIL = t.REPO_ROOT / "scripts" / "coord" / "mail.ps1"
STEER = t.REPO_ROOT / "scripts" / "hooks" / "steer-inject.ps1"

GIT_ID = ["-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
FIXTURE_CONFIG = '{ "prefix": "ccx", "trunk": "main", "worktreeLayout": "sibling" }'


def slashed(p: Path) -> str:
    """git's spelling of a path: forward slashes, even on Windows."""
    return str(p).replace("\\", "/")


class _Fixture(unittest.TestCase):
    """A primary checkout and one linked worktree, with a subdirectory to stand in."""

    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so the hooks cannot be executed here")
        if not shutil.which("git"):
            self.skipTest("git is not on PATH, so the fixture repository cannot be built")
        self.pwsh: str = pwsh
        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-payload-cwd-", ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        # Resolved, because the mail box key hashes the spelling. See tests/test_session_mail.py.
        self.base = Path(os.path.realpath(self.tmp.name))

        self.primary = self.base / "primary"
        self.primary.mkdir()
        self.git(self.primary, "init", "-q", "-b", "main")
        (self.primary / "ccx.config.json").write_text(FIXTURE_CONFIG, encoding="utf-8")
        (self.primary / ".claude").mkdir()
        (self.primary / ".claude" / "keep.txt").write_text("x", encoding="ascii")
        self.git(self.primary, "add", "-A")
        self.git(self.primary, "commit", "-qm", "init")

        self.worktree = self.base / "wt"
        self.git(self.primary, "worktree", "add", "-q", str(self.worktree), "-b", "wt-branch")
        self.subdir = self.worktree / "docs" / "deep"
        self.subdir.mkdir(parents=True)
        self.missing = self.base / "gone"

    def git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        r = subprocess.run(
            ["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT_SECONDS
        )
        if r.returncode != 0:
            raise AssertionError(f"fixture setup failed: git {' '.join(args)}\n{r.stdout}\n{r.stderr}")
        return r

    def run_hook(self, script: Path, payload, *args: str, env=None) -> subprocess.CompletedProcess:
        """Run a hook from the PRIMARY, with the payload on stdin as UTF-8 bytes."""
        e = dict(os.environ)
        for leak in ("CCX_CONFIG", "CCX_TRUNK", "CLAUDE_PROJECT_DIR", "CCX_SESSION_BANNER"):
            e.pop(leak, None)
        if env:
            e.update(env)
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(script), *args],
            input=text.encode("utf-8"),
            capture_output=True,
            env=e,
            cwd=str(self.primary),
            timeout=TIMEOUT_SECONDS,
        )
        r.stdout = r.stdout.decode("utf-8", "replace")
        r.stderr = r.stderr.decode("utf-8", "replace")
        return r

    def run_shim(self, script: Path, payload, *args: str) -> subprocess.CompletedProcess:
        """Run a hook the way the installed shim does: in-process, by `&`, with stdin inherited."""
        call = "& '" + str(script).replace("'", "''") + "'"
        for a in args:
            # A parameter name goes in bare. Quoted, PowerShell binds it as a positional value.
            call += " " + a if a.startswith("-") else " '" + a.replace("'", "''") + "'"
        e = dict(os.environ)
        for leak in ("CCX_CONFIG", "CCX_TRUNK", "CLAUDE_PROJECT_DIR", "CCX_SESSION_BANNER"):
            e.pop(leak, None)
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-Command", call],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            env=e,
            cwd=str(self.primary),
            timeout=TIMEOUT_SECONDS,
        )
        r.stdout = r.stdout.decode("utf-8", "replace")
        r.stderr = r.stderr.decode("utf-8", "replace")
        return r

    def stub_tree(self, name: str = "tree") -> Path:
        """A copy of `scripts/` whose presence and overlap are stubs that answer at once.

        The banner calls them by `$PSScriptRoot`, so a copy is the only way to swap them. The banner's
        own code runs unchanged. The real pair would read this machine's session registry.
        """
        tree = self.base / name
        if not tree.exists():
            shutil.copytree(t.REPO_ROOT / "scripts", tree / "scripts")
            stub = "param([switch]$Json,[switch]$All,[string]$Repo,[string]$File)\nWrite-Output '[]'\nexit 0\n"
            (tree / "scripts" / "coord" / "presence.ps1").write_text(stub, encoding="utf-8")
            (tree / "scripts" / "coord" / "overlap.ps1").write_text(stub, encoding="utf-8")
        return tree / "scripts"


class TheSessionBannerNamesTheSessionsWorktree(_Fixture):
    def banner(self, payload) -> str:
        r = self.run_hook(self.stub_tree() / "worktree" / "session-context.ps1", payload)
        self.assertEqual(0, r.returncode, r.stderr)
        return r.stdout

    def test_the_input_cwd_names_the_worktree(self):
        out = self.banner({"cwd": str(self.subdir), "session_id": "s"})
        self.assertIn(f"This chat's worktree: {slashed(self.worktree)}", out)
        self.assertNotIn("SHARED PRIMARY checkout", out)

    def test_without_a_cwd_it_names_the_primary(self):
        """The control. It reproduces the fault the case above fixes."""
        out = self.banner({"session_id": "s"})
        self.assertIn(f"This chat's worktree: {slashed(self.primary)}", out)
        self.assertIn("SHARED PRIMARY checkout", out)

    def test_a_missing_cwd_falls_back_and_says_so(self):
        out = self.banner({"cwd": str(self.missing)})
        self.assertIn(f"This chat's worktree: {slashed(self.primary)}", out)
        self.assertIn("[session-context] the hook input names cwd", out)

    def test_run_through_the_shim_it_still_reads_the_input(self):
        """The installed shim runs the hook in-process with `&`, so stdin is inherited, not piped."""
        r = self.run_shim(self.stub_tree() / "worktree" / "session-context.ps1", {"cwd": str(self.worktree)})
        self.assertIn(f"This chat's worktree: {slashed(self.worktree)}", r.stdout, r.stderr)

    def test_a_missing_input_reader_is_said_aloud(self):
        """A copier who leaves out _hookinput.ps1 gets the old answer, and is told why."""
        scripts = self.stub_tree("tree-no-helper")
        (scripts / "hooks" / "_hookinput.ps1").unlink()
        r = self.run_hook(scripts / "worktree" / "session-context.ps1", {"cwd": str(self.worktree)})
        self.assertIn("could not read its input", r.stdout)
        self.assertIn("_hookinput.ps1 is missing", r.stdout)

    def test_a_primary_whose_path_says_worktrees_is_still_the_primary(self):
        """From a subdirectory --git-dir is absolute, so a match on 'worktrees' misread this primary."""
        app = self.base / "worktrees" / "app"
        app.mkdir(parents=True)
        self.git(app, "init", "-q", "-b", "main")
        (app / "a.txt").write_text("a", encoding="ascii")
        self.git(app, "add", "-A")
        self.git(app, "commit", "-qm", "init")
        self.git(app, "worktree", "add", "-q", str(self.base / "app-wt"), "-b", "side")
        (app / "src").mkdir()
        out = self.banner({"cwd": str(app / "src")})
        self.assertIn(f"This chat's worktree: {slashed(app)}", out)
        self.assertIn("SHARED PRIMARY checkout", out)


class TheAnnouncementNamesTheSessionsWorktree(_Fixture):
    PEER = {
        "SessionId": "peer-session-1", "Short": "peer-ses", "Surface": "desktop", "Login": "",
        "Kind": "interactive", "IsSelf": False, "IsPrimary": False, "State": "LIVE",
        "Worktree": "peer", "Branch": "peer-branch",
    }

    def announce(self, payload, run: str, shim: bool = False) -> str:
        peer = dict(self.PEER, Cwd=str(self.base / "peer"))
        stub = self.base / "presence-stub.ps1"
        stub.write_text(
            "param([switch]$Json)\nWrite-Output '" + json.dumps([peer]).replace("'", "''") + "'\nexit 0\n",
            encoding="utf-8",
        )
        # A state dir per run, so one run's cooldown stamp cannot silence the next.
        state = self.base / f"announce-{run}"
        args = ("-PresenceScript", str(stub), "-StateDir", str(state))
        if shim:
            # The shim passes -CommonDir from where IT started, which is the primary.
            common = self.git(self.primary, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
            r = self.run_shim(ANNOUNCE, payload, *args, "-CommonDir", common)
        else:
            r = self.run_hook(ANNOUNCE, payload, *args)
        self.assertEqual(0, r.returncode, r.stderr)
        return r.stdout

    def test_the_input_cwd_names_the_worktree(self):
        out = self.announce({"session_id": "sess-a", "cwd": str(self.subdir)}, "a")
        self.assertIn(f"[SESSION-ANNOUNCE] {slashed(self.worktree)} (wt-branch)", out)

    def test_without_a_cwd_it_names_the_primary(self):
        """The control. Measured 2026-10-13: this is what a desktop worktree session was told."""
        out = self.announce({"session_id": "sess-b"}, "b")
        self.assertIn(f"[SESSION-ANNOUNCE] {slashed(self.primary)} (main)", out)

    def test_a_missing_cwd_announces_nothing_and_says_so(self):
        """Announcing the primary as this session's identity is the fault, so it announces nothing."""
        out = self.announce({"session_id": "sess-c", "cwd": str(self.missing)}, "c")
        self.assertNotIn("[SESSION-ANNOUNCE]", out)
        self.assertIn("[announce] the hook input names cwd", out)
        self.assertIn("announced nothing", out)

    def test_run_through_the_shim_it_names_the_worktree(self):
        out = self.announce({"session_id": "sess-d", "cwd": str(self.worktree)}, "d", shim=True)
        self.assertIn(f"[SESSION-ANNOUNCE] {slashed(self.worktree)} (wt-branch)", out)


class TheCollisionGateSkipsTheSessionsOwnWorktree(_Fixture):
    """overlap.ps1 skips "your own worktree" by the directory it runs in. The stub reports that one.

    A stub, because the real overlap needs a live session registry. It decides nothing: it names the
    directory the gate started it in, which is the one fact under test.
    """

    def gate(self, payload, state: str = "gate-state") -> str:
        stub = self.base / "overlap-stub.ps1"
        stub.write_text(
            "param([string]$File,[switch]$Json)\n"
            "$top = (& git rev-parse --path-format=absolute --show-toplevel 2>$null)\n"
            "$row = [pscustomobject]@{ Live = $true; MatchedDirty = $true; Short = 'stub'; Surface = 'desktop';"
            " Worktree = \"RAN-IN:$top\"; Branch = 'b'; Work = @() }\n"
            "ConvertTo-Json -InputObject @($row) -Compress\nexit 0\n",
            encoding="utf-8",
        )
        r = self.run_hook(
            COLLISION, payload, "-OverlapScript", str(stub), "-StateDir", str(self.base / state)
        )
        self.assertEqual(0, r.returncode, r.stderr)
        return r.stdout

    def test_the_input_cwd_is_where_overlap_runs(self):
        out = self.gate({"cwd": str(self.subdir), "tool_input": {"file_path": "a.txt"}})
        self.assertIn(f"RAN-IN:{slashed(self.worktree)}", out)

    def test_without_a_cwd_overlap_runs_in_the_primary(self):
        """The control. Here the session's own worktree would read as a peer's."""
        out = self.gate({"tool_input": {"file_path": "a.txt"}})
        self.assertIn(f"RAN-IN:{slashed(self.primary)}", out)

    def test_a_missing_cwd_is_reported_as_unchecked(self):
        out = self.gate({"cwd": str(self.missing), "tool_input": {"file_path": "a.txt"}})
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("could NOT check this edit (cwd-unusable)", ctx)
        self.assertNotIn("RAN-IN:", out)

    def test_two_sessions_with_unusable_cwds_each_get_the_notice(self):
        """Both gates start in the primary. Keyed on that, the second session's notice was throttled."""
        state = "gate-state-two"
        first = self.gate({"cwd": str(self.base / "gone-1"), "tool_input": {"file_path": "a.txt"}}, state)
        second = self.gate({"cwd": str(self.base / "gone-2"), "tool_input": {"file_path": "a.txt"}}, state)
        self.assertIn("cwd-unusable", first)
        self.assertIn("cwd-unusable", second, "one session's notice silenced another's")


class TheMailDrainReadsTheSessionsOwnBox(_Fixture):
    def setUp(self):
        super().setUp()
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(MAIL), "-Send", "-To", str(self.worktree), "-Body", "MAIL-SENTINEL"],
            capture_output=True, text=True, cwd=str(self.primary), timeout=TIMEOUT_SECONDS,
        )
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def drain(self, payload) -> str:
        base = {"session_id": "sess-m", "hook_event_name": "SessionStart"}
        r = self.run_hook(DRAIN, {**base, **payload}, "-Event", "SessionStart")
        self.assertEqual(0, r.returncode, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_the_input_cwd_reads_the_worktrees_box(self):
        self.assertIn("MAIL-SENTINEL", self.drain({"cwd": str(self.subdir)}))

    def test_without_a_cwd_it_reads_the_primarys_box(self):
        """The control. The message waits in the worktree's box, which this drain never opens."""
        ctx = self.drain({})
        self.assertNotIn("MAIL-SENTINEL", ctx)
        self.assertIn("No mail", ctx)

    def test_a_missing_cwd_reads_no_box_and_says_so(self):
        """Showing the primary's box here would let this session's Stop file the primary's mail."""
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(MAIL), "-Send", "-To", str(self.primary), "-Body", "PRIMARY-MAIL"],
            capture_output=True, text=True, cwd=str(self.worktree), timeout=TIMEOUT_SECONDS,
        )
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        ctx = self.drain({"cwd": str(self.missing)})
        self.assertIn("NO BOX", ctx)
        self.assertIn("the hook input names cwd", ctx)
        self.assertNotIn("PRIMARY-MAIL", ctx)


class TheSteeringHookReadsTheSessionsOwnNote(_Fixture):
    def plant(self, root: Path, text: str) -> Path:
        (root / ".claude").mkdir(exist_ok=True)
        note = root / ".claude" / "steer.txt"
        note.write_text(text, encoding="utf-8")
        return note

    def steer(self, payload) -> str:
        r = self.run_hook(STEER, payload, env={"CLAUDE_PROJECT_DIR": str(self.primary)})
        self.assertEqual(0, r.returncode, r.stderr)
        return r.stdout

    def test_the_input_cwd_reads_the_worktrees_note(self):
        note = self.plant(self.worktree, "STEER-SENTINEL")
        self.assertIn("STEER-SENTINEL", self.steer({"cwd": str(self.subdir)}))
        self.assertFalse(note.exists(), "the note was delivered but not consumed")

    def test_without_a_cwd_it_reads_the_project_dir(self):
        """The control. CLAUDE_PROJECT_DIR names the primary, so the worktree's note is never read."""
        note = self.plant(self.worktree, "STEER-SENTINEL")
        self.assertEqual("", self.steer({}).strip())
        self.assertTrue(note.exists())

    def test_a_missing_cwd_falls_back_and_says_so(self):
        self.plant(self.primary, "PRIMARY-NOTE")
        out = self.steer({"cwd": str(self.missing)})
        self.assertIn("PRIMARY-NOTE", out)
        self.assertIn("steer-inject: the hook input names cwd", out)

    def test_a_non_ascii_cwd_survives_the_read(self):
        """The input is read as UTF-8 bytes. A console-code-page read mangles this name and falls back."""
        wt = self.base / ("caf" + chr(0xE9))
        wt.mkdir()
        (wt / ".git").write_text("gitdir: elsewhere\n", encoding="ascii")
        self.plant(wt, "ACCENT-SENTINEL")
        self.assertIn("ACCENT-SENTINEL", self.steer({"cwd": str(wt)}))


if __name__ == "__main__":
    unittest.main()
