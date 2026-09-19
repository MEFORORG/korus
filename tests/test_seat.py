"""The episode record: the durable answer to "what was this seat doing".

WHAT IT IS FOR. A session's seat and its goal live in the conversation, and the conversation is the
one thing that does not survive. `scripts/coord/seat.ps1` writes them to disk so the next session
reads them instead of guessing. `scripts/hooks/precompact-reprime.ps1` is the first reader, and
`tests/test_precompact_reprime.py` covers that end.

THE ONE PROPERTY WORTH MOST IS THAT THE SCRIPT REFUSES TO INVENT A GOAL. A seat can be derived. A
goal cannot, and a record carrying a machine's guess at one is worse than an absent record: the
absent one prompts somebody to write it, while the invented one reads as a declaration and says
nothing. `TheGoalIsTheOnePartAMachineMayNotSupply` is that, from both directions -- `-Declare`
refuses without a goal, and `-Record`, the hook path, never writes one it was not handed.

THE SECOND IS THAT AN UNRECOGNISED LABEL IS REFUSED RATHER THAN RECORDED. A free-text seat field
produced 46 distinct role strings for a six-seat roster upstream, and at that point the field stops
being an instrument: nothing can be grouped by it. So the roster in `docs/roles/seats.json` is
enforced here, aliases collapse onto the canonical name, and a retired seat is refused WITH the
reason rather than silently.

EVERY CASE RUNS AGAINST A THROWAWAY CLONE WITH TWO REAL WORKTREES. The script's whole job is
resolving one worktree's state root and writing a file into it, so a mock would have to invent the
thing under test. Two worktrees, because a single one cannot show that the records stay separate --
and the shape of that failure is one seat's goal overwriting another's.
"""

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120
SEAT = t.REPO_ROOT / "scripts" / "coord" / "seat.ps1"
ROSTER = json.loads(t.read(t.REPO_ROOT / "docs" / "roles" / "seats.json"))

#: What `Get-CcxMailStamp` writes: a round-trippable UTC stamp, offset included.
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")


class _SeatCase(unittest.TestCase):
    """One clone, two worktrees, and a state root that is shared between them."""

    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so seat.ps1 cannot be executed here")
        self.pwsh: str = pwsh

        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-seat-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

        self.primary = self.root / "primary"
        self.primary.mkdir()
        self.git(self.primary, "init", "-b", "main")
        self.git(self.primary, "config", "user.email", "t@example.com")
        self.git(self.primary, "config", "user.name", "t")
        (self.primary / "a.txt").write_text("a", encoding="ascii")
        self.git(self.primary, "add", "a.txt")
        self.git(self.primary, "commit", "-m", "first")

        self.peer = self.root / "peer"
        self.git(self.primary, "worktree", "add", str(self.peer), "-b", "peer-branch")

    def git(self, cwd, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT_SECONDS
        )

    def seat(self, cwd, *args, session="s1", env_session=None) -> subprocess.CompletedProcess:
        """Run the script. `session` becomes `-SessionId`; pass None to leave it off entirely."""
        argv = [self.pwsh, "-NoProfile", "-File", str(SEAT), *args]
        if session is not None:
            argv += ["-SessionId", session]
        env = dict(os.environ)
        env.pop("CLAUDE_SESSION_ID", None)
        if env_session is not None:
            env["CLAUDE_SESSION_ID"] = env_session
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            env=env,
            timeout=TIMEOUT_SECONDS,
        )

    @property
    def seats_root(self) -> Path:
        return self.primary / ".git" / "ccx-coord" / "seats"

    def records(self) -> list[Path]:
        """Every record on disk. The box directory is a hash, so nothing here reconstructs it."""
        return sorted(self.seats_root.glob("*/*.json")) if self.seats_root.is_dir() else []

    def record(self, worktree: Path, session="s1") -> dict:
        """The record for one (worktree, session), matched on the worktree the script wrote."""
        want = str(worktree.resolve()).replace("\\", "/").lower()
        for path in self.records():
            if path.stem != session:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if str(data.get("worktree", "")).replace("\\", "/").lower() == want:
                return data
        raise AssertionError(
            f"no record for session {session!r} in {worktree}. On disk: "
            f"{[str(p.relative_to(self.seats_root)) for p in self.records()]}"
        )

    def marker(self, worktree: Path) -> Path:
        return worktree / ".claude" / "seat.local.txt"

    def declare(self, cwd, seat_name, goal, *extra, session="s1"):
        return self.seat(cwd, "-Declare", "-Seat", seat_name, "-Goal", goal, *extra, session=session)


class TheGoalIsTheOnePartAMachineMayNotSupply(_SeatCase):
    """The whole design rests here. A seat can be derived; a goal cannot."""

    def test_declaring_without_a_goal_is_refused(self):
        result = self.seat(self.primary, "-Declare", "-Seat", "builder")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("-Goal is required", result.stdout)

    def test_a_refused_declaration_writes_no_record_at_all(self):
        self.seat(self.primary, "-Declare", "-Seat", "builder")
        self.assertEqual(
            [],
            self.records(),
            "a half-written record is the failure the refusal exists to prevent: it looks declared "
            "and carries no goal, which is worse than nothing being there.",
        )

    def test_the_hook_path_writes_no_goal_it_was_not_given(self):
        result = self.seat(self.primary, "-Record")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("", self.record(self.primary)["goal"])
        self.assertEqual("", self.record(self.primary)["seat"])

    def test_the_hook_path_leaves_an_existing_declaration_exactly_as_it_was(self):
        self.declare(
            self.primary,
            "builder",
            "port the role cards",
            "-Done",
            "the suite is green",
            "-OutOfScope",
            "the site",
        )
        before = self.record(self.primary)
        self.assertEqual(0, self.seat(self.primary, "-Record").returncode)
        after = self.record(self.primary)
        for field in ("seat", "goal", "done_when", "out_of_scope", "declared_at"):
            self.assertEqual(before[field], after[field], f"-Record moved {field}")

    def test_the_hook_path_still_refreshes_what_a_machine_does_know(self):
        self.declare(self.primary, "builder", "port the role cards")
        before = self.record(self.primary)
        self.git(self.primary, "checkout", "-q", "-b", "renamed")
        self.assertEqual(0, self.seat(self.primary, "-Record").returncode)
        after = self.record(self.primary)
        self.assertEqual("renamed", after["branch"])
        self.assertNotEqual(before["updated_at"], after["updated_at"])


class AnUnrecognisedLabelIsRefusedRatherThanRecorded(_SeatCase):
    """46 role strings for a six-seat roster is what a free-text field produces."""

    def test_an_unknown_seat_is_refused_and_the_live_ones_are_named(self):
        result = self.declare(self.primary, "wizard", "something")
        self.assertEqual(1, result.returncode)
        self.assertIn("is not a live seat", result.stdout)
        for live in ROSTER["live"]:
            self.assertIn(live, result.stdout)
        self.assertEqual([], self.records())

    def test_every_live_seat_in_the_roster_is_accepted(self):
        for live in ROSTER["live"]:
            with self.subTest(seat=live):
                result = self.declare(self.primary, live, "a goal", session=f"s-{live}")
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(live, self.record(self.primary, f"s-{live}")["seat"])

    def test_an_alias_is_stored_under_the_canonical_seat(self):
        alias, canonical = next(iter(ROSTER["aliases"].items()))
        result = self.declare(self.primary, alias, "a goal")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            canonical,
            self.record(self.primary)["seat"],
            "an alias that survives into the record splits one seat into several labels, which is "
            "the thing the roster exists to stop.",
        )

    def test_a_retired_seat_is_refused_with_the_reason_it_was_retired(self):
        retired, reason = next(iter(ROSTER["retired"].items()))
        result = self.declare(self.primary, retired, "a goal")
        self.assertEqual(1, result.returncode)
        self.assertIn("RETIRED", result.stdout)
        self.assertIn(
            reason.split(".")[0],
            result.stdout,
            "silence would send the reader looking for a seat that was deliberately removed.",
        )

    def test_the_seat_is_matched_without_regard_to_case_or_padding(self):
        result = self.declare(self.primary, "  BUILDER  ", "a goal")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("builder", self.record(self.primary)["seat"])


class OneRecordPerWorktreeAndSession(_SeatCase):
    """A single record per worktree is one seat's goal overwriting another's."""

    def test_two_worktrees_keep_separate_records_under_one_session_id(self):
        self.declare(self.primary, "builder", "port the role cards")
        self.declare(self.peer, "steward", "attribute the red")
        self.assertEqual("builder", self.record(self.primary)["seat"])
        self.assertEqual("steward", self.record(self.peer)["seat"])
        self.assertEqual(2, len(self.records()))

    def test_two_sessions_in_one_worktree_keep_separate_records(self):
        self.declare(self.primary, "builder", "the first goal", session="s1")
        self.declare(self.primary, "steward", "the second goal", session="s2")
        self.assertEqual("the first goal", self.record(self.primary, "s1")["goal"])
        self.assertEqual("the second goal", self.record(self.primary, "s2")["goal"])

    def test_redeclaring_keeps_the_first_declared_at_and_moves_updated_at(self):
        self.declare(self.primary, "builder", "the first goal")
        before = self.record(self.primary)
        self.declare(self.primary, "builder", "the goal after a rethink")
        after = self.record(self.primary)
        self.assertEqual(before["declared_at"], after["declared_at"])
        self.assertNotEqual(before["updated_at"], after["updated_at"])
        self.assertEqual("the goal after a rethink", after["goal"])

    def test_the_session_id_is_read_from_the_environment_when_it_is_not_passed(self):
        result = self.declare(self.primary, "builder", "a goal", session=None)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.seat(self.primary, "-List", session=None)
        self.assertEqual(["unnamed-session"], [p.stem for p in self.records()])

        result = self.seat(
            self.primary, "-Declare", "-Seat", "builder", "-Goal", "a goal",
            session=None, env_session="from-the-harness",
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("from-the-harness", [p.stem for p in self.records()])

    def test_a_hostile_session_id_cannot_escape_its_box(self):
        result = self.declare(self.primary, "builder", "a goal", session="../../escaped")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        written = self.records()
        self.assertEqual(1, len(written))
        self.assertEqual(
            self.seats_root.resolve(),
            written[0].parent.parent.resolve(),
            "a session id is supplied by whatever launched the session, so it is untrusted input "
            "that names a file.",
        )


class TheMarkerIsCollapsedIntoTheDeclaration(_SeatCase):
    """`docs/ROLE-CARDS.md` files this as the cheaper end state than a fourth resolution rung."""

    def test_declaring_writes_the_role_card_marker(self):
        self.declare(self.primary, "builder", "a goal")
        self.assertEqual("builder", self.marker(self.primary).read_text(encoding="ascii").strip())

    def test_the_marker_carries_the_canonical_seat_not_the_alias_that_was_typed(self):
        alias, canonical = next(iter(ROSTER["aliases"].items()))
        self.declare(self.primary, alias, "a goal")
        self.assertEqual(canonical, self.marker(self.primary).read_text(encoding="ascii").strip())

    def test_a_refused_declaration_writes_no_marker(self):
        self.declare(self.primary, "wizard", "a goal")
        self.assertFalse(
            self.marker(self.primary).exists(),
            "a card injected at the weight of the working agreement outranks the document the "
            "session should be reading, so a refused seat must leave nothing behind.",
        )

    def test_the_hook_path_restores_a_marker_that_was_lost(self):
        self.declare(self.primary, "builder", "a goal")
        self.marker(self.primary).unlink()
        self.assertEqual(0, self.seat(self.primary, "-Record").returncode)
        self.assertEqual("builder", self.marker(self.primary).read_text(encoding="ascii").strip())

    def test_the_hook_path_mints_no_marker_when_no_seat_was_declared(self):
        self.assertEqual(0, self.seat(self.primary, "-Record").returncode)
        self.assertFalse(self.marker(self.primary).exists())

    def test_the_marker_belongs_to_its_own_worktree(self):
        self.declare(self.primary, "builder", "a goal")
        self.declare(self.peer, "steward", "another goal")
        self.assertEqual("builder", self.marker(self.primary).read_text(encoding="ascii").strip())
        self.assertEqual("steward", self.marker(self.peer).read_text(encoding="ascii").strip())


class ClosingSaysTheEpisodeEndedNotThatItNeverHappened(_SeatCase):
    def test_closing_stamps_the_record_and_keeps_the_goal(self):
        self.declare(self.primary, "builder", "port the role cards")
        result = self.seat(self.primary, "-Close")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        closed = self.record(self.primary)
        self.assertNotEqual("", closed["closed_at"])
        self.assertEqual("port the role cards", closed["goal"])
        self.assertEqual("builder", closed["seat"])

    def test_closing_an_absent_record_refuses_rather_than_minting_an_empty_one(self):
        result = self.seat(self.primary, "-Close")
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing to close", result.stdout)
        self.assertEqual([], self.records())


class TheStateLivesInsideGitAndCannotBeCommitted(_SeatCase):
    def test_the_record_is_written_under_the_git_common_directory(self):
        self.declare(self.primary, "builder", "a goal")
        self.assertEqual(
            self.primary / ".git" / "ccx-coord" / "seats",
            self.records()[0].parent.parent,
        )

    def test_a_declaration_leaves_nothing_stageable_but_the_marker(self):
        self.declare(self.primary, "builder", "a goal")
        porcelain = self.git(self.primary, "status", "--porcelain").stdout.split("\n")
        touched = sorted(line[3:] for line in porcelain if line.strip())
        self.assertEqual(
            [".claude/"],
            touched,
            "a per-session record in a tracked file conflicts every time two sessions run, and the "
            "conflict lands in the one file nobody wants to resolve.",
        )

    def test_the_declaration_from_a_peer_worktree_shares_one_state_root(self):
        self.declare(self.peer, "steward", "a goal")
        self.assertTrue(self.records(), "the peer wrote outside the shared state root")

    def test_no_temporary_file_survives_a_write(self):
        self.declare(self.primary, "builder", "a goal")
        self.seat(self.primary, "-Record")
        self.assertEqual(
            [],
            sorted(self.seats_root.rglob("*.tmp")),
            "the write is write-then-replace because a torn record parses as 'no declaration', "
            "which discards a goal nothing else holds a copy of.",
        )


class TheListingHidesNothing(_SeatCase):
    """State outlives the worktree, so the listing has to report what is gone."""

    def test_an_empty_state_root_says_so(self):
        result = self.seat(self.primary, "-List")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("no records yet", result.stdout)

    def test_a_record_whose_worktree_is_gone_is_flagged_rather_than_dropped(self):
        self.declare(self.peer, "steward", "attribute the red")
        self.git(self.primary, "worktree", "remove", "--force", str(self.peer))
        result = self.seat(self.primary, "-List")
        self.assertIn("WORKTREE GONE", result.stdout)
        self.assertIn(
            "steward",
            result.stdout,
            "the record is the only remaining evidence of what that seat was doing.",
        )

    def test_an_undeclared_record_reads_as_undeclared_rather_than_as_blank(self):
        self.seat(self.primary, "-Record")
        result = self.seat(self.primary, "-List")
        self.assertIn("(undeclared)", result.stdout)
        self.assertIn("(no goal declared)", result.stdout)

    def test_an_unreadable_record_is_named_rather_than_skipped(self):
        self.declare(self.primary, "builder", "a goal")
        self.records()[0].write_text("{ not json", encoding="utf-8")
        result = self.seat(self.primary, "-List")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("UNREADABLE", result.stdout)


class EveryStampStaysRoundTrippable(_SeatCase):
    """Found by this file, in the script it was written for.

    `ConvertFrom-Json` parses an ISO-8601 field into a [datetime], so every stamp this script
    carries FORWARD is re-rendered on the way out. `[string]` on a [datetime] uses the current
    culture, and `-Record` turned `2026-09-05T16:14:07.5348854+00:00` into `09/05/2026 11:14:07`:
    ambiguous between day and month, carrying no offset, parseable by nothing. `-Declare` had the
    milder half, rewriting a UTC stamp in the writer's local offset.

    The equality assertions in the classes above catch a stamp that MOVES. Only the shape assertion
    here catches one that stays put and stops being a stamp.
    """

    def test_a_fresh_declaration_is_stamped_in_utc(self):
        self.declare(self.primary, "builder", "a goal")
        record = self.record(self.primary)
        for field in ("declared_at", "updated_at"):
            self.assertRegex(record[field], ISO_UTC, f"{field} is not a round-trippable UTC stamp")

    def test_the_hook_path_carries_the_stamp_forward_unchanged(self):
        self.declare(self.primary, "builder", "a goal")
        before = self.record(self.primary)["declared_at"]
        self.seat(self.primary, "-Record")
        after = self.record(self.primary)["declared_at"]
        self.assertRegex(after, ISO_UTC)
        self.assertEqual(before, after)

    def test_closing_carries_the_stamp_forward_unchanged(self):
        self.declare(self.primary, "builder", "a goal")
        before = self.record(self.primary)["declared_at"]
        self.seat(self.primary, "-Close")
        closed = self.record(self.primary)
        self.assertEqual(before, closed["declared_at"])
        self.assertRegex(closed["closed_at"], ISO_UTC)

    def test_the_stamp_survives_being_carried_twice(self):
        self.declare(self.primary, "builder", "a goal")
        before = self.record(self.primary)["declared_at"]
        self.seat(self.primary, "-Record")
        self.declare(self.primary, "builder", "a second goal")
        self.seat(self.primary, "-Record")
        self.assertEqual(
            before,
            self.record(self.primary)["declared_at"],
            "a stamp that drifts a little on every rewrite is the version of this defect that "
            "survives a single-pass test.",
        )


class ItNeverPretendsToHaveAStateRoot(_SeatCase):
    def test_outside_a_clone_it_says_so_instead_of_writing_somewhere(self):
        outside = self.root / "not-a-clone"
        outside.mkdir()
        result = self.seat(outside, "-List")
        self.assertEqual(1, result.returncode)
        self.assertIn("not inside a git clone", result.stdout)


if __name__ == "__main__":
    unittest.main()
