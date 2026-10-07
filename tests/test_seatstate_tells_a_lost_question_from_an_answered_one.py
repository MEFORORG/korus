"""seatstate.py tells a question the Owner answered from one that ended with no answer.

WHAT THIS EXISTS FOR. The script paired an AskUserQuestion `tool_use` against ANY `tool_result`
carrying its id, so an ask counted as answered the moment a result row existed. Two kinds of result
are not answers, and both were measured on this machine on 2026-10-05 (UTC):

  * the session restarted while suspended on the dialog, and the harness wrote a result in the
    ask's place: `is_error` true, content opening `[Tool call interrupted: the session ended`;
  * the dialog was dismissed or timed out: `is_error` true, `Tool permission request aborted`.

In both the script printed `WORKING | ... | asks seen N, all answered`. No answer was recorded,
and no dialog was left on screen to show there had been a question.

THE RULE IS READ OFF THE ROW, NOT OFF ITS WORDING. Over 907 asks in 345 transcripts under 21 days
old, every answered result carried a top-level `toolUseResult` object holding `answers`, and every
other result carried a string there. The answered content opened two different ways across CLI
versions, on 650 and 241 rows, so the opening words are not the instrument. One case here pins the
older wording as answered for that reason.

THE OWNER DECLINING IS NOT A LOSS. 15 of the 22 results without answers were the Owner rejecting
the dialog, marked `toolUseResult: "User rejected tool use"`. The Owner saw that question. Calling
it lost would make the new token wrong two times in three, so it has its own count and never fires
the token. Anything the script cannot place reads as lost, which is the direction that costs less.

EVERY FIXTURE IS SYNTHETIC. The measured transcripts hold real questions and are not copied here.
Each row is shaped like the harness's own and holds no real question, with timestamps set relative
to now so the WORKING and IDLE arms are both reachable. The script is run as a subprocess, its real entry point.

WHAT main DID WITH THESE, at origin/main `3732801`: 17 of the 21 fail. The four that pass there
are the two open-ask cases and the two cases either side of the idle threshold, which pin
behaviour this change must not move. The two not-an-ask cases fail there only on the wording of
the count, which proves nothing about what they are for. So those six were each run against a
planted fault instead: a scan that matches the tool's name anywhere in a line, a scan that counts
every failed result as a lost ask, a main with the blocked branch removed, a main that always says
WORKING, and the threshold moved to 4 and to 24. Each fault reddens its cases.

Six more faults came from this change's own two QA passes, each of which passed every case
before its case was added: the last result row wins, the ask time printed as the end time, any
string opening `User` read as a decline, an object with no answers read as an answer, an error
with no marker read as a decline, and a loss ranked above a decline.
"""
import datetime as dt
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "board" / "seatstate.py"


def at(minutes_ago):
    then = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)
    return then.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def row(kind, minutes_ago, content, **extra):
    entry = {"type": kind, "timestamp": at(minutes_ago),
             "message": {"role": kind, "content": content}}
    entry.update(extra)
    return entry


def turn(minutes_ago, text="Working."):
    return row("assistant", minutes_ago, [{"type": "text", "text": text}])


def ask(tid, minutes_ago):
    return row("assistant", minutes_ago, [{
        "type": "tool_use", "id": tid, "name": "AskUserQuestion",
        "input": {"questions": [{"question": "Which one?", "options": []}]}}])


def result(tid, minutes_ago, content, tool_use_result, is_error=False):
    block = {"type": "tool_result", "tool_use_id": tid, "content": content}
    if is_error:
        block["is_error"] = True
    return row("user", minutes_ago, [block], toolUseResult=tool_use_result)


def answered(tid, minutes_ago, opening="Your questions have been answered:"):
    return result(tid, minutes_ago, opening + ' "Which one?"="The first"',
                  {"questions": [{"question": "Which one?"}], "answers": {"Which one?": "The first"}})


def interrupted(tid, minutes_ago):
    text = ("[Tool call interrupted: the session ended before this call's result was recorded. "
            "It may or may not have completed.]")
    return result(tid, minutes_ago, text, text, is_error=True)


def aborted(tid, minutes_ago):
    return result(tid, minutes_ago, "Tool permission request aborted",
                  "Error: Tool permission request aborted", is_error=True)


def declined(tid, minutes_ago):
    return result(tid, minutes_ago, "The user doesn't want to proceed with this tool use.",
                  "User rejected tool use", is_error=True)


class SeatState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def read(self, *entries):
        path = Path(self.tmp.name) / "transcript.jsonl"
        path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        done = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        self.assertEqual(len(lines), 1, "the script prints exactly one line: %r" % done.stdout)
        return lines[0]

    def state(self, line):
        return line.split(" | ")[0]


class AnAnswerIsCounted(SeatState):
    def test_an_answered_ask_is_counted_as_answered(self):
        line = self.read(ask("toolu_a", 9), answered("toolu_a", 8), turn(1))
        self.assertEqual(self.state(line), "WORKING")
        self.assertIn("asks seen 1: 1 answered, 0 declined, 0 lost", line)

    def test_the_older_wording_of_an_answer_is_still_an_answer(self):
        # 241 of the 891 answered results measured opened this way. A rule keyed on the newer
        # opening would call every one of them lost.
        line = self.read(ask("toolu_a", 9), answered("toolu_a", 8, "The user answered:"), turn(1))
        self.assertEqual(self.state(line), "WORKING")
        self.assertIn("1 answered, 0 declined, 0 lost", line)

    def test_a_seat_quiet_for_twenty_minutes_reads_idle(self):
        line = self.read(ask("toolu_a", 90), answered("toolu_a", 80), turn(20))
        self.assertEqual(line.split(" | ")[:2], ["IDLE", "0h 20m since its own last turn"])

    def test_a_seat_quiet_for_under_twenty_minutes_reads_working(self):
        line = self.read(ask("toolu_a", 90), answered("toolu_a", 80), turn(19))
        self.assertEqual(line.split(" | ")[:2], ["WORKING", "0h 19m since its own last turn"])

    def test_no_line_claims_every_ask_was_answered(self):
        # The retired detail. It was printed over an interrupted ask, which is the defect.
        line = self.read(ask("toolu_a", 9), answered("toolu_a", 8), turn(1))
        self.assertNotIn("all answered", line)


class AnOpenAskStillBlocks(SeatState):
    def test_an_ask_with_no_result_reads_blocked_exactly_as_before(self):
        line = self.read(turn(200), ask("toolu_a", 125))
        fields = line.split(" | ")
        self.assertEqual(fields[0], "BLOCKED-ON-A-QUESTION")
        self.assertEqual(fields[1], "waiting 2h 05m")
        self.assertTrue(fields[2].startswith("asked "), line)
        self.assertTrue(line.endswith("-- ONLY THE OWNER CAN CLEAR THIS"), line)

    def test_an_open_ask_outranks_an_earlier_lost_one(self):
        # A suspended seat cannot be woken, so that reading is the one the reader must get.
        line = self.read(ask("toolu_a", 90), interrupted("toolu_a", 60), ask("toolu_b", 30))
        self.assertEqual(self.state(line), "BLOCKED-ON-A-QUESTION")


class ALostAskIsNamed(SeatState):
    def test_an_interrupted_ask_that_is_the_newest_reads_lost(self):
        entries = [turn(200), ask("toolu_a", 150), interrupted("toolu_a", 30), turn(2)]
        line = self.read(*entries)
        self.assertEqual(self.state(line), "QUESTION-LOST")
        self.assertIn("asked %s, ended unanswered %s " % (entries[1]["timestamp"],
                                                          entries[2]["timestamp"]), line)
        self.assertIn("asks seen 1: 0 answered, 0 declined, 1 lost", line)

    def test_an_aborted_ask_that_is_the_newest_reads_lost(self):
        entries = [turn(200), ask("toolu_a", 150), aborted("toolu_a", 30), turn(2)]
        line = self.read(*entries)
        self.assertEqual(self.state(line), "QUESTION-LOST")
        self.assertIn("asked " + entries[1]["timestamp"], line)

    def test_a_lost_ask_is_named_however_long_the_seat_has_been_quiet(self):
        # IDLE would send the reader to nudge the seat, and a nudge cannot answer the question.
        # The word is kept at the end of the line, because the token took its place.
        line = self.read(ask("toolu_a", 600), interrupted("toolu_a", 500))
        self.assertEqual(self.state(line), "QUESTION-LOST")
        self.assertTrue(line.endswith("; otherwise IDLE"), line)

    def test_the_lost_line_says_working_where_the_seat_is_still_taking_turns(self):
        line = self.read(ask("toolu_a", 150), interrupted("toolu_a", 30), turn(2))
        self.assertTrue(line.endswith("; otherwise WORKING"), line)

    def test_the_lost_line_keeps_the_age_of_the_seats_last_turn(self):
        line = self.read(ask("toolu_a", 150), interrupted("toolu_a", 30), turn(3))
        self.assertEqual(line.split(" | ")[:2], ["QUESTION-LOST", "0h 03m since its own last turn"])

    def test_a_result_that_is_an_error_is_lost_even_where_the_row_carries_answers(self):
        entry = answered("toolu_a", 30)
        entry["message"]["content"][0]["is_error"] = True
        line = self.read(ask("toolu_a", 150), entry, turn(2))
        self.assertEqual(self.state(line), "QUESTION-LOST")

    def test_a_result_the_script_cannot_place_reads_lost(self):
        # Unknown reads as lost, never as answered and never as declined. Three shapes nobody
        # measured: no toolUseResult at all, an error with none, and an object with no answers.
        bare = row("user", 30, [{"type": "tool_result", "tool_use_id": "toolu_a", "content": "?"}])
        failed = row("user", 30, [{"type": "tool_result", "tool_use_id": "toolu_a",
                                   "content": "?", "is_error": True}])
        empty = result("toolu_a", 30, "?", {"questions": [{"question": "Which one?"}]})
        for name, entry in (("bare", bare), ("failed", failed), ("no answers", empty)):
            with self.subTest(shape=name):
                line = self.read(ask("toolu_a", 150), entry, turn(2))
                self.assertEqual(self.state(line), "QUESTION-LOST")
                self.assertIn("asks seen 1: 0 answered, 0 declined, 1 lost", line)


class ALaterAskSupersedesALostOne(SeatState):
    def test_a_lost_ask_followed_by_an_answered_one_does_not_read_lost(self):
        line = self.read(ask("toolu_a", 150), interrupted("toolu_a", 30),
                         ask("toolu_b", 20), answered("toolu_b", 10), turn(1))
        self.assertEqual(self.state(line), "WORKING")
        self.assertIn("asks seen 2: 1 answered, 0 declined, 1 lost", line)

    def test_an_answer_wins_where_one_ask_carries_two_results(self):
        # Both orders, because "the last row wins" passes one of them and is wrong on the other.
        orders = {"lost first": (interrupted("toolu_a", 30), answered("toolu_a", 20)),
                  "answered first": (answered("toolu_a", 30), interrupted("toolu_a", 20))}
        for name, pair in orders.items():
            with self.subTest(order=name):
                line = self.read(ask("toolu_a", 150), pair[0], pair[1], turn(1))
                self.assertEqual(self.state(line), "WORKING")
                self.assertIn("asks seen 1: 1 answered, 0 declined, 0 lost", line)


class ADeclinedAskIsNotLost(SeatState):
    def test_an_ask_the_owner_rejected_is_counted_apart_and_does_not_read_lost(self):
        line = self.read(ask("toolu_a", 150), declined("toolu_a", 30), turn(2))
        self.assertEqual(self.state(line), "WORKING")
        self.assertIn("asks seen 1: 0 answered, 1 declined, 0 lost", line)

    def test_a_decline_wins_over_a_loss_where_one_ask_carries_both(self):
        orders = {"lost first": (interrupted("toolu_a", 30), declined("toolu_a", 20)),
                  "declined first": (declined("toolu_a", 30), interrupted("toolu_a", 20))}
        for name, pair in orders.items():
            with self.subTest(order=name):
                line = self.read(ask("toolu_a", 150), pair[0], pair[1], turn(1))
                self.assertEqual(self.state(line), "WORKING")
                self.assertIn("asks seen 1: 0 answered, 1 declined, 0 lost", line)

    def test_only_the_exact_rejection_marker_is_a_decline(self):
        # A near miss is a shape nobody measured, and an unmeasured shape reads lost.
        entry = declined("toolu_a", 30)
        entry["toolUseResult"] = "User rejected something else"
        line = self.read(ask("toolu_a", 150), entry, turn(2))
        self.assertEqual(self.state(line), "QUESTION-LOST")


class AMentionIsNotAnAsk(SeatState):
    def test_a_transcript_that_only_names_the_tool_in_text_counts_no_ask(self):
        said = "I will not call AskUserQuestion here; a tool_use of AskUserQuestion would stall."
        line = self.read(turn(9, said), row("user", 5, said), turn(1, said))
        self.assertEqual(self.state(line), "WORKING")
        self.assertTrue(line.endswith("| asks seen 0: 0 answered, 0 declined, 0 lost"), line)

    def test_another_tools_failed_result_is_not_a_lost_question(self):
        failed = result("toolu_x", 4, "exit 1", "Error: exit 1", is_error=True)
        used = row("assistant", 5, [{"type": "tool_use", "id": "toolu_x", "name": "Bash",
                                     "input": {"command": "false"}}])
        line = self.read(used, failed, turn(1))
        self.assertEqual(self.state(line), "WORKING")
        self.assertTrue(line.endswith("| asks seen 0: 0 answered, 0 declined, 0 lost"), line)


if __name__ == "__main__":
    unittest.main()
