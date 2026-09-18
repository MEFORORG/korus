#!/usr/bin/env python3
"""Which frozen archives cite this heading? Ask before you rename it, not after.

WHAT THE TRAP IS. Fifty `.old.md` archives under `docs/` are frozen prose. Thirty-eight anchored
links inside them point OUT, at headings on pages that are still edited every day. Rename one of
those headings and `tests/test_internal_links_resolve.py` goes red over a link in a file NOBODY IS
PERMITTED TO REPAIR.

BOTH ROUTES OUT ARE CLOSED, which is what makes it a trap rather than a chore. The link cannot be
edited: every archive is sha256-pinned in `docs/_data/page-revisions.json`, so touching one reds
`tests/test_page_revisions.py` instead. Deleting the link is the same edit. The rename is what has
to be undone.

WHY A SEPARATE INSTRUMENT, when the link test already reddens. The link test answers "a link is
broken" once the suite runs, and its message reads like every other broken link -- go and fix it.
That advice is wrong here, and whoever follows it earns a second red from the other direction. This
script answers the question one step earlier, while the cheap option is still on the table: is this
heading load-bearing for a file I may not open?

IT IS THE HALF `HS-13` NEVER HAD. That rule says a heading must not be renamed until the repository
has been searched for its text. It does not say that some of what the search returns cannot be
repaired.

    python scripts/quality/frozen_citations.py
    python scripts/quality/frozen_citations.py docs/LIMITS.md
    python scripts/quality/frozen_citations.py docs/LIMITS.md "What actually switches each control on"
    python scripts/quality/frozen_citations.py --strict

Exit 0  no frozen archive cites the heading you named, so the rename is yours to decide.
Exit 1  one does. Read what is printed: "fix the link" is not among the options.
Exit 2  nothing was read. The registry is missing or empty, it names archives that are not in the
        tree, or the page you named is not a file. NOTHING WAS PROVEN EITHER WAY, which is a
        failure and never a quiet pass -- a mistyped page is how this tool would otherwise bless
        exactly the rename it exists to stop.

`--strict` turns the inventory form into a gate: exit 1 when a cited heading has already gone. It
is refused beside a page argument rather than ignored there.

WHAT IT DOES NOT SEE, stated because a silent exclusion is how the original trap was built. Only
the relative `](PAGE.md#anchor)` form is read. `test_internal_links_resolve.py` ALSO resolves this
site's own served URLs, `https://claude-multisession.pages.dev/PAGE.html#anchor`, back to markdown
and reddens on a missing anchor -- so that spelling inside an archive would be the same trap,
unwarned. Measured at `8cb2cf6`: zero anchored served URLs exist anywhere in the tree, against a
control of 40 unanchored served URLs inside the archives, so the shape is live and the anchored
population is empty. Widen this when the first one appears.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: The archive registry. It is the authority on which files are frozen, and it is the SAME file
#: whose hashes make them unrepairable -- so the set this script protects and the set nobody may
#: edit come from one declaration rather than two that can disagree.
REGISTRY = "docs/_data/page-revisions.json"

#: An anchored markdown link into another markdown file: `](TARGET.md#anchor)`.
#: Deliberately wider than the anchor charset the original measurement used. A `#Mixed_Case` anchor
#: is the same trap, and a narrower pattern would report it absent rather than report it.
ANCHORED_LINK = re.compile(r"\]\(([^)\s#]+\.md)#([^)\s]+)\)")

ATX_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`+[^`]*`+")
EXPLICIT_ANCHOR = re.compile(r"<(?:a|span)\s+id=[\"']([^\"']+)[\"']")


def anchor_slug(heading: str) -> str:
    """GitHub's heading-to-anchor rule.

    A SECOND COPY of `test_internal_links_resolve.anchor_slug`, on purpose and pinned as such. A
    script under `scripts/` that imported a function out of `tests/` would invert the dependency and
    stop working the day the suite moved. The cost of a copy is drift, and drift is the thing
    `tests/test_a_heading_a_frozen_archive_cites_cannot_be_renamed.py` measures: it runs both
    sluggers over every heading in the tree and requires them to agree character for character.
    """
    s = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"\s+", "-", s).strip("-")


class Citation:
    """One anchored link, written in a frozen archive, pointing at a page that is still edited."""

    def __init__(self, archive: str, line: int, target: str, anchor: str) -> None:
        self.archive = archive
        self.line = line
        self.target = target
        self.anchor = anchor

    @property
    def slug(self) -> str:
        return anchor_slug(self.anchor)

    @property
    def pair(self) -> tuple[str, str]:
        return (self.target, self.slug)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"Citation({self.archive}:{self.line} -> {self.target}#{self.anchor})"


def _repo_relative(path: Path | str) -> str:
    """One spelling for a repo-relative path: posix separators, `.` and `..` folded away.

    THREE KEYS ARE COMPARED AS STRINGS in this script -- the citation's target, the archive set it
    is excluded against, and the page a person types -- and all three go through here. An archive
    under `docs/roles/` citing `](../LIMITS.md#x)` yields `docs/roles/../LIMITS.md` unfolded, which
    matches no page anybody would name and quietly drops out of every answer. Seven of the fifty
    archives sit one directory down, so that shape is one page retirement away.
    """
    return Path(os.path.normpath(str(path))).as_posix()


def archives(root: Path = REPO_ROOT) -> list[str]:
    """Every frozen archive, as repo-relative posix paths, read from the registry.

    RAISES rather than returning an empty list. An empty archive set makes every later question
    answer "nothing cites this heading", which is the confident zero this repository exists to
    catch: byte-identical to the true answer, and produced by a reader that failed.
    """
    path = root / REGISTRY
    if not path.is_file():
        raise LookupError(
            f"{REGISTRY} is not there. It is the list of frozen archives, so without it this "
            "script cannot tell a heading nothing cites from a heading it failed to look up."
        )
    pages = json.loads(path.read_text(encoding="utf-8")).get("pages", [])
    found = ["docs/" + page["archive"] for page in pages if page.get("archive")]
    if not found:
        raise LookupError(f"{REGISTRY} names no archive. It is present, and it says nothing.")
    missing = [f for f in found if not (root / f).is_file()]
    if missing:
        raise LookupError(
            f"{REGISTRY} names {len(missing)} archive(s) that are not in the tree: {missing[:3]}. "
            "Part of the corpus is unreadable, so a zero here would be a scan that fell short."
        )
    return sorted(found)


def _without_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    """The part of a line a reader sees, and whether an HTML comment is still open after it.

    A PORT of `test_internal_links_resolve._without_comments`, and it stays a port for the reason
    `anchor_slug` does. Code spans are blanked before the delimiters are hunted, because a code
    example containing `<!--` does not open a comment.
    """
    scan = INLINE_CODE.sub(lambda match: " " * len(match.group()), line)
    visible: list[str] = []
    pos = 0
    while pos < len(line):
        if in_comment:
            end = scan.find("-->", pos)
            if end < 0:
                break
            pos = end + 3
            in_comment = False
        else:
            start = scan.find("<!--", pos)
            if start < 0:
                visible.append(line[pos:])
                break
            visible.append(line[pos:start])
            pos = start + 4
            in_comment = True
    return "".join(visible), in_comment


def _visible_lines(text: str) -> list[tuple[int, str]]:
    """Numbered lines outside fenced blocks and HTML comments. Inline code spans are left intact.

    CODE SPANS SURVIVE THIS, and the difference is load-bearing rather than an oversight. A heading
    reading ``### The vault primary's `roles/` folder ...`` slugs WITH the backticked word, so a
    reader that blanked it first would compute a slug no anchor ever matches. Callers that need
    code blanked -- the link scan does, since a page documenting a link has to write one -- blank it
    themselves. The order here mirrors the link test's `parse`: a fence inside a comment does not
    toggle the fence.
    """
    out: list[tuple[int, str]] = []
    fenced = False
    in_comment = False
    for lineno, line in enumerate(text.split("\n"), 1):
        if not in_comment and FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        line, in_comment = _without_comments(line, in_comment)
        out.append((lineno, line))
    return out


def anchors_on(page: Path) -> set[str]:
    """Every anchor a page serves: heading slugs with GitHub's duplicate suffixes, plus aliases.

    The alias half is the escape hatch this script recommends, so it is the half that has to be read
    accurately. `tests/test_page_revisions.py` pins that an alias really resolves, and that an
    `<a id>` written inside a code example does not.
    """
    seen: dict[str, int] = {}
    out: set[str] = set()
    for _, line in _visible_lines(page.read_text(encoding="utf-8")):
        m = ATX_HEADING.match(line)
        if m:
            slug = anchor_slug(m.group(2))
            n = seen.get(slug, 0)
            out.add(slug if n == 0 else f"{slug}-{n}")
            seen[slug] = n + 1
        out.update(EXPLICIT_ANCHOR.findall(INLINE_CODE.sub("", line)))
    return out


def citations(root: Path = REPO_ROOT) -> list[Citation]:
    """Every anchored link written in a frozen archive that names a page outside the archives.

    An archive citing another archive is excluded: both ends are frozen, so no edit anybody is
    allowed to make can break it. A same-file `#anchor` is excluded for the same reason.
    """
    frozen = archives(root)
    frozen_set = set(frozen)
    found: list[Citation] = []
    for rel in frozen:
        page = root / rel
        for lineno, line in _visible_lines(page.read_text(encoding="utf-8")):
            for target, anchor in ANCHORED_LINK.findall(INLINE_CODE.sub("", line)):
                dest = _repo_relative(Path(rel).parent / target)
                if dest in frozen_set:
                    continue
                found.append(Citation(rel, lineno, dest, anchor))
    if not found:
        raise LookupError(
            f"read {len(frozen)} frozen archive(s) and found no anchored link into a live page. "
            "Either every one was removed -- which cannot happen, the archives are hash-pinned -- "
            "or the link pattern stopped matching. Do not read this as an all-clear."
        )
    return found


def unresolved(root: Path = REPO_ROOT) -> list[Citation]:
    """The citations whose target heading is already gone. Empty is the healthy state.

    A TARGET PAGE THAT IS NOT THERE AT ALL serves no anchors, so every citation into it is
    reported. That is the right answer and the wrong DIAGNOSIS to hand a reader, so `explain` is
    told which of the two it is looking at rather than calling a deleted file a live page.
    """
    known: dict[str, set[str]] = {}
    broken: list[Citation] = []
    for cit in citations(root):
        if cit.target not in known:
            page = root / cit.target
            known[cit.target] = anchors_on(page) if page.is_file() else set()
        if cit.slug not in known[cit.target]:
            broken.append(cit)
    return broken


def explain(target: str, slug: str, citing: list[Citation], page_exists: bool = True) -> str:
    """What to tell somebody whose rename is about to strand a link they may not touch.

    THE MESSAGE IS THE DELIVERABLE. A reader told only that a link broke goes and fixes the link,
    and the second red they earn for editing a hash-pinned archive teaches them nothing about the
    first. So this names the closed route before it offers the open ones.

    TWO OPTIONS, NOT THREE, and the third was cut after it was tested rather than after it was
    reasoned about. "Retire the page instead" reads as a clean way out and is not one: retirement
    copies the prose to a NEW `X.old.md` and leaves `X.md` live, so the citation still names a page
    that is still edited and the warning reappears unchanged. Advice that survives only until
    somebody follows it is worse than no third option.
    """
    rows = sorted(citing, key=lambda c: (c.archive, c.line))
    where = "\n".join(f"    {c.archive}:{c.line}" for c in rows)
    lead = (
        f"{target}#{slug} is cited by {len(rows)} frozen archive(s):\n"
        if page_exists
        else f"{target} is not in the tree, and {len(rows)} frozen archive(s) cite {slug} on it:\n"
    )
    restore = (
        "    1. Keep the heading. Cheapest, and it is a real answer.\n"
        if page_exists
        else "    1. Put the page back. It is the target of a link that cannot be repointed.\n"
    )
    return (
        f"{lead}"
        f"{where}\n"
        "\n"
        "  YOU CANNOT FIX THOSE LINKS. Each of those files is sha256-pinned in\n"
        f"  {REGISTRY}, so editing one fails\n"
        "  tests/test_page_revisions.py instead of fixing anything. Deleting the link is the same\n"
        "  edit. Both routes are closed, which leaves your own change as the thing that has to give.\n"
        "\n"
        "  Two things you can do:\n"
        f"{restore}"
        "    2. Rename it, and leave the old slug behind as an alias above the new heading:\n"
        "\n"
        f"           <a id=\"{slug}\"></a>\n"
        "\n"
        "           ## Whatever you renamed it to\n"
        "\n"
        "       Inbound anchors go on resolving. test_page_revisions.py pins that they do.\n"
        "\n"
        "  Retiring the page is NOT a third option. Retirement copies the prose to a new .old.md\n"
        "  and leaves this page live, so the citation still names it and this warning returns.\n"
    )


def _summary(found: list[Citation], pages: list[str], pairs: list[tuple[str, str]]) -> None:
    print(
        f"frozen citations: {len(found)} anchored link(s) from "
        f"{len({c.archive for c in found})} frozen archive(s) into {len(pages)} live page(s), "
        f"{len(pairs)} distinct heading(s)."
    )
    print("  Rename one of those headings and the red lands in a file nobody may repair.")
    print("  Name a page to see which of its headings are held:")
    print("      python scripts/quality/frozen_citations.py docs/LIMITS.md")
    for page in pages:
        held = sorted({slug for target, slug in pairs if target == page})
        print(f"  {page}  ({len(held)} heading(s))")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Which frozen archives cite a heading?")
    ap.add_argument("page", nargs="?", help="a live page, e.g. docs/LIMITS.md")
    ap.add_argument("heading", nargs="?", help="the heading text, or its slug")
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--strict", action="store_true", help="exit 1 when a cited heading has gone")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    if args.strict and args.page is not None:
        # Refused rather than ignored. A gate wired as `--strict <page>` that silently answered a
        # different question is the shape this whole file exists to warn about.
        ap.error("--strict applies to the whole inventory; drop the page argument, or drop --strict")

    try:
        found = citations(root)
        gone = unresolved(root) if args.page is None else []
    except LookupError as exc:
        print(f"frozen citations: NOTHING WAS READ -- {exc}", file=sys.stderr)
        return 2

    pages = sorted({c.target for c in found})
    pairs = sorted({c.pair for c in found})

    if args.page is None:
        _summary(found, pages, pairs)
        if gone:
            print(f"\n{len({c.pair for c in gone})} cited heading(s) are ALREADY GONE:")
            for target, slug in sorted({c.pair for c in gone}):
                print()
                print(
                    explain(
                        target,
                        slug,
                        [c for c in gone if c.pair == (target, slug)],
                        page_exists=(root / target).is_file(),
                    )
                )
            if args.strict:
                return 1
        return 0

    # THE PAGE IS RESOLVED BEFORE IT IS COMPARED. Filtering the citations by a raw string means a
    # typo, a missing `docs/` prefix or a different case answers "nothing cites this" and exits 0 --
    # a confident all-clear for the exact rename this tool exists to stop. Resolving also folds the
    # on-disk spelling, so `docs/limits.md` reaches the same answer as `docs/LIMITS.md`.
    named = (root / args.page.replace("\\", "/")).resolve()
    if not named.is_file():
        print(
            f"frozen citations: NOTHING WAS READ -- {args.page} is not a file under {root}. "
            "No page was examined, so this is not an all-clear.",
            file=sys.stderr,
        )
        return 2
    try:
        page = _repo_relative(named.relative_to(root.resolve()))
    except ValueError:
        print(
            f"frozen citations: NOTHING WAS READ -- {args.page} resolves outside {root}, so no "
            "page in this repository was examined.",
            file=sys.stderr,
        )
        return 2
    held = sorted({slug for target, slug in pairs if target == page})

    if args.heading is None:
        if not held:
            print(f"frozen citations: no frozen archive cites a heading on {page}.")
            print(f"  {len(found)} citation(s) read across {len(pages)} page(s), so the scan ran.")
            return 0
        print(f"frozen citations: {len(held)} heading(s) on {page} are cited by frozen archives.")
        print("  Renaming any of them breaks a link that cannot be edited. Per heading:")
        for slug in held:
            print()
            print(explain(page, slug, [c for c in found if c.pair == (page, slug)]))
        return 1

    # ALWAYS SLUGGED. The earlier version passed a one-token argument through verbatim, so a heading
    # typed as written -- "Presence", which is what HOUSE-STYLE step 2 asks for -- was looked up as
    # `#Presence`, missed, and blessed. anchor_slug is idempotent on every slug in the pinned set.
    slug = anchor_slug(args.heading)
    if slug not in held:
        print(f"frozen citations: no frozen archive cites {page}#{slug}.")
        print(f"  {len(found)} citation(s) read, {len(held)} of them on this page, so the scan ran.")
        print("  That rename is yours to decide. Live pages still link to each other, so run")
        print("  `python -m unittest discover -s tests` after it.")
        return 0
    print(explain(page, slug, [c for c in found if c.pair == (page, slug)]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
