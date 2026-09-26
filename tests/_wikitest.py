"""Helpers shared by the three fleet-wiki test files. Standard library only.

EVERY CASE DRIVES THE REAL SCRIPTS THROUGH `pwsh`, the way `test_seat.py` does. The scripts' job is
reading and writing files in a state root, so a mock would have to invent the thing under test.

EVENTS ARE PLANTED BY HAND WHERE A TEST NEEDS A CHOSEN CLOCK. `write.ps1` reads the clock itself and
takes no stamp (spec FR-004), which is the point of it -- and which means an aging, stale or
tie-breaking case cannot be produced through it. A planted event is held to the same schema check
on the way out (`Test-WikiEvent` runs in every reader), so a malformed plant is skipped and counted
rather than silently trusted.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import string
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120
WIKI = t.REPO_ROOT / "scripts" / "wiki"
WRITE = WIKI / "write.ps1"
QUERY = WIKI / "query.ps1"
EVENT_LIB = WIKI / "_event.ps1"
GUARD_LIB = WIKI / "_guard.ps1"
SCANNER = t.REPO_ROOT / "scripts" / "security" / "scan_forbidden.py"

ID_PATTERN = r"^\d{8}T\d{9}Z-[0-9a-z]{6}$"

_B36 = string.digits + string.ascii_lowercase


def stamp_id(when: datetime, suffix: str) -> str:
    """An id in the shape write.ps1 mints, with a chosen suffix -- for a tie-break case."""
    return when.strftime("%Y%m%dT%H%M%S") + f"{when.microsecond // 1000:03d}Z-{suffix}"


def make_id(when: datetime) -> str:
    """An id in the shape write.ps1 mints, for an event planted at a chosen time."""
    return stamp_id(when, "".join(secrets.choice(_B36) for _ in range(6)))


def stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when.microsecond // 1000:03d}Z"


def days_ago(n: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


def plant(directory: Path, *, when: datetime | None = None, event_id: str | None = None, **fields) -> dict:
    """Write one event file straight into `directory`, as the compile job or a hand edit would.

    Defaults fill every required field, so a case names only what it is about.
    """
    when = when or datetime.now(timezone.utc)
    event = {
        "id": event_id or make_id(when),
        "ts": stamp(when),
        "type": "lesson",
        "key": "test/planted",
        "seat": "builder",
        "summary": "a planted event",
        "evidence": "2aec304",
        "trust": "generated",
    }
    event.update(fields)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{event['id']}.json").write_text(json.dumps(event, indent=2), encoding="utf-8")
    return event


def missing_drive(tail: str) -> str:
    """A path on a drive letter this machine does not have, such as `Q:` then `tail`.

    Resolving it makes PowerShell throw "Cannot find drive" on every platform: on Linux `Q:` still
    parses as a drive qualifier, and no such drive exists there either. The letter is chosen at run
    time, because a fixed one could be a real mapped drive on some machine.
    """
    for letter in "QRSTUVWXYZ":
        root = letter + ":" + chr(92)
        if not os.path.exists(root):
            return root + tail
    raise AssertionError("every drive letter from Q to Z exists here; no unreachable drive to test with")


def inbox_dir(state_root: Path) -> Path:
    return state_root / "wiki" / "inbox"


def log_dir(record_repo: Path, when: datetime) -> Path:
    return record_repo / "wiki" / "events" / when.strftime("%Y") / when.strftime("%m")


def find_pwsh_or_skip(case) -> str:
    pwsh = t.find_pwsh()
    if not pwsh:
        case.skipTest("pwsh is not on PATH, so the wiki scripts cannot be executed here")
    return pwsh


def run(pwsh: str, script: Path, *args: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    # The leak scan reads these. A developer's own token file or a CI secret must not change what a
    # planted value does, so each case runs structural-only unless it says otherwise.
    # KORUS_SEAT is the seat fallback write.ps1 reads; a session that has one set must not turn a
    # "no seat" case green.
    for var in ("CCX_FORBIDDEN_TOKENS", "CCX_REQUIRE_TOKENS", "CCX_MIN_DETECTORS", "CCX_CONFIG", "KORUS_SEAT"):
        full_env.pop(var, None)
    if env:
        full_env.update(env)
    return subprocess.run(
        [pwsh, "-NoProfile", "-File", str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=full_env,
        timeout=TIMEOUT_SECONDS,
    )


def run_ps(pwsh: str, command: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a PowerShell snippet that dot-sources the wiki libraries. For the guard-bypass controls."""
    prelude = f". '{EVENT_LIB}'; . '{GUARD_LIB}'; "
    return subprocess.run(
        [pwsh, "-NoProfile", "-Command", prelude + command],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        timeout=TIMEOUT_SECONDS,
    )


def ids_in(text: str) -> list[str]:
    """Event ids at the start of a result line, in order."""
    return re.findall(r"^(\d{8}T\d{9}Z-[0-9a-z]{6})\s", text, re.M)


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {r.stderr}")
    return r


def make_repo(path: Path, prefix: str | None) -> Path:
    """A throwaway clone with one commit. `prefix` writes a ccx.config.json; None writes none."""
    path.mkdir(parents=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "t")
    name = "ccx.config.json" if prefix is not None else "a.txt"
    content = '{"prefix": "%s"}\n' % prefix if prefix is not None else "a\n"
    (path / name).write_text(content, encoding="ascii")
    git(path, "add", name)
    # The path in the message makes every repository's root commit its own. Without it, two made
    # in one second share one root SHA, so tests of "a different repository" pass or fail by clock.
    git(path, "commit", "-m", f"first: {path}")
    return path
