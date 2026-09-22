"""The QA line a Builder writes must never carry the word "review".

THE FAILURE THIS EXISTS FOR. Owner ruling 2026-09-20 added a `qa` label and a QA line that records
that `BUILDER.md` step 11 ran. Neither may use the word "review". The reason is the label that
retired on 2026-09-04: `reviewed` recorded that a step had happened, any seat could apply it to its
own pull request, and readers took it for a verdict on the diff. `CLAUDE.md` keeps that history
under *RETIRED 2026-09-04: there is no review gate here*.

The rule was stated in four files and enforced by none of them. That is the shape Article V
forbids, and it is the one this file closes: the documents asserting the rule were the only
evidence the rule held, and prose does not stay true on its own.

WHAT THIS DOES NOT COVER, because it cannot be read from the tree. The `qa` label's own name and
description live on GitHub. Read them with `gh label list`, not with pytest.

MEASURED on the branch that introduces it: three template blocks carry the marker line, across
`roles/BUILDER.md`, `docs/roles/builder.card.md` and `docs/KORUS-BUILD.md`, and none of the three
contains the word. `test_the_control_fires` plants the word in a copy of every real block and
requires each one to be caught, so that zero is a reading rather than an empty corpus.
"""

from __future__ import annotations

import re
import unittest

import _ccxtest as t

# The first line of the QA line, in every file that carries a copy of it. `BUILDER.md` 4e is the
# authority on the shape; the other two carry the same three lines for a reader who never opens it.
MARKER = "QA -- korus roles/BUILDER.md step 11"

# The line plus the two under it: Level and Tag, then Rounds and Findings.
BLOCK_LINES = 3

# The second line of the block, which is the one whose premise failed on 2026-09-22. All three
# carriers must spell it identically; `roles/BUILDER.md` 4e is the authority.
FIELD_LINE_INDEX = 1

# Files required to carry at least one block. A file dropping its copy is a silent loss of the
# rule from the place a seat actually reads, so absence fails rather than passing vacuously.
CARRIERS = (
    "roles/BUILDER.md",
    "docs/roles/builder.card.md",
    "docs/KORUS-BUILD.md",
)

BANNED = re.compile(r"review", re.IGNORECASE)


def _blocks(text: str) -> list[str]:
    """Every QA line in `text`, each as the marker line plus the two lines under it."""
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        if MARKER in line:
            found.append("\n".join(lines[i : i + BLOCK_LINES]))
    return found


def _offenders(block: str) -> list[str]:
    return BANNED.findall(block)


def _field_spellings(texts: dict[str, str]) -> dict[str, str]:
    """Line two of every QA block, mapped to the first carrier that spelled it that way."""
    seen: dict[str, str] = {}
    for relpath, text in texts.items():
        for block in _blocks(text):
            seen.setdefault(block.splitlines()[FIELD_LINE_INDEX].strip(), relpath)
    return seen


class TheQaLineNeverSaysReview(unittest.TestCase):
    def test_every_carrier_still_holds_a_block(self):
        """A dropped copy must fail. A scan over nothing is what Article V forbids."""
        for relpath in CARRIERS:
            with self.subTest(file=relpath):
                blocks = _blocks(t.read(t.REPO_ROOT / relpath))
                self.assertTrue(
                    blocks,
                    f"{relpath} carries no {MARKER!r} block. Either the QA line moved and this "
                    "list is stale, or a file quietly lost the rule. Fix the file or fix CARRIERS "
                    "-- do not delete the entry to get to green.",
                )

    def test_no_block_carries_the_banned_word(self):
        total = 0
        for relpath in CARRIERS:
            for block in _blocks(t.read(t.REPO_ROOT / relpath)):
                total += 1
                with self.subTest(file=relpath):
                    self.assertEqual(
                        [],
                        _offenders(block),
                        f"{relpath}: the QA line uses the word \"review\". Owner ruling "
                        "2026-09-20 forbids it in the label and the line. The line cites "
                        "`BUILDER.md step 11` instead, which names exactly one skill. See "
                        "`roles/BUILDER.md` 4e.",
                    )
        self.assertGreaterEqual(total, len(CARRIERS), "fewer blocks than carriers")

    def test_every_carrier_spells_the_field_line_the_same_way(self):
        """The three copies must agree on line two, and a planted divergence must be caught.

        THE FAILURE THIS EXISTS FOR. Until 2026-09-22 that line read `Tag: <the skill's own first
        line>`, on a premise that did not hold: the tag is the first line of the skill's PROMPT,
        not of its report. Four consecutive runs recorded the field as empty. `roles/BUILDER.md`
        4e carries the measurement.

        The rule was stated in three files and checked in none, so nothing could tell a repair
        that reached all three from one that reached only the playbook. This closes that.
        """
        texts = {relpath: t.read(t.REPO_ROOT / relpath) for relpath in CARRIERS}
        seen = _field_spellings(texts)
        self.assertEqual(
            1,
            len(seen),
            "the carriers disagree on line two of the QA line: "
            + "; ".join(f"{path} says {field!r}" for field, path in seen.items())
            + ". `roles/BUILDER.md` 4e is the authority -- bring the other copies to it.",
        )

        # The control. Change line two in ONE carrier and require the same check to catch it.
        # Without this, three identical carriers and a detector reading nothing both return 1.
        victim = CARRIERS[-1]
        spelling = next(iter(seen))
        planted = dict(texts)
        planted[victim] = texts[victim].replace(spelling, "Tag: whatever the skill said")
        self.assertNotEqual(planted[victim], texts[victim], "the plant changed nothing")
        self.assertGreater(
            len(_field_spellings(planted)),
            1,
            "the control was not caught, so the agreement above measures the detector rather "
            "than the corpus.",
        )

    def test_the_control_fires(self):
        """Plant the word in a copy of every real block. Every one must be caught.

        Without this, a detector that matched nothing and a corpus that was clean would return
        the same zero.
        """
        planted = 0
        for relpath in CARRIERS:
            for block in _blocks(t.read(t.REPO_ROOT / relpath)):
                control = block.replace(MARKER, "QA -- korus code-review at step 11")
                self.assertNotEqual(control, block, "the plant changed nothing")
                planted += 1
                with self.subTest(file=relpath):
                    self.assertTrue(
                        _offenders(control),
                        f"{relpath}: the control was not caught, so the zero above measures "
                        "the detector rather than the corpus.",
                    )
        self.assertGreaterEqual(planted, len(CARRIERS), "the control ran over fewer blocks")


if __name__ == "__main__":
    unittest.main()
