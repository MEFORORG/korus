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

The korus#223 review found the `cwd` trusted too far: after a `cd` the hooks answered for a sibling
worktree or another repository, with or without a pin. So the cases also cover the rules at the top
of `_hookinput.ps1`. The collision gate reads no `cwd` at all now; it runs in the worktree that holds
the file.
"""

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
        # A second linked worktree of the same clone: where a session lands after `cd ../sib`.
        self.sibling = self.base / "sib"
        self.git(self.primary, "worktree", "add", "-q", str(self.sibling), "-b", "sib-branch")
        # A different repository altogether, with the same layout.
        self.other = self.base / "other"
        self.other.mkdir()
        self.git(self.other, "init", "-q", "-b", "main")
        (self.other / ".claude").mkdir()
        (self.other / ".claude" / "keep.txt").write_text("x", encoding="ascii")
        self.git(self.other, "add", "-A")
        self.git(self.other, "commit", "-qm", "init")

    def git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        r = subprocess.run(
            ["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT_SECONDS
        )
        if r.returncode != 0:
            raise AssertionError(f"fixture setup failed: git {' '.join(args)}\n{r.stdout}\n{r.stderr}")
        return r

    def run_hook(self, script: Path, payload, *args: str, env=None, start=None) -> subprocess.CompletedProcess:
        """Run a hook from the PRIMARY, or from start, with the payload on stdin as UTF-8 bytes."""
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
            cwd=str(start or self.primary),
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

    def launch(self, sid: str, cwd: Path, source: str = "startup") -> subprocess.CompletedProcess:
        """A SessionStart through the session banner, which pins the session where it launched."""
        payload = {"session_id": sid, "cwd": str(cwd), "hook_event_name": "SessionStart", "source": source}
        r = self.run_hook(self.stub_tree() / "worktree" / "session-context.ps1", payload)
        self.assertEqual(0, r.returncode, r.stderr)
        return r

    def pins(self) -> list:
        d = self.primary / ".git" / "ccx-session-root"
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

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
    def banner(self, payload, start=None) -> str:
        r = self.run_hook(self.stub_tree() / "worktree" / "session-context.ps1", payload, start=start)
        self.assertEqual(0, r.returncode, r.stderr)
        return r.stdout

    def test_the_input_cwd_names_the_worktree(self):
        self.launch("s", self.worktree)
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
        payload = {"cwd": str(self.worktree), "session_id": "shim", "hook_event_name": "SessionStart", "source": "startup"}
        r = self.run_shim(self.stub_tree() / "worktree" / "session-context.ps1", payload)
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
        # Started in that repository: a cwd in another clone than the start is refused.
        out = self.banner({"cwd": str(app / "src")}, start=app)
        self.assertIn(f"This chat's worktree: {slashed(app)}", out)
        self.assertIn("SHARED PRIMARY checkout", out)

    def start(self, sid: str, cwd: Path, source: str) -> str:
        return self.banner({"cwd": str(cwd), "session_id": sid, "hook_event_name": "SessionStart", "source": source})

    def test_after_a_cd_to_a_sibling_it_still_names_the_first_worktree(self):
        """korus#223 review point 4. The startup cwd pins; a later cwd in a sibling does not move it."""
        self.start("pin-1", self.worktree, "startup")
        out = self.start("pin-1", self.sibling, "compact")
        self.assertIn(f"This chat's worktree: {slashed(self.worktree)}", out)
        self.assertNotIn(f"This chat's worktree: {slashed(self.sibling)}", out)

    def test_with_no_pin_a_sibling_cwd_is_refused(self):
        """The Lander's re-review of korus#223: without a pin the sibling's cwd was believed. Now the
        banner names where the hook started and says why. The case above is its control."""
        out = self.start("pin-2", self.sibling, "compact")
        self.assertIn(f"This chat's worktree: {slashed(self.primary)}", out)
        self.assertIn("no pin records that this session started in", out)

    def test_a_clear_with_a_new_session_id_never_pins_the_sibling(self):
        """The Lander's HIGH finding: /clear mints a new session id, so its SessionStart finds no pin,
        and the old rule pinned whatever sibling a `cd` had reached."""
        self.start("before-clear", self.worktree, "startup")
        self.start("after-clear", self.sibling, "clear")
        out = self.banner({"cwd": str(self.sibling), "session_id": "after-clear"})
        self.assertNotIn(f"This chat's worktree: {slashed(self.sibling)}", out)
        self.assertEqual(1, len(self.pins()), "a /clear wrote a pin")

    def test_a_launch_pins_only_in_a_clone_that_opted_in(self):
        """The opt-in gate. A user-scope hook writes no file in a clone with no ccx.config.json, and
        still answers the launch itself, whose cwd is where the session started."""
        (self.primary / "ccx.config.json").unlink()
        out = self.start("gate", self.worktree, "startup")
        self.assertIn(f"This chat's worktree: {slashed(self.worktree)}", out)
        self.assertEqual([], self.pins())
        # The control: the same launch, opted in, pins.
        (self.primary / "ccx.config.json").write_text(FIXTURE_CONFIG, encoding="utf-8")
        self.start("gate", self.worktree, "startup")
        self.assertEqual(1, len(self.pins()))

    def test_a_launch_in_a_clone_no_longer_opted_in_removes_the_old_pin(self):
        """The opt-in gate guarded the removal too, so a resume after the opt-in went away kept the
        previous run's pin. Removing writes no new file, so it needs no opt-in."""
        self.start("optout", self.sibling, "startup")
        (self.primary / "ccx.config.json").unlink()
        self.start("optout", self.worktree, "resume")
        self.assertEqual([], self.pins())
        out = self.banner({"cwd": str(self.sibling), "session_id": "optout"})
        self.assertNotIn(f"This chat's worktree: {slashed(self.sibling)}", out)

    def test_a_pin_write_prunes_stale_temp_files(self):
        """A crashed writer's temp file was never removed. One an hour old goes; a fresh one stays."""
        d = self.primary / ".git" / "ccx-session-root"
        d.mkdir(parents=True)
        stale, fresh = d / "x.1.dead.tmp", d / "x.2.live.tmp"
        stale.write_text("x", encoding="ascii")
        fresh.write_text("x", encoding="ascii")
        old = time.time() - 3600
        os.utime(stale, (old, old))
        self.start("prune", self.worktree, "startup")
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists())

    def test_a_pin_that_cannot_be_replaced_is_not_kept(self):
        """A failed swap kept the previous run's pin. A read-only pin makes the move fail on demand."""
        self.start("swap", self.sibling, "startup")
        pin = next((self.primary / ".git" / "ccx-session-root").iterdir())
        os.chmod(pin, 0o444)
        try:
            self.start("swap", self.worktree, "resume")
            out = self.banner({"cwd": str(self.sibling), "session_id": "swap"})
            self.assertNotIn(f"This chat's worktree: {slashed(self.sibling)}", out)
        finally:
            if pin.exists():
                os.chmod(pin, 0o644)

    def test_a_resume_pins_again(self):
        """A resume's cwd is where the session was launched this time, so it replaces the old pin."""
        self.start("pin-3", self.worktree, "startup")
        out = self.start("pin-3", self.sibling, "resume")
        self.assertIn(f"This chat's worktree: {slashed(self.sibling)}", out)

    def test_a_clear_does_not_pin_again(self):
        """korus#223 review round 2: after a cd, a /clear's cwd may be the sibling, not the launch."""
        self.start("pin-5", self.worktree, "startup")
        out = self.start("pin-5", self.sibling, "clear")
        self.assertIn(f"This chat's worktree: {slashed(self.worktree)}", out)

    def test_a_refused_resume_leaves_no_old_pin_behind(self):
        """korus#223 review round 1: a refused launch cwd left the old run's pin answering in silence."""
        self.start("pin-4", self.worktree, "startup")
        self.start("pin-4", self.missing, "resume")
        self.assertEqual([], self.pins())
        out = self.banner({"cwd": str(self.worktree), "session_id": "pin-4", "hook_event_name": "SessionStart", "source": "compact"})
        self.assertNotIn(f"This chat's worktree: {slashed(self.worktree)}", out)

    def test_a_cwd_in_another_repository_falls_back_and_says_so(self):
        """korus#223 review point 4: the banner answered for the other repository, or said nothing."""
        out = self.banner({"cwd": str(self.other), "session_id": "s"})
        self.assertIn(f"This chat's worktree: {slashed(self.primary)}", out)
        self.assertIn("which is in another repository", out)


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
        self.launch("sess-a", self.worktree)
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
        self.launch("sess-d", self.worktree)
        out = self.announce({"session_id": "sess-d", "cwd": str(self.worktree)}, "d", shim=True)
        self.assertIn(f"[SESSION-ANNOUNCE] {slashed(self.worktree)} (wt-branch)", out)

    def test_after_a_cd_to_a_sibling_it_announces_the_first_worktree(self):
        """korus#223 review point 4: after a `cd` the session announced itself as the sibling."""
        self.launch("sess-e", self.worktree)
        out = self.announce({"session_id": "sess-e", "cwd": str(self.sibling)}, "e2")
        self.assertIn(f"[SESSION-ANNOUNCE] {slashed(self.worktree)} (wt-branch)", out)

    def test_with_no_pin_a_sibling_cwd_announces_nothing(self):
        """The Lander's re-review of korus#223: with no pin the sibling was announced. The case above
        is its control."""
        out = self.announce({"session_id": "sess-f", "cwd": str(self.sibling)}, "f")
        self.assertNotIn("[SESSION-ANNOUNCE]", out)
        self.assertIn("no pin records that this session started in", out)

    def test_the_self_test_writes_no_pin(self):
        """-SelfTest is a diagnostic: it reads a pin and never writes one, even at a launch."""
        payload = {"session_id": "sess-st", "cwd": str(self.worktree), "hook_event_name": "SessionStart", "source": "startup"}
        stub = self.base / "presence-stub.ps1"
        stub.write_text("param([switch]$Json)\nWrite-Output '[]'\nexit 0\n", encoding="utf-8")
        r = self.run_hook(ANNOUNCE, payload, "-PresenceScript", str(stub), "-StateDir", str(self.base / "st"),
                          "-SelfTest", "-PayloadOverride", json.dumps(payload))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual([], self.pins())
        # The control: the same payload through the banner, which is not a diagnostic, pins.
        self.launch("sess-st", self.worktree)
        self.assertEqual(1, len(self.pins()))

    def test_a_cwd_in_another_repository_announces_nothing_and_says_so(self):
        out = self.announce({"session_id": "sess-g", "cwd": str(self.other)}, "g")
        self.assertNotIn("[SESSION-ANNOUNCE]", out)
        self.assertIn("which is in another repository", out)

    def test_the_cannot_tell_line_obeys_the_kill_switch(self):
        """korus#223 review: the line ignored the OFF file."""
        state = self.base / "announce-h"
        state.mkdir()
        (state / "OFF").write_text("", encoding="ascii")
        out = self.announce({"session_id": "sess-h", "cwd": str(self.missing)}, "h")
        self.assertNotIn("announced nothing", out)

    def test_the_cannot_tell_line_is_said_once_not_every_prompt(self):
        """korus#223 review: the line was unthrottled, so it rode on every prompt."""
        first = self.announce({"session_id": "sess-i", "cwd": str(self.missing)}, "i")
        second = self.announce({"session_id": "sess-i", "cwd": str(self.missing)}, "i")
        self.assertIn("announced nothing", first)
        self.assertNotIn("announced nothing", second)


class TheCollisionGateSkipsTheSessionsOwnWorktree(_Fixture):
    """overlap.ps1 skips "your own worktree" by the directory it runs in. The stub reports that one.

    The gate runs it in the worktree that holds the TARGET file, never in the payload's cwd: after a
    `cd` the cwd names wherever the session went (korus#223 review point 1). The stub decides
    nothing; it names the directory the gate started it in, which is the one fact under test.
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

    def test_an_absolute_file_in_the_worktree_runs_overlap_there(self):
        out = self.gate({"tool_input": {"file_path": str(self.worktree / "a.txt")}})
        self.assertIn(f"RAN-IN:{slashed(self.worktree)}", out)

    def test_after_a_cd_to_a_sibling_overlap_runs_in_the_files_worktree(self):
        out = self.gate({"cwd": str(self.sibling), "tool_input": {"file_path": str(self.worktree / "a.txt")}})
        self.assertIn(f"RAN-IN:{slashed(self.worktree)}", out)

    def test_after_a_cd_to_another_repository_overlap_runs_in_the_files_worktree(self):
        out = self.gate({"cwd": str(self.other), "tool_input": {"file_path": str(self.worktree / "a.txt")}})
        self.assertIn(f"RAN-IN:{slashed(self.worktree)}", out)

    def test_a_relative_file_resolves_against_the_input_cwd(self):
        out = self.gate({"cwd": str(self.subdir), "tool_input": {"file_path": "a.txt"}})
        self.assertIn(f"RAN-IN:{slashed(self.worktree)}", out)

    def test_without_a_cwd_a_relative_file_runs_overlap_in_the_primary(self):
        """The control: with nothing naming the worktree, the gate answers from where it started."""
        out = self.gate({"tool_input": {"file_path": "a.txt"}})
        self.assertIn(f"RAN-IN:{slashed(self.primary)}", out)

    def test_a_missing_cwd_still_runs_the_check(self):
        """korus#223 review point 3: an unusable cwd gave one notice, then 30 silent minutes."""
        for _ in range(2):
            out = self.gate({"cwd": str(self.missing), "tool_input": {"file_path": str(self.worktree / "a.txt")}})
            self.assertIn(f"RAN-IN:{slashed(self.worktree)}", out)
            self.assertNotIn("could NOT check", out)

    def test_a_file_in_another_repository_keeps_the_old_run(self):
        """The gate never starts an overlap walk in a repository it was not installed for."""
        out = self.gate({"tool_input": {"file_path": str(self.other / "a.txt")}})
        self.assertIn(f"RAN-IN:{slashed(self.primary)}", out)

    def test_a_missing_input_reader_is_reported_as_unchecked(self):
        scripts = self.stub_tree("tree-gate-no-helper")
        (scripts / "hooks" / "_hookinput.ps1").unlink()
        r = self.run_hook(
            scripts / "hooks" / "collision_gate.ps1",
            {"tool_input": {"file_path": str(self.worktree / "a.txt")}},
            "-StateDir", str(self.base / "gate-state-nohelper"),
        )
        self.assertIn("input-reader-missing", r.stdout)


class TheCollisionGateDeniesARealCollision(_Fixture):
    """The REAL overlap.ps1, with a live peer dirty on the file. korus#223 review point 5.

    A wrapper forwards the gate's call to the real script, adding only a fixture session registry, so
    no session on this machine can appear in the answer. The peer's record carries this test's own
    pid, which is alive; with no startedAt it reads UNVERIFIED, which counts as live.
    """

    def setUp(self):
        super().setUp()
        self.peer = self.base / "peer"
        self.git(self.primary, "worktree", "add", "-q", str(self.peer), "-b", "peer-branch")
        (self.peer / ".claude" / "keep.txt").write_text("peer edit", encoding="ascii")
        self.roots = self.base / "roots"
        (self.roots / "sessions").mkdir(parents=True)
        (self.roots / "sessions" / "peer.json").write_text(
            json.dumps({"sessionId": "peer-session", "pid": os.getpid(), "cwd": str(self.peer)}), encoding="utf-8"
        )
        real = t.REPO_ROOT / "scripts" / "coord" / "overlap.ps1"
        self.wrapper = self.base / "overlap-wrapper.ps1"

        def q(p: Path) -> str:
            return "'" + str(p).replace("'", "''") + "'"

        self.wrapper.write_text(
            "param([string]$File,[switch]$Json)\n"
            f"& {q(real)} -File $File -Json -Refresh -ConfigRoot {q(self.roots)} -TasksDir {q(self.roots)}\n"
            "exit $LASTEXITCODE\n",
            encoding="utf-8",
        )

    def gate(self, payload) -> str:
        r = self.run_hook(
            COLLISION, payload, "-OverlapScript", str(self.wrapper), "-StateDir", str(self.base / "gate-real")
        )
        self.assertEqual(0, r.returncode, r.stderr)
        return r.stdout

    def assert_denied(self, out: str):
        self.assertTrue(out.strip(), "the gate printed nothing for a real collision")
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual("deny", decision.get("permissionDecision"), out)
        self.assertIn("peer-branch", decision["permissionDecisionReason"])

    def test_the_fixture_reproduces_a_collision(self):
        """The positive control: a repo-relative path from the primary, the shape main always checked."""
        self.assert_denied(self.gate({"tool_input": {"file_path": ".claude/keep.txt"}}))

    def test_a_worktree_sessions_absolute_path_is_denied(self):
        self.assert_denied(self.gate({"tool_input": {"file_path": str(self.worktree / ".claude" / "keep.txt")}}))

    def test_after_a_cd_to_a_sibling_the_collision_is_still_denied(self):
        """korus#223 review point 1: this printed nothing and exited 0."""
        payload = {"cwd": str(self.sibling), "tool_input": {"file_path": str(self.worktree / ".claude" / "keep.txt")}}
        self.assert_denied(self.gate(payload))

    def test_after_a_cd_to_another_repository_the_collision_is_still_denied(self):
        payload = {"cwd": str(self.other), "tool_input": {"file_path": str(self.worktree / ".claude" / "keep.txt")}}
        self.assert_denied(self.gate(payload))

    def test_a_file_nobody_else_is_changing_is_allowed_in_silence(self):
        """The negative control: the deny above is about the collision, not about the payload shape."""
        payload = {"cwd": str(self.sibling), "tool_input": {"file_path": str(self.worktree / "ccx.config.json")}}
        self.assertEqual("", self.gate(payload).strip())


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

    def pin(self):
        """Pin the session to the worktree the way its startup would, through the session banner."""
        self.launch("sess-m", self.worktree)

    def test_after_a_cd_to_a_sibling_it_reads_the_first_worktrees_box(self):
        """korus#223 review point 4: the drain showed, and marked shown, the sibling's box."""
        self.pin()
        self.assertIn("MAIL-SENTINEL", self.drain({"cwd": str(self.sibling), "source": "compact"}))

    def test_after_a_cd_to_another_repository_it_reads_the_first_worktrees_box(self):
        """korus#223 review point 4: in another repository the drain said no mail while mail waited."""
        self.pin()
        self.assertIn("MAIL-SENTINEL", self.drain({"cwd": str(self.other), "source": "compact"}))

    def test_with_no_pin_a_sibling_cwd_reads_no_box(self):
        """Without the pin the sibling's cwd is refused, so no box is read and the drain says so."""
        ctx = self.drain({"cwd": str(self.sibling), "source": "compact"})
        self.assertNotIn("MAIL-SENTINEL", ctx)
        self.assertIn("NO BOX", ctx)


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
        self.launch("steer-0", self.worktree)
        self.assertIn("STEER-SENTINEL", self.steer({"session_id": "steer-0", "cwd": str(self.subdir)}))
        self.assertFalse(note.exists(), "the note was delivered but not consumed")

    def test_without_a_cwd_it_reads_the_project_dir(self):
        """The control. CLAUDE_PROJECT_DIR names the primary, so the worktree's note is never read."""
        note = self.plant(self.worktree, "STEER-SENTINEL")
        self.assertEqual("", self.steer({}).strip())
        self.assertTrue(note.exists())

    def test_a_missing_cwd_reads_no_note_and_says_so(self):
        """korus#223 review round 1: the fallback here is the primary, and its note is another session's."""
        note = self.plant(self.primary, "PRIMARY-NOTE")
        r = self.run_hook(STEER, {"cwd": str(self.missing)}, env={"CLAUDE_PROJECT_DIR": str(self.primary)})
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotIn("PRIMARY-NOTE", r.stdout)
        self.assertTrue(note.exists(), "the hook deleted the primary's note")
        self.assertIn("[steer-inject] the hook input names cwd", r.stderr)

    def test_a_missing_input_reader_reads_no_note_and_says_so(self):
        """korus#223 review round 2: without the helper the fallback took the primary's note."""
        scripts = self.stub_tree("tree-steer-no-helper")
        (scripts / "hooks" / "_hookinput.ps1").unlink()
        note = self.plant(self.primary, "PRIMARY-NOTE")
        r = self.run_hook(scripts / "hooks" / "steer-inject.ps1", {"cwd": str(self.worktree)},
                          env={"CLAUDE_PROJECT_DIR": str(self.primary)})
        self.assertNotIn("PRIMARY-NOTE", r.stdout)
        self.assertTrue(note.exists())
        self.assertIn("_hookinput.ps1 is missing", r.stderr)

    def test_a_non_ascii_cwd_survives_the_read(self):
        """The input is read as UTF-8 bytes. A console-code-page read mangles this name and falls back."""
        wt = self.base / ("caf" + chr(0xE9))
        self.git(self.primary, "worktree", "add", "-q", str(wt), "-b", "accent")
        self.plant(wt, "ACCENT-SENTINEL")
        self.launch("steer-acc", wt)
        self.assertIn("ACCENT-SENTINEL", self.steer({"session_id": "steer-acc", "cwd": str(wt)}))

    def test_a_cwd_in_another_repository_is_not_read_or_deleted(self):
        """korus#223 review point 2: the hook read another repository's note as typed text, then deleted it."""
        note = self.plant(self.other, "OTHER-REPO-NOTE")
        out = self.steer({"cwd": str(self.other)})
        self.assertNotIn("OTHER-REPO-NOTE", out)
        self.assertTrue(note.exists(), "the hook deleted a note in another repository")

    def test_a_bare_git_file_is_not_a_checkout(self):
        """korus#223 review point 2: a directory holding only an empty `.git` file passed as a worktree."""
        fake = self.base / "fake"
        fake.mkdir()
        (fake / ".git").write_text("", encoding="ascii")
        note = self.plant(fake, "FAKE-NOTE")
        self.assertNotIn("FAKE-NOTE", self.steer({"cwd": str(fake)}))
        self.assertTrue(note.exists())

    def test_after_a_cd_to_a_sibling_the_siblings_note_is_left_alone(self):
        """korus#223 review point 2: after a `cd` the hook took a sibling session's note."""
        self.launch("steer-1", self.worktree)
        theirs = self.plant(self.sibling, "SIBLING-NOTE")
        mine = self.plant(self.worktree, "MY-NOTE")
        out = self.steer({"session_id": "steer-1", "cwd": str(self.sibling), "hook_event_name": "PreToolUse"})
        self.assertIn("MY-NOTE", out)
        self.assertNotIn("SIBLING-NOTE", out)
        self.assertTrue(theirs.exists(), "the hook deleted the sibling's note")
        self.assertFalse(mine.exists())

    def test_with_no_pin_a_sibling_cwd_reads_no_note(self):
        """The Lander's re-review of korus#223: this case read the sibling's note when there was no
        pin. Now neither the sibling's note nor the primary's is read. The case above is its control."""
        theirs = self.plant(self.sibling, "SIBLING-NOTE")
        primary = self.plant(self.primary, "PRIMARY-NOTE")
        r = self.run_hook(STEER, {"session_id": "steer-2", "cwd": str(self.sibling)},
                          env={"CLAUDE_PROJECT_DIR": str(self.primary)})
        self.assertNotIn("SIBLING-NOTE", r.stdout)
        self.assertNotIn("PRIMARY-NOTE", r.stdout)
        self.assertTrue(theirs.exists() and primary.exists(), "a note was deleted")
        self.assertIn("no pin records", r.stderr)

    def test_a_stdin_timeout_reads_no_note(self):
        """The Lander's LOW finding: input still open when the read gave up fell back to
        CLAUDE_PROJECT_DIR and took the primary's note. Stdin is held open here until the hook exits."""
        primary = self.plant(self.primary, "PRIMARY-NOTE")
        e = dict(os.environ)
        for leak in ("CCX_CONFIG", "CCX_TRUNK", "CCX_SESSION_BANNER"):
            e.pop(leak, None)
        e["CLAUDE_PROJECT_DIR"] = str(self.primary)
        p = subprocess.Popen([self.pwsh, "-NoProfile", "-File", str(STEER)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e, cwd=str(self.primary))
        try:
            p.wait(timeout=TIMEOUT_SECONDS)
            out, err = p.stdout.read(), p.stderr.read()
        finally:
            p.kill()
            p.stdin.close()
            p.stdout.close()
            p.stderr.close()
        self.assertNotIn(b"PRIMARY-NOTE", out)
        self.assertTrue(primary.exists(), "the primary's note was taken on a timeout")
        self.assertIn(b"still open", err)


if __name__ == "__main__":
    unittest.main()
