"""Read a watched seat's transcript and say which of three states it is in.

WORKING, IDLE and BLOCKED-ON-A-QUESTION look identical from outside: no pushes,
no merges, no queue entries. Only the transcript separates them, and the third
has a named owner who is not the seat.

Measured 2026-09-19: the Lander sat suspended on AskUserQuestion for 10h37m
while its Watchdog reported a capacity stall. One line from the Owner cleared it.

STRUCTURE, NOT STRINGS. A first draft matched the text "AskUserQuestion"
anywhere in an entry and fired on a session merely DISCUSSING the tool. This
version pairs a tool_use block by id against its tool_result. A seat is blocked
only when an AskUserQuestion tool_use has no matching tool_result.

Usage:  python seatstate.py <transcript.jsonl>
Prints one line: STATE | age | detail
"""
import json, io, sys, datetime as dt

ASK = "AskUserQuestion"


def blocks(entry):
    m = entry.get("message") or {}
    c = m.get("content")
    return c if isinstance(c, list) else []


def scan(path):
    asks, results, own = {}, set(), []
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
                results.add(b["tool_use_id"])
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
    print("%s | %s since its own last turn | asks seen %d, all answered"
          % ("IDLE" if age >= 20 else "WORKING", hm(age), len(asks)))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: seatstate.py <transcript.jsonl>")
        sys.exit(0)
    main(sys.argv[1])
