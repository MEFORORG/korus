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
               cwd=None, later=None, prefix=None, project="D--Code-korus"):
    sub = Path(projects) / project / session / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    meta = {"agentType": "general-purpose", "spawnDepth": 2 if shape == RELAYED else 1}
    if worktree is not None:
        meta["inheritedWorktreePath"] = worktree
        meta["parentAgentId"] = "builder01"
    (sub / f"agent-{agent}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    body = head(shape, args, tag)
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


def run(projects, *args, env_extra=None):
    env = dict(os.environ)
    # Both are set in a live session, and either would point the tool away from the fixture.
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.pop(review_tag.SESSION_ENV, None)
    env.update(env_extra or {})
    cmd = [sys.executable, str(SCRIPT)]
    if projects is not None:
        cmd += ["--projects-dir", str(projects)]
    proc = subprocess.run(
        cmd + list(args),
        capture_output=True,
        timeout=TIMEOUT_SECONDS,
        env=env,
    )
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


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

    def test_a_cwd_below_the_worktree_is_in_it_and_a_sibling_is_not(self):
        write_fork(self.projects, "s1", "inside", "Review x", TAG_XHIGH, shape=CLOUD,
                   cwd="/home/user/korus/tests", timestamp="2026-10-22T04:00:00Z")
        write_fork(self.projects, "s1", "sibling", "Review x", TAG_HIGH, shape=CLOUD,
                   cwd="/home/user/korus-other", timestamp="2026-10-22T05:00:00Z")
        _, out, _ = run(self.projects, "--worktree", "/home/user/korus")
        self.assertIn("agent inside", out)
        self.assertNotIn("sibling", out)

    def test_a_note_before_the_target_line_does_not_hide_the_fork(self):
        write_fork(self.projects, "s1", "a1", "Review this diff", TAG_XHIGH, shape=CLOUD,
                   cwd="/home/user/korus", timestamp="2026-10-22T04:00:00Z",
                   prefix="Note: findings are capped as you asked last time.")
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus")
        self.assertEqual(code, review_tag.EXIT_FOUND, out)
        self.assertIn("tag: " + TAG_XHIGH, out)


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
        self.assertIn("round 1 of 1", out)
        self.assertIn("placed by: inheritedWorktreePath", out)

    def test_a_fork_in_another_worktree_does_not_match(self):
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD,
                        "--target", "Review this branch's diff", "--latest")
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
        code, out, _ = run(self.projects, "--worktree", "/home/user/korus", "--latest",
                           env_extra={review_tag.SESSION_ENV: "mine"})
        self.assertEqual(code, review_tag.EXIT_FOUND)
        self.assertIn("agent m1", out)
        self.assertNotIn("p1", out, "a peer session's newer fork was quoted as this session's")

    def test_any_session_widens_it(self):
        # The control: the peer's fork is there to be found, so the test above is the filter.
        _, out, _ = run(self.projects, "--worktree", "/home/user/korus", "--any-session",
                        env_extra={review_tag.SESSION_ENV: "mine"})
        self.assertIn("agent p1", out)


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

    def test_both_rounds_list_oldest_first(self):
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD)
        self.assertEqual(code, review_tag.EXIT_FOUND)
        self.assertLess(out.index("r1aaaa"), out.index("r2bbbb"))
        self.assertIn("round 2 of 2", out)

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

    def test_latest_prints_the_newest_round_only(self):
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--latest")
        self.assertIn("round 2 of 2", out)
        self.assertNotIn("r1aaaa", out)

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
        _, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", "Review this")
        quotable = [line for line in out.splitlines() if not line.strip().startswith("target:")]
        self.assertGreaterEqual(len(quotable), 3)
        for line in quotable:
            self.assertNotIn("review", line.lower(), line)
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
    """Neither `inheritedWorktreePath` nor `cwd`: only a session filter can place it."""

    def setUp(self):
        super().setUp()
        write_fork(self.projects, "top1", "ccc333", "Review the top-level diff", TAG_XHIGH,
                   timestamp="2026-10-22T09:00:00Z")

    def test_without_a_session_it_is_unplaced_not_absent(self):
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--target", "top-level")
        self.assertEqual(code, review_tag.EXIT_UNPLACED)
        self.assertIn(review_tag.UNPLACED_MESSAGE, out)
        self.assertNotIn(review_tag.NO_FORK_MESSAGE, out, "a found fork was reported as none")

    def test_a_session_places_it_and_says_so(self):
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD, "--session", "top1")
        self.assertEqual(code, review_tag.EXIT_FOUND)
        self.assertIn("ccc333", out)
        self.assertIn("placed by: session only", out)


class EveryMissIsLoudAndDistinct(Fixture):
    def test_a_tree_with_no_fork_exits_no_fork(self):
        # THE PLANTED CONTROL. A projects dir holding a session and its transcript, and no fork.
        session = self.projects / "D--Code-korus"
        session.mkdir()
        (session / "s1.jsonl").write_text('{"type": "user"}\n', encoding="utf-8")
        code, out, _ = run(self.projects, "--any-worktree")
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
        code, _, _ = run(self.projects, "--any-worktree")
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

    def test_the_newest_round_without_a_tag_exits_no_tag_despite_an_older_one(self):
        write_fork(self.projects, "s1", "old111", "Review this diff", TAG_XHIGH,
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T09:00:00Z")
        write_fork(self.projects, "s1", "new222", "Review this diff", "Some other second line",
                   worktree=WORKTREE_WINDOWS, timestamp="2026-10-22T10:00:00Z")
        code, out, _ = run(self.projects, "--worktree", WORKTREE_FORWARD)
        self.assertEqual(code, review_tag.EXIT_NO_TAG)
        self.assertIn("NONE IN RECORD 0", out)
        self.assertIn(review_tag.NO_TAG_MESSAGE, out)

    def test_the_codes_are_distinct(self):
        codes = {review_tag.EXIT_FOUND, review_tag.EXIT_NO_FORK, review_tag.EXIT_NO_ROOT,
                 review_tag.EXIT_NO_TAG, review_tag.EXIT_UNPLACED, 1, 2}
        self.assertEqual(len(codes), 7, "an exit code collides with another, or with 1 or 2")


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
