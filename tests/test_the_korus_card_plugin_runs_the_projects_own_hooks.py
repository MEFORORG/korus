"""The korus-card plugin runs the project's own card and reprime hooks, once, or not at all.

WHAT THIS EXISTS FOR. `.claude/settings.example.json` wires the role card and the reprime with a
loud placeholder path, and a copier who merges it without editing gets neither. The plugin makes
the install the wiring. Its two SessionStart rows call one shim, and the shim runs the repository's
own `scripts/hooks/` copy. The plugin carries no copy of either script, because a copy drifts.

THE FAILURES IT PINS, IN THE ORDER A READER HITS THEM.

  1. A DOUBLE CARD. MessageFoundry's tracked settings already wire both scripts at SessionStart,
     and this machine's user settings carry a shim that runs the card hook. Where any of those
     wire the same script, the plugin must print nothing. `TheProjectsOwnWiringWins` pairs each
     silent arm with the unwired arm that prints the card, so the zero is not a dead shim.
  2. NOISE IN AN UNRELATED REPOSITORY. A user-scope install fires everywhere. A repository with
     no `ccx.config.json`, or with no script of its own, gets nothing.
  3. A SECOND GUARD. The reprime decides for itself whether a start is a compaction restart. The
     shim must not decide that too, so the reprime arms here drive the real script through the
     shim with a `startup` and a `compact` payload.

EVERY CASE DRIVES THE COMMAND STRING FROM `hooks/hooks.json`, with `${CLAUDE_PLUGIN_ROOT}`
substituted as the harness does. A test that called the shim by its own spelling would pass while
the plugin's row named a file that does not exist.

THE FIXTURE CARRIES THE REAL SCRIPTS. It copies `role-card-inject.ps1`, `precompact-reprime.ps1`,
the seat roster and the cards into a throwaway repository, because the card hook finds its roster
beside itself. A stub would prove the shim forwards bytes, not that a card arrives.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120
PLUGIN = t.REPO_ROOT / "plugins" / "korus-card"
HOOKS_JSON = PLUGIN / "hooks" / "hooks.json"
SHIM = PLUGIN / "hooks" / "run-project-hook.ps1"
CARD = "[role-card] SEAT: builder"
REPRIME = "[precompact]"
SCRIPTS = ("role-card-inject.ps1", "precompact-reprime.ps1")


def _commands() -> dict[str, str]:
    """The plugin's SessionStart command for each script, keyed by the script it runs."""
    spec = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for group in spec["hooks"]["SessionStart"]:
        for hook in group["hooks"]:
            command = hook["command"]
            for name in SCRIPTS:
                if name in command:
                    found[name] = command
    return found


def _wiring(command: str, event: str = "SessionStart") -> dict:
    """A settings object with one `command` row at `event`."""
    return {"hooks": {event: [{"hooks": [{"type": "command", "command": command}]}]}}


class _Project(unittest.TestCase):
    """A throwaway KORUS repository carrying the real hook scripts and an empty user config dir."""

    def setUp(self) -> None:
        if not t.find_pwsh():
            self.skipTest("pwsh is not on PATH, so the plugin's rows cannot run here")
        self.tmp = tempfile.TemporaryDirectory(prefix="korus-card-")
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.config = base / "config"
        self.config.mkdir()
        (self.repo / "scripts" / "hooks").mkdir(parents=True)
        (self.repo / "docs" / "roles").mkdir(parents=True)
        (self.repo / ".claude").mkdir()
        for name in SCRIPTS:
            shutil.copy(t.REPO_ROOT / "scripts" / "hooks" / name, self.repo / "scripts" / "hooks" / name)
        for card in (t.REPO_ROOT / "docs" / "roles").glob("*.card.md"):
            shutil.copy(card, self.repo / "docs" / "roles" / card.name)
        shutil.copy(t.REPO_ROOT / "docs" / "roles" / "seats.json", self.repo / "docs" / "roles" / "seats.json")
        (self.repo / "ccx.config.json").write_text('{"prefix": "ccx"}', encoding="ascii")
        (self.repo / ".claude" / "seat.local.txt").write_text("builder", encoding="ascii")
        for args in (("init", "-b", "work"), ("config", "user.email", "t@example.com"), ("config", "user.name", "t")):
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, timeout=TIMEOUT_SECONDS)
        (self.repo / ".git" / "ccx-coord").mkdir()

    def by_path(self, script: str) -> str:
        """A row that runs the fixture's own copy of `script` by its absolute path."""
        return f'pwsh -NoProfile -File "{(self.repo / "scripts" / "hooks" / script).as_posix()}"'

    def run_row(self, script: str, source: str = "startup", project: Path | None = None,
                cwd: Path | None = None) -> subprocess.CompletedProcess:
        command = _commands()[script].replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN))
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(PLUGIN), CLAUDE_CONFIG_DIR=str(self.config))
        env.pop("KORUS_SEAT", None)
        env.pop("CLAUDE_PROJECT_DIR", None)
        if project is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project)
        elif cwd is None:
            env["CLAUDE_PROJECT_DIR"] = str(self.repo)
        payload = json.dumps({"hook_event_name": "SessionStart", "source": source, "cwd": str(cwd or self.repo),
                              "session_id": "t", "transcript_path": ""})
        # The process runs from the temp root, so only CLAUDE_PROJECT_DIR or the payload's cwd
        # can lead the shim to the repository.
        r = subprocess.run(command, shell=True, input=payload, capture_output=True, text=True,
                           cwd=self.tmp.name, env=env, timeout=TIMEOUT_SECONDS)
        self.assertEqual(0, r.returncode, f"a SessionStart row must always exit 0. stderr: {r.stderr}")
        return r

    def settings(self, where: Path, body: dict | str) -> None:
        text = body if isinstance(body, str) else json.dumps(body)
        where.write_text(text, encoding="ascii")


class ThePluginIsWiredToTheShim(unittest.TestCase):
    def test_both_scripts_have_a_session_start_row(self):
        self.assertEqual(set(SCRIPTS), set(_commands()))

    def test_every_row_runs_the_shim_that_exists(self):
        for script, command in _commands().items():
            with self.subTest(script=script):
                self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/run-project-hook.ps1", command)
        self.assertTrue(SHIM.is_file())

    def test_the_plugin_ships_no_copy_of_either_script(self):
        """A copy drifts from the scripts it was taken from, and nothing reports the drift."""
        names = {p.name for p in PLUGIN.rglob("*") if p.is_file()}
        self.assertEqual(set(), names & set(SCRIPTS))

    def test_the_shim_adds_no_compaction_guard(self):
        """The reprime's own guard decides. A second one here could disagree with it."""
        source = t.strip_ps_comments(t.read(SHIM))
        self.assertNotRegex(source, r"['\"]compact['\"]")
        self.assertNotIn(".source", source)
        # The control: the same scan finds the reprime's own guard, so it can see one.
        reprime = t.strip_ps_comments(t.read(t.REPO_ROOT / "scripts" / "hooks" / "precompact-reprime.ps1"))
        self.assertRegex(reprime, r"['\"]compact['\"]")


class ItInjectsTheCardWhereNothingElseDoes(_Project):
    def test_startup_gets_the_card(self):
        self.assertIn(CARD, self.run_row("role-card-inject.ps1", "startup").stdout)

    def test_a_compaction_restart_gets_the_card_too(self):
        self.assertIn(CARD, self.run_row("role-card-inject.ps1", "compact").stdout)

    def test_the_reprime_speaks_after_a_compaction(self):
        self.assertIn(REPRIME, self.run_row("precompact-reprime.ps1", "compact").stdout)

    def test_the_reprime_is_silent_at_startup(self):
        """The script's own guard, reached through the shim. The arm above is its control."""
        self.assertEqual("", self.run_row("precompact-reprime.ps1", "startup").stdout.strip())


class TheProjectsOwnWiringWins(_Project):
    """Each silent arm here has the same fixture, unwired, as its control above."""

    def test_project_settings_wiring_the_card_silences_it(self):
        self.settings(self.repo / ".claude" / "settings.json", _wiring(self.by_path("role-card-inject.ps1")))
        self.assertEqual("", self.run_row("role-card-inject.ps1").stdout)

    def test_local_settings_wiring_the_card_silences_it(self):
        self.settings(self.repo / ".claude" / "settings.local.json", _wiring(self.by_path("role-card-inject.ps1")))
        self.assertEqual("", self.run_row("role-card-inject.ps1").stdout)

    def test_user_settings_wiring_the_card_silences_it(self):
        """The shape on the owner's machine: a user-scope shim that joins a relative path at run time."""
        shim = "$s = Join-Path $b 'scripts/hooks/role-card-inject.ps1'\nif (Test-Path -LiteralPath $s) { & $s }"
        self.settings(self.config / "settings.json", _wiring(shim))
        self.assertEqual("", self.run_row("role-card-inject.ps1").stdout)

    def test_a_row_naming_the_project_dir_variable_silences_it(self):
        self.settings(self.repo / ".claude" / "settings.json",
                      _wiring('pwsh -NoProfile -File "$CLAUDE_PROJECT_DIR/scripts/hooks/role-card-inject.ps1"'))
        self.assertEqual("", self.run_row("role-card-inject.ps1").stdout)

    def test_a_row_quoting_the_variable_before_the_path_silences_it(self):
        """The form the harness documents: the quotes close before the path goes on."""
        self.settings(self.repo / ".claude" / "settings.json",
                      _wiring('pwsh -NoProfile -File "$CLAUDE_PROJECT_DIR"/scripts/hooks/role-card-inject.ps1'))
        self.assertEqual("", self.run_row("role-card-inject.ps1").stdout)

    def test_project_settings_wiring_the_reprime_silences_it(self):
        self.settings(self.repo / ".claude" / "settings.json", _wiring(self.by_path("precompact-reprime.ps1")))
        self.assertEqual("", self.run_row("precompact-reprime.ps1", "compact").stdout)

    def test_wiring_one_script_leaves_the_other_running(self):
        """Standing down is per script. MessageFoundry wires both; a copier may wire one."""
        self.settings(self.repo / ".claude" / "settings.json", _wiring(self.by_path("precompact-reprime.ps1")))
        self.assertIn(CARD, self.run_row("role-card-inject.ps1").stdout)

    def test_a_row_on_another_event_is_not_wiring(self):
        """The old example wired the reprime on PreCompact, where it never reached context."""
        self.settings(self.repo / ".claude" / "settings.json",
                      _wiring(self.by_path("precompact-reprime.ps1"), "PreCompact"))
        self.assertIn(REPRIME, self.run_row("precompact-reprime.ps1", "compact").stdout)

    def test_settings_under_the_session_directory_are_read_too(self):
        """A session started in a subdirectory: the harness reads settings there, not at the top."""
        sub = self.repo / "sub"
        (sub / ".claude").mkdir(parents=True)
        self.settings(sub / ".claude" / "settings.json", _wiring(self.by_path("role-card-inject.ps1")))
        self.assertEqual("", self.run_row("role-card-inject.ps1", project=sub).stdout)


class ARowThatRunsNothingIsNotWiring(_Project):
    """Standing down for a row that runs nothing leaves the session with no card at all."""

    def test_the_example_placeholder_left_in_does_not_count(self):
        row = 'pwsh -NoProfile -File "REPLACE_WITH_ABSOLUTE_PATH_TO_YOUR_CHECKOUT/scripts/hooks/role-card-inject.ps1"'
        self.settings(self.repo / ".claude" / "settings.json", _wiring(row))
        self.assertIn(CARD, self.run_row("role-card-inject.ps1").stdout)

    def test_a_path_to_a_checkout_that_is_gone_does_not_count(self):
        gone = (Path(self.tmp.name) / "deleted-checkout" / "scripts" / "hooks" / "role-card-inject.ps1").as_posix()
        self.settings(self.repo / ".claude" / "settings.json", _wiring(f'pwsh -NoProfile -File "{gone}"'))
        self.assertIn(CARD, self.run_row("role-card-inject.ps1").stdout)

    def test_a_gone_short_name_path_does_not_count(self):
        """A Windows 8.3 short name carries a ~ that is not a home directory."""
        gone = (Path(self.tmp.name) / "OLDCHE~1" / "scripts" / "hooks" / "role-card-inject.ps1").as_posix()
        self.settings(self.repo / ".claude" / "settings.json", _wiring(f'pwsh -NoProfile -File "{gone}"'))
        self.assertIn(CARD, self.run_row("role-card-inject.ps1").stdout)

    def test_a_home_relative_path_is_taken_on_trust(self):
        """The control for the case above: a LEADING ~ is a home directory, so it counts."""
        self.settings(self.repo / ".claude" / "settings.json",
                      _wiring('pwsh -NoProfile -File "~/korus/scripts/hooks/role-card-inject.ps1"'))
        self.assertEqual("", self.run_row("role-card-inject.ps1").stdout)

    def test_a_longer_file_name_that_ends_the_same_does_not_count(self):
        (self.repo / "scripts" / "hooks" / "my-role-card-inject.ps1").write_text("exit 0\n", encoding="ascii")
        self.settings(self.repo / ".claude" / "settings.json", _wiring(self.by_path("my-role-card-inject.ps1")))
        self.assertIn(CARD, self.run_row("role-card-inject.ps1").stdout)

    def test_a_settings_file_that_does_not_parse_but_names_the_script_stands_down(self):
        self.settings(self.repo / ".claude" / "settings.json", '{ "role-card-inject.ps1": ')
        self.assertEqual("", self.run_row("role-card-inject.ps1").stdout)


class ItFindsTheRepositoryWithoutTheProjectVariable(_Project):
    def test_the_payload_cwd_leads_to_the_repository(self):
        self.assertIn(CARD, self.run_row("role-card-inject.ps1", cwd=self.repo).stdout)

    def test_a_subdirectory_walks_up_to_the_repository_root(self):
        sub = self.repo / "deep" / "er"
        sub.mkdir(parents=True)
        self.assertIn(CARD, self.run_row("role-card-inject.ps1", project=sub).stdout)


class TheChildIsRunFaithfully(_Project):
    def test_a_non_ascii_payload_reaches_the_child_byte_for_byte(self):
        echo = "$ms = [System.IO.MemoryStream]::new(); [Console]::OpenStandardInput().CopyTo($ms)\n" \
               "[Console]::Out.Write([Convert]::ToHexString($ms.ToArray()))\n"
        (self.repo / "scripts" / "hooks" / "role-card-inject.ps1").write_text(echo, encoding="ascii")
        payload = '{"cwd": "caf\u00e9"}'.encode("utf-8")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.repo), CLAUDE_CONFIG_DIR=str(self.config))
        r = subprocess.run([t.find_pwsh() or "pwsh", "-NoProfile", "-File", str(SHIM), "-Script", "role-card-inject.ps1"],
                           input=payload, capture_output=True, env=env, timeout=TIMEOUT_SECONDS)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(payload.hex().upper(), r.stdout.decode("ascii").strip())

    def test_a_failing_child_is_reported_not_silent(self):
        (self.repo / "scripts" / "hooks" / "role-card-inject.ps1").write_text(
            "[Console]::Error.Write('child broke'); exit 3\n", encoding="ascii")
        r = self.run_row("role-card-inject.ps1")
        self.assertIn("exited 3", r.stdout)
        self.assertIn("child broke", r.stderr)


class ItIsSilentInARepositoryThatDidNotOptIn(_Project):
    def test_no_ccx_config_means_no_card(self):
        (self.repo / "ccx.config.json").unlink()
        for script in SCRIPTS:
            with self.subTest(script=script):
                self.assertEqual("", self.run_row(script, "compact").stdout)

    def test_no_script_of_its_own_means_nothing_runs(self):
        for script in SCRIPTS:
            (self.repo / "scripts" / "hooks" / script).unlink()
        for script in SCRIPTS:
            with self.subTest(script=script):
                self.assertEqual("", self.run_row(script, "compact").stdout)

    def test_an_unknown_script_name_runs_nothing(self):
        """Each planted script prints a marker, so running it could not pass as silence."""
        marker = "Write-Output 'PLANTED-SCRIPT-RAN'\n"
        (self.repo / "scripts" / "hooks" / "other.ps1").write_text(marker, encoding="ascii")
        (self.repo / "x.ps1").write_text(marker, encoding="ascii")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.repo), CLAUDE_CONFIG_DIR=str(self.config))
        for name in ("other.ps1", "../../x.ps1"):
            with self.subTest(script=name):
                r = subprocess.run([t.find_pwsh() or "pwsh", "-NoProfile", "-File", str(SHIM), "-Script", name],
                                   input="{}", capture_output=True, text=True, env=env, timeout=TIMEOUT_SECONDS)
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertEqual("", r.stdout)
        # The control: the marker does print when the planted script is run directly.
        direct = subprocess.run([t.find_pwsh() or "pwsh", "-NoProfile", "-File", str(self.repo / "x.ps1")],
                                capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        self.assertIn("PLANTED-SCRIPT-RAN", direct.stdout)


if __name__ == "__main__":
    unittest.main()
