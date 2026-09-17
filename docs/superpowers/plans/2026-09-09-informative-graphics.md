# Informative Graphics Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Track the checkboxes below.

**Goal:** Help readers understand shared state, safe actions, and session handoffs through accurate, readable graphics.

**Architecture:** Add static, editable vector graphics beside the explanations they support. Each graphic answers one reader question. Keep the prose, commands, and evidence tables as the full reference.

**Tech Stack:** Existing Jekyll site, HTML figures, SVG, and CSS. Use editable draw.io sources for new diagrams and a plotting tool for the token chart. No new browser library is needed.

**Spec:** The user's September 9, 2026 request and the graphic briefs in this plan. This is a proposed plan; creating or publishing the graphics is a separate task.

## Start with five graphics on four pages

The first batch covers Concepts, Quickstart, Run a KORUS build, and Pruning. These pages teach the system and guide actions with real consequences.

The full proposal contains 14 graphics across 13 pages. Two replace the dense Concepts diagram; one refreshes the existing build diagram. Eleven are new.

The home page and BMAD page already have useful graphics. Keep them and check their readability against the same rules.

The review used the rewritten files from the site rewrite worktree, published through pull request #94. The primary checkout still contains older prose.

At implementation time, start from current main and read the relevant source again. Do not overwrite the primary checkout's unrelated work.

## Use graphics where they answer a concrete question

| Approach | Benefit | Cost | Decision |
|---|---|---|---|
| Add selected explanatory graphics | Focuses effort on hard concepts and consequential choices | Some pages remain text-only | Recommended |
| Put a graphic on every page | Gives each page a visual element | Creates repetition and filler, especially on reference pages | Do not use a page quota |
| Build interactive simulations | Lets readers explore races and timing | Adds code, maintenance, and accessibility work | Consider later only if static diagrams fail |

A graphic earns its place when readers can use it to explain a relationship, follow an event, or choose a safe next step.

## The first batch establishes the visual pattern

| ID | Page and placement | Graphic brief | Reader check |
|---|---|---|---|
| G01 | `docs/CONCEPTS.md`, beside the three-layer explanation | Replace the disk portion of the current diagram with a shared/private map. Show one clone, separate worktrees and branches, and one Git common directory holding coordination state. | Can the reader name what stays separate and what remains shared? |
| G02 | `docs/CONCEPTS.md`, beside the liveness explanation | Replace the remaining part with a small decision diagram. Liveness may veto an action; an empty result does not prove safety. Show unreadable state as a separate outcome. | Can the reader explain why no visible occupant is not permission to delete? |
| G03 | `docs/QUICKSTART.md`, after the introduction | Show four stages: inspect, install, verify, test a collision. Connect each stage to its numbered instructions. End with the expected blocked edit, not merely a successful install. | Can the reader identify what proves the setup works? |
| G04 | `docs/KORUS-BUILD.md`, replace the figure under The shape | Redraw the existing handoff diagram with lanes for Console, Builder, and Lander. Add a separate failed-check branch to Regulator. Name each handoff: brief, pull request, queue entry, and findings that stay on the pull request. | Can the reader identify who builds, who may merge, and where findings go? |
| G05 | `docs/PRUNING.md`, beside The rule | Draw the automated pruner's decision tree. Require merged, clean, and not occupied, plus its other documented checks. Show refusal on unknown state and rechecking before removal. Keep manual `remove.ps1` in a separate warning box. | Can the reader distinguish the automated pruner from the manual remover that has no occupancy check? |

G02 must state its limits. Held coordination state and expiring mail messages have different rules; a general no-timers claim must not spread to mail.

G04 must show authority as a condition. A role name alone does not grant permission, and the retired review-label rule must not return.

G05 is a map of the existing procedure, not a new deletion recipe. Keep the warnings about untracked files, recovery references, and invisible occupants beside it.

## The second batch explains events and failure paths

| ID | Page and placement | Graphic brief | Reader check |
|---|---|---|---|
| G06 | `docs/HOOKS.md`, beside The event map | Show two tracks: client events and Git events. Place each shipped control at its trigger. Treat the doctor as a separate verification tool. Use an event sequence, not elapsed-time spacing. | Can the reader tell which control runs before an edit, commit, or push? |
| G07 | `docs/COORDINATION.md`, beside The pieces | Compare presence, overlap, claims, and locks through one worked example. Distinguish observation, declared intent, and exclusive access. Connect each item to the question it answers. | Can the reader choose the right tool without treating a claim as a lock? |
| G08 | `docs/PR-AND-MERGE.md`, beside the four merge states | Map each documented state to its proper fix. Keep conflict resolution, updating a branch, waiting for checks, and queue decisions distinct where the source requires. Copy the exact state names from the current section. | Can the reader choose a fix without treating every blocked merge as a conflict? |
| G09 | `docs/SESSION-MAIL.md`, beside Step 5 | Use a message timeline with sender, inbox, and recipient lanes. Distinguish displaying a message from consuming it. Show the actual SessionStart and Stop behavior, including the failure window. | Can the reader explain why displaying a message does not mean it can be deleted? |
| G10 | `docs/SEQUENCE-ALLOC.md`, beside The defect | Show two callers racing. Contrast read-then-write with exclusive creation: one caller succeeds, the other retries according to the source. Show reserved allocation separately from commit-time checking. | Can the reader explain what prevents duplicate numbers and why allocation does not wire the gate? |
| G11 | `docs/LIMITS.md`, beside collision-gate limits | Draw the scope of observation: worktrees in one clone, another clone, and writes outside the covered edit path. Label each boundary with what the tooling can observe. | Can the reader name a real collision the gate cannot prevent? |

G09 must label the urgent mid-turn tier as unbuilt. It must also preserve the distinction between measured cross-account delivery and untested editor-extension delivery.

G11 must not look like a security perimeter. These controls prevent accidents within documented limits.

## The third batch explains evidence and account boundaries

| ID | Page and placement | Graphic brief | Reader check |
|---|---|---|---|
| G12 | `docs/DESKTOP-ACCOUNTS.md`, beside the launcher explanation | Show two application instances, their config roots, accounts, and discovery files. Distinguish separate account state from repository state. Label what the launcher changes. | Can the reader explain why opening a second window is not the same as starting a separate account instance? |
| G13 | `docs/TOKEN-ACCOUNTING.md`, after the measurement table | Make one two-panel chart for accounts A-D. Plot raw tokens per meter point and non-cache-read tokens per meter point. Use separate labeled axes with zero baselines and exact values from the table. | Can the reader see which measure varies less without mistaking token use for progress? |
| G14 | `docs/CASE-STUDY-refuted-but-true.md`, beside What happened | Show the evidence sequence and the claim each step supported. Distinguish refuted, untested, and confirmed. Keep the story's actual order and evidence sources. | Can the reader explain why failed verification did not refute the claim? |

G13 must display the measurement date, 2026-08-12, and the four-account sample size. Keep account D's missing coverage explicit.

The chart must not imply a current price promise or a measured productivity gain. Keep the source table beside it for exact comparison.

## Use the remaining pages as references

| Pages | Treatment |
|---|---|
| Home and BMAD | Keep their existing diagrams; improve small labels only if rendering shows a problem. |
| KORUS, FAQ, Install, Worktrees, and Troubleshooting | Link to the relevant new figures or their owning sections. Add another figure only for a distinct unanswered question. |
| Seats and worktrees, Playbooks, Role cards, and the seven individual cards | Refer to the build and shared/private maps. Keep injected role cards compact and text-based. |
| Worker brief, Steering, Running multiple sessions, and CI red watch | Refer to the handoff or event diagrams. Do not imply every communication channel has the same delivery timing. |
| CI for leaders, Usage awareness, and Leak gate | Keep their evidence and limits prominent. Reuse the observation-boundary idea only when its scope fits. |
| Other case studies, Spec Kit, and Tips and tricks | Retain their comparison tables. Reconsider diagrams after the first batches show what readers find useful. |
| Scripts, House style, Playbook size, Feed this to Claude Code, and 404 | Keep text and tables unless a reader task reveals a specific visual need. |
| Flowchart standard | Use its contrast audit and design guidance. Do not rewrite the supplied specification. |
| Earlier `-HUMAN` alternatives, revision index, and `.old` pages | Preserve them as comparisons. Do not add a second maintained copy of every new graphic. |

## Keep the visuals readable and consistent

- Give each graphic a short title that states what it shows.
- Use one reading direction within a graphic. Label arrows with the action or information they carry.
- Keep each main diagram to roughly five to eight nodes. Split it when exceptions overwhelm the main path.
- Use plain labels, with exact command and event names where precision matters.
- Pair color with text, shape, or line style. Color alone must never convey success, refusal, or uncertainty.
- Follow `docs/FLOWCHART-STANDARD.md`, including its contrast audit. Do not copy token pairings that the audit marks as failing.
- Target at least 4.5:1 contrast for ordinary text and 3:1 for meaningful lines against their backgrounds.
- Render labels at a readable size on a phone. Reflow into a vertical variant instead of shrinking a wide diagram to fit.
- Include a short caption, an accessible name, and a nearby text explanation. Explain complex relationships in prose rather than one enormous alt label.
- Keep graphics usable without JavaScript. Add motion only if a later reader test establishes a need.
- Keep existing commands, anchors, evidence tables, and exceptions intact.
- Preserve all `.old.md` and `.old.docx` files byte for byte.

## Keep editable sources beside exported assets

Use these proposed paths when implementation starts:

| Path | Responsibility |
|---|---|
| `docs/assets/diagrams/<id>-<name>.drawio` | Editable source for each new diagram |
| `docs/assets/diagrams/<id>-<name>.svg` | Export for web pages |
| `docs/assets/charts/g13-token-meter.svg` | Chart generated from the published measurement table |
| `scripts/site/plot_token_meter.py` | Rebuild the chart from those source values |
| `docs/assets/style.css` | Shared figure sizing, caption style, and theme rules, only where needed |
| The page named in each brief | Figure placement, caption, and accessible explanation |

For inline SVG, give every marker and description a unique ID. Use HTML figures that match the site's current structure.

Keep page-specific labels in the asset source, not in shared CSS. The chart builder should consume the existing table rather than introduce a second handwritten data set.

## Deliver the work in three reviewable batches

### Task 1: Build and check the five pilot graphics

- [ ] Read the current main versions of the four pilot pages and the scripts behind their safety claims.
- [ ] Write each graphic's caption and answer its reader-check question before drawing it.
- [ ] Create editable sources and SVG exports for G01-G05.
- [ ] Place each figure next to the section named in its brief.
- [ ] Render the four pages at desktop and phone widths in light and dark themes.
- [ ] Review every arrow, branch, and refusal condition against the owning source.
- [ ] Ask a reader to answer the five check questions using the pages.
- [ ] Revise any figure that causes an incorrect answer or adds no useful understanding.

The reader exercise is a proposed evaluation, not a measured result. If no reader is available, record that limitation and perform the source review.

### Task 2: Apply the accepted pattern to G06-G11

- [ ] Read each owning section and list its conditions before drawing.
- [ ] Create the six graphics from their briefs.
- [ ] Add captions and accessible explanations.
- [ ] Check the documented exceptions, especially unknown occupancy and unbuilt mail behavior.
- [ ] Render the pages in both themes and at both widths.
- [ ] Review each graphic against its reader-check question.

### Task 3: Add G12-G14 and finish integration

- [ ] Draw the account-boundary and evidence-sequence graphics.
- [ ] Build the chart from the four existing account rows.
- [ ] Compare every plotted value with the source table.
- [ ] Check the existing home and BMAD diagrams against the readability rules.
- [ ] Add useful section links from the reference pages listed above.
- [ ] Complete the validation below before publishing any batch.

## Completion requires correct content and readable rendering

1. Build the site with `bundle exec jekyll build --source docs --destination _site`.
2. Run `python scripts/site/publish_sources.py _site`.
3. Run `python scripts/site/publish_revisions.py _site` to verify the saved archives and page pairs.
4. Run the existing link, prose, and landing-page checks after changing page markup.
5. Check graphics at 390px and 1365px viewport widths, in both themes.
6. Check 200 percent browser zoom for clipped text and lost labels.
7. Check accessible names, captions, and reading order with a screen reader.
8. Compare every depicted state, boundary, number, and exception with the source.
9. Run the repository's required checks before merge.
10. Verify the published pages and asset URLs after deployment.

A batch is complete when its graphics answer the stated questions, preserve the source's limits, and remain readable on a phone.
