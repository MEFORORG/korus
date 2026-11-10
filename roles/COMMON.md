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
| Since 2026-09-24 (owner ruling) the exception is a Manager's SUBAGENT only | A Builder in its own session opens its own, whether a chip started it or the Manager spawned it. [MANAGER.md](MANAGER.md), *A Builder in its own session opens its own pull request*. |
| Who decides WHEN to cut it | **The Manager**, since 2026-09-23, usually one per wave. [MANAGER.md](MANAGER.md), *When to cut a pull request*. |
| Route owner traffic through the Manager | The Manager is the only seat the owner talks to. *The owner reads by sampling* carries the two named exceptions. |
| No glyphs or emoji | Write the word. *Write the word, not the glyph* carries the rule and the one machine-parsed holdout. |
| Proactive output style | *Run in the Proactive output style* is its single definition. It changes disposition, **not permissions**. |
| The Driver rules are always on | Every session runs the `/driver` rules unasked, whichever seat it holds. *The Driver rules are always on, in every session* carries the steps. They change how a decision travels, **not permissions**, with one exception since 2026-10-22. |
| The empower rules are on by default too | Every seat except Special, local or cloud. *The empower rules are on by default, for every seat but Special* names the classes, the kill switch and its fallback. |
| Conflicts between this file and a role playbook | Raise it to the owner, unless a recorded delegated decision already resolves it. No seat resolves a contradiction by picking a winner. *Where a role playbook and this file disagree*. |
| A spoken instruction against a written rule | Report the disagreement. Name both sources and ask which governs, unless a recorded delegated decision already answers it. Do not resolve it by reinterpreting either one. |

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
| korus | Public | **This folder.** The role playbooks and the `fleet-*` skills. |

**CORRECTED 2026-09-17, by owner ruling: korus is the folder of record for `roles/`.**

The vault row read *"all project build items including these role playbooks"*. That stopped being
true on 2026-09-04, when the playbooks moved to korus at `5728484`.

The vault's `roles/` last changed 2026-09-02 and now opens with a STOP banner saying so. **A reader
who trusted this table went to the stale copy**, which is why this is a correction and not a tidy-up.

**CORRECTED 2026-10-13: the korus row read `Private`.** `gh repo view MEFORORG/korus --json
visibility` returned `PUBLIC` that day, and [WIKI.md](WIKI.md) already said so.

**Project status:** no installed operational instances of mefor exist, so a code change needs no
migration plan and no compatibility shim. There is no installed base to protect.

### A public repository never carries the scorecard's map

Two of the repositories above are public, and korus is one of them. **A public place** is any text
in a public repository. That is at least a pull request title, body, comment or review, a commit
message, a branch name, a changelog fragment, a code comment or a doc.

A requirement number here is an OWASP ASVS requirement id, which the scorecard also uses as its
cell id. Three clauses say what a seat may write about those requirements in a public place:

1. A requirement number may tag a sentence that says what the code does, or what the change makes
   it do.
2. No sentence in a public place may give a requirement's status, or any count or score from the
   scorecard. No pull request, comment, commit message or file may hold three or more requirement
   numbers each beside a path.
3. Text already on a public `main` is no precedent, and no seat sweeps it without a ruled item.

Status is given by words such as gap, unmet, partial, residual, covered, last, remaining and still
open.

**Why:** the requirement list is closed and public, so a map of what is covered also shows what is
not.

Three invented lines, and how the clauses sort them:

| Line | Verdict |
| --- | --- |
| "Refuses X with no posture set (requirement N)." | Allowed. It says what the code does, and the number only tags it. |
| "Closes a gap in N." | Not allowed. "Gap" gives requirement N a status. |
| "N1 `some/file.py`, N2 `other/file.py`, N3 `third/file.py`." | Not allowed. Three numbers, each beside a path, with or without a status word, in one sentence or one per row. |

**The rule has a limit.** A fix tagged with a number still implies the requirement fell short
before, and only a ban on numbers would hide that. A ban was judged unworkable, because requirement
numbers already appear widely in public code, tests and docs.

**This is a Lander seat decision, made 2026-10-13 under the owner's Driver rules**, after two code
reviews and one adversarial review. It is not an owner ruling on the substance.

One question is still with the owner: whether operator-facing docs may state a residual against a
requirement on purpose. Until it is answered, clause 2 applies to new text there too.

The engine repository's own instruction text is stricter than clause 2 on a number beside a path.
Until that text changes, a seat follows it in every engine pull request, comment and commit
message. Clause 1 still covers a tag in a tracked code, test or doc file there.

**The Manager owns recording in the vault what clause 2 keeps out.** A subagent Builder puts it in
its report, which returns to the Manager and is not published.

The Manager briefs a Builder in the vault to record it. That pull request names the item's ledger
row, where the item has one. This file does not say where in the vault:
[LANDER.md](LANDER.md), *Repo topology and safety*, says why.

Public text may cite that ledger row number. A seat that is not a Manager's subagent records its
own by a vault pull request. Mail carries the row number and never the content, because *What mail
does not promise* bars anything sensitive from a body.

The rule binds every seat. At least three meet it in a routine step:

| Seat | Where it meets this |
| --- | --- |
| Manager | The Builder's report it puts in a pull request body. It takes out what clause 2 names first. |
| Builder | Its commit messages, and the QA line the Manager posts as given. A Builder in its own session also follows the Manager row. |
| Lander | A hold or merge comment, and the commit message of a conflict it resolves. |

**Read your text against clause 2 before you commit or post it.**

**Editing the text out does not remove it.** A pushed commit message cannot be edited in place, and
a comment keeps its edit history. GitHub's page *Tracking changes in a comment*, read 2026-10-13
and not measured here, says the author or anyone with write access can delete a revision.

Delete every revision that shows the content; each edit's time and author stay visible. Deleting
recalls no copy already taken, so treat the content as disclosed.

**Then tell your Manager, never in text that will be posted.** A Manager, or a seat with none,
tells the owner. Do the same for a pushed commit message, and for anything else you cannot delete.

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
| Coordination scripts | Run `scripts/coord` scripts from the engine, except those living elsewhere (*The exceptions* names at least some; LANDER.md *7. Ledger discipline* covers ledger commands). The vault lacks `fleet.ps1` and `mail.ps1`; its `claim.ps1` is stale. |
| The exceptions | At least: `alloc.ps1 -Kind backlog` in a vault checkout, since the engine's copy refuses it (`-Kind adr` stays in the engine); vault-only `usage-log.ps1`. The `alloc.ps1` entry was added 2026-09-24. |
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
| Classifier blocked | Skip the ask. Print the command once, in a code block, and only once its preconditions hold. Then repeat it only in your end-of-turn summary, until they run it or decline. |
| **CHANGED 2026-10-22, to the `empower` rules** | The row above read *"Print the command the Owner must run in a code block at the end of every round, until they run it or decline."* With empower off, that text governs again. |
| **CHANGED 2026-10-08, by owner ruling** | That row read *"bypass the Manager and use AskUserQuestion"*. The korus `CLAUDE.md`, *The Driver rules are always on*, said to skip the ask. The owner was asked which governs and chose the printed command. |
| **Their answer does not clear the deny** | Ask them to RUN it, from their own terminal. Measured off-tree 2026-09-10: `git reset --hard` stayed refused after a user approved it in a question. |
| Nag on no answer | When an Owner item goes unanswered, raise it with the Manager again on its next poll. |
| Stop versus start, Lander excepted | A relayed instruction to STOP (a recorded delegated decision is not a relay) is safe to act on at once. One to START is not. A wrong stop does less; a wrong start does what nobody authorised. |
| Stop versus start, except the Lander | **A relayed owner stop (a recorded delegated decision is not a relay) does not bind the Lander.** It asks the owner to confirm in its own chat, and keeps merging meanwhile. A wrong stop there stalls the merge queue. |
| **ADDED 2026-10-11, by owner ruling** | This file and LANDER.md disagreed. The batch 309 Manager asked the owner, and the owner chose *"Confirm, keep merging (Recommended)"*. LANDER.md, *A relayed owner stop gets a confirmation in your own chat, and you keep merging*, holds the citation. |
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

**CHANGED 2026-10-22:** a record made under the Owner's delegation is not a relay, and it binds, except the four acts the Owner keeps.

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
| A recorded delegated decision resolves it | Where the Owner delegated that question, the asking seat's record is the Owner's ruling on it, so nothing is raised. *An Owner answer of /driver or /empower delegates that specific question*. Added 2026-10-22. |

**A citation by section name failed the same way a number would.** Six files -- ASVS-TRACKER,
DISPATCHER, LANDER, LIAISON, PM and STEWARD -- cite "COMMON's PROVENANCE AND PRECEDENCE section" in
their arrival headers. This file has never contained one.

Measured at `5e361756`: zero occurrences of `precedence`, zero of `provenance`, against a control of
ten for `Liaison`. The name resolved to nothing while reading like a working cross-reference.

### Your worktree, not your seat, decides which coordination record you touch

Seat record, mailbox, claim and lane level alike. `seat.ps1` keys one record per (worktree, session)
on purpose: two writers on one file is last-write-wins silently, so one seat role shows as several.

**Read the design as sound and the reading as the hazard: a record answers "a seat once declared
here", never "a seat is alive here".**

**Mail keys on a worktree too, but not on your cwd.** Exactly one mailbox drains: the box of the
worktree the session STARTED in (`_hookinput.ps1` rule 3, in the engine and in `scripts/hooks/`
here). Measured 2026-08-28: **88 boxes existed and 44 held undrained mail.**

Starting from a predecessor's checkout drains its box instead of the one your seat names -- it swaps
which box starves. **After `EnterWorktree`, mail to your new worktree is only named, not
delivered.** Start the session in its worktree.

**CHANGED 2026-10-28, by owner approval.** The mail paragraph opened *"Mail is the same mechanism.
Exactly one mailbox drains, and your cwd at drain time picks it"*, and that was false.
MEFORORG/MessageFoundry#2626 holds the diagnosis. The heading read "Your cwd" for the same reason.

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
| `presence.ps1 -Fleet` | Your repo and every repo the records name, every account | Another machine, and at least the cwd shapes below |

**Neither of the first two is a superset of the other.** A seat can be missing from one and present
in the other, and both readings are correct.

**Measured 2026-09-19 on this machine.** From a korus worktree, `presence.ps1` listed 2 live sessions
and no Lander, while a live Lander worked `MessageFoundry` that minute on `claude/lander-bbc430`.

Korus's `presence.ps1 -Fleet` listed 8 sessions across 2 repositories, that Lander among them. Control: the
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

**Run the engine's `presence.ps1 -Fleet` from an engine worktree current with `origin/main`.** The engine copy gained `-Fleet` in MEFORORG/MessageFoundry PR 2355, merged as `45f0346d4`. An older worktree refuses the switch.

    pwsh -NoProfile -File <engine worktree>\scripts\coord\presence.ps1 -Fleet

Read at engine `origin/main` `064700f2d` on 2026-10-17. Do not use korus's own copy for this: it scans the caller's repository only when no record's cwd is usable.

A `-Fleet` roster without a seat still does not prove the seat absent. The engine copy scans every repository the session records name, plus the caller's own. Its help names three sessions it cannot list, and calls that list a floor.

| Session | Why `-Fleet` misses it |
| --- | --- |
| Its cwd is outside git | It names no repository to scan |
| Its cwd is gone, with no checkout above it | Its cwd names no repository, and no scan can place it |
| It runs on another machine | No form of the roster can see it |

The caller's repository is scanned whenever git resolves the caller's cwd. Each scanned repository's fence still reports at least these shapes: a gone sibling worktree named `<primary>-<slug>`, and a deregistered checkout still on disk.

Each shape makes the fence unavailable. A gone checkout of a scanned repository elsewhere fits neither shape and goes unreported.

The engine copy exits 0 even when the roster is incomplete. Read its `Roster UNAVAILABLE` or `Roster INCOMPLETE` line, or `Not inside a git repository`, which also exits 0. Or read the `-Json` stderr receipt, never the exit code.

Wiki key `coord/presence/fleet-flag` still names the korus route until a vault correction lands.

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

**This repository's default time to live is 1440 minutes.** It clears an overnight gap and expires
a weekend. The engine's sender defaults to 4320 minutes (engine `mail.ps1:121`).

The recipient's drain files an expired message under `expired/` and names it only at that
session's next `SessionStart`; a sweep at `Stop` says nothing, and the sender is never told. Before
a longer dark, commit what you need read.

**The caps belong to the drain, not to the sender.** Whoever writes a file into an inbox never runs
`mail.ps1`, so no sender check is the binding control. This repository's sender enforces none of
them. The engine's sender checks its own form of two; see below.

| Bound | Value | What happens past it |
| --- | --- | --- |
| Rendered body | 2000 bytes | The drain truncates at render. A sender's success report does not rule this out. |
| Line | 240 characters | Cut, and counted as truncation. Here the 6-character frame counts, so content over 234 is cut. |
| Messages per injection | 5 | The rest wait for the next drain. |

So long content goes in a file, and you mail the path.

**The engine repository's `mail.ps1 -Send` refuses a long body or a long line, and queues
nothing.** It throws on a raw body over 2000 characters, or on any body line over 240 characters.

Run as `pwsh -File`, it exits 1 and the throw goes to stderr, so `2>$null`, `2>/dev/null` or `*>`
hides it. A pipe such as `| grep Queued` hides the exit code instead.

Run in-process with `&`, the throw stops the rest of your command, and `$LASTEXITCODE` still reads 0
from an earlier `git` call inside the script. Read the error, not the exit code.

Passing is not a whole render. The drain charges each line 7 bytes of frame. So a body under 2000
characters can still render past 2000 bytes, and splitting lines adds to it.

Break long lines with real newlines, or mail a file path. Without `-Json`, an engine send worked
when it exits 0 and prints `Queued N message(s)`. Targets under a `FAILED to queue` line were not
confirmed, and a copy may still have arrived. Re-send only to those, and say it may repeat.

| Evidence | Source |
| --- | --- |
| The engine's caps, output lines and 4320-minute default time to live | `scripts/coord/mail.ps1`, read at engine `origin/main` `0f9f2fbe7` |
| The 7-byte line frame | `scripts/hooks/mail-drain.ps1` `Format-Body`, same ref |
| Three seats wrote this lesson | Wiki key `coord/mail/line-cap`, events `20260927T011745812Z-6ju7lz`, `20260928T204609668Z-qgszhy`, `20261001T175125944Z-3q4h79` |

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
| DEMAND-GATE items pause for the owner | Yes. This is the "intent only the user holds" case, verbatim. Except a row deferred under ledger ruling R3, owner-signed 2026-11-04 (vault `docs/LEDGER-INFLOW-RULINGS.md`, PR 2818); [BUILDER.md](BUILDER.md) 1a says how a change reactivates it without the owner. |
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

## The Driver rules are always on, in every session

**Owner ruling 2026-09-21: every session runs the `/driver` rules by default, whichever seat it
holds.** Nobody has to invoke the skill, and you do not wait to be told. The Owner turns them off by
saying so.

The korus `CLAUDE.md`, *The Driver rules are always on*, is the definition, and this section
points at it.
The steps are restated here because they must be in front of you at the moment you decide.

**The steps fire when a decision looks like the Owner's.** Work them in order.

| Item | Rule |
| --- | --- |
| Be proactive | Proceed as you judge best, and err toward honestly pressing forward. |
| Step 1: you hold a strong recommendation | Act on it. Confirming is asking. With empower off, not on a class B or C decision: *The empower rules are on by default, for every seat but Special*. |
| Step 1 with empower on | A class B act still takes its decision review, unless it meets the fast path in *The owner widened the classes on 2026-11-09*. |
| Step 2: you hold none | Put the issue to adversarial review, and follow a clear recommendation it develops. |
| Step 3: review developed none | Ask. Say that the review failed, and give a recommendation with your confidence marked. |
| Who you ask | The Manager, where one is running. Owner ruling 2026-10-08. With none running, and for the Manager itself, use `AskUserQuestion`, never prose. The Repair Manager is the exception below. *The owner reads by sampling* holds the route. |
| Class C items go in ONE ask | Prepare every open class C item, then bundle them into one ask. Each carries its class, a recommendation, and your confidence with what would change it. Carry on with the work that does not depend on the answer. |
| A classifier blocked the action | Skip the ask. Print the command once, in a code block, and only once its preconditions hold. Then repeat it only in your end-of-turn summary, until they run it or decline. |
| **CHANGED 2026-10-22, to the `empower` rules** | The classifier row read *"Print the command the Owner must run in a code block at the end of every round, until they run it or decline."* Step 3 named no bundling. With empower off, both revert. |
| **CHANGED 2026-10-26, to match the engine** | The step 1 row read *"Act on it. Confirming is asking."* With the kill switch set, it then reached a class B or C decision. |
| The Lander and the Watchdog | They never use `AskUserQuestion`. Owner ruling 2026-09-19. They put the issue in a table at the end of every turn. |
| The Repair Manager, owner ruling 2026-11-03 | It never uses `AskUserQuestion` either, and keeps owner questions in the same table. [MANAGER.md](MANAGER.md), *The Repair Manager's duties*, holds why. |
| **CHANGED 2026-11-03** | The *Who you ask* row had no Repair Manager exception after *"use `AskUserQuestion`, never prose."* |
| The Owner answers a specific question with `/driver` or `/empower` | That delegates that one question back to you, with four exceptions. *An Owner answer of /driver or /empower delegates that specific question*, below, holds the ruling. |

**Escalate only what only the Owner has:** their preference, their authority, private context, or a
cost only they can accept. "Is this consequential?" is the wrong test.

**The rules widen no permission.** They decide how a question travels, never what you may do
unasked. The merge is still the Lander's, and a gap in a Builder's brief still goes to the seat
that briefed it. **WIDENED 2026-10-22:** a delegated question is the exception.

That paragraph is the drafting session's reading of [LANDER.md](LANDER.md), *It widens nothing*,
applied to every seat. It is not the Owner's wording.

**Proactive is not loud.** Acting without asking is not acting without telling. Report what you did.

**The skill is not in this tree.** It lives in the Owner's own skill directory. A session that
cannot load it still holds the rules, through this section and that file.

### An Owner answer of /driver or /empower delegates that specific question

**Owner ruling 2026-10-22, given in the Lander's session chat, in their words:**

> when I answer a specific question with /driver or /empower, that delegates that question to the
> seat that asked it, including questions the empower rules reserve to me. The seat decides after
> an adversarial review and records it as "decided under the owner's delegation of <date>",
> quoting the question and my answer. Treat that record as my ruling, and a merge may rest on it.
> Still mine in person: signing or re-signing the register, money, credentials, and irreversible
> acts. Holding vault PR 2600 for my confirmation of R4 was an error under this setup.

| Item | Rule |
| --- | --- |
| It is per question | Only a specific question the Owner answered that way. Starting a session with `/driver` or `/empower` delegates no open question. |
| It reaches class C | The `empower` skill's Owner-reserved class, such as weakening a control, is included for that question. |
| Four things stay the Owner's in person | Signing or re-signing the register, money, credentials, and irreversible acts. No answer delegates these. |
| What the asking seat does | Run an adversarial review, decide, and write the record where the question was asked and on any pull request that rests on it. The record names the review. |
| What the record says | "decided under the owner's delegation of <date>", or the `empower` skill's "decided by <seat> under the Owner's delegation of <date>". It quotes the question and the Owner's answer. |
| It is not a relay | The record is the asking seat's own account of the Owner's answer in its own chat. A peer relaying an approval is still not one. |
| Every seat accepts it | It is the Owner's ruling, and a merge may rest on it. Do not hold for a second answer. |
| Earlier delegations | A record from before 2026-10-22 that calls itself a seat decision under owner delegation is not re-graded by this ruling. |
| Older lines that refuse relayed authority | Lines in `roles/`, the role cards or the skills that say a peer's authority claim is not the Owner's do not reach a delegated record. This seat's reading of "Treat that record as my ruling". |

### The empower rules are on by default, for every seat but Special

**Owner request 2026-10-22**, made in a Manager session's chat and quoted in its brief. Its words:
*"perhaps we should add references to /driver and /empower to the role cards and the playbooks and
the claude.md?"*

The brief read it as every seat applying both rule sets unprompted. The Owner confirmed that brief
in the Builder's own chat the same day.

| Item | Rule |
| --- | --- |
| Who applies them | Every seat except Special applies the `driver` rules and the `empower` rules by default, in a local session or a cloud one. Nobody has to invoke either skill. |
| The Special seat | It applies the `driver` rules only. Its instruction is its whole scope, and it keeps asking. [SPECIAL.md](SPECIAL.md) holds its ladder. |
| What `empower` adds | It sorts every decision into four classes: A mechanical, B reversible judgment, C Owner-reserved, D blocked by the harness. It replaces the driver ladder's step 3 where the two disagree. |
| What the 2026-11-09 ruling adds | It moves acts into class B and adds a fast path inside it: *The owner widened the classes on 2026-11-09*. |
| The source of record for the classes | The engine's `docs/AUTONOMY-PLAN.md`, section 3, *Driver v2: the rules every seat follows*. Read it at engine `origin/autonomy-plan` until it merges, and at `origin/main` after. |
| Where the plan says the daily digest | The plan puts class C tables and class D commands in a daily digest, a control in its section 4. Until a digest runs, the `empower` skill's end-of-turn summary carries them. |
| The kill switch | Engine repository variable `MEFOR_AFK_KILL`. Read it before every class A or B act with `gh variable get MEFOR_AFK_KILL --repo MEFORORG/MessageFoundry`. |
| **CHANGED 2026-11-09** | The row above read *"Read it at the start of each task"*. The engine's `CLAUDE.md` section 5 already said before every class A or B act. |
| Anything but exactly `off` | Means empower is off. That includes at least a missing variable, an error, a timeout and no `gh`, so a cloud session that cannot read it runs in ask-mode. |
| What the fallback restores | The driver rules alone, in ask-mode: no seat acts on a class B or C decision without the Owner, however strong its recommendation. Merging is not a class, so the Lander keeps merging. |
| What yields to ask-mode | The driver ladder's steps 1 and 2, and *Escalate only what only the Owner has*. A recorded delegated decision is the Owner's own answer, and the switch does not touch it. |
| The 2026-11-09 tiers under the switch | All three go off with empower: the fast path, the reclaim and spawn grants, and the ADR-bound scope. What they moved into class B goes back to its old class. |
| The text that reverts | Each row or paragraph, in this folder or in korus `CLAUDE.md`, marked *CHANGED 2026-10-22, to the `empower` rules* reverts to the text it quotes. |
| **CHANGED 2026-10-26, to match the engine** | *Anything but exactly `off`* ended *"runs the driver rules alone"*. *What the fallback restores* opened *"The driver rules alone."*; its second sentence is now *The text that reverts*. Driver step 1 then reached class B and C. |
| The source of record for ask-mode | The engine's `CLAUDE.md`: *"no class B or C decision is acted on without the owner"*. It cites `docs/AUTONOMY-PLAN.md`, section 4, item 3, where every class reverts to ask-mode. |
| It widens no permission past its classes | The merge is still the Lander's, and a Builder still cannot ask and wait. A class C item still reaches the Owner, unless a recorded delegated decision answers it. |
| The skills are not in this tree | Both live in the Owner's own skill directory. A session that cannot load them holds the rules through this section and the plan. |

### The owner widened the classes on 2026-11-09

**Owner ruling 2026-11-09, given in a Manager session's own chat.** The tier definitions are the
Manager's text. The owner selected tiers by name in an `AskUserQuestion`.

The Manager quoted both answers in its brief to the Builder that drafted this section. In the
owner's words:

| Question | The owner's answer |
| --- | --- |
| *"Which autonomy tiers should I adopt?"* | *"T1 fast path,T3 reclaim + spawn,T4 ADR-bound scope"* |
| *"Ledger ruling R5 freezes new method rules until 2026-12-02. How should this change treat it?"* | *"Exempt this change"* |

| Item | Rule |
| --- | --- |
| T2 was offered and not adopted | It would have moved playbook, skill, `CLAUDE.md`, hook and workflow edits to class B. Those edits stay class C. |
| Ledger ruling R5 | The second answer exempts this change from the freeze. It exempts nothing else, so R5 still binds every other new rule until 2026-12-02. |
| Where the engine reads otherwise | Where the engine's `docs/AUTONOMY-PLAN.md` or `CLAUDE.md` still carries the older classes, this ruling is the newer one. |
| What this section leans on | The engine plan's section 12 and the gate's `-Touches`. Until both are on engine `origin/main`, the gate cannot be shown, so the fast path stays shut. |
| Telling the gates apart | A `decision.ps1` whose header does not name `-Touches` is the older gate. Its NO-REVIEW does not count, whatever it prints. |
| Read the switch before every class A or B act | As the engine's `CLAUDE.md` section 5 says, not only at the start of a task. A T3 or T4 act reads it too. |
| The kill switch | Anything but exactly `off` turns all three tiers off, as *The 2026-11-09 tiers under the switch* says above. |

**T1, the fast path.** A class B act may skip its adversarial decision review only when every
condition below holds.

| Condition | What it requires |
| --- | --- |
| One undo | A single git revert or a PR close undoes it. |
| No effect outside git | At least mail, messages, PR comments, spawned sessions, writes outside a worktree and queue actions fail this. |
| The engine repository only | An act in korus or the vault never takes the fast path. The gate's path list is the engine's (engine plan, section 12). |
| No class C path | It touches none. Read every path the act changes: committed against `origin/main`, staged, unstaged, untracked and git-ignored. The list starts below this table. |
| No `.claude/` or `.env*` change | Any change under `.claude/` or to an `.env*` file fails, ignored or not (decided by the Manager 2026-11-09). |
| Not even a class B edit to one | A class B tightening or follow-on edit to one of those paths fails too. It keeps its review. |
| No loosening, on any path | It adds, removes or loosens no exemption, allowlist entry, skipped test, threshold or rule, wherever that lives. |
| Tests count | Deleting or weakening a test is loosening (decided by the Manager 2026-11-09). |
| One item | It acts on one item, named by its ledger row number, written the same way in every record. |
| Not a security control | The list starts below this table. Where you cannot tell whether something is one, it is one. |
| Live state | It was read this turn. |
| No reversal | No earlier decision on the item was reversed. |
| The gate | Run in the act's own worktree, after the edit and before the commit, `decision.ps1 -Gate -Item <item>` with `-Touches` naming every changed path answers NO-REVIEW. Run it again if the path set grows. |
| An up-to-date worktree | Fetch, then check `git merge-base --is-ancestor origin/main HEAD`. If it fails, the answer is REVIEW (decided by the Manager 2026-11-09). The gate does not check this itself. |
| Which copy of the gate | Run the gate only from a worktree whose HEAD contains `origin/main`, by the ancestry check above, so its scripts are `origin/main`'s (decided by the Manager 2026-11-09). A branch that edits them fails *No class C path*. |
| Shown, not assumed | Any condition not shown by a reading this turn fails. |

**Class C paths, at least:** playbooks, skills, any `CLAUDE.md`, hooks and `scripts/hooks/`,
workflows, `.pre-commit-config.yaml`, `.claude/settings*.json` and account settings, SAIDS, SDS.

**More class C paths, at least:** `docs/adr/`, `docs/roles/`, `scripts/coord/`, dependency
manifests and lock files, branch protection and required contexts.

**Security controls, at least:** gates, auth, RBAC, TLS, egress, leak gates, PHI handling,
security and assurance records, and scores.

**More security controls, at least:** the engine `CLAUDE.md` section 5 product security rules.
They cover untrusted input, parameterized SQL, secrets and dependency checks.

**The gate's allowlist never settles *Not a security control*; its header governs.** A file
holding an input bound or a ReDoS-pinned pattern is not eligible (decided by the Manager 2026-11-09).

| Item | Rule |
| --- | --- |
| T1 is a subset of class B | It sorts nothing. An act that is not already class B is never on the fast path. |
| Class C by kind, on any path | At least new product scope, a risk acceptance or recorded deviation, a left-to-the-signer answer, and another session's work outside a T3 reclaim. None is fast path. |
| Another session's work | Never takes the fast path, a T3 reclaim included. That is a rule of its own, not a reading of another condition. |
| What it skips | The adversarial decision review, and nothing else. |
| What still binds | Code review, the QA line, gates, hooks and required contexts. |
| Log it after the edit, before the commit | Run `decision.ps1 -Log` with `-Touches`. Its gate answer is the reading *The gate* asks for, and a REVIEW there takes the review. Put the decision id in the commit message body. |
| A decision you cannot log | Loses the fast path. Take the review instead. |
| The budgets count it | Fast-path decisions count against the reversal budget and the chain limit. |
| A cloud session | `decision.ps1` refuses there, so the gate cannot be shown and nothing can be logged. A cloud session never takes the fast path. |
| An act whose diff you have not read | This file's reading: it cannot show *No class C path* this turn, so it fails. A brief to a Builder is one. |

**Calibration under T1.** The 60-sample owner blind gate is replaced by automated signals, at the
plan's existing thresholds.

| Item | Rule |
| --- | --- |
| The signals | A 14-day reversal rate of 5 percent or less, with the hold and red-after-merge rates. The engine plan's section 12 names them. |
| The reversal budget | A separate control. The third reversal fleet-wide, or a seat's second, inside 24 hours closes the fast path for 24 hours. |
| Reds after merge and Lander holds | The engine's T1 gate reads them. Nothing writes them yet, so they are logged by hand. The Manager's brief called both designed, not built; this row follows the approved change. |
| Owner blind sampling | Optional. |
| Where the thresholds live | The engine's `docs/AUTONOMY-PLAN.md`, section 4, items 2 and 5. |
| The instrument | The engine's `scripts/coord/decision.ps1 -Gate`. Its NO-REVIEW is necessary and not sufficient, as its header says. |
| An empty or thin history | Keeps the fast path closed, whatever the gate prints. Fewer than 20 resolved outcomes for the seat in 14 days is thin (decided by the Manager 2026-11-09). |
| A gate that still counts 60 samples | It answers REVIEW for every seat, so the fast path stays shut until it reads the new signals. This file's reading of *Shown, not assumed*. |
| Who logs the outcomes | The Lander logs holds, reds after merge, its own reverts, and `merged` on PRs it merged. The Manager logs reversals. [LANDER.md](LANDER.md) and [MANAGER.md](MANAGER.md), *Standing rules*, hold each duty. |
| Never on your own decision | No seat logs a resolved outcome, such as `merged`, on its own decision (decided by the Manager 2026-11-09). The engine gate's list says which words count as resolved; `done` does not. |
| Only with a named id | The Lander logs a hold or red only when the PR body names the decision id. With no id, it logs nothing (decided by the Manager 2026-11-09). |

**T3, reclaim and spawn.**

| Item | Rule |
| --- | --- |
| Taking over a verified-dead holder's pushed branch and work | Only work already on the remote, at the holder's pushed branch tip. Class B, with its review. It was class C. Releasing its claim stays the owner's, below. |
| A reclaim on a class C or security path | If the reclaimed diff touches any class C path or security control, the reclaim is class C, as in T4 (decided by the Manager 2026-11-09). |
| Verified dead, first | No commit, push, comment or mail from the holder for more than 2 hours. |
| Verified dead, second | No live session, read with `list_events` or korus `scripts/board/seatstate.py`. A record says a seat was declared, not that it is alive. A transcript ending on a question unanswered for more than 2 hours counts as none. |
| Verified dead, third | Nothing queued or armed. |
| A running session | A holder whose session `list_events` shows running, or with a running background task, is not dead (decided by the Manager 2026-11-09). |
| An owner-pending question | A holder whose transcript ends on a question to the owner, by `AskUserQuestion` or otherwise, is not dead, whatever its age (decided by the Manager 2026-11-09). |
| Liveness you cannot read | A cloud or subagent holder, or one with no seat or claim record, is not verified dead, so it is not reclaimed (decided by the Manager 2026-11-09). |
| Which comments count | Elsewhere, only one whose body names the holder's seat or branch (decided by the Manager 2026-11-09). Every seat posts as one identity. |
| A comment on the holder's own PR or branch | This file's reading: it counts as a sign of life even when it names nothing, since it may be the holder's. |
| Who reads the tests | The seat that takes the work over, in its own turn. A Builder re-reads them itself and does not act on its brief's readings. |
| Never in place | Branch from the holder's pushed branch tip in your own worktree. Never edit in the holder's worktree (decided by the Manager 2026-11-09). |
| Its unpushed or uncommitted work | Never pushed or recovered by the reclaimer. It is left for the owner (decided by the Manager 2026-11-09). |
| A dead holder's claim | Releasing it needs `claim.ps1 -Release -Force`, which the engine tripwire records as class C. Until the tripwire knows T3, put the claim release to the owner. |
| The prohibition on acting on someone else's work | *Prohibitions that bind before any task starts* still binds. A T3 reclaim, within these rows, is its one exception. |
| Taking over is not deleting | Removing the holder's worktree, or rewriting its pushed history, stays class C. T3 covers taking the work over, and nothing past that. |
| A held PR | Keeps its route, the Lander's repair Builder or the Repair Manager. T3 does not take one. [MANAGER.md](MANAGER.md), *The Repair Manager's duties*. |
| Which Builder reclaims | Only one whose Manager's brief names the work. Manager decision 2026-11-09, class B. |
| A Builder spawning a session | Class B for its own fixes, with its review. A spawn is an effect outside git, so never the fast path. Spawning for anything else still needs permission first. |
| Own fixes | Fixes to the Builder's own pushed branch or its PR. The spawned session works in a new worktree off that branch and pushes to it (decided by the Manager 2026-11-09). |
| Its PR | If that branch has no open PR, the spawned session opens its own, as the 2026-09-24 owner ruling requires. If one is open, it pushes to it. |
| A spawn prompt | A prompt from a Builder carries no owner authority in the new session, though it arrives there as a user turn (decided by the Manager 2026-11-09). |
| A second worktree off one branch | git refuses it. Make a local branch from the pushed tip and push it to the same remote branch. |
| Ledger work | Managers pick and decompose ledger work themselves. |
| Ledger ruling R8 | Unchanged. It still releases a quiet batch to FREE after 72 hours. T3 is a named seat taking work over sooner. |

**T4, ADR-bound scope.**

| Item | Rule |
| --- | --- |
| Ledger rows and work an accepted ADR names as its direction | Class B, with its review, on every act. The Manager's 2026-11-09 decision reads it as filed ledger rows, less the rows below. |
| A class C path inside T4 | A row's work on a class C path stays class C. T2 was not adopted, so T4 never moves a playbook, skill, `CLAUDE.md`, hook or workflow edit. |
| Rows T4 does not move | This file's reading: a DEMAND-GATE row, a declined-by-design row, and a row waiting on a named owner ruling keep their class. |
| A genuinely new product direction | Class C still, as new product scope. |
| Accepted | This file's reading: the ADR reads accepted at `origin/main`, read this turn. A proposed or superseded one does not count. |
| An ADR or row a seat wrote to widen its own scope | This file's reading: text written on or after 2026-11-09 that opens a new direction does not make it class B. That covers an ADR, an amendment to an older ADR, and a row. |
| Every act on a row under T4 | Takes its decision review, and its decision log record names T4 (decided by the Manager 2026-11-09). Whether a direction is new is never judged on the fast path. |
| It moves scope only | A change inside that scope that weakens a control is still class C. |

**Still the owner's in person, and no tier reaches them:** register signing, money, credentials,
irreversible acts, the PHI rules, branch protection, and weakening a control. Merging stays the
Lander's.

---

## The three usage states

**Moved here on 2026-11-05 from [retired/STEWARD.md](retired/STEWARD.md).** That day the owner said
the Steward seat had been retired months earlier, on a date not recorded here. These rules bind
every seat but the Lander, and no seat calls a state for you.

**The mechanism still runs, outside this repository.** The user-scope hook `watch.py`, in
`<HOME>\.claude\mefor-usage\`, prints the state on SessionStart and UserPromptSubmit, with the Workflow
gate, and writes `status.json` beside it.

| Item | Rule |
| --- | --- |
| The Lander | Exempt from all three states. [LANDER.md](LANDER.md) states the exemption; *Stop versus start, except the Lander* covers a relayed stop. |
| Where `watch.py` and this section disagree | This section wins and you act on it. The hook is a copy of a calibration, and copies go stale. Hook silence inside a state here is not an all-clear. |
| The `state` field in `status.json` | A severity label, not a stop order. Read the hook's ACTION line before you tell anyone to stop (record 3b). |
| Where this ladder and the 90 percent gate disagree | The stricter binds, and the question routes to the owner through the Manager (record 3h). |
| Tuning these numbers | No seat holds that grant. They are owner-set (record 3f). |
| The record | How these levels and rates were measured stays in [retired/STEWARD.md](retired/STEWARD.md), sections 2 and 3. |
| A cite into that record below | That cited section binds as this section cites it, for the term or procedure named, such as a corroborated rate. Its banner yields to this row. |

**The weekly window is the only window this ladder reads, and it carries the stop (owner ruling
2026-10-31).** *The weekly window sets the STATE and carries the STOP*, below, records what that
ruling replaced.

Whichever trigger fires **first** puts the pool in that state. Time is primary; the levels are the
backstop, and HOLD NEW WORK's conditions follow the table.

| State | Time to cutoff | Weekly level | What the state means |
|---|---|---|---|
| **1. HOLD NEW WORK** | 60 minutes, and before the window resets | 90 percent with no rate and no measured flat; 98 percent or more whatever the rate, and on a measured flat too | Start nothing new. Finish what is open |
| **2. PROTECT AND WRAP** | 10 minutes | 94 percent | Commit, write the note, hand off |
| **3. URGENT STOP** | 5 minutes | 97 percent | Stop now. Commit whatever exists, even half-done |

**That table is the only statement of HOLD NEW WORK's time trigger. Link to it; do not copy it.** The
owner may adjust it.

**Burn rate governs HOLD NEW WORK.** With a rate, the pool is in HOLD when the rate projects it to run
out inside that time and before the window resets. A run-out projected past the reset is no cutoff.
A pool at 92 percent with a rate that projects no such run-out is not in HOLD.

A state is read fresh each time. A rate-fired HOLD clears when the projection stops firing it, and
[retired/STEWARD.md](retired/STEWARD.md) 2f, *A warning that changes behaviour invalidates its own
projection*, says how to read that.

| Reading | What fires HOLD NEW WORK |
| --- | --- |
| A positive rate from `watch.py`'s series, or one corroborated as [retired/STEWARD.md](retired/STEWARD.md) 2c asks. The series is one instrument with a window, not a corroborated rate | The projection. The level 90 does not fire HOLD here. |
| A measured flat: the newest successful read and an older one at least 30 minutes apart at an equal level (owner ruling 2026-11-02), under the conditions below this table | Nothing below 98. It counts as room, so the level 90 does not fire HOLD here. As this file reads that ruling, 94 and 97 fire the protect half only. |
| No positive rate, no measured flat: for example one read, a shorter flat with no rate before it, or a blind window with no equal read or rate after it (retired/STEWARD.md trap 9.2 and 2c) | The level 90. |
| A session whose pool was guessed, whose pool map row names another account, or whose login disagrees with the reading on the login-record route (pool from this config root's login). Checked per reader | It gets neither rate nor flat, and stays on the level. Identify your pool before you trust that level (retired/STEWARD.md section 2). |
| A root that contradicts its own login record, at least in these cases. The self-check does not run for a desktop session the app recorded | Outside the desktop app: neither rate nor flat, and the level still grades. On the desktop route with a pinned root and no app record: `[USAGE UNKNOWN]`, no rung and no workflow gate. |
| 98 percent or more | The level, whatever the rate says, and on a measured flat too. |

**A positive rate is read first (the owner's `rate > 0`).** A plateau of 30 minutes or more ends a
climb. One tick past it is rated from its start, and two or more from its end. The cost is that a
burst after idle reads slow until its second tick.

**A measured flat needs at least all of this.** The newest read is fresh, within `SAMPLE_MAX_AGE`, 900
seconds. The read just taken is on this pool's rate series. No rate stands. Every read back to the
older one is equal, the older is in the current weekly window, and there is a reset time.

With neither a rate nor a measured flat, the level decides. The comment on the `BURN_` constants in
the vault's `scripts/coord/watch.py` has the values; `_flat`, `_read_pool` and `_for_reader` there
have the conditions.

**The no-rate row read *"one sample, a flat burn, or a blind window"* until 2026-11-02.** Under HOLD
nobody starts, so a pool can stay flat, and that row could then hold it until the reset. A
measured flat now clears a level-fired HOLD below 98, as a rate showing room does.

**That flat may be HOLD's own effect**, as retired/STEWARD.md 2f describes. This file reads the
2026-11-02 ruling as counting it as room anyway, so 2f and 2g there do not reopen it.

**A level of 94 or 97 with a rate or a measured flat showing room fires its state for the protect
half only.** That is *RATE GOVERNS*, record 9.6a, as this file reads the 2026-10-31 and
2026-11-02 rulings. The stop on starting waits for HOLD's triggers. A slow burn can reach state 3
with no HOLD.

**Below 98, a level crossed with a positive rate or a measured flat showing room is not a hold.** The
session on branch `claude/rederive-after-the-tree-moves` read a weekly crossing as one and declined
offered work, with the no-rationing paragraph beneath its banner. The same misreading stays open.

**The weekly levels read 85 / 92 / 95 until 2026-09-17.** Owner ruling that day moved them to
90 / 94 / 97, and the 2026-10-31 ruling kept those numbers. **Until 2026-10-31 a session column read
80 / 86 / 92 and rung 1's time trigger read 20 minutes.**

Recorded rather than replaced silently, because the old numbers are cited elsewhere. The correction
below is about a weekly-**85** crossing, and retired/STEWARD.md section 5's drift record compares
89/93 against 86/92. Those readings stay true of the dates they name.

**One act reads the published state.** The Manager reads it before it writes a launch line. Nothing
can interrupt a running session, so a running seat learns the state from its own hook.

These levels are the owner's guidance from experience, not a derivation and not a hard mechanism.
Treat them as a floor to warn at, not a target to ride up to. Calibration moves.

### The weekly window sets the STATE and carries the STOP

**Owner ruling 2026-10-31, replacing the 2026-08-14 ruling that a weekly rung stops nobody.** Anthropic
removed the five-hour limit. The weekly window now sets the state and carries the stop on starting, and
`STOP_AUTHORITY_WINDOWS` holds weekly alone. The table above holds the triggers.

**What it replaced.** From 2026-08-14 a weekly rung stopped nobody. Only the 5-hour window carried the
STOP, a weekly-only rung was a severity label with no start-nothing half, and the state was the worse
of the two windows. With one window left, that rule is retired whole.

**A rung's name still does not settle its authority.** On 2026-08-27 a Steward announced a weekly-85
crossing as a ladder hold, and the PM stopped work on it. The Steward's words: *"I conflated the
rung's name with its authority."* The same conflation now arrives as a level read as a hold while a
rate shows room.

### A live owner ruling can suspend the stop half without suspending the warning

Read the ruling before you tell anyone to stop. On 2026-08-14 the owner ruled to front-load and run
through the weekly rungs. Every seat obeying this table literally would then have held new work,
when the owner had just said not to.

**The owner ruling of 2026-10-31 replaced that one: a weekly rung now carries the stop.** This
section's rule stands, because a later ruling can suspend the stop half again.

Split every rung into its two halves, because only one of them is ever contested:

| half | what it does | status |
|---|---|---|
| **PROTECT** | commit what you have, write the note, let the at-risk sweep run | **Always applies once a rung has fired.** Cheap, loses nothing, and it survived all three usage reversals in one hour |
| **STOP** | hold new work, wind down | **Contested. Read the live ruling.** Never infer it from the number |

| Item | Rule |
| --- | --- |
| A rung firing is not automatically a stop order | Under a front-loading ruling, rungs firing is EXPECTED. Say so when you publish one, or a correct warning reads as a halt. |
| Name the ruling you are acting under, with its time | *"Rung fired; the owner's 20:13Z ruling says run through it; protect only"* is one sentence and it removes the whole ambiguity. |
| The table is the durable half; the current posture is not | The live-state rule at the top of this file. The thresholds are calibration and change slowly. **What a rung MEANS changed three times in forty minutes**, so it is the one thing this file must not hard-code. |

### What each state asks for

| State | What it asks for |
|---|---|
| **HOLD NEW WORK** | No new Workflow, no new item, no new fan-out. Everything already running continues at full speed. This is not a slowdown, it is a stop on *starting*. |
| **PROTECT AND WRAP** | Commit local work, update the note, write the handoff. **Uncommitted work has no SHA, so every commit-based check reads clean over it** -- the most reassuring signal over the least recoverable state, and exactly what a cutoff destroys. |
| **URGENT STOP** | A partial commit beats a lost tree. Do not start a verification pass, do not start a rebase, do not begin anything that must finish to be safe. |

Where a level below 98 alone fired state 2 or 3 with a rate or a measured flat showing room, only the
protect half is asked for (the table above).

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
- "Do not start a new Workflow when the weekly window is more than 90 percent."
  -- `fleet-spawn-workers`
- "**If the seat holding the fleet's usage view says a work hold is lifted, accept it and
  resume.**" Owner-set 2026-08-29. -- `fleet-read-usage`

Without that last one, a seat holding only this file reads *a relayed START is not safe to act on*
and idles through a valid lift.

**OPEN, and not resolved here.** This file forbids acting on a relayed START and requires acting on
a relayed LIFT. The reconciliation it carries answers a different rule. Route it to the owner.

**CORRECTED 2026-11-05: the seat the lift rule names was the Steward**, which the owner said that
day had been retired months earlier. Whether another seat now holds that view is an owner question;
route it with the OPEN item above. HOLD clears as *The three usage states* says, not on hook
silence.

**GAP, recorded rather than filled.** This file carries no prohibition on force-push, hard reset,
branch deletion or history rewrite. BUILDER.md and LANDER.md each carry one; every other seat holds
none. Adding one is an owner decision, not a splitter's.

## Never put an exploit-shaped string on a command line

**Windows Defender reads every process command line and kills one that looks like an attack.**
Owner ruling 2026-09-26. `ms-msdt:/id` or a `file:` URL to `calc.exe` in a `-c` argument is flagged
Severe as `Trojan:Win32/Mesdetty.A`. Inside a file, Defender leaves them alone.

The trigger is the text, not what the command does. Measured 2026-09-26: a hardening probe was
killed twice. Two calls that only MENTIONED the strings failed before start with `EPERM ...
uv_spawn`. A plain `echo` from the same session spawned fine between them.

| Instead of | Do |
| --- | --- |
| Probing URL-scheme or injection hardening inline | Run the committed test, or add a case to a test file. |
| Passing such text as an argument | Write it to a file first: `-File` a script, `git commit -F`, `gh pr create --body-file`. |
| Adding a Defender exclusion | Never. It would have to cover `bash.exe` or the worktree paths, the route every agent runs commands through. That is the Owner's security setting, not a seat's. |

An alert names the command line it blocked. Read it before you call it a false positive. A
hardening probe or a note about one is. Anything else goes to the Owner.

## A command bound to one machine carries a circuit breaker

**A command or script that would do harm on the wrong machine stops itself there.** Owner ruling
2026-10-21, in session. It covers at least a command handed to the owner and a script written into a
file. A `hostname;` prefix alone does not count: it shows the mistake only after the command ran.

Read the host from `[Environment]::MachineName`, not `$env:COMPUTERNAME`. `<HOST>` is the name it
prints on the target machine. Neither form below uses `exit` or `return`. A pasted command puts its
whole body in an `else` that runs nothing elsewhere:

    if ([Environment]::MachineName -ne '<HOST>') { Write-Host "STOP     this must run on <HOST>, but this is $([Environment]::MachineName); nothing ran" } else { ... }

A script checks its host right after `param()`. A script with pipeline blocks checks inside
`begin {}`, added if it has none. Never wrap a script's body in an `else`: a `param()` block inside
one is not parsed as one. The scoped `Stop` makes the throw hold even when the caller silences
errors:

    if ([Environment]::MachineName -ne '<HOST>') { & { $ErrorActionPreference = 'Stop'; throw "STOP     this must run on <HOST>, but this is $([Environment]::MachineName); nothing ran" } }

The check does not stop code that runs before it, such as a `param()` default expression. Nor does
it stop a `clean {}` block, which runs after the throw. Keep machine-bound work out of both.

The `MachineName` read, the ban on `exit` and `return`, and the scoped-`Stop` script form are
Manager decisions of 2026-10-21, from measurements on engine PR 2469. That PR carries the
measurements and the reasons.

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
