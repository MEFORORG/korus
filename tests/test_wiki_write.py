"""`scripts/wiki/write.ps1` is the only way an event enters the fleet wiki. Pin what it refuses.

WHAT IT PROMISES (spec FR-001 to FR-007): one JSON file per event, in the inbox, stamped by its own
UTC clock, after the leak scan has passed every field -- and on any refusal, nothing on disk and a
one-line reason that never repeats a secret.

EVERY REFUSAL HERE IS PAIRED WITH A WRITE THAT SUCCEEDS. A refusal test alone cannot tell "the
script refused this input" from "the script refuses everything", and the second reads identically
in a green run.

THE LEAK CASES CARRY A CONTROL ON THE SCANNER ITSELF. A refusal proves the write stopped; it does not
prove the scan is why. So the same planted value is run through `scan_forbidden.py` directly and
must fire there, and a harmless twin of the same event must be written.

Run: python -m pytest tests/test_wiki_write.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _wikitest as w

BACKSLASH = chr(92)


def forge_token() -> str:
    """A credential-shaped value, built at run time so this file carries no literal the leak gate
    over the tracked tree would fire on."""
    return "gh" + "p_" + "A" * 36


def home_path() -> str:
    """A Windows home path with a plausible account name, built at run time for the same reason."""
    return "C:" + BACKSLASH + "Users" + BACKSLASH + "alice" + BACKSLASH + "proj"


class _WriteCase(unittest.TestCase):
    def setUp(self):
        self.pwsh = w.find_pwsh_or_skip(self)
        tmp = tempfile.TemporaryDirectory(prefix="wiki-write-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / "state"
        self.state.mkdir()

    def write(self, *args: str, seat: str | None = "builder", cwd: Path | None = None, state: Path | None = None,
              use_state: bool = True, env: dict | None = None):
        argv = list(args)
        if seat is not None:
            argv += ["-Seat", seat]
        if use_state:
            argv += ["-StateRoot", str(state or self.state)]
        return w.run(self.pwsh, w.WRITE, *argv, cwd=cwd, env=env)

    def good(self, **over) -> list[str]:
        fields = {
            "-Type": "lesson",
            "-Key": "gate/ascii/windows-exit-code",
            "-Summary": "The ascii gate collapses exit code 2 to 1 under -Command",
            "-Evidence": "9379109",
        }
        fields.update(over)
        out: list[str] = []
        for k, v in fields.items():
            if v is not None:
                out += [k, v]
        return out

    def inbox_files(self) -> list[Path]:
        d = w.inbox_dir(self.state)
        return sorted(d.glob("*")) if d.is_dir() else []

    def tmp_files(self) -> list[Path]:
        d = self.state / "wiki" / "tmp"
        return sorted(d.glob("*")) if d.is_dir() else []

    def assertRefused(self, r: subprocess.CompletedProcess, reason: str, code: int = 1):
        self.assertEqual(code, r.returncode, f"expected exit {code}; stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("REFUSED", r.stderr)
        self.assertIn(reason, r.stderr)
        self.assertEqual("", r.stdout.strip(), "a refusal printed something on stdout, where an id goes")
        self.assertEqual([], self.inbox_files(), "a refused event reached the inbox")


class AWriteLandsOneFile(_WriteCase):
    def test_it_prints_the_id_and_writes_exactly_that_file(self):
        before = datetime.now(timezone.utc)
        r = self.write(*self.good(**{"-Paths": "scripts/quality/check-ascii.ps1,docs/HOUSE-STYLE.md",
                                      "-StaleAfter": "2099-01-01", "-Body": "line one\nline two"}))
        after = datetime.now(timezone.utc)
        self.assertEqual(0, r.returncode, r.stderr)
        event_id = r.stdout.strip()
        self.assertRegex(event_id, w.ID_PATTERN)

        files = self.inbox_files()
        self.assertEqual([w.inbox_dir(self.state) / f"{event_id}.json"], files)
        self.assertEqual([], self.tmp_files(), "the scan file or the temp write was left behind")

        event = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(event_id, event["id"])
        self.assertEqual("lesson", event["type"])
        self.assertEqual("builder", event["seat"])
        self.assertEqual("generated", event["trust"])
        self.assertEqual(["scripts/quality/check-ascii.ps1", "docs/HOUSE-STYLE.md"], event["paths"])
        self.assertEqual("2099-01-01", event["stale_after"])
        self.assertIn("line two", event["body"])
        # The clock is the script's, in UTC, and between our two reads of ours.
        ts = datetime.strptime(event["ts"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        self.assertLessEqual(before.replace(microsecond=before.microsecond // 1000 * 1000), ts)
        self.assertLessEqual(ts, after)
        self.assertTrue(event_id.startswith(ts.strftime("%Y%m%dT%H%M%S")), "the id and ts disagree")

    def test_two_writes_make_two_files(self):
        """One file per event is the whole contention answer (Article XII)."""
        a = self.write(*self.good())
        b = self.write(*self.good())
        self.assertEqual(0, a.returncode, a.stderr)
        self.assertEqual(0, b.returncode, b.stderr)
        self.assertNotEqual(a.stdout.strip(), b.stdout.strip())
        self.assertEqual(2, len(self.inbox_files()))

    def test_a_caller_cannot_supply_the_stamp(self):
        r = self.write(*self.good(), "-Ts", "2020-01-01T00:00:00Z")
        self.assertNotEqual(0, r.returncode)
        self.assertEqual([], self.inbox_files())

    def test_any_type_may_carry_supersedes(self):
        """A `correction` usually replaces an earlier note, so -Supersedes is not reserved to `supersede`."""
        old = self.write(*self.good()).stdout.strip()
        r = self.write(*self.good(**{"-Type": "correction", "-Supersedes": old}))
        self.assertEqual(0, r.returncode, r.stderr)
        event = json.loads((w.inbox_dir(self.state) / f"{r.stdout.strip()}.json").read_text(encoding="utf-8"))
        self.assertEqual(("correction", [old]), (event["type"], event["supersedes"]))

    def test_supersedes_accepts_a_comma_list(self):
        """`pwsh -File` passes `a,b` as one string, so the script has to split it itself."""
        one = self.write(*self.good()).stdout.strip()
        two = self.write(*self.good()).stdout.strip()
        r = self.write(*self.good(**{"-Type": "supersede", "-Supersedes": f"{one},{two}"}))
        self.assertEqual(0, r.returncode, r.stderr)
        event = json.loads((w.inbox_dir(self.state) / f"{r.stdout.strip()}.json").read_text(encoding="utf-8"))
        self.assertEqual([one, two], event["supersedes"])


class TheDefaultStateRootIsTheCallersRepository(_WriteCase):
    """With no -StateRoot, the inbox is the one under the repository the caller STANDS in.

    Seats run this repository's copy of the script from inside another repository. A lookup keyed on
    where the script lives would file every event into this repository's own coordination
    directory, where no seat in the other repository ever reads. The prefix is a deliberately odd
    one, so a hit can only have come from the caller's own config.
    """

    def test_the_event_lands_under_the_cwd_repositorys_state_root(self):
        other = w.make_repo(self.root / "other-repo", prefix="zzq")
        r = self.write(*self.good(), cwd=other, state=None, use_state=False)
        self.assertEqual(0, r.returncode, r.stderr)
        event_id = r.stdout.strip()
        self.assertTrue((other / ".git" / "zzq-coord" / "wiki" / "inbox" / f"{event_id}.json").is_file(),
                        "the event did not land under the calling repository's state root")
        # Control: this repository's own state root holds no copy of it.
        own = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                             cwd=str(w.t.REPO_ROOT), capture_output=True, text=True, timeout=w.TIMEOUT_SECONDS)
        own_inbox = Path(own.stdout.strip()) / "ccx-coord" / "wiki" / "inbox"
        self.assertFalse((own_inbox / f"{event_id}.json").exists(), "the event was filed where the script lives")

    def test_a_repository_with_no_config_is_refused_not_redirected(self):
        """No ccx.config.json means no prefix, so no state root: refuse, and say to pass -StateRoot."""
        bare = w.make_repo(self.root / "no-config", prefix=None)
        r = self.write(*self.good(), cwd=bare, use_state=False)
        self.assertEqual(2, r.returncode, r.stderr)
        self.assertIn("not reachable", r.stderr)
        self.assertEqual([], list((bare / ".git").glob("*-coord")), "a state root was invented")


class TheSeatComesFromTheMarker(_WriteCase):
    def checkout(self, marker: str | None) -> Path:
        co = self.root / "checkout"
        (co / ".git").mkdir(parents=True)
        sub = co / "deep" / "er"
        sub.mkdir(parents=True)
        if marker is not None:
            (co / ".claude").mkdir()
            (co / ".claude" / "seat.local.txt").write_text(marker + "\n", encoding="ascii")
        return sub

    def test_no_seat_and_no_marker_is_refused(self):
        r = self.write(*self.good(), seat=None, cwd=self.checkout(None))
        self.assertRefused(r, "seat.local.txt")

    def test_korus_seat_is_the_fallback_the_role_card_hook_also_reads(self):
        r = self.write(*self.good(), seat=None, cwd=self.checkout(None), env={"KORUS_SEAT": "manager"})
        self.assertEqual(0, r.returncode, r.stderr)
        event = json.loads(self.inbox_files()[0].read_text(encoding="utf-8"))
        self.assertEqual("manager", event["seat"])

    def test_the_marker_supplies_the_seat_from_anywhere_in_the_checkout(self):
        r = self.write(*self.good(), seat=None, cwd=self.checkout("Lander"))
        self.assertEqual(0, r.returncode, r.stderr)
        event = json.loads(self.inbox_files()[0].read_text(encoding="utf-8"))
        self.assertEqual("lander", event["seat"])


class ItRefusesABadEvent(_WriteCase):
    def test_missing_evidence_is_refused(self):
        self.assertRefused(self.write(*self.good(**{"-Evidence": None})), "-Evidence is required")

    def test_evidence_that_cites_nothing_is_refused(self):
        self.assertRefused(self.write(*self.good(**{"-Evidence": "trust me"})), "evidence names no commit")

    def test_each_evidence_shape_is_accepted(self):
        """The other half: the evidence rule refuses "trust me", not a real citation."""
        for evidence in ("2aec304", "PR #1424", "origin/main:roles/LANDER.md", "Owner ruling 2026-09-23"):
            with self.subTest(evidence=evidence):
                r = self.write(*self.good(**{"-Evidence": evidence}))
                self.assertEqual(0, r.returncode, r.stderr)

    def test_a_clock_time_is_not_a_ref_path(self):
        self.assertRefused(self.write(*self.good(**{"-Evidence": "seen at 14:05"})), "evidence names no commit")

    def test_an_unknown_type_is_refused(self):
        self.assertRefused(self.write(*self.good(**{"-Type": "rumour"})), "unknown type 'rumour'")

    def test_a_supersede_without_supersedes_is_refused(self):
        self.assertRefused(self.write(*self.good(**{"-Type": "supersede"})), "must name the event(s) it replaces")

    def test_a_malformed_key_is_refused(self):
        self.assertRefused(self.write(*self.good(**{"-Key": "Gate/ASCII"})), "is not lower-case")

    def test_an_absolute_path_is_refused(self):
        self.assertRefused(self.write(*self.good(**{"-Paths": "/etc/passwd"})), "is absolute")

    def test_a_missing_state_root_is_refused_and_not_created(self):
        gone = self.root / "no-such-state"
        r = self.write(*self.good(), state=gone)
        self.assertEqual(2, r.returncode, r.stderr)
        self.assertIn("not reachable", r.stderr)
        self.assertIn(str(gone), r.stderr)
        self.assertFalse(gone.exists(), "a typo'd state root was created, swallowing the event")

    def test_the_refusal_names_the_root_as_the_caller_spelled_it(self):
        """Resolving can respell a path. CI's temp dir is an 8.3 short name (`RUNNER~1`), which
        GetFullPath expands, and a refusal naming only the expanded form named a path the caller
        never typed. A `..` segment respells it the same way on every platform, so it stands in.
        The resolved half is matched loosely because on CI it is the expanded form of `self.root`."""
        given = self.root / "state" / ".." / "no-such-state"
        r = self.write(*self.good(), state=given)
        self.assertEqual(2, r.returncode, r.stderr)
        self.assertIn(f"'{given}'", r.stderr, "the refusal does not name the path the caller passed")
        resolved = r.stderr.split("(resolved to '", 1)[-1] if "(resolved to '" in r.stderr else ""
        self.assertIn("no-such-state'", resolved, "the resolved path went missing")
        self.assertNotIn("..", resolved, "the resolved path is not resolved")

    def test_a_state_root_on_a_missing_drive_is_could_not_run_not_refused(self):
        """Resolving a path on a drive that does not exist throws. Uncaught, that exited 1, which
        this script reserves for a bad event; an inbox it cannot reach is exit 2."""
        r = self.write(*self.good(), state=w.missing_drive("coord"))
        self.assertEqual(2, r.returncode, r.stderr)
        self.assertIn("not reachable", r.stderr)
        self.assertIn("cannot be resolved", r.stderr)
        self.assertEqual("", r.stdout.strip())


class AWriteWithAStateRootRunsNoGit(_WriteCase):
    """FR-007: with -StateRoot given, a write makes no git call at all.

    A `git` shim sits first on PATH and records every call to a file. THE CONTROL is the default
    state root, which does call git; the shim must record that call, or it could not see one here.

    ITS REACH IS PWSH'S. On Windows the shim is `git.cmd`, which PowerShell resolves and Python's
    `subprocess` does not, so a git call from the leak scanner would pass unseen. The scanner is
    handed a file, and it runs git only when it is handed nothing."""

    def setUp(self):
        super().setUp()
        self.calls = self.root / "git-calls.txt"
        shim_dir = self.root / "shim"
        shim_dir.mkdir()
        if os.name == "nt":
            (shim_dir / "git.cmd").write_text(f'@echo called>>"{self.calls}"\r\n@exit /b 1\r\n', encoding="ascii")
        else:
            shim = shim_dir / "git"
            shim.write_text(f'#!/bin/sh\necho called >> "{self.calls}"\nexit 1\n', encoding="ascii")
            shim.chmod(0o755)
        self.env = {"PATH": str(shim_dir) + os.pathsep + os.environ.get("PATH", "")}

    def test_an_explicit_state_root_calls_no_git(self):
        r = self.write(*self.good(), env=self.env)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(1, len(self.inbox_files()))
        self.assertFalse(self.calls.exists(), "a write given -StateRoot called git")

    def test_control_the_default_state_root_is_seen_calling_git(self):
        repo = w.make_repo(self.root / "repo", prefix="zzq")
        r = self.write(*self.good(), cwd=repo, use_state=False, env=self.env)
        self.assertTrue(self.calls.exists(), f"the shim saw no git call, so it proves nothing: {r.stderr}")


class TheLeakScanRunsFirst(_WriteCase):
    def scan_directly(self, text: str) -> subprocess.CompletedProcess:
        """The CONTROL: the scanner, on its own, over a file holding the planted value."""
        f = self.root / "scan-control.txt"
        f.write_text(text + "\n", encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(w.SCANNER), f.name],
            capture_output=True,
            text=True,
            cwd=str(self.root),
            timeout=w.TIMEOUT_SECONDS,
        )

    def test_a_planted_credential_is_refused_naming_the_class_and_not_the_value(self):
        secret = forge_token()

        control = self.scan_directly(f"summary: token {secret} here")
        self.assertEqual(1, control.returncode, "the scanner does not fire on the planted value by itself")
        self.assertIn("forge access token", control.stderr)
        clean = self.scan_directly("summary: token REDACTED here")
        self.assertEqual(0, clean.returncode, "the scanner fires on the harmless twin too")

        r = self.write(*self.good(**{"-Summary": f"token {secret} here"}))
        self.assertRefused(r, "forge access token")
        self.assertNotIn(secret, r.stdout + r.stderr, "the refusal printed the secret it refused")
        self.assertEqual([], self.tmp_files(), "the scan file holding the secret was left on disk")

        twin = self.write(*self.good(**{"-Summary": "token REDACTED here"}))
        self.assertEqual(0, twin.returncode, "the harmless twin was refused, so the refusal above is not the scan's")

    def test_a_secret_in_a_field_that_is_also_malformed_is_not_echoed(self):
        """Schema refusals quote the bad value. They run after the scan, so a secret never reaches one."""
        secret = forge_token()
        r = self.write(*self.good(**{"-Key": f"Bad/{secret}"}))
        self.assertRefused(r, "forge access token")
        self.assertNotIn(secret, r.stdout + r.stderr)

    def test_a_control_character_is_refused_before_the_scanner_can_skip_the_file(self):
        """A NUL makes the scanner read the whole file as binary and pass it unscanned.

        The control proves that hole is real: the scanner, given a NUL beside the credential, exits
        0. So the write has to refuse the NUL itself, by field name, before any scan.
        """
        secret = forge_token()
        f = self.root / "nul-control.txt"
        f.write_bytes(b"summary: \x00 " + secret.encode("ascii") + b"\n")
        control = subprocess.run([sys.executable, str(w.SCANNER), f.name], capture_output=True, text=True,
                                 cwd=str(self.root), timeout=w.TIMEOUT_SECONDS)
        self.assertEqual(0, control.returncode, "the scanner now reads past a NUL; this guard may be redundant")

        r = self.write(*self.good(**{"-Summary": "a\x01b"}))
        self.assertRefused(r, "field 'summary' contains a control character")

    def test_an_allowlisted_neighbour_does_not_exempt_a_home_path(self):
        """The scanner skips a whole LINE matching its allowlist. A home path beside an allowlisted
        example path must still be caught, so each word is also scanned on a line of its own."""
        example = "C:" + BACKSLASH + "Users" + BACKSLASH + "someone" + BACKSLASH + "project" + BACKSLASH + "file.txt"
        line = f"copy {home_path()} not {example}"
        self.assertEqual(0, self.scan_directly(f"summary: {line}").returncode,
                         "control: the allowlist no longer exempts the line, so this case is moot")
        r = self.write(*self.good(**{"-Summary": line}))
        self.assertRefused(r, "absolute user-home path")

    def test_a_clean_pass_says_when_it_was_structural_only(self):
        r = self.write(*self.good())
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("structural-only", r.stderr)

    def test_a_windows_home_path_is_caught_although_json_would_hide_it(self):
        """Why the scan reads a plain rendering and not just the JSON (the plan's named risk).

        JSON doubles each backslash, and the home-path detector wants one. The control shows the
        JSON form alone passes the scanner, so a write that scanned only its JSON would ship it.
        """
        value = home_path()
        as_json = json.dumps({"summary": f"see {value}"})
        self.assertIn(BACKSLASH * 2, as_json)
        self.assertEqual(0, self.scan_directly(as_json).returncode,
                         "the JSON form now fires too; the plain rendering may no longer be needed")
        self.assertEqual(1, self.scan_directly(f"summary: see {value}").returncode,
                         "the scanner no longer fires on a raw home path")

        r = self.write(*self.good(**{"-Summary": f"see {value}"}))
        self.assertRefused(r, "absolute user-home path")
        self.assertNotIn("alice", r.stdout + r.stderr)


class AWriteIsQuick(_WriteCase):
    """SC-003: a write returns in under one second on the reference machine.

    THE ASSERTED CEILING IS LOOSER THAN THE TARGET, on purpose. The wall clock here includes a cold
    `pwsh` start and a python start for the scan, and a shared CI runner can spend longer than the
    whole target on the first alone. So this catches a regression by an order of magnitude, and the
    measured figure on the reference machine is recorded in the pull request that set it.
    """

    CEILING_SECONDS = 5.0

    def test_the_fastest_of_three_writes_is_under_the_ceiling(self):
        times = []
        for _ in range(3):
            start = time.perf_counter()
            r = self.write(*self.good())
            times.append(time.perf_counter() - start)
            self.assertEqual(0, r.returncode, r.stderr)
        self.assertLess(min(times), self.CEILING_SECONDS, f"write wall-clock seconds: {times}")



class NotedIsTheDayAFactWasObserved(_WriteCase):
    def test_a_past_noted_is_written_and_ts_is_still_the_clock(self):
        r = self.write(*self.good(), "-Noted", "2026-07-03")
        self.assertEqual(0, r.returncode, r.stderr)
        [f] = self.inbox_files()
        ev = json.loads(f.read_text(encoding="utf-8"))
        self.assertEqual("2026-07-03", ev["noted"])
        self.assertEqual(datetime.now(timezone.utc).strftime("%Y-%m-%d"), ev["ts"][:10], "noted moved ts")

    def test_a_malformed_or_future_noted_is_refused_and_nothing_is_written(self):
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
        for bad in ("2026-7-3", "03/07/2026", "yesterday", tomorrow):
            with self.subTest(noted=bad):
                r = self.write(*self.good(), "-Noted", bad)
                self.assertEqual(1, r.returncode, r.stdout + r.stderr)
                self.assertIn("noted", r.stderr)
                self.assertEqual([], self.inbox_files())
        # CONTROL: today itself is accepted.
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(0, self.write(*self.good(), "-Noted", today).returncode)

if __name__ == "__main__":
    unittest.main()
