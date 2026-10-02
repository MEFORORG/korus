"""The precompact hook restores held ledger state, and says so when it cannot read it.

WHAT THIS EXISTS FOR. A compaction summarises the conversation, and everything a session knows
about its own held state lives there: which numbers it allocated, which keys it claimed, whether
the branch is pushed. Afterwards it has no idea it holds an unfiled allocation, and an unfiled
number BURNS -- allocation is a one-way door and numbers are never reclaimed.

THE TEST THAT CARRIES THE MOST WEIGHT IS `SilenceIsLegible`. "I hold nothing" and "I could not read
the ledger" have OPPOSITE fixes, and both render as an empty report unless the hook distinguishes
them. This repository has been bitten by that shape twice in a different form: a scan returning zero
because the tree was clean, and a scan returning zero because the detector was off, look identical.

THE SECOND IS `AStaleRecordIsNotRestoredAsCurrentIntent`. A worktree outlives its sessions. A claim
recorded on a different branch is more likely a previous occupant's, and restoring it as this
session's intent is a confidently-wrong coordination fact -- worse than saying nothing, because it
reads as recovered memory.

Every case runs against a THROWAWAY git repository with a real state root, not a mocked one. The
hook's whole job is reading files that a mock would have to invent.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120
HOOK = t.REPO_ROOT / "scripts" / "hooks" / "precompact-reprime.ps1"


def _context(result: subprocess.CompletedProcess) -> str | None:
    out = (result.stdout or "").strip()
    if not out:
        return None
    try:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError):
        return None


class _RepoCase(unittest.TestCase):
    """A throwaway repo with a real `.git/ccx-coord` state root."""

    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so the hook cannot be executed here")
        self.pwsh: str = pwsh

        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-precompact-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()

        self.git("init", "-b", "work")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        (self.repo / "a.txt").write_text("a", encoding="ascii")
        self.git("add", "a.txt")
        self.git("commit", "-m", "first")

        self.state = self.repo / ".git" / "ccx-coord"
        self.state.mkdir(parents=True, exist_ok=True)

        # The worktree path a ledger row actually carries, as scripts/coord/alloc.ps1 and claim.ps1
        # record it: `git rev-parse --path-format=absolute --show-toplevel`. The hook reads the same
        # command, so in production the two sides cannot disagree.
        #
        # Do NOT default these rows to `str(self.repo)`. On a GitHub Windows runner %TEMP% is the 8.3
        # SHORT form, so Python hands back the 8.3 alias of the account directory while git reports
        # its long spelling. That mismatch is a property of the FIXTURE, not of the hook, and
        # it reddened seven tests here while every one passed on a machine whose account name is short
        # enough to need no 8.3 alias.
        self.repo_path = self.git(
            "rev-parse", "--path-format=absolute", "--show-toplevel"
        ).stdout.strip()

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, timeout=TIMEOUT_SECONDS
        )

    def branch(self) -> str:
        return self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def write_alloc(self, kind: str, number: str, worktree=None):
        d = self.state / "alloc" / kind
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{number}.json").write_text(
            json.dumps({"number": number, "kind": kind, "worktree": str(worktree or self.repo_path)}),
            encoding="ascii",
        )

    def write_claim(self, key: str, note: str, branch=None, worktree=None):
        d = self.state / "claims"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{key}.json").write_text(
            json.dumps(
                {
                    "key": key,
                    "note": note,
                    "branch": branch if branch is not None else self.branch(),
                    "worktree": str(worktree or self.repo_path),
                }
            ),
            encoding="ascii",
        )

    def run_hook(self, payload: str = "{}") -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            cwd=str(self.repo),
            timeout=TIMEOUT_SECONDS,
        )

    def ctx(self) -> str:
        r = self.run_hook()
        self.assertEqual(0, r.returncode, f"the hook must always exit 0. stderr: {r.stderr}")
        out = _context(r)
        if out is None:
            raise AssertionError("the hook said nothing, but this test needs it to report")
        return out


class ItReportsWhatThisWorktreeHolds(_RepoCase):
    def test_an_allocation_is_reported(self):
        self.write_alloc("adr", "0007")
        self.assertIn("adr #0007", self.ctx())

    def test_an_allocation_warns_that_an_unfiled_number_burns(self):
        """The permanent cost is the reason this half was the one worth porting."""
        self.write_alloc("adr", "0007")
        self.assertIn("BURNS", self.ctx())

    def test_a_claim_is_reported_with_its_note(self):
        self.write_claim("worker-brief", "specifying the brief")
        ctx = self.ctx()
        self.assertIn("worker-brief", ctx)
        self.assertIn("specifying the brief", ctx)

    def test_another_worktrees_records_are_not_reported(self):
        """The control for every test above: matching on nothing would report these too."""
        self.write_alloc("adr", "0009", worktree=Path(self.tmp.name) / "somewhere-else")
        self.write_claim("not-mine", "another tree's work", worktree=Path(self.tmp.name) / "elsewhere")
        ctx = self.ctx()
        self.assertNotIn("0009", ctx)
        self.assertNotIn("not-mine", ctx)

    def test_a_path_spelled_differently_still_matches(self):
        """A raw string compare reports two spellings of one worktree as two worktrees."""
        self.write_alloc("adr", "0011", worktree=str(self.repo_path).replace("\\", "/").upper())
        self.assertIn("0011", self.ctx())


class AStaleRecordIsNotRestoredAsCurrentIntent(_RepoCase):
    def test_a_claim_from_another_branch_is_flagged_not_restored(self):
        self.write_claim("old-work", "a previous occupant's job", branch="some-other-branch")
        ctx = self.ctx()
        self.assertIn("MAY NOT BE YOURS", ctx)
        self.assertIn("some-other-branch", ctx)

    def test_a_claim_on_the_current_branch_is_restored_normally(self):
        """The control. Without it the test above passes for a hook that flags everything."""
        self.write_claim("current-work", "this session's job")
        ctx = self.ctx()
        self.assertIn("HELD CLAIMS", ctx)
        self.assertNotIn("MAY NOT BE YOURS", ctx)


class ItReportsWhetherTheWorkIsPushed(_RepoCase):
    def test_a_branch_with_no_upstream_says_nothing_is_recoverable(self):
        ctx = self.ctx()
        self.assertIn("NO UPSTREAM", ctx)

    def test_unpushed_commits_are_counted(self):
        remote = Path(self.tmp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, timeout=TIMEOUT_SECONDS)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "-u", "origin", "work")
        (self.repo / "b.txt").write_text("b", encoding="ascii")
        self.git("add", "b.txt")
        self.git("commit", "-m", "second")
        ctx = self.ctx()
        self.assertIn("UNPUSHED", ctx)
        self.assertIn("1 commit", ctx)

    def test_a_pushed_branch_is_not_reported_as_unpushed(self):
        """The control for the test above."""
        remote = Path(self.tmp.name) / "remote2.git"
        subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, timeout=TIMEOUT_SECONDS)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "-u", "origin", "work")
        ctx = self.ctx()
        self.assertNotIn("UNPUSHED", ctx)
        self.assertNotIn("NO UPSTREAM", ctx)


class SilenceIsLegible(_RepoCase):
    """Holding nothing and failing to look have opposite fixes and must not both render blank."""

    def test_holding_nothing_says_so_explicitly(self):
        remote = Path(self.tmp.name) / "remote3.git"
        subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, timeout=TIMEOUT_SECONDS)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "-u", "origin", "work")
        ctx = self.ctx()
        self.assertIn("no allocations and no claims", ctx)

    def test_holding_nothing_says_it_is_a_reading(self):
        """The distinction the whole class exists for, stated in the output a reader sees."""
        remote = Path(self.tmp.name) / "remote4.git"
        subprocess.run(["git", "init", "--bare", str(remote)], capture_output=True, timeout=TIMEOUT_SECONDS)
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "-u", "origin", "work")
        self.assertIn("not a failure to look", self.ctx())

    def test_a_corrupt_record_does_not_become_a_clean_slate(self):
        """A claim file that will not parse must not silently reduce the report to 'nothing held'."""
        self.write_alloc("adr", "0013")
        d = self.state / "claims"
        d.mkdir(parents=True, exist_ok=True)
        (d / "broken.json").write_text("{ this is not json", encoding="ascii")
        ctx = self.ctx()
        self.assertIn("0013", ctx, "one unreadable claim discarded the whole report")


class TheHookNeverFailsATurn(_RepoCase):
    def test_it_exits_zero_outside_a_git_repository(self):
        outside = Path(self.tmp.name) / "not-a-repo"
        outside.mkdir()
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(HOOK)],
            input="{}",
            capture_output=True,
            text=True,
            cwd=str(outside),
            timeout=TIMEOUT_SECONDS,
        )
        self.assertEqual(0, r.returncode, r.stderr)

    def test_it_exits_zero_with_junk_on_stdin(self):
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(HOOK)],
            input="not json {{{",
            capture_output=True,
            text=True,
            cwd=str(self.repo),
            timeout=TIMEOUT_SECONDS,
        )
        self.assertEqual(0, r.returncode, r.stderr)

    def test_it_exits_zero_with_no_state_root(self):
        for child in self.state.iterdir():
            child.unlink() if child.is_file() else None
        self.state.rmdir()
        r = self.run_hook()
        self.assertEqual(0, r.returncode, r.stderr)

    def test_it_never_returns_a_permission_decision(self):
        """A hook that could deny would block the session it exists to help."""
        self.write_alloc("adr", "0015")
        self.assertNotIn("permissionDecision", self.run_hook().stdout)


class ItSpeaksOnlyAfterACompaction(_RepoCase):
    """The source guard in the script is the only guard, so it is pinned here.

    The settings row and the `korus-card` plugin both run this script match-all on SessionStart.
    Neither adds a matcher, so a guard that went quiet on `compact`, or spoke on `startup`, would
    reach every session with nothing else to catch it.
    """

    def payload(self, **fields: str) -> str:
        return json.dumps(fields)

    def test_a_compact_restart_speaks(self):
        """The control for every silent case below: the same repo, the one source that speaks."""
        self.write_alloc("adr", "0021")
        r = self.run_hook(self.payload(hook_event_name="SessionStart", source="compact"))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("adr #0021", _context(r) or "")

    def test_the_payload_names_session_start(self):
        """The harness refuses PreCompact as a hookEventName, so the old payload never landed."""
        r = self.run_hook(self.payload(hook_event_name="SessionStart", source="compact"))
        self.assertEqual("SessionStart", json.loads(r.stdout)["hookSpecificOutput"]["hookEventName"])

    def test_every_other_start_is_silent(self):
        self.write_alloc("adr", "0021")
        for source in ("startup", "resume", "clear", "fork", "a-source-added-later"):
            with self.subTest(source=source):
                r = self.run_hook(self.payload(hook_event_name="SessionStart", source=source))
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertEqual("", r.stdout.strip())

    def test_a_leftover_precompact_row_is_silent(self):
        self.write_alloc("adr", "0021")
        r = self.run_hook(self.payload(hook_event_name="PreCompact", trigger="auto"))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())

    def test_an_unreadable_payload_speaks(self):
        """Fail open: only a payload that POSITIVELY says 'not a compaction' silences it."""
        self.write_alloc("adr", "0021")
        for payload in ("", "not json {{{"):
            with self.subTest(payload=payload):
                self.assertIn("adr #0021", _context(self.run_hook(payload)) or "")


class ItRestoresTheDeclarationHalfToo(_RepoCase):
    """The half that could not be built until scripts/coord/seat.ps1 existed.

    Before that there was no declaration on disk to read, and a hook that closed the gap by
    INFERRING a goal would have written the exact record this design refuses: one that looks
    declared and says nothing. So the half shipped second, on purpose, and these tests are what
    make it answerable now that it exists.
    """

    def declare(self, seat="builder", goal="port the role cards", branch=None, worktree=None):
        d = self.state / "seats" / "box"
        d.mkdir(parents=True, exist_ok=True)
        rec = {
            "seat": seat,
            "goal": goal,
            "done_when": "the suite is green",
            "out_of_scope": "branch protection",
            "worktree": str(worktree or self.repo_path),
            "branch": branch if branch is not None else self.branch(),
            "declared_at": "2026-09-05T00:00:00.0000000+00:00",
        }
        (d / f"{seat}-session.json").write_text(json.dumps(rec), encoding="ascii")

    def test_the_seat_and_goal_come_back(self):
        self.declare()
        ctx = self.ctx()
        self.assertIn("SEAT: builder", ctx)
        self.assertIn("port the role cards", ctx)

    def test_what_the_session_said_it_would_not_do_comes_back(self):
        """Scope is the half a compaction loses most expensively: the next turn re-opens it."""
        self.declare()
        self.assertIn("OUT OF SCOPE", self.ctx())

    def test_a_declaration_from_another_branch_is_flagged_not_restored(self):
        self.declare(branch="some-earlier-branch")
        ctx = self.ctx()
        self.assertIn("PROBABLY NOT YOURS", ctx)
        self.assertNotIn("SEAT: builder", ctx)

    def test_another_worktrees_declaration_is_not_restored(self):
        """The control: matching on nothing would adopt any record in the state root."""
        self.declare(worktree=Path(self.tmp.name) / "somewhere-else", goal="not this tree's job")
        self.assertNotIn("not this tree's job", self.ctx())

    def test_no_declaration_says_so_rather_than_going_quiet(self):
        """Undeclared and unreadable have opposite fixes and must not both render blank."""
        (self.state / "seats").mkdir(parents=True, exist_ok=True)
        ctx = self.ctx()
        self.assertIn("NO SEAT DECLARED", ctx)
        self.assertIn("not a failure to look", ctx)

    def test_it_never_invents_a_goal(self):
        """Pinned at the source. A goal no human wrote is the failure this whole design avoids."""
        source = t.strip_ps_comments(t.read(HOOK))
        self.assertNotIn("default_goal", source)
        self.assertIn("$declared.goal", source)


if __name__ == "__main__":
    unittest.main()
