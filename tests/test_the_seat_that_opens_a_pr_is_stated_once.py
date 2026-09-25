"""Who opens a pull request is one rule, and it is written in fourteen files.

WHAT THIS EXISTS FOR. On 2026-09-18 the owner moved pull-request opening from the Builder to the
Manager. The old rule was not stated once. It was stated, in slightly different words, in
`roles/COMMON.md`, `roles/BUILDER.md`, `roles/LANDER.md`, `roles/STEWARD.md`, `roles/README.md`,
three role cards, the working agreement, four pages under `docs/` and a skill. Repointing them took
one sweep and a grep, and nothing makes them stay repointed.

THE FAILURE THIS PINS. A later edit -- a playbook split, a revert, a seat copying a retired row it
remembers -- restores "opens its own pull request" as a LIVE instruction covering the Builder. Every
other check in this suite stays green, because they measure prose shape, link targets and corpus
membership, not what a sentence claims. Two seats then open the same pull request, or a Builder
holds a finished branch waiting to open one it may not.

WHY IT IS NOT A BARE BAN ON THE PHRASE. `roles/COMMON.md`'s *Never assert a string's global absence
in a document whose job is to discuss that string* is exactly this corpus. These files QUOTE the
retired wording, and must keep quoting it: a retired rule is kept with the reason it was retired, so
a seat that remembers it meets the correction instead of re-deriving it. A scan that forbade the
string would fire on every correction and be disabled within a day.

So the discrimination is between a QUOTED rule and an ASSERTED one. A retirement note carries a
marker on the same line -- RETIRED, NARROWED, CHANGED, "it read", "until 2026-..", "no longer". A
live instruction does not.

ARTICLE V. A check that passes against an empty corpus measures nothing, so every assertion below is
paired with a planted control that MUST fire. Planting one in the tree would be the violation the
test exists to catch, so the controls are synthetic strings -- AND THAT IS WHERE THE FIRST VERSION OF
THIS FILE WENT WRONG. See `BUILDER_SUBJECT_NOTE` below: its controls named the Builder, the real
wording never did, and the test passed against the pre-change tree. The controls that decide this
test now are the three lines the repository actually shipped, read off `main`.
"""

from __future__ import annotations

import re
import unittest

import _ccxtest as t

#: Every file that states, or has stated, who opens a pull request. Enumerated rather than globbed:
#: adding a file here has to be a visible diff somebody approves, and a glob would quietly widen the
#: subject the day somebody adds a page that mentions pull requests in passing.
CORPUS = (
    "CLAUDE.md",
    "roles/COMMON.md",
    "roles/BUILDER.md",
    "roles/LANDER.md",
    "roles/MANAGER.md",
    "roles/STEWARD.md",
    "roles/README.md",
    "docs/roles/builder.card.md",
    "docs/roles/manager.card.md",
    "docs/roles/lander.card.md",
    "docs/PLAYBOOKS.md",
    "docs/KORUS-BUILD.md",
    "docs/WORKER-BRIEF.md",
    ".claude/skills/fleet-push-or-open-a-pr/SKILL.md",
)

#: A line that tells SOMEBODY to open their own pull request. Deliberately loose: the job of this
#: pattern is to catch the sentence in whatever wording it comes back in, and the marker test below
#: is what keeps the loose pattern from being noise.
OPENS_ITS_OWN = re.compile(
    r"open(?:s|ing)?\s+(?:its|their|your|his|her)\s+own\s+(?:pull request|PR)",
    re.IGNORECASE,
)

BUILDER_SUBJECT_NOTE = """THE FIRST VERSION OF THIS TEST MATCHED ONLY THE WORD "BUILDER", AND IT
PASSED AGAINST THE PRE-CHANGE TREE. Measured 2026-09-18: `main`'s `roles/COMMON.md` copied over the
current one left this file green at 8 passed. The rule it was built to catch was written *"Every
seat pushes its own branch and opens its own pull request"*, which never says "Builder";
`roles/STEWARD.md` wrote the same sentence with "PR"; and `roles/BUILDER.md` wrote *"You push your
own branch and open your own pull request"*, which never says it either. Three live sites, zero
caught, and the only thing that fired was the synthetic string planted by the same hand that wrote
the pattern. A control an author invents tests the pattern against its author's imagination."""

#: The seat named on the line.
BUILDER = re.compile(r"\bbuilder\b", re.IGNORECASE)

#: A universal quantifier over seats. "Every seat opens its own pull request" is now FALSE, because
#: the Builder is an exception, so an unmarked universal is a violation wherever it appears.
UNIVERSAL = re.compile(
    r"\bevery seat\b|\beach seat\b|\ball seats\b|\bevery session\b|\bsessions\b",
    re.IGNORECASE,
)

#: Files whose whole subject is the Builder. In these a bare "you" or "your own" IS the Builder, so
#: an unmarked occurrence counts without the word appearing on the line.
BUILDER_OWN_FILES = frozenset({"roles/BUILDER.md", "docs/roles/builder.card.md"})

#: What makes an occurrence a QUOTATION of a retired rule rather than a live instruction. Any one of
#: these on the same line is enough. They are the markers this corpus already uses.
RETIREMENT_MARKER = re.compile(
    r"RETIRED|NARROWED|WITHDRAW|CHANGED \d{4}|SUPERSED"
    r"|until \d{4}-\d{2}-\d{2}|no longer|it read|that row read|this read|EXCEPT|does not",
    re.IGNORECASE,
)


#: A line scoped to a Builder in its OWN SESSION. Owner ruling 2026-09-24:
#: the Manager opens the pull request only for a Builder that is its subagent. A Builder a chip
#: started, or the Manager spawned, opens its own, so a line naming that scope is the live rule, not
#: the retired one. The scope must be on the same line, as the retirement marker must: an unscoped
#: line still reads as the old rule.
OWN_SESSION_SCOPE = re.compile(r"own session|spawned you|a chip started", re.IGNORECASE)


def unmarked_builder_lines(text: str, relpath: str = "") -> list[str]:
    """Lines telling a Builder to open its own pull request, with no retirement marker.

    Three ways a line is about the Builder, and the last two are the ones the real wording used:
    the word itself, a universal over seats, or the file being the Builder's own playbook.
    """
    subject_is_builder = relpath in BUILDER_OWN_FILES
    out = []
    for line in text.splitlines():
        if not OPENS_ITS_OWN.search(line):
            continue
        if not (subject_is_builder or BUILDER.search(line) or UNIVERSAL.search(line)):
            continue
        if RETIREMENT_MARKER.search(line) or OWN_SESSION_SCOPE.search(line):
            continue
        out.append(line.strip())
    return out


class TheCorpusIsReal(unittest.TestCase):
    """The subject has to exist before a zero over it means anything."""

    def test_every_named_file_is_present(self):
        missing = [f for f in CORPUS if not (t.REPO_ROOT / f).is_file()]
        self.assertEqual([], missing, f"corpus names files that are not here: {missing}")

    def test_the_corpus_actually_discusses_pull_requests(self):
        """A file that stopped mentioning pull requests is a file that dropped the rule.

        Without this, deleting the sentence from a card would show up as a pass.
        """
        silent = []
        for relpath in CORPUS:
            body = t.read(t.REPO_ROOT / relpath).lower()
            if "pull request" not in body and " pr " not in body:
                silent.append(relpath)
        self.assertEqual([], silent, f"these no longer mention a pull request at all: {silent}")


class TheDetectorFires(unittest.TestCase):
    """Planted controls. Every one MUST fire, or the zero below is a broken instrument."""

    def test_the_three_wordings_this_tree_actually_shipped_are_caught(self):
        """The controls that decide this test, read off `main` rather than invented.

        `BUILDER_SUBJECT_NOTE` records what happened when they were missing.
        """
        common = (
            "| Every seat pushes its own branch and opens its own pull request | No approval "
            "needed. |"
        )
        steward = "| Every seat pushes its own branch and opens its own PR | COMMON owns it. |"
        builder = (
            "| You push your own branch and open your own pull request | Owner ruling "
            "2026-08-29. |"
        )
        self.assertEqual(1, len(unmarked_builder_lines(common)), "COMMON's universal form missed")
        self.assertEqual(1, len(unmarked_builder_lines(steward)), "STEWARD's PR spelling missed")
        self.assertEqual(
            1,
            len(unmarked_builder_lines(builder, "roles/BUILDER.md")),
            "BUILDER.md's second-person form missed",
        )

    def test_the_second_person_form_counts_only_in_the_builders_own_files(self):
        """Otherwise every seat's own playbook would redden on its own correct rule."""
        builder = "| You push your own branch and open your own pull request | Owner ruling. |"
        self.assertEqual([], unmarked_builder_lines(builder, "roles/LANDER.md"))

    def test_an_unmarked_live_instruction_naming_the_seat_is_caught(self):
        planted = "| Builder | One brief, one turn. It opens its own pull request, then exits. |"
        self.assertEqual([planted], unmarked_builder_lines(planted))

    def test_a_retired_quotation_is_not_caught(self):
        kept = (
            '| **RETIRED 2026-09-18** | It read *"the Builder pushes and opens its own pull '
            'request."* The Manager opens it now. |'
        )
        self.assertEqual([], unmarked_builder_lines(kept))

    def test_a_builder_in_its_own_session_is_not_caught(self):
        """The 2026-09-24 scope. Paired with the next test, so it cannot silence everything."""
        scoped = "### A Builder in its own session opens its own pull request"
        spawned = (
            "In your own session, whether a chip started you or the Manager spawned you, open "
            "your own pull request."
        )
        self.assertEqual([], unmarked_builder_lines(scoped))
        self.assertEqual([], unmarked_builder_lines(spawned, "roles/BUILDER.md"))

    def test_the_scope_does_not_excuse_an_unscoped_builder_line(self):
        unscoped = "A Builder working to a Manager's brief opens its own pull request."
        self.assertEqual([unscoped], unmarked_builder_lines(unscoped))

    def test_another_seat_is_not_caught(self):
        """Only the Builder was narrowed. A Regulator opening its own is still correct."""
        other = "The Regulator pushes and opens its own pull request, unasked."
        self.assertEqual([], unmarked_builder_lines(other))


class TheRuleIsStatedOnce(unittest.TestCase):
    def test_no_file_tells_a_builder_to_open_its_own_pull_request(self):
        offenders = {}
        for relpath in CORPUS:
            hits = unmarked_builder_lines(t.read(t.REPO_ROOT / relpath), relpath)
            if hits:
                offenders[relpath] = hits
        self.assertEqual(
            {},
            offenders,
            "The Manager opens the pull request for its subagent Builders (owner ruling "
            "2026-09-18, narrowed 2026-09-24). These lines instruct a Builder to open its own, "
            "with no retirement marker and no own-session scope on the line. Either mark the line "
            "as retired text or repoint it: " + repr(offenders),
        )

    def test_the_replacement_rule_is_actually_written_somewhere(self):
        """A corpus scrubbed of the old rule and never given the new one passes the test above.

        This is the other half: the sweep must have LEFT something, not just removed something.
        """
        carriers = [
            f for f in CORPUS
            if re.search(r"manager\b[^.\n]{0,80}open", t.read(t.REPO_ROOT / f), re.IGNORECASE)
        ]
        self.assertGreaterEqual(
            len(carriers),
            5,
            f"only {len(carriers)} file(s) state that the Manager opens the pull request; the rule "
            "lives in more places than that and a sweep that removed the old wording without "
            "leaving the new one reads identically to a correct one",
        )


if __name__ == "__main__":
    unittest.main()
