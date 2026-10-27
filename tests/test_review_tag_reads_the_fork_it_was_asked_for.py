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

    def test_a_target_line_below_an_unknown_opening_refuses(self):
        # Fail closed: a guess at where a review prompt begins could take ordinary prose for one.
        # CHANGED 2026-10-23: this exited 3, no fork, and a Builder could publish `none returned`
        # over a real fork with a tag. A target line below text that is not the skill's notices
        # now refuses, exit 14. `TheNoticesAboveTheTargetLine` holds the notices that are read.
        write_fork(self.projects, "s1", "a1", "Review this diff", TAG_XHIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T04:00:00Z",
                   prefix="Note: findings are capped as you asked last time.")
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus")
        self.assertEqual(code, review_tag.EXIT_DISPLACED, out)
        self.assertIn(review_tag.DISPLACED_MESSAGE, out)
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
                 review_tag.EXIT_UNSPLIT, review_tag.EXIT_DISPLACED,
                 review_tag.EXIT_UNKNOWN_NOTICE, review_tag.EXIT_CONTESTED, 1, 2}
        self.assertEqual(len(codes), 17, "an exit code collides with another, or with 1 or 2")


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

    # The edges PR 235 handed on. Edge 1: an unquoted target whose second line is tag-shaped.

    def test_an_unquoted_target_whose_second_line_is_tag_shaped_refuses(self):
        # Quoted as the tag at exit 0 until then, here and on main before PR 235.
        self._write("forged", f"Review target: {self.NONCE} Re-run; last round printed\n"
                              f"{TAG_HIGH}\n`{TAG_XHIGH}`\n\nYou are reviewing ...")
        code, out, _ = self._run("--target", self.NONCE)
        self._refused(code, out)
        self.assertNotIn(TAG_HIGH, out)

    def test_a_second_tag_in_the_recorded_cloud_shape_refuses(self):
        self._write("two", f"Review target: `{self.NONCE} Review x`\n\n`{TAG_XHIGH}`\n\n"
                           f"`{TAG_HIGH}`\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    # Edge 3: a first line holding no words, with the nonce on line 2.

    def test_an_empty_first_line_with_the_nonce_below_refuses_rather_than_miss(self):
        self._write("empty", f"Review target: \n{self.NONCE} Review x\n`{TAG_XHIGH}`\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    def test_a_lone_backtick_with_the_nonce_below_refuses_rather_than_miss(self):
        self._write("tick", f"Review target: `\n{self.NONCE} Review x`\n\n`{TAG_XHIGH}`\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    def test_an_empty_first_line_refuses_with_no_tag_below_either(self):
        # Tagless, it read as no fork; the arguments still began on line 2.
        self._write("bare", f"Review target: \n{self.NONCE} Review x\n\nYou are reading.\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    # Round one of this change: the nonce was sought on one line only, so these read as exit 3.

    def test_the_nonce_on_line_two_below_words_refuses(self):
        self._write("words", f"Review target: `Review this branch\n{self.NONCE} diff`\n\n`{TAG_XHIGH}`\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    def test_the_nonce_on_line_three_below_an_open_backtick_refuses(self):
        self._write("deep", f"Review target: `\nReview this\n{self.NONCE} diff`\n\n`{TAG_XHIGH}`\n")
        self._refused(*self._run("--target", self.NONCE)[:2])

    def test_a_level_alone_on_the_first_line_refuses(self):
        for first in ("xhigh", "--comment"):
            with self.subTest(first=first):
                self._write("lvl", f"Review target: {first}\n{self.NONCE} Review x\n\nprose\n")
                self._refused(*self._run("--target", self.NONCE)[:2])

    def test_a_tag_shaped_argument_line_above_the_nonce_refuses_rather_than_miss(self):
        # Round two: the arguments were cut at the FIRST tag-shaped line, so this read as exit 3.
        for body in (f"Review target: `xhigh\n{TAG_HIGH}\n{self.NONCE} Review`\n\n`{TAG_XHIGH}`\n",
                     f"Review target: `Review x\n\n`{TAG_HIGH}`\n\n{self.NONCE}`\n\n`{TAG_XHIGH}`\n"):
            with self.subTest(body=body[:40]):
                self._write("above", body)
                self._refused(*self._run("--target", self.NONCE)[:2])

    def test_control_a_nonce_below_the_tag_is_not_the_forks_own(self):
        # The arguments end at the first tag-shaped line; a nonce in the prompt below is not theirs.
        self._write("below", f"Review target: `Review x\nand y`\n\n`{TAG_XHIGH}`\n\n{self.NONCE}\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_control_another_rounds_nonce_below_an_empty_line_is_out_of_scope(self):
        self._write("tick", f"Review target: `\nround-0000000000 Review x`\n\n`{TAG_XHIGH}`\n")
        code, out, _ = self._run("--target", self.NONCE)
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_control_an_empty_target_with_the_tag_next_still_reads_it(self):
        # No arguments spill, so the empty target is the whole of them.
        head = review_tag.read_head(["Review target: ", "", f"`{TAG_XHIGH}`"])
        # read_head returns a Head since korus PR 243; this read `head[2:4], (TAG_XHIGH, False)`.
        self.assertEqual((head.tag, head.refusal), (TAG_XHIGH, None))

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


class TheNoticesAboveTheTargetLine(Fixture):
    """PR 242, round two. CLI 2.1.309 builds the skill's prompt as notices, then the target line,
    so a real fork with a tag read as no fork, exit 3. The notices below are copied from that
    binary's prompt builder, with the level filled in. Each match sits beside a refusal of the
    nearest shape that is not the skill's."""

    NONCE = "round-242abcdef0"
    ARGS = f"{NONCE} Review this branch's diff against origin/main"

    # A remembered `--max-findings all`, in the fork form.
    FINDINGS = ("(Reporting every finding, as the user chose last time with `--max-findings all`."
                " Open your report with one short line telling the user this, and that passing"
                " `--max-findings default` goes back to the usual limit; that opening line reaches"
                " them with the findings.)")
    IGNORED = ("(`--max-findings` was ignored: type a whole number above zero, `all`, or `default`"
               " after it. Using the usual limit. Open your report with one short line telling the"
               " user this; that opening line reaches them with the findings.)")
    UNRECOGNIZED = ('(Ignoring unrecognized effort "xhighh"; valid: low, medium, high, xhigh,'
                    ' max. Using xhigh.)')
    LAST_USED = ("(No effort level given \u2014 reusing xhigh, the level the user typed last time."
                 " Open your report with one short line telling the user this, and that typing a"
                 " level (for example `/code-review high`) changes it; that opening line reaches"
                 " them with the findings.)")
    ULTRA = ("(Claude can't launch the cloud review directly \u2014 the user can run"
             " `claude ultrareview` from a terminal to start it. Falling back to a local"
             " xhigh-effort review for now.)")
    POST = ("(The typed `--post` applies only to the `/code-review ultra` cloud review and was"
            " ignored \u2014 this local review will not post to GitHub; `--comment` is the flag that"
            " posts local findings as inline PR comments. Tell the user this in one short line.)")

    def _body(self, *notices, gap="\n\n"):
        opening = "".join(notice + gap for notice in notices)
        return f"{opening}Review target: `{self.ARGS}`\n\n`{TAG_XHIGH}`\n\nYou are reviewing ..."

    def _write(self, agent, body, session="s1"):
        write_fork(self.projects, session, agent, "", "", shape=CLOUD, cwd="/home/user/korus",
                   timestamp="2026-10-23T09:00:00Z", body=body)

    def _main(self, target=None, session="s1"):
        out = io.StringIO()
        argv = ["--projects-dir", str(self.projects), "--session", session,
                "--worktree", "/home/user/korus", "--target", target or self.NONCE]
        with contextlib.redirect_stdout(out):
            code = review_tag.main(argv)
        return code, out.getvalue()

    def _found(self, code, out):
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + TAG_XHIGH, out)
        self.assertIn(f"target: {self.ARGS}\n", out)

    def _refused(self, code, out):
        self.assertEqual(code, review_tag.EXIT_DISPLACED, out)
        self.assertIn(review_tag.DISPLACED_MESSAGE, out)
        self.assertNotIn("tag:", out)
        self.assertNotIn(review_tag.NO_FORK_MESSAGE, out, "a fork with a tag was called absent")

    def test_control_no_notice_reads_the_tag(self):
        self._write("bare", self._body())
        self._found(*self._main())

    def test_each_measured_notice_reads_the_tag(self):
        for name in ("FINDINGS", "IGNORED", "UNRECOGNIZED", "LAST_USED", "ULTRA", "POST"):
            with self.subTest(notice=name):
                # A session each, so one notice that stops reading cannot fail the others as two.
                self._write(name, self._body(getattr(self, name)), session=name)
                self._found(*self._main(session=name))

    def test_the_most_notices_the_skill_writes_read_the_tag(self):
        # A level notice and the `--post` notice from one builder, then the `--max-findings` one.
        self._write("three", self._body(self.ULTRA, self.POST, self.FINDINGS))
        self._found(*self._main())

    def test_one_notice_past_the_limit_refuses(self):
        self._write("four", self._body(self.ULTRA, self.POST, self.FINDINGS, self.FINDINGS))
        self._refused(*self._main())

    def test_a_notice_without_its_blank_line_refuses(self):
        self._write("tight", self._body(self.FINDINGS, gap="\n"))
        self._refused(*self._main())

    def test_a_notice_with_two_blank_lines_refuses(self):
        self._write("loose", self._body(self.FINDINGS, gap="\n\n\n"))
        self._refused(*self._main())

    def test_a_notice_followed_by_prose_refuses(self):
        # Stepping two lines at a time is not the rule: the second must be blank.
        self._write("prose", self._body(self.FINDINGS, gap="\nAnd a line of prose.\n"))
        self._refused(*self._main())

    def test_a_notice_that_never_closes_its_parenthesis_refuses(self):
        # Round two: the wrapped case below fails on its opening, so it never tested the `)`.
        self._write("open", self._body("(Reporting every finding, as the user chose last time"))
        self._refused(*self._main())

    def test_a_notice_wrapped_over_two_lines_refuses(self):
        self._write("wrapped", self._body("(Reporting every finding,\nas chosen last time.)"))
        self._refused(*self._main())

    def test_an_opening_that_is_not_in_parentheses_refuses(self):
        self._write("prose", self._body("Reporting every finding, as chosen last time."))
        self._refused(*self._main())

    def test_the_target_line_is_read_from_below_the_notice(self):
        # The full arguments match too, not only the nonce: the target is the line past the notice.
        self._write("one", self._body(self.FINDINGS))
        self._found(*self._main(f"xhigh {self.ARGS}"))

    def test_a_displaced_fork_is_kept_by_its_own_nonce_alone(self):
        # Its words may not match the caller's, as with arguments spanning lines; its nonce does.
        self._write("prose", self._body("Something else first."))
        self._refused(*self._main(f"xhigh {self.ARGS} and the docs"))

    def test_a_displaced_fork_of_another_round_is_out_of_scope(self):
        self._write("other", self._body("Something else first."))
        code, out = self._main("round-0000000000")
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_a_displaced_fork_of_another_round_does_not_block_the_callers_own(self):
        other = self._body("Something else first.").replace(self.NONCE, "round-0000000000")
        self._write("old", other)
        self._write("mine", self._body(self.FINDINGS))
        code, out = self._main()
        self._found(code, out)
        self.assertIn("agent mine", out)

    def test_parenthesised_prose_that_is_no_notice_refuses(self):
        # Round one: any line in parentheses was skipped, so a helper's brief above a pasted head
        # read at exit 0 and its text landed on a `tag:` line. Only the skill's sentences skip.
        # CHANGED 2026-10-23: this refused as exit 14. One line in parentheses above a canonical
        # head now has its own refusal, exit 15, which names its opening words.
        self._write("helper", self._body("(Check this QA line for me)"))
        code, out = self._main()
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)
        self.assertNotIn("tag:", out)

    def test_a_brief_quoting_the_target_line_with_no_tag_does_not_block(self):
        # Round one: a finder's or helper's brief quoting the round's target line refused the
        # caller's own fork, exit 14, for good. With no tag after it, it is not a skill prompt.
        self._write("finder", f"You are angle A.\n\nReview target: `{self.ARGS}`\n\nFind bugs.\n")
        self._write("mine", self._body(self.FINDINGS))
        code, out = self._main()
        self._found(code, out)
        self.assertIn("agent mine", out)

    def test_a_later_target_line_carrying_the_nonce_refuses(self):
        # Round one: only the first target line was judged, so another round's line above the
        # fork's own one read as exit 3.
        self._write("two", "Note\nReview target: `other words`\n\n" + self._body())
        self._refused(*self._main())

    def test_an_indented_or_quoted_target_line_refuses(self):
        for opening in ("  ", "> "):
            with self.subTest(opening=opening):
                session = "q" if opening.strip() else "i"
                body = "Note\n" + "\n".join(opening + line for line in self._body().split("\n"))
                self._write("indented", body, session=session)
                self._refused(*self._main(session=session))

    def test_notice_shaped_prose_with_no_target_line_is_not_a_fork(self):
        self._write("prose", f"{self.FINDINGS}\n\nYou are exploring the tree.\n`{TAG_XHIGH}`\n")
        code, out = self._main()
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    # The merge with korus PR 242: its second-tag and wordless-target rules hold below a notice.

    def _unsplit(self, code, out):
        self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)
        self.assertIn(review_tag.UNSPLIT_MESSAGE, out)
        self.assertNotIn("tag:", out)

    def test_a_second_tag_below_a_notice_refuses_as_unsplit(self):
        body = self._body(self.FINDINGS) + f"\n`{TAG_XHIGH}`\n"
        self._write("two-tags", body)
        self._unsplit(*self._main())

    def test_a_wordless_target_below_a_notice_refuses_as_unsplit(self):
        # The level alone on the target line, the arguments and their nonce on the next one. No tag
        # follows, so only the wordless-target rule, not the later-tag rule, can refuse it.
        body = f"{self.FINDINGS}\n\nReview target: xhigh\n{self.ARGS}\n\nYou are reviewing ...\n"
        self._write("wordless", body)
        self._unsplit(*self._main())

    def test_a_displaced_target_spanning_lines_refuses_rather_than_miss(self):
        # Merge review: the displaced path read only the target line, so each of these exited 3.
        shapes = {
            "tick": f"Review target: `\n{self.ARGS}`",
            "wordless": f"Review target: xhigh\n{self.ARGS}",
            "words": f"Review target: Review this\n{self.ARGS}",
        }
        for name, opening in shapes.items():
            with self.subTest(shape=name):
                body = f"Something else first.\n\n{opening}\n\n`{TAG_XHIGH}`\n"
                self._write(name, body, session=name)
                self._refused(*self._main(session=name))

    def test_mutant_no_notice_skipped_fails_the_notice_case(self):
        # Mutation check: with the skip removed, the measured notice no longer reads its tag.
        self._write("one", self._body(self.FINDINGS))
        with mock.patch.object(review_tag, "NOTICE_LIMIT", 0):
            code, out = self._main()
        self.assertNotEqual(code, review_tag.EXIT_FOUND, out)
        self._refused(code, out)

    def test_mutant_displaced_read_as_absent_fails_the_refusal_case(self):
        # Mutation check: read a displaced head as no fork, the pre-fix rule, and the refusal is
        # gone: the run exits 3, the code that let a Builder publish `none returned`.
        self._write("prose", self._body("Something else first."))
        real = review_tag.read_head

        def absent(lines):
            found = real(lines)
            return review_tag.Head() if found.refusal is review_tag.Refusal.DISPLACED else found

        with mock.patch.object(review_tag, "read_head", side_effect=absent):
            code, out = self._main()
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)
        code, out = self._main()
        self._refused(code, out)


class TheRoundTwoFindingsOfPr243(Fixture):
    """PR 243 handed on seven round-two findings and two older edges. Each rule below sits beside a
    control of the nearest shape that reads the other way. The notices are the measured sentences
    in `TheNoticesAboveTheTargetLine`; the budget line is copied from CLI 2.1.309's prompt builder,
    with its count filled in."""

    NONCE = TheNoticesAboveTheTargetLine.NONCE
    ARGS = TheNoticesAboveTheTargetLine.ARGS
    FINDINGS = TheNoticesAboveTheTargetLine.FINDINGS
    LOCAL = "(Running a local xhigh-effort review and applying its findings.)"
    BUDGET = ("This diff is about 420 lines. Spawn about 3 finder subagents (min 2, max 8) \u2014"
              " scale your investigation depth to the diff size rather than using a fixed large"
              " fleet.")
    OTHER = "D:/Code/korus-wt-b"

    def _body(self, *notices, args=None, between=""):
        opening = "".join(notice + "\n\n" for notice in notices)
        return (f"{opening}Review target: `{args or self.ARGS}`\n\n{between}`{TAG_XHIGH}`\n\n"
                "You are reviewing ...")

    def _write(self, agent, body, cwd="/home/user/korus", session="s1"):
        write_fork(self.projects, session, agent, "", "", shape=CLOUD, cwd=cwd,
                   timestamp="2026-10-23T09:00:00Z", body=body)

    def _main(self, target=None, *extra, session="s1"):
        out, err = io.StringIO(), io.StringIO()
        argv = ["--projects-dir", str(self.projects), "--session", session,
                "--worktree", "/home/user/korus", "--target", target or self.NONCE, *extra]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = review_tag.main(argv)
        return code, out.getvalue(), err.getvalue()

    def _found(self, code, out, agent="mine"):
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + TAG_XHIGH, out)
        self.assertIn(f"agent {agent}", out)

    # 1. A brief that pastes the whole head refuses, even beside the caller's readable fork.
    # CHANGED 2026-10-24, takeover: such a head was set aside beside a readable fork with the same
    # tag. The readable one can be a helper's brief and the refused one the real fork, so the run
    # exited 0 naming the brief. Nothing in record 0 tells them apart, so it refuses, as on main.

    def _displaced(self, code, out):
        self.assertEqual(code, review_tag.EXIT_DISPLACED, out)
        self.assertIn(review_tag.DISPLACED_MESSAGE, out)
        self.assertNotIn(review_tag.NO_FORK_MESSAGE, out)
        self.assertNotIn("tag:", out)

    def test_1_a_brief_pasting_the_head_beside_the_callers_fork_refuses(self):
        self._write("helper", "Run this for me, as written:\n\n" + self._body())
        self._write("mine", self._body(self.FINDINGS))
        self._displaced(*self._main()[:2])

    def test_1_a_real_fork_under_a_new_notice_beside_a_canonical_brief_refuses(self):
        # The takeover probe's case B: the real fork sits under a notice no measured CLI writes,
        # and a helper's record 0 opens with the same target line and tag. At 64178ac this exited
        # 0 and named the helper as the fork.
        self._write("real", self._body("(A notice a later CLI added, reworded.)"))
        self._write("helper", self._body().replace("You are reviewing ...", "Helper brief."))
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)
        self.assertNotIn("tag:", out)
        self.assertNotIn("agent helper", out)

    def test_1_control_the_brief_alone_still_refuses(self):
        self._write("helper", "Run this for me, as written:\n\n" + self._body())
        self._displaced(*self._main()[:2])

    def test_1_beside_two_canonical_forks_the_brief_refuses_before_ambiguity(self):
        # The refusal outranks exit 7, so the brief is named rather than lost behind it.
        self._write("helper", "Run this for me, as written:\n\n" + self._body())
        self._write("mine", self._body())
        self._write("twin", self._body())
        self._displaced(*self._main()[:2])

    def test_1_control_the_callers_fork_alone_reads(self):
        self._write("mine", self._body(self.FINDINGS))
        self._found(*self._main()[:2])

    def test_1_beside_a_tagless_canonical_fork_it_still_refuses(self):
        # Round one: set aside beside any canonical fork, a displaced head holding a tag lost to
        # a tagless one, exit 5, and a fork with a tag would be published as `none returned`.
        self._write("real", "Something else first.\n\n" + self._body())
        self._write("brief", f"Review target: `{self.ARGS}`\n\nFind bugs.\n")
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_DISPLACED, out)
        self.assertNotIn(review_tag.NO_TAG_MESSAGE, out)

    def test_1_a_later_target_line_below_an_unknown_notice_refuses(self):
        # Takeover review: below an unknown notice only the first target line was matched, so
        # the round's own line further down read as no fork, exit 3. A plain opening refused 14.
        other = "Review target: `round-00000000aa old words`\n\nThen:\n\n"
        for opening, want in (("(Compare.)", review_tag.EXIT_UNKNOWN_NOTICE),
                              ("Compare.", review_tag.EXIT_DISPLACED)):
            with self.subTest(opening=opening):
                session = "p" if opening.startswith("(") else "q"
                self._write("later", f"{opening}\n\n{other}" + self._body(), session=session)
                code, out, _ = self._main(session=session)
                self.assertEqual(code, want, out)
                self.assertNotIn("tag:", out)

    # 2. A notice is skipped only as a whole measured sentence, never by its opening words.

    def test_2_prose_opening_with_a_notices_words_is_not_skipped(self):
        for session, line in (("local", "(Running a local check of the tree first.)"),
                              ("upto", "(Reporting up to three issues is plenty.)")):
            with self.subTest(line=line):
                # A session each, so one subtest's fork cannot stand in another's scope.
                self._write("helper", self._body(line), session=session)
                code, out, _ = self._main(session=session)
                self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)
                self.assertNotIn("tag:", out)

    def test_2_control_the_whole_sentence_is_skipped(self):
        self._write("mine", self._body(self.LOCAL))
        self._found(*self._main()[:2])

    def test_2_every_notice_template_is_one_line_in_parentheses(self):
        for template in review_tag.NOTICE_TEMPLATES:
            with self.subTest(template=template[:40]):
                self.assertTrue(template.startswith("(") and template.endswith(")"), template)
                self.assertNotIn("\n", template)

    # 3. A displaced brief in another worktree is not the round's fork found elsewhere.

    def test_3_a_displaced_brief_elsewhere_refuses_as_displaced_not_elsewhere(self):
        # Exit 12 sent an inline round to --worktree; exit 14's row says `(inline, no fork)`
        # still holds. Round one: dropping it instead read a real displaced fork as absent, exit 3.
        self._write("helper", "Run this for me:\n\n" + self._body(), cwd=self.OTHER)
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_DISPLACED, out)
        self.assertNotIn(review_tag.ELSEWHERE_MESSAGE, out)
        self.assertNotIn(review_tag.NO_FORK_MESSAGE, out)

    def test_3_control_a_canonical_fork_elsewhere_is_still_exit_12(self):
        self._write("mine", self._body(), cwd=self.OTHER)
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_ELSEWHERE, out)

    # 4. An unknown notice above a canonical head has its own exit, and names its opening words.

    def test_4_an_unknown_notice_refuses_with_its_own_exit_and_words(self):
        notice = "(Reporting the top findings first, as a later CLI might say it.)"
        self._write("mine", self._body(notice))
        code, out, err = self._main(None, "--verbose")
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)
        self.assertIn(review_tag.UNKNOWN_NOTICE_MESSAGE, out)
        self.assertNotIn("tag:", out)
        self.assertIn('"(Reporting the top findings first, as ..."', err)
        self.assertIn("agent mine", err)

    def test_4_without_verbose_the_words_stay_out(self):
        # They are record 0's own words, and could carry a path, so they sit behind --verbose.
        self._write("mine", self._body("(Check D:/work/korus-wt-z first.)"))
        code, out, err = self._main()
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)
        self.assertNotIn("korus-wt-z", out + err)

    def test_4_the_opening_words_are_printed_in_ascii(self):
        self._write("mine", self._body("(A dash \u2014 in a notice nobody measured.)"))
        code, _, err = self._main(None, "--verbose")
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE)
        # One escape, as a reader would search for it: round one printed it doubled.
        self.assertIn("dash \\u2014 in", err)
        self.assertNotIn("\\\\u2014", err)
        err.encode("ascii")

    def test_4_unsplit_arguments_below_an_unknown_notice_refuse_as_15(self):
        # Round one: these fell through to displaced, exit 14, under the wrong diagnosis.
        self._write("mine",
                    f"(A new notice.)\n\nReview target: `{self.NONCE} a\nb`\n\n`{TAG_XHIGH}`\n")
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)

    def test_4_control_a_measured_notice_in_the_same_place_reads(self):
        self._write("mine", self._body(self.FINDINGS))
        self._found(*self._main()[:2])

    def test_4_an_unknown_notice_above_a_tagless_target_is_no_fork(self):
        # A brief quoting the target line with no tag is no skill prompt, notice-shaped or not.
        self._write("brief",
                    "(Please look at this.)\n\nReview target: `" + self.ARGS + "`\n\nGo.\n")
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_4_a_parenthesised_brief_beside_the_callers_fork_refuses(self):
        # CHANGED 2026-10-24, takeover: this was set aside, exit 0. Like a plain-prose brief, it
        # now refuses, because the readable fork beside it may be the brief (see section 1).
        self._write("brief", self._body("(Run this for me)"))
        self._write("mine", self._body())
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)
        self.assertNotIn("tag:", out)

    # 5. One table maps each refusal to its exit and message.

    def test_5_every_refusal_carries_its_own_exit_and_message(self):
        rows = list(review_tag.Refusal)
        self.assertEqual(len({r.exit for r in rows}), len(rows))
        self.assertEqual(len({r.message for r in rows}), len(rows))
        self.assertEqual(review_tag.Refusal.UNKNOWN_NOTICE.exit, review_tag.EXIT_UNKNOWN_NOTICE)
        with self.assertRaises(AttributeError):
            review_tag.Refusal.DISPLACD  # noqa: B018 -- a typo fails loudly

    def test_5_a_refusal_lands_in_its_own_list_never_in_forks(self):
        self._write("mine", self._body("(A notice a later CLI added.)"))
        result = review_tag.scan([self.projects], review_tag.Filters(
            "/home/user/korus", self.NONCE, "s1", None))
        self.assertEqual(result.forks, [])
        self.assertEqual(len(result.refused[review_tag.Refusal.UNKNOWN_NOTICE]), 1)

    # 6. A transcript with no target line is ruled out before it is copied or scanned for tags.

    def test_6_no_target_line_means_no_tag_scan(self):
        lines = [f"line {n}" for n in range(200)] + [f"`{TAG_XHIGH}`"]
        with mock.patch.object(review_tag, "is_tag", wraps=review_tag.is_tag) as probe:
            self.assertEqual(review_tag.displaced_heads(lines), [])
        self.assertEqual(probe.call_count, 0)

    def test_6_control_a_target_line_is_still_scanned_and_kept(self):
        # The merge with main: displaced_targets became displaced_heads, PR 243's one reader.
        lines = ["Note", f"Review target: `{self.ARGS}`", "", f"`{TAG_XHIGH}`"]
        read = [(h.target, h.tag) for h in review_tag.displaced_heads(lines)]
        self.assertEqual(read, [(self.ARGS, TAG_XHIGH)])
        self.assertEqual(review_tag.displaced_heads(lines[:2]), [], "no tag after it")

    # Round two of this work. It set aside only a head carrying the readable fork's own tag; since
    # the takeover nothing is set aside, and these still refuse.

    def test_r2_a_real_fork_under_a_new_notice_is_not_set_aside_for_a_brief(self):
        # The fork under the unknown notice ran at xhigh; a brief pasted a high head. Quoting the
        # brief's tag at exit 0 would publish the wrong level.
        self._write("real", self._body("(A notice a later CLI added.)"))
        self._write("brief", self._body().replace(TAG_XHIGH, TAG_HIGH))
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)
        self.assertNotIn("tag:", out)

    def test_r2_a_displaced_fork_with_another_tag_still_refuses(self):
        self._write("real", "Something else first.\n\n" + self._body())
        self._write("rerun", self._body().replace(TAG_XHIGH, TAG_HIGH))
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_DISPLACED, out)
        self.assertNotIn("tag:", out)

    def test_r2_unsplit_arguments_under_a_new_notice_keep_the_fork_by_its_nonce(self):
        # The full arguments match only the first target line, so the nonce alone keeps it.
        self._write("mine", f"(A new notice.)\n\nReview target: `{self.NONCE} Review\nthis diff`"
                            f"\n\n`{TAG_XHIGH}`\n")
        code, out, _ = self._main(f"{self.NONCE} Review this diff")
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)

    def test_r2_a_wrapped_line_with_its_own_backtick_and_two_tags_refuses(self):
        self._write("mine",
                    f"Review target: `{self.NONCE} quote `x`\n{TAG_HIGH}`\n\n`{TAG_XHIGH}`\n")
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)
        self.assertNotIn("tag:", out)

    def test_r2_a_parenthesised_brief_elsewhere_refuses_rather_than_exit_12(self):
        self._write("brief", self._body("(Run this for me)"), cwd=self.OTHER)
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNKNOWN_NOTICE, out)
        self.assertNotIn(review_tag.ELSEWHERE_MESSAGE, out)

    def test_r2_beside_a_canonical_fork_elsewhere_exit_12_stands(self):
        # Takeover: a refused head elsewhere outranked a canonical fork elsewhere, so the round
        # was refused (14 or 15) where its fork was found in another worktree. Exit 12 says where.
        for name, opening in (("unknown", "(Run this for me)"), ("displaced", "Run this:")):
            with self.subTest(head=name):
                body = (self._body(opening) if opening.startswith("(")
                        else opening + "\n\n" + self._body())
                self._write("brief", body, cwd=self.OTHER, session=name)
                self._write("real", self._body(), cwd=self.OTHER, session=name)
                code, out, _ = self._main(session=name)
                self.assertEqual(code, review_tag.EXIT_ELSEWHERE, out)
                self.assertIn(review_tag.ELSEWHERE_MESSAGE, out)

    def test_r2_the_rerun_exit_12_asks_for_refuses_on_what_it_finds(self):
        # Review of 30f1c88: exit 12 is not a result. Rerun in that worktree, the brief is in
        # scope there, so the round refuses rather than read the head beside it.
        self._write("brief", "Run this:\n\n" + self._body(), cwd=self.OTHER)
        self._write("real", self._body(), cwd=self.OTHER)
        code, out, _ = self._main(None, "--worktree", self.OTHER)
        self.assertEqual(code, review_tag.EXIT_DISPLACED, out)

    def test_r2_a_tagless_head_elsewhere_does_not_unlock_exit_12(self):
        # Review of 30f1c88: any head elsewhere unlocked exit 12, a tagless finder brief too, so
        # a displaced head holding a tag lost to it, the round-one rule in another worktree.
        self._write("real", "Something else first.\n\n" + self._body(), cwd=self.OTHER)
        self._write("brief", f"Review target: `{self.ARGS}`\n\nFind bugs.\n", cwd=self.OTHER)
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_DISPLACED, out)

    def test_r2_a_refused_head_elsewhere_contests_a_fork_here(self):
        # CHANGED 2026-10-27, vault #4121: this was out of scope, exit 0. The same files, with the
        # names swapped, are the real fork displaced elsewhere and a helper's pasted head here, and
        # exit 0 named the helper. It now refuses, exit 16. Review of 30f1c88 feared a brief
        # elsewhere refusing the caller's fork for good; a fresh round clears it, as
        # `TheHeadElsewhereContestsTheForkHere` shows.
        self._write("brief", "Run this:\n\n" + self._body(), cwd=self.OTHER)
        self._write("mine", self._body())
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_CONTESTED, out)
        self.assertNotIn("tag:", out)

    def test_r2_control_a_refused_head_here_still_outranks_exit_12(self):
        self._write("brief", "Run this:\n\n" + self._body())
        self._write("real", self._body(), cwd=self.OTHER)
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_DISPLACED, out)

    def test_r2_a_tagless_brief_under_a_notice_with_an_open_backtick_is_no_fork(self):
        self._write("brief", f"(Please look at this.)\n\nReview target: `{self.NONCE} fix the"
                             " `x` y\n\nGo now.\n")
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    # Edge from PR 242: one literal backtick inside a one-line target.

    def test_a_one_line_target_holding_one_backtick_reads_its_tag(self):
        args = f"{self.NONCE} Check the `--max-findings flag"
        self._write("mine", self._body(args=args))
        code, out, _ = self._main()
        self._found(code, out)
        self.assertIn(f"target: {args}\n", out)

    def test_control_a_backtick_left_open_at_line_end_still_refuses(self):
        self._write("mine", f"Review target: `{self.NONCE} Check the\nflag`\n\n`{TAG_XHIGH}`\n")
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)

    def test_control_a_wrapped_first_line_spanning_lines_still_refuses(self):
        # Wrapped whole on its first line, then more arguments: the later tag still refuses it.
        self._write("mine", f"Review target: `{self.NONCE} a `b`\nc`\n\n`{TAG_XHIGH}`\n")
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)

    # Edge from PR 243: the finder-budget line between the target line and the tag.

    def test_the_budget_line_is_skipped_once(self):
        self._write("mine", self._body(between=self.BUDGET + "\n\n"))
        self._found(*self._main()[:2])

    def test_control_another_line_in_its_place_still_refuses(self):
        self._write("mine", self._body(between="This diff is long; spawn many.\n\n"))
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)

    def test_control_two_budget_lines_refuse(self):
        self._write("mine", self._body(between=(self.BUDGET + "\n\n") * 2))
        code, out, _ = self._main()
        self.assertEqual(code, review_tag.EXIT_UNSPLIT, out)


class ConfigDirNamesTheRoot(Fixture):
    def test_claude_config_dir_is_read_when_set(self):
        write_fork(self.projects, "s1", "eee555", "Review this diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        code, out, _ = run(None, "--worktree", WORKTREE_FORWARD,
                           env_extra={"CLAUDE_CONFIG_DIR": str(self.projects.parent)})
        self.assertEqual(code, review_tag.EXIT_FOUND)
        self.assertIn("eee555", out)


class TheHeadElsewhereContestsTheForkHere(Fixture):
    """Vault #4121. A real fork that refuses in another worktree was out of scope beside a helper's
    canonical head that read here, so the run exited 0 and named the helper. The cases are the
    row's probe table, rebuilt from its descriptions: the original probe scripts lived in a
    scratchpad and are gone. Each fail-open case exited 0 on korus `main` at 20af3e6.

    Nothing in record 0 or the meta tells a real fork from a helper that pasted its head, in one
    worktree or across two. So a head elsewhere carrying the round's nonce contests a fork that
    reads here, exit 16. PR 244 kept such a head out of scope, because a brief elsewhere then
    "refused a readable fork for good". A pasted head carries the old round's nonce, so a fresh
    round clears it; the last cases hold that. Record times do not discriminate: code-review
    round two of this work defeated a time rule with a helper written before the round."""

    NONCE = "round-4121abcdef"
    FRESH = "round-4121fedcba"
    HERE = "D:/probe/wt"
    B = "D:/probe/wt-b"
    C = "D:/probe/wt-c"
    TAG_LOW = "low effort \u2192 1 inline angle \u2192 \u22645 findings"
    UNKNOWN = "(A notice a later CLI added, reworded.)"
    #: The real fork first, then the helper that pasted it.
    EARLY = "2026-10-24T09:00:00Z"
    LATE = "2026-10-24T09:05:00Z"

    def _head(self, nonce=None, tag=TAG_XHIGH, opening="", tail="You are reviewing ..."):
        return (f"{opening}Review target: `{nonce or self.NONCE} Review this branch's diff`\n\n"
                f"`{tag}`\n\n{tail}")

    def _write(self, agent, body, cwd, session="s1", timestamp=EARLY):
        write_fork(self.projects, session, agent, "", "", shape=CLOUD, cwd=cwd,
                   timestamp=timestamp, body=body)

    def _real_unknown(self, cwd):
        self._write("bREAL", self._head(opening=self.UNKNOWN + "\n\n"), cwd)

    def _helper(self, cwd, tag=TAG_XHIGH):
        self._write("bHELP", self._head(tag=tag, tail="Helper brief."), cwd, timestamp=self.LATE)

    def _probe(self, worktree=None, nonce=None):
        # The probe's call: --target <nonce> --worktree <wt> --any-session --projects-dir --ascii.
        out = io.StringIO()
        argv = ["--target", nonce or self.NONCE, "--worktree", worktree or self.HERE,
                "--any-session", "--projects-dir", str(self.projects), "--ascii"]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = review_tag.main(argv)
        return code, out.getvalue()

    def _contested(self, code, out):
        self.assertEqual(code, review_tag.EXIT_CONTESTED, out)
        self.assertIn(review_tag.CONTESTED_MESSAGE, out)
        self.assertNotIn("tag:", out, "a contested run printed a quotable tag")

    # The fail-open cases.

    def test_p2_a_real_fork_under_an_unknown_notice_elsewhere_contests_a_helper_here(self):
        self._real_unknown(self.B)
        self._helper(self.HERE)
        self._contested(*self._probe())

    def test_p2b_a_displaced_real_fork_elsewhere_contests_a_helper_here(self):
        self._write("bREAL", self._head(opening="Something else first.\n\n"), self.B)
        self._helper(self.HERE)
        self._contested(*self._probe())

    def test_p2c_a_helper_with_another_level_prints_no_tag(self):
        # The round's target says xhigh; main printed the helper's low tag at exit 0.
        self._real_unknown(self.B)
        self._helper(self.HERE, tag=self.TAG_LOW)
        code, out = self._probe(nonce=f"xhigh {self.NONCE}")
        self.assertNotIn("low effort", out)
        self._contested(code, out)

    def test_f1_the_rerun_exit_12_advises_is_contested(self):
        # The helper is listed as a candidate, never as the fork read, and its tag never prints.
        self._real_unknown(self.B)
        self._helper(self.C, tag=self.TAG_LOW)
        code, out = self._probe(worktree=self.C)
        self._contested(code, out)
        self.assertIn("agent bREAL | another worktree", out)
        self.assertIn("agent bHELP | here", out)
        self.assertNotIn("fork | ", out)
        self.assertNotIn("low effort", out)

    def test_a_readable_head_elsewhere_contests_a_fork_here_too(self):
        # The same argument with nothing refused: either canonical head could be the round's.
        self._write("bREAL", self._head(), self.B)
        self._helper(self.HERE)
        self._contested(*self._probe())

    # The controls, whose exits do not change.

    def test_f1_control_the_first_call_is_still_exit_12(self):
        self._real_unknown(self.B)
        self._helper(self.C)
        code, out = self._probe()
        self.assertEqual(code, review_tag.EXIT_ELSEWHERE, out)

    def test_p8_control_a_readable_fork_elsewhere_alone_is_exit_12(self):
        self._write("bREAL", self._head(), self.B)
        code, out = self._probe()
        self.assertEqual(code, review_tag.EXIT_ELSEWHERE, out)

    def test_p9_control_a_readable_fork_here_alone_reads(self):
        self._write("bREAL", self._head(), self.HERE)
        code, out = self._probe()
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent bREAL", out)
        self.assertIn("tag: xhigh effort -> 10 inline angles", out)

    def test_p2d_control_a_tagless_helper_is_still_exit_5(self):
        # A tagless fork quotes no tag, so it names no wrong level.
        self._real_unknown(self.B)
        self._write("bHELP", f"Review target: `{self.NONCE} Review this branch's diff`\n\nGo.\n",
                    self.HERE)
        code, out = self._probe()
        self.assertEqual(code, review_tag.EXIT_NO_TAG, out)

    # The trade PR 244 named: a brief elsewhere must not block a reading for good.

    def test_a_fresh_round_clears_a_brief_elsewhere(self):
        self._write("brief", "Run this:\n\n" + self._head(), self.B)
        self._write("again", self._head(nonce=self.FRESH), self.HERE)
        code, out = self._probe(nonce=self.FRESH)
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent again", out)

    def test_a_helper_written_before_the_real_fork_still_contests(self):
        # Round two of this work: a time rule exempted a head elsewhere newer than the fork here.
        # A helper's head can be written before the round, so the real fork was exempted and the
        # helper's low tag quoted. Order is not evidence; every order contests.
        for name, opening in (("displaced", "Run this:\n\n"), ("unknown", self.UNKNOWN + "\n\n"),
                              ("canonical", "")):
            with self.subTest(head=name):
                # A tree each, so one subtest's head cannot contest for another's.
                self.projects = Path(self._tmp.name) / ("projects-" + name)
                self.projects.mkdir()
                self._write("bHELP", self._head(tag=self.TAG_LOW, tail="Helper brief."),
                            self.HERE)
                self._write("real" + name, opening + self._head(), self.B, timestamp=self.LATE)
                code, out = self._probe()
                self._contested(code, out)
                self.assertNotIn("low effort", out)

    def test_since_does_not_drop_the_head_that_contests(self):
        # Round two of this work: --since between the real fork and the helper dropped the real
        # fork before it could contest, and the helper's low tag was quoted.
        self._real_unknown(self.B)
        self._helper(self.HERE, tag=self.TAG_LOW)
        out = io.StringIO()
        argv = ["--target", self.NONCE, "--worktree", self.HERE, "--any-session", "--ascii",
                "--projects-dir", str(self.projects), "--since", "2026-10-24T09:02:00Z"]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = review_tag.main(argv)
        self._contested(code, out.getvalue())

    def _since(self, nonce=None):
        out = io.StringIO()
        argv = ["--target", nonce or self.NONCE, "--worktree", self.HERE, "--any-session",
                "--ascii", "--projects-dir", str(self.projects), "--since", "2026-10-24T09:02:00Z"]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = review_tag.main(argv)
        return code, out.getvalue()

    def test_since_does_not_drop_an_older_real_fork_here(self):
        # Manager review of 22fbe10: an older real fork here, a newer low-tag helper here, and
        # --since between them read exit 0 with the low tag. The nonce keeps both: ambiguous.
        self._write("bREAL", self._head(), self.HERE)
        self._helper(self.HERE, tag=self.TAG_LOW)
        code, out = self._since()
        self.assertEqual(code, review_tag.EXIT_AMBIGUOUS, out)
        self.assertNotIn("low effort", out)

    def test_control_since_still_drops_a_different_rounds_head(self):
        # A head of another round that only --since excludes: a --no-nonce search for words both
        # rounds share. Without --since both match; with it, only the later one does.
        self._write("old", self._head(nonce=self.FRESH), self.HERE)
        self._write("mine", self._head(), self.HERE, timestamp=self.LATE)
        argv = ["--target", "Review this branch's diff", "--no-nonce", "--worktree", self.HERE,
                "--any-session", "--projects-dir", str(self.projects)]
        for since, want in ((None, review_tag.EXIT_AMBIGUOUS),
                            ("2026-10-24T09:02:00Z", review_tag.EXIT_NOT_ATTRIBUTABLE)):
            with self.subTest(since=since):
                out = io.StringIO()
                extra = ["--since", since] if since else []
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    code = review_tag.main(argv + extra)
                self.assertEqual(code, want, out.getvalue())
                if since:
                    self.assertIn("agent mine", out.getvalue())
                    self.assertNotIn("agent old", out.getvalue())

    def test_a_tagless_unsplit_head_elsewhere_does_not_contest(self):
        # Round two of this work: an odd backtick refuses as unsplit with no tag-shaped line, and
        # a target line alone is no reading, so it does not contest.
        self._write("relay", f"Review target: `{self.NONCE} Review this branch's diff\n\nRelay.",
                    self.B)
        self._write("mine", self._head(), self.HERE, timestamp=self.LATE)
        code, out = self._probe()
        self.assertEqual(code, review_tag.EXIT_FOUND, out)

    def test_a_blockquoted_head_elsewhere_contests(self):
        # Manager review of 22fbe10: tag_shaped read raw lines while the head was read with a
        # leading > stripped, so a blockquoted paste elsewhere did not contest.
        quoted = "\n".join("> " + line for line in self._head().splitlines())
        self._write("real", "Forwarded:\n\n" + quoted, self.B)
        self._helper(self.HERE)
        self._contested(*self._probe())

    def _unread_elsewhere(self, content, agent="bREAL"):
        sub = self.projects / "D--probe" / "s1" / "subagents"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / f"agent-{agent}.meta.json").write_text(
            json.dumps({"inheritedWorktreePath": self.B}), encoding="utf-8")
        (sub / f"agent-{agent}.jsonl").write_text(content, encoding="utf-8")

    def test_an_unread_fork_elsewhere_holding_the_nonce_refuses_beside_a_fork_here(self):
        # Manager review of 22fbe10: a fork elsewhere whose record 0 could not be read was dropped,
        # so the helper here read at exit 0. Its raw text holds the nonce, past the first newline
        # too, so it may be the round's real fork: it refuses as unread.
        self._unread_elsewhere('{"type": "user", "message": {"content": "(A notice.)\n\n'
                               f'Review target: `{self.NONCE} Review this')
        self._helper(self.HERE)
        code, out = self._probe()
        self.assertEqual(code, review_tag.EXIT_UNREAD, out)
        self.assertIn(review_tag.UNREAD_ELSEWHERE_MESSAGE, out)
        self.assertNotIn("tag:", out)

    def test_an_unrelated_unread_transcript_elsewhere_does_not_refuse(self):
        # Manager review of 90e52ee: any unreadable transcript elsewhere refused every reading.
        # Without the round's nonce in its raw text, it is out of scope.
        for name, content in (("empty", ""), ("truncated", '{"type": "user", "mess'),
                              ("another round", '{"message": "Review target: `round-00000000ab')):
            with self.subTest(transcript=name):
                self._unread_elsewhere(content, agent="other")
                self._write("mine", self._head(), self.HERE)
                code, out = self._probe()
                self.assertEqual(code, review_tag.EXIT_FOUND, out)

    def test_control_an_unread_fork_elsewhere_alone_is_still_no_fork(self):
        self._unread_elsewhere('{"type": "user", "mess')
        code, out = self._probe()
        self.assertEqual(code, review_tag.EXIT_NO_FORK, out)

    def test_verbose_names_the_unknown_notice_that_contests(self):
        self._real_unknown(self.B)
        self._helper(self.HERE)
        out, err = io.StringIO(), io.StringIO()
        argv = ["--target", self.NONCE, "--worktree", self.HERE, "--any-session", "--verbose",
                "--projects-dir", str(self.projects)]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = review_tag.main(argv)
        self.assertEqual(code, review_tag.EXIT_CONTESTED, out.getvalue())
        self.assertIn("the unknown notice opens", err.getvalue())
        self.assertIn(self.B, err.getvalue())

    def test_a_tagless_head_elsewhere_does_not_contest(self):
        # A target line alone is no reading, here or elsewhere.
        self._write("relay", f"Review target: `{self.NONCE} Review this branch's diff`\n\nRelay.",
                    self.B)
        self._write("mine", self._head(), self.HERE, timestamp=self.LATE)
        code, out = self._probe()
        self.assertEqual(code, review_tag.EXIT_FOUND, out)

    def test_control_the_old_round_stays_contested(self):
        self._write("brief", "Run this:\n\n" + self._head(), self.B)
        self._write("mine", self._head(), self.HERE)
        self._write("again", self._head(nonce=self.FRESH), self.HERE)
        self._contested(*self._probe())


class OneFileReachedTwiceIsOneFork(Fixture):
    """Vault #4121 step 8 (#3963's M14): a projects directory reached through a junction listed one
    fork twice, so a QA tag read exited 7. A file is now one fork however many paths reach it."""

    NONCE = "round-3963abcdef"
    HERE = "D:/probe/wt"

    def setUp(self):
        super().setUp()
        write_fork(self.projects, "s1", "only", f"{self.NONCE} Review x", TAG_XHIGH, shape=CLOUD,
                   cwd=self.HERE, timestamp="2026-10-24T09:00:00Z", project="D--probe-wt")

    def _main(self, *roots):
        out = io.StringIO()
        argv = ["--target", self.NONCE, "--worktree", self.HERE, "--any-session", "--ascii"]
        for root in roots:
            argv += ["--projects-dir", str(root)]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = review_tag.main(argv)
        return code, out.getvalue()

    def _found(self, code, out):
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("agent only", out)

    def _junction(self, link, target):
        if os.name != "nt":
            self.skipTest("a junction is a Windows directory link")
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                              capture_output=True, timeout=TIMEOUT_SECONDS)
        if made.returncode != 0 or not link.exists():
            self.skipTest("mklink /J did not make a junction here")

    def test_control_one_root_reads(self):
        self._found(*self._main(self.projects))

    def test_one_directory_named_twice_is_one_fork(self):
        self._found(*self._main(self.projects, self.projects / ".." / "projects"))

    def test_a_projects_dir_reached_through_a_junction_is_one_fork(self):
        link = Path(self._tmp.name) / "projects-link"
        self._junction(link, self.projects)
        self._found(*self._main(self.projects, link))

    def test_a_project_junctioned_inside_the_projects_dir_is_one_fork(self):
        link = self.projects / "D--probe-wt-link"
        self._junction(link, self.projects / "D--probe-wt")
        self._found(*self._main(self.projects))

    def test_control_two_files_with_one_nonce_stay_ambiguous(self):
        # The identity is the file's, not its content's: a copy is a second fork.
        write_fork(self.projects, "s2", "copy", f"{self.NONCE} Review x", TAG_XHIGH, shape=CLOUD,
                   cwd=self.HERE, timestamp="2026-10-24T09:00:00Z", project="D--probe-wt")
        code, out = self._main(self.projects)
        self.assertEqual(code, review_tag.EXIT_AMBIGUOUS, out)


if __name__ == "__main__":
    unittest.main()
