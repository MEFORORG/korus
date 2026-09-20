"""Lander Board collector. Emits data.json. Re-runnable, no jq needed.

Readiness is classified on the REQUIRED contexts, read live, never on mergeStateStatus alone.
That field reports BEHIND in preference to BLOCKED, so a pull request with a failing required
check reads BEHIND and would be counted ready. LANDER-BOARD.md section 4a has the measurement.

A read this file cannot trust stops the run BEFORE data.json is written, so a failed collect
leaves the last good file in place (section 9). A default here would be a silent false clean.
"""
import json, subprocess, sys, datetime as dt
import os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("LANDER_BOARD_OUT", HERE)

REPOS = [("MEFORORG/MessageFoundry", "engine"),
         ("wshallwshall/korus", "korus"),
         ("wshallwshall/MessageFoundry-vault", "vault")]

def refuse(msg):
    sys.exit("collect.py: REFUSING to write data.json. " + msg)

# The search API cannot see wshallwshall/korus or wshallwshall/MessageFoundry-vault: it answers
# HTTP 422 "cannot be searched", and `gh pr list --search` reports that as an empty list with
# exit 0. Every merged, created and closed figure for those two repositories therefore read as
# zero while both were merging. Measured 2026-09-19. So the window is read off the REST pulls
# list, which is not indexed and works on all three. LANDER-BOARD.md section 7 carries the trap.
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

PASSING = {"SUCCESS", "NEUTRAL", "SKIPPED"}

def check_state(c):
    if c["__typename"] == "CheckRun":
        if c["status"] != "COMPLETED":
            return "pending"
        return "pass" if c["conclusion"] in PASSING else "fail"
    return {"SUCCESS": "pass", "PENDING": "pending", "EXPECTED": "pending"}.get(c["state"], "fail")

def classify(p, required):
    """needs a person / waiting on CI / ready. The three partition the open set."""
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

    repos = []
    for full, short in REPOS:
        owner, name = full.split("/")
        required = required_contexts(full)
        openprs = open_prs(owner, name)
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
        buckets = {}
        for p in openprs:
            buckets[p["mergeStateStatus"]] = buckets.get(p["mergeStateStatus"], 0) + 1
        count = lambda b: sum(1 for x in prs if x["bucket"] == b)
        repos.append({
            "repo": full, "short": short,
            "open": len(openprs),
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
        })

    out = {"generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "repos": repos}
    with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    for r in repos:
        print("%-10s open=%-4d ready=%-3d ci=%-3d person=%-3d required=%d enq=%-3d merged3d=%-4d"
              % (r["short"], r["open"], r["ready"], r["ci"], r["person"], len(r["required"]),
                 r["enqueued"], len(r["merged"])))


if __name__ == "__main__":
    main()
