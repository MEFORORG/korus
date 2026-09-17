"""`rescue.ps1` must restore the entry it pushed, not whatever is on top of the shared stack.

THE FAILURE THIS EXISTS FOR. The stash stack lives in the shared git directory, so one stack serves
every worktree of a clone. `rescue.ps1` pushes the primary's work, then runs `new.ps1` as a child
process -- a fetch and a setup hook, seconds to minutes -- and only then restores. It used to restore
with a bare `git stash pop`, which means `stash@{0}`, which by then may be somebody else's.

Measured on the fixture below, against the shipped code with the restore reverted to that bare pop:
the rescue worktree came out holding `peer-untracked.txt` and the peer's edit to `tracked.txt`, and
the work the script was asked to move was gone from the stack as well. Two sessions' work, both in
the wrong place, and exit 0. With the object name pinned, the same fixture puts `mine-untracked.txt`
and the primary's own edit in the worktree and leaves the peer's entry untouched at `stash@{0}`.

WHAT THIS PROVES, AND HOW. The behavioural cases RUN rescue.ps1 against a throwaway repository. The
peer arrives through the repository's own setup hook, which `new.ps1` invokes in a child pwsh with
`CCX_PRIMARY_ROOT` set -- inside the window, with no threads and no sleeps. The hook is the shipped
mechanism, not a shim: it exits 0, so nothing about the run is degraded to make the fixture work.

Every case carries a control. The peer's own entry is asserted to exist before the target is judged,
because a green "the peer's work stayed put" is equally consistent with a hook that never ran. The
no-peer case proves the rescue still works when nothing contends, so the headline case cannot pass
by rescuing nothing. And `TheSameFixtureCatchesTheBarePop` runs the whole thing again against a copy
of `scripts/` with the restore reverted, and requires the headline assertion to go red.

WHAT IT DOES NOT PROVE. Not that the window is closed. Three reads remain that are not atomic
against a peer: the push and the pin are two commands, and so are the drop's index lookup and the
drop itself. The script detects both -- it refuses to continue when no entry carries its token, and
it reads git's own "Dropped ... (<sha>)" receipt and puts the entry back with `git stash store` when
the receipt names somebody else. This file pins the detection, not an absence of races. It also says
nothing about `--index`: neither `pop` nor `apply` restores a staged index here, and this change did
not alter that.

THE STATIC CASE READS THE SOURCE instead of running it, so this file still measures something on a
host with no `pwsh` or no `git`, where everything else skips.

Run: cd tests && python -m unittest discover -s . -q
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

RESCUE = t.REPO_ROOT / "scripts" / "worktree" / "rescue.ps1"

TIMEOUT_SECONDS = 180

# A fixture repo must not inherit the operator's identity, signing config, or advice settings: a
# commit that needs a passphrase, or a hook that runs, turns a test failure into a hang.
GIT_ID = (
    "-c", "user.email=ccx@test", "-c", "user.name=ccx test",
    "-c", "commit.gpgsign=false", "-c", "advice.detachedHead=false",
)

# The real session's own coordination variables must not reach the fixture. CCX_TRUNK in particular
# would override the pinned trunk; CCX_CONFIG would point the run at another repository's knobs.
ENV_LEAKS = ("CCX_CONFIG", "CCX_TRUNK", "CCX_STATE_ROOT")

# The line this change replaced. Kept as the mutation, so the control reverts exactly one thing.
PINNED_RESTORE = "& git -C $Target stash apply $stashSha"
BARE_POP_RESTORE = "& git -C $Target stash pop"

# `stash pop` in executable PowerShell. The word boundary keeps `stash popped` and similar out; the
# comment strip below keeps the header's explanation of why the pop is gone out.
BARE_POP = re.compile(r"\bstash\s+pop\b")

# A `stash@{...}` that is not inside a quoted string. pwsh parses a bareword `stash@{0}` as the start
# of a hashtable and dies at RUNTIME with "ScriptBlock should only be specified as a value of the
# Command parameter" -- and `[Parser]::ParseFile` reports ZERO errors on the same file, so CI's
# "PowerShell parses" step does not catch it. This is the only instrument that does.
BAREWORD_STASH_REF = re.compile(r"(?<!['\"])stash@\{")

# The setup hook the fixture installs. new.ps1 runs it in a child pwsh between rescue's push and its
# restore, with CCX_PRIMARY_ROOT naming the primary. A non-zero exit aborts rescue.ps1 before the
# restore, so it must end in `exit 0` or every behavioural case below measures an aborted run.
#
# The last line is the instrument. It records the stack AS THE PEER LEFT IT, inside the window, to a
# file outside the repository that nothing stashes or restores. Reading the stack after the run
# instead would not work: a bare pop CONSUMES the peer's entry, so the mutation control would report
# "the peer never arrived" for the very run in which the peer's work was taken.
PEER_HOOK = """$ErrorActionPreference = 'Stop'
$p = $env:CCX_PRIMARY_ROOT
Set-Content -LiteralPath (Join-Path $p 'peer-untracked.txt') -Value 'PEER-PAYLOAD' -Encoding ascii
Add-Content -LiteralPath (Join-Path $p 'tracked.txt') -Value 'PEER-TRACKED-EDIT'
& git -C $p stash push --include-untracked -m 'peer WIP -- must not be taken'
& git -C $p stash list --format='%gs' | Set-Content -LiteralPath $env:CCX_PEER_MARKER -Encoding ascii
exit 0
"""


class RescueCase(unittest.TestCase):
    """A primary with uncommitted work, a peer that stashes mid-run, and a way to run the rescue."""

    #: Set to False by the negative control, which builds a primary with no setup hook at all.
    PEER = True

    #: Overridden by the mutation control to point at a modified copy of `scripts/`.
    def script_root(self) -> Path:
        return t.REPO_ROOT / "scripts"

    def setUp(self):
        self.pwsh = t.find_pwsh()
        if not self.pwsh:
            self.skipTest("pwsh is not on PATH, so rescue.ps1 cannot be executed here")
        if not shutil.which("git"):
            self.skipTest("git is not on PATH, so the fixture repository cannot be built")
        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-rescue-", ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.marker = self.base / "peer-saw-this.txt"
        self.primary = self.fixture(peer=self.PEER)

    def git(self, *args, cwd=None) -> str:
        r = subprocess.run(
            ["git", *GIT_ID, *args],
            cwd=str(cwd or self.primary), capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        )
        self.assertEqual(0, r.returncode, f"git {' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
        return r.stdout

    def fixture(self, peer: bool) -> Path:
        primary = self.base / "primary"
        primary.mkdir()
        self.git("init", "-q", "-b", "main", str(primary), cwd=self.base)
        # trunk is pinned rather than 'auto': the fixture has no remote, so there is no recorded
        # default branch for auto to resolve, and the run would refuse before doing anything.
        config = {"prefix": "ccx", "trunk": "main", "worktreeLayout": "sibling"}
        if peer:
            config["setupHook"] = "hook.ps1"
        (primary / "ccx.config.json").write_text(json.dumps(config), encoding="ascii")
        (primary / "hook.ps1").write_text(PEER_HOOK, encoding="ascii")
        (primary / "tracked.txt").write_text("base\n", encoding="ascii")
        self.git("add", "-A", cwd=primary)
        self.git("commit", "-qm", "init", cwd=primary)

        # The work to be rescued: one tracked edit and one untracked file. Both, because
        # --include-untracked is the reason this script exists rather than a plain `git stash`.
        with (primary / "tracked.txt").open("a", encoding="ascii") as fh:
            fh.write("MINE-TRACKED-EDIT\n")
        (primary / "mine-untracked.txt").write_text("MINE-PAYLOAD\n", encoding="ascii")
        return primary

    def rescue(self, name: str = "demo") -> subprocess.CompletedProcess:
        env = dict(os.environ)
        for leak in ENV_LEAKS:
            env.pop(leak, None)
        env["CCX_PEER_MARKER"] = str(self.marker)
        # cwd is load-bearing, not tidiness. rescue.ps1 resolves the primary from the CURRENT
        # DIRECTORY, so a run launched from anywhere else rescues THAT checkout -- a real repository,
        # emptied into a real worktree, reporting success.
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(self.script_root() / "worktree" / "rescue.ps1"),
             "-Name", name],
            capture_output=True, text=True, env=env, cwd=str(self.primary), timeout=TIMEOUT_SECONDS,
        )

    def stack(self) -> list[str]:
        return [ln for ln in self.git("stash", "list", "--format=%H %gs").splitlines() if ln.strip()]

    def target(self, name: str = "demo") -> Path:
        return self.base / f"primary-{name}"

    def assert_the_peer_actually_stashed(self, run: subprocess.CompletedProcess):
        """The instrument, checked before anything resting on it.

        Without this, every assertion below is equally consistent with a setup hook that never ran --
        in which case nothing ever contended for `stash@{0}` and the case proves nothing at all.

        It reads the marker the hook wrote INSIDE the window, not the stack afterwards. The two
        answers differ under the mutation control, where the bare pop has consumed the peer's entry
        by the time the run ends.
        """
        self.assertTrue(
            self.marker.is_file(),
            "the setup hook never wrote its marker, so nothing arrived inside the window and this "
            "fixture is not testing contention. The hook runs from new.ps1 and must exit 0; a "
            "non-zero exit aborts rescue.ps1 before the restore.\n"
            f"--- rescue stdout ---\n{run.stdout}\n--- rescue stderr ---\n{run.stderr}",
        )
        self.assertIn(
            "peer WIP", self.marker.read_text(encoding="ascii"),
            "the hook ran but its stash push did not reach the stack, so `stash@{0}` was never "
            "contended and nothing below is measuring the shared-stack failure.",
        )


class APeerStashInTheWindowIsNotTaken(RescueCase):
    def test_the_rescue_worktree_gets_the_primarys_work_and_not_the_peers(self):
        run = self.rescue()
        self.assert_the_peer_actually_stashed(run)
        target = self.target()
        self.assertTrue(
            target.is_dir(),
            f"the rescue worktree was never created (exit {run.returncode}):\n{run.stdout}\n{run.stderr}",
        )

        tracked = (target / "tracked.txt").read_text(encoding="ascii")
        self.assertIn(
            "MINE-TRACKED-EDIT", tracked,
            "the rescue worktree does not carry the edit the primary was asked to move. The restore "
            "took some other entry off the shared stack.",
        )
        self.assertNotIn(
            "PEER-TRACKED-EDIT", tracked,
            "the rescue worktree carries a PEER SESSION'S edit. A bare `git stash pop` means "
            "`stash@{0}`, and the stack is shared with every worktree of this clone, so whoever "
            "stashed last during new.ps1 is whose work gets moved here.",
        )
        self.assertTrue(
            (target / "mine-untracked.txt").is_file(),
            "the untracked file the primary was carrying did not arrive. --include-untracked put it "
            "in the entry; the restore did not take it out.",
        )
        self.assertFalse(
            (target / "peer-untracked.txt").exists(),
            "a peer session's untracked file was moved into this worktree.",
        )

    def test_the_peers_entry_survives_and_the_rescues_own_entry_is_dropped(self):
        run = self.rescue()
        self.assert_the_peer_actually_stashed(run)
        rows = self.stack()
        self.assertEqual(
            1, len(rows),
            "the stack should hold exactly the peer's entry: the rescue's own entry is spent once it "
            "has been applied, and nothing else was ever pushed.\n" + "\n".join(rows),
        )
        self.assertIn(
            "peer WIP", rows[0],
            "the entry left on the stack is not the peer's, so the drop took the wrong one.",
        )
        self.assertFalse(
            any("rescue -> demo" in row for row in rows),
            "the rescue left its own spent entry on the shared stack. Every rescue would then add "
            "one more, and `git stash list` stops being readable for everybody.",
        )

    def test_the_primary_is_emptied_of_the_work_it_was_asked_to_move(self):
        run = self.rescue()
        self.assert_the_peer_actually_stashed(run)
        self.assertEqual(
            0, run.returncode,
            f"rescue.ps1 exited {run.returncode}:\n{run.stdout}\n{run.stderr}",
        )
        self.assertNotIn(
            "MINE-TRACKED-EDIT", (self.primary / "tracked.txt").read_text(encoding="ascii"),
            "the work is now in two places. A rescue that leaves a copy behind is the duplication "
            "the --include-untracked note in rescue.ps1 exists to prevent.",
        )
        self.assertFalse((self.primary / "mine-untracked.txt").exists())


class ARescueWithNobodyContendingStillWorks(RescueCase):
    """The negative control. Proves the headline case is not passing on a rescue that does nothing."""

    PEER = False

    def test_the_work_moves_and_the_stack_is_left_empty(self):
        run = self.rescue()
        self.assertEqual(
            0, run.returncode, f"rescue.ps1 exited {run.returncode}:\n{run.stdout}\n{run.stderr}")
        target = self.target()
        self.assertIn("MINE-TRACKED-EDIT", (target / "tracked.txt").read_text(encoding="ascii"))
        self.assertTrue((target / "mine-untracked.txt").is_file())
        self.assertEqual(
            [], self.stack(),
            "nothing else ever pushed, so the stack must be empty once the rescue's own entry is "
            "dropped. Anything here is litter on a stack every worktree of this clone shares.",
        )


class TheSameFixtureCatchesTheBarePop(APeerStashInTheWindowIsNotTaken):
    """Prove the instrument. Revert the restore to the bare pop and require the case to go red.

    A green suite against the shipped code is equally consistent with a fixture whose peer never
    contends for `stash@{0}` -- so the fixture has to be shown catching the thing it was built for.
    One line is reverted and nothing else, so what the mutant measures is the restore and not some
    second difference introduced by the copy.

    The mutant is slightly harsher than the code that shipped: the drop this change added is still
    present, so under the mutant the rescue's own entry is dropped after the peer's was popped, and
    the stack ends up empty rather than holding the orphan. The assertion these cases turn on -- whose
    work reaches the worktree -- is the same either way.
    """

    def setUp(self):
        super().setUp()
        self.mutant = self.base / "mutant"
        shutil.copytree(t.REPO_ROOT / "scripts", self.mutant)
        script = self.mutant / "worktree" / "rescue.ps1"
        source = script.read_text(encoding="ascii")
        self.assertIn(
            PINNED_RESTORE, source,
            f"rescue.ps1 no longer restores with `{PINNED_RESTORE}`, so this control reverts nothing "
            "and every case in this class passes against an unmodified script. Re-point the mutation "
            "at whatever the restore is now. Do NOT delete the class: it is the only thing here that "
            "shows the fixture can fail.",
        )
        script.write_text(source.replace(PINNED_RESTORE, BARE_POP_RESTORE), encoding="ascii")

    def script_root(self) -> Path:
        return self.mutant

    def test_the_rescue_worktree_gets_the_primarys_work_and_not_the_peers(self):
        with self.assertRaises(AssertionError):
            super().test_the_rescue_worktree_gets_the_primarys_work_and_not_the_peers()

    def test_the_peers_entry_survives_and_the_rescues_own_entry_is_dropped(self):
        with self.assertRaises(AssertionError):
            super().test_the_peers_entry_survives_and_the_rescues_own_entry_is_dropped()

    def test_the_primary_is_emptied_of_the_work_it_was_asked_to_move(self):
        """NOT inverted. The bare pop still empties the primary -- it just fills the wrong worktree.

        Kept so the mutant is shown failing for the reason claimed. A mutation that broke the run
        outright would redden the two cases above without saying anything about `stash@{0}`.
        """
        super().test_the_primary_is_emptied_of_the_work_it_was_asked_to_move()


class TheSourceNeverOffersABarePop(unittest.TestCase):
    """Reading, not running -- so this file still measures something with no pwsh and no git.

    It also covers what the behavioural cases structurally cannot: the `finally` block only prints,
    and what it prints is pasted into a shell by a person. A bare pop offered there is the same bug,
    moved out of the script and into the operator.
    """

    def source(self) -> str:
        # Comments stripped, and that is mandatory rather than tidy here: this script's header now
        # explains at length why the pop is gone. A raw-text scan is one reword away from matching
        # the prose that describes the fix instead of the fix.
        return t.ps_source(RESCUE)

    def test_no_bare_pop_survives_anywhere_in_the_script(self):
        hits = BARE_POP.findall(self.source())
        self.assertEqual(
            [], hits,
            "rescue.ps1 still runs or prints a bare `git stash pop`. `pop` means `stash@{0}`, and "
            "the stack is shared with every worktree of this clone -- so it takes whichever entry "
            "some other session pushed last. Name the entry by object name instead.",
        )

    def test_the_matcher_would_catch_one(self):
        """Prove the instrument. A pattern that matches nothing gives the same green as a clean file."""
        self.assertTrue(BARE_POP.search("    & git -C $Target stash pop\n"))
        self.assertTrue(BARE_POP.search('Write-Warning "  git stash pop   # put it back"'))
        self.assertFalse(BARE_POP.search("& git -C $Target stash apply $stashSha"))
        self.assertFalse(BARE_POP.search("$popped = $true"))

    def test_the_restore_names_the_entry_by_object_name(self):
        source = self.source()
        self.assertIn(
            PINNED_RESTORE, source,
            "the restore no longer applies the pinned object name. Whatever replaced it has to be "
            "immune to another session pushing onto the shared stack while new.ps1 runs.",
        )
        self.assertRegex(
            source, r"\$stashSha\s*=\s*Get-RescueStashSha\b",
            "nothing pins the entry after the push, so `$stashSha` names something this run did not "
            "put on the stack.",
        )

    def test_the_drop_resolves_its_index_at_drop_time(self):
        """`git stash drop` refuses an object name, so the index has to be looked up -- late.

        Dropping an entry renumbers every entry beneath it. An index read at push time and used
        after new.ps1 can name a different session's entry by then.
        """
        source = self.source()
        lookup = re.search(r"\$index\s*=\s*Get-RescueStashIndex\b", source)
        drop = re.search(r"stash\s+drop\s+\$index\b", source)
        self.assertIsNotNone(lookup, "nothing resolves the object name back to a `stash@{n}` index.")
        self.assertIsNotNone(drop, "the drop does not use the resolved index.")
        self.assertLess(
            lookup.start(), drop.start(),
            "the index is used before it is looked up, which cannot be what was meant.",
        )

    def test_a_wrong_drop_is_put_back_rather_than_reported(self):
        """The lookup and the drop are two commands. git's receipt says which entry actually died."""
        source = self.source()
        self.assertIn(
            "stash store", source,
            "nothing restores an entry dropped by mistake. `git stash drop` prints "
            "`Dropped stash@{n} (<sha>)`, and a dropped stash commit is still a commit -- so a drop "
            "that took the wrong entry is recoverable, but only if the script reads that receipt.",
        )
        self.assertRegex(
            source, r"\[0-9a-f\]\{40\}",
            "the receipt is not parsed for an object name, so nothing compares what git dropped "
            "against what this run meant to drop.",
        )

    def test_no_stash_ref_is_left_as_a_pwsh_bareword(self):
        """`[Parser]::ParseFile` returns zero errors on a bareword `stash@{0}`; pwsh then dies on it.

        Measured at git 2.55.0.windows.5 / pwsh 7.6.6: `& git rev-parse stash@{0}` throws
        "ScriptBlock should only be specified as a value of the Command parameter" at runtime, while
        the CI step that checks the file parses reports it clean. Nothing else here would catch it.
        """
        hits = BAREWORD_STASH_REF.findall(self.source())
        self.assertEqual(
            [], hits,
            "a `stash@{...}` appears outside a quoted string. pwsh reads `@{` as the start of a "
            "hashtable and the call dies at runtime -- after the primary has already been emptied.",
        )

    def test_that_matcher_would_catch_one_too(self):
        self.assertTrue(BAREWORD_STASH_REF.search("& git rev-parse stash@{0}"))
        self.assertFalse(BAREWORD_STASH_REF.search("& git rev-parse 'stash@{0}'"))
        self.assertFalse(BAREWORD_STASH_REF.search('& git rev-parse "stash@{0}"'))


if __name__ == "__main__":
    unittest.main()
