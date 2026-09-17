# Feature Specification: The worker brief, for both kinds of worker

**Feature Branch**: `spec/001-worker-brief-v2`

**Created**: 2026-09-04

**Status**: Draft

**Supersedes**: pull request 43, closed unmerged 2026-09-04. That draft specified one worker kind
and was written three days before the second one existed. Its measurements survive here; four of
its counts were wrong and are corrected below with the needle that produced each.

**Governs**: [`docs/WORKER-BRIEF.md`](../../docs/WORKER-BRIEF.md), which is the current guidance and
predates the second worker kind.

---

## Why this exists

A brief is the whole of what a worker knows. It cannot ask a follow-up question cheaply, it cannot
read the conversation that produced it, and when it finishes it is gone. Everything the briefer
knows and does not write down is lost at the moment of the spawn.

`docs/WORKER-BRIEF.md` already says this and prescribes a template. This spec exists because the
document describes **one** kind of worker, the fleet now runs **two**, and the difference is not
cosmetic: it changes where a question can be sent, whose token budget the work spends, and whether
the work survives the worker's exit.

### The evidence this spec is built on

Eight briefs written for real work between 2026-08-30 and 2026-09-01, held outside this repository
in the operator's own working notes: **8 files, 869 lines, 49,366 bytes**. Five Builder or
iteration briefs, three briefs for a different seat, deliberately unnamed here.

The corpus is not published. It is one operator's real dispatch traffic and carries repository and
account detail that does not belong in a public repo, so every count below is stated with the needle
that produced it and cannot be recomputed from anything here. That is a real weakness of this spec
and it is named rather than hidden: a reader can check the reasoning but not the arithmetic.

Every count below names the needle that produced it, per Constitution Article VI. Counts are of
**this corpus only** and nothing here recomputes them. The corpus is small, it is all from one
operator over three days, and it is drawn from the briefs that happened to be kept, so it can show
that a practice **exists** and cannot show how common it is in general (Article IV).

---

## The two kinds of worker

Both take a brief. Almost nothing else about them is the same.

| | **Session worker** | **Subagent worker** |
|---|---|---|
| Started by | `claude -p` from a Manager | the Agent tool, in-process |
| Lifetime | outlives the session that started it | dies when the parent turn ends |
| Account | may be a **different** account from the briefer | always the **parent's** account |
| Budget | its own | drawn from the parent's remaining budget |
| Writes to | its own worktree, its own branch | the parent's worktree unless isolated |
| Output | commits, a pull request, a session record | a returned final message, plus any commits |
| Reachable by | session mail, pull request comment | nothing, the parent is the only reader |
| Needs a spawn grant | yes | no |
| Survives the briefer | yes | no |

**The distinction the corpus already found.** Of the eight briefs, three carry the prohibition
block, and **all three** replaced the document's `Write the question to the console` with
`Write the question in your final message`. Needle: the literal strings, case-insensitive,
whitespace-normalised.

**The needle no longer matches the corpus, and that does not change the finding.** The Console seat
retired on 2026-09-10, and the playbooks now read `Write the question to the Manager`. Re-run the
needle against `roles/` at a ref on or after that date and it returns zero. The measurement stands at
the ref it was taken at; the defect it found is about naming a SURFACE, and renaming the seat did not
fix that.

That substitution is correct, and it is not a rewording of convenience. A worker whose output is a
returned message has no console to write to. Three independent briefs made the same substitution
because the document's wording assumes a surface the worker does not have.

**This makes the canonical block a Constitution Article IX violation.** Article IX says no design
may require a particular surface. `the console` is a surface. The fix is not to pick one of the two
wordings; it is to name the **destination by its role** and let each worker kind resolve it.

---

## User Scenarios and Testing

### User Story 1 - A worker meets a question its brief does not answer (Priority: P1)

A worker is midway through its items and hits something it must know to proceed: which of two
files is authoritative, whether a failing test was already red, whether an item is in scope. The
briefer is not watching, and on a session worker may be on another account entirely.

**Why this priority**: this is the failure the whole brief contract exists to prevent. A worker
that guesses produces a pull request nobody can tell from a decided one, and the guess is
discovered downstream by a reader who has no way to know a guess happened.

**Independent Test**: give a worker a brief with a deliberate hole, run it, and check that it
stopped and asked rather than choosing. Fully testable with one worker and one brief.

**Acceptance Scenarios**:

1. **Given** a brief that omits an answer the worker needs, **When** the worker reaches the point
   of needing it, **Then** it writes the question to the two addresses its brief names and stops,
   and it does not choose a branch of the ambiguity.
2. **Given** the same brief, **When** the worker is a subagent with no console, **Then** it writes
   the question into its returned final message, which is the parent's only reader.
3. **Given** a worker that stopped and asked, **When** the briefer reads the question, **Then** the
   answer arrives as a **new brief**, not as a reply to the stopped worker, because the stopped
   worker is already gone.

---

### User Story 2 - A subagent's work has to outlive it (Priority: P1)

A Manager runs three subagent workers in one turn. Each does real work. The turn ends. Everything
in their context is gone, and the Manager holds only what each returned.

**Why this priority**: a session worker leaves commits, a branch and a session record behind by
default. A subagent leaves **nothing** unless its brief made it write something down first. This is
Constitution Article XI at the worker scale, and it is the failure mode that has no session-worker
equivalent.

**Independent Test**: run a subagent, let the parent turn end, and check whether a reader who was
not in that turn can find the work.

**Acceptance Scenarios**:

1. **Given** a subagent brief, **When** the subagent finishes, **Then** its work is on a branch, in
   a file, or in a pull request, something outside its own context.
2. **Given** a subagent that could not finish, **When** the parent turn ends, **Then** the
   unfinished state is recorded somewhere a later session can read, not only described in a
   returned message the parent may not persist.
3. **Given** two subagents briefed in one turn, **When** both write, **Then** their briefs named
   non-overlapping paths, because they share one worktree unless isolated.

---

### User Story 3 - Two workers must not collide (Priority: P1)

A briefer dispatches more than one worker against one repository.

**Why this priority**: collision is the founding problem of KORUS. The two worker kinds collide
differently. Session workers collide on **branches and the merge queue**; subagents collide on
**files in a single shared worktree**; and a brief that guards against one does not guard against
the other.

**Independent Test**: dispatch two workers with overlapping scope and observe whether either
brief prevented the overlap.

**Acceptance Scenarios**:

1. **Given** two session-worker briefs, **When** both are dispatched, **Then** each names a
   distinct branch and a distinct worktree.
2. **Given** two subagent briefs in one turn, **When** both are dispatched, **Then** each names
   the paths it owns, or one is given an isolated worktree.
3. **Given** a brief that claims an item, **When** a second brief claims a different item in the
   same file, **Then** the collision is still possible, because claiming an item is not claiming a
   path.

---

### User Story 4 - A briefer wants to know what a worker was allowed to do (Priority: P2)

Something a worker was told to do did not happen. The reader needs to know whether it refused,
failed, or was never able to.

**Why this priority**: it is diagnosis rather than prevention, so it ranks below the three above.
It matters because refusal and inability are indistinguishable from the outside, and the wrong
diagnosis sends the fix to the wrong place. Constitution Article III.

**Acceptance Scenarios**:

1. **Given** a worker that could not run a command, **When** it reports, **Then** the report
   carries the refusal **verbatim** rather than the worker's reading of it.
2. **Given** a verbatim refusal in a report, **When** a reader judges it, **Then** the reader
   re-runs it before overruling it.

---

### Edge Cases

- **The brief names a pull request that does not exist yet.** One of eight briefs sends questions
  to `the pull request you open`, an address that is empty at turn zero, which is exactly when a
  worker is most likely to find the brief incomplete. Needle: `the pull request you open`,
  1 of 8. The other two that name a pull request name an existing number.
- **The worker is on an account with a different grant.** Config roots carry different permission
  grants (Constitution Article VIII: 8, 10, 8, 8, 19 and 13 allow rules across six roots, and one
  of the six holds the spawn grant). A brief that tells a worker to do something its root forbids
  produces a refusal that reads as a worker failure.
- **A subagent is told to ask a coordinator.** It cannot. It has no mail lane and no pull request
  of its own until it opens one.
- **The parent turn ends while a subagent is mid-flight.** The subagent dies. Anything it had not
  written down is gone with no error anywhere.
- **A brief is copied from one worker kind to the other.** This is how the console-to-final-message
  drift entered the corpus, and nothing detects it.
- **The worker finishes early and has budget left.** Stopping is free; waiting is not
  (Constitution Article VII: waiting costs **22,275 tokens per waiting minute**, more than working,
  while idling costs zero). A brief must not tell a worker to wait for anything.

---

## Requirements

Each requirement is marked **[C]** if a machine can check it against a brief text, or **[J]** if it
needs a reader's judgment. The distinction is deliberate: pull request 43 mixed them and made the
whole set look automatable when about half of it is not.

### Universal, both worker kinds

- **FR-001** **[C]** A brief MUST state the one thing the worker owns, in a section that is the
  first heading in the document. *Corpus: `## Scope` is the first heading in **8 of 8**.*
- **FR-002** **[C]** A brief MUST name what the worker must not touch, explicitly rather than by
  implication.
- **FR-003** **[C]** A brief MUST state an end state a **different** reader can check without
  access to the worker's context.
- **FR-004** **[C]** A brief MUST list its items in order.
- **FR-005** **[C]** A brief MUST carry the ask-and-stop prohibition (FR-008), in the form matching
  its worker kind.
- **FR-006** **[J]** A brief MUST be sized so the worker can finish one turn without guessing. It
  does not have to answer everything; that is the bar `docs/WORKER-BRIEF.md` sets and it stands.
- **FR-007** **[C]** A brief MUST NOT instruct a worker to wait, sleep, poll, or watch for
  anything. Stopping is free and waiting is not.

### The prohibition

- **FR-008** **[C]** The ask-and-stop block MUST carry three clauses: **do not guess**, **do not
  wait**, and **stop**. These are the invariant part.
- **FR-009** **[C]** The block MUST name **two** destinations: one that reaches the briefer, and
  one that is attached to the work and survives the worker. The **roles** are invariant; the
  **surfaces** are resolved per worker kind, per Constitution Article IX.
- **FR-010** **[C]** The destinations resolve as follows, and a brief MUST use its row:

  | Worker kind | Reaches the briefer | Attached to the work |
  |---|---|---|
  | Session worker | session mail to the coordinator worktree | a comment on a **numbered, existing** pull request or issue |
  | Subagent worker | the returned final message | a comment on a **numbered, existing** pull request or issue, or a file on the branch |

- **FR-011** **[C]** A brief MUST NOT name a destination that does not exist at the moment the
  brief is read. `the pull request you open` is not an address at turn zero.
- **FR-012** **[C]** `docs/WORKER-BRIEF.md` MUST be amended so its canonical block names
  destinations by role rather than by surface, and MUST show both rows of the FR-010 table.

  *This is the measured defect. The document says "Keep that last block identical in every brief. A
  reworded prohibition is a different rule." Against the shipped text, **0 of 8** briefs comply,
  verbatim and whitespace-normalised both. The three that carry the block all made the same
  substitution, and the substitution is right. The document is what is wrong, not the briefs.*

  *Sub-clause conformance: `do not guess` **3 of 8**; `do not wait` **4 of 8**; both destinations
  named **2 of 8**. Needles are the literal strings, case-insensitive.*

### Session workers only

- **FR-013** **[C]** A brief MUST name the **branch** and the **worktree**. *Corpus: both named in
  **5 of 8**. This corrects pull request 43, which reported 8 of 8 by testing only that a `## Scope`
  heading existed.*
- **FR-014** **[C]** A brief MUST name a coordinator address that a stopped worker can reach and
  that will still be read after the worker exits.
- **FR-015** **[J]** A brief SHOULD state what the worker's account root permits where the work
  depends on it. *Corpus: **2 of 8** record account capability. Pull request 43 reported 0 of 8 by
  searching for the flag name `allowedTools`, which appears **0** times; the concept appears twice
  in prose. A needle that names an implementation spelling cannot count a concept.*
- **FR-016** **[C]** A brief MUST NOT assume the worker shares the briefer's account, permissions,
  or budget.

### Subagent workers only

These four are currently specified only in [`roles/MANAGER.md`](../../roles/MANAGER.md) section 6.
This spec is where they become requirements.

- **FR-017** **[C]** A brief MUST name the paths the subagent owns, because subagents share the
  parent's worktree unless explicitly isolated. Naming an **item** is not naming a **path**.
- **FR-018** **[C]** A brief MUST require the subagent to write its work somewhere outside its own
  context before returning: a branch, a file, or a pull request.
- **FR-019** **[C]** A brief MUST tell the subagent that its returned final message is the
  parent's **only** reader, so anything not in it and not written down is lost.
- **FR-020** **[J]** A brief MUST be sized against the **parent's remaining** budget, not against a
  fresh one, because the subagent spends the parent's tokens.

### Reporting

- **FR-021** **[C]** A worker MUST report a refusal or an error **verbatim**, not paraphrased.
- **FR-022** **[J]** A reader MUST NOT overrule a verbatim refusal without re-running it.

  *FR-021 and FR-022 are split on purpose. Pull request 43 had a single requirement binding the
  worker to quote accurately, which mis-identified the party at fault: in the incident behind it the
  worker **did** quote correctly and readers overruled the correct quote. Binding only the worker
  would have left the actual failure unaddressed.*

- **FR-023** **[J]** A report MUST separate what the worker measured from what it concluded
  (Constitution Article II).

### Explicitly not required

Named so a later reader can see these were considered and declined, rather than forgotten.

- **NR-001** A brief need not answer every question the worker might have. One turn is the bar.
- **NR-002** A brief need not be generated by a tool. Every brief in the corpus was hand-written.
- **NR-003** A brief need not use a fixed section order beyond FR-001. *Corpus: 3 of 8 use bullets
  under Done and the rest use a numbered list; both are readable, and pull request 43 wrongly
  reported 0 of 8 as bulleted.*
- **NR-004** A worker need not report progress mid-flight. Stopping is free; a check-in is waiting
  by another name.

---

## Key Entities

- **Brief**: the complete instruction a worker receives at spawn. Text. Not versioned, and no tool
  stores one today.
- **Worker**: a session worker or a subagent worker. The kind determines which requirements apply.
- **Briefer**: the Manager that writes the brief. Named because FR-022 binds it, not
  the worker.
- **Destination**: a role, either *reaches the briefer* or *attached to the work*, resolved to a
  surface by worker kind.

---

## Success Criteria

- **SC-001**: A brief can be checked against every **[C]** requirement without running the worker.
- **SC-002**: A reader given a brief and its worker kind can tell within one minute which of the
  two rows of FR-010 applies.
- **SC-003**: Of briefs written after `docs/WORKER-BRIEF.md` is amended, the share carrying a
  correct-for-kind prohibition block is measured. The baseline it is measured against is **0 of 8**.
- **SC-004**: No brief written after this spec names a destination that does not yet exist.
  Baseline: **1 of 8**.
- **SC-005**: A subagent's work is findable by a reader who was not present in the parent turn.
  No baseline: the corpus contains no subagent briefs, because the seat did not exist yet.

---

## Assumptions

- The eight-brief corpus is representative enough to show that a practice exists. It is **not**
  large enough to support a rate, and no count in this document should be read as one.
- Session mail works between accounts. Measured 2026-08-31, five messages each way, all delivered;
  one box recorded 396 messages consumed. Not re-measured since.
- Subagent behaviour is taken from `roles/MANAGER.md` and the Agent tool contract, **not** from a
  measured corpus. The Manager seat is one day old at the time of writing.
- Nothing enforces any of this today. Every requirement here is a claim about what a brief should
  contain, and there is no gate that reads a brief.

---

## Open Questions

1. **Does a subagent brief need the prohibition at all?** Its parent is present and can be asked
   mid-turn in a way a session worker's briefer cannot. The argument for keeping it is that a
   subagent still cannot reach the parent until it returns.
2. **What is the coordinator address for a Manager?** A Manager's subagents return to the Manager,
   which may itself be a subagent of nothing. Undecided. The retired Console had a coordinator
   worktree, which is why this question reads as a gap rather than as a new requirement.
3. **Should FR-018 name a specific artifact?** A branch, a file and a pull request are not
   equivalent in durability, and the spec currently accepts any of the three.
4. **Is the two-destination rule right for a subagent that opens no pull request?** FR-010 permits
   a file on the branch, which is weaker than a comment somebody is notified about.
5. **Who checks the [C] requirements?** No gate reads briefs. A checker is a separate feature and
   is not specified here.
6. **Does a review worker need its own row?** All three review briefs in the corpus
   carry **no** prohibition at all, and a reviewer that guesses is arguably worse than a builder
   carry **no** prohibition at all, and a reviewer that guesses is arguably worse than a builder
   that does.
7. **Is 22,275 tokens per waiting minute still current?** It is a single measurement from one
   configuration, and FR-007 rests on it.

---

## Falsification

This spec is wrong if any of the following turns out to be true. Each is checkable.

1. A brief carrying the canonical block **verbatim** is found in the corpus. Would falsify the
   0-of-8 count and with it FR-012's premise.
2. A subagent is shown to reach an address other than its returned message before it returns.
   Would falsify the FR-010 subagent row.
3. Session workers are shown always to share the briefer's account. Would make FR-016 vacuous.
4. A worker that guessed rather than stopped is shown to have produced a **better** outcome than
   stopping would have, on a case where the guess was checkable. Would weaken FR-008.
5. `the pull request you open` is shown to be resolvable at turn zero. Would falsify FR-011.
6. The eight briefs are shown not to be the full set kept from that period. Would not change any
   count, but would change what the corpus can be said to represent.
7. A reader is shown to have correctly overruled a verbatim refusal without re-running it. Would
   weaken FR-022.
8. `docs/WORKER-BRIEF.md` is shown to have been amended between the corpus dates and now, such
   that the briefs were measured against the wrong version of the canonical block.

---

## Corrections carried forward from pull request 43

Recorded rather than silently fixed, because the wrong counts were published and a correction
travels by the channel that carried the error.

| Claim in pull request 43 | Corrected | Why it was wrong |
|---|---|---|
| Scope names branch and worktree, 8 of 8 | **5 of 8** | tested that a `## Scope` heading existed, not what was in it |
| No brief uses bullets under Done, 0 of 8 | **3 of 8**, six bullets | the section was not isolated before counting |
| No brief records its grants, 0 of 8 | **2 of 8** | searched the flag name `allowedTools`, which occurs 0 times; the concept occurs twice |
| Ask-address names a future pull request, 3 of 3 | **1 of 8** | two of the three name existing numbered pull requests |

All four re-measured independently on 2026-09-04 against the same eight files, with the needle
printed alongside each count above.
