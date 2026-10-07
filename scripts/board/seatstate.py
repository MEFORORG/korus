"""Read a watched seat's transcript and say which state it is in.

WORKING, IDLE and BLOCKED-ON-A-QUESTION look identical from outside: no pushes,
no merges, no queue entries. Only the transcript separates them, and the third
has a named owner who is not the seat.

Measured 2026-09-19: the Lander sat suspended on AskUserQuestion for 10h37m
while its Watchdog reported a capacity stall. One line from the Owner cleared it.

STRUCTURE, NOT STRINGS. A first draft matched the text "AskUserQuestion"
anywhere in an entry and fired on a session merely DISCUSSING the tool. This
version pairs a tool_use block by id against its tool_result. A seat is blocked
only when an AskUserQuestion tool_use has no matching tool_result.

A RESULT IS NOT AN ANSWER. Until 2026-10-05 (UTC) any tool_result carrying the
ask's id counted as one, and the line ended "all answered". Measured that day
on two live transcripts: a session that restarted while suspended on the
dialog, and a dialog that was dismissed or timed out, each leave an is_error
result in the ask's place. Both printed WORKING, with no answer recorded and no
dialog left on screen to show a question had been put.

So a result is placed three ways, off the ROW and never off its wording:

  answered   not an error, and the row's toolUseResult is an object holding "answers"
  declined   the row's toolUseResult is exactly "User rejected tool use"
  lost       anything else, including a shape this script has never seen

DECLINED IS NOT LOST. The Owner saw that dialog and rejected it, so it does not
fire the token below. An unknown shape reads as lost: a false QUESTION-LOST
costs a second look, and a false "answered" cost the stall this exists to catch.
So the line says what was read, that no answer was RECORDED, and not why.

QUESTION-LOST is printed when the NEWEST ask is lost. The seat is not suspended,
so unlike a blocked one it can be reached. The detail still ends WORKING or
IDLE, because the token replaces that word and the reader needs both. That word
is read off the newest row's age as it always was, and the lost result is
itself a row: a seat that has done nothing since still reads WORKING for 20
minutes after it.

A LATER ASK CLEARS IT, and so does a better result under the same ask. Nothing
else does. NOT VARIED: an Owner who answers in plain chat leaves the line
unchanged, because a chat turn and a peer's message are the same row here. A seat that never asks again, as the
Lander and Watchdog are told not to, keeps the token for the rest of its
transcript. Read the "ended unanswered" time before treating an old one as news.

ALSO NOT VARIED: a row holding two tool_results. toolUseResult sits on the row,
so both blocks would be placed by one value. Every ask result measured below
was alone on its row.

MEASURED 2026-10-05 (UTC), on one machine. The instrument was scan() below, as
the change that added this paragraph wrote it, called on each transcript under
21 days old in every config root. It counted results[id][0] per ask, and "open" where an ask had no
result. The loop around scan() was a scratch script and is not in this tree.

It returned 907 asks in 345 transcripts: 881 answered, 15 declined, 7 lost and
4 open. That is a live read, so a later run moves. Every answered row held the
object and every other row held a string.

CARRIED, not reproducible from this tree: a scratch walker read the wording.
The answered CONTENT opened two different ways, on 650 and 241 rows, so a rule
keyed on either wording loses the other. Those 891 rows are ten more than the
881 asks: nine asks carried a repeated answer, one of them twice. No ask mixed
two outcomes, so RANK is a guard no transcript has yet exercised. Of the 7
lost, 4 were interrupted and 3 aborted. Nine asks also carried a repeated
tool_use row, each with the timestamp of the first, so which copy sets the ask
time has not mattered yet.

Usage:  python seatstate.py <transcript.jsonl>
Prints one line: STATE | age | detail
"""
import json, io, sys, datetime as dt

ASK = "AskUserQuestion"
ANSWERED, DECLINED, LOST = "answered", "declined", "lost"
# Where one ask carries two results, the better outcome stands.
RANK = {LOST: 0, DECLINED: 1, ANSWERED: 2}
REJECTED = "User rejected tool use"


def blocks(entry):
    m = entry.get("message") or {}
    c = m.get("content")
    return c if isinstance(c, list) else []


def outcome(block, entry):
    r = entry.get("toolUseResult")
    if not block.get("is_error") and isinstance(r, dict) and "answers" in r:
        return ANSWERED
    return DECLINED if r == REJECTED else LOST


def scan(path):
    asks, results, own = {}, {}, []
    for line in io.open(path, encoding="utf-8", errors="replace"):
        if '"timestamp"' not in line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        ts = d.get("timestamp")
        if not ts:
            continue
        ty = d.get("type")
        if ty in ("assistant", "user"):
            own.append(ts)
        for b in blocks(d):
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use" and b.get("name") == ASK:
                asks[b.get("id")] = ts
            elif b.get("type") == "tool_result" and b.get("tool_use_id"):
                tid, new = b["tool_use_id"], outcome(b, d)
                if tid not in results or RANK[new] > RANK[results[tid][0]]:
                    results[tid] = (new, ts)
    return asks, results, sorted(own)


def hm(mins):
    return "%dh %02dm" % (mins // 60, mins % 60)


def main(path):
    asks, results, own = scan(path)
    now = dt.datetime.now(dt.timezone.utc)
    if not own:
        print("UNKNOWN | no assistant or user entries | %s" % path)
        return

    unanswered = sorted((ts, tid) for tid, ts in asks.items() if tid not in results)
    if unanswered:
        ts = unanswered[-1][0]
        waited = int((now - dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() // 60)
        print("BLOCKED-ON-A-QUESTION | waiting %s | asked %s -- ONLY THE OWNER CAN CLEAR THIS"
              % (hm(waited), ts))
        return

    age = int((now - dt.datetime.fromisoformat(own[-1].replace("Z", "+00:00"))).total_seconds() // 60)
    counts = "asks seen %d: %s" % (len(asks), ", ".join(
        "%d %s" % (sum(1 for tid in asks if results[tid][0] == k), k)
        for k in (ANSWERED, DECLINED, LOST)))
    newest = max(asks.values()) if asks else None
    lost = sorted(results[tid][1] for tid, ts in asks.items()
                  if ts == newest and results[tid][0] == LOST)
    pace = "IDLE" if age >= 20 else "WORKING"
    if lost:
        print("QUESTION-LOST | %s since its own last turn | asked %s, ended unanswered %s"
              " -- NO ANSWER WAS RECORDED, AND NO DIALOG IS OPEN; %s; otherwise %s"
              % (hm(age), newest, lost[-1], counts, pace))
        return

    print("%s | %s since its own last turn | %s" % (pace, hm(age), counts))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: seatstate.py <transcript.jsonl>")
        sys.exit(0)
    main(sys.argv[1])
