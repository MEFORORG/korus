# The playbooks

<a id="tldrbluf"></a>

KORUS keeps short cards and full playbooks for its roles. Name the current playbook in the
session's opening prompt.

The roster changed on 2026-09-01, when seven seats retired. It changed again on 2026-09-10 and
2026-09-12. Older instructions may still route work to a seat that is gone.

The Special seat joined on 2026-09-16. It is an addition, not a replacement, so nothing retired to
make room for it.

The site serves the cards. Open the full playbooks in your checkout; nothing delivers them to a
session automatically.

---

## Use the Manager for new builds

Read `roles/COMMON.md` before your seat's playbook. It holds the rules shared by all seats.

| Seat | What it owns | Card | Playbook |
|---|---|---|---|
| Manager | Runs one or more Builders as subagents or separate sessions. Writes their briefs, reads their results, opens the pull request, and hands it to the Lander. | [Manager](roles/manager.card.md) | `roles/MANAGER.md` |
| Builder | One brief, one turn. Takes the claim, builds, runs a code-review subagent, commits, pushes, reports, exits. | [Builder](roles/builder.card.md) | `roles/BUILDER.md` |
| Steward | A cron rather than a seat. Reads usage and names the account with headroom. | [Steward](roles/steward.card.md) | `roles/STEWARD.md` |
| Lander | What enters the merge queue, and in what order. It owns a handed-over pull request from the handover on. | [Lander](roles/lander.card.md) | `roles/LANDER.md` |
| Special | Work the Owner wants done outside the other six. It stands by silently until instructed. | [Special](roles/special.card.md) | `roles/SPECIAL.md` |
| Watchdog | Watches another seat work and files what it learns where the affected seats read. It does not do the work it watches. | [Watchdog](roles/watchdog.card.md) | `roles/WATCHDOG.md` |

Cards live under `docs/`, which Jekyll builds into this site. Playbooks live at the repository root,
outside Jekyll's source directory, so this host has no page for them.

---

## The card is a summary and the playbook governs

A card holds the seat's scope, prohibitions, authority, arrival checks, and playbook path. Each card
has a 150-line and 6 KB cap.

Put open queues, item numbers, and blockers in dated notes. Keep them out of both cards and
playbooks.

A seat folder elsewhere failed this twice. In one case, a standing instruction became wrong after
the fix it awaited merged.

[Seats and worktrees](SEATS-AND-WORKTREES.md) covers how a card reaches a session.

---

## The seats that retired, and what replaced each

Seven seats retired on 2026-09-01, the Console on 2026-09-10, and a ninth seat on 2026-09-12.
Retired playbooks remain in `roles/retired/` as a record. Instructions that route work through
those seats are stale.

| Retired seat | What replaced it |
|---|---|
| The ninth seat to retire, 2026-09-12, deliberately unnamed | Nothing, by Owner decision. The review gate it fed was retired on 2026-09-04, so a pull request merges on its two required checks with no review step. |
| Console, 2026-09-10 | The Manager. Broad oversight across every account did not work. |
| Dispatcher | The Console replaced it in September 2026, then retired. Use the Manager. |
| Liaison | The Console replaced it in September 2026, then retired. The Owner talks to the Manager. |
| PM | Nothing, by Owner decision. |
| Cleaner | Nothing, by Owner decision. |
| Role manager | Nothing, by Owner decision. |
| Process improvement | Nothing, by Owner decision. |
| ASVS tracker | Nothing, by Owner decision. Renamed from ASVS monitor on 2026-08-13, then retired with the other five on 2026-09-01. |

A retired label returns no card and prints its retirement reason. This tells readers the missing
card was removed on purpose.

**RETRACTED 2026-09-12.** This section said the ASVS tracker had a playbook in `roles/retired/` but
no roster entry, and that its label returned nothing, including no retirement notice.

Both were true when written. `docs/roles/seats.json`'s retired map now carries `asvs-tracker` and
`asvs-monitor`, its former name, so the label returns a retirement notice like every other retired
seat.

---

## `roles/README.md` agrees with the roster, and this page said it did not

RETIRED 2026-09-08, the day this page first appeared: "It came across from a private vault, and it
still lists every seat in the table above as live."

That claim was false. This page copied it from CLAUDE.md without checking the file.

At `9658940`, `roles/README.md:22` names all seven retired seats in bold. Line 26 says not to route
work to them or read retired rows as live.

Section 1a listed the same seven live seats this page then listed. Section 1b lists the retired
files. This page and that section both show five now: the Console retired on 2026-09-10 and the
ninth seat on 2026-09-12.

As a control, `wc -l roles/README.md` returned 237. The search read a real document, not an empty
file.

CLAUDE.md's seat table remains the governing roster. We retire the claim that `roles/README.md`
contradicts it.

`COMMON-STAGED.md` and `LANDER-ROUTED-OUT.md` hold material awaiting a destination. They were split
out on 2026-09-05 and remain unedited.

The Owner has not yet chosen where each block belongs.

---

## Naming a playbook to a session

Name the full playbook in the first message:

```text
You are the Lander. Read roles/COMMON.md, then roles/LANDER.md, before anything else.
```

A [role card](ROLE-CARDS.md) keeps the seat's core rules available after compaction. The session still needs the full
playbook it points to.

---

## Related

[Seats and worktrees](SEATS-AND-WORKTREES.md) has how a seat reaches a session. [Role cards](ROLE-CARDS.md) has the card format and the design record.
[Run a KORUS build](KORUS-BUILD.md) has the shape a build runs in. [Worker brief](WORKER-BRIEF.md) has what to put in the opening prompt.

The [handoff diagram](KORUS-BUILD.md#g04) shows how work moves between the build roles.
