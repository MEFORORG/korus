"""`scripts/coord/fleet.ps1`: the roster a stranded session reads, and the JSON a fleet board draws.

WHAT IT IS FOR. After an account switch the session reading the roster is the one that lost the
context. An empty roster and a dead writer print the same thing to that reader, so the script
states what it EXAMINED, and fires a stop condition rather than rendering a confident empty answer.

THE DENOMINATOR IS THE LOAD-BEARING PART, so it is tested from both sides. A live session in the
repository that wrote no seat record must raise `liveSessionsWithoutRecord`; the same session with a
record must not. Either arm alone passes a script hard-wired to one answer.

THE JSON SHAPE IS A CONTRACT. A board reads `receipt.renderedAtUtc`, `receipt.liveSessionsInRepo`,
`receipt.stopConditions` and, per row, `Seat`, `Box`, `Branch`, `State` and `AgeHours`.
`docs/SCRIPTS.md` states it; `TheJsonContractHolds` pins it.

EVERY CASE RUNS AGAINST A THROWAWAY CLONE WITH TWO REAL WORKTREES, and the seat records are written
by the real `seat.ps1`. The reader's job is to read what that writer writes, so a hand-planted record
would test the reader against this file's idea of the format rather than the writer's. The session
registry IS planted, under a private config root, because the real one belongs to the client. Its
one live entry is a real child process, so the fence's start-time check runs for real.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120
FLEET = t.REPO_ROOT / "scripts" / "coord" / "fleet.ps1"
SEAT = t.REPO_ROOT / "scripts" / "coord" / "seat.ps1"


class _FleetCase(unittest.TestCase):
    """One clone, two worktrees, a private session registry, and no records until a case writes one."""

    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so fleet.ps1 cannot be executed here")
        self.pwsh: str = pwsh

        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-fleet-")
        self.addCleanup(self.tmp.cleanup)
        # Resolved, so a Windows runner's 8.3 temp path (RUNNER~1) is expanded before git sees it:
        # `git worktree list` keeps the spelling it was given, and the matcher compares strings.
        self.root = Path(os.path.realpath(self.tmp.name))

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

        self.config_root = self.root / "cfg"
        (self.config_root / "sessions").mkdir(parents=True)
        # One registry entry that places nowhere in this clone, so the fence has something to examine.
        # A registry with no readable record is an unavailable fence, which `NoRegistryIsNoFence` pins.
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (self.config_root / "sessions" / "1.json").write_text(
            json.dumps({"pid": 1, "startedAt": int(time.time() * 1000), "sessionId": "ffff", "cwd": str(elsewhere)}),
            encoding="utf-8",
        )

    def git(self, cwd, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT_SECONDS
        )

    def toplevel(self, worktree: Path) -> str:
        """The worktree path as git spells it, which is what a session's cwd is matched against.

        Not `str(worktree)`: a Windows runner's temp directory can be an 8.3 short path, and the
        matcher compares strings, so a planted cwd in the other spelling would never place.
        """
        return self.git(worktree, "rev-parse", "--path-format=absolute", "--show-toplevel").stdout.strip()

    def plant_live_session(self, worktree: Path, session_id: str) -> None:
        """A registry entry backed by a real process, so the fence answers LIVE on its own terms."""
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        record = {
            "pid": proc.pid,
            "startedAt": int(time.time() * 1000),
            "sessionId": session_id,
            "cwd": self.toplevel(worktree),
        }
        (self.config_root / "sessions" / f"{proc.pid}.json").write_text(json.dumps(record), encoding="utf-8")

    def declare(self, worktree: Path, seat_name: str, goal: str, *extra) -> None:
        env = dict(os.environ)
        env.pop("CLAUDE_SESSION_ID", None)
        result = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(SEAT), "-Declare", "-Seat", seat_name, "-Goal", goal, *extra],
            capture_output=True,
            text=True,
            cwd=str(worktree),
            env=env,
            timeout=TIMEOUT_SECONDS,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def close(self, worktree: Path) -> None:
        env = dict(os.environ)
        env.pop("CLAUDE_SESSION_ID", None)
        subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(SEAT), "-Close"],
            cwd=str(worktree),
            env=env,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=True,
        )

    def fleet(self, *args, config_root: Path | None = None) -> subprocess.CompletedProcess:
        cfg = self.config_root if config_root is None else config_root
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(FLEET), *args, "-ConfigRoot", str(cfg)],
            capture_output=True,
            text=True,
            cwd=str(self.primary),
            timeout=TIMEOUT_SECONDS,
        )

    def fleet_json(self, config_root: Path | None = None) -> tuple[int, dict]:
        result = self.fleet("-Json", config_root=config_root)
        try:
            return result.returncode, json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"-Json did not print JSON. stdout={result.stdout!r} stderr={result.stderr!r}")

    @property
    def seats_root(self) -> Path:
        return self.primary / ".git" / "ccx-coord" / "seats"

    def record_files(self) -> list[Path]:
        return sorted(self.seats_root.glob("*/*.json")) if self.seats_root.is_dir() else []

    def row_for(self, data: dict, branch: str) -> dict:
        rows = [r for r in data["rows"] if r["Branch"] == branch]
        self.assertEqual(1, len(rows), f"expected one row on {branch}, got {data['rows']}")
        return rows[0]


class TheJsonContractHolds(_FleetCase):
    """The fields a fleet board reads, with the types it reads them as."""

    def test_the_receipt_and_rows_carry_the_contract_fields(self):
        self.declare(self.peer, "builder", "build the thing")
        code, data = self.fleet_json()
        self.assertEqual(0, code)
        receipt = data["receipt"]
        self.assertRegex(receipt["renderedAtUtc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertIsInstance(receipt["liveSessionsInRepo"], int)
        self.assertIsInstance(receipt["stopConditions"], list)
        self.assertEqual(1, receipt["recordsExamined"])
        row = self.row_for(data, "peer-branch")
        self.assertEqual("builder", row["Seat"])
        self.assertTrue(row["Box"].startswith("peer-"), row["Box"])
        self.assertIn("State", row)
        self.assertIsInstance(row["AgeHours"], (int, float))
        self.assertGreaterEqual(row["AgeHours"], 0)
        self.assertLess(row["AgeHours"], 1)

    def test_rows_is_a_list_even_with_one_record(self):
        """ConvertTo-Json unwraps a one-element array unless it is told not to."""
        self.declare(self.peer, "builder", "one record")
        _, data = self.fleet_json()
        self.assertIsInstance(data["rows"], list)

    def test_a_single_stop_is_still_a_list(self):
        """ConvertTo-Json can unwrap a one-element array into a bare string, and a board reading
        `stopConditions.length` would then count characters. The fixture clone has never fetched, so
        exactly one stop fires here: the fetch clock's."""
        self.declare(self.peer, "builder", "x")
        _, data = self.fleet_json()
        stops = data["receipt"]["stopConditions"]
        self.assertIsInstance(stops, list)
        self.assertEqual(1, len(stops), stops)
        self.assertTrue(stops[0].startswith("originMainFetchAgeMinutes=UNMEASURABLE"), stops)


class ADeadWriterIsACountNotASilence(_FleetCase):
    """The denominator, from both sides."""

    def test_a_live_session_with_no_record_fires_the_stop(self):
        self.plant_live_session(self.peer, "aaaaaaaa-1111")
        self.declare(self.primary, "manager", "a record elsewhere")
        _, data = self.fleet_json()
        receipt = data["receipt"]
        self.assertEqual(1, receipt["liveSessionsInRepo"])
        self.assertEqual(1, receipt["liveSessionsWithoutRecord"])
        self.assertTrue(
            any(s.startswith("liveSessionsWithoutRecord=1") for s in receipt["stopConditions"]),
            receipt["stopConditions"],
        )

    def test_the_same_session_with_a_record_does_not(self):
        self.plant_live_session(self.peer, "aaaaaaaa-1111")
        self.declare(self.peer, "builder", "declared this time")
        _, data = self.fleet_json()
        receipt = data["receipt"]
        self.assertEqual(1, receipt["liveSessionsInRepo"], "control: the fence must still see the session")
        self.assertEqual(0, receipt["liveSessionsWithoutRecord"])
        row = self.row_for(data, "peer-branch")
        self.assertEqual("RUNNING", row["State"])
        self.assertEqual("worktree", row["FenceBasis"])

    def test_a_closed_record_does_not_cover_a_new_undeclared_session(self):
        """One session declares and closes; the next one in the same checkout never declares."""
        self.declare(self.peer, "builder", "earlier episode")
        self.close(self.peer)
        self.plant_live_session(self.peer, "bbbbbbbb-2222")
        _, data = self.fleet_json()
        self.assertEqual(1, data["receipt"]["liveSessionsWithoutRecord"])

    def test_an_open_record_older_than_the_session_does_not_cover_it(self):
        """The usual korus path: no session id, so the record is keyed on the worktree. A record last
        written before the live session started was written by somebody else."""
        self.declare(self.peer, "builder", "an earlier episode, never closed")
        (path,) = self.record_files()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["updated_at"] = data["declared_at"] = "2026-01-01T00:00:00.0000000+00:00"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.plant_live_session(self.peer, "dddddddd-4444")
        _, out = self.fleet_json()
        self.assertEqual(1, out["receipt"]["liveSessionsWithoutRecord"])
        self.assertEqual("POSSIBLY RUNNING", self.row_for(out, "peer-branch")["State"])

    def test_an_unreadable_record_fires_a_stop(self):
        self.declare(self.peer, "builder", "x")
        (self.seats_root / "torn-0000").mkdir()
        (self.seats_root / "torn-0000" / "s.json").write_text("{ half", encoding="ascii")
        _, data = self.fleet_json()
        self.assertEqual(1, data["receipt"]["recordsUnreadable"])
        self.assertTrue(
            any(s.startswith("recordsUnreadable=1") for s in data["receipt"]["stopConditions"]),
            data["receipt"]["stopConditions"],
        )

    def test_no_records_at_all_fires_its_own_stop(self):
        code, data = self.fleet_json()
        self.assertEqual(0, code)
        self.assertEqual([], data["rows"])
        self.assertTrue(
            any(s.startswith("recordsExamined=0") for s in data["receipt"]["stopConditions"]),
            data["receipt"]["stopConditions"],
        )


class NoRegistryIsNoFence(_FleetCase):
    def test_no_config_root_is_an_unavailable_fence_and_exit_2(self):
        self.declare(self.peer, "builder", "x")
        code, data = self.fleet_json(config_root=self.root / "no-such-config-root")
        self.assertEqual(2, code)
        self.assertFalse(data["receipt"]["fenceAvailable"])
        self.assertEqual("UNKNOWN-NO-FENCE", self.row_for(data, "peer-branch")["State"])

    def test_a_config_root_with_no_session_records_is_no_fence_either(self):
        """A root exists but holds nothing to examine. Reading that as an available fence would turn
        every open row INTERRUPTED, which is the state a respawner acts on."""
        self.declare(self.peer, "builder", "x")
        empty = self.root / "empty-cfg"
        (empty / "sessions").mkdir(parents=True)
        code, data = self.fleet_json(config_root=empty)
        self.assertEqual(2, code)
        self.assertFalse(data["receipt"]["fenceAvailable"])
        self.assertEqual("UNKNOWN-NO-FENCE", self.row_for(data, "peer-branch")["State"])


class EveryStateIsDerivedAtReadTime(_FleetCase):
    def test_a_record_with_no_live_session_reads_interrupted(self):
        self.declare(self.peer, "builder", "left behind")
        _, data = self.fleet_json()
        self.assertEqual("INTERRUPTED", self.row_for(data, "peer-branch")["State"])

    def test_a_closed_record_reads_closed(self):
        self.declare(self.peer, "builder", "finished")
        self.close(self.peer)
        _, data = self.fleet_json()
        self.assertEqual("CLOSED", self.row_for(data, "peer-branch")["State"])

    def test_a_session_keyed_record_the_fence_misses_is_possibly_running_not_interrupted(self):
        """A resumed session can carry a new id. Another live session in the same checkout is not
        proof the recorded one stopped."""
        self.declare(self.peer, "builder", "x", "-SessionId", "old-id")
        self.plant_live_session(self.peer, "new-id-2222")
        _, data = self.fleet_json()
        row = self.row_for(data, "peer-branch")
        self.assertEqual("POSSIBLY RUNNING", row["State"])
        self.assertEqual("worktree", row["FenceBasis"])

    def test_a_session_keyed_record_the_fence_finds_is_running_by_session(self):
        """Control for the case above: the same record, joined on its own id."""
        self.declare(self.peer, "builder", "x", "-SessionId", "abcd")
        self.plant_live_session(self.peer, "abcd-1234")
        _, data = self.fleet_json()
        row = self.row_for(data, "peer-branch")
        self.assertEqual("RUNNING", row["State"])
        self.assertEqual("session", row["FenceBasis"])

    def test_a_dangling_handoff_pointer_fires_a_stop_and_a_present_one_does_not(self):
        (self.peer / "HANDOFF.md").write_text("notes", encoding="ascii")
        self.declare(self.peer, "builder", "x", "-Handoff", "HANDOFF.md")
        self.declare(self.primary, "manager", "y", "-Handoff", "MISSING.md")
        _, data = self.fleet_json()
        self.assertEqual("resolves", self.row_for(data, "peer-branch")["HandoffState"])
        self.assertEqual("dangling", self.row_for(data, "main")["HandoffState"])
        self.assertEqual(1, data["receipt"]["handoffPointersDangling"])


class ItWritesNothing(_FleetCase):
    """A pure reader. The snapshot covers files AND directories under the clone, both worktrees and
    the config root: an empty directory created on demand is the write a dot-sourced helper makes."""

    def snapshot(self) -> dict[str, tuple[int, int]]:
        return {
            str(p): ((p.stat().st_size, p.stat().st_mtime_ns) if p.is_file() else (-1, 0))
            for p in self.root.rglob("*")
        }

    def test_no_file_or_directory_is_created_or_changed(self):
        self.declare(self.peer, "builder", "x")
        # The box and key come off the record's own path, so the baseline is taken before ANY run.
        (path,) = self.record_files()
        before = self.snapshot()
        runs = [(), ("-Text",), ("-Json",), ("-Text", "-All"),
                ("-Chip", "-BoxKey", path.parent.name, "-SessionKey", path.stem)]
        for args in runs:
            result = self.fleet(*args)
            self.assertEqual(0, result.returncode, f"{args}: {result.stdout}{result.stderr}")
            self.assertTrue(result.stdout.strip(), f"{args} printed nothing")
        self.assertEqual(before, self.snapshot())


class TheFetchClockNamesOriginsTrunk(_FleetCase):
    """FETCH_HEAD is planted, because a fixture has no remote to fetch from. Git writes the url
    without its `user@` part and its `.git` suffix, which is what the planted line copies."""

    def plant_fetch_head(self, description: str) -> None:
        self.git(self.primary, "remote", "add", "origin", "git@example.com:org/repo.git")
        sha = self.git(self.primary, "rev-parse", "HEAD").stdout.strip()
        self.git(self.primary, "update-ref", "refs/remotes/origin/main", sha)
        (self.primary / ".git" / "FETCH_HEAD").write_text(f"{sha}\t\t{description}\n", encoding="ascii")

    def test_an_ssh_origin_fetch_is_measured(self):
        self.plant_fetch_head("branch 'main' of example.com:org/repo")
        _, data = self.fleet_json()
        self.assertIsInstance(data["receipt"]["originMainFetchAgeMinutes"], int)

    def test_a_pull_ref_fetch_is_not_a_trunk_fetch(self):
        """Control: same remote, same file, but it fetched something other than main."""
        self.plant_fetch_head("'refs/pull/7/head' of example.com:org/repo")
        _, data = self.fleet_json()
        self.assertIsNone(data["receipt"]["originMainFetchAgeMinutes"])


class EveryRenderRuns(_FleetCase):
    def test_default_and_text_print_the_receipt_first(self):
        self.declare(self.peer, "builder", "x")
        for args in ((), ("-Text",)):
            result = self.fleet(*args)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue(result.stdout.startswith("FLEET CONTINUITY ROSTER"), result.stdout[:200])
            self.assertIn("RECEIPT", result.stdout)
            self.assertIn("peer-branch", result.stdout)

    def test_the_empty_render_says_it_is_not_an_idle_fleet(self):
        result = self.fleet()
        self.assertIn("NO EPISODE RECORDS EXIST", result.stdout)
        self.assertIn("STOP CONDITIONS FIRED", result.stdout)

    def chip(self, row: dict) -> subprocess.CompletedProcess:
        return self.fleet("-Chip", "-BoxKey", row["Box"], "-SessionKey", row["SessionKey"])

    def test_chip_renders_the_declared_goal(self):
        self.declare(self.peer, "builder", "the declared goal")
        _, data = self.fleet_json()
        result = self.chip(self.row_for(data, "peer-branch"))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("GOAL AS DECLARED: the declared goal", result.stdout)
        self.assertIn("SEAT: builder", result.stdout)
        self.assertNotIn("WARNING: THIS ROW IS", result.stdout)

    def test_chip_for_a_missing_row_exits_2(self):
        result = self.fleet("-Chip", "-BoxKey", "no-such-box", "-SessionKey", "none")
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("no record for", result.stderr)

    def test_outside_a_repository_exits_2(self):
        outside = self.root / "not-a-repo"
        outside.mkdir()
        result = self.fleet("-RepoHint", str(outside), "-Json")
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("not inside a git repository", result.stderr)

    def test_chip_warns_when_the_row_is_still_running(self):
        """Control for the case above: the same briefing, for a seat that is not gone."""
        self.declare(self.peer, "builder", "still at it")
        self.plant_live_session(self.peer, "cccc-3333")
        _, data = self.fleet_json()
        result = self.chip(self.row_for(data, "peer-branch"))
        self.assertIn("WARNING: THIS ROW IS RUNNING", result.stdout)


if __name__ == "__main__":
    unittest.main()
