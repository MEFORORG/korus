"""No live page may name the vault by its old `wshallwshall` owner without its current slug.

THE FAILURE THIS EXISTS FOR. The vault moved from `wshallwshall` to `MEFORORG`. Two live playbooks,
`roles/LANDER.md` and `roles/MANAGER.md`, went on naming the old slug while `roles/BUILDER.md` named
the new one. So the playbooks disagreed, and the old slug still answered through a redirect.

A REDIRECT IS WHY NOTHING NOTICED. `gh repo view` on the old slug returns the new pair and exits 0,
so a seat using the stale name sees success. `MANAGER.md` warns about exactly this hazard, and it
carried the stale slug in the same row. Measured 2026-09-24: `gh repo view` on the old slug returns
`MEFORORG/MessageFoundry-vault`.

RETRACTION IN PLACE IS ALLOWED. A block that names the current slug, or is followed at once by a
block that does, records a rename rather than routing work to it. That is the repository's
retired-text convention: keep the old text, and put the dated correction beside it or under it.

THE BLOCK IS A PARAGRAPH, OR ONE TABLE ROW. Prose wraps, so a line test cannot see a correction on
the next line. A table is one paragraph, so treating it whole would let one current slug anywhere in
a twenty-row table excuse every stale row in it. Only the NEXT block counts as the correction.

THE CORPUS is every tracked text file outside `roles/retired/`, which records what a retired seat
did and is not live. This file spells the old slug in two halves so it never matches itself.

BOTH ARMS RUN. A planted stale mention must trip, a planted retraction must not, and the scan must
find the current slug somewhere, so a zero is a reading rather than a blind scan.

Run: python -m pytest tests/test_no_live_page_names_the_vault_by_its_old_owner.py
"""

from __future__ import annotations

import re
import subprocess
import unittest

import _ccxtest as t

# Split so this file's own source never carries the stale slug whole.
STALE = "wshallwshall" + "/MessageFoundry-vault"
CURRENT = "MEFORORG/MessageFoundry-vault"

NOT_LIVE = ("roles/retired/",)


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=t.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def live(path: str) -> bool:
    return not path.startswith(NOT_LIVE)


def blocks(raw: str) -> list[str]:
    """Paragraphs, except that a table yields one block per row."""
    out = []
    for para in re.split(r"\n\s*\n", raw):
        if not para.strip():
            continue
        lines = para.splitlines()
        if all(line.lstrip().startswith("|") for line in lines):
            out.extend(lines)
        else:
            out.append(para)
    return out


def offences(pages: dict[str, str]) -> list[tuple[str, str]]:
    """Every block that names the stale slug, with the current one neither in it nor right after."""
    found = []
    for path, raw in pages.items():
        page = blocks(raw)
        for i, block in enumerate(page):
            if STALE not in block or CURRENT in block:
                continue
            if i + 1 < len(page) and CURRENT in page[i + 1]:
                continue
            found.append((path, " ".join(block.split())[:160]))
    return found


def read_live_pages() -> dict[str, str]:
    pages = {}
    for path in tracked_files():
        if not live(path):
            continue
        try:
            pages[path] = (t.REPO_ROOT / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return pages


class NoLivePageNamesTheVaultByItsOldOwner(unittest.TestCase):
    def setUp(self):
        self.pages = read_live_pages()

    def test_the_scan_reads_the_playbooks_and_finds_the_current_slug(self):
        """The coverage floor. A scan that read nothing would also report zero offences."""
        for path in ("roles/BUILDER.md", "roles/LANDER.md", "roles/MANAGER.md"):
            self.assertIn(path, self.pages, f"{path} is not in the corpus -- the filter is wrong")
        holders = [p for p, raw in self.pages.items() if CURRENT in raw]
        self.assertTrue(
            holders,
            f"no live page names `{CURRENT}`, so the scan cannot tell a clean tree from a blind one",
        )

    def test_no_live_page_names_the_old_slug_alone(self):
        found = offences(self.pages)
        self.assertEqual(
            [],
            found,
            f"a live page names `{STALE}`, which answers only through a redirect. Name "
            f"`{CURRENT}` instead, or keep the history and name the current slug in the same "
            "paragraph or table row:\n" + "\n".join(f"  {p}\n    | {b}" for p, b in found),
        )

    def test_a_planted_stale_mention_trips_and_a_planted_retraction_does_not(self):
        """Both arms, planted into a copy of a real playbook rather than an invented one."""
        real = self.pages["roles/LANDER.md"]
        self.assertIn(CURRENT, real, "the plant site moved -- LANDER.md no longer names the vault")

        stale_copy = real.replace(CURRENT, STALE, 1)
        self.assertTrue(
            offences({"roles/LANDER.md": stale_copy}),
            "MUST-TRIP arm: the real LANDER.md with its vault slug reverted was not caught",
        )

        retraction = f"The vault was `{STALE}` until it moved.\nIt is now `{CURRENT}`."
        self.assertEqual(
            [],
            offences({"planted.md": retraction}),
            "MUST-NOT-TRIP arm: a wrapped retraction naming both slugs was reported as a defect",
        )

    def test_a_current_slug_in_an_earlier_row_does_not_excuse_a_later_one(self):
        table = f"| A | uses `{CURRENT}` |\n| B | ok |\n| C | uses `{STALE}` |"
        self.assertEqual(
            1,
            len(offences({"planted.md": table})),
            "a table was read as one block, so one row's current slug excused another row",
        )

    def test_a_correction_in_the_next_row_excuses_the_row_above(self):
        """The shape `roles/MANAGER.md` uses: the old row kept, the dated correction under it."""
        table = (
            f"| So | the vault was renamed to `{STALE}` |\n"
            f"| CORRECTED 2026-09-24 | the vault is `{CURRENT}` |"
        )
        self.assertEqual(
            [],
            offences({"planted.md": table}),
            "a stale row with its correction in the next row was reported as a defect",
        )


if __name__ == "__main__":
    unittest.main()
