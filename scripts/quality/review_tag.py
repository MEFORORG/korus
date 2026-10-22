#!/usr/bin/env python3
"""Read the `code-review` skill's level tag out of its reviewer fork's transcript.

WHY THIS EXISTS. The `code-review` skill is built into the Claude Code CLI. It does not print its
level tag back to its caller, so a QA line could name the level a Builder PASSED and not prove which
level and shape RAN. `roles/BUILDER.md` section 4e records where the tag does land: near the top of
the PROMPT the skill feeds its reviewer fork, and that prompt is record 0 of the fork's transcript.

    <projects dir>/<project>/<session id>/subagents/agent-<id>.jsonl
    <projects dir>/<project>/<session id>/subagents/agent-<id>.meta.json

Record 0's user message opens with a `Review target: <args>` line, and the tag is the next line
that is not blank, inside backticks. Measured in one cloud session at CLI 2.1.307, the target was
itself in backticks, line 2 was blank and the tag was line 3. A Windows sample at 2.1.301 was relayed
as "line 2". A message that does not START with the target line is not a review fork, and only a
`<level> effort -> ...` pipeline counts as a tag. Both refusals fail closed: a miss, never a match.

WHERE THE FORK RAN. The meta file may carry `inheritedWorktreePath` (the relayed Windows sample,
Builder subagents at spawn depth 2). The cloud sample's meta did not; its record 0 carried `cwd`.
The tool uses the first of the two it finds and says which on the row. A fork with neither is
never placed by its session alone: every subagent Builder shares its Manager's session.

IT ANSWERS FOR EXACTLY ONE FORK, OR REFUSES. It exits 0 only when exactly one fork matches the
filters. More than one candidate refuses, in one session or several; so does any fork in scope it
could not read (transcript or meta), any directory it could not read -- a `~/.claude*` whose stat
fails among them -- and any fork it cannot place. It never picks the newest readable one.

A ROUND NONCE MAKES THE ONE MATCH THE CALLER'S OWN. Arguments alone cannot: Builders share the
standard ones, so a round that left no fork (the inline shape) could find another Builder's fork as
its one match. So a Builder puts a fresh nonce in its arguments right after the level --
`xhigh round-7f3a9c21e4 Review ...` -- and `--target` is REQUIRED, with the nonce in it: a target
without one is refused unless `--no-nonce`. With it, only the Builder's own fork can match, and an
inline, misplaced or unpersisted round exits 3, never 0. The nonce also places a fork that records
no worktree.

IT NEVER WIDENS ON ITS OWN. A `--target` holding only a level selects nothing and is refused. A
failed `git rev-parse` refuses rather than searching every worktree. A refusal prints no `tag:`
line. Widening takes an explicit flag.

`cwd` placement is EXACT. A fork whose `cwd` is below the worktree -- a harness worktree nested at
`.claude/worktrees/<name>` among them -- ran somewhere else.

WHAT IT PROVES, AND WHAT IT DOES NOT. The tag proves which prompt template the skill selected, not
that the fork obeyed it.

ARGUMENTS SPANNING LINES ARE REFUSED, NOT GUESSED AT. The target is the first line, and the tag is
the next line that is not blank. Where the first line leaves a backtick open, or the next line is no
tag and a later line is one, the arguments may span lines: the tool refuses (exit 13) rather than
read a line of them as the tag, or call the fork tagless. Keep the skill's arguments on one line.

IT IS READ-ONLY, AND IT READS AS LITTLE AS IT CAN. With a session filter, it walks only that
session's directory inside each project directory. Per fork it reads the meta file, then record 0 -- one line of the transcript --
and prints from that only the target and the tag line. No later record is read or printed. Path
columns are printed only under `--verbose`, because the leak gate forbids a user-home path in
published text and a QA line is published text.

NOT MEASURED, so it says so rather than guessing. The inline shape (`Agent tool unavailable ->
single-pass inline`) has no fork: its prompt lands in the caller's own transcript, which this tool
does not read. A miss therefore names that possibility instead of printing a blank.

    python scripts/quality/review_tag.py --target round-7f3a9c21e4 --since 2026-10-22T09:00:00Z
    python scripts/quality/review_tag.py --target round-7f3a9c21e4 --since ... --ascii --verbose

Exit codes. Each failure has its own, so a caller can tell them apart without parsing text:

    0  exactly one fork matched the filters, and it carried a tag
    2  usage error (argparse)
    3  no fork found; inline shape or unpersisted transcript possible
    4  no projects dir could be read; or a projects directory could not be read, whether or not a
       fork matched elsewhere
    5  exactly one fork matched, and it carried no tag line
    6  a fork in scope records no worktree, so it could be the run asked for
    7  ambiguous: more than one fork could be the run asked for
    8  no git toplevel here, and neither --worktree nor --any-worktree was given
    9  nothing selects a fork: no --target, a --target holding only a level or flags, or one with
       no round nonce (unless --no-nonce, whose answer is not attributable)
   10  a fork transcript in scope could not be read, so it could be the run asked for
   11  --no-nonce with a target that carries no nonce: exactly one fork matched, tag or none,
       but the answer is not attributable. A tag prints on a NOT-ATTRIBUTABLE line, never on a
       `tag:` line, so it cannot be pasted as a QA reading
   12  a fork carries the round's nonce, but it ran in another worktree; it is not "no fork"
   13  a fork in scope may have arguments spanning lines, so no line can be read as its tag
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

EXIT_FOUND = 0
EXIT_NO_FORK = 3
EXIT_NO_ROOT = 4
EXIT_NO_TAG = 5
EXIT_UNPLACED = 6
EXIT_AMBIGUOUS = 7
EXIT_NO_TOPLEVEL = 8
EXIT_NO_SELECTOR = 9
EXIT_UNREAD = 10
EXIT_NOT_ATTRIBUTABLE = 11
EXIT_ELSEWHERE = 12
EXIT_UNSPLIT = 13

#: Where --no-nonce prints the tag instead of on a `tag:` line.
NOT_ATTRIBUTABLE_PREFIX = "  NOT-ATTRIBUTABLE (--no-nonce, not a QA reading): "

# Every stdout line a Builder may quote is one of these or a `tag:` line. None carries the word the
# QA line may not; `tests/test_review_tag_reads_the_fork_it_was_asked_for.py` holds that.
NO_FORK_MESSAGE = "no fork found; inline shape or unpersisted transcript possible"
NO_ROOT_MESSAGE = "no projects dir could be read"
PARTIAL_ROOT_MESSAGE = (
    "a projects directory could not be read; a fork there could be the one asked for"
)
NO_TAG_MESSAGE = "the one matching fork carried no tag line"
NOT_ATTRIBUTABLE_MESSAGE = (
    "not attributable: the target carries no round nonce; never quote this; run again with the nonce"
)
ELSEWHERE_MESSAGE = (
    "fork(s) carry the round's nonce but ran in another worktree; pass that worktree with --worktree"
)
UNPLACED_MESSAGE = (
    "fork(s) in scope record no worktree, so any could be the one asked for;"
    " narrow with --since set before the round"
)
UNREAD_MESSAGE = (
    "fork(s) in scope could not be read, so any could be the one asked for;"
    " if a round is still running, run this again when it ends"
)
UNSPLIT_MESSAGE = (
    "fork(s) in scope may have arguments spanning lines, so no line can be read as the tag;"
    " keep the skill's arguments on one line"
)
NO_SELECTOR_MESSAGE = "--target is required; pass the round's nonce, round-<hex>"
NO_NONCE_MESSAGE = (
    "--target carries no round nonce (round- and 8 or more hex digits);"
    " --no-nonce allows that, and no QA line may use it"
)
NO_WORDS_MESSAGE = "--target holds only a level or flags; pass the words of your arguments"
AMBIGUOUS_MESSAGE = (
    "more than one fork could be the one asked for; narrow with --since set before the round,"
    " --target or --session"
)
NO_TOPLEVEL_MESSAGE = "no git toplevel here; run this from your worktree, or pass --worktree"

TARGET_PREFIX = "Review target:"

#: A round nonce: 8 or more hex digits, fresh each round, after `round-`, as a whole token. One
#: pattern both finds a nonce in --target and matches it in a fork's target, so the two cannot
#: disagree on where a token ends: `round-...22` never matches `round-...22-b`.
NONCE_SHAPE = re.compile(r"(?<![0-9A-Za-z-])round-[0-9a-f]{8,}(?![0-9A-Za-z-])", re.IGNORECASE)

#: The levels the skill parses, and the flags its description advertises. The `Review target` line
#: drops a level that parsed, and probably the flags too (not traced), so a level is stripped from
#: the front of an argument string, and a flag wherever it sits, `--max-findings=<n>` among them.
#: A value flag takes the next word only when that word is a value: prose naming the flag keeps
#: its next word, and so does a nonce.
FLAG_VALUE = re.compile(r"^(?:\d+|all|default)$", re.IGNORECASE)
LEVELS = ("low", "medium", "high", "xhigh", "max")
VALUE_FLAGS = ("--max-findings",)
BARE_FLAGS = ("--comment", "--fix")

#: A tag is a level, `effort`, then the arrow pipeline, in either spelling -- measured at CLI 2.1.278,
#: 2.1.301 (relayed) and 2.1.307. Any other `<word> effort` line is ordinary prose, not a tag.
TAG_SHAPE = re.compile(r"^(?:low|medium|high|xhigh|max) effort (?:\u2192|->) ")

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
    #: No tag after the target line, and the arguments may span lines.
    unsplit: bool = False

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
    roots = []
    for candidate in candidates:
        # Not is_dir(): it answers False when the stat fails, which dropped an unreadable
        # ~/.claude-X as if it did not exist, and a fork there could be the one asked for. A
        # candidate that cannot be stat'ed stays in, so scan() reads it as unreadable and refuses.
        try:
            mode = os.stat(candidate).st_mode
        except FileNotFoundError:
            continue
        except OSError:
            roots.append(candidate / "projects")
            continue
        if stat.S_ISDIR(mode):
            roots.append(candidate / "projects")
    return roots


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


def read_meta(transcript: Path) -> tuple[dict, bool]:
    """(meta, read). An ABSENT meta file is no meta. One that exists and cannot be read or parsed
    is unread: it may hold the `inheritedWorktreePath` that would place the fork elsewhere."""
    meta_path = transcript.with_name(transcript.name[: -len(".jsonl")] + ".meta.json")
    try:
        with meta_path.open(encoding="utf-8") as fh:
            value = json.load(fh)
    except FileNotFoundError:
        return {}, True
    except (OSError, ValueError):
        return {}, False
    return (value, True) if isinstance(value, dict) else ({}, False)


def read_record_zero(transcript: Path) -> tuple[dict | None, list[str]]:
    """Record 0 only, and its message's lines. Never a later record."""
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        first = fh.readline()
    try:
        record = json.loads(first)
    except ValueError:
        return None, []
    if not isinstance(record, dict):
        return None, []
    return record, message_text(record).splitlines()


def unquote(text: str) -> str:
    return text.strip().strip("`").strip()


def is_tag(line: str) -> bool:
    return bool(TAG_SHAPE.match(unquote(line)))


def read_head(lines: list[str]) -> tuple[bool, str, str, bool]:
    """(is a review fork, target args, tag, unsplit) from record 0's message.

    A review fork's message STARTS with the target line; the tag is the next non-blank line, and
    only if it has the tag's shape. The arguments may span lines where the target line leaves a
    backtick open, or where that next line is no tag and a later line is one: that is `unsplit`, a
    refusal, never a tagless fork. Only the target line and the tag are kept; the rest is tested.
    """
    if not lines or not lines[0].startswith(TARGET_PREFIX):
        return False, "", "", False
    first = lines[0][len(TARGET_PREFIX) :].strip()
    target = unquote(first)
    # An odd count of backticks leaves one open, so the next line is still the arguments, whatever
    # it looks like: `scripts/x.py` round-... closes its own pair and opens nothing.
    opened = first.count("`") % 2 == 1
    rest = lines[1:]
    for index, line in enumerate(rest):
        if line.strip():
            if opened:
                return True, target, "", True
            if is_tag(line):
                return True, target, unquote(line), False
            return True, target, "", any(is_tag(later) for later in rest[index + 1 :])
    return True, target, "", opened


def strip_invocation(text: str) -> str:
    """Drop a level from the front of an argument string, and the skill's flags wherever they sit."""
    words = text.split()
    kept: list[str] = []
    leading = True
    index = 0
    while index < len(words):
        word = words[index]
        if word in BARE_FLAGS or any(word.startswith(flag + "=") for flag in VALUE_FLAGS):
            index += 1
        elif word in VALUE_FLAGS:
            follows = words[index + 1] if index + 1 < len(words) else ""
            index += 2 if FLAG_VALUE.match(follows) else 1
        elif leading and word.casefold() in LEVELS:
            index += 1
        else:
            leading = False
            kept.append(word)
            index += 1
    return " ".join(kept)


def squash(text: str) -> str:
    return " ".join(unquote(text).split()).casefold()


def target_words(wanted: str | None) -> str:
    """What is left of `--target` once the level and the skill's flags are stripped."""
    return squash(strip_invocation(unquote(wanted))) if wanted else ""


def target_matches(wanted: str, args: str) -> bool:
    """Substring match, whitespace-normalized and case-folded, after the invocation is stripped.

    A level alone leaves no words, and `main` refuses that before any scan. The guard here stays,
    because an empty string is a substring of everything: that is how a bare level once matched
    every fork.
    """
    # The fork's own target is stripped the same way, so a flag the skill kept matches one it dropped.
    have = squash(strip_invocation(unquote(args)))
    words = target_words(wanted)
    if not words:
        return have == ""
    # A nonce matches only as a whole token: as a substring, round-7f3a9c21 would match a fork
    # whose nonce is round-7f3a9c21e4.
    # And only as the fork's OWN nonce: the first one in its target line, where the skill leaves it
    # after dropping the level. A later mention of an earlier round's nonce is not that round.
    if NONCE_SHAPE.search(wanted) and not own_nonce_matches(wanted, args):
        return False
    return squash(wanted) in have or words in have


def own_nonce_matches(wanted: str, args: str) -> bool:
    """The first nonce in `wanted` is the fork's own: the first nonce in its target line."""
    wanted_nonces = NONCE_SHAPE.findall(wanted)
    own = NONCE_SHAPE.findall(args)
    return bool(wanted_nonces and own and own[0].casefold() == wanted_nonces[0].casefold())


def fork_files(root: Path, unreadable: list[Path], session: str | None = None) -> list[Path]:
    """Every `agent-*.jsonl` under a `subagents` directory of a session, at any depth below it.

    A walk, not a glob: glob skips a directory it cannot read without a word, and a fork in that
    directory could be the one asked for. Every directory that could not be read is recorded.
    With a session filter, only that session's directory is walked: another session's forks are
    out of scope, and so is a directory of theirs that could not be read.
    """

    def failed(err: OSError) -> None:
        unreadable.append(Path(err.filename) if err.filename else root)

    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=failed):
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth == 1 and session:
            dirnames[:] = [d for d in dirnames if d == session]
        if depth == 2:
            # <project>/<session>: only its subagents directory can hold a fork.
            dirnames[:] = [d for d in dirnames if d == "subagents"]
        if depth >= 3:
            found.extend(
                Path(dirpath) / f
                for f in filenames
                if f.startswith("agent-") and f.endswith(".jsonl")
            )
    return sorted(found)


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
    elsewhere: int = 0
    unsplit: int = 0


def place(fork: Fork, want: str | None) -> bool | None:
    """True if the fork ran in `want`, False if elsewhere, None if it records nowhere to place it.

    A session never places a fork: every subagent Builder shares its Manager's session.
    """
    if want is None:
        fork.placed_by = "any worktree"
        return True
    if fork.worktree:
        fork.placed_by = "inheritedWorktreePath"
        return normalize_path(fork.worktree) == want
    if fork.cwd:
        fork.placed_by = "record 0 cwd (no inheritedWorktreePath)"
        return normalize_path(fork.cwd) == want
    return None


def scan(roots: list[Path], filters: Filters) -> Scan:
    result = Scan()
    want = normalize_path(filters.worktree) if filters.worktree else None
    # With a nonce in the target, every fork past the target filter carries the caller's own.
    nonced = bool(filters.target and NONCE_SHAPE.search(filters.target))
    for root in roots:
        try:
            # The probe is the unreadable-root check, and it comes before any is_dir: on 3.13 a
            # denied stat raises from is_dir, and on 3.14 is_dir answers False, filing the root
            # as missing when it is only unreadable.
            os.listdir(root)
        except (FileNotFoundError, NotADirectoryError):
            result.missing_roots.append(root)
            continue
        except OSError:
            result.unreadable_roots.append(root)
            continue
        files = fork_files(root, result.unreadable_roots, filters.session)
        for transcript in files:
            parts = transcript.relative_to(root).parts
            # The walk already kept to the session filter's directory.
            session_id = parts[1] if len(parts) > 1 else ""
            agent_id = transcript.name[len("agent-") : -len(".jsonl")]
            meta, meta_read = read_meta(transcript)
            fork = Fork(transcript, agent_id, session_id, meta)
            try:
                record, head = read_record_zero(transcript)
            except OSError:
                record, head = None, []
            if record is None or not meta_read:
                # Unread is not absent: a fork still being written could be the very run asked
                # for. Only what proves it is elsewhere rules it out -- a recorded worktree that
                # differs, or a file last written before --since.
                if want is not None and fork.worktree and normalize_path(fork.worktree) != want:
                    continue
                if filters.since:
                    try:
                        written = dt.datetime.fromtimestamp(
                            transcript.stat().st_mtime, tz=dt.timezone.utc
                        )
                    except OSError:
                        written = None
                    if written is not None and written < filters.since:
                        continue
                result.unreadable_files += 1
                continue
            is_review, fork.target, fork.tag, fork.unsplit = read_head(head)
            if not is_review:
                continue
            # The caller's own filters run first, so a fork they exclude is never counted unplaced.
            if filters.target and not target_matches(filters.target, fork.target):
                # An unsplit fork's arguments are known only in part, so its own nonce alone keeps it.
                if not (fork.unsplit and own_nonce_matches(filters.target, fork.target)):
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
            cwd = record.get("cwd")
            fork.cwd = cwd if isinstance(cwd, str) else ""
            placed = place(fork, want)
            if placed is None and nonced:
                # The target filter already ran, so this fork carries the caller's own nonce: the
                # nonce places it, where a worktree cannot.
                fork.placed_by = "the round nonce (no worktree or cwd recorded)"
                placed = True
            if placed is None:
                result.unplaced += 1
                continue
            if placed and fork.unsplit:
                result.unsplit += 1
            elif placed:
                result.forks.append(fork)
            elif nonced:
                # It carries the caller's nonce and ran elsewhere: found, not absent.
                result.elsewhere += 1
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


def render(
    forks: list[Fork], ascii_only: bool, verbose: bool, attributable: bool = True
) -> list[str]:
    out: list[str] = []
    for fork in forks:
        out.append(f"fork | {stamp(fork.time)} | agent {fork.agent_id}")
        out.append(f"  target: {spell(fork.target, ascii_only) or '(none)'}")
        # No placeholder on a `tag:` line: what follows `tag:` is quoted as the tag.
        if fork.tag:
            # Without a nonce, another Builder's fork with the same arguments can be the one match,
            # so the tag never lands on a `tag:` line a QA line would quote.
            label = "  tag: " if attributable else NOT_ATTRIBUTABLE_PREFIX
            out.append(f"{label}{spell(fork.tag, ascii_only)}")
        else:
            out.append("  no tag line in record 0")
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
    parser.add_argument(
        "--no-nonce",
        action="store_true",
        help="allow a --target with no round nonce; the answer is then not attributable",
    )
    parser.add_argument(
        "--target", help="REQUIRED: the round's nonce (round-<hex>), or the arguments that carry it"
    )
    parser.add_argument(
        "--session", help=f"the session id the fork ran under (default: ${SESSION_ENV}, if set)"
    )
    parser.add_argument(
        "--any-session", action="store_true", help=f"do not default --session from ${SESSION_ENV}"
    )
    parser.add_argument(
        "--since", help="only forks whose record 0 is at or after this ISO time, with an offset"
    )
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
    described = ["any worktree, by --any-worktree"]
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
            if worktree is None:
                # Refuse rather than widen: an unfiltered search would quote another worktree's tag.
                print(NO_TOPLEVEL_MESSAGE)
                return EXIT_NO_TOPLEVEL
            described = ["worktree = current git toplevel"]

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
    # The nonce, not the flag, decides: --no-nonce beside a real nonce changes nothing.
    attributable = bool(args.target and NONCE_SHAPE.search(args.target))
    if not attributable and args.no_nonce:
        described.append("--no-nonce: NOT ATTRIBUTABLE")

    if args.target and not target_words(args.target):
        print(NO_WORDS_MESSAGE)
        return EXIT_NO_SELECTOR
    if not args.target:
        # Required: without the round's nonce, another Builder's fork with the same arguments can be
        # the one match while the caller's own round left no fork at all.
        print(NO_SELECTOR_MESSAGE)
        return EXIT_NO_SELECTOR
    if not NONCE_SHAPE.search(args.target) and not args.no_nonce:
        # Refused, not warned: without a nonce a peer's fork with the same arguments can be the one
        # match. A malformed nonce -- `round-` alone, too few digits -- is refused the same way.
        print(NO_NONCE_MESSAGE)
        return EXIT_NO_SELECTOR

    roots = projects_roots(args.projects_dir)
    result = scan(roots, Filters(worktree, args.target, session, since))
    print(f"matched {len(result.forks)} fork(s) ({'; '.join(described)})")

    if args.verbose:
        for root in result.unreadable_roots:
            print(f"review_tag: could not read {root}", file=sys.stderr)

    # Every refusal comes BEFORE any row is rendered, so a refused run prints no quotable tag. Each
    # one fires whether or not a readable fork also matched: whatever could not be read, placed or
    # told apart could be the run asked for, and the newest readable fork is not a stand-in for it.
    readable = [r for r in roots if r not in result.missing_roots + result.unreadable_roots]
    if not readable:
        print(NO_ROOT_MESSAGE)
        return EXIT_NO_ROOT
    if result.unreadable_roots:
        print(PARTIAL_ROOT_MESSAGE)
        return EXIT_NO_ROOT
    if result.unreadable_files:
        print(f"{result.unreadable_files} {UNREAD_MESSAGE}")
        return EXIT_UNREAD
    if result.unplaced:
        print(f"{result.unplaced} {UNPLACED_MESSAGE}")
        return EXIT_UNPLACED
    if result.unsplit:
        print(f"{result.unsplit} {UNSPLIT_MESSAGE}")
        return EXIT_UNSPLIT
    if not result.forks and result.elsewhere:
        print(f"{result.elsewhere} {ELSEWHERE_MESSAGE}")
        return EXIT_ELSEWHERE
    if not result.forks:
        print(NO_FORK_MESSAGE)
        if session_from_env:
            print(f"review_tag: the session filter came from ${SESSION_ENV}; "
                  "--any-session widens it", file=sys.stderr)
        return EXIT_NO_FORK
    if len(result.forks) > 1:
        print(AMBIGUOUS_MESSAGE)
        for fork in result.forks:
            print(f"candidate | {stamp(fork.time)} | agent {fork.agent_id} | session {fork.session_id}")
        return EXIT_AMBIGUOUS

    for line in render(result.forks, args.ascii, args.verbose, attributable):
        print(line)

    if not attributable:
        # Tag or none: a no-nonce answer is never a reading, so it never takes exit 0 or 5.
        print(NOT_ATTRIBUTABLE_MESSAGE)
        return EXIT_NOT_ATTRIBUTABLE
    if not result.forks[0].tag:
        print(NO_TAG_MESSAGE)
        return EXIT_NO_TAG
    return EXIT_FOUND


if __name__ == "__main__":
    sys.exit(main())
