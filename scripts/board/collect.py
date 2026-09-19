"""Lander Board collector. Emits data.json. Re-runnable, no jq needed."""
import json, subprocess, datetime as dt
import os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("LANDER_BOARD_OUT", HERE)

REPOS = [("MEFORORG/MessageFoundry", "engine"),
         ("wshallwshall/korus", "korus"),
         ("wshallwshall/MessageFoundry-vault", "vault")]

def sh(args):
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""

def j(args, default):
    out = sh(args)
    try:
        return json.loads(out) if out.strip() else default
    except Exception:
        return default

now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
since_day = (now - dt.timedelta(days=3)).strftime("%Y-%m-%d")

repos = []
for full, short in REPOS:
    owner, name = full.split("/")
    openprs = j(["gh","pr","list","--repo",full,"--state","open","--limit","300",
                 "--json","number,mergeStateStatus,isDraft,createdAt"], [])
    gq = ('{repository(owner:"%s",name:"%s"){mergeQueue(branch:"main")'
          '{entries(first:50){nodes{position state pullRequest{number}}}}}}' % (owner, name))
    qd = j(["gh","api","graphql","-f","query="+gq], {})
    try:
        nodes = qd["data"]["repository"]["mergeQueue"]["entries"]["nodes"] or []
    except Exception:
        nodes = []
    merged = j(["gh","pr","list","--repo",full,"--state","merged","--search",
                "merged:>=%s" % since_day,"--limit","400","--json","number,mergedAt"], [])
    created = j(["gh","pr","list","--repo",full,"--state","all","--search",
                 "created:>=%s" % since_day,"--limit","400","--json","number,createdAt"], [])
    closed = j(["gh","pr","list","--repo",full,"--state","closed","--search",
                "closed:>=%s" % since_day,"--limit","400","--json","number,closedAt"], [])
    buckets = {}
    for p in openprs:
        buckets[p["mergeStateStatus"]] = buckets.get(p["mergeStateStatus"], 0) + 1
    # NEEDS A PERSON: draft, conflicted, blocked, or failing a required check.
    # BEHIND is NOT here -- the queue rebases it without anyone touching it.
    NEEDS_PERSON = {"DIRTY", "BLOCKED", "UNSTABLE"}
    notready = sum(1 for p in openprs
                   if p["isDraft"] or p["mergeStateStatus"] in NEEDS_PERSON)
    repos.append({
        "repo": full, "short": short,
        "open": len(openprs),
        "draft": sum(1 for p in openprs if p["isDraft"]),
        "clean": sum(1 for p in openprs if p["mergeStateStatus"]=="CLEAN" and not p["isDraft"]),
        "buckets": buckets,
        "notready": notready,
        "ready": len(openprs) - notready,
        "enqueued": len(nodes),
        "entries": [{"n": e["pullRequest"]["number"], "state": e["state"],
                     "pos": e["position"]} for e in nodes],
        "merged": [m["mergedAt"] for m in merged if m.get("mergedAt")],
        "created": [c["createdAt"] for c in created if c.get("createdAt")],
        "closed": [c["closedAt"] for c in closed if c.get("closedAt")],
    })

out = {"generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "repos": repos}
with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
for r in repos:
    print("%-10s open=%-4d clean=%-3d enq=%-3d merged3d=%-4d buckets=%s"
          % (r["short"], r["open"], r["clean"], r["enqueued"], len(r["merged"]), r["buckets"]))
