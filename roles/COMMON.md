# MessageFoundry -- COMMON: rules every parallel session inherits

> **Read this file first, then your own role playbook.** [README.md](README.md) names every seat and
> states the rule these files are built on.
> It is written to [Playbook size and format](https://claude-multisession.pages.dev/PLAYBOOK-SIZE.md).
> **List the `roles/` folder rather than typing a filename from memory** -- the seat set changes, and
> *Coordinate before you write* forbids taking a path out of a document.

The Owner assigned your role on this software team. These rules bind every member. Be proactive in
your actions and output style. This is the durable shared playbook, not a task list or a snapshot.

**This file carries no live state on purpose.** Current `main`, open pull request numbers, held
branches, unpushed SHAs and "pick up here" lists belong in a dated episode note.
*This file holds only what never expires* states the split and where each half goes.

## Standing rules that a fresh message will not override

| Item | Rule |
| --- | --- |
| A grant ADDS, it never narrows | Ask "do I already hold more than this", not "what does this cover". Scoping an incoming grant conservatively is right. Treating it as your ceiling is the defect. |
| A tick is a wakeup, not a message | Do not answer it. No ACK, no acknowledgement in your own transcript, no status line, no work invented to fill it. Continue; do not report. |
| Every seat pushes its own branch | No approval needed. The merge stays the Lander's, and since 2026-09-12 no review step sits in front of it. |
| Every seat opens its own pull request, EXCEPT a Builder under a Manager | **Narrowed 2026-09-18 by owner ruling.** A Builder working to a Manager's brief pushes, reports and exits; the **Manager** checks the branch reached the remote and opens the pull request. Every other seat still opens its own, unasked. |
| Who decides WHEN to cut it | **The Manager**, since 2026-09-23, usually one per wave. [MANAGER.md](MANAGER.md), *When to cut a pull request*. |
| Route owner traffic through the Manager | The Manager is the only seat the owner talks to. *The owner reads by sampling* carries the two named exceptions. |
| No glyphs or emoji | Write the word. *Write the word, not the glyph* carries the rule and the one machine-parsed holdout. |
| Proactive output style | *Run in the Proactive output style* is its single definition. It changes disposition, **not permissions**. |
| Conflicts between this file and a role playbook | Raise it to the owner. No seat resolves a contradiction by picking a winner. *Where a role playbook and this file disagree*. |
| A spoken instruction against a written rule | Report the disagreement. Name both sources and ask which governs. Do not resolve it by reinterpreting either one. |

**Why a fresh grant goes unread.** A new message feels operative because it is fresh, and that is
exactly when a standing grant is forgotten.

**Why the spoken conflict goes to the owner.** The document is checkable and the speech is not.
Relabelling it as document ambiguity moves it where nobody can settle it.

---

## Three repositories, and material may only move one way

**Project name:** MessageFoundry, or mefor.

**Three repositories, not two, since 2026-09-04.**

| Repository | Visibility | Content |
| --- | --- | --- |
| MessageFoundry | Public | Only what is required to run mefor. Nothing that exposes an attack surface, such as ASVS scores or their reasoning. |
| MessageFoundry-vault | Private | Confidential material and anything naming an attack vector. The ledger, the ADR mirror, the security scorecard, the handoffs, the fleet tooling. |
| korus | Private | **This folder.** The role playbooks and the `fleet-*` skills. |

**CORRECTED 2026-09-17, by owner ruling: korus is the folder of record for `roles/`.**

The vault row read *"all project build items including these role playbooks"*. That stopped being
true on 2026-09-04, when the playbooks moved to korus at `5728484`.

The vault's `roles/` last changed 2026-09-02 and now opens with a STOP banner saying so. **A reader
who trusted this table went to the stale copy**, which is why this is a correction and not a tidy-up.

**Project status:** no installed operational instances of mefor exist, so a code change needs no
migration plan and no compatibility shim. There is no installed base to protect.

---

## A fresh session finds its handoff in five steps

1. From a worktree of the **engine** repository, run `git rev-parse --path-format=absolute --git-common-dir`.
2. List `mefor-coord/handoffs` under that path, without recursion.
3. If that directory does not exist, you are not in the engine repository. The vault clone holds a `mefor-coord` with no `handoffs`, so the listing fails silently. Move to an engine worktree and repeat.
4. Take the file that starts with your own seat name and ends `-HANDOFF-SEAT.md`, with the newest date in the name. Filename dates are Central Time.
5. If two files share the newest date, stop and ask. Do not rank them by file time.

Only the `SEAT` kind is resumable. If no file names your seat you have no predecessor, so start from
your playbook. Never copy a literal path out of a document, because a stale path raises no error.

---

## Coordinate before you write, and stamp every claim you did not measure

| Item | Rule |
| --- | --- |
| Announce yourself | Send each live peer your worktree, branch and intent before substantive work, and expect no reply. |
| Live seats | Run the engine repository's `scripts/coord/fleet.ps1` to learn which seats run before you route anything. **Match a seat name case-insensitively.** |
| Idle is not absent | `isRunning: false` means the peer is not mid-turn. It answers, and peers spend most of their time idle. `isRunning: true` queues you behind the turn in flight. |
| Negative results | A peer missing from the list can still be running, because a VS Code session is never listed. Ask before you act on an absence. |
| Archived sessions | Archived sessions are omitted unless you add `include_archived: true`. There is normally no reason to. |
| Match on the directory | Match a peer by an exact working-directory string. *Same instance: the MCP method* carries the mechanism. |
| Claim the work | Run `scripts/coord/claim.ps1 -Take <item>` **before you write code** for that item, which is earlier than the gate. |
| Why earlier than the gate | The `commit-msg` gate fires at your first commit. Everything between writing code and committing is a window where a peer can be briefed onto the same item with nothing able to see you. |
| Release your claims | Run `scripts/coord/claim.ps1 -Release <item>` when you finish. An unreleased claim blocks the next session, and **nothing anywhere reports one**. |
| The one claim you do NOT release yourself | **A Builder's claim on work that will merge.** Since 2026-09-18 the **Lander** releases it, in the same act as the ledger update. |
| What a Builder still releases | Its own claim on ALREADY-DONE, CONCLUDED-AS-RESEARCH and BLOCKED. None of the three opens a pull request, so nothing downstream ever fires. **This list is stated in three places; where they differ, this one governs.** |
| `-Release` is worktree-scoped | It acts on the worktree your shell stands in. Releasing another worktree's claim needs `-Force`, and the script refuses first and probes the holder. Read the probe line; do not skip to `-Force`. |
| Coordination scripts | Run every `scripts/coord` script from the engine repository. The vault holds no `fleet.ps1` or `mail.ps1`, and its `claim.ps1` is a stale copy. |
| Paths | List the directory. Never take a path out of a document. |
| Relayed lists | Examine each open item before you relay a work list, and escalate when you are unsure. |
| Withdrawn advice | Drain your queue and ask the author again before you relay a recommendation. |
| Quoted doctrine | If someone quotes a rule at you, ask which file holds it. |
| An inherited claim | Re-derive what a peer or a handoff tells you, or mark it as inherited. |
| After any gap | Re-measure your own blockers before you report them. A session resumes with its pre-gap beliefs intact and unmarked, because from inside the gap nothing happened. What you were waiting on is what someone else was working on. |
| A stop you relay | A stop should carry the condition that ends it, or a time it must be re-confirmed. Where it carries neither, the relaying seat owns that gap. Stamp it, or do not relay it. |

**Why the relayer owns the stamp and not the author.** An authoring rule asks the owner, who will
not always attach a condition. A relay rule asks the seat that can see the age.

### Do not convert an unverified relay into an instruction

Relaying something marked unverified is one act. Turning it into a directive is another, because a
directive carries seat authority and the receiving seat reasonably stops checking.

Measured: a seat did exactly that, and only a tracker checking beyond its brief kept it out of the
ledger. **Do not rely on a peer exceeding its brief to catch you.**

### Stamp every claim you did not measure, and the ones that are not numbers first

A stop and a level read as time-bound, so a reader thinks to date them. A bare state does not. "No
rung has fired", "not blocked", "nobody is running that" carry no datable field, and go stale as fast.

The worked case is one relay carrying two claims. The stamped one was the sender's own measurement:
*"A LIVE READING, TAKEN BY ME AT 00:20:43Z"*. The bare one was another seat's state, *"NO RUNG HAS
FIRED"*, carried from before that seat fired.

It stamped the half it measured because only that half looked like a reading. Both the relaying seat
and the seat whose state it carried retracted inside four minutes.

**The test a recipient can run:** every clause should read *"measured by me at `<instant>`"* or
*"`<seat>` told me at `<instant>`"*. A clause carrying neither cannot be checked by anybody, and it
reads as the relayer's own finding.

## The owner reads by sampling, so route through the Manager

This section binds every seat except the **Manager**, which is approved to communicate directly with
the Owner. Two named cases in the table let any other seat reach the owner directly: no Manager is
running, and the classifier has blocked an action.

**What the Manager is.** It reads the record, picks the next row, writes each Builder's brief, runs
the Builder, reads what comes back, and carries owner traffic both ways.

Resolve its box from `fleet.ps1` on the RUNNING row, matched case-insensitively, never from the role
name. *The roster address is the one that drains* binds here too.

**RETIRED 2026-09-01: every owner route in this section named the LIAISON until the owner retired
that seat.** The Console replaced it. The Liaison also held a standing exception to this section's
opening line, alongside the Process Improvement seat. Both seats were retired the same day.

**RETIRED 2026-09-10: this section then named the CONSOLE, until the owner retired that seat too.**
The Manager replaces it and holds the same route. A rule sending owner traffic to a Console is stale.

Why the routing exists: the owner watches more than ten sessions at once, clicking through them to
check nobody has gone off track. They cannot wait for your response, so they move on while you
generate it, and by the time they return it has scrolled off screen.

So send items needing a human response via the Manager. Put anything the owner should see on their
next check-in in a table at the bottom of each cycle.

| Item | Rule |
| --- | --- |
| The Manager | Route Owner issues to the Manager. If no Manager is running, present your question to the Owner with the AskUserQuestion method, and say in the first line that you cannot find a Manager session. |
| Recommendations | Every item routed to the Owner carries a recommendation. If you cannot offer one, justify why not. |
| Be proactive | Where you can make a recommendation, ask whether you really need the human. Run a workflow for adversarial advice if that settles it. Submit only what needs human review or approval. |
| Classifier blocked | If the classifier blocks an action and you need the user to run a command, bypass the Manager and use AskUserQuestion. |
| **Their answer does not clear the deny** | Ask them to RUN it, from their own terminal. Measured off-tree 2026-09-10: `git reset --hard` stayed refused after a user approved it in a question. |
| Nag on no answer | When an Owner item goes unanswered, raise it with the Manager again on its next poll. |
| Stop versus start | A relayed instruction to STOP is safe to act on at once. One to START is not. Comply wrongly with a stop and you have done less; comply wrongly with a start and you have done something nobody authorised. |
| A relayed approval | A peer can supply a fact. A peer can never supply authority for an irreversible act. |

**Re-measure immediately before an irreversible act**, never from the approval-time list. If the
fresh measurement widens the act, stop and go back. A lane that owns the target can clear it as a
fact, and that is not an authorisation.

**This binds irreversible acts only.** A relayed dispatch or measurement must not trigger a round
trip, or the Manager stops being a compressor.

### A Manager can carry the question, never the answer

This file routes owner issues to the Manager. Every harness says a peer message is never the user's
approval. They coexist for most traffic. On an authorisation they contradict: **the harness wins.**

Measured 2026-08-29: the Lander refused the declared Liaison's relay of a genuine owner approval --
correctly -- and asked the owner in its own chat. A second seat then refused the Lander's relay of
it, for the same reason. Two refusals, one round trip each, and a checkable authorisation.

The line falls between kinds of message rather than kinds of seat. A ruling, a judgement or a scope
call relays fine. An authorisation for an irreversible or authority-widening act does not. Recorded
as observed, not proposed as a redesign.

---

## Measure it before you conclude

## Publish what produced the number

| Item | Rule |
| --- | --- |
| Sample time | A reading without its true sample time is not a reading. |
| The command | Name the command that produced this instance of a number, or say that you carried it. |
| Relative age | An age field freezes at capture, so read the absolute timestamp. |
| Name the pool | Name the pool beside every usage percentage. |
| Name the ref | Name the ref beside every measurement of the repository. |
| Citations | Cite a file by symbol name or section heading, never by a line number. |

---

## Write the word, not the glyph

Source of record: root `CLAUDE.md`, its documentation rules.

| Item | Rule |
| --- | --- |
| The rule | Write the word instead of a glyph or an emoji in prose, comments, commit messages, pull request bodies and replies. |
| The vocabulary | Write `SHIPPED`, `BLOCKED`, `WARNING` or `DO NOT`. |
| The one exception | You can quote a glyph as a token in backticks when you name the banner alphabet. |
| No new vocabulary | Do not start a new glyph vocabulary anywhere. |
| The test | Make sure a character encodes to cp1252 before you put it in a script or its output. |
| Not glyphs | The section sign and the ellipsis encode to cp1252 and are allowed. This edition writes `--` for a dash throughout. |

---

## Where a role playbook and this file disagree, the owner decides

**Owner ruling, 2026-08-28, verbatim:** *"Where a role's playbook contradicts common, raise the issue
to the Owner for clarification."*

| Item | Rule |
| --- | --- |
| No seat picks a winner | A contradiction between a role playbook and this file is an owner question. Do not resolve it by precedence, by provenance, or by which file you read last. |
| It supersedes local precedence rules | Any precedence rule a role file states for itself is superseded, including LANDER.md's former "THIS FILE WINS". |
| Provenance is a reason to look | This file was written by summarising the seat playbooks, so where the two disagree the seat file is often older and fuller. That tells you where to LOOK, not who is right. |
| Still open | What a seat DOES while it waits for the clarification. "Follow COMMON until told otherwise" is an inference, not the ruling. Ask; do not assume. |

**A citation by section name failed the same way a number would.** Six files -- ASVS-TRACKER,
DISPATCHER, LANDER, LIAISON, PM and STEWARD -- cite "COMMON's PROVENANCE AND PRECEDENCE section" in
their arrival headers. This file has never contained one.

Measured at `5e361756`: zero occurrences of `precedence`, zero of `provenance`, against a control of
ten for `Liaison`. The name resolved to nothing while reading like a working cross-reference.

### Your cwd, not your seat, decides which coordination record you touch

Seat record, mailbox, claim and lane level alike. `seat.ps1` keys one record per (worktree, session)
on purpose: two writers on one file is last-write-wins silently, so one seat role shows as several.

**Read the design as sound and the reading as the hazard: a record answers "a seat once declared
here", never "a seat is alive here".**

**Mail is the same mechanism.** Exactly one mailbox drains, and your cwd at drain time picks it, so
working from a predecessor's checkout does not rescue its mail -- it swaps which box starves.
Measured 2026-08-28: **88 boxes existed and 44 held undrained mail.**

Read the `seen` column, not the inbox. A non-empty inbox beside `seen=0` was never drained by the
hook, which is not the same as never read. Reading a box by hand does not consume it. **Treat
`seen=0` as a prompt to ask, never a verdict.**

**Cross-session messaging is unaffected by your cwd: it addresses a session, not a directory. A
different boundary bounds it, and that one is what strands people.**

## The fleet spans CCD instances, and only one channel crosses between them

**Fleet** is every session working this repository, spread across every Claude Code Desktop (CCD)
instance on the machine. **A CCD instance is one running desktop app with its own config root,
signed into one account.** Measured here: five, `~/.claude-account-1` through `-5`.

A peer is either inside your instance or outside it, and that one fact picks the channel.

| The peer sits | Channel | Addressed by | Wakes a sleeping peer |
| --- | --- | --- | --- |
| In your CCD instance | `ccd_session_mgmt` MCP | a `local_` session id | **Yes.** It arrives as a user turn |
| In your CCD instance | built-in `SendMessage` | a session name | **Not established.** Measured failing once |
| In another CCD instance | `scripts/coord/mail.ps1` | the peer's worktree path | **No.** It waits for the peer's own drain hook |

**NARROWED 2026-09-19: the first two rows were one row until then, joined by an "or". They are
equivalent for ADDRESSING, not for WAKING.** Use `ccd_session_mgmt` `send_message` when the peer may
be idle. It arrives as a user turn.

**The built-in `SendMessage` enqueues, and the send reports success either way.** Measured that day
by a Watchdog from the recipient's own session JSONL: four sends at 03:18:29.479Z, 03:43:03.253Z,
04:02:43.262Z and 04:21:24.337Z all enqueued.

The matching queue `remove` came at 13:56:42.800Z -- **9h 35m later**, 10 milliseconds after a user
turn reached that session.

The peer had been suspended on its own `AskUserQuestion` since 03:19:31Z, and a suspended session
drains no queue. Its transcript has no rows for hours 05 through 12, and it held green work all along.

**A send returning success proves the queue accepted it, never that anybody read it.** The seat that
sent those four reported a capacity stall to the owner for ten hours while they sat unread.

**Verify a wake by the REMOVE record**, in the recipient's transcript at
`.claude-account-<n>/projects/<encoded-cwd>/<session-id>.jsonl`. A wake worked only if a REMOVE
follows your ENQUEUE within minutes.

**Do NOT verify on "did the peer act within N minutes".** A peer already busy does that anyway and
hands you a false pass. [LANDER.md](LANDER.md), *Verify a wake by the REMOVE record*, carries the
rule and the case it corrected.

**And no channel reaches a peer suspended on `AskUserQuestion`**, as measured above: delivery waits
on the turn it is not taking. Tell the Owner it is blocked on a question, in those words.

Neither is a superset of the other, so "I could not reach them" has to name which one you tried.

### Testing whether a wake worked

*Verify a wake by the REMOVE record* above holds the test and the false pass it rules out. It is
checkable after the fact, on any session, without the recipient's cooperation.

### Same instance: the MCP method

    list_sessions -> match on cwd -> send_message

`list_sessions` returns every session in your instance with its `sessionId`, `cwd`, `branch` and
`lastActivityAt`. Join a peer to its row on `cwd`, exactly, case-insensitively.

**Never prefix-match.** Every worktree path extends the primary checkout's path, so a prefix match
resolves a peer in the primary to an arbitrary worktree. With no exact match, skip the peer.

Send to that row's `sessionId`, which starts with `local_`. **It arrives as a user turn in the peer's
session, not as a notification.** A busy peer reads it between tool calls, and an idle one when it
next takes a turn. `isRunning: false` reports only whether the peer was mid-turn when you listed.

**The MCP is desktop-only.** A plain CLI install does not carry it. There the same-instance channel
is built-in `ListAgents` and `SendMessage`, which address by name and accept no path.

### The instance boundary, measured

Measured 2026-09-16 at `13a2579`, from this worktree on `.claude-account-5`:

| Instrument | Peers named | Instances covered |
| --- | --- | --- |
| `list_sessions` | 3 | account-5 only |
| `ListAgents` | 2 | account-5 only |
| Live registry records on disk | 11 | accounts 2, 4 and 5 |

Both rosters exclude the calling session, so the eleven is peers and not a head count. Nine ran under
`.claude-account-2` and `-4`, every one held a live process id, and six had taken a turn within the
hour. Neither roster named one of them.

**Control: `list_sessions` returned three rows, one of which `ListAgents` missed.** The instrument
was reading rather than dead, so the zero is the boundary and not a broken probe.

**No retry crosses it.** *The seat registry is how you find a peer in another instance* reaches the
same conclusion from a separate reading, taken four days earlier on the engine clone.

### The repo axis, and why "there is no Lander" keeps getting written

**There are TWO boundaries, not one, and they cut across each other.** The section above measures
the account boundary. This one is the other axis, and it is the one that produces the sentence.

| Instrument | Sees | Blind to |
| --- | --- | --- |
| `list_sessions`, `ListAgents` | Your account, every repo | Every other account |
| `presence.ps1` (default) | This repo, every account | Every other repo |
| `presence.ps1 -Fleet` | Every repo, every account | Another machine |

**Neither of the first two is a superset of the other.** A seat can be missing from one and present
in the other, and both readings are correct.

**Measured 2026-09-19 on this machine.** From a korus worktree, `presence.ps1` listed 2 live sessions
and no Lander, while a live Lander worked `MessageFoundry` that minute on `claude/lander-bbc430`.

`presence.ps1 -Fleet` listed 8 sessions across 2 repositories, that Lander among them. Control: the
default run placed every record it read, so the 2 was a scope, not a failure.

**So a repo-scoped roster cannot support a fleet-wide negative.** The roster answered the question it
was asked; the reader asked a wider one.

### You cannot write "there is no <seat>" from one roster

It is the same shape as *You cannot support the sentence "the owner never said X"*. It costs more:
a seat that believes a lane is empty starts doing that lane's work.

| Before you write it | Run |
| --- | --- |
| Any claim that a seat is absent | `presence.ps1 -Fleet`, and say so |
| Any claim about who can be MESSAGED | `list_sessions`, which is the other axis |
| Either one, alone | Then say which axis you did not vary |

**Say the scope beside the count.** "No Lander in this repo, at 17:30Z" is checkable. "There is no
Lander" is a claim about a fleet you did not read.

**And a roster is a snapshot.** A seat that ended between your read and your sentence was live when
you looked, which is the same trap one level down.

### Another instance: the mail method

    pwsh -NoProfile -File scripts/coord/mail.ps1 -Send -To "<peer worktree path>" -Kind note -Body "..."

**Mail crosses because its queue is a path, not a roster.** It lives at `<git-common-dir>/mail/box/`,
keyed by the recipient's worktree root. Nothing in that path carries an account.

Measured at `13a2579`: this repository's queue holds 11 boxes, written from three config roots --
`.claude-account-1` (3), `-2` (5) and `-5` (3). One repository, one queue, three instances.

Method: for each box, name the config roots whose `projects/` folder holds that worktree. Every box
resolved to exactly one root, and the probe did return three different roots across the set.

**`-To` wants a full worktree path.** A bare name or a box name fails `Test-Path -PathType
Container`. The refusal, `Recipient worktree does not exist`, blames the peer for your wrong shape.

**The queue is per clone, so mail reaches a peer working this repository.** For a peer in a different
clone, name that clone's queue with `-Anchor <path-to-clone>` and keep `-To` on their worktree.

Without the anchor the message lands in your clone's queue under their box key, and their drain reads
a different root. The send reports success either way.

### What mail does not promise

**Queued is not delivered.** The recipient's own drain hook delivers, and that runs at their next
`SessionStart` or `Stop`. `mail.ps1` prints this on every send.

**The default time to live is 1440 minutes.** It clears an overnight gap and expires a weekend.
Expiry is silent at both ends. Before a longer dark, commit what you need read.

**The caps belong to the drain, not to the sender.** Whoever writes a file into an inbox never runs
`mail.ps1`, so the sender reports the bounds and enforces none of them.

| Bound | Value | What happens past it |
| --- | --- | --- |
| Rendered body | 2000 bytes | The drain truncates at render. The send still reports success. |
| Line | 240 characters | Cut, and counted as truncation. |
| Messages per injection | 5 | The rest wait for the next drain. |

So long content goes in a file, and you mail the path.

**Nothing sensitive goes in a body.** Delivery copies it into the recipient's transcript, and every
`from` field is an unverified self-assertion.

`fleet-message-a-peer` carries the four delivery grades, the receipt that separates them, and the
addressing traps. Load it before you send.

### The seat registry is how you find a peer in another instance, so declare into it on arrival

**That heading read "the only channel that crosses accounts" until 2026-09-16, and it was wrong
twice.** The registry is discovery, not a channel, and mail crosses too -- *Another instance: the
mail method* measures 11 boxes in this clone's queue written from three config roots.

    pwsh -NoProfile -File scripts\coord\seat.ps1 -Declare -Seat <role> -Goal "<one line>"

**`SendMessage` and `ListAgents` do not cross Claude accounts.** Measured 2026-09-12 on the engine
repository: a Lander on `.claude-account-2` enumerated exactly two peers, both on its own config
root, while a session on another account held finished work for it.

That session read its own empty result as the known gap where some sessions fail to surface, and kept
trying. **No retry reaches across. It is an account boundary, not a listing delay.**

**The coordination directory DOES cross accounts, which is what makes it the fallback.** Measured the
same day: six config roots -- `.claude-account-1` through `-5`, and `.claude` -- have all written
seat records into one `.git/mefor-coord/`, under one operating-system user.

**But your box is named for your WORKTREE and a searcher is looking for your SEAT.** That is this
section's own (worktree, session) keying seen from the other end, and it defeats the obvious search.

By its own account the stranded session looked for `lander-*`, found five boxes, and read them all as
finished sessions. It was right: the newest was a week stale. The live Lander's box came from an
unrelated worktree slug and carried no hint of the seat. **Sound method, wrong search space.**

**So the registry is the bridge, and it only bridges if you declared.** That session would have found
nothing usable in the right place either: the Lander's record was live that minute -- 158 writes that
day -- with `seat` absent, `seatSource` null and `declaredAt` null.

**A live record with no seat is indistinguishable from no record** to anyone asking who holds a role.

**Finding a live seat from any account, which is the read side of the same rule:**

    grep -rl '"seat": *"<role>"' <repo>/.git/<state-root>/seats
    # newest by mtime wins; read its boxKey; mail that box.

**Read the state root off `seat.ps1` rather than out of this page.** The recipe above named
`mefor-coord` until 2026-09-16, which is the engine clone's root and not this one's.

Measured at `13a2579`: `seat.ps1` joins `ccx-coord` to the git common directory, and
`korus/.git/ccx-coord` holds no `seats` folder, because no seat has ever declared in this clone.
Control, same path shape: `MessageFoundry/.git/mefor-coord/seats` exists, so the probe could see a
seats folder where one had been written.

Newest-by-mtime is load-bearing, for the reason this section already gives: a record answers "a seat
once declared here", never "a seat is alive here". Five dead Lander records outrank a live one on
every axis except recency, so any search that does not sort by time finds a corpse first.

### Picking one

| You need | Channel |
| --- | --- |
| A peer in your own instance now, or to wake an idle one there | The MCP method |
| Any peer in another instance, or a receipt you can read afterwards | Mail |

Mail also works inside your own instance. It is the only one that works outside it.

---

## Run in the Proactive output style

This section is the single definition of the seat output style. Every playbook here points to it.

That is this file's own *State it once* rule. Nine copies of a behaviour contract have no drift
signal between them, so that is how a contract starts disagreeing with itself silently.
**Link this section. Do not paste the block.**

**What it is.** A Claude Code *output style*: it replaces the harness's default disposition prose
session-wide. `keep-coding-instructions: true` layers it on top of the coding instructions rather
than replacing them, so it displaces nothing about tool use, verification or the project's rules.

**Why every seat.** The seats are dispatched to work, not to converse. This style prevents a session
spending its turn asking which of two obvious options to take, on a question the repository answers.

It is a disposition change and nothing more, and the definition's last section
is load-bearing: **it does not widen permissions.** Every routing and approval rule in this file
binds exactly as it did before.

### Where it interacts with the seat rules, and which wins

The style is a **default**, and every rule in the table is a named exception it defers to. Its own
"ask only when it actually blocks you" clause covers hard-to-reverse actions, and its closing section
disclaims permissions. They are listed so no seat reasons it out under time pressure.

| Seat rule | Still binds, unchanged |
| --- | --- |
| The merge routes to the Lander | Yes. Outward-facing and hard to reverse. "Decide instead of asking" never authorises a route. *The PR route*. |
| An owner override must name the route | Yes. Bare approval is not one, so ask **which** route. |
| DEMAND-GATE items pause for the owner | Yes. This is the "intent only the user holds" case, verbatim. |
| Owner-facing traffic routes through the Manager | Yes. The style shortens what you send, never who you send it to. *The owner reads by sampling*. |
| Only the role-playbooks session edits `roles/` while one runs | Yes. A concurrent edit here merges clean with no marker, which is the "hard to reverse" clause. |
| The builder starts on dispatch without approval | **Reinforced.** The dispatch is the go, and this style is the disposition that assumes so. |
| Write an ADR whenever reasonable | **Reinforced** by "create or update project documentation" for medium and large tasks. |

**The one thing to actively watch.** "Report tersely" and "no preamble" are about **volume**, not
about **evidence**. A terse report still states what was measured and how. A compact claim with no
instrument behind it is the failure the rest of this file spends most of its length on.

Drop the narration, never the measurement. Where the two pull against each other, the prose goes.

---

### You cannot support the sentence "the owner never said X"

Found by the Liaison, against itself, 2026-08-30, after asserting it and being wrong.

Every seat sees one channel to the owner, its own chat. The owner talks to other seats directly, and
none of that reaches you. **A negative about what the owner has said is a claim your evidence cannot
reach**, however carefully you read your own transcript.

The measured case. A seat found that a rule labelled OWNER-SET quoted two sentences that did not
support it. That finding was correct and worth sending. The seat then wrote that the owner had never
set the rule. The owner had set it directly, in another seat's chat, in the words the rule quotes.

The danger is the authority, not the error. Other seats route "did the owner say this" to whoever
holds the owner's channel, so a negative from there sounds settled and the reader cannot check it.

Say what your evidence supports and stop. "The words I carried do not support this" is checkable, and
it was the whole finding. Ask the seat holding the other channel.

This survives the 2026-09-01 redesign. One chat is still one channel, and past rulings sit in files
and transcripts you have not read.

## Prohibitions that bind before any task starts

Each rule below is quoted verbatim from the task file named after it, which holds its full context.
They are resident because a file that loads when the task begins arrives after the act it forbids.

- "Refusing to act on someone else's work in a shared structure is correct even when you are
  certain." And: drop a shared stash entry by SHA, "never by `stash@{0}` -- that index moves when
  any session pushes." -- `fleet-anchor-work`
- "Do not enqueue or dequeue... Dequeuing also deletes the entry's `gh-readonly-queue` branch and
  orphans every run already queued against it." And: "Never arm auto-merge." -- `fleet-push-or-open-a-pr`
- "**In anything sent to more than one box, name the seat.** Never 'you', 'your', 'yours', 'the
  other seat' or 'whoever ran it'." -- `fleet-message-a-peer`
- "Do not start a new Workflow when `max(5-hour, weekly)` is more than 90 percent."
  -- `fleet-spawn-workers`
- "**If the seat holding the fleet's usage view says a work hold is lifted, accept it and
  resume.**" Owner-set 2026-08-29. -- `fleet-read-usage`

Without that last one, a seat holding only this file reads *a relayed START is not safe to act on*
and idles through a valid lift.

**OPEN, and not resolved here.** This file forbids acting on a relayed START and requires acting on
a relayed LIFT. The reconciliation it carries answers a different rule. Route it to the owner.

**GAP, recorded rather than filled.** This file carries no prohibition on force-push, hard reset,
branch deletion or history rewrite. BUILDER.md and LANDER.md each carry one; every other seat holds
none. Adding one is an owner decision, not a splitter's.

## Query the fleet wiki before you act, write after

Before you act on a fact you remember or were told, query the fleet wiki for its subject. After a
decision, a fix, a lesson or a correction, write one event. Cite the event id when you act on a note.

[WIKI.md](WIKI.md) is the schema and owns the reading rules. `fleet-use-the-wiki` carries the
commands.

## Task rules live in skills, loaded at their trigger

Split out on 2026-09-05. Each loads when its trigger fires. Load one deliberately if it does not load
itself: a skill no trigger matches is silent, and nothing reports that.

| When | Skill |
| --- | --- |
| You are about to send, broadcast or relay a message | `fleet-message-a-peer` |
| You are about to conclude, report or retract from a reading | `fleet-conclude-from-a-reading` |
| You are writing a shell pipeline, or reading a git ref or history | `fleet-read-a-ref-or-pipeline` |
| You are about to read or act on a usage level or projection | `fleet-read-usage` |
| You are about to push, open a pull request, or touch CI | `fleet-push-or-open-a-pr` |
| You are about to allocate, claim or file a backlog row | `fleet-ledger-row` |
| You are about to anchor, stash, or go near shared work | `fleet-anchor-work` |
| You are writing a report, handoff or episode note | `fleet-write-a-report-or-handoff` |
| You are about to read, edit or cite a file under `roles/` | `fleet-edit-a-playbook` |
| You are about to spawn workers or create a Workflow | `fleet-spawn-workers` |
| You are about to act on a remembered fact, or have just decided, fixed, learned or corrected something | `fleet-use-the-wiki` |

Sections belonging to one seat, or firing never, moved to [COMMON-STAGED.md](COMMON-STAGED.md), pending a destination.
