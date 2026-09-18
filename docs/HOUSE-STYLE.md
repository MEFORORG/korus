# House style: what a page here has to do

<a id="tldrbluf"></a>

Write sentences that carry a fact, number, constraint, link, or instruction. Give each rule a
permanent identifier so a reviewer can cite it. No rule requires an opening summary.

These rules do not apply to generated files or to edits that would weaken `PD`, the protected-content rules.
`SECURE-DEVELOPMENT.md` moved to [the standards repository](https://github.com/wshallwshall/secure-development-standards)
and follows that repository's style.

Before editing, check `PD` for facts and limits that must survive. PD-8 remains a retired rule:
its four named sections moved with the standards.

---

## How to read these rules

| Element | What it means |
|---|---|
| `OPEN-<n>` | The opening of a page |
| `HS-<n>` | House style, anywhere on a page |
| `PD-<n>` | Protected density. What an editor MUST NOT cut |
| `B-<n>` | A banned construction |
| **MUST**, **MUST NOT** | Absolute. Not meeting one is a defect, not a judgment call |
| **SHOULD** | Ignore it only for a stated reason you have weighed |

Keep a rule's identifier when you change its wording. Allocate a new identifier when you change
what the rule requires.

`PD` takes priority over the other rules. If a length limit conflicts with preserving a
measurement, keep the measurement and rewrite the surrounding prose.

### The numbering is shared with another repository, and this page is not the whole of it

Use the number above the highest one issued in either rule sheet.
[secure-development-standards](https://github.com/wshallwshall/secure-development-standards)
continued numbering after the split, so gaps in this sheet may already be taken.

| Series | Issued here | Issued there | **Next free** |
|---|---|---|---|
| `B-<n>` | B-1 to B-10 | B-11 to B-18 | **B-19** |
| `HS-<n>` | HS-1 to HS-16, HS-20 to HS-23 | HS-17 spent on a superseded branch, HS-18 to HS-21 | **HS-24** |
| `PD-<n>` | PD-1 to PD-8 | PD-9 to PD-13 | **PD-14** |
| `OPEN-<n>` | OPEN-1 to OPEN-8 | none | **OPEN-9** |

Check that repository's `origin/main` before allocating a number. Concurrent edits can make a
local copy stale while you are writing.

The table was checked on 2026-08-16 at `d393aad`. The earlier version listed only `PD-9` and
`B-17`; the other repository had already issued `PD-9` through `PD-13` and `B-18`.

Its one `OPEN` reference gave this page's range as `OPEN-1 to OPEN-6`.

Neither sheet detects changes to the other. The other page's `OPEN-1 to OPEN-6` range became
stale when `OPEN-7` was added.

That gap prompted `HS-13` and the cross-repository anchor ban. The table records its check date
and commit so readers can judge its age.

---

## OPEN: the opening

The opening of `standards/SECURE-DEVELOPMENT.md` fell from 99 lines to 22 after two sections
that repeated its contents were removed. That edit supplied the model for these rules.

| ID | Rule | Evidence |
|---|---|---|
| OPEN-3 | An opening **MUST NOT** describe the page's own structure, sections, or reading order | No "this page is organized as", no "first we cover" |
| OPEN-5 | An opening **SHOULD** link rather than summarise, where the target says it already | A link, not a paraphrase |
| OPEN-6 | A page longer than roughly 2,000 words **SHOULD** name its own starting point | One link, near the top |
| OPEN-8 | A page published in its author's own words is exempt from the prose ratchets and from the extensionless half of the source-link scan, and **MUST** be named in `AUTHORED_VERBATIM` in `tests/_ccxtest.py`. It stays bound by every rule that does not require rewriting the author: ASCII, `HS-16`, and every link resolving | One tuple, one entry. `tests/test_docs_do_not_drift.py` fails when it names a file this page does not |

### OPEN-8 names one file, and that is the whole of the exemption

`docs/KORUS.old.md` preserves the author's unedited account. The owner approved rewriting the
current `docs/KORUS.md` on 2026-09-09, so the exemption now follows the archived copy.

Before OPEN-8, four checks failed on that account: `OPEN-2`, `OPEN-7`, the source-link scan, and
`HS-20`. The paragraph count was 94 against a baseline of 88; the first two rules were later retired.

`AUTHORED_VERBATIM` in `tests/_ccxtest.py` lists exact paths. Three tests in two files read it.
Adding another exempt page requires an approved change to that list.

Excluding that one page kept the baseline at 88. Raising `BASELINE_FAT_PARAGRAPHS` to 94 would
have given every other page six extra long paragraphs.

An exempt page may use `/WORKTREES` without `.html` only if `WORKTREES.md` exists on the site.
Clean-URL fallback was checked on 2026-08-12 against `/WORKTREES` and `/USAGE-AWARENESS`.

OPEN-8 does not exempt ASCII, `HS-16`, link resolution, or the site build.

### OPEN-1, OPEN-2, OPEN-4 and OPEN-7: retired 2026-08-27, and no rule replaces them

The owner retired these four rules on 2026-08-27. `PD-6` keeps their identifiers, which must
not be reused.

The rules required an opening summary on every rendered page. `OPEN-2` required the exact
heading `<a id="tldrbluf"></a>`, and `tests/test_docs_do_not_drift.py` checked for it.

`OPEN-1` and `OPEN-7` required separate paragraphs answering what this is, why readers should
care, and how to use it, in that order.

`OPEN-4` required the `Why you should care` paragraph to say who the page was not for.

The presence check was deleted. `tests/test_docs_do_not_drift.py` still rejects `## In short`
and `**TL;DR --**`, the two replaced spellings.

A page that includes a summary must use the accepted spelling. A page may omit the summary.

Retiring the rules did not delete existing summaries. The 2026-09-09 rewrite removes their
formulaic labels from current pages; the archives preserve the earlier text.

Archives are listed by exact path and SHA-256 hash in `docs/_data/page-revisions.json`. They stay
outside current-prose ratchets because their purpose is to preserve earlier wording.

`tests/test_page_revisions.py` checks those hashes, including planted changed and missing files.
An unlisted `.old.md` file gains no exemption.

### What the four demanded before they were retired, so an old citation resolves

`OPEN-1` originally asked four questions: what this is, what it costs, who it is not for, and
where to start. On 2026-08-10, cost moved into `Why you should care`, leaving three answers.

Until 2026-08-10, `OPEN-2` ended with "A page **MAY** have no summary section at all". On that
date, 15 of 18 rendered pages lacked a summary.

`OPEN-7` required exact labels: `**What this is.**`, `**Why you should care.**`, and
`**How to use it.**`. A substring check treated changed wording or missing bold as absent.

On 2026-08-16, the rule allowed those answers in the author's words. The exact-label check
remained for one more day, so the documented rule and the check disagreed.

`OPEN-4` was reworded once without changing its requirement. The sentence about who the page
was not for still had to appear in the assigned paragraph.

---

## HS: house style

| ID | Rule | Evidence |
|---|---|---|
| HS-1 | Every sentence **MUST** carry a fact, a number, a constraint, a link, or an instruction | Delete the sentence and something is lost |
| HS-2 | A section **MUST NOT** restate a fact the page has already stated | One statement, one place |
| HS-3 | A fact stated in two files **MUST** live in one and be linked from the other | One owner per fact |
| HS-4 | Prose **MUST NOT** explain why the document omits something | Say it or do not; the omission needs no defence |
| HS-5 | A count of a set **MUST NOT** appear in prose unless the same page enumerates the set | Counts rot silently |
| HS-6 | A claim about behaviour **SHOULD** name how it was established | "Measured on", "verified against" |
| HS-7 | Tabular content **MUST** be a table; a table whose rows are one clause each **SHOULD** be prose | Shape follows content |
| HS-8 | A destructive command's description **MUST** state what is lost and whether it is recoverable | The loss, named |
| HS-9 | A diagnostic message **MUST NOT** be phrasable as reassurance when the tool could not determine an answer | "Could not tell" reads as "could not tell" |
| HS-10 | A refusal **MUST** say what was refused, why, and the next command, and the command **MUST** be runnable as printed | Three slots, all filled |
| HS-11 | Prose **MUST** be ASCII: no em dash, no smart quotes, no section sign | `scripts/quality/check-ascii.ps1` |
| HS-12 | A normative rule document **MUST** carry a "how to read the rules" section, stable rule identifiers, and an evidence column | The three, present |
| HS-13 | A heading **MUST NOT** be renamed until the repository has been searched for its text | Standards cite headings by name. `scripts/quality/frozen_citations.py` names the frozen archives citing one; `tests/test_a_heading_a_frozen_archive_cites_cannot_be_renamed.py` holds the set and reddens when one goes |
| HS-14 | Lines **SHOULD** wrap near 100 characters | The wrap |
| HS-15 | A quantity **MUST** be the number where one exists, not a vague determiner | "139", not "nearly all" |
| HS-20 | A paragraph **MUST NOT** exceed 300 characters. Rewrite it shorter; do **not** satisfy this by splitting one paragraph into two | A hard cap in `tests/test_prose_rules_hold.py` since 2026-08-16, when the last of the debt cleared. It shipped as a ratchet because 463 paragraphs were over the limit on 2026-08-10; the baseline is now 0, so the next one over fails the run |
| HS-16 | A markdown link **MUST** sit on one line, text and target both, and that outranks HS-14 | `tests/test_a_links_text_never_wraps.py`. `jekyll-relative-links` matches a link with a pattern whose `.` excludes a newline, so a wrapped one is never rewritten and the published site serves the raw `.md` while github.com renders it correctly. 35 links were in this state on 2026-08-07 |
| HS-22 | A heading or title **MUST** use sentence case: the first word, the first word after a colon, and proper nouns are capitalized, nothing else. **MUST NOT** end in a period | [Google's developer documentation style guide](https://developers.google.com/style/headings). No gate; checked by eye |
| HS-23 | A page a reader ARRIVES on **MUST** route rather than explain. It **MUST NOT** carry the install procedure, the requirements table or a script inventory, and it **MUST** name the first command's page in its opening | `tests/test_the_landing_page_stays_a_front_door.py`. The landing page reached 3,143 words before this rule, with the first install command 68% of the way down it |

### HS-21: retired 2026-08-16, and the identifier is kept rather than reissued

HS-21 required each `docs/FRAMEWORK-*.md` page to answer nine questions in a fixed order.
`tests/test_a_series_answers_one_set_of_questions.py` enforced that format for comparison.

The comparison needed at least two pages. The BMAD page adopted a shorter format covering
what it is, its relation to Ultracode, its uses, and setup, leaving one page in the series.

The test instructed maintainers: "if the series is genuinely gone, delete this file rather
than leaving it to certify an empty set." It was deleted.

`FRAMEWORK-spec-kit.md` retained its nine sections. No other page has to match that order.

### HS-23: what the landing page stopped carrying, and why a rule was needed

The home page accumulated the install procedure, requirements, vendor limits, and a 40-row
script inventory. Each addition was accurate, but together they made the starting point hard to find.

A new reader had to pass the caveats before reaching commands 68% of the way down a
3,143-word page.

The split gave the procedure to [Quickstart](QUICKSTART.md), requirements and limits to
[Limits and requirements](LIMITS.md), and the inventory to [Every script](SCRIPTS.md).
The home page kept the links that help readers choose.

Move a fact to its owning page when the home page gets too long. Do not delete it to meet the
cap; `PD` still takes priority.

---

## PD: protected density, and what an editor MUST NOT cut

Keep the measurements and the limits that make advice accurate. A shorter sentence is not an
improvement if it loses either one.

| ID | Rule |
|---|---|
| PD-1 | **MUST NOT** remove a measured number, a date, or a named source. A diff removing a digit outside a code fence needs a reason in the commit message |
| PD-2 | **MUST NOT** remove a "Limit:" statement, or any sentence saying where a control stops working |
| PD-3 | **MUST NOT** remove the mechanism sentence that makes a rule actionable, even where the rule survives without it |
| PD-4 | **MUST NOT** convert a trap, limit, or status table into prose to satisfy a length rule |
| PD-5 | **MUST NOT** remove a statement that a control is advisory, unwired, or unproven |
| PD-6 | **MUST NOT** remove a rule identifier, or renumber rules. Retire an identifier with a tombstone instead |
| PD-7 | **MUST NOT** rewrite an agentless passive into an active sentence in a normative rule. The requirement holds whoever performs it |

### PD-8: retired, and the identifier is kept rather than reissued

PD-8 protected four sections from `OPEN-3` and `B-6` edits. All four moved to
[secure-development-standards](https://github.com/wshallwshall/secure-development-standards).
PD-8 now covers no section here, and PD-6 prevents reusing its number.

The other repository uses its own gates. Two of the four sections have tests for other
reasons: `test_rule_ids_are_stable.py` parses `## Retired rules`, and the selector test pins both sides of its sentinel.

No check there protects the status-check date line or the ASVS Part 1 to Part 2 boundary
marker. A rule covering them is proposed, not established.

---

## B: banned constructions

These bans came from prose found in this repository.

| ID | Banned | Write instead |
|---|---|---|
| B-1 | A page instructing the reader how to read it | The content, in the order that serves it |
| B-2 | A sentence explaining why a fact is omitted | Nothing |
| B-3 | "It is worth noting", "It should be noted", "Importantly" | The note |
| B-4 | A sentence whose only work is transition | Nothing |
| B-5 | "provides the capability to", "in order to", "utilize", "leverage" | "can", "to", "use", "use" |
| B-6 | A sentence asserting its own significance | The fact that makes it significant |
| B-7 | "cleanly", "elegantly", "robustly", "carefully" describing this project's own work | The property, measured |
| B-8 | Three adjectives or three parallel clauses where one carries the meaning | The one |
| B-9 | "nearly every", "most", "a number of" for a countable set | The count |
| B-10 | A rhetorical question as a section opener | The answer |

---

## The standing edit protocol

1. Find the passage by its heading or exact wording. Line numbers from an earlier plan or review may have moved.
2. Search the repository before renaming a heading. Run `python scripts/quality/frozen_citations.py <page> "<heading>"` first: a frozen archive may cite it, and that link cannot be repaired. Preserve inbound anchors and run `tests/test_internal_links_resolve.py`.
3. Run tests from `tests/` with `python -m unittest discover -s . -q`. Running discovery from the root can find no tests.
4. Run `scripts/coord/overlap.ps1` before editing. A clean text merge does not establish that two changes serve different purposes.