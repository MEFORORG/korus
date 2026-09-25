"""No live page may name korus by its old `wshallwshall` owner without its current slug.

THE FAILURE THIS EXISTS FOR. This repository moved from `wshallwshall` to `MEFORORG`. Measured
2026-09-24 at `9c26644`: 17 files still named the old slug, among them both quickstarts' `git clone`
line, the site's `repo_url` and the nav's source link. Every one of them still worked.

A REDIRECT IS WHY NOTHING NOTICED. `gh repo view` on the old slug returns `MEFORORG/korus` and exits
0, and `git clone` follows the redirect too. A reader copying the command sees success, so nothing
reports the drift until the old owner name is reused and the redirect stops.

THE SIBLING OF `test_no_live_page_names_the_vault_by_its_old_owner.py`, and it keeps that file's
block rule on purpose. A block that names the current slug, or is followed at once by a block that
does, records the move rather than routing work to it. A table yields one block per row, so one
current slug in a long table cannot excuse every stale row in it.

THE CORPUS is every tracked text file outside `roles/retired/` and the frozen `.old.md` archives.
Retired seats record what they did. Each archive is sha256-pinned in `docs/_data/page-revisions.json`
and cannot be edited, so a hit there is a hit nobody may fix. The archive exclusion is itself checked
against that manifest, so it cannot quietly widen. This file spells the old slug in two halves so it
never matches itself.

BOTH ARMS RUN. A real quickstart with its clone URL reverted must trip, a planted retraction must
not, and the scan must find the current slug on the pages it names, so a zero is a reading rather
than a blind scan.

Run: python -m pytest tests/test_no_live_page_names_korus_by_its_old_owner.py
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest

import _ccxtest as t

# Split so this file's own source never carries the stale slug whole.
STALE = "wshallwshall" + "/korus"
CURRENT = "MEFORORG/korus"

NOT_LIVE = ("roles/retired/",)

MANIFEST = t.REPO_ROOT / "docs" / "_data" / "page-revisions.json"


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=t.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def pinned_archives() -> set[str]:
    """The `.old.md` files whose bytes the manifest pins, as repo-relative paths."""
    pages = json.loads(MANIFEST.read_text(encoding="utf-8"))["pages"]
    return {"docs/" + entry["archive"] for entry in pages}


def live(path: str, frozen: set[str]) -> bool:
    return not path.startswith(NOT_LIVE) and path not in frozen


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


def read_live_pages(frozen: set[str]) -> dict[str, str]:
    pages = {}
    for path in tracked_files():
        if not live(path, frozen):
            continue
        try:
            pages[path] = (t.REPO_ROOT / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return pages


class NoLivePageNamesKorusByItsOldOwner(unittest.TestCase):
    def setUp(self):
        self.frozen = pinned_archives()
        self.pages = read_live_pages(self.frozen)

    def test_the_scan_reads_the_front_door_pages_and_finds_the_current_slug(self):
        """The coverage floor. A scan that read nothing would also report zero offences."""
        for path in ("docs/QUICKSTART.md", "docs/_config.yml", "docs/_data/nav.yml"):
            self.assertIn(path, self.pages, f"{path} is not in the corpus -- the filter is wrong")
            self.assertIn(CURRENT, self.pages[path], f"{path} no longer names `{CURRENT}`")

    def test_only_pinned_archives_are_excused(self):
        """The `.old.md` exclusion is read off the manifest, so it cannot grow past it."""
        archives = {p for p in tracked_files() if p.endswith(".old.md")}
        self.assertEqual(50, len(self.frozen), "the manifest no longer pins 50 archives")
        self.assertEqual(
            set(),
            archives - self.frozen,
            "an `.old.md` file is tracked but not pinned, so it is live and must be scanned",
        )
        self.assertTrue(
            archives & self.frozen,
            "no tracked archive matched the manifest -- the path join is wrong, and the "
            "exclusion excuses nothing while looking like it excuses fifty files",
        )

    def test_no_live_page_names_the_old_slug_alone(self):
        found = offences(self.pages)
        self.assertEqual(
            [],
            found,
            f"a live page names `{STALE}`, which answers only through a redirect. Name "
            f"`{CURRENT}` instead, or keep the history and name the current slug in the same "
            "paragraph or table row, or the block right after it:\n"
            + "\n".join(f"  {p}\n    | {b}" for p, b in found),
        )

    def test_a_planted_stale_clone_url_trips_and_a_planted_retraction_does_not(self):
        """Both arms, planted into a copy of a real page rather than an invented one."""
        real = self.pages["docs/QUICKSTART.md"]
        clone = f"git clone https://github.com/{CURRENT}.git"
        self.assertIn(clone, real, "the plant site moved -- QUICKSTART.md no longer has the clone")

        stale_copy = real.replace(CURRENT, STALE, 1)
        self.assertTrue(
            offences({"docs/QUICKSTART.md": stale_copy}),
            "MUST-TRIP arm: the real QUICKSTART.md with its clone URL reverted was not caught",
        )

        retraction = f"korus was `{STALE}` until it moved.\nIt is now `{CURRENT}`."
        self.assertEqual(
            [],
            offences({"planted.md": retraction}),
            "MUST-NOT-TRIP arm: a wrapped retraction naming both slugs was reported as a defect",
        )

    def test_a_pinned_archive_hit_is_excused_and_a_live_one_is_not(self):
        """The exclusion is by path. The same text in a live page must still trip."""
        archive = sorted(self.frozen)[0]
        self.assertFalse(live(archive, self.frozen), f"{archive} is pinned but read as live")
        self.assertTrue(live("docs/QUICKSTART.md", self.frozen), "a live page read as frozen")

    def test_a_current_slug_in_an_earlier_row_does_not_excuse_a_later_one(self):
        table = f"| A | uses `{CURRENT}` |\n| B | ok |\n| C | uses `{STALE}` |"
        self.assertEqual(
            1,
            len(offences({"planted.md": table})),
            "a table was read as one block, so one row's current slug excused another row",
        )


if __name__ == "__main__":
    unittest.main()
