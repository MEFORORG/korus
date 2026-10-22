#!/usr/bin/env python3
"""Read the `code-review` skill's level tag out of its reviewer fork's transcript.

WHY THIS EXISTS. The `code-review` skill is built into the Claude Code CLI. It does not print its
level tag back to its caller, so a QA line could name the level a Builder PASSED and not prove which
level and shape RAN. `roles/BUILDER.md` section 4e records where the tag does land: near the top of
the PROMPT the skill feeds its reviewer fork, and that prompt is record 0 of the fork's transcript.

    <projects dir>/<project>/<session id>/subagents/agent-<id>.jsonl
    <projects dir>/<project>/<session id>/subagents/agent-<id>.meta.json

Record 0's user message opens with a `Review target: <args>` line, and the tag is a line of its own
shortly after it, inside backticks. Measured in one cloud session at CLI 2.1.307, the target was
itself in backticks, line 2 was blank and the tag was line 3. A Windows sample at 2.1.301 was relayed
as "line 2". So the tag is the first line of the head that has the tag's shape, not a fixed index.

WHERE THE FORK RAN. The meta file may carry `inheritedWorktreePath` (the relayed Windows sample,
Builder subagents at spawn depth 2). The cloud sample's meta did not; its record 0 carried `cwd`.
The tool uses the first of the two it finds, says which on every row, and matches a fork that has
neither only when a session filter already placed it.

WHAT IT PROVES, AND WHAT IT DOES NOT. The tag proves which prompt template the skill selected, not
that the fork obeyed it.

IT IS READ-ONLY, AND IT READS AS LITTLE AS IT CAN. Per fork it reads the meta file, applies the
session filter, and only then reads record 0 -- one line of the transcript -- and from that only the
first HEAD_LINES lines of the message. No later record is read or printed. Path columns are printed
only under `--verbose`, because the leak gate forbids a user-home path in published text and a QA
line is published text.

NOT MEASURED, so it says so rather than guessing. The inline shape (`Agent tool unavailable ->
single-pass inline`) has no fork: its prompt lands in the caller's own transcript, which this tool
does not read. A miss therefore names that possibility instead of printing a blank.

    python scripts/quality/review_tag.py --target "Review this branch's diff"
    python scripts/quality/review_tag.py --latest --ascii
    python scripts/quality/review_tag.py --worktree . --since 2026-10-22T09:00:00Z --verbose

Exit codes. Each failure has its own, so a caller can tell them apart without parsing text:

    0  the newest matching fork carried a tag
    2  usage error (argparse)
    3  no fork found; inline shape or unpersisted transcript possible
    4  no projects dir could be read, or a root could not be read and nothing matched in the rest
    5  matching forks were found, and the newest carried no tag line
    6  forks were found with no recorded worktree and no session filter to place them
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
EXIT_UNPLACED = 6

# Every stdout line a Builder may quote is one of these or a `tag:` line. None carries the word the
# QA line may not; `tests/test_review_tag_reads_the_fork_it_was_asked_for.py` holds that.
NO_FORK_MESSAGE = "no fork found; inline shape or unpersisted transcript possible"
NO_ROOT_MESSAGE = "no projects dir could be read"
PARTIAL_ROOT_MESSAGE = "a projects root could not be read, and no fork matched in the rest"
NO_TAG_MESSAGE = "the newest matching fork carried no tag line"
UNPLACED_MESSAGE = "fork(s) found with no recorded worktree; pass --session to match them"

TARGET_PREFIX = "Review target:"

#: How many lines of record 0's message are read. The tag sat on line 3 in the cloud sample; the CLI
#: may put a note before the target line (inferred from the bundle, not traced), so this leaves room.
HEAD_LINES = 12

#: The levels the skill parses, and the flags its description advertises. The `Review target` line
#: drops a level that parsed, and probably the flags too (not traced), so a caller's own argument
#: string is matched with any of these stripped from its front.
LEVELS = ("low", "medium", "high", "xhigh", "max")
VALUE_FLAGS = ("--max-findings",)
BARE_FLAGS = ("--comment", "--fix")

#: A tag line starts `<level> effort` -- measured at CLI 2.1.278, 2.1.301 (relayed) and 2.1.307.
TAG_SHAPE = re.compile(r"^[a-z]+ effort\b")

#: The glyphs the tag is known to carry, and their ASCII spellings under `--ascii`.
ASCII_SPELLINGS = {"\u2192": "->", "\u2264": "<=", "\u2265": ">="}

SESSION_ENV = "CLAUDE_CODE_SESSION_ID"


@dataclass
class Fork:
    transcript: Path
    agent_id: str
    session_id: str
    meta: dict = field(default_factory=dict)
    cwd: str = ""
    time: dt.datetime | None = None
    target: str = ""
    tag: str = ""
    placed_by: str = ""

    @property
    def worktree(self) -> str:
        value = self.meta.get("inheritedWorktreePath")
        return value if isinstance(value, str) else ""


def normalize_path(path: str, fold_case: bool | None = None) -> str:
    """Compare-ready spelling: forward slashes, no trailing slash, case-folded on Windows."""
    if fold_case is None:
        fold_case = os.name == "nt"
    text = re.sub(r"/+", "/", path.replace("\\", "/"))
    if len(text) > 1:
        text = text.rstrip("/")
    return text.casefold() if fold_case else text


def is_under(path: str, root: str) -> bool:
    """Both already normalized. Equal, or below `root` at a separator."""
    return path == root or path.startswith(root.rstrip("/") + "/")


def projects_roots(explicit: list[str] | None = None) -> list[Path]:
    """`--projects-dir` if given, else `$CLAUDE_CONFIG_DIR/projects`, else every `~/.claude*/projects`."""
    if explicit:
        return [Path(p) for p in explicit]
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if config:
        return [Path(config) / "projects"]
    try:
        candidates = sorted(Path.home().glob(".claude*"))
    except OSError:
        return []
    return [c / "projects" for c in candidates if c.is_dir()]


def parse_time(text: str, require_offset: bool = False) -> dt.datetime | None:
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
        if require_offset:
            return None
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


def read_record_zero(transcript: Path) -> tuple[dict | None, list[str]]:
    """Record 0 only, and of its message only the first HEAD_LINES lines. Never a later record."""
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        first = fh.readline()
    try:
        record = json.loads(first)
    except ValueError:
        return None, []
    if not isinstance(record, dict):
        return None, []
    return record, message_text(record).splitlines()[:HEAD_LINES]


def unquote(text: str) -> str:
    return text.strip().strip("`").strip()


def read_head(lines: list[str]) -> tuple[bool, str, str]:
    """(is a review fork, target args, tag) from the head of record 0's message."""
    target = None
    tag = ""
    for line in lines:
        if target is None and line.startswith(TARGET_PREFIX):
            target = unquote(line[len(TARGET_PREFIX) :])
        elif not tag and TAG_SHAPE.match(unquote(line)):
            tag = unquote(line)
    return target is not None or bool(tag), target or "", tag


def strip_invocation(text: str) -> str:
    """Drop the level and the flags the skill consumes from the front of an argument string."""
    words = text.split()
    while words:
        if words[0].casefold() in LEVELS or words[0] in BARE_FLAGS:
            words.pop(0)
        elif words[0] in VALUE_FLAGS:
            del words[:2]
        else:
            break
    return " ".join(words)


def target_matches(wanted: str, args: str) -> bool:
    """Substring match, whitespace-normalized and case-folded, after the invocation is stripped."""

    def squash(text: str) -> str:
        return " ".join(unquote(text).split()).casefold()

    have = squash(args)
    want = squash(wanted)
    return want in have or squash(strip_invocation(unquote(wanted))) in have


def fork_files(root: Path) -> list[Path]:
    """Every `agent-*.jsonl` under a `subagents` directory of a session, at any depth below it."""
    return sorted(root.glob("*/*/subagents/**/agent-*.jsonl"))


@dataclass
class Filters:
    worktree: str | None = None
    target: str | None = None
    session: str | None = None
    since: dt.datetime | None = None


@dataclass
class Scan:
    forks: list[Fork] = field(default_factory=list)
    unreadable_roots: list[Path] = field(default_factory=list)
    missing_roots: list[Path] = field(default_factory=list)
    unreadable_files: int = 0
    unplaced: int = 0


def place(fork: Fork, want: str | None, session_given: bool) -> bool | None:
    """True if the fork ran in `want`, False if elsewhere, None if it records nowhere to place it."""
    if want is None:
        fork.placed_by = "any worktree"
        return True
    if fork.worktree:
        fork.placed_by = "inheritedWorktreePath"
        return normalize_path(fork.worktree) == want
    if fork.cwd:
        fork.placed_by = "record 0 cwd (no inheritedWorktreePath)"
        return is_under(normalize_path(fork.cwd), want)
    if session_given:
        fork.placed_by = "session only (no worktree or cwd recorded)"
        return True
    return None


def scan(roots: list[Path], filters: Filters) -> Scan:
    result = Scan()
    want = normalize_path(filters.worktree) if filters.worktree else None
    for root in roots:
        if not root.is_dir():
            result.missing_roots.append(root)
            continue
        try:
            # The probe is the unreadable-root check: glob swallows a permission error and returns
            # nothing, which would read as "no fork" rather than "could not look".
            os.listdir(root)
            files = fork_files(root)
        except OSError:
            result.unreadable_roots.append(root)
            continue
        for transcript in files:
            parts = transcript.relative_to(root).parts
            session_id = parts[1] if len(parts) > 1 else ""
            if filters.session and session_id != filters.session:
                continue
            agent_id = transcript.name[len("agent-") : -len(".jsonl")]
            fork = Fork(transcript, agent_id, session_id, read_meta(transcript))
            try:
                record, head = read_record_zero(transcript)
            except OSError:
                result.unreadable_files += 1
                continue
            if record is None:
                result.unreadable_files += 1
                continue
            is_review, fork.target, fork.tag = read_head(head)
            if not is_review:
                continue
            cwd = record.get("cwd")
            fork.cwd = cwd if isinstance(cwd, str) else ""
            placed = place(fork, want, bool(filters.session))
            if placed is None:
                result.unplaced += 1
                continue
            if not placed:
                continue
            if filters.target and not target_matches(filters.target, fork.target):
                continue
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
        out.append(f"  tag: {spell(fork.tag, ascii_only) if fork.tag else 'NONE IN RECORD 0'}")
        out.append(f"  placed by: {fork.placed_by}")
        if verbose:
            meta = fork.meta
            out.append(f"  session: {fork.session_id}")
            out.append(f"  parentAgentId: {meta.get('parentAgentId', '(absent)')}")
            out.append(f"  spawnDepth: {meta.get('spawnDepth', '(absent)')}")
            out.append(f"  agentType: {meta.get('agentType', '(absent)')}")
            out.append(f"  worktree: {fork.worktree or '(absent)'}")
            out.append(f"  cwd: {fork.cwd or '(absent)'}")
            out.append(f"  transcript: {fork.transcript}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read the code-review skill's level tag from its reviewer fork's transcript.",
    )
    parser.add_argument(
        "--worktree",
        help="match forks that ran in this path (default: the current git toplevel)",
    )
    parser.add_argument(
        "--any-worktree", action="store_true", help="do not filter on the worktree at all"
    )
    parser.add_argument("--target", help="the arguments the skill was called with, or a substring")
    parser.add_argument(
        "--session", help=f"the session id the fork ran under (default: ${SESSION_ENV}, if set)"
    )
    parser.add_argument(
        "--any-session", action="store_true", help=f"do not default --session from ${SESSION_ENV}"
    )
    parser.add_argument(
        "--since", help="only forks whose record 0 is at or after this ISO time, with an offset"
    )
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
        since = parse_time(args.since, require_offset=True)
        if since is None:
            parser.error(
                f"--since needs an ISO 8601 time WITH an offset, such as 2026-10-22T09:00:00Z "
                f"or 2026-10-22T09:00:00-07:00: {args.since!r}"
            )

    worktree = None
    described = ["any worktree"]
    if not args.any_worktree:
        if args.worktree:
            # A drive-letter or rooted spelling is taken as given, so a Windows path names the same
            # worktree when this runs on Linux; only a relative one is resolved against the cwd.
            given = args.worktree
            absolute = re.match(r"^(?:[A-Za-z]:)?[\\/]", given)
            worktree = given if absolute else str(Path(given).resolve())
            described = ["worktree from --worktree"]
        else:
            worktree = git_toplevel()
            described = [
                "worktree = current git toplevel" if worktree else "any worktree (no git toplevel)"
            ]

    session = args.session
    session_from_env = False
    if not session and not args.any_session and os.environ.get(SESSION_ENV):
        session = os.environ[SESSION_ENV]
        session_from_env = True
    if session:
        described.append(f"session = {session}" + (f" from ${SESSION_ENV}" if session_from_env else ""))
    if args.target:
        # The value is not echoed: it is the caller's own words, and may carry what a QA line may not.
        described.append("--target given")
    if since:
        described.append(f"since {stamp(since)}")

    roots = projects_roots(args.projects_dir)
    result = scan(roots, Filters(worktree, args.target, session, since))
    print(f"matched {len(result.forks)} fork(s) ({'; '.join(described)})")

    for root in result.unreadable_roots:
        print(f"review_tag: could not read a projects root{f': {root}' if args.verbose else ''}",
              file=sys.stderr)
    if result.unreadable_files:
        print(f"review_tag: {result.unreadable_files} fork transcript(s) could not be read",
              file=sys.stderr)

    if not result.forks:
        readable = [r for r in roots if r not in result.missing_roots + result.unreadable_roots]
        if not readable:
            print(NO_ROOT_MESSAGE)
            return EXIT_NO_ROOT
        if result.unreadable_roots:
            print(PARTIAL_ROOT_MESSAGE)
            return EXIT_NO_ROOT
        if result.unplaced:
            print(f"{result.unplaced} {UNPLACED_MESSAGE}")
            return EXIT_UNPLACED
        print(NO_FORK_MESSAGE)
        if session_from_env:
            print(f"review_tag: the session filter came from ${SESSION_ENV}; "
                  "--any-session widens it", file=sys.stderr)
        return EXIT_NO_FORK

    total = len(result.forks)
    shown = result.forks[-1:] if args.latest else result.forks
    for line in render(shown, total, total - len(shown), args.ascii, args.verbose):
        print(line)

    if not result.forks[-1].tag:
        print(NO_TAG_MESSAGE)
        return EXIT_NO_TAG
    return EXIT_FOUND


if __name__ == "__main__":
    sys.exit(main())
