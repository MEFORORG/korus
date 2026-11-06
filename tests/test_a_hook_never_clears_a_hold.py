"""No usage page says a seat's own hook clears a HOLD.

THE FAILURE THIS EXISTS FOR. `roles/COMMON.md`, *The three usage states*, says the section wins
over `watch.py` and that hook silence inside a state is not an all-clear. The 2026-11-05 lift
correction then said, in COMMON.md and again in `fleet-read-usage/SKILL.md`, that "your own hook
clears HOLD". A seat reading that could lift a weekly HOLD NEW WORK because its hook stopped
printing it, which is the reading the section forbids. Both sentences now send the reader to the
section's own clearing conditions.

WHAT IS MATCHED. One clause at a time, after the lines of a paragraph are rejoined: a hook (or
`watch.py`), a clearing verb and a hold, in either order. A match that holds a negation is not a
claim, so "not on hook silence" passes. A table cell is its own clause.

THE POSITIVE CONTROL is both retired sentences, verbatim, plus four regression wordings. The
negative control is the replacement wording and the section's own all-clear sentence, so a check
that fired on every mention of a hook would go red here rather than pass.

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

_SUBJECT = r"\b(?:hooks?|watch\.py)\b"
_VERB = r"\b(?:clears?|cleared|clearing|lifts?|lifted|lifting|releases?|released|releasing)\b"
_HOLD = r"\bholds?\b"

CLAIMS = (
    re.compile(_SUBJECT + r".*?" + _VERB + r".*?" + _HOLD, re.I),
    re.compile(_HOLD + r".*?" + _VERB + r".*?" + _SUBJECT, re.I),
)
NEGATION = re.compile(r"\b(?:not|never|cannot|no|nor)\b|n't\b", re.I)

# A clause ends at a sentence stop followed by space, or at a table cell boundary. `watch.py` keeps
# its dot because no space follows it.
CLAUSE_BREAK = re.compile(r"[.;!?](?=\s|$)|\|")


def claims_in(text: str) -> list[str]:
    """Every clause in `text` that says a hook clears a hold."""
    found = []
    for paragraph in re.split(r"\n\s*\n", text):
        for line in (
            paragraph.splitlines()
            if paragraph.lstrip().startswith("|")
            else [paragraph]
        ):
            flat = " ".join(line.split())
            for clause in CLAUSE_BREAK.split(flat):
                # Every start position, not only the leftmost: a negated match early in a clause
                # must not hide a plain claim later in it.
                spans = (
                    m.group(1)
                    for pattern in CLAIMS
                    for m in re.finditer(f"(?=({pattern.pattern}))", clause, re.I)
                )
                if any(not NEGATION.search(span) for span in spans):
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
)

NOT_CLAIMS = (
    "HOLD clears as *The three usage states* says, not on hook silence.",
    "HOLD clears as [COMMON.md](../../../roles/COMMON.md), *The three usage states*, says, not on "
    "hook silence.",
    "Hook silence inside a state here is not an all-clear.",
    "The hook does not clear HOLD.",
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
                text = t.read(page)
                self.assertRegex(
                    text,
                    r"\bHOLD\b",
                    f"{page}: no HOLD at all. The page moved or was reshaped, and a scan of a page "
                    "that never discusses a hold proves nothing.",
                )
                self.assertEqual(
                    [],
                    claims_in(text),
                    f"{page} says a hook clears a HOLD. COMMON.md, *The three usage states*, says "
                    "the section wins over the hook and hook silence is not an all-clear. Point at "
                    "that section's clearing conditions instead.",
                )


if __name__ == "__main__":
    unittest.main()
