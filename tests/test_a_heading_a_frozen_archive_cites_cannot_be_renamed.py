"""A heading a frozen archive cites cannot be renamed, because the citing file cannot be repaired.

THE TRAP, and it is the whole reason this file exists. Fifty `.old.md` archives under `docs/` are
frozen prose. Thirty-eight anchored links inside them point OUT, at headings on pages that are still
edited every day. Rename one of those headings and `test_internal_links_resolve.py` goes red over a
link in a file nobody is permitted to open.

BOTH ROUTES OUT ARE CLOSED. The link cannot be edited, because each archive is sha256-pinned in
`docs/_data/page-revisions.json` and touching one reds `test_page_revisions.py` instead. Deleting
the link is the same edit. So the rename is what has to be undone, and nothing said so.

WHY THIS IS NOT A SECOND COPY OF THE LINK TEST. They fire at the same moment and they say different
things. `test_internal_links_resolve.py` reports a broken link, in the same words it uses for the
other 58 anchored links in this tree, and those words tell a reader to go and fix it. Following that
advice here earns a second red from the other direction. This file answers the question the link
test cannot: WHOSE file the broken link is in, and why leaving the heading alone is the fix.

WHY IT IS ALSO NOT A HOOK. No hook in `scripts/hooks/` reads the TEXT of an edit; the two that fire
on the Edit family decide on the path. Measured at `8cb2cf6`:

    git grep -c -E 'new_string|old_string' -- 'scripts/hooks/*'    # 0, the subject
    git grep -c -E 'tool_input' -- 'scripts/hooks/*'               # 7 across 4 files, the control

A rename detector would be the first hook here to parse an edit's strings, on new payload surface
with no sibling to copy, and every `PreToolUse` guard here fails open. The instrument that fires
before a rename is `scripts/quality/frozen_citations.py`, which a person runs; this file is what
stops that script and its inventory rotting.

AN EARLIER DRAFT OF THAT PARAGRAPH PUBLISHED 0 AND 6, and both numbers were wrong. The subject
pattern included `content`, which matches inside `contention` and `contents` and returns 4 hits of
prose; no spelling of the control returned 6. The conclusion survived and the instrument did not,
which is the half that matters -- an unarmed control is what Article V is about, and it was sitting
inside the file arguing for arming things.

THE SPLIT BETWEEN THE TWO. The script owns the extraction and the message. This file owns the
proof: that the set it reads is the set that is there, that its slug rule still agrees with the one
the link test resolves anchors with, and that it fires on a rename rather than reporting agreement.

HOW THE PIN BEHAVES. `FROZEN_CITATIONS` below is an exact set, and it is IMMUTABLE: every row is
read out of a hash-pinned archive, so nothing anybody is allowed to do can move it. Retiring the
target page does not move it either -- retirement writes a new `X.old.md` and leaves `X.md` live,
so the citation goes on naming a page outside the archive set. Any movement here is an extraction
that went blind, and there is no legitimate reason to update the set.

Measured at `8cb2cf6`: 38 citations, 20 citing archives, 17 target pages, 27 distinct headings, and
every one of the 27 resolves.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

sys.path.insert(0, str(t.REPO_ROOT / "scripts" / "quality"))
import frozen_citations as fc  # noqa: E402

from test_internal_links_resolve import (  # noqa: E402
    anchor_slug as link_test_slug,
    parse as link_test_parse,
    resolvable_anchors as link_test_anchors,
)

#: Every heading a frozen archive cites, as `(target page, anchor slug)`. Read at `8cb2cf6` with
#: `python scripts/quality/frozen_citations.py`. Twenty-seven rows behind thirty-eight citations:
#: eight rows are cited from more than one archive, and the worst of them from three at once, so a
#: single rename can strand three links in three separate files nobody may open.
FROZEN_CITATIONS = frozenset({
    ("docs/CASE-STUDY-drift-audit.md", "4-evaluate-prohibitions-as-a-set-never-one-at-a-time"),
    ("docs/CI-FOR-LEADERS.md", "what-you-must-never-claim"),
    ("docs/CONCEPTS.md", "the-rule-is-about-held-state-and-a-message-is-not-held-state"),
    ("docs/COORDINATION.md", "a-broadcast-needs-an-expiry-or-a-recipient-evaluable-predicate"),
    ("docs/COORDINATION.md", "a-clean-merge-is-not-evidence-that-nobody-duplicated-your-work"),
    ("docs/COORDINATION.md", "announcing-yourself"),
    ("docs/COORDINATION.md", "presence-who-is-here"),
    ("docs/FAQ-HUMAN.md", "more-sessions-can-fill-the-merge-queue-faster"),
    ("docs/FAQ.md", "how-many-sessions-should-i-run"),
    ("docs/HOOKS.md", "establishing-what-a-hook-actually-does"),
    ("docs/HOOKS.md", "every-exit-from-a-stateful-hook-is-a-state-transition"),
    ("docs/HOOKS.md", "the-git-hook-contract"),
    ("docs/INSTALL.md", "now-prove-all-of-it"),
    ("docs/KORUS-BUILD.md", "before-you-open-any-session"),
    ("docs/LIMITS.md", "what-actually-switches-each-control-on"),
    ("docs/LIMITS.md", "what-the-collision-gate-does-not-see"),
    ("docs/PRUNING.md", "a-wrong-cwd-run-must-refuse-loudly-never-green-no-op"),
    ("docs/SEQUENCE-ALLOC.md", "wiring-the-pre-commit-hook"),
    ("docs/SESSION-MAIL.md", "step-5-split-show-from-consume-across-two-hook-events"),
    ("docs/SESSION-MAIL.md", "who-actually-needs-this"),
    ("docs/STEERING.md", "the-trust-boundary"),
    ("docs/TIPS-AND-TRICKS.md", "4-when-you-write-a-guardrail"),
    ("docs/TIPS-AND-TRICKS.md", "put-at-least-one-signal-outside-the-component-being-audited"),
    ("docs/TIPS-AND-TRICKS.md", "reconcile-the-parts-against-the-total-the-tool-already-printed"),
    ("docs/WORKER-BRIEF.md", "why-a-prohibition-rather-than-ask-if-you-are-unsure"),
    ("docs/WORKTREES.md", "two-layouts-coexist-and-only-one-has-scripted-teardown"),
    ("docs/WORKTREES.md", "what-actually-stops-the-failure"),
})

#: The occurrence count behind those 27 rows, and the two other shapes of the same reading. Pinned
#: separately because a pattern that half-matched could still produce the right SET from fewer rows.
FROZEN_CITATION_COUNT = 38
CITING_ARCHIVE_COUNT = 20

HOW_TO_SEE_IT = (
    "Run `python scripts/quality/frozen_citations.py` for the whole inventory, or name a page and "
    "a heading for the one row."
)


def _plant(root: Path, archive_body: str, page_body: str | None) -> None:
    """A planted tree in the shape this checker reads: one registered archive, live pages.

    TWO LIVE PAGES, NOT ONE, AND BOTH ARE CITED. `DECOY.md` carries the very heading the citation
    names and keeps it. With a single live page, a checker that pooled the anchors of every cited
    page instead of reading the CITED one is indistinguishable from a correct checker -- measured,
    that sabotage passed all ten cases the first version of this file had. The decoy separates
    them, and it has to be CITED to do it: an uncited page is never looked up, so pooling never
    sees it and the fixture proves nothing.

    `page_body` of None leaves the target page absent, which is the other branch a single fixture
    left unpinned.
    """
    (root / "docs" / "_data").mkdir(parents=True)
    (root / "docs" / "OLD.old.md").write_text(
        archive_body + "Also [the decoy](DECOY.md#a-heading).\n", encoding="ascii"
    )
    (root / "docs" / "DECOY.md").write_text("## A heading\n", encoding="ascii")
    if page_body is not None:
        (root / "docs" / "LIVE.md").write_text(page_body, encoding="ascii")
    (root / "docs" / "_data" / "page-revisions.json").write_text(
        json.dumps({"pages": [{"archive": "OLD.old.md", "sha256": "0" * 64}]}), encoding="ascii"
    )


class TheInventoryIsTheOneThatIsThere(unittest.TestCase):
    """The pinned set, the live extraction, and the registry all describe one corpus.

    THIS IS THE ARMING HALF. Every other assertion in this file compares something against the
    citations the script returns, so a script that returned nothing would pass all of them by
    reporting agreement between two empty sets. That is the confident zero this repository exists
    to catch, and it is why the count is pinned beside the set rather than derived from it.
    """

    def test_the_extraction_finds_the_pinned_citations(self):
        found = fc.citations()
        self.assertEqual(
            FROZEN_CITATION_COUNT,
            len(found),
            f"the frozen archives now yield {len(found)} anchored citation(s), not "
            f"{FROZEN_CITATION_COUNT}. Every one of them is read out of a hash-pinned archive, so "
            "this number cannot move for any reason anybody is allowed to cause. Do not update it "
            "to match. The link pattern in scripts/quality/frozen_citations.py has stopped "
            f"matching, or the registry no longer names the archives. {HOW_TO_SEE_IT}",
        )
        self.assertEqual(
            FROZEN_CITATIONS,
            frozenset(c.pair for c in found),
            "the set of headings frozen archives cite has changed, and it has no legitimate reason "
            "to. Retiring a target page does not move it: retirement writes a new .old.md and "
            "leaves the cited page live. Find the extraction defect rather than updating the pin. "
            f"{HOW_TO_SEE_IT}",
        )
        self.assertEqual(
            CITING_ARCHIVE_COUNT,
            len({c.archive for c in found}),
            "a different number of frozen archives carries these citations. The count is pinned "
            "beside the pair set because one archive dropping out can leave the set unchanged.",
        )

    def test_the_registry_and_git_name_the_same_archives(self):
        """The script reads the registry; the link test reads `git ls-files`. Pin the agreement.

        They are two declarations of one set, and the trap is exactly what happens when a file is
        in one and not the other. An archive git tracks but the registry omits is unprotected by
        this file AND unhashed by test_page_revisions.py, so nothing would report it.
        """
        out = subprocess.run(
            ["git", "ls-files", "*.old.md"],
            cwd=t.REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked = {line.strip() for line in out.stdout.splitlines() if line.strip()}
        self.assertTrue(
            tracked,
            "git ls-files matched no archive at all. An empty set would compare equal to an empty "
            "registry and report agreement, so this raises instead.",
        )
        self.assertEqual(
            tracked,
            set(fc.archives()),
            "git and docs/_data/page-revisions.json disagree about which files are frozen. A file "
            "in only one of them is protected by neither: unpinned by test_page_revisions.py, and "
            "invisible to the citation scan that would otherwise warn about its inbound links.",
        )
        # A WEAKER ASSERTION THAN IT LOOKS, kept and labelled rather than dropped. Both sides build
        # `"docs/" + page["archive"]` from the same registry, so today this cannot report a
        # disagreement. What it pins is that they go on deriving it: a future hard-coded copy of
        # either list is the drift that would split the prose scan's exemption from the archive set
        # the link scan reads, which is the original trap.
        self.assertEqual(
            set(t.ARCHIVED_PAGES),
            set(fc.archives()),
            "the checker's archive list and _ccxtest.ARCHIVED_PAGES disagree, which means one of "
            "them stopped being derived from docs/_data/page-revisions.json. ARCHIVED_PAGES is "
            "what the prose scan skips; a divergence splits it from the set the link scan reads.",
        )


class EveryCitedHeadingStillExists(unittest.TestCase):
    """The warning itself. It fires on a rename, and it says why the link cannot be fixed.

    A FAILURE HERE IS NOT A BROKEN LINK TO GO AND MEND. It is a rename that took a heading a frozen
    file depends on, and the message carries the three real options in place of the one that does
    not work.
    """

    def test_no_rename_has_stranded_a_frozen_citation(self):
        gone = fc.unresolved()
        if not gone:
            return
        report = "\n\n".join(
            fc.explain(target, slug, [c for c in gone if c.pair == (target, slug)])
            for target, slug in sorted({c.pair for c in gone})
        )
        self.fail(
            f"{len({c.pair for c in gone})} heading(s) that a frozen archive cites are gone from "
            "the live pages. Do NOT go and fix those links.\n\n" + report
        )


class TheCheckerAgreesWithTheLinkTest(unittest.TestCase):
    """Two copies of the slug rule and two heading readers, measured against each other.

    THE COPY IS DELIBERATE and the reason is in the script's docstring: a file under `scripts/` that
    imported out of `tests/` would invert the dependency. The cost of a copy is drift, and drift
    here is silent in the worst direction -- a checker that slugs differently reports a heading as
    uncited, waves the rename through, and the link test reddens afterwards anyway.

    Both cases run over the REAL corpus rather than a fixture, because the disagreement worth
    catching is the one a real heading in this tree provokes.
    """

    def _tracked_markdown(self) -> list[Path]:
        out = subprocess.run(
            ["git", "ls-files", "*.md"],
            cwd=t.REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        paths = [t.REPO_ROOT / p for p in out.stdout.splitlines() if p.strip()]
        if not paths:
            raise AssertionError("git ls-files matched no markdown -- nothing would be compared")
        return paths

    def test_the_two_slug_rules_agree_on_every_heading_in_the_tree(self):
        headings: list[str] = []
        for path in self._tracked_markdown():
            for line in t.read(path).split("\n"):
                m = fc.ATX_HEADING.match(line)
                if m:
                    headings.append(m.group(2))
        self.assertGreater(
            len(headings),
            500,
            f"only {len(headings)} heading(s) were read from the tree. The comparison below is "
            "only as good as its corpus, and a corpus this small means the reader broke.",
        )
        disagree = [h for h in headings if fc.anchor_slug(h) != link_test_slug(h)]
        self.assertEqual(
            [],
            disagree,
            "frozen_citations.anchor_slug and test_internal_links_resolve.anchor_slug have drifted: "
            f"{disagree[:5]}. A checker that slugs differently reports a cited heading as uncited "
            "and waves through the rename it exists to stop.",
        )

    def test_the_two_heading_readers_serve_the_same_anchors(self):
        compared = 0
        for path in self._tracked_markdown():
            mine = fc.anchors_on(path)
            theirs = link_test_anchors(link_test_parse(t.read(path))[0])
            compared += 1
            self.assertEqual(
                theirs,
                mine,
                f"{path.relative_to(t.REPO_ROOT).as_posix()}: the checker and the link test "
                f"disagree about which anchors this page serves. Only in the checker: "
                f"{sorted(mine - theirs)[:5]}. Only in the link test: {sorted(theirs - mine)[:5]}. "
                "The checker decides whether a rename is safe; the link test decides whether the "
                "run is red. They have to be reading the same page.",
            )
        self.assertGreater(compared, 100, "too few pages compared for this to mean anything")


class TheCheckerCanActuallyFail(unittest.TestCase):
    """Planted controls. A guard that cannot fail reports agreement, which is worse than no guard.

    THREE ARMS, and each rules out a different way of passing for nothing. The clean arm rules out a
    checker hard-wired to complain. The renamed arm rules out one hard-wired to stay quiet. The
    empty arm rules out the one that matters most here: a reader that found no corpus and returned
    a zero shaped exactly like a healthy tree.
    """

    def test_a_clean_planted_tree_reports_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(root, "See [it](LIVE.md#a-heading).\n", "## A heading\n")
            self.assertEqual(
                [("docs/DECOY.md", "a-heading"), ("docs/LIVE.md", "a-heading")],
                sorted(c.pair for c in fc.citations(root)),
            )
            self.assertEqual([], fc.unresolved(root))

    def test_a_renamed_heading_is_reported_with_the_archive_that_cites_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(root, "See [it](LIVE.md#a-heading).\n", "## A renamed heading\n")
            gone = fc.unresolved(root)
            self.assertEqual(1, len(gone), "the rename went unreported -- this check is asleep")
            self.assertEqual(("docs/LIVE.md", "a-heading"), gone[0].pair)
            self.assertEqual("docs/OLD.old.md", gone[0].archive)

            message = fc.explain("docs/LIVE.md", "a-heading", gone)
            for owed in (
                "YOU CANNOT FIX THOSE LINKS",
                "docs/_data/page-revisions.json",
                "test_page_revisions.py",
                "docs/OLD.old.md:1",
                '<a id="a-heading"></a>',
                "Retiring the page is NOT a third option",
            ):
                self.assertIn(
                    owed,
                    message,
                    f"the message no longer carries {owed!r}. A reader who is not told the citing "
                    "file is unrepairable goes and edits it, and earns a second red for it.",
                )

    def test_a_deleted_target_page_is_reported_as_a_deletion(self):
        """The other way a citation strands, and it needs a different first sentence.

        A page that is gone serves no anchors, so every citation into it reads as a renamed
        heading. Reported that way it tells the reader to keep a heading on a file that is not
        there. Measured: with the target page merely absent, a checker that skipped missing pages
        entirely passed all the other cases in this class.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(root, "See [it](LIVE.md#a-heading).\n", None)
            gone = fc.unresolved(root)
            self.assertEqual(1, len(gone), "a citation into a deleted page went unreported")
            self.assertEqual(("docs/LIVE.md", "a-heading"), gone[0].pair)

            message = fc.explain("docs/LIVE.md", "a-heading", gone, page_exists=False)
            self.assertIn("docs/LIVE.md is not in the tree", message)
            self.assertIn("Put the page back", message)
            self.assertNotIn(
                "Keep the heading",
                message,
                "the deleted-page report still offers to keep a heading on a file that is gone.",
            )

    def test_the_cited_page_is_the_one_that_is_read(self):
        """A slug surviving somewhere ELSE does not make the rename safe.

        `_plant` writes `DECOY.md` carrying the cited heading, so a checker that pooled anchors
        across the tree would call this rename clean. This is the case that separates the two.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(root, "See [it](LIVE.md#a-heading).\n", "## A renamed heading\n")
            self.assertIn("a-heading", fc.anchors_on(root / "docs" / "DECOY.md"))
            self.assertEqual(
                [("docs/LIVE.md", "a-heading")],
                [c.pair for c in fc.unresolved(root)],
                "the rename was waved through because the old slug survives on another page. The "
                "checker has to read the page the citation names, not the tree.",
            )

    def test_an_alias_keeps_the_rename_safe(self):
        """Option 2 in the message has to be true, or the advice sends a reader into a third red."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(
                root,
                "See [it](LIVE.md#a-heading).\n",
                '<a id="a-heading"></a>\n\n## A renamed heading\n',
            )
            self.assertEqual([], fc.unresolved(root))

    def test_a_dot_dot_target_resolves_to_the_page_a_person_would_name(self):
        """An archive one directory down cites `](../PAGE.md#x)`, and that has to fold.

        Unfolded it reads `docs/roles/../PAGE.md`, which matches no page anybody types, so the
        query form answers "nothing cites this" and the rename is blessed. Seven of the fifty
        archives sit under `docs/roles/`, so the shape is one page retirement away.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs" / "roles").mkdir(parents=True)
            (root / "docs" / "_data").mkdir(parents=True)
            (root / "docs" / "roles" / "OLD.old.md").write_text(
                "See [it](../LIVE.md#a-heading).\n", encoding="ascii"
            )
            (root / "docs" / "LIVE.md").write_text("## A heading\n", encoding="ascii")
            (root / "docs" / "_data" / "page-revisions.json").write_text(
                json.dumps({"pages": [{"archive": "roles/OLD.old.md", "sha256": "0" * 64}]}),
                encoding="ascii",
            )
            self.assertEqual(
                [("docs/LIVE.md", "a-heading")],
                [c.pair for c in fc.citations(root)],
                "a `../` target did not fold, so this citation is invisible to anyone naming the "
                "page it actually points at.",
            )

    def test_an_empty_corpus_raises_rather_than_reading_as_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs" / "_data").mkdir(parents=True)
            registry = root / "docs" / "_data" / "page-revisions.json"

            with self.assertRaises(LookupError):
                fc.archives(root)  # no registry at all

            registry.write_text(json.dumps({"pages": []}), encoding="ascii")
            with self.assertRaises(LookupError):
                fc.citations(root)  # registry present, and it names nothing

            registry.write_text(
                json.dumps({"pages": [{"archive": "absent.old.md", "sha256": "0" * 64}]}),
                encoding="ascii",
            )
            with self.assertRaises(LookupError):
                fc.citations(root)  # registry names a file that is not there

            (root / "docs" / "absent.old.md").write_text("no links here\n", encoding="ascii")
            with self.assertRaises(LookupError):
                fc.citations(root)  # corpus readable, pattern matched nothing

    def _exit(self, argv: list[str]) -> int:
        """Run the command line, keeping its report out of the suite's own output."""
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return fc.main(argv)

    def test_the_command_line_says_which_answer_it_gave(self):
        """Exit codes are the half a person automates against, so they are pinned separately."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(root, "See [it](LIVE.md#a-heading).\n", "## A heading\n")
            self.assertEqual(1, self._exit(["--root", str(root), "docs/LIVE.md", "A heading"]))
            self.assertEqual(0, self._exit(["--root", str(root), "docs/LIVE.md", "Another one"]))
            self.assertEqual(0, self._exit(["--root", str(root)]))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(root, "See [it](LIVE.md#a-heading).\n", "## A renamed heading\n")
            self.assertEqual(1, self._exit(["--root", str(root), "--strict"]))
            self.assertEqual(
                0,
                self._exit(["--root", str(root)]),
                "the inventory form exited 1 without --strict. A stranded citation is reported "
                "there, not gated there; the gate is this file.",
            )

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                2,
                self._exit(["--root", tmp]),
                "an unreadable corpus exited as though it had looked. Exit 2 is the only code that "
                "says nothing was proven either way.",
            )

    def test_a_page_it_could_not_find_is_a_refusal_and_never_an_all_clear(self):
        """The sharpest false green this tool can give, and the one a reader would act on.

        `HOUSE-STYLE.md` step 2 tells every editor to run the query form before a rename. Filtering
        the citations by the raw argument means a typo, a dropped `docs/` prefix or a different
        case answers "nothing cites this" and exits 0 -- a confident all-clear for exactly the
        rename this tool exists to stop. The sibling instrument in the same table, `check-ascii.ps1`,
        exits 2 on a root that is not there for the same reason.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(root, "See [it](LIVE.md#a-heading).\n", "## A heading\n")
            cited = ["--root", str(root), "docs/LIVE.md", "A heading"]
            self.assertEqual(1, self._exit(cited), "the armed case stopped firing")
            for wrong in (["LIVE.md"], ["docs/NOPE.md"], ["docs/NOPE.md", "A heading"]):
                self.assertEqual(
                    2,
                    self._exit(["--root", str(root), *wrong]),
                    f"{wrong} exited as though a page had been examined. Nothing was read, and "
                    "the reader is about to rename a heading on the strength of it.",
                )

    def test_strict_beside_a_page_is_refused_rather_than_dropped(self):
        """A flag that is accepted and ignored is a gate that never fires."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(root, "See [it](LIVE.md#a-heading).\n", "## A renamed heading\n")
            with self.assertRaises(SystemExit):
                self._exit(["--root", str(root), "--strict", "docs/LIVE.md"])


if __name__ == "__main__":
    unittest.main()
