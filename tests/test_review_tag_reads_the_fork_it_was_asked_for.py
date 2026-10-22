"""`scripts/quality/review_tag.py`, **executed** over a fixture projects tree. No real transcript is read.

WHY THIS EXISTS. The `code-review` skill does not print its level tag to its caller, so a QA line
could name the level a Builder passed and not prove which one ran. The tag does land in the reviewer
fork's transcript, near the top of record 0, and this tool reads it from there. A reader of a QA line
then trusts the tool, so the tool has to be shown to pick the right fork and to fail loudly.

The two failures that matter most are the quiet ones. A tool that matched a fork from ANOTHER
worktree would quote a tag from somebody else's review, and it would look exactly like a pass. A
tool that printed nothing on a miss would let a Builder write "none returned" over a search that
never ran. So the miss is a distinct exit code, and the planted control below proves it fires: a
fixture tree with a session and no fork at all.

THE FIXTURE FOLLOWS THE RECORDED SHAPES, NOT THE TOOL'S ASSUMPTIONS. Its first draft wrote the tag
on line 2 with an unquoted target, which is what the tool then assumed, and the suite passed while
the tool read `NONE` off a real fork. Measured 2026-10-22 on this branch's own cloud fork, CLI
2.1.307: the target in backticks, line 2 blank, the tag on line 3; `cwd` in record 0; no
`inheritedWorktreePath` in the meta. `CLOUD` below copies that head with the path removed. `RELAYED`
is the Windows 2.1.301 shape as the dispatching brief described it, and was not seen here.

The fixture tags are written with escapes, so this file stays ASCII under `check-ascii.ps1`.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _ccxtest as t

sys.path.insert(0, str(t.REPO_ROOT / "scripts" / "quality"))

import review_tag  # noqa: E402

SCRIPT = t.REPO_ROOT / "scripts" / "quality" / "review_tag.py"
TIMEOUT_SECONDS = 60

TAG_XHIGH = "xhigh effort \u2192 10 inline angles \u2192 dedup (no verify) \u2192 sweep \u2192 \u226415 findings"
TAG_HIGH = "high effort \u2192 8 inline angles \u2192 dedup (no verify) \u2192 \u226410 findings"

WORKTREE_WINDOWS = "D:\\Code\\korus-wt-a"
WORKTREE_FORWARD = "D:/Code/korus-wt-a"
WORKTREE_OTHER = "D:\\Code\\korus-wt-b"

CLOUD = "cloud"
RELAYED = "relayed"


def head(shape, args, tag):
    """Record 0's message head, in one of the two shapes on record."""
    if shape == CLOUD:
        return f"Review target: `{args}`\n\n`{tag}`\n\nYou are reviewing for **recall** ..."
    return f"Review target: {args}\n`{tag}`\n\nYou are reviewing ..."


def write_fork(projects, session, agent, args, tag, *, timestamp, shape=RELAYED, worktree=None,
               cwd=None, later=None, prefix=None, project="D--Code-korus", body=None):
    sub = Path(projects) / project / session / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    meta = {"agentType": "general-purpose", "spawnDepth": 2 if shape == RELAYED else 1}
    if worktree is not None:
        meta["inheritedWorktreePath"] = worktree
        meta["parentAgentId"] = "builder01"
    (sub / f"agent-{agent}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    # `body` replaces the whole message, for heads neither recorded shape writes.
    body = head(shape, args, tag) if body is None else body
    if prefix is not None:
        body = prefix + "\n" + body
    record = {
        "type": "user",
        "timestamp": timestamp,
        "sessionId": session,
        "message": {"role": "user", "content": [{"type": "text", "text": body}]},
    }
    if cwd is not None:
        record["cwd"] = cwd
    records = [record]
    if later is not None:
        records.append({"type": "assistant", "timestamp": timestamp, "message": later})
    with (sub / f"agent-{agent}.jsonl").open("w", encoding="utf-8") as fh:
        for item in records:
            fh.write(json.dumps(item) + "\n")


def as_attributable(code, out):
    """Read a --no-nonce answer the way the case would read an attributable one.

    The cases not about the nonce run with --no-nonce, which now exits 11 and prints its tag on a
    NOT-ATTRIBUTABLE line. Mapping that back here, in one place, keeps each case testing what it
    names; `TheNoNonceAnswerIsNeverAReading` tests the raw behaviour with no mapping.
    """
    if code == review_tag.EXIT_NOT_ATTRIBUTABLE:
        tagless = "no tag line in record 0" in out
        code = review_tag.EXIT_NO_TAG if tagless else review_tag.EXIT_FOUND
        closing = review_tag.NO_TAG_MESSAGE if tagless else ""
        out = out.replace(review_tag.NOT_ATTRIBUTABLE_MESSAGE, closing)
    return code, out.replace(review_tag.NOT_ATTRIBUTABLE_PREFIX, "  tag: ")


def run(projects, *args, env_extra=None, cwd=None, default_target=True, words_ok=True):
    env = dict(os.environ)
    # Both are set in a live session, and either would point the tool away from the fixture.
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.pop(review_tag.SESSION_ENV, None)
    env.update(env_extra or {})
    cmd = [sys.executable, str(SCRIPT)]
    if projects is not None:
        cmd += ["--projects-dir", str(projects)]
    # --target is required. A case that is not about the target gets one every fixture matches,
    # so it still tests what it names; the cases about the requirement opt out.
    if default_target and "--target" not in args:
        args = args + ("--target", "Review")
    # Most fixtures carry no nonce, and a target without one is refused. Cases not about the nonce
    # say --no-nonce, so they test what they name; the nonce cases opt out with words_ok=False.
    target = args[args.index("--target") + 1] if "--target" in args else ""
    injected = words_ok and target and not review_tag.NONCE_SHAPE.search(target)
    if injected:
        args = args + ("--no-nonce",)
    proc = subprocess.run(
        cmd + list(args),
        capture_output=True,
        timeout=TIMEOUT_SECONDS,
        env=env,
        cwd=cwd,
    )
    # Text mode on Windows writes CRLF, which reddened an assertion that ends in a newline on the
    # windows-latest leg only (run 39725164513). Normalize here, so every case reads one spelling.
    out = proc.stdout.decode("utf-8").replace("\r\n", "\n")
    err = proc.stderr.decode("utf-8").replace("\r\n", "\n")
    code = proc.returncode
    if injected:
        code, out = as_attributable(code, out)
    return code, out, err


class Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.projects = Path(self._tmp.name) / "projects"
        self.projects.mkdir()

    def tearDown(self):
        self._tmp.cleanup()


class TheRecordedCloudShapeIsRead(Fixture):
    """The shape the first draft failed on: blank line 2, tag on line 3, placed by `cwd`."""

    def test_the_tag_on_line_three_is_found(self):
        write_fork(self.projects, "s1", "a1", "Review this branch's diff", TAG_XHIGH,
                   shape=CLOUD, cwd="/home/user/korus", timestamp="2026-10-22T04:14:20.493Z")
        code, out, err = run(self.projects, "--worktree", "/home/user/korus")
        self.assertEqual(code, review_tag.EXIT_FOUND, out + err)
        self.assertIn("tag: " + TAG_XHIGH, out)
        self.assertIn("target: Review this branch's diff\n", out, "the target kept its backticks")
        self.assertIn("placed by: record 0 cwd", out)

    def test_cwd_placement_is_exact(self):
        # Round three found containment matching a harness worktree nested in the checkout, so a
        # session in the primary quoted the nested one's tag. Exact, like inheritedWorktreePath.
        write_fork(self.projects, "s1", "here", "Review x", TAG_XHIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T04:00:00Z")
        write_fork(self.projects, "s1", "nested", "Review x", TAG_HIGH, shape=CLOUD,
                   cwd="/home/user/korus/.claude/worktrees/other", timestamp="2026-10-22T05:00:00Z")
        write_fork(self.projects, "s1", "sibling", "Review x", TAG_HIGH, shape=CLOUD,
                   cwd="/home/user/korus-other", timestamp="2026-10-22T06:00:00Z")
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent here", out)
        self.assertNotIn("nested", out)
        self.assertNotIn("sibling", out)

    def test_a_message_not_starting_with_the_target_line_is_not_a_fork(self):
        # Fail closed: a guess at where a review prompt begins could take ordinary prose for one.
        write_fork(self.projects, "s1", "a1", "Review this diff", TAG_XHIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T04:00:00Z",
                   prefix="Note: findings are capped as you asked last time.")
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)
        self.assertNotIn("tag: " + TAG_XHIGH, out)


class OnlyALevelPipelineIsATag(Fixture):
    """Round two found any `<word> effort` line taken as a tag, and a tag line alone taken as a
    review fork. Both failed open: an Explore fork's prose was quoted as a level."""

    def test_prose_that_says_effort_is_not_a_fork(self):
        write_fork(self.projects, "s1", "explore", "ignored", "x", shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T05:00:00Z",
                   prefix="Explore the tree.\nminimal effort is fine here")
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus", "--session", "s1")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)
        self.assertNotIn("minimal effort", out)

    def test_a_review_fork_with_a_non_level_effort_line_has_no_tag(self):
        write_fork(self.projects, "s1", "rv", "Review this diff", "minimal effort is fine here",
                   shape=CLOUD, cwd="/home/user/korus", timestamp="2026-10-22T05:00:00Z")
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus", "--session", "s1")
        self.assertEqual(code, review_tag.EXIT_NO_TAG, out)
        self.assertIn("no tag line in record 0", out)
        self.assertNotIn("tag:", out, "a placeholder sat on a tag: line")

    def test_the_ascii_spelling_of_the_pipeline_is_a_tag(self):
        # The control: the shape is the level and the arrow, in either spelling, not one byte.
        ascii_tag = "high effort -> 8 inline angles -> dedup (no verify) -> <=10 findings"
        write_fork(self.projects, "s1", "rv", "Review this diff", ascii_tag, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T05:00:00Z")
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus", "--session", "s1")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + ascii_tag, out)


class NothingWidensOnItsOwn(Fixture):
    """The three fail-open paths round two found, each refused with its own exit code."""

    def setUp(self):
        super().setUp()
        write_fork(self.projects, "s1", "one", "Review the ledger change", TAG_XHIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T04:00:00Z")
        write_fork(self.projects, "s2", "two", "Review something unrelated", TAG_HIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T05:00:00Z")

    def test_a_bare_level_is_refused_as_selecting_nothing(self):
        for wanted in ("xhigh", "xhigh --fix", "--max-findings all high"):
            with self.subTest(target=wanted):
                code, out, _ = run(self.projects, "--worktree", "/home/user/korus",
                                   "--session", "s1", "--target", wanted)
                self.assertEqual(code, review_tag.EXIT_NO_SELECTOR, out)
                self.assertIn(review_tag.NO_WORDS_MESSAGE, out)
                self.assertNotIn("tag:", out)

    def test_a_target_without_a_nonce_is_refused(self):
        # Round five: a no-nonce target only warned, and a peer's fork could be the one match.
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus", "--any-session",
                           "--target", "Review the ledger change", words_ok=False)
        self.assertEqual(code, review_tag.EXIT_NO_SELECTOR, out)
        self.assertIn(review_tag.NO_NONCE_MESSAGE, out)
        self.assertNotIn("tag:", out)

    def test_target_words_shared_by_two_sessions_stay_ambiguous(self):
        # Round three: the standard arguments are shared by every Builder, so words matching both
        # sessions quoted the newer one's tag with exit 0.
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus", "--any-session",
                           "--target", "Review")
        self.assertEqual(code, review_tag.EXIT_AMBIGUOUS, out)
        self.assertNotIn("tag:", out)

    def test_a_session_resolves_the_ambiguity(self):
        # The control for the three above: the same tree selects one fork once a session is given.
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus", "--session", "s1",
                           "--target", "xhigh Review the ledger change")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent one", out)
        self.assertNotIn("agent two", out)

    def test_no_target_is_refused_because_target_is_required(self):
        code, out, _ = run(self.projects, "--any-worktree", "--any-session", default_target=False)
        self.assertEqual(code, review_tag.EXIT_NO_SELECTOR, out)
        self.assertIn(review_tag.NO_SELECTOR_MESSAGE, out)

    def test_no_git_toplevel_refuses_rather_than_widens(self):
        outside = tempfile.mkdtemp(dir=self._tmp.name)
        code, out, _ = run(self.projects, "--session", "s1", cwd=outside,
                           env_extra={"GIT_CEILING_DIRECTORIES": self._tmp.name})
        self.assertEqual(code, review_tag.EXIT_NO_TOPLEVEL, out)
        self.assertIn(review_tag.NO_TOPLEVEL_MESSAGE, out)
        self.assertNotIn("agent one", out)

    def test_any_worktree_is_the_explicit_widening(self):
        # The control: from the same directory, the explicit flag finds the fork.
        outside = tempfile.mkdtemp(dir=self._tmp.name)
        code, out, _ = run(self.projects, "--any-worktree", "--session", "s1", cwd=outside,
                           env_extra={"GIT_CEILING_DIRECTORIES": self._tmp.name})
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent one", out)


class AForkInTheWorktreeIsFoundAndOneElsewhereIsNot(Fixture):
    def setUp(self):
        super().setUp()
        write_fork(self.projects, "s1", "aaa111", "Review this branch's diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00.000Z")
        write_fork(self.projects, "s2", "bbb222", "Review this branch's diff", TAG_HIGH,
                   worktree=WORKTREE_OTHER, timestamp="2026-10-22T10:00:00.000Z")

    def test_the_matching_fork_is_printed_with_its_tag(self):
        code, out, err = run(self.projects, "--worktree", WORKTREE_FORWARD)
        self.assertEqual(code, review_tag.EXIT_FOUND, out + err)
        self.assertIn("agent aaa111", out)
        self.assertIn("tag: " + TAG_XHIGH, out)
        self.assertIn("fork | 2026-10-22T09:00:00Z | agent aaa111", out)
        self.assertIn("placed by: inheritedWorktreePath", out)

    def test_a_fork_in_another_worktree_does_not_match(self):
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD,
                        "--target", "Review this branch's diff")
        self.assertNotIn("bbb222", out, "a fork from another worktree was quoted as this one's")
        self.assertNotIn("high effort \u2192 8", out)

    def test_the_other_worktree_is_itself_findable(self):
        # The control for the test above: the excluded fork is readable, so its absence was the
        # filter rather than a fixture the tool could not parse.
        code, out, _ = run(self.projects, "--worktree", WORKTREE_OTHER)
        self.assertEqual(code, review_tag.EXIT_FOUND)
        self.assertIn("agent bbb222", out)

    def test_no_path_column_appears_by_default(self):
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD)
        self.assertNotIn("Code", out, "a path column was printed without --verbose")
        self.assertNotIn(str(self.projects), out)
        _, verbose, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--verbose")
        self.assertIn(WORKTREE_WINDOWS, verbose)


class TheSessionFilterKeepsAnotherSessionsTagOut(Fixture):
    def setUp(self):
        super().setUp()
        write_fork(self.projects, "mine", "m1", "Review this diff", TAG_XHIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T04:00:00Z")
        write_fork(self.projects, "peer", "p1", "Review this diff", TAG_HIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T05:00:00Z")

    def test_the_session_defaults_from_the_environment(self):
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus",
                           env_extra={review_tag.SESSION_ENV: "mine"})
        self.assertEqual(code, review_tag.EXIT_FOUND)
        self.assertIn("agent m1", out)
        self.assertNotIn("p1", out, "a peer session's newer fork was quoted as this session's")

    def test_any_session_widens_it(self):
        # The control: the peer's fork is there to be found, so the test above is the filter. Two
        # sessions are ambiguous, so the run names both and prints no tag.
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus", "--any-session",
                           env_extra={review_tag.SESSION_ENV: "mine"})
        self.assertEqual(code, review_tag.EXIT_AMBIGUOUS, out)
        self.assertIn("agent m1 | session mine", out)
        self.assertIn("agent p1 | session peer", out)
        self.assertNotIn("tag:", out)


class BackslashesAndForwardSlashesNameOneWorktree(unittest.TestCase):
    def test_the_two_spellings_normalize_alike(self):
        self.assertEqual(
            review_tag.normalize_path(WORKTREE_WINDOWS, fold_case=False),
            review_tag.normalize_path(WORKTREE_FORWARD + "/", fold_case=False),
        )

    def test_case_is_folded_only_where_asked(self):
        lower = WORKTREE_FORWARD.lower()
        self.assertEqual(
            review_tag.normalize_path(WORKTREE_WINDOWS, fold_case=True),
            review_tag.normalize_path(lower, fold_case=True),
        )
        self.assertNotEqual(
            review_tag.normalize_path(WORKTREE_WINDOWS, fold_case=False),
            review_tag.normalize_path(lower, fold_case=False),
        )


class TargetTellsTwoRoundsApart(Fixture):
    def setUp(self):
        super().setUp()
        write_fork(self.projects, "s1", "r1aaaa", "Review round one of the ledger change", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        write_fork(self.projects, "s1", "r2bbbb", "Review round two, after the fixes", TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T11:00:00Z")

    def test_two_rounds_with_nothing_to_tell_them_apart_refuse(self):
        # Never the newest readable one: two candidates is a refusal that names both, oldest first.
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD)
        self.assertEqual(code, review_tag.EXIT_AMBIGUOUS, out)
        self.assertLess(out.index("r1aaaa"), out.index("r2bbbb"))
        self.assertNotIn("tag:", out)

    def test_target_picks_one_round(self):
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", "round two")
        self.assertIn("r2bbbb", out)
        self.assertNotIn("r1aaaa", out)

    def test_the_level_and_flags_in_the_target_still_match(self):
        # The skill drops a level that parsed from its `Review target` line, so the caller's own
        # argument string, level and flags first, has to match what is left.
        for wanted in ("xhigh Review round one",
                       "xhigh --max-findings all Review round one",
                       "--fix high Review round one"):
            with self.subTest(target=wanted):
                _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", wanted)
                self.assertIn("r1aaaa", out)
                self.assertNotIn("r2bbbb", out)

    def test_latest_is_gone(self):
        # It picked the newest readable fork, which is the choice the tool now refuses to make.
        code, _, err = run(self.projects, "--worktree", WORKTREE_FORWARD, "--latest")
        self.assertEqual(code, 2, err)

    def test_since_drops_the_earlier_round(self):
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD,
                        "--since", "2026-10-22T10:00:00Z")
        self.assertIn("r2bbbb", out)
        self.assertNotIn("r1aaaa", out)

    def test_since_without_an_offset_is_refused(self):
        code, _, err = run(self.projects, "--worktree", WORKTREE_FORWARD,
                           "--since", "2026-10-22T10:00:00")
        self.assertEqual(code, 2)
        self.assertIn("offset", err)


class AsciiSpellsTheGlyphsOut(Fixture):
    def test_ascii_output_carries_no_glyph(self):
        write_fork(self.projects, "s1", "aaa111", "Review this diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--ascii")
        self.assertEqual(code, review_tag.EXIT_FOUND)
        self.assertIn(
            "tag: xhigh effort -> 10 inline angles -> dedup (no verify) -> sweep -> <=15 findings",
            out,
        )
        self.assertTrue(out.isascii(), "--ascii printed a non-ASCII character")

    def test_without_ascii_the_glyphs_are_printed_verbatim(self):
        # The control: the same fixture without the flag prints the glyph, so the test above is the
        # flag at work and not a fixture that never held one.
        write_fork(self.projects, "s1", "aaa111", "Review this diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD)
        self.assertIn("\u2192", out)


class NothingAQaLineQuotesSaysTheBannedWord(Fixture):
    """`tests/test_the_qa_line_never_says_review.py` bans one word in the QA line, and this tool's
    own file name carries it. So every stdout line a Builder quotes -- the header, the tag line and
    each refusal message -- must be free of it, under the documented `--target` call too."""

    def setUp(self):
        super().setUp()
        write_fork(self.projects, "s1", "aaa111", "Review this diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")

    def test_the_quotable_lines_never_carry_it(self):
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--session", "s1",
                        "--target", "Review this")
        quotable = [line for line in out.splitlines() if not line.strip().startswith("target:")]
        self.assertGreaterEqual(len(quotable), 3)
        for line in quotable:
            self.assertNotIn("review", line.lower(), line)
        # The attributable path, with a nonce, as the playbook documents it.
        write_fork(self.projects, "s1", "nonced", "round-1234abcd99 Review this diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:30:00Z")
        _, nonced, _ = run(self.projects, "--worktree", WORKTREE_FORWARD,
                           "--target", "round-1234abcd99", words_ok=False)
        for line in nonced.splitlines():
            if not line.strip().startswith("target:"):
                self.assertNotIn("review", line.lower(), line)
        self.assertNotIn("review", review_tag.NOT_ATTRIBUTABLE_PREFIX.lower())
        for name in dir(review_tag):
            if name.endswith("_MESSAGE"):
                message = getattr(review_tag, name)
                self.assertNotIn("review", message.lower(), f"{name}: {message}")

    def test_the_target_line_does_carry_it(self):
        # The control: the target line echoes "Review this diff", so the filter above is what keeps
        # the word out, and the scan was not run over output that could never hold it.
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", "Review this")
        self.assertIn("review", out.lower())


class OnlyRecordZeroIsRead(Fixture):
    def test_a_later_record_is_never_printed(self):
        write_fork(self.projects, "s1", "aaa111", "Review this diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z",
                   later={"role": "assistant", "content": "PLANTED-LATER-RECORD"})
        _, out, err = run(self.projects, "--worktree", WORKTREE_FORWARD, "--verbose")
        self.assertNotIn("PLANTED-LATER-RECORD", out + err)
        self.assertNotIn("You are reviewing", out + err, "prose past the tag was printed")


class AForkWithNowhereRecorded(Fixture):
    """Neither `inheritedWorktreePath` nor `cwd`: nothing places it but `--any-worktree`."""

    def setUp(self):
        super().setUp()
        write_fork(self.projects, "top1", "ccc333", "Review the top-level diff", TAG_XHIGH,
                   timestamp="2026-10-22T09:00:00Z")

    def test_without_a_session_it_is_unplaced_not_absent(self):
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", "top-level")
        self.assertEqual(code, review_tag.EXIT_UNPLACED)
        self.assertIn(review_tag.UNPLACED_MESSAGE, out)
        self.assertNotIn(review_tag.NO_FORK_MESSAGE, out, "a found fork was reported as none")

    def test_an_unplaced_newer_fork_refuses_rather_than_quote_an_older_one(self):
        # Round three: the newest real round was dropped silently while an older placed fork's
        # tag was quoted with exit 0.
        write_fork(self.projects, "top1", "older", "Review the top-level diff", TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T08:00:00Z")
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", "top-level")
        self.assertEqual(code, review_tag.EXIT_UNPLACED, out)
        self.assertNotIn("tag:", out)

    def test_a_fork_the_target_excludes_is_not_counted_unplaced(self):
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", "elsewhere")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_a_session_does_not_place_it(self):
        # The Lander's case 2: every subagent Builder shares its Manager's session, so a session
        # says nothing about which worktree, or which Builder, a fork belongs to.
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--session", "top1")
        self.assertEqual(code, review_tag.EXIT_UNPLACED, out)
        self.assertNotIn("tag:", out)

    def test_any_worktree_includes_it_and_says_so(self):
        code, out, _ = run(self.projects, "--any-worktree", "--session", "top1")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("ccc333", out)
        self.assertIn("placed by: any worktree", out)


class EveryMissIsLoudAndDistinct(Fixture):
    def test_a_tree_with_no_fork_exits_no_fork(self):
        # THE PLANTED CONTROL. A projects dir holding a session and its transcript, and no fork.
        session = self.projects / "D--Code-korus"
        session.mkdir()
        (session / "s1.jsonl").write_text('{"type": "user"}\n', encoding="utf-8")
        code, out, _ = run(self.projects, "--any-worktree", "--session", "s1")
        self.assertEqual(code, review_tag.EXIT_NO_FORK)
        self.assertIn(review_tag.NO_FORK_MESSAGE, out)

    def test_a_fork_that_is_not_a_review_is_not_counted(self):
        sub = self.projects / "p" / "s1" / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-x.jsonl").write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "Explore the tree"}})
            + "\n",
            encoding="utf-8",
        )
        code, _, _ = run(self.projects, "--any-worktree", "--session", "s1")
        self.assertEqual(code, review_tag.EXIT_NO_FORK)

    def test_no_projects_dir_exits_no_root(self):
        code, out, _ = run(Path(self._tmp.name) / "absent")
        self.assertEqual(code, review_tag.EXIT_NO_ROOT)
        self.assertIn(review_tag.NO_ROOT_MESSAGE, out)

    def test_an_unreadable_root_beside_an_empty_one_says_which(self):
        other = Path(self._tmp.name) / "other-projects"
        other.mkdir()
        real_listdir = os.listdir

        def refuse(path):
            if Path(path) == other:
                raise PermissionError(path)
            return real_listdir(path)

        result = None
        with mock.patch.object(review_tag.os, "listdir", side_effect=refuse):
            result = review_tag.scan([self.projects, other], review_tag.Filters())
        self.assertEqual(result.unreadable_roots, [other])
        self.assertEqual(result.forks, [])

    def test_one_fork_without_a_tag_exits_no_tag(self):
        write_fork(self.projects, "s1", "new222", "Review this diff", "Some other second line",
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T10:00:00Z")
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD)
        self.assertEqual(code, review_tag.EXIT_NO_TAG)
        self.assertIn("no tag line in record 0", out)
        self.assertNotIn("tag:", out, "a placeholder sat on a tag: line")
        self.assertIn(review_tag.NO_TAG_MESSAGE, out)

    def test_the_codes_are_distinct(self):
        codes = {review_tag.EXIT_FOUND, review_tag.EXIT_NO_FORK, review_tag.EXIT_NO_ROOT,
                 review_tag.EXIT_NO_TAG, review_tag.EXIT_UNPLACED, review_tag.EXIT_AMBIGUOUS,
                 review_tag.EXIT_NO_TOPLEVEL, review_tag.EXIT_NO_SELECTOR, review_tag.EXIT_UNREAD,
                 review_tag.EXIT_NOT_ATTRIBUTABLE, review_tag.EXIT_ELSEWHERE,
                 review_tag.EXIT_UNSPLIT, 1, 2}
        self.assertEqual(len(codes), 14, "an exit code collides with another, or with 1 or 2")


class TheFourFailOpensTheLanderFoundAtF3a4a39(Fixture):
    """Each case exited 0 with the WRONG fork's tag. The rule now: refuse whenever more than one
    candidate fork, or any unread fork or root, could be the run asked for. Each refusal sits
    beside a control showing the right fork is findable once the doubt is gone."""

    STD = "Review this branch's diff against origin/main"

    def test_1_two_builders_under_one_manager_session_refuse(self):
        # The Manager's documented call: --session plus --any-worktree. Both Builders' forks share
        # the Manager's session, and the run quoted Builder B's tag for Builder A.
        write_fork(self.projects, "mgr", "builderA", self.STD, TAG_XHIGH,
                   worktree="D:\\Code\\wt-a", timestamp="2026-10-22T09:00:00Z")
        write_fork(self.projects, "mgr", "builderB", self.STD, TAG_HIGH,
                   worktree="D:\\Code\\wt-b", timestamp="2026-10-22T09:05:00Z")
        code, out, _ = run(self.projects, "--session", "mgr", "--any-worktree",
                           "--target", "xhigh " + self.STD)
        self.assertEqual(code, review_tag.EXIT_AMBIGUOUS, out)
        self.assertNotIn("tag:", out)
        code, out, _ = run(self.projects, "--session", "mgr", "--worktree", "D:/Code/wt-a",
                           "--target", "xhigh " + self.STD)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent builderA", out)
        self.assertNotIn("builderB", out)

    def test_2_two_forks_in_one_session_and_worktree_refuse(self):
        write_fork(self.projects, "mgr", "first", self.STD, TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        write_fork(self.projects, "mgr", "second", self.STD, TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:30:00Z")
        code, out, _ = run(self.projects, "--session", "mgr", "--worktree", WORKTREE_FORWARD,
                           "--target", self.STD)
        self.assertEqual(code, review_tag.EXIT_AMBIGUOUS, out)
        self.assertNotIn("tag:", out)
        code, out, _ = run(self.projects, "--session", "mgr", "--worktree", WORKTREE_FORWARD,
                           "--target", self.STD, "--since", "2026-10-22T09:15:00Z")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent second", out)

    def _unread(self, agent, content, worktree=WORKTREE_WINDOWS):
        sub = self.projects / "D--Code-korus" / "s1" / "subagents"
        sub.mkdir(parents=True, exist_ok=True)
        meta = {"agentType": "general-purpose"}
        if worktree is not None:
            meta["inheritedWorktreePath"] = worktree
        (sub / f"agent-{agent}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (sub / f"agent-{agent}.jsonl").write_text(content, encoding="utf-8")

    def test_3_an_unread_fork_refuses_rather_than_let_an_older_one_win(self):
        write_fork(self.projects, "s1", "older", self.STD, TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        for name, content in (("empty", ""), ("truncated", '{"type": "user", "mess')):
            with self.subTest(record0=name):
                self._unread("writing", content)
                code, out, _ = run(self.projects, "--session", "s1", "--worktree",
                                   WORKTREE_FORWARD, "--target", self.STD)
                self.assertEqual(code, review_tag.EXIT_UNREAD, out)
                self.assertIn(review_tag.UNREAD_MESSAGE, out)
                self.assertNotIn("tag:", out, "the older fork's tag was quoted over an unread one")

    def test_3_control_an_unread_fork_recorded_elsewhere_is_ruled_out(self):
        write_fork(self.projects, "s1", "older", self.STD, TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        self._unread("writing", "", worktree=WORKTREE_OTHER)
        code, out, _ = run(self.projects, "--session", "s1", "--worktree", WORKTREE_FORWARD,
                           "--target", self.STD)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent older", out)

    def _main(self, roots, *args):
        out = io.StringIO()
        argv = [a for root in roots for a in ("--projects-dir", str(root))] + list(args)
        argv.append("--no-nonce")
        with contextlib.redirect_stdout(out):
            code = review_tag.main(argv)
        return as_attributable(code, out.getvalue())

    def test_4_an_unreadable_root_refuses_even_when_another_matched(self):
        write_fork(self.projects, "s1", "elsewhere", self.STD, TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        other = Path(self._tmp.name) / "other-projects"
        other.mkdir()
        real_listdir = os.listdir

        def refuse(path):
            if Path(path) == other:
                raise PermissionError(path)
            return real_listdir(path)

        args = ("--session", "s1", "--worktree", WORKTREE_FORWARD, "--target", self.STD)
        with mock.patch.object(review_tag.os, "listdir", side_effect=refuse):
            code, out = self._main([self.projects, other], *args)
        self.assertEqual(code, review_tag.EXIT_NO_ROOT, out)
        self.assertIn(review_tag.PARTIAL_ROOT_MESSAGE, out)
        self.assertNotIn("tag:", out)
        # The control: the same call with both roots readable quotes the fork.
        code, out = self._main([self.projects, other], *args)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent elsewhere", out)


class TheFinalRoundsFailOpens(Fixture):
    """Round four, on 8e00ab1: the unread rule held at the root and for record 0, and not one level
    down or for the meta file. Each case exited 0 with a fork's tag where a refusal was owed."""

    STD = "Review this branch's diff against origin/main"

    def test_an_unreadable_project_directory_refuses(self):
        write_fork(self.projects, "s1", "seen", self.STD, TAG_XHIGH, project="projA",
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        blocked = self.projects / "projB"
        blocked.mkdir()
        real_scandir = os.scandir

        def refuse(path="."):
            if Path(path) == blocked:
                raise PermissionError(13, "denied", str(blocked))
            return real_scandir(path)

        args = ["--projects-dir", str(self.projects), "--session", "s1",
                "--worktree", WORKTREE_FORWARD, "--target", self.STD, "--no-nonce"]
        out = io.StringIO()
        with mock.patch.object(review_tag.os, "scandir", side_effect=refuse):
            with contextlib.redirect_stdout(out):
                code = review_tag.main(args)
        self.assertEqual(code, review_tag.EXIT_NO_ROOT, out.getvalue())
        self.assertNotIn("tag:", out.getvalue())
        # The control: with the directory readable, the one fork is quoted.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = review_tag.main(args)
        code, text = as_attributable(code, out.getvalue())
        self.assertEqual(code, review_tag.EXIT_FOUND, text)

    def test_a_meta_file_that_cannot_be_parsed_makes_the_fork_unread(self):
        # The meta may hold the inheritedWorktreePath that puts the fork elsewhere; without it the
        # fork would be placed by its cwd and quoted.
        write_fork(self.projects, "s1", "halfmeta", self.STD, TAG_HIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T09:00:00Z")
        meta = self.projects / "D--Code-korus" / "s1" / "subagents" / "agent-halfmeta.meta.json"
        meta.write_text('{"inheritedWorktreePath": "D:\\\\Co', encoding="utf-8")
        code, out, _ = run(self.projects, "--session", "s1", "--worktree", "/home/user/korus",
                           "--target", self.STD)
        self.assertEqual(code, review_tag.EXIT_UNREAD, out)
        self.assertNotIn("tag:", out)

    def test_an_absent_meta_file_is_no_meta_not_unread(self):
        # The control: the cloud shape may carry no meta at all, and that fork is still read.
        write_fork(self.projects, "s1", "nometa", self.STD, TAG_XHIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T09:00:00Z")
        (self.projects / "D--Code-korus" / "s1" / "subagents" / "agent-nometa.meta.json").unlink()
        code, out, _ = run(self.projects, "--session", "s1", "--worktree", "/home/user/korus",
                           "--target", self.STD)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)

    def test_since_rules_out_an_unread_fork_written_before_it(self):
        # The mtime branch the final round found untested: a stale unread file older than --since
        # is not a candidate, and without --since the same tree refuses.
        write_fork(self.projects, "s1", "fresh", self.STD, TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:30:00Z")
        sub = self.projects / "D--Code-korus" / "s1" / "subagents"
        stale = sub / "agent-stale.jsonl"
        stale.write_text("", encoding="utf-8")
        old = review_tag.parse_time("2026-10-22T08:00:00Z").timestamp()
        os.utime(stale, (old, old))
        args = ("--session", "s1", "--worktree", WORKTREE_FORWARD, "--target", self.STD)
        code, out, _ = run(self.projects, *args, "--since", "2026-10-22T09:00:00Z")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent fresh", out)
        code, out, _ = run(self.projects, *args)
        self.assertEqual(code, review_tag.EXIT_UNREAD, out)

    def test_no_refusal_offers_the_widening_that_would_let_a_peer_in(self):
        for name in ("UNPLACED_MESSAGE", "NO_TOPLEVEL_MESSAGE", "UNREAD_MESSAGE"):
            self.assertNotIn("--any-worktree", getattr(review_tag, name), name)


class ARoundNonceMakesTheOneMatchTheCallersOwn(Fixture):
    """F2. Builders share the standard arguments, so without a nonce a round that left no fork could
    find another Builder's fork as its one match. The nonce sits after the level, so the level stays
    the bare first word the skill parses: `xhigh round-<hex> Review ...`."""

    STD = "Review this branch's diff against origin/main"

    def setUp(self):
        super().setUp()
        # The skill drops the parsed level, so the target line starts with the nonce.
        write_fork(self.projects, "mgr", "builderA", "round-1111aaaa22 " + self.STD, TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        write_fork(self.projects, "mgr", "builderB", "round-3333bbbb44 " + self.STD, TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:05:00Z")

    def _run(self, *extra):
        return run(self.projects, "--session", "mgr", "--worktree", WORKTREE_FORWARD, *extra)

    def test_the_nonce_selects_the_callers_fork_among_shared_arguments(self):
        code, out, _ = self._run("--target", "round-1111aaaa22")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent builderA", out)
        self.assertNotIn("builderB", out)

    def test_the_full_arguments_with_level_and_nonce_select_it_too(self):
        code, out, _ = self._run("--target", "xhigh round-3333bbbb44 " + self.STD)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent builderB", out)

    def test_an_inline_round_exits_no_fork_never_a_peers_tag(self):
        # The caller's round left no fork. Its nonce matches nothing, so no peer's tag is quoted.
        code, out, _ = self._run("--target", "round-5555cccc66")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)
        self.assertNotIn("tag:", out)

    def test_a_later_mention_of_a_nonce_is_not_that_rounds_fork(self):
        # Round six: round two's arguments mentioned round one's nonce, and round one -- which ran
        # inline and left no fork -- was answered with round two's tag.
        write_fork(self.projects, "mgr", "round2", "round-bbbbbbbbbb Recheck from round-aaaaaaaaaa",
                   TAG_HIGH, worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:30:00Z")
        code, out, _ = self._run("--target", "round-aaaaaaaaaa")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)
        self.assertNotIn("tag:", out)

    def test_a_nonce_matches_only_as_a_whole_token(self):
        code, out, _ = self._run("--target", "round-1111aaaa")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_without_a_nonce_the_shared_arguments_stay_ambiguous(self):
        # The control: the same tree, the arguments alone under --no-nonce, two candidates.
        code, out, _ = self._run("--target", self.STD)
        self.assertEqual(code, review_tag.EXIT_AMBIGUOUS, out)

    def test_a_malformed_nonce_is_refused_not_matched_broadly(self):
        # `round-` alone is what an empty command substitution leaves; every fork carries it.
        for bad in ("round-", "round-1111aaa", "pre-round-1111aaaa22"):
            with self.subTest(target=bad):
                code, out, _ = run(self.projects, "--session", "mgr", "--worktree",
                                   WORKTREE_FORWARD, "--target", bad, words_ok=False)
                self.assertEqual(code, review_tag.EXIT_NO_SELECTOR, out)
                self.assertNotIn("tag:", out)

    def test_a_nonce_does_not_match_a_longer_hyphenated_token(self):
        write_fork(self.projects, "mgr", "hyphen", "round-7777dddd88-b " + self.STD, TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:10:00Z")
        code, out, _ = self._run("--target", "round-7777dddd88")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_the_nonce_places_a_fork_that_records_no_worktree(self):
        # Round five: exit 6 told the Builder to narrow with --since, which can never drop its
        # own fork. The target filter has run, so the nonce identifies the fork.
        write_fork(self.projects, "mgr", "nowhere", "round-9999eeee00 " + self.STD, TAG_XHIGH,
                   timestamp="2026-10-22T09:20:00Z")
        code, out, _ = self._run("--target", "round-9999eeee00")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("placed by: the round nonce", out)

    def test_without_a_nonce_that_fork_still_refuses_unplaced(self):
        write_fork(self.projects, "mgr", "nowhere", "round-9999eeee00 " + self.STD, TAG_XHIGH,
                   timestamp="2026-10-22T09:20:00Z")
        code, out, _ = self._run("--target", "Review this branch")
        self.assertEqual(code, review_tag.EXIT_UNPLACED, out)


class TheSurvivingMutantsAreKilled(Fixture):
    """The Lander's mutation run on 5e77d46 left five mutants alive. Each case below fails on its
    mutant, beside the behaviour it pins."""

    STD = "Review this branch's diff"

    def _main(self, *args):
        out = io.StringIO()
        argv = ["--projects-dir", str(self.projects), "--session", "s1", "--no-nonce"] + list(args)
        with contextlib.redirect_stdout(out):
            code = review_tag.main(argv)
        return as_attributable(code, out.getvalue())

    def test_m21_an_oserror_opening_the_transcript_is_unread_not_skipped(self):
        write_fork(self.projects, "s1", "older", self.STD, TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T08:00:00Z")
        write_fork(self.projects, "s1", "locked", self.STD, TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        real = review_tag.read_record_zero

        def deny(transcript):
            if transcript.name == "agent-locked.jsonl":
                raise PermissionError(13, "denied", str(transcript))
            return real(transcript)

        with mock.patch.object(review_tag, "read_record_zero", side_effect=deny):
            code, out = self._main("--worktree", WORKTREE_FORWARD, "--target", self.STD)
        self.assertEqual(code, review_tag.EXIT_UNREAD, out)
        self.assertNotIn("tag:", out)

    def test_m26_inherited_worktree_path_is_matched_exactly_not_by_prefix(self):
        for elsewhere in (WORKTREE_WINDOWS + "-other", WORKTREE_WINDOWS + "\\.claude\\worktrees\\x"):
            with self.subTest(worktree=elsewhere):
                write_fork(self.projects, "s1", "peer", self.STD, TAG_HIGH,
                           worktree=elsewhere, timestamp="2026-10-22T09:00:00Z")
                code, out = self._main("--worktree", WORKTREE_FORWARD, "--target", self.STD)
                self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_m15_a_meta_that_is_not_an_object_is_unread(self):
        write_fork(self.projects, "s1", "listmeta", self.STD, TAG_XHIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T09:00:00Z")
        meta = self.projects / "D--Code-korus" / "s1" / "subagents" / "agent-listmeta.meta.json"
        meta.write_text("[]", encoding="utf-8")
        code, out = self._main("--worktree", "/home/user/korus", "--target", self.STD)
        self.assertEqual(code, review_tag.EXIT_UNREAD, out)

    def test_m19_an_unread_fork_whose_stat_fails_is_not_ruled_out_by_since(self):
        write_fork(self.projects, "s1", "fresh", self.STD, TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:30:00Z")
        sub = self.projects / "D--Code-korus" / "s1" / "subagents"
        (sub / "agent-nostat.jsonl").write_text("", encoding="utf-8")
        real_stat = Path.stat

        def deny(path, *a, **k):
            if path.name == "agent-nostat.jsonl":
                raise PermissionError(13, "denied", str(path))
            return real_stat(path, *a, **k)

        with mock.patch.object(review_tag.Path, "stat", autospec=True, side_effect=deny):
            code, out = self._main("--worktree", WORKTREE_FORWARD, "--target", self.STD,
                                   "--since", "2026-10-22T09:00:00Z")
        self.assertEqual(code, review_tag.EXIT_UNREAD, out)

    def test_m37_a_fork_nested_deeper_than_subagents_is_found(self):
        sub = self.projects / "D--Code-korus" / "s1" / "subagents"
        write_fork(self.projects, "s1", "deep", self.STD, TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        nested = sub / "nested" / "deeper"
        nested.mkdir(parents=True)
        for name in ("agent-deep.jsonl", "agent-deep.meta.json"):
            (sub / name).rename(nested / name)
        code, out = self._main("--worktree", WORKTREE_FORWARD, "--target", self.STD)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent deep", out)


class AnUnreadableConfigDirRefuses(unittest.TestCase):
    """F1. With CLAUDE_CONFIG_DIR unset, a ~/.claude-X whose stat failed was dropped as absent,
    because is_dir() answers False, and another root's fork was quoted with exit 0."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.good = self.home / ".claude"
        self.bad = self.home / ".claude-locked"
        write_fork(self.good / "projects", "s1", "seen", "Review this diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        (self.bad / "projects").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _main(self, deny):
        real_stat, real_listdir, real_is_dir = os.stat, os.listdir, Path.is_dir

        def stat(path, *a, **k):
            if deny and Path(path) == self.bad:
                raise PermissionError(13, "denied", str(path))
            return real_stat(path, *a, **k)

        def is_dir(path, *a, **k):
            # F1a: from Python 3.14, Path.is_dir answers False on a failed stat, and on Windows it
            # answers through nt._path_isdir without reaching the patched os.stat, so a mutant that
            # went back to is_dir() could survive there. On 3.12 and 3.13 is_dir re-raises a
            # denied stat, so the mutant dies by an error instead. Patching is_dir to answer False
            # kills it by a failure on every version.
            if deny and Path(path) == self.bad:
                return False
            return real_is_dir(path, *a, **k)

        def listdir(path="."):
            if deny and Path(path) == self.bad / "projects":
                raise PermissionError(13, "denied", str(path))
            return real_listdir(path)

        env = {"HOME": str(self.home), "USERPROFILE": str(self.home)}
        out = io.StringIO()
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(review_tag.os, "stat", side_effect=stat), \
                mock.patch.object(review_tag.os, "listdir", side_effect=listdir), \
                mock.patch.object(review_tag.Path, "is_dir", autospec=True, side_effect=is_dir), \
                contextlib.redirect_stdout(out):
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            code = review_tag.main(["--session", "s1", "--worktree", WORKTREE_FORWARD,
                                    "--target", "Review this diff", "--no-nonce"])
        return as_attributable(code, out.getvalue())

    def test_an_unstatable_claude_dir_refuses(self):
        code, out = self._main(deny=True)
        self.assertEqual(code, review_tag.EXIT_NO_ROOT, out)
        self.assertNotIn("tag:", out)

    def test_the_control_finds_the_fork_when_both_are_readable(self):
        code, out = self._main(deny=False)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent seen", out)


class TheNoNonceAnswerIsNeverAReading(Fixture):
    """D1. --no-nonce exited 0 with a `tag:` line under the same header as an attributable run, so
    an inline round beside a same-args peer could quote the peer's tag: F2 back through a flag."""

    def setUp(self):
        super().setUp()
        write_fork(self.projects, "s1", "peer", "Review this branch's diff", TAG_HIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")

    def test_it_exits_with_its_own_code_and_no_tag_line(self):
        code, out, _ = run(self.projects, "--session", "s1", "--worktree", WORKTREE_FORWARD,
                           "--target", "Review this branch's diff", "--no-nonce", words_ok=False)
        self.assertEqual(code, review_tag.EXIT_NOT_ATTRIBUTABLE, out)
        self.assertNotIn("tag:", out, "a --no-nonce answer printed a quotable tag: line")
        self.assertIn(review_tag.NOT_ATTRIBUTABLE_PREFIX.strip(), out)
        self.assertIn("NOT ATTRIBUTABLE", out.splitlines()[0])

    def test_a_tagless_match_is_not_attributable_either(self):
        # Round six: a tagless match under --no-nonce exited 5, whose row has a Builder write
        # `none returned` naming a fork that may be a peer's.
        write_fork(self.projects, "s2", "tagless", "Review this branch's diff", "plain prose",
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        code, out, _ = run(self.projects, "--session", "s2", "--worktree", WORKTREE_FORWARD,
                           "--target", "Review this branch's diff", "--no-nonce", words_ok=False)
        self.assertEqual(code, review_tag.EXIT_NOT_ATTRIBUTABLE, out)
        self.assertNotIn(review_tag.NO_TAG_MESSAGE, out)

    def test_no_nonce_beside_a_real_nonce_changes_nothing(self):
        write_fork(self.projects, "s1", "mine", "round-abcdef0123 Review this branch's diff",
                   TAG_XHIGH, worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:10:00Z")
        code, out, _ = run(self.projects, "--session", "s1", "--worktree", WORKTREE_FORWARD,
                           "--target", "round-abcdef0123", "--no-nonce", words_ok=False)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + TAG_XHIGH, out)

    def test_the_same_fork_with_its_nonce_is_a_reading(self):
        # The control: the attributable path still prints `tag:` and exits 0.
        write_fork(self.projects, "s1", "mine", "round-abcdef0123 Review this branch's diff",
                   TAG_XHIGH, worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:10:00Z")
        code, out, _ = run(self.projects, "--session", "s1", "--worktree", WORKTREE_FORWARD,
                           "--target", "round-abcdef0123", words_ok=False)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + TAG_XHIGH, out)
        self.assertNotIn("NOT-ATTRIBUTABLE", out)


class ANonceDoesNotPlaceAForkRecordedElsewhere(Fixture):
    """N14. The nonce places a fork that records NO location. Mutating `placed is None` to `not
    placed` let it also place a fork recorded in ANOTHER worktree, and no case caught that."""

    def test_a_nonce_fork_in_another_worktree_does_not_match(self):
        # Round six: exit 3 said "no fork found" for a fork that carries the nonce; it is found,
        # and ran elsewhere, which is its own exit.
        write_fork(self.projects, "s1", "elsewhere", "round-0123456789 Review x", TAG_HIGH,
                   worktree=WORKTREE_OTHER, timestamp="2026-10-22T09:00:00Z")
        code, out, _ = run(self.projects, "--session", "s1", "--worktree", WORKTREE_FORWARD,
                           "--target", "round-0123456789", words_ok=False)
        self.assertEqual(code, review_tag.EXIT_ELSEWHERE, out)
        self.assertIn(review_tag.ELSEWHERE_MESSAGE, out)
        self.assertNotIn(review_tag.NO_FORK_MESSAGE, out)
        self.assertNotIn("tag:", out)

    def test_the_same_fork_is_found_from_its_own_worktree(self):
        write_fork(self.projects, "s1", "elsewhere", "round-0123456789 Review x", TAG_HIGH,
                   worktree=WORKTREE_OTHER, timestamp="2026-10-22T09:00:00Z")
        code, out, _ = run(self.projects, "--session", "s1", "--worktree", "D:/Code/korus-wt-b",
                           "--target", "round-0123456789", words_ok=False)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)


class TheVault4006Findings(Fixture):
    """vault #4006, the round-two findings PR 233 left open. Each refusal or match sits beside the
    control that shows the fixture would read the other way."""

    NONCE = "round-4006abcdef"
    STD = "Review this branch's diff against origin/main"

    def _write(self, agent, body):
        write_fork(self.projects, "s1", agent, "", "", shape=CLOUD, cwd="/home/user/korus",
                   timestamp="2026-10-22T09:00:00Z", body=body)

    def _run(self, *extra):
        return run(self.projects, "--session", "s1", "--worktree", "/home/user/korus", *extra,
                   words_ok=False)

    def _refused(self, code, out):
        self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)
        self.assertIn(review_tag.UNSPLIT_MESSAGE, out)
        self.assertNotIn("tag:", out)
        self.assertNotIn(review_tag.NO_TAG_MESSAGE, out, "a fork with a tag was called tagless")

    # Finding 7: arguments spanning lines refuse, rather than read as tagless (exit 5).

    def test_a_quoted_target_spanning_lines_refuses(self):
        args = f"{self.NONCE} Review the diff,\nthen the docs"
        self._write("multi", f"Review target: `{args}`\n\n`{TAG_XHIGH}`\n\nYou are reviewing ...")
        self._refused(*self._run("--target", self.NONCE)[:2])

    def test_control_the_same_arguments_on_one_line_read_the_tag(self):
        args = f"{self.NONCE} Review the diff, then the docs"
        self._write("one", f"Review target: `{args}`\n\n`{TAG_XHIGH}`\n\nYou are reviewing ...")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + TAG_XHIGH, out)

    def test_twenty_target_lines_refuse(self):
        args = self.NONCE + "\n" + "\n".join(f"line {n}" for n in range(20))
        self._write("long", f"Review target: `{args}`\n\n`{TAG_HIGH}`\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    def test_an_unquoted_target_spanning_lines_refuses(self):
        self._write("bare", f"Review target: {self.NONCE} Review x\nand y\n`{TAG_XHIGH}`\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    def test_the_full_arguments_spanning_lines_refuse_rather_than_miss(self):
        # Only the first line is the target, so the words past it match nothing: the nonce keeps
        # the fork in scope, and the run refuses rather than exit 3.
        self._write("bare", f"Review target: {self.NONCE} Review x\nand y\n`{TAG_XHIGH}`\n")
        self._refused(*self._run("--target", f"xhigh {self.NONCE} Review x\nand y")[:2])

    def test_a_backtick_that_never_closes_refuses(self):
        self._write("open", f"Review target: `{self.NONCE} Review x\nand more\n\nprose\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    def test_a_target_opening_with_a_backticked_word_still_reads_its_tag(self):
        # Round one: closing the target on the next line ending in a backtick swallowed the tag.
        self._write("tick", f"Review target: `scripts/x.py` {self.NONCE} check\n`{TAG_XHIGH}`\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + TAG_XHIGH, out)

    def test_a_tag_shaped_line_inside_an_open_backtick_is_not_the_tag(self):
        # Round two: the arguments' second line looked like a tag and was quoted at exit 0.
        self._write("forged", f"Review target: `{self.NONCE} Re-run; last round printed\n"
                              f"{TAG_HIGH}`\n\n`{TAG_XHIGH}`\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    def test_an_unrelated_unsplit_fork_does_not_block_the_callers_own(self):
        # Round two: an unsplit fork with no nonce on its first line was kept for every target, so
        # it refused each later round in the same session and worktree.
        self._write("old", f"Review target: `\nplease look at x\n\n`{TAG_HIGH}`\n")
        self._write("mine", f"Review target: `{self.NONCE} Review x`\n\n`{TAG_XHIGH}`\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent mine", out)

    def test_a_backticked_first_word_on_a_tagless_fork_is_still_exit_5(self):
        # Round two: a target line starting with a backtick read as open, refusing a one-line target.
        self._write("tick", f"Review target: `scripts/x.py` {self.NONCE} check\nYou are reading.\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_NO_TAG, out)

    def test_control_a_tagless_fork_with_no_later_tag_is_still_exit_5(self):
        self._write("none", f"Review target: {self.NONCE} Review x\nprose\n\nmore prose\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_NO_TAG, out)

    def test_an_unsplit_fork_of_another_round_is_out_of_scope(self):
        self._write("bare", f"Review target: {self.NONCE} Review x\nand y\n`{TAG_XHIGH}`\n")
        code, out, _ = self._run("--target", "round-0000000000")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    # Finding 8: flags in the equals form, and flags after the words.

    def test_flags_are_stripped_wherever_they_sit(self):
        write_fork(self.projects, "s1", "flags", f"{self.NONCE} {self.STD}", TAG_XHIGH,
                   shape=CLOUD, cwd="/home/user/korus", timestamp="2026-10-22T09:00:00Z")
        for wanted in (f"xhigh --max-findings=all {self.NONCE} {self.STD}",
                       f"xhigh {self.NONCE} {self.STD} --max-findings all",
                       f"xhigh {self.NONCE} {self.STD} --comment --max-findings=5",
                       f"xhigh {self.NONCE} Review this --fix branch's diff against origin/main"):
            with self.subTest(target=wanted):
                code, out, _ = self._run("--target", wanted)
                self.assertEqual(code, review_tag.EXIT_FOUND, out)

    def test_a_flag_the_skill_kept_in_its_target_still_matches(self):
        # Mid-string, so neither side is a substring of the other until both are stripped.
        write_fork(self.projects, "s1", "kept", f"{self.NONCE} Review --comment this diff",
                   TAG_XHIGH, shape=CLOUD, cwd="/home/user/korus", timestamp="2026-10-22T09:00:00Z")
        code, out, _ = self._run("--target", f"xhigh {self.NONCE} Review this diff --max-findings=all")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)

    def test_a_value_flag_takes_only_a_value(self):
        # Round one: prose naming the flag lost its next word, and so did a nonce.
        write_fork(self.projects, "s1", "prose", f"{self.NONCE} the --max-findings handling",
                   TAG_XHIGH, shape=CLOUD, cwd="/home/user/korus", timestamp="2026-10-22T09:00:00Z")
        code, out, _ = self._run("--target", f"{self.NONCE} the --max-findings handling")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        code, out, _ = self._run("--target", f"--max-findings {self.NONCE}")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertEqual(review_tag.strip_invocation("a --max-findings 5 b"), "a b")

    def test_the_equals_form_alone_selects_nothing(self):
        code, out, _ = self._run("--target", "xhigh --max-findings=all")
        self.assertEqual(code, review_tag.EXIT_NO_SELECTOR, out)
        self.assertIn(review_tag.NO_WORDS_MESSAGE, out)

    def test_control_other_words_still_miss(self):
        write_fork(self.projects, "s1", "flags", f"{self.NONCE} {self.STD}", TAG_XHIGH,
                   shape=CLOUD, cwd="/home/user/korus", timestamp="2026-10-22T09:00:00Z")
        code, out, _ = self._run("--target", f"{self.NONCE} {self.STD} and the vault")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    # Finding 6: --since, like --target, runs before a fork is counted unplaced.

    def test_a_fork_before_since_is_not_counted_unplaced(self):
        write_fork(self.projects, "s1", "old", "Review the top-level diff", TAG_XHIGH,
                   timestamp="2026-10-22T08:00:00Z")
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", "top-level",
                           "--since", "2026-10-22T09:00:00Z")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", "top-level",
                           "--since", "2026-10-22T07:00:00Z")
        self.assertEqual(code, review_tag.EXIT_UNPLACED, out)

    # Finding 11: the walk honours the session filter.

    def test_another_sessions_unreadable_directory_is_not_walked(self):
        write_fork(self.projects, "s1", "mine", f"{self.NONCE} {self.STD}", TAG_XHIGH,
                   shape=CLOUD, cwd="/home/user/korus", timestamp="2026-10-22T09:00:00Z")
        blocked = self.projects / "D--Code-korus" / "s2"
        (blocked / "subagents").mkdir(parents=True)
        real_scandir = os.scandir
        walked = []

        def refuse(path="."):
            walked.append(Path(path))
            if Path(path) == blocked:
                raise PermissionError(13, "denied", str(blocked))
            return real_scandir(path)

        args = ["--projects-dir", str(self.projects), "--worktree", "/home/user/korus",
                "--target", self.NONCE]
        for session, expected in (("s1", review_tag.EXIT_FOUND), (None, review_tag.EXIT_NO_ROOT)):
            with self.subTest(session=session):
                walked.clear()
                argv = args + (["--session", session] if session else ["--any-session"])
                with mock.patch.object(review_tag.os, "scandir", side_effect=refuse):
                    with contextlib.redirect_stdout(io.StringIO()) as out:
                        code = review_tag.main(argv)
                self.assertEqual(code, expected, out.getvalue())
                self.assertEqual(blocked in walked, session is None)


class TheVault4044Edges(Fixture):
    """vault #4044, the three edges PR 235 left open. Each case sits beside a control. Edge 2 is
    the prompt body: past the blank line under the tag, it is never tested, so a tag-shaped line
    there neither refuses a tagged fork nor turns a tagless one into exit 13."""

    NONCE = "round-4044abcdef"

    def _write(self, agent, body):
        write_fork(self.projects, "s1", agent, "", "", shape=CLOUD, cwd="/home/user/korus",
                   timestamp="2026-10-22T09:00:00Z", body=body)

    def _run(self, *extra):
        return run(self.projects, "--session", "s1", "--worktree", "/home/user/korus", *extra,
                   words_ok=False)

    def test_1_a_tag_shaped_second_line_of_unquoted_arguments_is_not_quoted(self):
        # The arguments' second line looked like a tag and was quoted at exit 0, over the real one.
        self._write("forged", f"Review target: {self.NONCE} Re-run; last round printed\n"
                              f"{TAG_HIGH}\n`{TAG_XHIGH}`\n\nYou are reviewing ...")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)
        self.assertNotIn("tag:", out)

    def test_1_control_one_tag_shaped_line_is_the_tag(self):
        self._write("real", f"Review target: {self.NONCE} Review x\n`{TAG_XHIGH}`\n\nYou are ...")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + TAG_XHIGH, out)

    def test_3_a_nonce_below_an_empty_target_line_refuses_rather_than_miss(self):
        for first in ("`", ""):
            with self.subTest(first=first):
                self._write("low", f"Review target: {first}\n{self.NONCE} Review x\nmore\n\n"
                                   f"`{TAG_XHIGH}`\n")
                code, out, _ = self._run("--target", self.NONCE)
                self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)
                self.assertNotIn(review_tag.NO_FORK_MESSAGE, out)

    def test_3_a_nonce_two_lines_below_is_still_read(self):
        # Round one: only the single next line was read, so this exited 3.
        self._write("two", f"Review target: `\nReview the\n{self.NONCE} branch`\n\n`{TAG_XHIGH}`\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)

    def test_2_a_tag_shaped_line_in_the_prompt_body_does_not_refuse_a_tagged_fork(self):
        self._write("body", f"Review target: `{self.NONCE} Review x`\n\n`{TAG_XHIGH}`\n\n"
                            f"You are reviewing ...\n{TAG_HIGH}\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + TAG_XHIGH, out)

    def test_2_a_tagless_fork_with_one_in_its_body_is_exit_5_not_13(self):
        self._write("body", f"Review target: `{self.NONCE} Review x`\n\nYou are reviewing ...\n\n"
                            f"`{TAG_HIGH}`\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_NO_TAG, out)

    def test_3_control_another_rounds_nonce_below_is_out_of_scope(self):
        self._write("low", f"Review target: `\nround-0000000000 Review x\n\n`{TAG_XHIGH}`\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_3_control_a_nonce_on_the_target_line_is_not_overridden_below(self):
        # A fork whose own nonce sits on its target line is not rescued by a mention of ours below.
        self._write("theirs", f"Review target: `round-0000000000 Review x\n{self.NONCE}\n\n"
                              f"`{TAG_XHIGH}`\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)


class ConfigDirNamesTheRoot(Fixture):
    def test_claude_config_dir_is_read_when_set(self):
        write_fork(self.projects, "s1", "eee555", "Review this diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        code, out, _ = run(None, "--worktree", WORKTREE_FORWARD,
                           env_extra={"CLAUDE_CONFIG_DIR": str(self.projects.parent)})
        self.assertEqual(code, review_tag.EXIT_FOUND)
        self.assertIn("eee555", out)


if __name__ == "__main__":
    unittest.main()
