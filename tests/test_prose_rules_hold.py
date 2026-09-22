"""The prose checker. Hard-fail where a violation is unambiguous, baselined ratchet everywhere else.

WHAT THIS EXISTS FOR. `docs/HOUSE-STYLE.md` states the writing rules and nothing enforced any of
them, so the only thing standing between the corpus and a slow drift back was whether a reviewer
happened to remember a rule identifier. This file enforces the subset that CAN be enforced and says
plainly which subset that is.

THE DESIGN RULE, taken from the writing plan and not negotiable here: hard-fail ONLY where a
violation is unambiguous and the current corpus is clean. A gate that reddens a legitimate editorial
choice is one people delete, and the repository already recorded that judgment once in
`test_docs_do_not_drift.TheBlufConventionHasOneSpelling`.

WHAT WAS MEASURED BEFORE CHOOSING, because the choice is the whole design. Every candidate pattern
was run over the corpus on 2026-08-08 and every hit was read:

  B-7  "cleanly", "elegantly", "robustly"      16 hits, ~0 genuine  -> NOT ENFORCED
  B-5  "in order to", "utilize", "leverage"    10 hits,  1 genuine  -> ENFORCED, narrowed
  B-3  "Importantly", "It is worth noting"      5 hits,  0 genuine  -> ENFORCED, narrowed
  B-10 a heading that is a question             1 hit,   0 genuine  -> NOT ENFORCED

B-7 IS THE INSTRUCTIVE ONE AND IT IS DELIBERATELY ABSENT. The rule bans those adverbs "describing
this project's own work". Measured, every single hit was standard technical vocabulary instead:
`git merges both cleanly`, `a session that exits cleanly`, `an execution-alias stub that resolves
cleanly`, `a transform producing valid-but-wrong output passes cleanly`. The distinction the rule
draws is about WHAT IS BEING DESCRIBED, and no pattern over the text can see that. Enforcing it would
redden sixteen correct sentences to catch nothing, so it stays a review item. The same reasoning
retires B-10: its one hit, `## The one question: does failing it stop the change?`, is a question the
section immediately answers, which is not the rhetorical opener the rule is about.

B-5 IS NARROWED TO THE UNAMBIGUOUS FORMS. Bare "leverage" is a noun as often as a verb here --
`ordered by its own leverage`, `the highest-leverage gate` -- so only the participles and the
unmistakable phrases are enforced. The one genuine violation the scan found, a cloud program that had
`begun leveraging an external framework`, was fixed in the same commit that added this file, because
a hard-fail rule whose corpus is already red is a rule that ships disabled.

THE RULE SHEET MUST BE ABLE TO QUOTE WHAT IT BANS. `docs/HOUSE-STYLE.md` lists every banned
construction verbatim in its own tables, so a naive scan reddens the one file that defines the rules.
The exemption is deliberately NARROW: a table row whose first cell is a rule identifier, and nothing
else. Exempting the whole file would leave the rule sheet the only unchecked prose in the repository.

WHAT IS REPORTED RATHER THAN FAILED, and why each is not a hard fail:

  cross-file duplication   HS-3, but which of two copies should go is an editorial call
  table cell word counts   fourteen files exceed 40 words per cell, SECURE-DEVELOPMENT among them
  long sentences           a cap at 30 fires on 1,397 of 6,579; the long tail carries the warnings

Each is a RATCHET against a baseline measured from the corpus. It may not get worse. If it gets
better the test says so and asks for the baseline to be lowered, because a ratchet nobody tightens is
a number that stops meaning anything.

`roles/` WAS THE CORPUS NOTHING READ, AND IT IS THE LARGER HALF. Until 2026-09-04 this checker read
`docs/`, `README` and `INSTALL` and stopped there. Measured at `1b6b7fc` over the paths
`git ls-files` returns: `docs/` with the two root pages is 36 files and 115,357 words of markdown;
`roles/` is 15 files and 180,043. So the unread half was 61% of the corpus, and it is the half every
epistemic mechanism here is actually written in. Those are WHOLE-FILE word counts, the quantity the
empty-corpus guard below reads; the ratchets read a smaller one, prose after tables, headings and
fenced blocks come out.

WHAT WIDENING COST, and it is the reason to do it now rather than later. The three hard-fail patterns
fire ZERO times across `roles/`, so B-3, B-5 and B-6 extended to it with no page edited and no
exemption added. The three ratchets did not: `roles/` measures 708 long sentences, 138 fat table
cells and 986 fat paragraphs against `docs/` figures of 49, 10 and 0.

THE RATCHETS ARE PER-CORPUS, NOT SHARED, and that is the whole of the design. See
`ROLES_BASELINE_FAT_PARAGRAPHS` for the argument; the short form is that one shared number would
hand `docs/` 986 paragraphs of headroom against a cap `docs/` has already reached.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import re
import subprocess
import unittest

import _ccxtest as t

# ---------------------------------------------------------------------------
# Corpus


def tracked_files() -> list[str]:
    """Every path git is tracking, as forward-slash repo-relative strings."""
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=t.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def _markdown_under(prefixes: tuple[str, ...]) -> list[str]:
    """Tracked markdown under `prefixes` that is prose. Word copies are generated and not edited.

    OPEN-8 pages are excluded for the same reason: they are not edited either. Every rule measured
    over this corpus -- sentence length, table cell width, paragraph length -- is satisfied only by
    rewriting the sentence, and a page published in its author's words has no such edit available.

    EXCLUDED RATHER THAN ABSORBED INTO THE BASELINES, and the difference matters. Raising
    BASELINE_FAT_PARAGRAPHS from 88 to 94 would also have gone green at the time, and would have
    handed every OTHER page six paragraphs of new headroom against a rule the corpus was then red
    behind. The ratchet stayed at 88, measuring exactly what it had measured before.

    That reasoning is now load-bearing in a way it was not on the day it was written: the paragraph
    baseline reached 0 on 2026-08-16, so absorbing an exempt page's paragraphs would not merely have
    loosened a ratchet, it would have made the cap unreachable.

    IT IS ALSO WHY `roles/` GOT ITS OWN BASELINES RATHER THAN A SEAT IN THESE ONES. The argument
    above is about six paragraphs from one exempt page. Absorbing `roles/` would be the same move at
    986, so the split below is that reasoning applied at the scale it was written for.
    """
    return [
        f
        for f in tracked_files()
        if f.endswith(".md")
        and f.startswith(prefixes)
        and "/word/" not in f
        and f not in t.AUTHORED_VERBATIM
        and f not in t.ARCHIVED_PAGES
    ]


def docs_prose_files() -> list[str]:
    """The site pages and the two root pages. The corpus the three ratchets were measured against."""
    return _markdown_under(("docs/", "README", "INSTALL"))


def role_prose_files() -> list[str]:
    """The role playbooks, `roles/retired/` included.

    A RETIRED PLAYBOOK IS STILL READ, which is why it is in the corpus rather than skipped as dead
    weight. This repository retires in place and keeps the wrong version with the reason it was
    wrong, so `roles/retired/` is prose someone is expected to open. It is also where the debt sits:
    of the 986 paragraphs over the limit, 357 are under `retired/`.
    """
    return _markdown_under(("roles/",))


def skills_prose_files() -> list[str]:
    """The trigger-loaded skills, split out of the playbooks on 2026-09-05.

    THIS CORPUS EXISTS BECAUSE A SPLIT MOVED PROSE OUT OF A SCAN WITHOUT MOVING THE SCAN. 6,336
    lines left `roles/` for `.claude/skills/` on 2026-09-05, and nothing followed them. `CLAUDE.md`
    went on saying the rules were enforced "against every tracked page" while the newest third of
    the playbook text was read by nothing.

    THAT IS THE FAILURE MODE THIS FILE'S HEADER NAMES, arriving by a route the header did not: the
    corpus did not shrink and no ratchet moved, so every number stayed green while its subject was
    quietly cut. A ratchet measures what it is pointed at, and a split re-points it.

    SO THE RULE IS THE CORPUS FOLLOWS THE PROSE. Moving a page out of `roles/` does not retire its
    prose obligations, and the next split has to add its destination here in the same change.

    THE VENDORED `speckit-*` SKILLS ARE NOT IN IT, and the reason is arithmetic rather than taste.
    They are Spec Kit 0.16.4 install output: `metadata.author` reads `github-spec-kit`, `metadata.
    source` names the upstream template, `.specify/integrations/claude.manifest.json` lists these
    exact paths, `.specify/init-options.json` pins that version, and `git log fa7ff92..HEAD` returns
    no commit touching any of them.

    THEY CARRY MOST OF THE DEBT AND NONE OF IT IS PAYABLE. Of 62 fat paragraphs, 44 are theirs; of
    37 long sentences, 25 are. Paying either means diverging from a pinned upstream, and a bump to
    0.17 would redden the run for reasons that have nothing to do with writing here.

    AND THE RATCHET COULD NEVER HAVE FIRED WITH THEM IN. The tighten arm asks for re-derivation at
    `baseline - slack`. Sweeping every payable fat paragraph moves 62 to 44 against an arm at 31;
    every payable long sentence moves 37 to 25 against an arm at 19. Perfect effort left both arms
    silent. At 18 and 12 the arms sit at 9 and 6, which pages korus owns can reach.

    `.specify/` ITSELF WAS ALREADY EXEMPT FOR THIS REASON, so leaving the same vendor's other output
    in would have given one release two answers inside one file.
    """
    return [f for f in _markdown_under((".claude/skills/",)) if "/speckit-" not in f]


def prose_files() -> list[str]:
    """Every prose page the hard-fail scan reads: docs, the role playbooks, and the skills.

    THE RATCHETS DO NOT USE THIS. They take one corpus each, because their numbers are not
    interchangeable. The hard-fail patterns take the union because they carry no number to launder:
    the corpus fires zero times on all three, and zero plus zero is still zero.

    `.claude/skills/` JOINED ON 2026-09-06 AT ZERO COST, measured rather than assumed: B-3, B-5 and
    B-6 return 0 hits each across all 28 skill pages, vendored ones included. That is the same
    reason they widened to the union in the first place -- a rule the corpus already satisfies costs
    nothing to enforce. The ten vendored pages are excluded from the RATCHETS, which carry numbers,
    and would have been harmless in this scan, which does not.
    """
    return docs_prose_files() + role_prose_files() + skills_prose_files()


RULE_ROW = re.compile(r"^\|\s*`?(?:B|HS|PD|OPEN|SD|CP)-\d+`?\s*\|")
FENCE = re.compile(r"^\s*(```|~~~)")
LIST_MARKER = re.compile(r"^(?:[-*+]|\d+\.)\s+")

# A raw HTML block, kramdown's own rule: a paragraph starting with '<' is markup, not prose, and
# runs until the next blank line -- matching how a fenced fence code block is excluded below, for
# the same reason. A hand-authored inline SVG diagram is the case that surfaced this: its attribute
# text (an aria-label, a multi-line figcaption) reads as sentences to a scanner that does not know
# the tag around it is not prose. Only the block's OPENING line has to start with '<'; a wrapped
# attribute or caption continuation line does not, which is why this tracks state rather than
# testing each line on its own the way FENCE-adjacent checks above do.
HTML_BLOCK_START = re.compile(r"^<[a-zA-Z!]")


def scannable_lines(text: str) -> list[tuple[int, str]]:
    """Prose lines only: no code fences, and no rule-definition rows.

    The rule-row exemption is why HOUSE-STYLE.md can list "utilize" as a banned word without this
    file reddening on it. It matches ONLY a table row whose first cell is a rule identifier.
    """
    out: list[tuple[int, str]] = []
    inside = False
    for n, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            inside = not inside
            continue
        if inside or RULE_ROW.match(line):
            continue
        out.append((n, line))
    return out


def paragraphs(text: str) -> list[tuple[str, list[tuple[int, int]]]]:
    """Prose rejoined into paragraphs, each with an offset -> line map.

    THIS IS THE WHOLE REASON THE CHECKER WORKS. HS-14 wraps prose near 100 characters, so a sentence
    here is spread over three or four lines. Scanning line by line gets both halves wrong: no line
    ever reaches 30 words, so a sentence-length measure reports zero, and a line that happens to
    BEGIN with a wrapped "importantly" looks like a sentence opener when it is the middle of one.
    Both were observed before this was rewritten.

    A LIST ITEM BEGINS ITS OWN UNIT, and its marker is not a word. Rejoining a list into one blob
    measured a run of items as a single sentence: 17 of the long sentences this file counted were
    lists, not sentences. The defect punished the fix it existed to ask for, because pulling a long
    sentence apart into bullets moved words from one blob into the same blob and changed nothing.
    A WRAPPED continuation line still belongs to the item above it, which is why only a line that
    STARTS with a marker flushes.

    Tables are excluded here and counted separately -- a table row is not prose and PD-4 protects it.
    """
    out: list[tuple[str, list[tuple[int, int]]]] = []
    current: list[tuple[int, str]] = []

    def flush() -> None:
        if not current:
            return
        parts: list[str] = []
        spans: list[tuple[int, int]] = []
        pos = 0
        for line_no, line in current:
            stripped = line.strip()
            if parts:
                pos += 1  # the space join() will insert
            spans.append((pos, line_no))
            parts.append(stripped)
            pos += len(stripped)
        out.append((" ".join(parts), spans))
        current.clear()

    inside = False
    inside_html = False
    for n, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            inside = not inside
            flush()
            continue
        stripped = line.strip()
        if inside:
            continue
        if not stripped:
            inside_html = False
            flush()
            continue
        if inside_html:
            continue
        if HTML_BLOCK_START.match(stripped):
            inside_html = True
            flush()
            continue
        if stripped.startswith(("|", "#", ">")) or RULE_ROW.match(line):
            flush()
            continue
        marker = LIST_MARKER.match(stripped)
        if marker:
            flush()
            line = stripped[marker.end() :]
        current.append((n, line))
    flush()
    return out


def line_at(spans: list[tuple[int, int]], offset: int) -> int:
    """Map a character offset inside a joined paragraph back to its source line."""
    line_no = spans[0][1]
    for start, n in spans:
        if start <= offset:
            line_no = n
        else:
            break
    return line_no


# ---------------------------------------------------------------------------
# Hard fail. Every pattern here fires zero times on the corpus as committed.

BANNED = [
    (
        "B-3",
        'an opener whose only work is to announce that what follows matters. Write the note.',
        re.compile(r"(?:\A|(?<=[.!?] ))(?:Importantly|Notably)\b|\bIt (?:is worth noting|should be noted)\b", re.I),
    ),
    (
        "B-5",
        'padding. Write "use", "to", or "can".',
        re.compile(r"\bin order to\b|\bprovides? the (?:capability|ability) to\b|\butili[sz](?:e|es|ed|ing)\b|\bleverag(?:ing|ed)\b", re.I),
    ),
    (
        "B-6",
        "a sentence asserting its own significance. State the fact that makes it significant.",
        re.compile(r"\bthis is (?:important|significant|critical)\b|\bthe key (?:point|thing) (?:is|here)\b|\bcannot be overstated\b|\bworth emphasi[sz]ing\b", re.I),
    ),
]


class BannedConstructionsAreAbsent(unittest.TestCase):
    def test_no_tracked_page_carries_a_banned_construction(self):
        offenders = []
        for relpath in prose_files():
            text = t.read(t.REPO_ROOT / relpath)
            for joined, spans in paragraphs(text):
                for rule_id, why, pattern in BANNED:
                    for m in pattern.finditer(joined):
                        line_no = line_at(spans, m.start())
                        offenders.append(f"{relpath}:{line_no}: {rule_id} {m.group(0).strip()!r} -- {why}")
        self.assertEqual(
            [],
            offenders,
            "these pages carry a construction docs/HOUSE-STYLE.md bans:\n  "
            + "\n  ".join(offenders)
            + "\nOnly the unambiguous rules are enforced here. If you believe one of these is a false "
            "positive, that is a reason to narrow the pattern in this file and say why in the commit "
            "-- not a reason to add an exemption for your page.",
        )

    def test_the_scan_actually_reads_the_corpus(self):
        """The empty-match guard. A scan for absences passes trivially against an empty corpus.

        THE FLOORS WENT UP WITH THE CORPUS, and that is the point rather than bookkeeping. At 15
        files and 30,000 words the guard passed on `docs/` alone, so `roles/` could have been
        dropped from `prose_files()` and this test would have stayed green over a corpus missing
        61% of its words. Both floors now sit ABOVE the docs-only figures -- 36 files and 115,357
        words at `1b6b7fc` -- which is what makes losing either half redden rather than pass.
        """
        files = prose_files()
        self.assertGreaterEqual(
            len(files),
            45,
            f"the prose scan found only {len(files)} pages, against 51 measured at 1b6b7fc. The "
            "absence check above would pass against an empty corpus while measuring nothing, so "
            "this is what makes it mean anything. If the corpus really did shrink this far, lower "
            "the number deliberately.",
        )
        words = sum(len(t.read(t.REPO_ROOT / f).split()) for f in files)
        self.assertGreater(
            words,
            150_000,
            f"only {words} words scanned; the corpus is ~295,000. Below 150,000 one of the two "
            "halves has gone missing: docs/ with README and INSTALL is ~115,000, roles/ ~180,000.",
        )


# EXEMPTIONS FROM `test_every_tracked_prose_page_lands_in_some_corpus`, EACH WITH ITS PRICE.
# Measured 2026-09-06 through this file's own `_measure` and `BANNED`. The guard found all five on
# its first run, which is the argument for keeping it: none were known before it existed.
#
# NOT ONE OF THESE IS EXEMPT FROM THE HOUSE STYLE. They are unmeasured, and the difference is the
# whole point of writing them down. Admitting a page means paying its debt or baselining it, and
# baselining it into `docs/` would hand every swept page that much silent headroom -- the move
# `_markdown_under` refuses at a scale of six.
#
#   page                                       long  fat paras  what blocks it
#   CLAUDE.md                                     0          0  B-5, on the line quoting the phrase
#   examples/sequence-adr/README.md               6          5  debt, and it is example prose
#   examples/sequence-adr/index-row-format.md     4          3  debt, and it is example prose
#   scripts/validation/README.md                  0          2  debt
#   specs/001-worker-brief/spec.md               12          9  debt
#   specs/002-fleet-wiki/spec.md                  0          0  none; specs/ has no corpus
#   specs/002-fleet-wiki/plan.md                  0          0  none; specs/ has no corpus
#
# THE TWO 002 PAGES ARE CLEAN, measured 2026-09-22 with `_measure([page])`: (0, 0, 2457, 0) and
# (0, 0, 912, 0). They are listed only because no corpus reads `specs/`, and admitting that prefix
# would pull in 001's debt. A `specs/` corpus is the fix once 001 is paid down.
#
# CLAUDE.md IS THE ONE TO FIX FIRST, and it is nearly free: zero long sentences, zero fat cells,
# zero fat paragraphs. One hard-fail hit blocks it, on the line that names `in order to` as a banned
# construction. That is the RULE_ROW problem in prose form -- a page stating the rules has to be able
# to quote them -- and `scannable_lines` exempts only a table row whose first cell is a rule id.
#
# THE FIX IS NOT A QUOTED-TEXT EXEMPTION. "Ignore the pattern inside quotes" is a loophole any page
# can reach for, and it would silence the rule everywhere to admit one page. Either widen RULE_ROW
# to the shape CLAUDE.md actually uses, or reword that one line. Both are edits somebody should make
# deliberately rather than as a side effect of adding a corpus.
UNREAD_PREFIXES = (
    ".specify/",   # vendored Spec Kit templates. Not written here and not read for guidance.
    "tests/",      # fixtures and this file's own README. Test data, not pages.
    ".claude/skills/speckit-",  # Spec Kit 0.16.4 install output. Same vendor as `.specify/` above.
)

UNREAD_PAGES = frozenset({
    "CLAUDE.md",
    "examples/sequence-adr/README.md",
    "examples/sequence-adr/index-row-format.md",
    "scripts/validation/README.md",
    "specs/001-worker-brief/spec.md",
    "specs/002-fleet-wiki/spec.md",
    "specs/002-fleet-wiki/plan.md",
})


def unread_pages(paths: list[str]) -> list[str]:
    """Tracked Markdown that no prose corpus reads, minus the named exemptions.

    A FUNCTION RATHER THAN A TEST BODY SO THE CONTROL CAN REACH IT. The guard's honest result is an
    empty list, and a filter that has broken returns an empty list too. Passing it a planted path is
    the only way to tell those apart, and that is this repository's rule about zeros.
    """
    covered = set(prose_files())
    return sorted(
        f
        for f in paths
        if f.endswith(".md")
        and not f.startswith(UNREAD_PREFIXES)
        and f not in UNREAD_PAGES
        and "/word/" not in f
        and f not in t.AUTHORED_VERBATIM
        and f not in t.ARCHIVED_PAGES
        and f not in covered
    )


class TheScannedCorpusIsBothHalves(unittest.TestCase):
    """Pinned separately from the word floor above, because the two fail differently.

    The floor catches a corpus that SHRANK. It cannot catch the two halves overlapping or one being
    counted twice, and a prefix typo does exactly that: `role_prose_files()` reading `("docs/",)` by
    mistake doubles the docs pages, keeps the union over every floor, and reports `roles/` clean by
    never opening it. Composition is the property; size is only its shadow.
    """

    def test_no_corpus_is_empty(self):
        self.assertTrue(docs_prose_files(), "the docs corpus is empty; every ratchet reads nothing.")
        self.assertTrue(role_prose_files(), "roles/ is empty. It was never read until 2026-09-04.")
        self.assertTrue(
            skills_prose_files(),
            ".claude/skills/ is empty. It was never read until 2026-09-06, and a split had put "
            "6,336 lines there. An empty corpus reports zero on every metric and reads like a pass.",
        )

    def test_the_thirds_do_not_overlap_and_the_union_is_their_sum(self):
        docs, roles, skills = docs_prose_files(), role_prose_files(), skills_prose_files()
        for a, b, why in (
            (docs, roles, "docs and roles"),
            (docs, skills, "docs and skills"),
            (roles, skills, "roles and skills"),
        ):
            self.assertEqual(set(), set(a) & set(b), f"a page is in both {why} and counted twice.")
        self.assertEqual(sorted(docs + roles + skills), sorted(prose_files()))

    def test_every_tracked_prose_page_lands_in_some_corpus(self):
        """The guard for the defect that created the skills corpus, not for its symptom.

        A split moves prose to a new prefix and no other test here notices. The corpora stay
        non-empty, they still do not overlap, their union still equals `prose_files()`, and every
        ratchet stays green over a subject that no longer holds the moved pages. Composition tests
        cannot see it, because nothing about the composition is wrong.

        So this asks the one question none of them ask: is there tracked Markdown that no corpus
        reads? Every exemption is named below with what it would cost to admit, because pruning one
        silently is the defect this test exists to catch.
        """
        unread = unread_pages(tracked_files())
        self.assertEqual(
            [],
            unread,
            "tracked Markdown that no prose corpus reads:\n  "
            + "\n  ".join(unread)
            + "\n\nAdd its prefix to a corpus above, or name it in this test with the reason. A "
            "page outside every corpus is not exempt from the house style. It is unmeasured, which "
            "is the state the skills corpus was added to end.",
        )

    def test_the_guard_fires_on_a_page_no_corpus_reads(self):
        """The positive control. Without it, a filter that matches nothing passes silently.

        `notes/whatever.md` is the shape of the next split: a new top-level prefix holding prose,
        added by somebody who did not think to widen a corpus. That is exactly how 6,336 lines
        reached `.claude/skills/` unmeasured on 2026-09-05.
        """
        self.assertEqual(
            ["notes/whatever.md"],
            unread_pages(["notes/whatever.md"]),
            "the guard did not fire on a page in no corpus, so it guards nothing.",
        )

    def test_the_guard_declines_a_page_a_corpus_already_reads(self):
        """The negative arm. A guard that fires on everything is as useless as one that never does."""
        already = prose_files()[0]
        self.assertEqual(
            [],
            unread_pages([already]),
            f"the guard flagged {already}, which a corpus already reads.",
        )

    def test_every_named_exemption_still_exists(self):
        """An exemption for a deleted file is a stale claim that reads like a live one."""
        tracked = set(tracked_files())
        gone = sorted(p for p in UNREAD_PAGES if p not in tracked)
        self.assertEqual(
            [],
            gone,
            "UNREAD_PAGES names files that are no longer tracked:\n  "
            + "\n  ".join(gone)
            + "\n\nDelete the row. An exemption outliving its file hides the next page that "
            "lands on the same path.",
        )

    def test_a_retired_playbook_is_in_the_corpus(self):
        """`roles/retired/` holds 357 of the 986 fat paragraphs. Skipping it would hide a third."""
        self.assertTrue(
            [f for f in role_prose_files() if f.startswith("roles/retired/")],
            "no retired playbook is scanned. This repository retires in place and keeps the wrong "
            "version, so a retired page is prose someone still opens.",
        )


class TheBannedPatternsCatchWhatTheyExistToCatch(unittest.TestCase):
    """Prove each pattern on a planted example, and prove it declines the near-neighbour.

    Without the negative half this class would pass against a pattern that matches everything.
    """

    PLANTED = [
        ("B-3", "Importantly, the gate is advisory."),
        ("B-3", "It is worth noting that the hook is unwired."),
        ("B-5", "The installer exists in order to write a shim."),
        ("B-5", "The script will utilize the registry."),
        ("B-5", "One program has begun leveraging an external framework."),
        ("B-6", "This is important: the gate is advisory."),
    ]

    # Every one of these appears in the corpus today, or is the near-miss the pattern must decline.
    ACCEPTED = [
        "Git merges both cleanly, and nothing in the graph can see it.",
        "A session that exits cleanly unlinks its registry file.",
        "The rows are ordered by its own leverage.",
        "The highest-leverage gate to build first.",
        "A version pin does not satisfy it, and more importantly does not satisfy the property.",
        "The one question: does failing it stop the change?",
    ]

    def test_each_pattern_fires_on_its_planted_example(self):
        for rule_id, planted in self.PLANTED:
            pattern = next(p for r, _, p in BANNED if r == rule_id)
            self.assertTrue(
                pattern.search(planted),
                f"{rule_id} did not fire on {planted!r}; the rule is unenforced.",
            )

    def test_no_pattern_fires_on_prose_the_corpus_legitimately_uses(self):
        for accepted in self.ACCEPTED:
            for rule_id, _, pattern in BANNED:
                m = pattern.search(accepted)
                if m is not None:
                    self.fail(
                        f"{rule_id} fired on {accepted!r}, matching {m.group(0)!r}. That sentence is "
                        "correct prose from this corpus, so the pattern is too wide and would redden "
                        "a legitimate page."
                    )

    def test_a_rule_definition_row_is_exempt_but_the_rest_of_the_page_is_not(self):
        """HOUSE-STYLE.md must be able to name what it bans, without becoming unscannable."""
        text = "| B-5 | \"in order to\", \"utilize\" | \"to\", \"use\" |\nThe installer runs in order to help."
        lines = scannable_lines(text)
        self.assertEqual(
            [2],
            [n for n, _ in lines],
            "the rule-row exemption should skip the table row and keep the prose line. Skipping "
            "more than the row would leave the rule sheet unchecked.",
        )


# ---------------------------------------------------------------------------
# Reported, and ratcheted. These may not get worse.

# Measured on 2026-08-08, AFTER the standards left for their own repository. The figures roughly
# halved with them, which is the whole point of a ratchet being re-derived rather than carried:
# keeping the old numbers would have left a gate that could never fail.
#
# MEASURE WITH THE FILES STAGED. `prose_files()` reads `git ls-files`, so a baseline taken before a
# deletion is staged still counts the deleted pages.
# To change one, run the test: it names the current figure and which direction it moved.
#
# These are lower than the figures in the writing plan (which counted 1,397 long sentences) because
# that count included headings, table rows and block quotes. This one is prose only, for the same
# reason PD-4 exists: a table row is not a sentence and shortening it is not an improvement.
# 470 -> 390 ON 2026-08-10 WITH NO SENTENCE EDITED. Both drops were measurement errors in this
# file, found by the sibling standards repository in its own copy of this checker and reproduced
# here: 17 for a bullet list rejoined into one blob, 67 for a stop inside `**` not counting as a
# stop. 80 of the old 470, or 17%, was the instrument rather than the prose. Any figure quoted from
# a scan before this date should be re-derived. Both are pinned by planted cases above, because a
# corpus check cannot find them -- the corpus is where the wrong number came from.
#
# 390 -> 294 ON 2026-08-10 BY EDITING PROSE, in a sweep over the 18 pages the site RENDERS. Every
# edit split a sentence carrying two independent claims joined by a dash or a semicolon, where
# splitting cost no fact; five enumerations became lists. Nothing was cut: the checklist that
# prompted the sweep was measured against this corpus first and found nothing to purge, with B-5,
# B-11, B-12, B-13 and B-14 all firing zero times and every `very`/`really` hit load-bearing.
#
# 294 -> 290 ON 2026-08-10 by the OPEN-7 pass, which gave all 18 rendered pages a three-answer
# opening. That pass ADDED prose and still came out ahead, because this ratchet caught its own new
# sentences: eight of the openings were written over 30 words, and the failure named them before the
# work landed rather than after.
#
# 68 OF THE REMAINING 290 WERE IN README.md AND INSTALL.md, which neither sweep touched. They are in
# this corpus but are not site pages: they live at the repository root, outside the Jekyll source, so
# the site links them as raw `.md` rather than serving them. They were named here as the obvious next
# chunk, and 68 as the figure to beat. That chunk was taken on 2026-08-16, below.
#
# 181 -> 59 AND 19 -> 11 ON 2026-08-16, in the pass that rebuilt the site as a KORUS how-to guide.
# Every page under docs/ was rewritten for a reader rather than for completeness, and README.md and
# INSTALL.md were swept for the first time. The two figures moved for the same reason and by the same
# means: a sentence carrying two independent claims became two sentences, and a paragraph that
# narrated its own reasoning before reaching the fact lost the narration.
#
# NOTHING WAS REACHED BY DELETION, and that was checked rather than asserted. Every numeric token and
# every link target in the pre-pass revision was diffed against the post-pass one. Three pages came
# back with a token missing; two were deliberate (a range rewritten as `HS-20 to HS-23`, a date
# restated twice and now stated once) and the third was a real loss -- the ASVS large-assessment link
# dropped when the landing page was split -- which was restored to the page that now owns that case.
BASELINE_LONG_SENTENCES = 7        # sentences over 30 words
BASELINE_FAT_TABLE_CELLS = 11       # table cells over 40 words

# HS-20: a paragraph over 300 characters. THE BASELINE IS NOW ZERO, SO THIS IS A CAP RATHER THAN A
# RATCHET, and the next paragraph written over the limit fails the run rather than being absorbed.
#
# It did not start that way, and the history is the argument for the mechanism. The rule was written
# on 2026-08-10 against a measured corpus: 391 of 1,387 rendered-site paragraphs were over the limit,
# a shade under a third, so a hard fail would have shipped disabled on day one for the reason this
# file's header states. It shipped as a ratchet at 88 instead, and the debt was paid down to nothing
# on 2026-08-16.
#
# TREAT A FAILURE HERE AS A CAP BEING HIT, NOT AS A NUMBER TO RAISE. Raising it re-opens the debt
# this took two sweeps to clear, and the corpus can no longer absorb a paragraph silently.
#
# THE FIX IS A REWRITE, NOT A SPLIT. Chopping a long paragraph in half satisfies the number and
# changes nothing a reader experiences: the same prose arrives in two pieces. An over-long paragraph
# here is treated as a signal that the writing wound up, restated itself, or narrated its own
# reasoning before getting to the fact. What comes out is shorter because it says the same things in
# fewer words -- never because a measurement, a date, a limit or a mechanism sentence was dropped.
# PD-1 through PD-7 outrank this rule, and an editor who satisfies it by deleting a number has
# broken the sheet rather than served it.
#
# 88 -> 15 ON 2026-08-16, and the corpus is no longer meaningfully red behind this rule. Every page
# under docs/ now carries ZERO paragraphs over the limit; all 15 that remain are in README.md and
# INSTALL.md, the two files that live at the repository root and had never been swept.
#
# THE RULE WENT UP BEFORE IT CAME DOWN, which is the part worth keeping. The same pass that fixed the
# corpus first made it worse -- 88 to 110 -- because four new pages and a batch of rewrites each added
# a paragraph or two over the limit, and every one of them read fine in isolation. The ratchet named
# all 22 with their line numbers before the work landed. Nothing else would have: this defect is
# invisible to review, because the offending paragraph is never the one you are looking at.
#
# 15 -> 0 the same day, once the last two files were swept. Every page in the corpus is now under
# the limit, including README.md and INSTALL.md.
BASELINE_FAT_PARAGRAPHS = 0        # paragraphs over 300 chars (HS-20). A CAP now, not a ratchet.
FAT_PARAGRAPH_LIMIT = 300

# How far below baseline a metric may drift before the test asks for the baseline to be lowered.
# Sized to each metric rather than shared: 40 is noise against 833 and most of the way to zero
# against 49.
LONG_SENTENCE_SLACK = 30
FAT_CELL_SLACK = 5
FAT_PARAGRAPH_SLACK = 25

# ---------------------------------------------------------------------------
# The roles/ corpus. Separate numbers, measured 2026-09-04, and the argument for keeping them
# separate is the point of this block.
#
# HOW THEY WERE MEASURED, because a number without its instrument is not a measurement.
#
#   python -m pytest tests/test_prose_rules_hold.py -q
#
# On a clean tree that is the whole instrument: set a ROLES_ baseline to 0 and the run names the
# true figure in its own failure text. THE TREE WAS NOT CLEAN when these were taken. `git status`
# reported uncommitted edits to four files under `docs/` and three under `roles/`, none of them
# this one, so the working tree was a moving subject and a figure read off it could not be
# re-derived from any ref. How many sessions held those edits was not measured and is not claimed.
#
# SO THE BASELINES ARE MEASURED AT `HEAD`, through this file's own `paragraphs()` and
# `scannable_lines()` over `git show HEAD:<path>` for every path `role_prose_files()` returns.
# Same code, stable subject. Anyone can reproduce them by running the command above on a clean
# checkout of that commit.
#
# WHAT THE TWO SUBJECTS RETURNED, docs alongside roles for comparison:
#
#                                    HEAD              working tree
#   long sentences over 30 words     docs 49  roles 708    docs 49  roles 708
#   table cells over 40 words        docs 10  roles 138    docs 12  roles 140
#   paragraphs over 300 characters   docs  0  roles 986    docs  3  roles 987
#
# THE WORKING-TREE COLUMN IS THE RATCHET DOING ITS JOB, not noise to baseline away. Eight
# regressions across four corpus-and-metric pairs, none of them in this file's diff, every one named
# before the edits carrying them were even committed. Baselining to that column would have gone
# green and bought somebody else's regressions with this file's signature on the purchase.
#
# THEY WERE ALSO TRANSIENT, which is the second half of the argument for `HEAD`. Between the first
# reading and the last the docs figures moved 10 -> 12 -> 10 and 0 -> 3 -> 1 -> 0 as the other
# edits were revised. Every one of those was a real reading, and any of them baselined would have
# been wrong within the hour.
#
# THE THREE HARD-FAIL PATTERNS RETURNED ZERO on `roles/`, which is why B-3, B-5 and B-6 widened to
# the union corpus with no page edited. The ratchets could not follow, and that asymmetry is the
# honest result rather than an obstacle: a rule the corpus already satisfies costs nothing to
# enforce, and a rule it does not is debt that has to be named before it can be paid.
#
# WHAT WAS NOT VARIED, and it bounds every figure above. All six numbers come from ONE revision of
# ONE repository on ONE day. They say nothing about whether `roles/` is worse prose than `docs/`:
# `roles/` was never swept, and `docs/` was swept twice (2026-08-10 and 2026-08-16, both recorded
# above). The comparison measures sweeps, not authors.
ROLES_BASELINE_LONG_SENTENCES = 417
ROLES_BASELINE_FAT_TABLE_CELLS = 6

# HS-20 OVER `roles/`: A MEASURED RATCHET AT 986, NOT A CAP AND NOT AN EXCLUSION. Three options
# were on the table and this comment exists so the two rejected ones stay visible.
#
# REJECTED: one shared baseline of 986. It goes green immediately, and it is the exact move
# `_markdown_under`'s docstring refuses at a scale of six. `docs/` reached zero over two sweeps;
# folding `roles/` in would hand every page under `docs/` 986 paragraphs of silent headroom against
# a cap it has already met. The cap would survive as a constant and stop being reachable.
#
# REJECTED: excluding `roles/` from HS-20 the way OPEN-8 pages are excluded. The OPEN-8 reason does
# not transfer. Those pages are exempt because no edit is AVAILABLE -- they are published in their
# author's words. A role playbook is edited here every week, so the debt is payable, and an
# exclusion would record none of the paying.
#
# CHOSEN: a second ratchet, measured, sitting beside the cap rather than inside it. It cannot go up,
# it names the new figure whenever a sweep brings it down, and `docs/` keeps its zero.
#
# TREAT 986 AS DEBT, NOT AS A BUDGET. It is the largest single number this file has ever carried --
# BASELINE_FAT_PARAGRAPHS peaked at 110 before it was paid to zero. Three files hold 627 of it:
# LANDER.md 355, COMMON.md 143, retired/PM.md 129. THE FIX IS A REWRITE, NOT A SPLIT, and PD-1 to
# PD-7 outrank the number exactly as they do for the docs cap above.
ROLES_BASELINE_FAT_PARAGRAPHS = 489

# One tenth of each measured figure, rounded down. The docs slacks above are near half their
# baselines, which is right at 58 and 11 where a tenth would be 5 and 1 and every ordinary edit
# would redden the run. At 708 and 986 the same ratio would let a whole file be swept without the
# ratchet ever asking to be tightened, and an unrecorded paydown is how a ratchet stops meaning
# anything. Tighter here buys more re-derivation, which is what a corpus this far in debt needs.
ROLES_LONG_SENTENCE_SLACK = 70
ROLES_FAT_CELL_SLACK = 13
ROLES_FAT_PARAGRAPH_SLACK = 98

# `.claude/skills/`, MEASURED 2026-09-06 THROUGH THIS FILE'S OWN `_measure` OVER THE 18 AUTHORED
# PAGES, 22,159 words. The ten vendored `speckit-*` pages are excluded, and `skills_prose_files`
# carries the evidence and the arithmetic. A third corpus rather than a seat in either existing one,
# for the reason `_markdown_under` gives at the scale it was written for.
#
# THE FIRST VERSION OF THIS BLOCK READ 37 / 0 / 62 OVER ALL 28 PAGES, and it is recorded rather than
# quietly replaced because the failure it carried is the interesting part. The numbers were real and
# the corpus was wrong, so every arm went green over a subject two thirds of which nobody here could
# edit. A measurement can be exactly right and still measure the wrong thing.
#
# THE FAT-CELL FIGURE IS ZERO, SO THAT ONE IS A CAP FROM THE START. It is the only baseline in this
# file that never had debt to pay, and the next 40-word cell written into a skill fails the run
# rather than being absorbed. Do not raise it.
#
# WHY THESE ARE SMALLER THAN `roles/` AND IT PROVES NOTHING ABOUT THE WRITING. The skills were cut
# from `roles/` by a mechanical split that moved whole sections and reworded none, so the two
# corpora hold the same authorship at different dates. What the gap measures is which pages the
# split happened to carry, not that one set is better prose than the other.
SKILLS_BASELINE_LONG_SENTENCES = 12
SKILLS_BASELINE_FAT_TABLE_CELLS = 0    # a CAP from the start, not a ratchet. Never raise it.
SKILLS_BASELINE_FAT_PARAGRAPHS = 18

# Near half, matching the docs slacks rather than the `roles/` tenth. THE TEST THAT MATTERS IS
# WHETHER THE TIGHTEN ARM CAN EVER FIRE: at 18 and 12 it sits at 9 and 6, and sweeping pages korus
# owns reaches both. The rejected 62 and 37 put it at 31 and 19, which perfect effort could not
# reach. Check that arithmetic before changing either number.
#
# THE `roles/` COMMENT ABOVE CITES 708 AND 986. Its constants three lines on read 417 and 489, and
# both arrived in `e5fefd5`. Those two figures have no instrument that reproduces them today, so
# nothing here rests on them; the live constants are what this block was compared against.
SKILLS_LONG_SENTENCE_SLACK = 6
SKILLS_FAT_CELL_SLACK = 5
SKILLS_FAT_PARAGRAPH_SLACK = 9

# A STOP INSIDE EMPHASIS IS STILL A STOP. This document set writes `**A claim.** The evidence.`
# constantly, and the bare `(?<=[.!?])\s+` form never fired on it, because the character after the
# stop is `*` rather than a space. Every such paragraph measured its bold lede fused to the sentence
# after it, which is 67 of the long sentences this file used to count. The defect punished its own
# remedy: splitting a fused claim off as its own lede is the ordinary fix, and it made the number
# worse. A COLON lede -- `**Control not met:** independent review` -- introduces rather than closes
# and must NOT split, which is why only `[.!?]` widens. Before widening, every emphasis run ending
# in a stop was read: all are lede labels, and an abbreviation inside emphasis (`**e.g.**`), which
# WOULD cut mid-sentence, does not occur in this corpus.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])(?:\*{1,2})?\s+")


def _measure(files: list[str]) -> tuple[int, int, int, int]:
    """(sentences over 30 words, table cells over 40 words, words examined, paragraphs over 300).

    THE CORPUS IS AN ARGUMENT, not a call to `prose_files()`. Each ratchet measures one corpus and
    compares it to that corpus's own baseline; passing the union in would produce one number that
    no single baseline can be read against.
    """
    long_sentences = 0
    fat_cells = 0
    fat_paragraphs = 0
    words = 0
    for relpath in files:
        text = t.read(t.REPO_ROOT / relpath)
        for joined, _ in paragraphs(text):
            words += len(joined.split())
            if len(joined) > FAT_PARAGRAPH_LIMIT:
                fat_paragraphs += 1
            for sentence in SENTENCE_SPLIT.split(joined):
                if len(sentence.split()) > 30:
                    long_sentences += 1
        for line_no, line in scannable_lines(text):
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            for cell in stripped.strip("|").split("|"):
                if len(cell.split()) > 40:
                    fat_cells += 1
    return long_sentences, fat_cells, words, fat_paragraphs


class AListIsNotOneLongSentence(unittest.TestCase):
    """Planted, because the corpus cannot find this one: the corpus IS where the wrong number came
    from. A measure that counts a run of bullets as one 40-word sentence reports a defect that is
    not there, and reports no change when somebody applies the fix it was asking for."""

    def test_each_item_is_its_own_unit(self):
        text = "- the gate is advisory\n- the hook is unwired\n- the claim is stale\n"
        self.assertEqual(3, len(paragraphs(text)))

    def test_a_marker_is_not_counted_as_a_word(self):
        joined, _ = paragraphs("- one two three\n")[0]
        self.assertEqual(3, len(joined.split()), f"the marker leaked into {joined!r}")

    def test_a_numbered_item_splits_too(self):
        self.assertEqual(2, len(paragraphs("1. the first\n2. the second\n")))

    def test_a_wrapped_continuation_stays_with_its_item(self):
        """HS-14 wraps near 100 characters, so most items are more than one line."""
        text = "- the gate is advisory and this item\n  wraps onto a second line\n- a second item\n"
        units = paragraphs(text)
        self.assertEqual(2, len(units))
        self.assertIn("wraps onto a second line", units[0][0])

    def test_a_dash_run_and_a_bold_opener_are_not_markers(self):
        """`--` is this corpus's em dash and `**` opens a lede. Neither begins a list."""
        for text in ("-- the aside continues\nand wraps here\n", "**Trap.** The gate is advisory\nand wraps\n"):
            self.assertEqual(1, len(paragraphs(text)), f"{text!r} was split as a list")


class RawHtmlIsNotProse(unittest.TestCase):
    """Planted, for the same reason as the list class above: an inline SVG diagram is markup, and a
    scanner that does not know that reads its coordinates and its aria-label as run-on sentences.
    Surfaced by docs/FRAMEWORK-bmad.md's comparison diagram, whose figcaption alone was long enough
    to fail on its own before this exclusion existed."""

    def test_an_svg_block_is_excluded(self):
        text = (
            "Prose before.\n\n"
            '<svg viewBox="0 0 10 10">\n'
            '  <text x="1" y="1">label</text>\n'
            "</svg>\n\n"
            "Prose after.\n"
        )
        units = paragraphs(text)
        self.assertEqual(2, len(units))
        self.assertEqual("Prose before.", units[0][0])
        self.assertEqual("Prose after.", units[1][0])

    def test_a_wrapped_attribute_stays_excluded(self):
        """The opening line starts with '<'; a wrapped aria-label or figcaption continuation does
        not, and still has to stay out -- this is why the state persists to the next blank line
        rather than testing each line for a leading '<' on its own."""
        text = (
            '<figcaption>A sentence that keeps going\n'
            "onto a second line with no leading angle bracket at all.</figcaption>\n\n"
            "Real prose paragraph.\n"
        )
        units = paragraphs(text)
        self.assertEqual(1, len(units))
        self.assertEqual("Real prose paragraph.", units[0][0])

    def test_a_less_than_sign_starting_a_sentence_is_not_swallowed(self):
        """Guards the exclusion from being too broad: '<' beginning ordinary prose (a comparison,
        not a tag) must still be measured."""
        text = "<100ms is the budget, and the gate enforces it.\n"
        units = paragraphs(text)
        self.assertEqual(1, len(units))
        self.assertIn("budget", units[0][0])


class ABoldLedeEndsASentence(unittest.TestCase):
    """The larger of the two, and the one that punished its own remedy. Positive cases and the
    near-neighbours that must NOT split are pinned together; without the negative half this passes
    against a pattern that splits on every asterisk."""

    SPLITS = [
        ("**Rule.** Pick the source.", 2),
        ("**Trap.** The gate is advisory.", 2),
        ("*Rule.* Pick the source.", 2),
        ("The gate is advisory. It never blocks.", 2),
    ]

    HOLDS = [
        # A colon lede introduces what follows; cutting here would sever the label from its content.
        "**Control not met:** independent review never happened.",
        # Emphasis inside a sentence, which is not a lede at all.
        "An entry is a *claim*; a receipt is evidence.",
        "The rows are ordered by *leverage* rather than by name.",
    ]

    def test_a_stop_inside_emphasis_splits(self):
        for text, expected in self.SPLITS:
            self.assertEqual(
                expected,
                len(SENTENCE_SPLIT.split(text)),
                f"{text!r} did not split into {expected}; a bold lede is fusing with what follows.",
            )

    def test_the_near_neighbours_stay_whole(self):
        for text in self.HOLDS:
            self.assertEqual(
                1,
                len(SENTENCE_SPLIT.split(text)),
                f"{text!r} was split. That is one sentence, and the pattern is too wide.",
            )


# Each row: corpus name, the files it reads, the constant to edit, its value, its slack.
# THREE ROWS PER METRIC, ONE PER CORPUS. The constant NAME travels in the row because the failure
# text has to name the line to edit -- a message that says "lower the baseline" over three baselines
# sends the reader to the wrong one, and two of the three are already at zero.
LONG_SENTENCE_RATCHET = (
    ("docs", docs_prose_files, "BASELINE_LONG_SENTENCES", BASELINE_LONG_SENTENCES, LONG_SENTENCE_SLACK),
    ("roles", role_prose_files, "ROLES_BASELINE_LONG_SENTENCES", ROLES_BASELINE_LONG_SENTENCES, ROLES_LONG_SENTENCE_SLACK),
    ("skills", skills_prose_files, "SKILLS_BASELINE_LONG_SENTENCES", SKILLS_BASELINE_LONG_SENTENCES, SKILLS_LONG_SENTENCE_SLACK),
)

FAT_CELL_RATCHET = (
    ("docs", docs_prose_files, "BASELINE_FAT_TABLE_CELLS", BASELINE_FAT_TABLE_CELLS, FAT_CELL_SLACK),
    ("roles", role_prose_files, "ROLES_BASELINE_FAT_TABLE_CELLS", ROLES_BASELINE_FAT_TABLE_CELLS, ROLES_FAT_CELL_SLACK),
    ("skills", skills_prose_files, "SKILLS_BASELINE_FAT_TABLE_CELLS", SKILLS_BASELINE_FAT_TABLE_CELLS, SKILLS_FAT_CELL_SLACK),
)

FAT_PARAGRAPH_RATCHET = (
    ("docs", docs_prose_files, "BASELINE_FAT_PARAGRAPHS", BASELINE_FAT_PARAGRAPHS, FAT_PARAGRAPH_SLACK),
    ("roles", role_prose_files, "ROLES_BASELINE_FAT_PARAGRAPHS", ROLES_BASELINE_FAT_PARAGRAPHS, ROLES_FAT_PARAGRAPH_SLACK),
    ("skills", skills_prose_files, "SKILLS_BASELINE_FAT_PARAGRAPHS", SKILLS_BASELINE_FAT_PARAGRAPHS, SKILLS_FAT_PARAGRAPH_SLACK),
)


class TheReportedMetricsDoNotRegress(unittest.TestCase):
    """A ratchet, not a cap. The plan rejected all three as hard fails, with the measurement.

    EACH METRIC RUNS THREE TIMES, over `docs/`, `roles/` and `.claude/skills/`, against that
    corpus's own baseline. A subTest per corpus so one red corpus still reports the others' figures.
    With a single assertion the later numbers would be invisible behind the first failure.
    """

    def _ratchet(self, count: int, name: str, constant: str, baseline: int, slack: int, why: str) -> None:
        """Both sides of one ratchet. It may not grow, and it may not quietly shrink either."""
        self.assertLessEqual(
            count,
            baseline,
            f"{name}: {count} against a baseline of {baseline} ({constant}). {why}",
        )
        self.assertGreater(
            count,
            baseline - slack,
            f"{name}: only {count} remain, against a baseline of {baseline}. Lower {constant} to "
            f"{count} in this file. A ratchet nobody tightens stops measuring anything.",
        )

    def test_it_reports_what_it_examined(self):
        for name, files, floor in (
            ("docs", docs_prose_files, 30_000),
            ("roles", role_prose_files, 60_000),
            ("skills", skills_prose_files, 20_000),
        ):
            with self.subTest(corpus=name):
                long_sentences, _, words, _ = _measure(files())
                self.assertGreater(
                    words,
                    floor,
                    f"the {name} pass examined {words} words of prose, which is too few to have "
                    "read the corpus. A measurement over nothing reports zero and reads like a "
                    "pass.",
                )
                self.assertGreater(
                    long_sentences,
                    0,
                    f"zero sentences over 30 words is not credible for {name} and means the "
                    "paragraph rejoin has broken. It reported exactly this before the line-based "
                    "scan was replaced.",
                )

    def test_long_sentences_do_not_increase(self):
        for name, files, constant, baseline, slack in LONG_SENTENCE_RATCHET:
            with self.subTest(corpus=name):
                count, _, _, _ = _measure(files())
                self._ratchet(
                    count, name, constant, baseline, slack,
                    "Sentences over 30 words. This is not a cap -- the long tail of this corpus is "
                    "where the engineering warnings live -- but it may not grow.",
                )

    def test_fat_table_cells_do_not_increase(self):
        for name, files, constant, baseline, slack in FAT_CELL_RATCHET:
            with self.subTest(corpus=name):
                _, count, _, _ = _measure(files())
                self._ratchet(
                    count, name, constant, baseline, slack,
                    "Table cells over 40 words. PD-4 forbids solving this by converting a table to "
                    "prose.",
                )

    def test_fat_paragraphs_do_not_increase(self):
        for name, files, constant, baseline, slack in FAT_PARAGRAPH_RATCHET:
            with self.subTest(corpus=name):
                _, _, _, count = _measure(files())
                self._ratchet(
                    count, name, constant, baseline, slack,
                    f"Paragraphs over {FAT_PARAGRAPH_LIMIT} characters (HS-20). Fix it by REWRITING "
                    "the paragraph shorter, not by splitting it in two -- a split satisfies the "
                    "count and changes nothing a reader experiences. PD-1 to PD-7 outrank this: "
                    "never reach the number by deleting a measurement, a date, a limit or a "
                    "mechanism sentence. The docs baseline is a CAP at zero and must not be "
                    "raised; the roles baseline is debt and moves one way only, down.",
                )


if __name__ == "__main__":
    unittest.main()
