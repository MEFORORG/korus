"""Lander Board collector. Emits data.json. Re-runnable, no jq needed.

Readiness is classified on the REQUIRED contexts, read live, never on mergeStateStatus alone.
That field reports BEHIND in preference to BLOCKED, so a pull request with a failing required
check reads BEHIND and would be counted ready. LANDER-BOARD.md section 4a has the measurement.

A read this file cannot trust stops the run BEFORE data.json is written, so a failed collect
leaves the last good file in place (section 9). A default here would be a silent false clean.
"""
import base64
import json, subprocess, sys, time, datetime as dt
import os
import re
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("LANDER_BOARD_OUT", HERE)

# CANONICAL owner/name, not the pre-transfer one. korus and the vault moved to MEFORORG; REST,
# GraphQL and `gh pr` all follow the rename silently, so a stale owner here works everywhere except
# the search index, which answers HTTP 422 for a repository that is not at that owner. Addressing a
# repository by a name that only resolves through a redirect is a reading waiting to break.
#   gh api repos/<owner>/<name> --jq .full_name    tells you the canonical pair.
REPOS = [("MEFORORG/MessageFoundry", "engine"),
         ("MEFORORG/korus", "korus"),
         ("MEFORORG/MessageFoundry-vault", "vault")]

def refuse(msg):
    sys.exit("collect.py: REFUSING to write data.json. " + msg)

# Read off REST rather than the search API, for two independent reasons.
#
# 1. SEARCH DOES NOT FOLLOW A REPOSITORY RENAME. korus and the vault moved to MEFORORG. REST still
#    resolved the old owner, so every other call kept working, while search answered HTTP 422 for
#    a repository that was not at that owner. Both read as zero merges for three days while both
#    were merging. The REPOS list above is canonical now, but REST is the instrument that would
#    have survived the transfer either way.
# 2. `gh pr list --search` REPORTS A 422 AS `[]` WITH EXIT 0, so the failure arrived looking like
#    a clean repository. That half is true of any search failure, rename or not.
#
# Measured 2026-09-19. LANDER-BOARD.md section 7 carries the trap and the numbers.
def closed_window(full, since):
    """Merged, created and closed timestamps in the window, from repos/{full}/pulls.

    Pages `state=closed` newest-updated first until a page predates the window. Open pull
    requests carry the creates, so they are added by the caller. Refuses on any failed page
    rather than defaulting, because a default here is a silent false clean."""
    merged, created, closed, page = [], [], [], 1
    while page <= 20:
        r = subprocess.run(
            ["gh", "api", "-X", "GET", "repos/%s/pulls" % full, "-f", "state=closed",
             "-f", "sort=updated", "-f", "direction=desc", "-f", "per_page=100",
             "-f", "page=%d" % page, "--jq",
             '.[] | [(.merged_at // "-"), (.closed_at // "-"), .created_at, .updated_at]'
             ' | join(" ")'],
            capture_output=True, encoding="utf-8", errors="replace")
        if r.returncode:
            refuse("The closed pull request read for %s failed on page %d: %s"
                   % (full, page, (r.stderr or "").strip()[:300]))
        rows = [ln.split() for ln in r.stdout.splitlines() if ln.strip()]
        if not rows:
            return merged, created, closed, True
        for m, c, cr, _u in rows:
            if m != "-" and m >= since:
                merged.append(m)
            if c != "-" and c >= since:
                closed.append(c)
            if cr >= since:
                created.append(cr)
        if min(x[3] for x in rows) < since:
            return merged, created, closed, True
        page += 1
    refuse("The closed pull request read for %s hit the page cap before reaching %s."
           % (full, since))

# SCHEDULED-RUN REDS. Owner ruling 2026-09-26: the Lander owns them, and they reach the Lander
# through this board. A scheduled run has no pull request, so no required check and no merge state
# ever shows its red; before this, the only record was an issue nobody polled. Engine issue 288,
# *Nightly Security is failing*, stayed open 48 days with 49 comments (vault BACKLOG #1800).
#
# THE MATCH IS THE WRITER'S OWN PREDICATE, NOT A GUESS. The engine's `nightly-notice.yml` sets
# `TITLE="Nightly $WF_NAME is failing"` and `LABEL="bug"`, and finds the issue to comment on by an
# OPEN issue with that label whose title is exactly that. So every issue the workflow would adopt
# matches here. The converse does not hold: an issue for a workflow since dropped from its watch
# list, or a duplicate it lost track of, also matches and will never be closed by it. Showing those
# is deliberate -- an orphan is a red nobody will clear, which is the thing this panel is for.
# The name is left free rather than listed: the watch list is the engine's, and a copy here drifts.
#
# ONLY THE ENGINE CARRIES THE WORKFLOW. Measured 2026-09-30 with
# `git ls-tree --name-only origin/main .github/workflows/ | grep -c nightly-notice`: korus 0 at
# 4a5af872d, the vault 0 at 4c9855c75, and the engine 1 at ce9a8ddba, which is the control. Every
# other repository is NOT READ, and the board says so rather than printing a clean zero for it.
NIGHTLY_NOTICE_REPOS = ("MEFORORG/MessageFoundry",)
NIGHTLY_LABEL = "bug"
# Applied with fullmatch, never match plus `$`: `$` also matches before a trailing newline, and the
# workflow compares titles exactly, so "Nightly CI is failing\n" is not an issue it would adopt.
NIGHTLY_TITLE = re.compile(r"Nightly (.+) is failing")


# SCHEDULED-RUN CONCLUSIONS, read off Actions for EVERY repository in REPOS. Owner instruction
# 2026-10-01. The issue read above reaches only the engine, and only the workflows its notice
# watches, so korus and the vault printed "not read" and a red there reached nobody. Measured
# 2026-10-01: the vault's ASVS scorecard had failed its last 30 scheduled runs with no row here.
#
# WHY RUNS AND NOT A PORTED NOTICE. Every repository has a run list, so a repository added to
# REPOS, or a scheduled workflow added to one, is read with no edit anywhere. A ported notice
# covers only the repositories someone remembers to port it to, and only its own watch list.
#
# WHAT COUNTS. An ACTIVE workflow with a scheduled run in the window. Its state is its latest
# completed scheduled run that reached a verdict. `cancelled` is no verdict and is stepped over;
# every conclusion not in RUN_PASS is red, so a conclusion GitHub adds later shows rather than hides.
# A red whose workflow file no longer declares a schedule is not shown, and is named instead: the
# vault's ci.yml dropped its cron, and its last scheduled run, red, would otherwise show for weeks.
#
# A FAILED READ REFUSES THE COLLECT, unlike the issue read. Owner instruction 2026-10-01: keep the
# fail-closed rule. A refused collect leaves the last good board and its old stamp, which a reader
# can see. "No scheduled run is red" off a read that failed is the false clean this file refuses.
SCHEDULE_WINDOW_DAYS = 35
RUN_PASS = {"success", "neutral", "skipped"}
RUN_NO_VERDICT = {"cancelled"}
# The runs endpoint returns at most 1,000 results for a filtered query, so a window holding more
# cannot be read whole. Measured 2026-10-01 over 35 days: engine 294, vault 133, korus 50.
RUNS_API_CAP = 1000


def gh_json_rows(args, what):
    """Every line of a `gh api ... --jq '... | @json'` read, parsed. Refuses on any failure."""
    r = subprocess.run(["gh", "api"] + args, capture_output=True, encoding="utf-8",
                       errors="replace")
    if r.returncode:
        refuse("The %s read failed: %s"
               % (what, (r.stderr or "").strip()[:300] or "exit %d" % r.returncode))
    rows = []
    for line in r.stdout.split("\n"):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            refuse("The %s read returned a line that is not JSON: %r" % (what, line[:120]))
    return rows


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


# The TRIGGER KEY, block form `schedule:` or flow form `on: [push, schedule]`. A bare word match
# also fired on `github.event_name == 'schedule'`, which engine ci.yml, security.yml and fuzz.yml
# carry, so a dropped cron there would never have been noticed. Measured 2026-10-01.
SCHEDULE_KEY = re.compile(r"""^\s*(["']?schedule["']?\s*:|["']?on["']?\s*:.*\bschedule\b)""")


def declares_schedule(full, path):
    """Whether the workflow file at the default branch still declares a schedule trigger.

    A file gone from the default branch declares none. GitHub keeps a deleted workflow listed as
    `active` (measured 2026-10-01: three engine workflows 404), and refusing there would freeze the
    whole board until its last run left the window. A file the API will not inline, over 1 MB,
    counts as declaring one: that keeps its red shown, which is the safe side."""
    what = "workflow file %s in %s" % (path, full)
    r = subprocess.run(["gh", "api", "repos/%s/contents/%s" % (full, path), "--jq",
                        "[.content, .encoding] | @json"],
                       capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode and "HTTP 404" in (r.stderr or ""):
        return False
    if r.returncode:
        refuse("The %s read failed: %s"
               % (what, (r.stderr or "").strip()[:300] or "exit %d" % r.returncode))
    try:
        content, encoding = json.loads(r.stdout)
    except (ValueError, TypeError):
        refuse("The %s did not come back as one file: %r" % (what, r.stdout[:120]))
    if encoding != "base64" or not isinstance(content, str):
        return True
    try:
        text = base64.b64decode(content).decode("utf-8", errors="replace")
    except ValueError:
        refuse("The %s is not base64." % what)
    return any(SCHEDULE_KEY.search(ln) for ln in text.splitlines()
               if not ln.lstrip().startswith("#"))


def scheduled_reds(full, since_day):
    """Each active workflow in `full` whose latest scheduled run with a verdict did not pass.

    Returns {"window_days", "read", "reds", "unscheduled", "stopped"}. `read` counts the
    workflows judged green or red, so a zero beside it says how much was looked at. A red filed as
    `unscheduled` is not in `read`: the clear headline says each read workflow passed."""
    flows = gh_json_rows(["-X", "GET", "repos/%s/actions/workflows" % full, "-f", "per_page=100",
                          "--paginate", "--jq",
                          ".workflows[] | [.id, .state, .path, .name] | @json"],
                         "workflow list for %s" % full)
    active, stopped = {}, []
    for f in flows:
        if not (isinstance(f, list) and len(f) == 4 and is_int(f[0])
                and all(isinstance(x, str) for x in f[1:])):
            refuse("The workflow list for %s holds a row it cannot read: %r" % (full, f))
        if f[1] == "active":
            active[f[0]] = {"path": f[2], "name": f[3]}
        elif f[1] == "disabled_inactivity":
            # GitHub turned a scheduled workflow off, and nobody chose it. Named on the board.
            stopped.append(f[3])
    runs = gh_json_rows(["-X", "GET", "repos/%s/actions/runs" % full, "-f", "event=schedule",
                         "-f", "created=>=" + since_day, "-f", "per_page=100", "--paginate",
                         "--jq", ".total_count as $t | .workflow_runs[] | [$t, .id, .workflow_id,"
                         " .status, .conclusion, .created_at, .html_url] | @json"],
                        "scheduled run list for %s" % full)
    seen, totals, by_flow = set(), set(), {}
    for r in runs:
        if not (isinstance(r, list) and len(r) == 7 and all(is_int(x) for x in r[:3])
                and isinstance(r[3], str) and (r[4] is None or isinstance(r[4], str))
                and aware_instant(r[5]) and isinstance(r[6], str)):
            refuse("The scheduled run list for %s holds a row it cannot read: %r" % (full, r))
        total, run_id, flow, status, conclusion, created, url = r
        totals.add(total)
        # A run created mid-read shifts the newest-first pages, so a row can arrive twice.
        if run_id in seen:
            continue
        seen.add(run_id)
        if status == "completed" and conclusion not in RUN_NO_VERDICT:
            by_flow.setdefault(flow, []).append((P(created), conclusion, created, url))
    if totals and max(totals) > RUNS_API_CAP:
        refuse("%s holds %d scheduled runs in %d days, past the %d the API returns; narrow "
               "SCHEDULE_WINDOW_DAYS." % (full, max(totals), SCHEDULE_WINDOW_DAYS, RUNS_API_CAP))
    if totals and len(seen) < min(totals):
        refuse("%s reports %d scheduled runs in the window but %d were read."
               % (full, min(totals), len(seen)))
    reds, unscheduled, read = [], [], 0
    for flow, info in sorted(active.items(), key=lambda kv: kv[1]["name"]):
        verdicts = sorted(by_flow.get(flow, []), key=lambda x: x[0], reverse=True)
        if not verdicts:
            continue
        if verdicts[0][1] in RUN_PASS:
            read += 1
            continue
        streak = []
        for run in verdicts:
            if run[1] in RUN_PASS:
                break
            streak.append(run)
        if not declares_schedule(full, info["path"]):
            unscheduled.append(info["name"])
            continue
        read += 1
        green = verdicts[len(streak)][2] if len(streak) < len(verdicts) else None
        reds.append({"workflow": info["name"], "path": info["path"],
                     "conclusion": verdicts[0][1] or "none", "latest": verdicts[0][2],
                     "url": verdicts[0][3], "since": streak[-1][2], "streak": len(streak),
                     # Every run in the window failed, so the streak and its start are floors.
                     "floor": green is None, "last_green": green})
    return {"window_days": SCHEDULE_WINDOW_DAYS, "read": read, "reds": reds,
            "unscheduled": unscheduled, "stopped": sorted(stopped)}


def P(s):
    """An ISO instant, `Z` or offset, as a datetime. Callers check awareness first."""
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def aware_instant(s):
    """True when `s` is an ISO timestamp carrying a zone, the only form the board can age."""
    if not isinstance(s, str):
        return False
    try:
        return P(s).tzinfo is not None
    except ValueError:
        return False


def nightly_reds(full):
    """The OPEN issues matching `nightly-notice.yml`'s own predicate in `full`.

    Read off REST, filtered to the workflow's label, and paged to the end. The REST issues list
    carries pull requests too, so each row says which it is and a pull request is dropped here,
    where a test can see it.

    Returns (issues, skipped). A failed read returns ({"error": ...}, []) rather than refusing the
    whole collect: this is a secondary panel, and refusing would freeze every merge reading beside
    it. It is not a default either: the board renders the marker as "not read: the read failed",
    never as a zero, because "no scheduled run is red" is exactly the reading a default would forge.

    ONE ROW IS ONE `@json` ARRAY, never tab-joined text. The label read returns every open `bug`
    issue, and any title may hold a newline or a carriage return. Raw text let such a title forge a
    row or cut one in half; `@json` escapes both, so a line is always exactly one issue.

    A row that still cannot be read is SKIPPED AND REPORTED in `skipped`, and the rows beside it
    are kept. A row whose title is readable and does not match is filtered like any other, so an
    unrelated issue cannot fill the report."""
    r = subprocess.run(
        ["gh", "api", "-X", "GET", "repos/%s/issues" % full, "-f", "state=open",
         "-f", "labels=" + NIGHTLY_LABEL, "-f", "per_page=100", "--paginate", "--jq",
         '.[] | [.number, (if .pull_request then "pr" else "issue" end),'
         ' .created_at, .comments, .html_url, .title] | @json'],
        capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode:
        return {"error": "the read failed: %s" % ((r.stderr or "").strip()[:200] or
                                                   "exit %d" % r.returncode)}, []
    found, skipped = [], []
    # A JSON line holds no raw newline, so splitting on "\n" alone is exact. str.splitlines()
    # would also cut at U+2028, U+2029 and NEL, which JSON may carry raw.
    for line in r.stdout.split("\n"):
        if not line.strip():
            continue
        try:
            fields = json.loads(line)
        except ValueError:
            skipped.append("not a JSON row: %r" % line[:120])
            continue
        if not isinstance(fields, list) or len(fields) != 6:
            skipped.append("not a six-field row: %r" % line[:120])
            continue
        number, kind, opened, comments, url, title = fields
        if not isinstance(title, str):
            skipped.append("a row with no readable title: %r" % line[:120])
            continue
        m = NIGHTLY_TITLE.fullmatch(title)
        if not m or kind == "pr":
            continue
        ok = (kind == "issue" and aware_instant(opened) and isinstance(url, str)
              and all(isinstance(x, int) and not isinstance(x, bool) for x in (number, comments)))
        if not ok:
            skipped.append("a row could not be read: %r" % title[:120])
            continue
        found.append({"n": number, "workflow": m.group(1), "opened": opened,
                      "comments": comments, "url": url})
    return found, skipped


def required_contexts(full):
    """The required set from branch protection, read live. The count moves; never pin it."""
    r = subprocess.run(["gh", "api", "repos/%s/branches/main/protection/required_status_checks"
                        % full, "--jq", ".contexts[]"], capture_output=True, text=True)
    names = {line.strip() for line in r.stdout.splitlines() if line.strip()}
    # An empty set would read every pull request as ready. That is indistinguishable from a
    # failed read, so it is refused rather than trusted.
    if r.returncode or not names:
        refuse("Could not read the required contexts for %s (exit %d): %s"
               % (full, r.returncode, r.stderr.strip() or "empty set"))
    return names

# Paged, because `gh pr list --json statusCheckRollup` over 60+ pull requests returns HTTP 504.
OPEN_Q = """query($owner:String!,$name:String!,$first:Int!,$cursor:String){
 repository(owner:$owner,name:$name){pullRequests(states:OPEN,first:$first,after:$cursor){
  totalCount pageInfo{hasNextPage endCursor}
  nodes{number isDraft mergeStateStatus createdAt
   commits(last:1){nodes{commit{statusCheckRollup{contexts(first:100){pageInfo{hasNextPage}
    nodes{__typename ...on CheckRun{name status conclusion startedAt}
                     ...on StatusContext{context state createdAt}}}}}}}}}}}"""

def open_page(owner, name, cursor):
    """One page of open pull requests. Halves the page on a failure, then refuses."""
    err = ""
    for first in (20, 10, 5):
        args = ["gh", "api", "graphql", "-f", "query=" + OPEN_Q, "-F", "owner=" + owner,
                "-F", "name=" + name, "-F", "first=%d" % first]
        if cursor:
            args += ["-F", "cursor=" + cursor]
        r = subprocess.run(args, capture_output=True, text=True)
        try:
            d = json.loads(r.stdout) if r.returncode == 0 else {}
        except ValueError:
            d = {}
        # GraphQL can return partial data beside an `errors` list. Partial is not a reading.
        page = (d.get("data") or {}).get("repository") or {}
        if not d.get("errors") and page.get("pullRequests"):
            return page["pullRequests"]
        err = r.stderr.strip() or json.dumps(d.get("errors"))[:300]
    refuse("The open pull request read for %s/%s failed at every page size: %s"
           % (owner, name, err))

def open_prs(owner, name):
    prs, cursor, total = [], None, None
    while True:
        page = open_page(owner, name, cursor)
        total = page["totalCount"] if total is None else total
        prs += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    # Every open pull request must be present, with its head commit, before any is classified.
    if len(prs) != total:
        refuse("%s/%s reports %d open pull requests but %d were read."
               % (owner, name, total, len(prs)))
    for p in prs:
        heads = p["commits"]["nodes"]
        if len(heads) != 1:
            refuse("%s/%s #%d has no head commit in the read." % (owner, name, p["number"]))
        roll = heads[0]["commit"]["statusCheckRollup"]
        if roll and roll["contexts"]["pageInfo"]["hasNextPage"]:
            refuse("%s/%s #%d has more than 100 checks; the rest were not read."
                   % (owner, name, p["number"]))
    return prs

# One re-read per pass, a few passes, a short wait between. The recompute is quick; what it is
# not is instant, and a board that prints UNKNOWN for a whole repository is reporting the read
# rather than the repository.
UNKNOWN_RETRIES = 3
UNKNOWN_WAIT_S = 2.0

RESOLVE_Q = """query($owner:String!,$name:String!,$n:Int!){
 repository(owner:$owner,name:$name){pullRequest(number:$n){mergeStateStatus}}}"""


def resolve_unknown(owner, name, prs, sleep=time.sleep):
    """Re-read any pull request whose mergeability GitHub had not computed yet.

    Mutates `prs` in place and returns how many were STILL unknown when the retries ran out.
    A row that never resolves keeps UNKNOWN, which is the honest answer; what is not honest is
    reporting the first read as though it were a state. A failed re-read leaves the row alone
    rather than refusing the whole collect: a stale UNKNOWN on one row is a far smaller wrong
    than no board at all, and the count below says how many there were.
    """
    pending = [p for p in prs if p.get("mergeStateStatus") == "UNKNOWN"]
    for attempt in range(UNKNOWN_RETRIES):
        if not pending:
            return 0
        sleep(UNKNOWN_WAIT_S)
        still = []
        for p in pending:
            r = subprocess.run(
                ["gh", "api", "graphql", "-f", "query=" + RESOLVE_Q, "-F", "owner=" + owner,
                 "-F", "name=" + name, "-F", "n=%d" % p["number"]],
                capture_output=True, encoding="utf-8", errors="replace")
            state = None
            if not r.returncode:
                try:
                    d = json.loads(r.stdout)
                    if not d.get("errors"):
                        state = (((d.get("data") or {}).get("repository") or {})
                                 .get("pullRequest") or {}).get("mergeStateStatus")
                except ValueError:
                    state = None
            if state and state != "UNKNOWN":
                p["mergeStateStatus"] = state
            else:
                still.append(p)
        pending = still
    return len(pending)


PASSING = {"SUCCESS", "NEUTRAL", "SKIPPED"}

def check_state(c):
    if c["__typename"] == "CheckRun":
        if c["status"] != "COMPLETED":
            return "pending"
        return "pass" if c["conclusion"] in PASSING else "fail"
    return {"SUCCESS": "pass", "PENDING": "pending", "EXPECTED": "pending"}.get(c["state"], "fail")

def classify(p, required):
    """needs a fix / waiting on CI / ready. The three partition the open set.

    The bucket KEY stays "person" because data.json is a wire format others read. The label a
    reader sees is "Needs a fix", corrected by the owner on 2026-09-20: none of the three arms
    waits on a human. A draft needs its author to finish it, a conflict needs a rebase, and a red
    needs diagnosing -- all fixes the fleet does and the Lander drives.
    """
    roll = p["commits"]["nodes"][0]["commit"]["statusCheckRollup"]
    latest = {}
    # A re-run leaves the old run in the rollup. Keep the newest per name, as `gh pr checks` does.
    # A run not yet started has no timestamp and is the newest of all.
    for c in (roll["contexts"]["nodes"] if roll else []):
        nm = c.get("name") or c.get("context")
        ts = c.get("startedAt") or c.get("createdAt") or "9999"
        if nm not in latest or ts >= latest[nm][0]:
            latest[nm] = (ts, check_state(c))
    # Intersect with the REQUIRED set, always. Counting every red check is the mirror error:
    # advisory legs go red and block nothing. A required context not reported yet is pending,
    # so missing data can never read as ready.
    state = {n: latest.get(n, ("", "pending"))[1] for n in required}
    failing = sorted(n for n, s in state.items() if s == "fail")
    pending = sorted(n for n, s in state.items() if s == "pending")
    if p["isDraft"] or p["mergeStateStatus"] == "DIRTY" or failing:
        bucket = "person"
    elif pending:
        bucket = "ci"
    else:
        bucket = "ready"
    return {"n": p["number"], "bucket": bucket, "merge": p["mergeStateStatus"],
            "draft": p["isDraft"], "failing": failing, "pending": pending}

def main():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    # The series is 48 hours wide and the collector must cover it with room for the hour edges.
    since_iso = (now - dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    since_day = (now - dt.timedelta(days=SCHEDULE_WINDOW_DAYS)).strftime("%Y-%m-%d")

    repos = []
    for full, short in REPOS:
        owner, name = full.split("/")
        required = required_contexts(full)
        openprs = open_prs(owner, name)
        # Before anything is classified or counted. UNKNOWN means "not computed yet", and every
        # merge to main invalidates it for every open pull request.
        unresolved = resolve_unknown(owner, name, openprs)
        prs = [classify(p, required) for p in openprs]
        gq = ('{repository(owner:"%s",name:"%s"){mergeQueue(branch:"main")'
              '{entries(first:50){nodes{position state pullRequest{number}}}}}}' % (owner, name))
        # A null mergeQueue is a real answer -- KORUS and the vault have no queue. A FAILED call
        # is not, and defaulting it to zero would publish "nothing is enqueued" while the queue
        # runs. Only the second is refused.
        qr = subprocess.run(["gh","api","graphql","-f","query="+gq],
                            capture_output=True, encoding="utf-8", errors="replace")
        if qr.returncode:
            refuse("The merge queue read for %s failed: %s" % (full, (qr.stderr or "").strip()[:300]))
        qd = json.loads(qr.stdout)
        if qd.get("errors"):
            refuse("The merge queue read for %s returned errors: %s" % (full, str(qd["errors"])[:300]))
        mq = ((qd.get("data") or {}).get("repository") or {}).get("mergeQueue")
        nodes = (mq or {}).get("entries", {}).get("nodes") or []
        merged, created, closed, _done = closed_window(full, since_iso)
        # The closed list cannot carry a still-open pull request, so its creates come from the
        # open read already in hand. Without this the reconstructed open line in section 5b
        # loses every arrival that has not closed yet, which is most of a busy window.
        created += [p["createdAt"] for p in openprs if p["createdAt"] >= since_iso]
        # None is "this repository keeps no such issues", a declared scope and not a reading.
        nightly, nightly_skipped = (nightly_reds(full) if full in NIGHTLY_NOTICE_REPOS
                                    else (None, []))
        scheduled = scheduled_reds(full, since_day)
        buckets = {}
        for p in openprs:
            buckets[p["mergeStateStatus"]] = buckets.get(p["mergeStateStatus"], 0) + 1
        count = lambda b: sum(1 for x in prs if x["bucket"] == b)
        repos.append({
            "repo": full, "short": short,
            "open": len(openprs),
            # How many rows GitHub still had not computed when the retries ran out. A non-zero
            # value here is why a strip shows UNKNOWN, and it is a fact about the read.
            "unresolved": unresolved,
            "draft": sum(1 for p in openprs if p["isDraft"]),
            "clean": sum(1 for p in openprs if p["mergeStateStatus"]=="CLEAN" and not p["isDraft"]),
            "buckets": buckets,
            "required": sorted(required),
            "person": count("person"),
            "ci": count("ci"),
            "ready": count("ready"),
            "prs": prs,
            "enqueued": len(nodes),
            "entries": [{"n": e["pullRequest"]["number"], "state": e["state"],
                         "pos": e["position"]} for e in nodes],
            "merged": merged,
            "created": created,
            "closed": closed,
            "nightly": nightly,
            "nightly_skipped": nightly_skipped,
            "scheduled": scheduled,
        })

    out = {"generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "repos": repos}
    with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    for r in repos:
        print("%-10s open=%-4d ready=%-3d ci=%-3d person=%-3d required=%d enq=%-3d merged3d=%-4d%s"
              % (r["short"], r["open"], r["ready"], r["ci"], r["person"], len(r["required"]),
                 r["enqueued"], len(r["merged"]),
                 "  STILL-UNKNOWN=%d" % r["unresolved"] if r["unresolved"] else "")
              + ("" if r["nightly"] is None else
                 "  nightly-red=%d" % len(r["nightly"]) if isinstance(r["nightly"], list) else
                 "  NIGHTLY-READ-FAILED")
              + ("  nightly-skipped=%d" % len(r["nightly_skipped"])
                 if r["nightly_skipped"] else "")
              + "  scheduled-red=%d/%d" % (len(r["scheduled"]["reds"]), r["scheduled"]["read"]))


if __name__ == "__main__":
    main()
