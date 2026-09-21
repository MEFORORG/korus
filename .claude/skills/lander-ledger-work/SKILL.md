---
name: "lander-ledger-work"
description: "File, close or reconcile a ledger item in docs/BACKLOG.md. Use when writing a banner, closing an item, or running the reconcile pass."
user-invocable: true
disable-model-invocation: false
---

# lander-ledger-work

> Task rules for the Lander seat, split out of [LANDER.md](../../../roles/LANDER.md) on 2026-09-05.
> The prohibitions that bind before this task starts stay in that file. Read it first.

### 4i-bis. An ADR that rests on a REFUSAL is falsified when the code does the refused thing

| Item | Rule |
| --- | --- |
| The reading rule | An ADR that never considered an option merely predates it. |
| The falsified kind | An ADR that CONSIDERED an option and rests its decision on REFUSING it is falsified the moment the code does the refused thing. |
| What nothing reports | Its Status line still reads Accepted. |
| DEFERRED is not REJECTED | A DEFERRED option is the ADR's named follow-on. Landing it is the expected next step and the ADR needs a status update, not an amendment. |
| The REJECTED kind | One whose refusal the decision stands on. Landing it deletes a premise, and the amendment or supersession is the work. |
| Why the line matters | A rule that skips it fires on every deferred-then-delivered item in the repo. |
| The worked case | Verified on `origin/main`, 2026-08-22, on the file under `docs/adr/` whose name begins `0143-web-console-on-by-default`. It carries both kinds in one file. |
| What made it easy to misread | Status reads `Status: Accepted (2026-07-21)`, and the Decision engages the http-safe hardening subset over the loopback secure context *"without auto-TLS"*. |
| Why that clause is not a refusal | A section headed *"Deferred (considered, not built): auto-TLS on loopback"* names auto-TLS as the follow-on, and the options list marks it Deferred while marking two others Rejected. |
| What went wrong | A seat reading only the Decision clause called the deferral a refusal. |
| The merge-time condition, REJECTED kind only | The amendment or supersession is in the SAME diff. Run `gh pr diff --name-only` and require the ADR file before arming. |
| For a deferred option | Land it and update the status. |
| Read the body, not the Status line or title | The title says what the ADR chose. Both the refusal and the deferral live in the body. |
| **EXPIRY** | None while an ADR can record a refusal its decision stands on. Per ADR, the expiry is that ADR's supersession, checked by re-reading its options list. |

### 7a. Ownership is keyed to the worktree that ran `alloc.ps1`, and is NON-TRANSFERABLE

When a session is blocked the instinct is to delegate. For anything keyed to ownership, **delegation
is exactly what fails.** Three manifestations in one night:

1. A conflict resolved correctly by the lander was **refused at commit time**, because entitlement
   keys to the worktree that ran `alloc.ps1`.
2. **Gate rule 3b pushes you into a NEW worktree** to reach a conflicted branch, and the ledger gate
   then refuses what you commit there. Two correct rules composing badly. *Right content, wrong
   worktree.*
3. **A cherry-pick by the lander is refused** even when the owner authored the commits. The
   cherry-pick makes the lander the committer, so added headings are checked against *their*
   ownership.

| Item | Rule |
| --- | --- |
| The escape both rules permit | `git checkout -b <new> origin/main` from the **allocating** worktree, since `-b` is exempt from rule 3b. Then re-apply the item. |
| Never plan the hand-off | A ledger-number commit routed through anyone else cannot work, and the failure arrives late, after the work is done. |
| Never force-push a stranded branch | It rewrites a branch whose entitlement belongs to another worktree. |
| A worktree running a workflow | It cannot `checkout -b` either. An implement agent mid-run is reading and writing files in that tree, and switching HEAD swaps them underneath it. Wait for the run to land. |

### 7b. Entitlement gates FILING a number, not CORRECTING a landed one

`ledger_check.py` iterates `sorted(head - base)`, so **only headings ADDED relative to base are
examined.** Once an item is on `origin/main`, editing it adds no heading, ownership is never
consulted, and any session can correct it.

Confirmed by the pre-commit gate passing on a non-allocating worktree, and separately for a banner
flip: the heading set is identical with an open banner and a closed one.

| Item | Rule |
| --- | --- |
| The boundary | A conflict that RE-INTRODUCES a heading not yet on `main` is an addition, and ownership does apply. |
| Why the boundary matters | The two cases are easy to confuse and the difference decides whether the work is delegable. |
| Do not confirm this by running the tool | `ledger_check.py --base X --head Y` ignores both arguments. |
| The proof | `main(argv)` is `return Ledger(ci="--ci" in argv).run()` (`scripts/hooks/ledger_check.py:382-383`). Only `--ci` is read from `argv`. |
| What everything else inspects | The **STAGED TREE**. So a deliberately bogus ref still exits 0, and that zero reads as confirmation. |
| Cite the structure instead | `added_files()` is `--diff-filter=A` (`:168-172`); a banner edit adds no FILE, so the ownership rule is never reached. |
| Corollary | *Hand it back to the allocating session* is correct for an **unlanded** number and needless friction for a **landed** one. |
| The generalisation that was available hours early | Two sessions each established this for the case where they found it and left it scoped there. |
| So | When you establish a gate's boundary, ask what else sits inside that boundary before moving on. |

### 7f. A claim outliving the work it guards

| Item | Rule |
| --- | --- |
| Why it stalls a lane | A held claim on a completed item looks exactly like someone actively building it, so it blocks the next session for days. |
| Since 2026-09-18 the release is YOURS, with the ledger update | Owner-set, and both in one act. A Builder no longer holds its claim open until the fix reaches `main`. |
| `claim.ps1 -Release` is worktree-scoped | Like `alloc.ps1`, it acts on the worktree the shell stands in, so releasing a Builder's needs `-Force`. |
| Expect the refusal, then read the probe | `HOLDER GONE` means the worktree is off disk, and the script recommends `-Force` itself. `HOLDER IS STILL THERE` is about a directory, not a live session. |
| What licenses the force in this flow | The Manager's handover for that branch, plus the merge. Both say the author has exited. Name the two you read. |
| What makes that worse | Background watches cap at ten minutes, so if the holding session goes quiet the claim just sits. |
| The release condition | The fix **TEXT** is on `main`, never that the PR closed. |
| How that earned itself | Twice in one day, when a PR merged while the correction its author believed was in it had never been pushed. |
| If the text is absent | Do **not** release. That is the exact case the condition exists to catch. |
| Checking one number | Grep for THAT NUMBER. A grep of `<N>\|held` matches the word *held* in every row and returns unrelated claims, which reads exactly like "N is still held". |

### 7g. The ledger reconcile pass -- one atomic operation

**The premise this section opened with was false, and correcting it is the point.** It said build
sessions flip banners. They do not and may not. `BUILDER.md`: *"You may not conclude an item CLOSED.
Banner flips and ledger reconciles are not the builder's."*

**So nothing upstream ever flips a banner**, and a reconcile that only archives already-closed items
archives nothing. Deciding an item is closed is YOURS, and it is a separate act from recomputing the
census.

| Item | Rule |
| --- | --- |
| The measured cost of skipping it | 2026-08-22, across the 24 ledger commits in one drain: 673 insertions, 5 deletions, **zero status-banner lines deleted**, 11 items filed, none closed. |
| What that did to the census | Open went 225 to 236. The prior drain's five reconcile commits deleted 13 banner lines and closed 13 items. |
| A banner flip needs a DELETION | Diff `docs/BACKLOG.md` with `-U0` and count REMOVED lines beginning with a status banner. Unit: diff LINES. |
| What zero means | You filed and closed nothing. A pure insertion cannot be a flip. |
| Scope the sweep to the class that can close | Census the `**Verdict:**` field before you spend a pass. |
| Measured at `fdd89b49` | Of 236 open items, **96 build, 21 demand, 94 research**. Of the 13 closed in the prior window, **12 build and 1 demand, zero research**. |
| And across all archived items | `Verdict: research` appears **zero** times. |
| A research item closes in TWO acts | The vault ASVS cell is re-scored first, and the banner flips second. The second act is yours. |
| Who performs the first | **UNASSIGNED. This cell names no seat.** Corrected 2026-09-21. |
| What it read before | *"No live seat."* until 2026-09-15, then **YOU** from 2026-09-15 to 2026-09-21. Both are superseded, and this cell re-adopts neither. |
| The owner's correction, 2026-09-21 | They did not intend the Lander to always handle re-scoring, and they named nobody in its place. So neither does this cell. |
| What the standing-authority grant does | Engine `CLAUDE.md` section 5's Lander row reads *"Standing authority on the engine repo and the vault, with no per-action owner approval."* Present since `f0e1365bc`, 2026-09-02. |
| And what it does not do | It is authority to act in the vault without asking first. It is not an assignment of the re-score. Reading it as one is how this cell reached **YOU** on 2026-09-15. |
| What commit `7c673513f` did, as a record | On 2026-09-05 it changed that engine row by exactly one line: *"Merging."* became *"Merging, and the vault scorecard re-score (owner ruling 2026-09-05)."* |
| And what it is no longer | Authority for this seat performing the re-score. Do not cite it as that. The engine's own row has since been corrected in engine PR 1402. |
| Why that record does not settle it | Its context line shows the standing-authority sentence already present, so the ruling added specificity to a grant it did not create. |
| What the owner corrected | The SCOPE they intended by that specificity. The 2026-09-05 ruling is neither wrong nor withdrawn, and do not write that it is. |
| So one act is yours, not both | The banner flip after the items merge is yours, affirmed by the owner on 2026-09-21. The re-score before it is unassigned. |
| Unassigned is not forbidden | The owner removed the re-score as a standing duty of this seat, not as something you may never do. One you are specifically asked to run, you may run. |
| Still read the scorecard commits yourself | Nothing sends a notice, and now there is no one to send it. |
| Why the 2026-09-15 correction was made | The *"No live seat."* text was **carried, not authored**: a refactor moved it without re-reading it, and a seat reading `7c673513f` concluded it was false. |
| Which half of that survives | The carried-without-re-reading half. The *"already false when carried"* half rested on the scope the 2026-09-21 correction removed, so this cell no longer asserts it. |
| The grant and the retirement are one commit | `f0e1365bc`, 2026-09-02T02:56:49Z, both retired the ASVS Tracker and granted the Lander standing authority. |
| When the carried text arrived | Three days later, at `0e44aba01` (2026-09-05T23:07:52Z), the refactor that split the playbooks into skills. |
| The failure shape to carry forward | A pointer and the thing it points at are two edits, and **nothing fails when only the first is made**. |
| What that cost here | For ten days this skill and the engine's seat row disagreed about who performs the re-score, and nothing failed. |
| And how it was settled | Twice: on 2026-09-15 by a seat reading the commits, and on 2026-09-21 by the owner. No check surfaced it either time. |
| You cannot learn a re-score happened | The scorecard is a vault file gitignored from every engine checkout. Nothing reports it. |
| So | Both halves can be done correctly while the item still reads open, and nothing surfaces it. |
| The discriminator for a stranded item | Compare the cell's `last_verified` against the banner's last touch. |
| What it tells you | Re-scored **after** the banner was last touched means step one is done and step two is missing. That item is closeable right now. |
| Read the DIRECTION before the cell id | Re-scores flow both ways, and the backward one is the dangerous half. |
| Measured 2026-08-22 | Of five scorecard commits, two were re-scores and **one went pass to PARTIAL**. |
| Why it reverted | The first measurement had been scoped to two files when the corpus was wider. |
| So | **If an item was closed on the superseded pass, it must RE-OPEN.** Every other part of this handoff assumes verdicts move toward closing. |
| Only re-scores move a banner | Of those same five commits, three changed no verdict: repaired anchors and corrected citations. |
| Why that matters | Treating every scorecard commit as closable flips banners on bookkeeping. |
| The cell-id to item-number mapping does not exist | Cell ids and item numbers live in different records, and **none** of those five commits carries an item ref. |
| Where the refs in that range come from | Merge commits pulling other seats' work. |
| So | Derive the items yourself, or say you could not. **Never accept supplied item numbers as the link**, because a supplier is guessing at the very link this handoff exists to make reliable. |

**The same two-seats gap one act earlier: build, then banner.** Measured 2026-08-22, a builder finished
all four scopes of an item and knew the work could not close the security requirement the item was
filed against. That requirement's named example is a control nothing in the work performs.

**The ceiling on what the change may CLAIM lived only in the builder's context, and the banner is
written later, by this seat.** Nothing carries the sentence across.

So require a completion note to carry an explicit **CEILING** field, and refuse a PASS banner on any
item whose completion note names one. Same remedy as the re-score handoff, applied one act earlier,
and needed for the same reason: both seats do their job correctly and the record still comes out
wrong.

| Item | Rule |
| --- | --- |
| Shipped code plus an open item is COMPLETE | It is a legitimate outcome and it is **not** a closure. Never report a wave's item count as if it were. |
| Cannot close is not cannot be worked | Never refuse an item because no seat can close it. |
| The evidence | At least four PRs from the research range are ancestors of `origin/main`, including a log redactor that emitted the very token it claimed to redact. |
| So | A rule refusing those items would have blocked that fix. Name the closing act and the seat that performs it; never refuse the item on it. |
| The dispatcher's own words | *"I picked unclosable work believing it would close, then proposed refusing workable items because they cannot close."* Both are the same fusion. |
| What is being fused | *Can a builder do it* with *can anyone here close it*. |
| The stale `Verdict` line | Ruling 2026-08-21: the `Verdict` line on `#1107`-`#1199` is *"filing-time text the landed research superseded; it is stale, not governing"*. |
| What briefing it cost | Two builders real time. Read the item's current body. The field scopes YOUR sweep; it gates nobody's dispatch. |
| Do it in ONE commit | Archive closed items out with their rows, file new items with rows, renumber ranks, re-derive all census lines. Two passes each publish a wrong count in between. |

**Three traps a green gate cannot see, because it reads banners, not ranks and not row prose:**

1. **Scope the renumber to the LIVE table.** A first attempt renumbered 235 ranks when the live table
   held about 103. The file also holds a superseded historical table and an unscoped loop walked into
   it. Bound the loop and assert the historical rows come out byte-identical.
2. **Match census lines precisely.** A loose `"sum to"` match rewrote **an item's own row text**, the
   item whose subject is counts not reconciling, silently making its count not reconcile. Caught only
   by a `changed == N` assertion firing before the write.
3. **The prose census line drifts every time.** It is not emitted by the recompute script, so it is
   stale after every filing. It was corrected once and came back seven out. Fixing the output without
   fixing the generator guarantees a third occurrence, so say so in the commit.

| Item | Rule |
| --- | --- |
| Verify in BOTH directions, never on a total | `open heading with no row` and `row whose item is not open` must both be empty. |
| Why a total cannot do it | A closed-but-rowed item and a filed-without-a-row item **cancel**, so a matching total passes while both sets are wrong. |
| Two independent claims | A correct filing neither fixes a prior error nor hides it, so *"my filing was correct"* and *"the census is now correct"* are separate. |
| Keep the assertions even when it looks mechanical | An assertion added for this caught its author corrupting their own work twice in two ledger passes. |

### 14d. Citations and anchors go stale without failing

| Rule | Detail |
| --- | --- |
| Resolving is not current | Anchors had moved 12 lines and passed only because 12 sits inside a plus-or-minus-40 window. Re-derive anchors against `main` at filing time. |
| Not resolving YET must say so | Label forward-looking citations as forward-looking. |
| Pin a surface, never a value | A doc-drift gate anchored on the phrase *"retry forever"* named a **posture** while every sibling anchor in the same tuple named a **surface**: a function, a route, an algorithm. |
| What happened when the value changed | When the default stopped being retry-forever the anchor survived only incidentally, matching a sentence about a still-expressible non-default option. |
| What that would have cost | Trimming that now-niche sentence would have redded the gate for no good reason. |
| The fix is stricter, not looser | Replacing it with the type name is measured to occur exactly once in the section, where a prose phrase can match anywhere in it. |
| **The general shape** | A category error in an anchor set is invisible while the value happens to hold. |

### 14q. A correct process applied to the wrong question produces a confident wrong answer

Every other trap here is an instrument returning a wrong value. **Here no value was wrong anywhere.**

A session filed a new backlog item and the whole chain was correct: `alloc.ps1` ran correctly, the
ledger gate correctly refused a cross-worktree allocation, the re-allocation was correct, the
deliberate number hole was correct, and the commit message explaining that holes are free was correct.
**The item already existed, filed six days earlier, in that session's own block.**

The toolchain answered *"is this number safe to use."* The question was *"does this item already
exist."* No gate asks the second, and nothing was going to.

**The procedural care is what disguised it.** A session that hits a gate, diagnoses it correctly and
re-allocates cleanly *feels* thoroughly checked. The rigour was real; it was aimed one question to the
left. It was found by reading the list, not by any check.

Same family as the `#1008` ruling: **do not read the existence of working code as authorization.**
When a chain of steps all pass, ask once what question the chain actually answers, and whether it is
yours.

## 16i / 16k. NOT LANDED and NOT CLAIMED are different populations, and a CORRECTION inherits authority

**Measured instance.** A lander told a session the contract integer `ENGINE_UI_SEAM` was free to take:
*"Nothing has taken 19 yet -- main is 18 and neither held branch has landed."* The session measured
instead:

    origin/main                     18        w3-log-write-failure           19   NOT landed
    (the branch's own value)        20        w3-store-privilege-preflight   19   NOT landed

Both branches had already CLAIMED 19. Taking it would have made a third claimant on one integer, the
exact collision the open item about that gate describes.

The session took **20**, which collides with nothing, and named both colliding branches in the
constant's comment so nobody later "fixes" the gap. A third branch nobody was watching then also
claimed **20** and lands first, which would have put both held branches BELOW main.

| Item | Rule |
| --- | --- |
| The instrument error | `main`'s value plus whether those PRs merged answers LANDED. Claims live in UNLANDED branches, exactly where that instrument cannot look. |
| The authoritative population | For any scarce shared value -- ledger numbers, contract integers, ports, ADR ids -- it is **every live branch, not `main`**. |
| What `main` shows | The one thing that cannot collide with you. |
| Density is not a requirement | A contract integer needs uniqueness and monotonicity. Skipping one costs nothing. |
| A fact you WROTE DOWN is not one you will use | The lander's own episode note already recorded the collision, then a fresh measurement of the wrong population overrode it. |
| Why the measurement won | A live measurement *feels* more rigorous than consulting your own notes, even when it is rigorous about the wrong question. |
| So | Before measuring something you have handled before, check whether you already recorded the answer. If note and measurement disagree, THAT is the finding. |
| A correction removes the reason to re-check | It arrives pre-framed as the more-examined claim, so it lands with more weight and LESS scrutiny than what it replaced. |
| The measured chain | A peer's handoff brief carried a correct framing. A lander overrode it, and the peer **rewrote their brief around it, discarding their own correct version.** |
| The peer's words | *"It agreed with what you had told me, and you had corrected me, so it carried more authority than my own original."* |
| Compose that with the detectability asymmetry | A claim that AGREES with expectation is only ever fixed by someone who re-measures without cause, and a correction actively removes the cause. |
| So | **When you override a peer's measured framing, you own re-checking it, because you have just removed their reason to.** Volunteering the reversal later is not courtesy; by then it is the only mechanism left. |
| The fix that held: a PROCEDURE, self-excluding | *"Read the value on current `origin/main`, read it on every unlanded branch touching that file, take a value above all of them -- never hand-pick a number from a document, INCLUDING THIS ONE."* |
| Why a stored value cannot work | A value in a DOCUMENT is falsified by a change to a FILE the document does not reference. No merge, therefore no conflict and no marker. Prose and code cannot conflict. |
| The other half of that argument | **A derived value cannot be mis-transcribed into a handoff, because there is no number to transcribe.** |
