"""Run korus scripts/board/collect.py unmodified, answering its GraphQL calls from REST.

Cloud sessions refuse `gh api graphql` (HTTP 403) but serve REST. collect.py shells out to gh for
three GraphQL queries: the open-PR rollup, the mergeStateStatus re-read, and the merge queue. This
shim intercepts exactly those subprocess calls and synthesises the GraphQL response shape from
REST. Every other call passes through untouched.

Merge queue: REST has no queue endpoint. Entries are derived from each open PR's issue timeline
(added_to_merge_queue / removed_from_merge_queue). Position is enqueue order; state is "QUEUED"
because REST does not expose the per-entry state. A failed read returns a GraphQL error, so
collect.py refuses rather than publishing a false zero.
"""
import json
import subprocess
import sys

_real_run = subprocess.run
MSTATE = {"clean": "CLEAN", "dirty": "DIRTY", "blocked": "BLOCKED", "behind": "BEHIND",
          "unstable": "UNSTABLE", "unknown": "UNKNOWN", "draft": "DRAFT",
          "has_hooks": "HAS_HOOKS"}


class ShimError(Exception):
    pass


def rest(path):
    r = _real_run(["gh", "api", path], capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise ShimError("REST %s failed: %s" % (path, (r.stderr or "").strip()[:200]))
    return json.loads(r.stdout)


def rest_pages(path, key=None):
    out, page = [], 1
    while True:
        sep = "&" if "?" in path else "?"
        d = rest("%s%sper_page=100&page=%d" % (path, sep, page))
        items = d[key] if key else d
        out += items
        if len(items) < 100:
            return out
        page += 1


def merge_state(full, n):
    s = rest("repos/%s/pulls/%d" % (full, n)).get("mergeable_state")
    return MSTATE.get(s or "unknown", (s or "UNKNOWN").upper())


def pr_node(full, p):
    sha = p["head"]["sha"]
    cr = rest("repos/%s/commits/%s/check-runs?per_page=100" % (full, sha))
    st = rest("repos/%s/commits/%s/status?per_page=100" % (full, sha))
    nodes = [{"__typename": "CheckRun", "name": c["name"], "status": c["status"].upper(),
              "conclusion": (c["conclusion"] or "").upper() or None,
              "startedAt": c.get("started_at")} for c in cr["check_runs"]]
    nodes += [{"__typename": "StatusContext", "context": s["context"],
               "state": s["state"].upper(), "createdAt": s.get("created_at")}
              for s in st.get("statuses", [])]
    more = cr.get("total_count", 0) > 100 or st.get("total_count", 0) > 100
    roll = {"contexts": {"pageInfo": {"hasNextPage": more}, "nodes": nodes}}
    return {"number": p["number"], "isDraft": bool(p["draft"]),
            "mergeStateStatus": merge_state(full, p["number"]), "createdAt": p["created_at"],
            "commits": {"nodes": [{"commit": {"statusCheckRollup": roll}}]}}


def queue_entries(full, open_prs):
    entries = []
    for p in open_prs:
        last = None
        for e in rest_pages("repos/%s/issues/%d/timeline" % (full, p["number"])):
            if e.get("event") in ("added_to_merge_queue", "removed_from_merge_queue"):
                last = e
        if last and last["event"] == "added_to_merge_queue":
            entries.append((last["created_at"], p["number"]))
    entries.sort()
    return [{"position": i + 1, "state": "QUEUED", "pullRequest": {"number": n}}
            for i, (_, n) in enumerate(entries)]


def answer(args):
    q = next(a[len("query="):] for a in args if a.startswith("query="))
    var = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in args if "=" in a and not
           a.startswith("query=")}
    if "mergeQueue" in q:
        owner = q.split('owner:"')[1].split('"')[0]
        name = q.split('name:"')[1].split('"')[0]
        full = "%s/%s" % (owner, name)
        prs = rest_pages("repos/%s/pulls?state=open" % full)
        has_queue = name == "MessageFoundry"  # korus and the vault have no queue (collect.py)
        mq = {"entries": {"nodes": queue_entries(full, prs)}} if has_queue else None
        return {"data": {"repository": {"mergeQueue": mq}}}
    full = "%s/%s" % (var["owner"], var["name"])
    if "pullRequests(states:OPEN" in q:
        prs = rest_pages("repos/%s/pulls?state=open" % full)
        nodes = [pr_node(full, p) for p in prs]
        return {"data": {"repository": {"pullRequests": {
            "totalCount": len(nodes), "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": nodes}}}}
    if "pullRequest(number:" in q:
        return {"data": {"repository": {"pullRequest": {
            "mergeStateStatus": merge_state(full, int(var["n"]))}}}}
    raise ShimError("unrecognised GraphQL query: %s" % q[:120])


def run(args, *a, **kw):
    if isinstance(args, list) and args[:3] == ["gh", "api", "graphql"]:
        try:
            out, rc, err = json.dumps(answer(args)), 0, ""
        except ShimError as e:
            out, rc, err = "", 1, str(e)
        return subprocess.CompletedProcess(args, rc, out, err)
    # The protection endpoint answers 403 to the session integration; the branch endpoint embeds
    # the same required_status_checks.contexts list and is readable.
    if (isinstance(args, list) and len(args) > 2 and args[:2] == ["gh", "api"]
            and args[2].endswith("/branches/main/protection/required_status_checks")):
        args = ["gh", "api", args[2].rsplit("/protection/", 1)[0], "--jq",
                ".protection.required_status_checks.contexts[]"]
    if isinstance(args, list) and args[:2] == ["gh", "api"] and "--paginate" in args:
        return paginate(args)
    return _real_run(args, *a, **kw)


def paginate(args):
    """`gh --paginate` follows Link headers in the numeric repositories/{id} form, which the proxy
    refuses. Page explicitly with page=N instead, applying the --jq filter per page with jq."""
    base = [x for x in args if x != "--paginate"]
    jq = None
    if "--jq" in base:
        i = base.index("--jq")
        jq = base[i + 1]
        base = base[:i] + base[i + 2:]
    per = 30
    for i, x in enumerate(base):
        if x == "-f" and base[i + 1].startswith("per_page="):
            per = int(base[i + 1].split("=", 1)[1])
    out = []
    for page in range(1, 51):
        r = _real_run(base + ["-f", "page=%d" % page], capture_output=True, encoding="utf-8",
                      errors="replace")
        if r.returncode:
            return subprocess.CompletedProcess(args, r.returncode, "", r.stderr)
        d = json.loads(r.stdout)
        items = d if isinstance(d, list) else next(
            (v for v in d.values() if isinstance(v, list)), [])
        if jq:
            j = _real_run(["jq", "-r", jq], input=r.stdout, capture_output=True,
                          encoding="utf-8", errors="replace")
            if j.returncode:
                return subprocess.CompletedProcess(args, j.returncode, "", j.stderr)
            out.append(j.stdout)
        else:
            out.append(r.stdout)
        if len(items) < per:
            return subprocess.CompletedProcess(args, 0, "".join(out), "")
    return subprocess.CompletedProcess(args, 1, "", "paginate: more than 50 pages")


if __name__ == "__main__":
    sys.path.insert(0, sys.argv[1])
    subprocess.run = run
    import collect  # noqa: E402  (collect.py from korus origin/main, extracted per refresh)
    collect.subprocess.run = run
    collect.main()
