#!/usr/bin/env python3
"""Read the `code-review` skill's level tag out of its reviewer fork's transcript.

WHY THIS EXISTS. The `code-review` skill is built into the Claude Code CLI. It does not print its
level tag back to its caller, so a QA line could name the level a Builder PASSED and not prove which
level and shape RAN. `roles/BUILDER.md` section 4e records where the tag does land: near the top of
the PROMPT the skill feeds its reviewer fork, and that prompt is record 0 of the fork's transcript.

    <projects dir>/<project>/<session id>/subagents/agent-<id>.jsonl
    <projects dir>/<project>/<session id>/subagents/agent-<id>.meta.json

Record 0's user message opens with a `Review target: <args>` line, or with the skill's notices and
then that line, and the tag is the next line that is not blank, inside backticks. Measured in one
cloud session at CLI 2.1.307, the target was itself in backticks, line 2 was blank and the tag was
line 3. A Windows sample at 2.1.301 was relayed as "line 2". A message that does not START with the
target line, past the notices below, is never read as a review fork: it is no fork, or a refusal
(exit 14). Only a `<level> effort -> ...` pipeline counts as a tag. Both fail closed: a miss or a
refusal, never a match.

NOTICES MAY COME FIRST. At CLI 2.1.309 the skill builds its prompt as notices, then the target line:
a remembered or ignored `--max-findings`, an unrecognized or last-used level, an ultra fallback, a
typed `--post`. Each is one line in parentheses, then one blank line, and there are at most three.
A notice is skipped only where the WHOLE line is one of the sentences that binary writes
(`NOTICE_TEMPLATES`), so a helper's brief that merely opens with the same words is not.

A target line below anything else, with a tag-shaped line somewhere after it, is DISPLACED: the
tool refuses (exit 14) rather than call the fork absent, which once let a real tag read as exit 3.
A notice-shaped line the tool does not know -- one line in parentheses, one blank line, then a
target line and a tag after it -- is most likely a notice a later CLI added or reworded. It refuses
with its own exit (15). Under `--verbose` its opening words go to stderr, so the sentence can be measured and
added; they are record 0's own words, so they sit behind the flag with the paths.

A brief that pastes a whole head is displaced, or below an unknown notice. In scope it refuses,
whatever fork reads beside it: nothing in record 0 tells the skill's own prompt from a brief that
pasted it, so the readable one may be the brief. With nothing read here, a refused head elsewhere
refuses rather than exit 12, unless a head elsewhere reads with its tag.

A HEAD ELSEWHERE CONTESTS A FORK HERE (exit 16). Beside a fork that reads here with its tag, a
head in another worktree carrying the round's nonce and a tag-shaped line -- refused or readable,
before `--since` or after it -- refuses the reading. A fork in another worktree whose record 0
cannot be read refuses too, as unread (exit 10), when its first 64 KiB hold the round's nonce. A
tagless fork here exits 5, unless such an unread fork sits elsewhere: then 10. The same argument
holds across worktrees: the head elsewhere may be the round's real fork, under a notice this tool
does not know or displaced, and the readable one here a helper that pasted it. It once exited 0
there and quoted the helper's tag, a `low` one under an `xhigh` round among them. Record times do
not tell them apart: a helper's head can be written before the round, from the caller's own
arguments and a documented tag. A fresh round clears it: a pasted head carries the OLD round's
nonce, and a nonce matches only as the fork's own. A rerun of this tool does not, and a head
pasted elsewhere later blocks a re-check of the old round for good: a refusal, never a wrong tag.

ONE FILE IS ONE FORK. A projects directory reached twice -- two roots naming one directory, or a
junction or link inside one -- once listed the same fork twice and refused it as ambiguous. A file
seen already, by its device, inode, size and write time, is skipped. A file still being written
between two reaches can read as two forks, exit 7, which a later run clears.

A `finderBudgetHint` line (`This diff is about N lines. Spawn about ...`) may sit between the target
line and the tag, at 2.1.309 with claude-sonnet-5 at high, xhigh or max and a bare git range as the
target. It is skipped, once, where the whole line is that sentence.

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

WITH A NONCE, `--since` DROPS NOTHING THE NONCE KEEPS. A fork carrying the round's own nonce is
that round's whatever its time, so an older real fork cannot be cut away from a newer helper.
An unreadable file whose first 64 KiB hold the nonce is kept the same way, here or elsewhere.
`--since` still bounds an unreadable file whose first 64 KiB lack it, and a `--no-nonce` search.

IT NEVER WIDENS ON ITS OWN. A `--target` holding only a level selects nothing and is refused. A
failed `git rev-parse` refuses rather than searching every worktree. A refusal prints no `tag:`
line. Widening takes an explicit flag.

`cwd` placement is EXACT. A fork whose `cwd` is below the worktree -- a harness worktree nested at
`.claude/worktrees/<name>` among them -- ran somewhere else.

WHAT IT PROVES, AND WHAT IT DOES NOT. The tag proves which prompt template the skill selected, not
that the fork obeyed it.

ARGUMENTS SPANNING LINES ARE REFUSED, NOT GUESSED AT. The target is the first line past the
notices, and the tag is the next line that is not blank. Where the target line leaves a backtick
open, or the next line is no tag and a later line is one, the arguments may span lines: the tool
refuses (exit 13) rather than read a line of them as the tag, or call the fork tagless. Keep the
skill's arguments on one line. Two more shapes refuse the same way. A second tag-shaped line
anywhere after the target line: every tag in CLI 2.1.309 opens its template, one per prompt, so one
of the two came from the arguments. And a target line holding no words, or a level or flags alone,
whose arguments start on the next line. Where the arguments span lines, the fork's own nonce is the
first one on any of them, up to the last tag-shaped line, so the round refuses rather than reading
as no fork at all. That holds for a displaced target line too: each is read by these same rules.

IT IS READ-ONLY, AND IT READS AS LITTLE AS IT CAN. With a session filter, it walks only that
session's directory inside each project directory. Per fork it reads the meta file, then record 0 -- one line of the transcript --
and prints from that only the target and the tag line, and under `--verbose` an unknown notice's
opening words. No later record is read or printed. Path
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
   14  a fork in scope carries its target line below text that is not the skill's notices
   15  a fork in scope carries its target line and tag below a notice-shaped line no measured CLI
       writes; --verbose prints its opening words on stderr
   16  a fork here reads with its tag, but a head in another worktree carries the round's nonce
       too, so either could be the run asked for; a fresh round clears it
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
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
EXIT_DISPLACED = 14
EXIT_UNKNOWN_NOTICE = 15
EXIT_CONTESTED = 16

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
UNREAD_ELSEWHERE_MESSAGE = (
    "fork(s) in another worktree carry this round's nonce and could not be read, so any could be"
    " the one asked for beside the fork here"
)
UNSPLIT_MESSAGE = (
    "fork(s) in scope may have arguments spanning lines, so no line can be read as the tag;"
    " keep the skill's arguments on one line, with no tag-shaped line in them"
)
DISPLACED_MESSAGE = (
    "fork(s) in scope carry the target line below an opening that is not the skill's notices,"
    " so no line can be read as the tag"
)
UNKNOWN_NOTICE_MESSAGE = (
    "fork(s) in scope carry a notice-shaped line above the target line that no measured CLI writes;"
    " --verbose prints its opening words"
)
CONTESTED_MESSAGE = (
    "head(s) in another worktree carry the round's nonce beside the fork here, so either could be"
    " the one asked for; run the round again with a fresh nonce"
)
NO_SELECTOR_MESSAGE = "--target is required; pass the round's nonce, round-<hex>"
NO_NONCE_MESSAGE = (
    "--target carries no round nonce (round- and 8 or more hex digits);"
    " --no-nonce allows that, and no QA line may use it"
)
NO_WORDS_MESSAGE = "--target holds only a level or flags; pass the words of your arguments"
AMBIGUOUS_MESSAGE = (
    "more than one fork could be the one asked for; with a round nonce, two forks carry it:"
    " a reused nonce, a head pasted in this worktree, or one file read twice while being"
    " written, and a later run clears only the last; without one, narrow with --since set"
    " before the round, --target or --session"
)
NO_TOPLEVEL_MESSAGE = "no git toplevel here; run this from your worktree, or pass --worktree"

TARGET_PREFIX = "Review target:"

#: The most notice paragraphs the skill puts above the target line, measured at CLI 2.1.309: two
#: from its level and `--post` notices, one from its `--max-findings` notice.
NOTICE_LIMIT = 3

#: The sentences the skill writes above the target line, read from the prompt builder of CLI 2.1.309
#: (`roles/BUILDER.md` 4e names the commands). A whole line must match one, so prose that merely
#: opens with a notice's words is not skipped. `{L}` is a level, `{N}` a count, `{T}` free text.
_DASH = "\u2014"
_LEVEL_TELL = (
    " Open your report with one short line telling the user this, and that typing a level (for"
    " example `/code-review high`) changes it; that opening line reaches them with the findings.)",
    " Tell the user this in one short line as you begin, including that typing a level (for example"
    " `/code-review high`) changes it.)",
)
_FINDINGS_TELL = (
    " Open your report with one short line telling the user this{OPT_DEFAULT_AND}; that opening"
    " line reaches them with the findings.)",
    " Tell the user this in one short line as you begin{OPT_DEFAULT_INCLUDING}.)",
)
_FINDINGS_BODIES = (
    "This review reports at most {N} findings, so the limit is {N} here.",
    "`--max-findings` does not change this review: low effort here has no maximum.",
    "The user set `--max-findings {T}` last time. This review reports at most {N} findings, so the"
    " limit is {N} here.",
    "Reporting every finding, as the user chose last time with `--max-findings all`.",
    "Reporting up to {N} {FINDING}, the limit the user set last time with `--max-findings`.",
)
_IGNORED = (
    "`--max-findings` was ignored: type a whole number above zero, `all`, or `default` after it."
)
_UNRECOGNIZED = 'Ignoring unrecognized effort "{T}"; valid: {T}. Using {L}{OPT_LAST}.'
_LAST_USED = (
    f"No effort level given {_DASH} reusing {{L}}, the level the user typed last time{{OPT_RUN}}."
)
NOTICE_TEMPLATES = (
    "(Running a local {L}-effort review and applying its findings.)",
    "(ultra (cloud review) {T} Falling back to a local {L}-effort review.)",
    f"(Claude can't launch the cloud review directly {_DASH} type `/code-review ultra --fix` to"
    " review in the cloud and apply the findings locally when it completes. Running a local {L}-effort"
    " review and applying its findings for now.)",
    f"(Claude can't launch the cloud review directly {_DASH} type `/code-review ultra` to run it."
    " Falling back to a local {L}-effort review for now.)",
    f"(Claude can't launch the cloud review directly {_DASH} the user can run `claude ultrareview`"
    " from a terminal to start it. Falling back to a local {L}-effort review for now.)",
    "(" + _UNRECOGNIZED + ")",
    *("(" + body + tell for body in (_UNRECOGNIZED, _LAST_USED) for tell in _LEVEL_TELL),
    "(The typed `--post` applies only to the `/code-review ultra` cloud review and was ignored"
    f" {_DASH} {{T}}. Tell the user this in one short line.)",
    *(
        "(" + ignored + body + tell
        for ignored in ("", _IGNORED + " ")
        for body in _FINDINGS_BODIES
        for tell in _FINDINGS_TELL
    ),
    *("(" + _IGNORED + "{OPT_USUAL}" + tell for tell in _FINDINGS_TELL),
)
_FIELDS = {
    "{L}": "(?:low|medium|high|xhigh|max)",
    "{N}": "[0-9]+",
    "{T}": ".+?",
    "{FINDING}": "findings?",
    "{OPT_LAST}": "(?:, the level the user typed last time)?",
    "{OPT_RUN}": "(?:; running at (?:low|medium|high|xhigh|max) here)?",
    "{OPT_USUAL}": "(?: Using the usual limit\\.)?",
    "{OPT_DEFAULT_AND}": (
        "(?:, and that passing `--max-findings default` goes back to the usual limit)?"
    ),
    "{OPT_DEFAULT_INCLUDING}": (
        "(?:, including that passing `--max-findings default` goes back to the usual limit)?"
    ),
}


def notice_pattern(template: str) -> re.Pattern[str]:
    """One whole notice line: the template's text literally, each `{FIELD}` as its pattern."""
    parts = re.split("(" + "|".join(re.escape(f) for f in _FIELDS) + ")", template)
    return re.compile("".join(_FIELDS.get(part, re.escape(part)) for part in parts))


#: Every notice sentence as one alternation, so a line is matched in one pass.
NOTICE_SHAPE = re.compile(
    "|".join(f"(?:{notice_pattern(t).pattern})" for t in NOTICE_TEMPLATES)
)

#: The finder-budget line some model cells add between the target line and the tag, at 2.1.309.
BUDGET_HINT = notice_pattern(
    f"This diff is about {{N}} lines. Spawn about {{N}} finder subagents (min 2, max 8) {_DASH}"
    " scale your investigation depth to the diff size rather than using a fixed large fleet."
)

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


class Refusal(enum.Enum):
    """Why a fork in scope cannot be read: one row each, its exit and its message, in the order
    `main` checks them. A misspelt member is an AttributeError, never a fork read as readable."""

    #: The arguments may span lines, or carry a tag-shaped line: refused, never read as tagless.
    UNSPLIT = (EXIT_UNSPLIT, UNSPLIT_MESSAGE)
    #: The target line sits below a notice-shaped line no measured CLI writes.
    UNKNOWN_NOTICE = (EXIT_UNKNOWN_NOTICE, UNKNOWN_NOTICE_MESSAGE)
    #: A target line sits below an opening that is not the skill's notices.
    DISPLACED = (EXIT_DISPLACED, DISPLACED_MESSAGE)

    def __init__(self, exit_code: int, message: str) -> None:
        self.exit = exit_code
        self.message = message


#: The refusals a brief that pasted the round's head produces.
BRIEF_REFUSALS = (Refusal.DISPLACED, Refusal.UNKNOWN_NOTICE)


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
    #: Why the fork cannot be read, if it cannot.
    refusal: Refusal | None = None
    #: For an unknown notice, its opening words, printed on stderr.
    notice: str = ""
    #: The first nonce in the fork's arguments: the target line's, or for arguments that may span
    #: lines, the first on any of them. Matched, never printed.
    own_nonce: str = ""
    #: Any tag-shaped line in record 0. Only such a head elsewhere contests a fork here.
    tag_shaped: bool = False

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


def is_notice(line: str) -> bool:
    """One of the measured notice sentences, the whole line."""
    return bool(NOTICE_SHAPE.fullmatch(line))


def is_notice_shaped(line: str) -> bool:
    """One line in parentheses: a notice's shape, whether or not its words are known."""
    return len(line) > 2 and line.startswith("(") and line.endswith(")")


def target_index(lines: list[str]) -> tuple[int | None, list[str]]:
    """Where the target line sits past the notices, and the notice lines no measured CLI writes.

    Each notice is one line in parentheses followed by exactly one blank line, and there are at most
    NOTICE_LIMIT. Anything else above a target line is not skipped: the index is then None.
    """
    index = 0
    unknown: list[str] = []
    for _ in range(NOTICE_LIMIT + 1):
        if index < len(lines) and lines[index].startswith(TARGET_PREFIX):
            return index, unknown
        if index + 1 >= len(lines) or not is_notice_shaped(lines[index]) or lines[index + 1] != "":
            return None, []
        if not is_notice(lines[index]):
            unknown.append(lines[index])
        index += 2
    return None, []


def opening_words(line: str, count: int = 6) -> str:
    """The first words of a line, enough to find its sentence in a CLI binary."""
    words = line.split()
    return " ".join(words[:count]) + (" ..." if len(words) > count else "")


@dataclass
class Head:
    """What record 0's message says about the fork: read, refused, or not a review fork."""

    review: bool = False
    target: str = ""
    tag: str = ""
    refusal: Refusal | None = None
    #: The first nonce in the arguments: the target line's, or for arguments that may span lines,
    #: the first on any of them. Matched, never printed.
    own_nonce: str = ""
    #: For a displaced head, each target line with a tag after it, read as if it opened the message.
    candidates: list["Head"] = field(default_factory=list)
    #: For an unknown notice, its opening words.
    notice: str = ""


def first_nonce(text: str) -> str:
    found = NONCE_SHAPE.search(text)
    return found.group(0) if found else ""


def displaced_heads(lines: list[str]) -> list[Head]:
    """Each target line, indented or quoted too, with a tag-shaped line after it, read from there.

    A subagent brief that quotes a target line and no tag is not a skill prompt, and is not kept.
    Each is read by the same rules as a target line that opens the message, so arguments spanning
    lines carry their own nonce here too. Most non-fork transcripts carry no target line at all, so
    they are ruled out before any copy, and the tag-shaped lines are found once.
    """
    if not any(TARGET_PREFIX in line for line in lines):
        return []
    bare = [line.lstrip(" \t>") for line in lines]
    last_tag = max((index for index, line in enumerate(bare) if is_tag(line)), default=-1)
    return [
        read_target(bare, index)
        for index, line in enumerate(bare)
        if index < last_tag and line.startswith(TARGET_PREFIX)
    ]


def read_head(lines: list[str]) -> Head:
    """What record 0's message says: a review fork's target and tag, a refusal, or no fork.

    A review fork's message STARTS with the target line, or with the skill's notices and then the
    target line. The tag is the next non-blank line, and only if it has the tag's shape; one
    finder-budget line between the target line and the tag is skipped. The fork is `unsplit` -- a
    refusal, never a tagless fork or a quoted tag -- where the target line leaves a backtick open;
    where the next non-blank line is no tag and either a later line is one or the target line holds
    no words; or where a second tag-shaped line follows the tag.

    Past a notice-shaped line no measured CLI writes, a target line with a tag after it, unsplit or
    not, is `unknown notice`, a refusal. With no tag after it, the head is read as below.

    A target line below anything else, with a tag after it, is `displaced`, also a refusal: a real
    fork with a tag once read as no fork that way. Only the target line and the tag are kept; the
    rest is tested.

    The own nonce is the first one in the arguments: the target line, and for an unsplit fork every
    line after it up to the LAST tag-shaped one, since a tag-shaped line above that may be theirs.
    It is matched, never printed.
    """
    start, unknown = target_index(lines)
    if start is not None:
        found = read_target(lines, start)
        if not unknown:
            return found
        if found.tag or any(is_tag(line) for line in lines[start + 1 :]):
            # A head below a notice no measured CLI writes, with a tag after its target line: most
            # likely a new notice. Unsplit arguments under it refuse here too, never as displaced.
            return Head(
                True,
                found.target,
                refusal=Refusal.UNKNOWN_NOTICE,
                own_nonce=found.own_nonce,
                notice=opening_words(unknown[0]),
                # A later target line may be the round's own, as below a displaced opening.
                candidates=displaced_heads(lines),
            )
    candidates = displaced_heads(lines)
    if not candidates:
        return Head()
    first = candidates[0]
    return Head(
        True,
        first.target,
        refusal=Refusal.DISPLACED,
        own_nonce=first.own_nonce,
        candidates=candidates,
    )


def read_target(lines: list[str], start: int) -> Head:
    """The target line at `start` and the lines below it, read as read_head describes."""
    first = lines[start][len(TARGET_PREFIX) :].strip()
    target = unquote(first)
    # An odd count of backticks leaves one open, so the next line is still the arguments, whatever
    # it looks like: `scripts/x.py` round-... closes its own pair and opens nothing. A line the
    # skill wrapped whole, `...`, is closed whatever it holds: one literal backtick in the
    # arguments made the count odd, and a one-line target refused as exit 13.
    wrapped = len(first) > 1 and first.startswith("`") and first.endswith("`")
    opened = first.count("`") % 2 == 1 and not wrapped
    rest = lines[start + 1 :]
    tags = [index for index, line in enumerate(rest) if is_tag(line)]
    tag, unsplit = "", opened
    filled = (index for index, line in enumerate(rest) if line.strip())
    following = next(filled, None)
    if following is not None and not opened and BUDGET_HINT.fullmatch(rest[following]):
        # The finder-budget line, once: the tag follows it.
        following = next(filled, None)
    if following is not None and not opened:
        if tags and tags[0] == following:
            # Each template opens with its one tag, so with two tag-shaped lines one came from
            # the arguments, and either could be the line the skill wrote.
            unsplit = len(tags) > 1
            tag = "" if unsplit else unquote(rest[following])
        else:
            # A target line with no words, a level or flags alone among them, puts the
            # arguments on the lines below it.
            unsplit = not target_words(target) or any(index > following for index in tags)
    args = [first] + (rest[: tags[-1]] if tags else rest) if unsplit else [first]
    return Head(
        True,
        target,
        tag,
        refusal=Refusal.UNSPLIT if unsplit else None,
        own_nonce=first_nonce("\n".join(args)),
    )


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
    #: The forks each refusal holds.
    refused: dict[Refusal, list[Fork]] = field(
        default_factory=lambda: {refusal: [] for refusal in Refusal}
    )
    #: Beside a fork here, every head in another worktree that carries the round's nonce.
    contested: list[Fork] = field(default_factory=list)
    #: Beside a fork here, unread forks in another worktree whose raw text holds the nonce.
    unread_elsewhere: int = 0


#: How much of an unreadable transcript is searched for the round's nonce.
RAW_NONCE_PREFIX = 64 * 1024

#: One JSON string escape: a backslash and u with four hex digits, or a backslash and one character.
JSON_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|.)", re.DOTALL)
JSON_SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}


def unescape_json(text: str) -> str:
    """Decode the JSON string escapes in raw transcript text, in one pass, so an escaped backslash
    followed by the letter n stays a backslash and an n. In the raw text a nonce right after an
    escaped newline sits after the letter n, which the nonce's left boundary refuses."""

    def decode(match: re.Match[str]) -> str:
        escaped = match.group(1)
        if len(escaped) == 5:
            return chr(int(escaped[1:], 16))
        return JSON_SIMPLE_ESCAPES.get(escaped, escaped)

    return JSON_ESCAPE.sub(decode, text)


def raw_holds_nonce(transcript: Path, wanted: str) -> bool:
    """Whether the first RAW_NONCE_PREFIX bytes hold the first nonce of `wanted`, as a whole token.

    For a transcript whose record 0 cannot be parsed: a truncated record 0 can still hold the
    target line, past its first newline too, so its JSON escapes are decoded before matching. A
    file that cannot be opened or read, deleted mid-scan among them, is read as not holding it, as
    on main: --since bounds it by write time, and elsewhere it is out of scope.
    """
    nonces = NONCE_SHAPE.findall(wanted)
    if not nonces:
        return False
    try:
        with transcript.open("rb") as fh:
            text = fh.read(RAW_NONCE_PREFIX).decode("utf-8", errors="replace")
    except OSError:
        return False
    text = unescape_json(text)
    return any(found.casefold() == nonces[0].casefold() for found in NONCE_SHAPE.findall(text))


def file_identity(path: Path) -> tuple[int, int, int, int] | str | None:
    """One spelling per file, however it was reached: device, inode, size and write time, or the
    resolved path where the platform reports no inode. Size and write time ride along so that a
    filesystem reusing an inode number cannot drop a second, different fork as a duplicate. None
    where the stat fails, so the fork is never dropped as a duplicate of one it may not be; it is
    read, and refuses as unread if it cannot be."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    if info.st_ino:
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    return os.path.normcase(os.path.realpath(path))


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
    refused_elsewhere: list[Fork] = []
    readable_elsewhere = 0
    nonce_elsewhere: list[Fork] = []
    #: Forks whose record 0 could not be read, placed in another worktree by their meta.
    unread_elsewhere = 0
    seen: set[tuple[int, int, int, int] | str] = set()
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
            # A junction, a link or a second root can reach one file twice; it is one fork.
            identity = file_identity(transcript)
            if identity is not None:
                if identity in seen:
                    continue
                seen.add(identity)
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
                elsewhere = (
                    want is not None and fork.worktree and normalize_path(fork.worktree) != want
                )
                # Read before --since: a file whose raw text holds the round's nonce may be that
                # round's fork whatever its write time, as a readable one is. --since once dropped
                # an older unread real fork, and a newer helper's low tag read at exit 0.
                raw_nonce = bool(
                    nonced and filters.target and raw_holds_nonce(transcript, filters.target)
                )
                if filters.since and not raw_nonce:
                    try:
                        written = dt.datetime.fromtimestamp(
                            transcript.stat().st_mtime, tz=dt.timezone.utc
                        )
                    except OSError:
                        written = None
                    if written is not None and written < filters.since:
                        continue
                if elsewhere:
                    # Out of scope, as before, unless its raw text holds the caller's nonce: then
                    # it may be the round's real fork, and beside a fork here it refuses as unread,
                    # below, rather than vanish. An unrelated truncated transcript stays out.
                    if raw_nonce:
                        unread_elsewhere += 1
                    continue
                result.unreadable_files += 1
                continue
            read = read_head(head)
            if not read.review:
                continue
            fork.target, fork.tag, fork.own_nonce = read.target, read.tag, read.own_nonce
            # Stripped as displaced_heads strips them, so a blockquoted paste is tag-shaped too.
            fork.tag_shaped = any(is_tag(line.lstrip(" \t>")) for line in head)
            fork.refusal, fork.notice = read.refusal, read.notice
            if read.candidates and filters.target:
                # Any of its target lines may be the fork's own; the one carrying the nonce is.
                mine = next(
                    (c for c in read.candidates if own_nonce_matches(filters.target, c.own_nonce)),
                    None,
                )
                if mine is not None:
                    fork.target, fork.own_nonce = mine.target, mine.own_nonce
            # The caller's own filters run first, so a fork they exclude is never counted unplaced.
            if filters.target and not target_matches(filters.target, fork.target):
                # A refused fork's arguments are known only in part, so its own nonce alone keeps it.
                partial = fork.refusal is not None
                if not (partial and own_nonce_matches(filters.target, fork.own_nonce)):
                    continue
            fork.time = parse_time(record.get("timestamp", ""))
            if fork.time is None:
                try:
                    fork.time = dt.datetime.fromtimestamp(
                        transcript.stat().st_mtime, tz=dt.timezone.utc
                    )
                except OSError:
                    pass
            cwd = record.get("cwd")
            fork.cwd = cwd if isinstance(cwd, str) else ""
            placed = place(fork, want)
            if placed is None and nonced:
                # The target filter already ran, so this fork carries the caller's own nonce: the
                # nonce places it, where a worktree cannot.
                fork.placed_by = "the round nonce (no worktree or cwd recorded)"
                placed = True
            if placed is False and nonced and fork.tag_shaped:
                nonce_elsewhere.append(fork)
            # --since drops an older round. With a nonce, every fork past the target filter carries
            # this round's own, so it is this round's whatever its time, here or elsewhere: an
            # older real fork dropped by --since once let a newer helper's tag read at exit 0.
            if filters.since and not nonced and (fork.time is None or fork.time < filters.since):
                continue
            if placed is None:
                result.unplaced += 1
                continue
            if placed and fork.refusal is not None:
                result.refused[fork.refusal].append(fork)
            elif placed:
                result.forks.append(fork)
            elif fork.refusal in BRIEF_REFUSALS and nonced:
                # Such a head is most often a brief that quoted the round's head. It may still be
                # the round's fork; below decides whether it refuses.
                refused_elsewhere.append(fork)
            elif nonced:
                # It carries the caller's nonce and ran elsewhere: found, not absent.
                result.elsewhere += 1
                readable_elsewhere += fork.refusal is None and bool(fork.tag)
    # Beside a fork here, a head elsewhere carrying the round's nonce and a tag-shaped line contests
    # it (exit 16, in main): the head elsewhere may be the round's real fork and the one here a
    # helper that pasted it, and nothing in record 0, its time or the meta tells them apart. PR 244
    # kept such a head out of scope so a brief elsewhere could not block a reading for good; a
    # fresh round clears it, since a pasted head carries the old round's nonce. With nothing read
    # here, a refused head elsewhere refuses (14 or 15) rather than send an inline round to
    # --worktree (exit 12) after a helper's brief, unless a head elsewhere reads with its tag:
    # then exit 12 says where, and a rerun there either reads, refuses on what it finds, or is
    # contested by the head it left. A refused head in scope always refuses, never set aside
    # beside a readable fork.
    if result.forks:
        result.contested = nonce_elsewhere
        result.unread_elsewhere = unread_elsewhere
    elif readable_elsewhere:
        result.elsewhere += len(refused_elsewhere)
    else:
        for fork in refused_elsewhere:
            result.refused[fork.refusal].append(fork)
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
        "--since",
        help="only forks whose record 0 is at or after this ISO time, with an offset; a fork"
        " carrying the round's nonce is kept whatever its time",
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
    if result.unread_elsewhere:
        print(f"{result.unread_elsewhere} {UNREAD_ELSEWHERE_MESSAGE}")
        return EXIT_UNREAD
    if result.unplaced:
        print(f"{result.unplaced} {UNPLACED_MESSAGE}")
        return EXIT_UNPLACED
    for refusal in Refusal:
        refused = result.refused[refusal]
        if refused:
            for fork in refused:
                # Record 0's own words, so behind --verbose with the paths: one could be a path.
                if fork.notice and args.verbose:
                    print(f'review_tag: agent {fork.agent_id}: the unknown notice opens '
                          f'"{spell(fork.notice, True)}"', file=sys.stderr)
            print(f"{len(refused)} {refusal.message}")
            return refusal.exit
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
    if result.contested and result.forks[0].tag:
        # Before any row is rendered, so the fork here prints no quotable tag. A tagless fork here
        # still exits 5: it quotes no tag, so it names no wrong level.
        print(f"{len(result.contested)} {CONTESTED_MESSAGE}")
        for where, forks in (("here", result.forks), ("another worktree", result.contested)):
            for fork in forks:
                print(f"candidate | {stamp(fork.time)} | agent {fork.agent_id} | {where}")
                if args.verbose:
                    # A path and record 0's own words, so behind --verbose: where to look for the
                    # head that contests, and an unknown notice to measure and add.
                    print(f"review_tag: agent {fork.agent_id} ran in "
                          f"{fork.worktree or fork.cwd or '(absent)'}", file=sys.stderr)
                    if fork.notice:
                        print(f'review_tag: agent {fork.agent_id}: the unknown notice opens '
                              f'"{spell(fork.notice, True)}"', file=sys.stderr)
        return EXIT_CONTESTED

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
