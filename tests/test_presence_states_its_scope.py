"""The presence roster is scoped to one repository, and a reader who misses that states a negative.

THE MEASURED FAILURE. Sessions were reporting "there is no Lander". Measured 2026-09-19 on this
machine: `presence.ps1` from a korus worktree listed 2 live sessions and no Lander, while a live
Lander -- `isRunning: true`, active that minute -- was working `MessageFoundry` in the same fleet.
`presence.ps1 -Repo <that repo>` listed 6, including it. `presence.ps1 -Fleet` lists 8 across both.

WHY THE ROSTER WAS NOT WRONG. It answered the question it was asked, which was scoped to one repo
family. The reader asked a fleet-wide question and read a repo-scoped answer, and nothing in the
output said which one it was.

THAT IS THIS FILE'S SUBJECT. Not the count, which is correct, but whether the output states its own
scope. `roles/COMMON.md` already carries the same shape for the ACCOUNT axis -- two rosters that see
different halves of the fleet -- and said nothing about the repo axis, which is the one that bit.

THE OTHER AXIS IS NOT FIXED BY THIS. `list_sessions` is account-scoped and repo-wide; `presence.ps1`
is repo-scoped and account-wide. Neither is a superset, and `-Fleet` widens only the second. A seat
on another machine is still invisible to both.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 180

PRESENCE = t.REPO_ROOT / "scripts" / "coord" / "presence.ps1"
COMMON = t.REPO_ROOT / "roles" / "COMMON.md"


class TheScriptOffersAFleetWideScope(unittest.TestCase):
    """A reader who needs the wider answer must have a command that gives it."""

    def source(self) -> str:
        return t.ps_source(PRESENCE)

    def test_the_fleet_switch_exists(self):
        self.assertIn("$Fleet", self.source())

    def test_the_control_shows_the_source_is_readable(self):
        """Without this, an unreadable or emptied file passes the assertion above by returning ''."""
        src = self.source()
        self.assertIn("$Repo", src, "the pre-existing -Repo parameter is missing, so the read failed")
        self.assertGreater(len(src), 2000)

    def test_the_fleet_switch_reads_the_record_wrapper_not_the_record(self):
        """The bug this file was written beside.

        `Get-SessionRecords` returns {Root, File, Record, Unreadable, Error}. Reading `$rec.cwd`
        yields null on every record, the hint list collapses to empty, and -Fleet silently scopes
        to ONE repository while printing the word FLEET. Measured: it reported "the FLEET (1
        repositories)" against a true answer of 2.
        """
        self.assertIn("$rec.Record.cwd", self.source())
        self.assertNotIn("$rec.cwd", self.source())


class TheDefaultRosterSaysItIsScoped(unittest.TestCase):
    """A count that omits half the fleet must not render as the whole of it.

    The file already argues this for a PARTIAL roster, under "A PARTIAL ROSTER MUST NOT RENDER AS A
    COMPLETE ONE". The repo scope is the same failure one level up: every record placed, every
    config root read, and a number that still answers a narrower question than the reader asked.
    """

    def source(self) -> str:
        return t.ps_source(PRESENCE)

    def test_the_default_run_warns_that_it_is_scoped_to_one_repository(self):
        self.assertIn("SCOPED TO THIS REPOSITORY", self.source())

    def test_the_warning_names_the_command_that_widens_it(self):
        """A warning with no remedy attached gets read and not acted on."""
        src = self.source()
        self.assertRegex(src, r"presence\.ps1 -Fleet")

    def test_the_heading_is_not_hardcoded_to_one_repo(self):
        """The heading read "in this repo" unconditionally, including under -Fleet."""
        self.assertNotIn('Live Claude sessions in this repo', self.source())


class TheRuleIsWrittenWhereASeatReadsIt(unittest.TestCase):
    """A script that warns at the moment of use is half the fix; the standing rule is the other half.

    A seat that has already written "there is no Lander" did not run the script first. COMMON.md is
    what it read instead.
    """

    def common(self) -> str:
        return t.read(COMMON)

    def test_common_carries_the_repo_axis(self):
        self.assertIn("repo-scoped", self.common().lower())

    def test_common_forbids_the_bare_absence_claim(self):
        self.assertIn("there is no", self.common().lower())

    def test_the_control_shows_common_was_actually_read(self):
        """An empty or missing file would satisfy nothing above and everything below it."""
        text = self.common()
        self.assertGreater(len(text), 10000)
        self.assertIn("Coordinate before you write", text)


class TheRosterRunsAndAgreesWithItself(unittest.TestCase):
    """An end-to-end pass. It asserts shape, never a session count, which moves minute to minute.

    THE PRECONDITION IS PART OF THE TEST, and leaving it out is what reddened CI on the first
    attempt. `presence.ps1` renders a roster only where a Claude Code config root exists. A CI
    runner has none, so the script correctly refuses and prints "Roster UNAVAILABLE" instead of the
    scope line these tests look for.

    The first version asserted the scope line unconditionally. It passed on the author's machine,
    which has a registry, and failed on `gates (windows-latest)`, which does not -- the same shape
    as every finding in `roles/WATCHDOG.md` section 4: a reading whose filter did not match what it
    claimed to check.

    So the environment is established first and the run is skipped with a reason where no roster can
    exist. `TheRosterRefusesRatherThanReportingNobody` below then covers the refusal path, and it
    runs everywhere, so this file is not silently vacuous on the machines that skip.
    """

    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so the roster cannot be executed here")
        self.pwsh: str = pwsh
        if "Roster UNAVAILABLE" in self.run_presence().stdout:
            self.skipTest(
                "no Claude Code config root on this machine, so presence.ps1 refuses to render a "
                "roster at all -- the refusal path is covered by "
                "TheRosterRefusesRatherThanReportingNobody"
            )

    def run_presence(self, *args: str):
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(PRESENCE), *args],
            capture_output=True, text=True, cwd=str(t.REPO_ROOT), timeout=TIMEOUT_SECONDS,
        )

    def test_the_default_run_prints_the_scope_warning(self):
        r = self.run_presence()
        self.assertIn(r.returncode, (0, 2), r.stderr)
        self.assertIn("SCOPED TO THIS REPOSITORY", r.stdout)

    def test_the_fleet_run_does_not_print_the_scope_warning(self):
        """The control for the test above: the same instrument, a run that must NOT satisfy it."""
        r = self.run_presence("-Fleet")
        self.assertIn(r.returncode, (0, 2), r.stderr)
        self.assertNotIn("SCOPED TO THIS REPOSITORY", r.stdout)

    def test_the_fleet_run_names_how_many_repositories_it_covered(self):
        """A fleet count with no denominator cannot be told from a repo count."""
        r = self.run_presence("-Fleet")
        self.assertRegex(r.stdout, r"FLEET \(\d+ repositor")

    def test_the_fleet_run_never_covers_fewer_repositories_than_one(self):
        """Guards the collapse this file's other control describes, at runtime rather than in source."""
        r = self.run_presence("-Fleet")
        m = re.search(r"FLEET \((\d+) repositor", r.stdout)
        self.assertIsNotNone(m, f"no fleet count in output: {r.stdout[:300]}")
        self.assertGreaterEqual(int(m.group(1)), 1)


class TheRosterRefusesRatherThanReportingNobody(unittest.TestCase):
    """The path a CI runner actually takes, and the reason the skip above is not a hole.

    An empty roster and an unexamined one are the same two bytes to a consumer. `presence.ps1`
    already argues this for itself; this pins it, and it runs on every machine because it supplies
    its own empty config root rather than depending on the one the host happens to have.
    """

    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so the roster cannot be executed here")
        self.pwsh: str = pwsh

    def run_with_no_registry(self, *args: str):
        """Point the script at an empty directory, so no config root can be found."""
        with tempfile.TemporaryDirectory(prefix="ccx-noroster-") as tmp:
            return subprocess.run(
                [self.pwsh, "-NoProfile", "-File", str(PRESENCE), "-ConfigRoot", tmp, *args],
                capture_output=True, text=True, cwd=str(t.REPO_ROOT), timeout=TIMEOUT_SECONDS,
            )

    def test_an_absent_registry_says_so_rather_than_listing_nobody(self):
        r = self.run_with_no_registry()
        self.assertIn("UNAVAILABLE", r.stdout + r.stderr)

    def test_it_says_the_empty_result_is_not_an_all_clear(self):
        """The whole point. A consumer must not read 'nothing found' as 'nobody is live'."""
        r = self.run_with_no_registry()
        self.assertIn("NOT", r.stdout + r.stderr)

    def test_it_does_not_exit_zero_on_an_unexamined_roster(self):
        """Exit 0 beside an empty list is the reading that cannot be told from a real all-clear."""
        r = self.run_with_no_registry()
        self.assertNotEqual(0, r.returncode)


if __name__ == "__main__":
    unittest.main()
