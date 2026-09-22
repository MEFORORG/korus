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

# The field lines, which are every line of the block after the marker. All three carriers must
# agree on the FIELD LABELS in them; `roles/BUILDER.md` 4e is the authority.
#
# BOTH LINES, NOT JUST THE ONE THAT BROKE. Line two is where the 2026-09-22 premise failed, and
# pinning only it would leave line three free to diverge -- which it already had, `(null path)` in
# the playbook against `(reason)` in the other two. That is the same gap in one line down.
FIELD_LINES = slice(1, BLOCK_LINES)

# LABELS, NOT VALUES, and the difference is what keeps this check honest. Pinning the whole line
# pins the sample values too -- `xhigh`, `2`, the rejection reason -- so 4e's own second Level
# spelling, `inherited, not passed`, could not be written as a worked example anywhere in the
# three carriers without reddening this file. The drift it exists to catch is in the NAMES: a copy
# still headed `Tag:` where the authority now says `Level:`. Values are free to differ, and the
# authority is free to carry a real rejection reason where a card carries a placeholder.
FIELD_LABEL = re.compile(r"(?:^|(?<=[.] ))([A-Z][A-Za-z]*):")

# Files required to carry at least one block. A file dropping its copy is a silent loss of the
# rule from the place a seat actually reads, so absence fails rather than passing vacuously.
CARRIERS = (
    "roles/BUILDER.md",
    "docs/roles/builder.card.md",
    "docs/KORUS-BUILD.md",
)

BANNED = re.compile(r"review", re.IGNORECASE)


def _blocks(text: str) -> list[str]:
    """Every QA line in `text`, each as the marker line plus the two lines under it.

    A marker in the last two lines of a file yields a SHORT slice. It is returned as it stands
    rather than padded or dropped: `test_every_carrier_still_holds_a_block` is the check that
    speaks to a truncated copy, and callers here must not raise before it gets the chance.
    """
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        if MARKER in line:
            found.append("\n".join(lines[i : i + BLOCK_LINES]))
    return found


def _offenders(block: str) -> list[str]:
    return BANNED.findall(block)


def _field_labels(texts: dict[str, str]) -> dict[str, str]:
    """Every block's field labels, mapped to the first carrier that used that sequence.

    A short block keys on what it has, so a truncated copy reads as a divergence rather than
    raising IndexError out of whichever test the runner happens to reach first.
    """
    seen: dict[str, str] = {}
    for relpath, text in texts.items():
        for block in _blocks(text):
            labels = []
            for line in block.splitlines()[FIELD_LINES]:
                labels.extend(FIELD_LABEL.findall(line.strip()))
            seen.setdefault(" ".join(labels), relpath)
    return seen


def _insert_at(text: str, offset: int, line: str) -> str:
    """Put `line` `offset` lines below the first marker, pushing the rest down."""
    lines = text.splitlines()
    for i, existing in enumerate(lines):
        if MARKER in existing:
            lines.insert(i + offset, line)
            return "\n".join(lines) + "\n"
    raise AssertionError("no block to plant in")


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

    def test_every_carrier_uses_the_same_field_labels(self):
        """The three copies must agree on the field labels, proven by three plants.

        THE FAILURE THIS EXISTS FOR. Until 2026-09-22 line two read `Tag: <the skill's own first
        line>`, on a premise that did not hold: the tag is the first line of the skill's PROMPT,
        not of its report. Both QA lines on `MEFORORG/MessageFoundry` 1419 recorded the field as
        empty. `roles/BUILDER.md` 4e carries the measurement.

        The rule was stated in three files and checked in none, so nothing could tell a repair
        that reached all three from one that reached only the playbook. This closes that.

        FOUR PLANTS, AND TWO OF THEM MUST NOT FIRE.

        A renamed label must be caught. A changed VALUE must not, or the check pins sample text
        and 4e's own second Level spelling could never be written as a worked example.

        The last two BRACKET THE WINDOW, and they are the same text one line apart: planted at
        the last line INSIDE `FIELD_LINES` it must fire, and at the first line OUTSIDE it must
        not. One line, opposite outcomes, so neither arm can be passing for a general reason.
        A reader that scanned whole files rather than the slice would fire on both.

        AN EARLIER ARM APPENDED THE PLANT AT END OF FILE, 128 lines past the nearest marker,
        where no window of any plausible width reaches. It passed at every width from 3 to 129
        and measured nothing.
        """
        texts = {relpath: t.read(t.REPO_ROOT / relpath) for relpath in CARRIERS}
        seen = _field_labels(texts)
        self.assertEqual(
            1,
            len(seen),
            "the carriers disagree on the QA line's field labels: "
            + "; ".join(f"{path} uses {labels!r}" for labels, path in seen.items())
            + ". `roles/BUILDER.md` 4e is the authority -- bring the other copies to it.",
        )

        victim = CARRIERS[-1]

        # 1. A RENAMED LABEL inside the block must be caught.
        renamed = dict(texts)
        renamed[victim] = texts[victim].replace("Tag: none returned", "Shape: none returned")
        self.assertNotEqual(renamed[victim], texts[victim], "the rename plant changed nothing")
        self.assertGreater(
            len(_field_labels(renamed)),
            1,
            "a renamed field label was not caught, so the agreement above measures the detector "
            "rather than the corpus.",
        )

        # 2. A CHANGED VALUE inside the block must NOT be caught, or the check pins sample text.
        revalued = dict(texts)
        revalued[victim] = texts[victim].replace(
            "Level: xhigh, from the brief.", "Level: inherited, not passed."
        )
        self.assertNotEqual(revalued[victim], texts[victim], "the value plant changed nothing")
        self.assertEqual(
            seen,
            _field_labels(revalued),
            "changing a sample VALUE moved the reading, so this check pins example text and 4e's "
            "own `inherited, not passed` spelling cannot be written as a worked example.",
        )

        # 3. The same new label at the LAST line inside the window must be caught.
        boundary = "Shape: planted at the window edge"
        last_inside = dict(texts)
        last_inside[victim] = _insert_at(texts[victim], FIELD_LINES.stop - 1, boundary)
        self.assertNotEqual(last_inside[victim], texts[victim], "the inside plant changed nothing")
        self.assertGreater(
            len(_field_labels(last_inside)),
            1,
            "a label on the LAST line of the window was not caught, so the window is narrower "
            "than FIELD_LINES claims and arm 4 below proves nothing.",
        )

        # 4. The same text one line further down must NOT be caught. That is the window edge.
        first_outside = dict(texts)
        first_outside[victim] = _insert_at(texts[victim], FIELD_LINES.stop, boundary)
        self.assertNotEqual(first_outside[victim], texts[victim], "the outside plant changed nothing")
        self.assertEqual(
            seen,
            _field_labels(first_outside),
            "a label on the first line BELOW the window moved the reading, so this check is not "
            "scoped to FIELD_LINES and its agreement above proves less than it claims.",
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
