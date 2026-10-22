#!/usr/bin/env python3
"""Read the `code-review` skill's level tag out of its reviewer fork's transcript.

WHY THIS EXISTS. The `code-review` skill is built into the Claude Code CLI. It does not print its
level tag back to its caller, so a QA line could name the level a Builder PASSED and not prove which
level and shape RAN. `roles/BUILDER.md` section 4e records where the tag does land: it is line 2 of
the PROMPT the skill feeds its reviewer fork, and that prompt is record 0 of the fork's transcript.

    <projects dir>/<project>/<session id>/subagents/agent-<id>.jsonl
    <projects dir>/<project>/<session id>/subagents/agent-<id>.meta.json

Record 0's user message begins `Review target: <args>`, and line 2 carries the tag inside
backticks. The meta file carries `inheritedWorktreePath`, `parentAgentId`, `spawnDepth` and
`agentType`.

WHAT IT PROVES, AND WHAT IT DOES NOT. The tag proves which prompt template the skill selected, not
that the fork obeyed it.

IT IS READ-ONLY, AND IT READS AS LITTLE AS IT CAN. Per fork it reads the meta file first, applies
every filter it can from there, and only then reads record 0 -- one line of the transcript -- and
from that only the first two lines of the message. No later record is read or printed. Path columns
(the transcript, the worktree) are printed only under `--verbose`, because the leak gate forbids a
user-home path in published text and a QA line is published text.

NOT MEASURED, so it says so rather than guessing. The inline shape (`Agent tool unavailable ->
single-pass inline`) has no fork: its prompt lands in the caller's own transcript, which this tool
does not read. A miss therefore names that possibility instead of printing a blank.

    python scripts/quality/review_tag.py --target "Review this branch's diff"
    python scripts/quality/review_tag.py --latest --ascii
    python scripts/quality/review_tag.py --worktree . --since 2026-10-22T09:00:00Z --verbose

Exit codes. Each failure has its own, so a caller can tell them apart without parsing text:

    0  at least one matching fork carried a tag on line 2
    2  usage error (argparse)
    3  no fork found; inline shape or unpersisted transcript possible
    4  no projects dir, or a root could not be read and nothing matched
    5  matching forks were found, and none carried a tag on line 2
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

EXIT_FOUND = 0
EXIT_NO_FORK = 3
EXIT_NO_ROOT = 4
EXIT_NO_TAG = 5

NO_FORK_MESSAGE = "no fork found; inline shape or unpersisted transcript possible"
NO_ROOT_MESSAGE = "no projects dir could be read"
NO_TAG_MESSAGE = "matching fork(s) found, and none carried a tag on line 2"

TARGET_PREFIX = "Review target:"

#: The levels the skill parses. Its `Review target` line drops a level that parsed, so a caller who
#: passes `--target "xhigh Review this diff"` must still match a line reading `Review this diff`.
LEVELS = ("low", "medium", "high", "xhigh", "max")

#: A tag line starts `<level> effort` -- measured at CLI 2.1.278 and 2.1.301. Anything else on line 2
#: is reported as no tag rather than quoted as one.
TAG_SHAPE = re.compile(r"^[a-z]+ effort\b")

#: The glyphs the tag is known to carry, and their ASCII spellings under `--ascii`.
ASCII_SPELLINGS = {"\u2192": "->", "\u2264": "<=", "\u2265": ">="}


@dataclass
class Fork:
    transcript: Path
    agent_id: str
    session_id: str
    meta: dict = field(default_factory=dict)
    time: dt.datetime | None = None
    target: str = ""
    tag: str = ""
    matched_without_worktree: bool = False

    @property
    def worktree(self) -> str:
        value = self.meta.get("inheritedWorktreePath")
        return value if isinstance(value, str) else ""


def normalize_path(path: str, fold_case: bool | None = None) -> str:
    """Compare-ready spelling: forward slashes, no trailing slash, case-folded on Windows."""
    if fold_case is None:
        fold_case = os.name == "nt"
    text = path.replace("\\", "/")
    text = re.sub(r"/+", "/", text)
    if len(text) > 1:
        text = text.rstrip("/")
    return text.casefold() if fold_case else text


def projects_roots(explicit: list[str] | None = None) -> list[Path]:
    """`--projects-dir` if given, else `$CLAUDE_CONFIG_DIR/projects`, else every `~/.claude*/projects`."""
    if explicit:
        return [Path(p) for p in explicit]
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if config:
        return [Path(config) / "projects"]
    home = Path.home()
    try:
        candidates = sorted(home.glob(".claude*"))
    except OSError:
        return []
    return [c / "projects" for c in candidates if c.is_dir()]


def parse_time(text: str) -> dt.datetime | None:
    """ISO 8601 to an aware UTC datetime. A trailing `Z` is accepted on every supported Python."""
    if not isinstance(text, str) or not text:
        return None
    raw = text.strip()
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        value = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def message_text(record: dict) -> str:
    """The user message text of one transcript record, string or content-block form."""
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    return text
    return ""


def read_meta(transcript: Path) -> dict:
    meta_path = transcript.with_name(transcript.name[: -len(".jsonl")] + ".meta.json")
    try:
        with meta_path.open(encoding="utf-8") as fh:
            value = json.load(fh)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def read_record_zero(transcript: Path) -> tuple[dict | None, str]:
    """Record 0 only, and of its message only the first two lines. Never a later record."""
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        first = fh.readline()
    try:
        record = json.loads(first)
    except ValueError:
        return None, ""
    if not isinstance(record, dict):
        return None, ""
    lines = message_text(record).splitlines()[:2]
    return record, "\n".join(lines)


def target_matches(wanted: str, args: str) -> bool:
    """Substring match, whitespace-normalized and case-folded, with a leading level tolerated."""

    def squash(text: str) -> str:
        return " ".join(text.split()).casefold()

    have = squash(args)
    want = squash(wanted)
    if want in have:
        return True
    first, _, rest = want.partition(" ")
    return first in LEVELS and bool(rest) and rest in have


def fork_files(root: Path) -> list[Path]:
    """Every `agent-*.jsonl` under a `subagents` directory of a session, at any depth below it."""
    return sorted(root.glob("*/*/subagents/**/agent-*.jsonl"))


@dataclass
class Filters:
    worktree: str | None = None
    target: str | None = None
    session: str | None = None
    since: dt.datetime | None = None
    fold_case: bool | None = None


@dataclass
class Scan:
    forks: list[Fork] = field(default_factory=list)
    unreadable_roots: list[Path] = field(default_factory=list)
    missing_roots: list[Path] = field(default_factory=list)
    unreadable_files: int = 0
    skipped_no_worktree: int = 0


def scan(roots: list[Path], filters: Filters) -> Scan:
    result = Scan()
    want_worktree = (
        normalize_path(filters.worktree, filters.fold_case) if filters.worktree else None
    )
    for root in roots:
        if not root.is_dir():
            result.missing_roots.append(root)
            continue
        try:
            os.listdir(root)
            files = fork_files(root)
        except OSError:
            result.unreadable_roots.append(root)
            continue
        for transcript in files:
            parts = transcript.relative_to(root).parts
            session_id = parts[1] if len(parts) > 1 else ""
            agent_id = transcript.name[len("agent-") : -len(".jsonl")]
            if filters.session and session_id != filters.session:
                continue
            fork = Fork(transcript, agent_id, session_id, read_meta(transcript))
            if want_worktree is not None:
                if fork.worktree:
                    if normalize_path(fork.worktree, filters.fold_case) != want_worktree:
                        continue
                elif filters.session or filters.target:
                    fork.matched_without_worktree = True
                else:
                    result.skipped_no_worktree += 1
                    continue
            try:
                record, head = read_record_zero(transcript)
            except OSError:
                result.unreadable_files += 1
                continue
            if record is None:
                result.unreadable_files += 1
                continue
            lines = head.split("\n")
            if not lines[0].startswith(TARGET_PREFIX):
                continue
            fork.target = lines[0][len(TARGET_PREFIX) :].strip()
            if filters.target and not target_matches(filters.target, fork.target):
                continue
            if len(lines) > 1:
                candidate = lines[1].strip().strip("`").strip()
                if TAG_SHAPE.match(candidate):
                    fork.tag = candidate
            fork.time = parse_time(record.get("timestamp", ""))
            if fork.time is None:
                try:
                    fork.time = dt.datetime.fromtimestamp(
                        transcript.stat().st_mtime, tz=dt.timezone.utc
                    )
                except OSError:
                    pass
            if filters.since and (fork.time is None or fork.time < filters.since):
                continue
            result.forks.append(fork)
    epoch = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    result.forks.sort(key=lambda f: (f.time or epoch, f.agent_id))
    return result


def git_toplevel() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def spell(text: str, ascii_only: bool) -> str:
    if not ascii_only:
        return text
    for glyph, plain in ASCII_SPELLINGS.items():
        text = text.replace(glyph, plain)
    return "".join(c if ord(c) < 128 else f"\\u{ord(c):04x}" for c in text)


def stamp(value: dt.datetime | None) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else "time unknown"


def render(forks: list[Fork], total: int, offset: int, ascii_only: bool, verbose: bool) -> list[str]:
    out: list[str] = []
    for index, fork in enumerate(forks, start=offset + 1):
        out.append(f"round {index} of {total} | {stamp(fork.time)} | agent {fork.agent_id}")
        out.append(f"  target: {spell(fork.target, ascii_only) or '(none)'}")
        out.append(f"  tag: {spell(fork.tag, ascii_only) if fork.tag else 'NONE ON LINE 2'}")
        if fork.matched_without_worktree:
            out.append("  note: no inheritedWorktreePath recorded; matched by session and --target")
        if verbose:
            meta = fork.meta
            out.append(f"  session: {fork.session_id}")
            out.append(f"  parentAgentId: {meta.get('parentAgentId', '(absent)')}")
            out.append(f"  spawnDepth: {meta.get('spawnDepth', '(absent)')}")
            out.append(f"  agentType: {meta.get('agentType', '(absent)')}")
            out.append(f"  worktree: {fork.worktree or '(absent)'}")
            out.append(f"  transcript: {fork.transcript}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read the code-review skill's level tag from its reviewer fork's transcript.",
    )
    parser.add_argument(
        "--worktree",
        help="match forks whose inheritedWorktreePath is this path (default: the current git toplevel)",
    )
    parser.add_argument(
        "--any-worktree", action="store_true", help="do not filter on the worktree at all"
    )
    parser.add_argument("--target", help="substring of the arguments the skill was called with")
    parser.add_argument("--session", help="the session id the fork ran under")
    parser.add_argument("--since", help="only forks whose record 0 is at or after this ISO time")
    parser.add_argument("--latest", action="store_true", help="print only the newest matching round")
    parser.add_argument("--ascii", action="store_true", help="print -> and <= instead of the glyphs")
    parser.add_argument("--verbose", action="store_true", help="add session, meta and path columns")
    parser.add_argument(
        "--projects-dir",
        action="append",
        help="read this projects dir instead of the default roots (repeatable)",
    )
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    since = None
    if args.since:
        since = parse_time(args.since)
        if since is None:
            parser.error(f"--since is not an ISO 8601 time: {args.since!r}")

    worktree = None
    worktree_label = "any worktree"
    if not args.any_worktree:
        if args.worktree:
            # A drive-letter or rooted spelling is taken as given, so a Windows path names the same
            # worktree when this runs on Linux; only a relative one is resolved against the cwd.
            given = args.worktree
            absolute = re.match(r"^(?:[A-Za-z]:)?[\\/]", given)
            worktree = given if absolute else str(Path(given).resolve())
            worktree_label = "worktree from --worktree"
        else:
            worktree = git_toplevel()
            worktree_label = "worktree = current git toplevel"
            if worktree is None:
                worktree_label = "any worktree (no git toplevel here)"

    roots = projects_roots(args.projects_dir)
    result = scan(roots, Filters(worktree, args.target, args.session, since))

    described = [worktree_label]
    if args.target:
        described.append(f"target ~ {spell(args.target, args.ascii)!r}")
    if args.session:
        described.append(f"session = {args.session}")
    if args.since:
        described.append(f"since {stamp(since)}")
    # Nothing on stdout carries the word the QA line may not, except the target line, which echoes
    # the caller's own arguments. Builders quote the tag line and the refusal lines from here.
    print(f"matched {len(result.forks)} fork(s) ({'; '.join(described)})")

    for root in result.unreadable_roots:
        print(f"review_tag: could not read a projects root{f': {root}' if args.verbose else ''}",
              file=sys.stderr)
    if result.unreadable_files:
        print(f"review_tag: {result.unreadable_files} fork transcript(s) could not be read",
              file=sys.stderr)
    if result.skipped_no_worktree:
        print(
            f"review_tag: {result.skipped_no_worktree} fork(s) record no worktree and were skipped;"
            " pass --session or --target to match them",
            file=sys.stderr,
        )

    if not result.forks:
        readable = [r for r in roots if r not in result.missing_roots + result.unreadable_roots]
        if not readable:
            print(NO_ROOT_MESSAGE)
            return EXIT_NO_ROOT
        print(NO_FORK_MESSAGE)
        return EXIT_NO_ROOT if result.unreadable_roots else EXIT_NO_FORK

    total = len(result.forks)
    shown = result.forks[-1:] if args.latest else result.forks
    for line in render(shown, total, total - len(shown), args.ascii, args.verbose):
        print(line)

    if not any(f.tag for f in shown):
        print(NO_TAG_MESSAGE)
        return EXIT_NO_TAG
    return EXIT_FOUND


if __name__ == "__main__":
    sys.exit(main())
