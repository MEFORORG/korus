"""No usage page says a seat's own hook clears a HOLD.

THE FAILURE THIS EXISTS FOR. `roles/COMMON.md`, *The three usage states*, says the section wins
over `watch.py` and that hook silence inside a state is not an all-clear. The 2026-11-05 lift
correction then said, in COMMON.md and again in `fleet-read-usage/SKILL.md`, that "your own hook
clears HOLD". A seat reading that could lift a weekly HOLD NEW WORK because its hook stopped
printing it, which is the reading the section forbids. Both sentences now send the reader to the
section's own clearing conditions.

WHAT IS MATCHED. One clause at a time, after the lines of a paragraph are rejoined; a table row is
one unit, so a row naming HOLD in its first cell and the hook in its second is read whole. A clause
that names a hook (or `watch.py`), a clearing or starting verb and a hold, in any order, is a
claim.

WHAT EXEMPTS A CLAUSE is a negation that governs every hook it names, within five words before each
("not on hook silence", "Never assume that your own hook ..."), or one right before every verb
("does not clear"). A contrast word -- but, only, until, unless -- turns both exemptions off,
because "not by a relay but by your hook" asserts the claim.

THIS IS A MATCHER, SO IT MISSES WORDINGS. It catches at least the retired sentences and the
regressions listed below, and it is no proof that a page is free of the claim. Two cases hold the
line where a matcher cannot: each page must carry its corrected sentence exactly, and each page,
with that sentence turned back into the retired one, must fire.

Run: cd tests && python -m unittest test_a_hook_never_clears_a_hold -v
"""

from __future__ import annotations

import re
import unittest

import _ccxtest as t

COMMON = t.REPO_ROOT / "roles" / "COMMON.md"
SKILL = t.REPO_ROOT / ".claude" / "skills" / "fleet-read-usage" / "SKILL.md"

# Each page's corrected sentence, exactly as written (COMMON's wraps), and the sentence it replaced.
CORRECTIONS = {
    COMMON: (
        "HOLD clears as *The three usage states* says, not on hook\nsilence.",
        "Your own hook clears HOLD as *The three usage states* says.",
    ),
    SKILL: (
        "HOLD clears as [COMMON.md](../../../roles/COMMON.md), *The three usage states*, says, "
        "not on hook silence.",
        "Your own hook clears HOLD as COMMON says.",
    ),
}

SUBJECT = re.compile(r"\b(?:hooks?|watch\.py)\b", re.I)
VERB = re.compile(
    r"\b(?:clear|clears|cleared|clearing|lift|lifts|lifted|lifting|release|releases|released"
    r"|releasing|end|ends|ended|ending|resume|resumes|resumed|start|starts|started|drop|drops"
    r"|dropped|lapse|lapses|lapsed)\b",
    re.I,
)
# "LIFT" in capitals is the noun these pages use for a relayed lift, not the verb.
NOUN_VERBS = {"LIFT", "LIFTS"}
# Singular only: "holds" is far more often the verb ("the file this directory holds") than a plural.
HOLD = re.compile(r"\bhold\b", re.I)
NEGATION = re.compile(r"\b(?:not|never|cannot|no|nor)\b|n't\b", re.I)
CONTRAST = re.compile(r"\b(?:but|only|until|unless)\b", re.I)

# A clause ends at a sentence stop, after any closing emphasis or bracket, followed by space. A
# colon counts too. `watch.py` keeps its dot because no space follows it; "e.g." and "i.e." are not
# stops.
CLAUSE_BREAK = re.compile(r"(?<!\be\.g)(?<!\bi\.e)[.;:!?][*_)\]`]*(?=\s|$)", re.I)

NEGATION_REACH = 5


def _negated_before(clause: str, at: int, words: int) -> bool:
    """A negation among the `words` words that end at offset `at`."""
    return bool(NEGATION.search(" ".join(clause[:at].split()[-words:])))


def _is_claim(clause: str) -> bool:
    subjects = list(SUBJECT.finditer(clause))
    verbs = [m for m in VERB.finditer(clause) if m.group(0) not in NOUN_VERBS]
    if not (subjects and verbs and HOLD.search(clause)):
        return False
    if CONTRAST.search(clause):
        return True
    if all(_negated_before(clause, m.start(), NEGATION_REACH) for m in subjects):
        return False
    return not all(_negated_before(clause, m.start(), 2) for m in verbs)


def _units(text: str) -> list[str]:
    """Prose paragraphs rejoined, and table rows one per unit."""
    units = []
    for paragraph in re.split(r"\n\s*\n", text):
        lines = paragraph.strip().splitlines()
        if lines and all(line.lstrip().startswith("|") for line in lines):
            units.extend(line.replace("|", " ") for line in lines)
        else:
            units.append(paragraph)
    return [" ".join(unit.split()) for unit in units]


def claims_in(text: str) -> list[str]:
    """Every clause in `text` that says a hook clears a hold."""
    return [
        clause.strip()
        for unit in _units(text)
        for clause in CLAUSE_BREAK.split(unit)
        if _is_claim(clause)
    ]


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
    "Start new work once your hook stops printing HOLD.",
    "HOLD clears as COMMON says, not on a relayed LIFT, but on hook silence.",
    "Your own hook, and not a relayed LIFT, clears HOLD.",
    "The hook, e.g. on SessionStart, clears HOLD.",
    "The hook, E.g. on SessionStart, clears HOLD.",
    "HOLD is not cleared by a relay but by your own hook.",
    "A HOLD is never cleared by a relayed LIFT, only by your hook.",
    "HOLD does not lift until your hook stops printing it.",
    "Your own hook clears HOLD as COMMON says, not on hook silence.",
    "Not the Steward: your hook clears HOLD.",
    "**There is no relay.** Your hook clears HOLD.",
    "| HOLD NEW WORK | Clears when your hook stops printing it. |",
    "| Under a hold | Your hook clears it once it goes quiet. |",
)

NOT_CLAIMS = (
    "HOLD clears as *The three usage states* says, not on hook silence.",
    "Hook silence inside a state here is not an all-clear.",
    "The hook does not clear HOLD.",
    "Do not assume your hook clears HOLD.",
    "Never assume that your own hook clears a HOLD.",
    "Never treat the hook as clearing HOLD.",
    "The Stop hook clears the inbox this directory holds.",
)


class TheCheckCanFire(unittest.TestCase):
    def test_both_retired_sentences_fire(self):
        for _, retired in CORRECTIONS.values():
            with self.subTest(sentence=retired):
                self.assertEqual(1, len(claims_in(retired)))

    def test_a_retired_sentence_fires_inside_a_table_row_and_across_a_wrap(self):
        row = (
            "| **CORRECTED 2026-11-05** | That seat was the Steward. Your own hook clears HOLD as "
            "COMMON says. |"
        )
        self.assertEqual(["Your own hook clears HOLD as COMMON says"], claims_in(row))
        wrapped = (
            "route it with the OPEN item above. Your own hook\n"
            "clears HOLD as *The three usage states* says."
        )
        self.assertEqual(1, len(claims_in(wrapped)))

    def test_regression_wordings_fire(self):
        for sentence in REGRESSIONS:
            with self.subTest(sentence=sentence):
                self.assertEqual(1, len(claims_in(sentence)))

    def test_wording_that_denies_the_claim_does_not_fire(self):
        for sentence in NOT_CLAIMS + tuple(new for new, _ in CORRECTIONS.values()):
            with self.subTest(sentence=sentence):
                self.assertEqual([], claims_in(sentence))


class NoUsagePageSaysTheHookClearsAHold(unittest.TestCase):
    def test_no_page_says_it(self):
        for page in CORRECTIONS:
            with self.subTest(page=page.name):
                self.assertEqual(
                    [],
                    claims_in(t.read(page)),
                    f"{page} says a hook clears a HOLD. COMMON.md, *The three usage states*, says "
                    "the section wins over the hook and hook silence is not an all-clear. Point at "
                    "that section's clearing conditions instead.",
                )

    def test_each_page_carries_its_correction(self):
        for page, (new, _) in CORRECTIONS.items():
            with self.subTest(page=page.name):
                self.assertIn(
                    new,
                    t.read(page),
                    f"{page}: the corrected sentence {new!r} is gone or reworded. Update "
                    "CORRECTIONS to the new wording, or a scan that no longer reaches it proves "
                    "nothing about it.",
                )

    def test_each_page_fires_with_its_retired_sentence_put_back(self):
        """The page itself as the positive control: a page quirk that hid the claim would show."""
        for page, (new, retired) in CORRECTIONS.items():
            with self.subTest(page=page.name):
                text = t.read(page)
                if new not in text:
                    self.skipTest(
                        "test_each_page_carries_its_correction reports the missing sentence"
                    )
                self.assertEqual(1, len(claims_in(text.replace(new, retired))))


if __name__ == "__main__":
    unittest.main()
