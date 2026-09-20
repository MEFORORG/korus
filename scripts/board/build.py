"""Render board.html from data.json + series.json. Re-runnable."""
import json, datetime as dt, html
import os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("LANDER_BOARD_OUT", HERE)

CT = dt.timezone(dt.timedelta(hours=-5), "CDT")
d = json.load(open(os.path.join(OUT, "data.json"), encoding="utf-8"))
s = json.load(open(os.path.join(OUT, "series.json"), encoding="utf-8"))
P = lambda x: dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
now = P(d["generated_utc"])

NAMES = {"engine": "Engine", "korus": "KORUS", "vault": "Vault"}
order = ["engine", "vault", "korus"]
by = {r["short"]: r for r in d["repos"]}
esc = lambda x: html.escape(str(x))


def ago(iso):
    return None if not iso else (now - P(iso)).total_seconds() / 60.0


def clock(iso):
    """The Central clock time of an instant, e.g. `7:29 PM CT`, with the day when it is not today.

    Owner instruction 2026-09-19: never a relative age. An age is computed once and then frozen,
    so a board read an hour later still says "8m" and nothing on the page contradicts it. A clock
    time cannot rot without the reader seeing it against the stamp in the masthead.
    """
    if not iso:
        return "never"
    t = P(iso).astimezone(CT)
    hhmm = "%d:%02d %s CT" % ((t.hour % 12) or 12, t.minute, "AM" if t.hour < 12 else "PM")
    return hhmm if t.date() == now.astimezone(CT).date() else t.strftime("%a ") + hhmm


def dur(mins):
    """A SPAN, not an age: how long an idle run lasted. Spans stay true as the page ages."""
    if mins is None:
        return "never"
    if mins < 60:
        return "%dm" % int(mins)
    if mins < 1440:
        return "%dh %02dm" % (int(mins // 60), int(mins % 60))
    return "%dd %dh" % (int(mins // 1440), int((mins % 1440) // 60))


rows = []
for k in order:
    r, m = by[k], s["repos"][k]
    rows.append({
        "key": k, "name": NAMES[k],
        "open": r["open"], "clean": r["clean"], "draft": r["draft"], "enq": r["enqueued"],
        "entries": r["entries"], "m60": m["merged_60m"], "m24": m["merged_24h"],
        "rate": m["merged_24h"] / 24.0, "since": ago(m["last_merge"]),
        "last_at": clock(m["last_merge"]),
        "buckets": r["buckets"], "ready": r["ready"], "ci": r["ci"], "person": r["person"],
    })

tot = {k: sum(x[k] for x in rows)
       for k in ("open", "clean", "ready", "ci", "person", "enq", "m60", "m24")}
tot["rate"] = tot["m24"] / 24.0
sinces = [x["since"] for x in rows if x["since"] is not None]
last_any = min(sinces) if sinces else None

if last_any is None:
    verdict, vclass = "NO DATA", "warn"
elif last_any <= 60:
    verdict, vclass = "DRAINING", "good"
elif last_any <= 180:
    verdict, vclass = "SLOW", "warn"
else:
    verdict, vclass = "STALLED", "crit"

# ---------------------------------------------------------------- chart ----
W, H = 1160, 302
PADL, PADR, PADT, PADB = 54, 54, 24, 36
mer, opn, labels = s["total_merged_per_hour"], s["total_open_per_hour"], s["hours_ct"]
n = len(mer)
mmax = max(max(mer), 1)
omin, omax = min(opn), max(opn)
opad = max(1, round((omax - omin) * 0.15)) if omax > omin else 1
olo, ohi = max(0, omin - opad), omax + opad
iw, ih = W - PADL - PADR, H - PADT - PADB
bw = iw / n
bx = lambda i: PADL + i * bw
oy = lambda v: PADT + ih - ((v - olo) / ((ohi - olo) or 1)) * ih

bars = []
for i, v in enumerate(mer):
    x, w = bx(i) + bw * 0.27, bw * 0.46
    h = 2 if v == 0 else max(3, (v / mmax) * ih)
    bars.append(
        '<rect class="bar%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2.5">'
        '<title>%s CT &mdash; %d merged</title></rect>'
        % (" is-zero" if v == 0 else "", x, PADT + ih - h, w, h, labels[i], v))

line = " ".join("%.1f,%.1f" % (bx(i) + bw / 2, oy(v)) for i, v in enumerate(opn))
dots = "".join(
    '<circle class="odot" cx="%.1f" cy="%.1f" r="3.4"><title>%s CT &mdash; %d open</title></circle>'
    % (bx(i) + bw / 2, oy(v), labels[i], v) for i, v in enumerate(opn))
grid = "".join('<line class="gl" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>'
               % (PADL, W - PADR, PADT + ih * f, PADT + ih * f) for f in (0, .25, .5, .75, 1))
lyl = "".join('<text class="ax lyl" x="%d" y="%.1f">%d</text>'
              % (PADL - 10, PADT + ih * f + 4, round(mmax * (1 - f))) for f in (0, .5, 1))
ryl = "".join('<text class="ax ryl" x="%d" y="%.1f">%d</text>'
              % (W - PADR + 10, PADT + ih * f + 4, round(ohi - (ohi - olo) * f)) for f in (0, .5, 1))
xtk = "".join('<text class="ax xtk" x="%.1f" y="%d">%s</text>'
              % (bx(i) + bw / 2, H - 13, labels[i]) for i in range(n) if i % 3 == 0 or i == n - 1)

bands, i = "", 0
while i < n:
    if mer[i] == 0:
        j = i
        while j + 1 < n and mer[j + 1] == 0:
            j += 1
        if j - i >= 1:
            bands += ('<rect class="idle" x="%.1f" y="%d" width="%.1f" height="%d"/>'
                      % (bx(i), PADT, bw * (j - i + 1), ih))
        i = j + 1
    else:
        i += 1

# ---------------------------------------------------------------- cards ----
def card(label, accent, hero, unit, val, say, wide=False):
    """One data card: hero number, per-repo strip, one interpreting sentence."""
    strip = "".join(
        '<div class="sp"><span class="k">%s</span><span class="v%s">%s</span></div>'
        % (esc(r["name"]), " is-zero" if val(r) in ("0", "0.0", "0m") else "", val(r))
        for r in rows) if val else ""
    return ('<article class="card ac-%s%s">'
            '<h3>%s</h3>'
            '<p class="hero"><b>%s</b><span>%s</span></p>'
            '%s'
            '<p class="say">%s</p>'
            '</article>'
            % (accent, " card-wide" if wide else "", esc(label), esc(hero), esc(unit),
               ('<div class="split">%s</div>' % strip) if strip else "",
               say))


vault_clear = by["vault"]["open"] == 0
open_say = ("The vault is <b>clear</b>." if vault_clear
            else "The vault holds <b>%d</b>." % by["vault"]["open"])
enq_say = ("<b>Nothing is enqueued.</b> Ready work is not moving."
           if tot["enq"] == 0 else
           "Entries the queue is working through now.")
ready_say = ("Every required check is green. <b>Queue throughput is the only thing "
             "between these and main.</b>")
ci_say = "No required check is red, and one or more is still running. <b>Nobody acts yet.</b>"
# Most reds measured on 2026-09-19 were STALE: the check ran against an older main and a branch
# refresh cleared it. "Each needs a person" sent readers looking for work that did not exist.
nr_say = ("Draft, conflicted, or a red required check. <b>Refresh the branch before reading a "
          "red as broken.</b> Only a red that survives the refresh needs code.")
m60_say = "Best hour on the chart landed <b>%d</b>." % s["best_hour"]
rate_say = ("Over the last 24 hours. <b>%d</b> landed across the full %d."
            % (s["merged_window"], s["window_h"]))
idle_say = ("Stretches of <b>%dh or more</b> with no merge anywhere. Longest ran <b>%dh</b>."
            % (s["idle_run_min_h"], s["longest_idle_run_h"]))
last_any_at = min((x for x in rows if x["since"] is not None),
                  key=lambda x: x["since"], default=None)
last_any_clock = last_any_at["last_at"] if last_any_at else "never"
since_say = ("The last merge anywhere landed at <b>%s</b>." % last_any_clock)

cards = [
    card("PRs open", "amber", tot["open"], "total", lambda r: str(r["open"]), open_say),
    card("Ready and waiting", "teal", tot["ready"], "PRs", lambda r: str(r["ready"]), ready_say),
    card("Waiting on CI", "amber", tot["ci"], "PRs", lambda r: str(r["ci"]), ci_say),
    card("Needs a person", "warn", tot["person"], "PRs", lambda r: str(r["person"]), nr_say),
    card("Enqueued now", "teal", tot["enq"], "entries", lambda r: str(r["enq"]), enq_say),
    card("Merged, last 60 min", "teal", tot["m60"], "PRs", lambda r: str(r["m60"]), m60_say),
    card("Avg merged per hour", "teal", "%.1f" % tot["rate"], "/ h",
         lambda r: "%.1f" % r["rate"], rate_say),
    card("Idle periods", "crit", s["idle_runs"], "runs", None, idle_say),
    card("Last merge", vclass, last_any_clock, "", lambda r: r["last_at"], since_say,
         wide=True),
]

since_rows = "".join(
    '<div class="mrow"><span class="mname">%s</span><span class="mval %s">%s</span></div>'
    % (esc(r["name"]),
       "crit" if (r["since"] or 0) > 180 else ("warn" if (r["since"] or 0) > 60 else "good"),
       r["last_at"]) for r in rows)


def chips(entries):
    if not entries:
        return '<span class="chip chip-empty">empty</span>'
    cls = {"UNMERGEABLE": "crit", "MERGEABLE": "good"}
    return "".join('<span class="chip chip-%s" title="%s">#%d</span>'
                   % (cls.get(e["state"], "wait"), esc(e["state"]), e["n"])
                   for e in sorted(entries, key=lambda z: z["pos"]))


# One class per state -- never two states sharing one. The pair of (hue, fill) is what makes six
# readable out of four hues, and the fill is what survives greyscale and a colour-vision
# deficiency. `st-` rather than `seg-` so the chart's own segment classes cannot drift into this.
ORD = [("CLEAN", "st-clean"), ("BEHIND", "st-behind"), ("UNKNOWN", "st-unknown"),
       ("UNSTABLE", "st-unstable"), ("BLOCKED", "st-blocked"), ("DIRTY", "st-dirty")]

# What each state MEANS, shown on hover and read out to a screen reader. The strip is the one
# place a reader meets these words, and "UNKNOWN" tells nobody anything on its own.
STATE_SAY = {
    "CLEAN": "every required check green, nothing in the way",
    "BEHIND": "behind main; the queue rebases it, but this can hide a red required check",
    "UNKNOWN": "GitHub has not computed mergeability yet",
    "UNSTABLE": "a non-required check is red, which blocks no merge",
    "BLOCKED": "a required check is red or missing",
    "DIRTY": "conflicts with main; needs a person",
}


def bbar(b, total):
    if not total:
        return '<div class="bbar bbar-empty"></div>'
    return '<div class="bbar">%s</div>' % "".join(
        '<span class="seg %s" style="flex:%d" title="%s: %d -- %s"></span>'
        % (c, b[k], k, b[k], STATE_SAY[k])
        for k, c in ORD if b.get(k))


queue_rows = "".join(
    '<div class="qrow"><span class="mname">%s</span><span class="chips">%s</span></div>'
    % (esc(r["name"]), chips(r["entries"])) for r in rows)
mix_rows = "".join(
    '<div class="qrow qmix"><span class="mname">%s</span>%s<span class="mixn">%d</span></div>'
    % (esc(r["name"]), bbar(r["buckets"], r["open"]), r["open"]) for r in rows)

legend_mix = "".join('<span class="lg" title="%s: %s"><i class="sw %s"></i>%s</span>'
                     % (k, STATE_SAY[k], c, k) for k, c in ORD)

tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
out = (tpl
       .replace("{{CT}}", esc(s["generated_ct"]))
       .replace("{{UTC}}", esc(d["generated_utc"]))
       .replace("{{VERDICT}}", verdict).replace("{{VCLASS}}", vclass)
       .replace("{{SINCE_ANY}}", last_any_clock)
       .replace("{{CARDS}}", "".join(cards))
       .replace("{{WINDOW}}", str(s.get("chart_hours", s["window_h"])))
       .replace("{{QUEUE_ROWS}}", queue_rows)
       .replace("{{MIX_ROWS}}", mix_rows)
       .replace("{{LEGEND_MIX}}", legend_mix)
       .replace("{{SVGW}}", str(W)).replace("{{SVGH}}", str(H))
       .replace("{{GRID}}", grid).replace("{{BANDS}}", bands)
       .replace("{{BARS}}", "".join(bars)).replace("{{LINE}}", line).replace("{{DOTS}}", dots)
       .replace("{{LYL}}", lyl).replace("{{RYL}}", ryl).replace("{{XTK}}", xtk))
open(os.path.join(OUT, "board.html"), "w", encoding="utf-8", newline="\n").write(out)
print("board.html %d bytes | %s | last merge at %s | %d idle runs >=%dh, longest %dh"
      % (len(out), verdict, last_any_clock, s["idle_runs"], s["idle_run_min_h"],
         s["longest_idle_run_h"]))
