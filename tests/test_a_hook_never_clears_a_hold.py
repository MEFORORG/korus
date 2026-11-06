"""No usage page says a seat's own hook clears a HOLD.

THE FAILURE THIS EXISTS FOR. `roles/COMMON.md`, *The three usage states*, says the section wins
over `watch.py` and that hook silence inside a state is not an all-clear. The 2026-11-05 lift
correction then said, in COMMON.md and again in `fleet-read-usage/SKILL.md`, that "your own hook
clears HOLD". A seat reading that could lift a weekly HOLD NEW WORK because its hook stopped
printing it, which is the reading the section forbids. Both sentences now send the reader to the
section's own clearing conditions.

WHAT IS MATCHED. One clause at a time, after the lines of a paragraph are rejoined: a clause that
names a hook (or `watch.py`), a clearing verb and a hold, in any order, is a claim. A table cell is
its own clause. Order-free on purpose: "After your hook goes quiet, the HOLD is lifted" puts the
hook first as a condition, and an ordered pattern missed it.

WHAT EXEMPTS A CLAUSE is a negation that governs the hook or the verb: one within four words before
the hook ("not on hook silence", "Do not assume your hook ..."), or right before the verb ("does
not clear"). A negation elsewhere in the clause does not, so "not on a relayed LIFT, but on hook
silence" still fires. The limit is known: "Not the Steward but your hook clears HOLD" is exempt.

THE POSITIVE CONTROL is both retired sentences, verbatim, plus regression wordings in each word
order. The negative control is the replacement wording, the section's own all-clear sentence and
two prohibitions, so a check that fired on every mention of a hook would go red here rather than
pass.

Run: cd tests && python -m unittest test_a_hook_never_clears_a_hold -v
"""

from __future__ import annotations

import re
import unittest

import _ccxtest as t

PAGES = (
    t.REPO_ROOT / "roles" / "COMMON.md",
    t.REPO_ROOT / ".claude" / "skills" / "fleet-read-usage" / "SKILL.md",
)

# What each page now says in place of the retired sentence. Pinned so the scan is shown to reach
# the corrected paragraph: deleting the note would otherwise leave this file green.
REPLACEMENT = "says, not on hook silence."

SUBJECT = re.compile(r"\b(?:hooks?|watch\.py)\b", re.I)
VERB = re.compile(
    r"\b(?:clear|clears|cleared|clearing|lift|lifts|lifted|lifting|release|releases|released"
    r"|releasing|end|ends|ended|ending|resume|resumes|resumed|drop|drops|dropped|lapse|lapses"
    r"|lapsed)\b",
    re.I,
)
# Singular only: "holds" is far more often the verb ("the file this directory holds") than a plural.
HOLD = re.compile(r"\bhold\b", re.I)
NEGATION = re.compile(r"\b(?:not|never|cannot|no|nor)\b|n't\b", re.I)

# A clause ends at a sentence stop followed by space, or at a table cell boundary. `watch.py` keeps
# its dot because no space follows it; "e.g." and "i.e." are not stops.
CLAUSE_BREAK = re.compile(r"(?<!\be\.g)(?<!\bi\.e)[.;!?](?=\s|$)|\|")

NEGATION_REACH = 4


def _negated_before(clause: str, at: int, words: int) -> bool:
    """A negation among the `words` words that end at offset `at`."""
    return bool(NEGATION.search(" ".join(clause[:at].split()[-words:])))


def _is_claim(clause: str) -> bool:
    if not (SUBJECT.search(clause) and HOLD.search(clause)):
        return False
    verbs = list(VERB.finditer(clause))
    if not verbs:
        return False
    if any(
        _negated_before(clause, m.start(), NEGATION_REACH)
        for m in SUBJECT.finditer(clause)
    ):
        return False
    return not all(_negated_before(clause, m.start(), 2) for m in verbs)


def claims_in(text: str) -> list[str]:
    """Every clause in `text` that says a hook clears a hold."""
    found = []
    for paragraph in re.split(r"\n\s*\n", text):
        for clause in CLAUSE_BREAK.split(" ".join(paragraph.split())):
            if _is_claim(clause):
                found.append(clause.strip())
    return found


RETIRED_SENTENCES = (
    "Your own hook clears HOLD as *The three usage states* says.",
    "Your own hook clears HOLD as COMMON says.",
)

REGRESSIONS = (
    "Once your hook stops printing it, the hook has cleared the HOLD.",
    "A weekly HOLD is lifted when your hook goes quiet.",
    "`watch.py` releases the hold for you.",
    "HOLD clears on hook silence.",
    "After your hook goes quiet, the HOLD is lifted.",
    "A HOLD the hook no longer prints is cleared.",
    "Your own hook prints HOLD and clears it.",
    "HOLD, once your hook is quiet, clears.",
    "Your hook's silence ends the HOLD.",
    "Resume once your hook stops printing HOLD.",
    "HOLD clears as COMMON says, not on a relayed LIFT, but on hook silence.",
    "Your own hook, and not a relayed LIFT, clears HOLD.",
    "The hook, e.g. on SessionStart, clears HOLD.",
)

NOT_CLAIMS = (
    "HOLD clears as *The three usage states* says, not on hook silence.",
    "HOLD clears as [COMMON.md](../../../roles/COMMON.md), *The three usage states*, says, not on "
    "hook silence.",
    "Hook silence inside a state here is not an all-clear.",
    "The hook does not clear HOLD.",
    "Do not assume your hook clears HOLD.",
    "Never treat the hook as clearing HOLD.",
    "The Stop hook clears the inbox this directory holds.",
)


class TheCheckCanFire(unittest.TestCase):
    def test_both_retired_sentences_fire(self):
        for sentence in RETIRED_SENTENCES:
            with self.subTest(sentence=sentence):
                self.assertEqual(1, len(claims_in(sentence)))

    def test_a_retired_sentence_fires_inside_a_table_cell_and_across_a_wrap(self):
        row = "| **CORRECTED 2026-11-05** | That seat was the Steward. Your own hook clears HOLD as COMMON says. |"
        self.assertEqual(["Your own hook clears HOLD as COMMON says"], claims_in(row))
        wrapped = "route it with the OPEN item above. Your own hook\nclears HOLD as *The three usage states* says."
        self.assertEqual(1, len(claims_in(wrapped)))

    def test_regression_wordings_fire(self):
        for sentence in REGRESSIONS:
            with self.subTest(sentence=sentence):
                self.assertEqual(1, len(claims_in(sentence)))

    def test_wording_that_denies_the_claim_does_not_fire(self):
        for sentence in NOT_CLAIMS:
            with self.subTest(sentence=sentence):
                self.assertEqual([], claims_in(sentence))


class NoUsagePageSaysTheHookClearsAHold(unittest.TestCase):
    def test_no_page_says_it(self):
        for page in PAGES:
            with self.subTest(page=page.name):
                self.assertEqual(
                    [],
                    claims_in(t.read(page)),
                    f"{page} says a hook clears a HOLD. COMMON.md, *The three usage states*, says "
                    "the section wins over the hook and hook silence is not an all-clear. Point at "
                    "that section's clearing conditions instead.",
                )

    def test_each_page_still_carries_the_correction(self):
        for page in PAGES:
            with self.subTest(page=page.name):
                self.assertIn(
                    REPLACEMENT,
                    " ".join(t.read(page).split()),
                    f"{page}: the corrected sentence ending {REPLACEMENT!r} is gone. Either the "
                    "note was reshaped or deleted, and a scan that no longer reaches it proves "
                    "nothing about it.",
                )


if __name__ == "__main__":
    unittest.main()
