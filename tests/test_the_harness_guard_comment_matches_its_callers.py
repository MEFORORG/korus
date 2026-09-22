"""Hold the harness-guard rows in `Get-CcxWorktreePath`'s doc comment to the scripts they name.

THE FAILURE THIS EXISTS FOR. Until 2026-09-22 that comment said any `.claude/worktrees/` path "is
excluded from destructive operations unconditionally". `scripts/worktree/remove.ps1` is destructive
and never called `Test-CcxHarnessWorktreePath`, so under the `nested` layout it removed exactly such
a path. A ledger row in another repository relied on the comment and published a false conclusion.

The comment now has one row per script, opening "calls it" or "does NOT call it". This file reads
each named script's CODE, comments stripped, and fails the moment that opening stops being true.
Adding the guard to `remove.ps1` fails it too. That would be a design change, and the comment has
to follow it.

A CALL THROUGH A HELPER COUNTS. Any function in `_common.ps1` whose own code calls the guard is
read as reaching it, so a new wrapper there is caught without editing this file. One level only:
a wrapper of a wrapper, or a helper defined anywhere else, goes unseen.

ARMED BY CONTROLS ON BOTH SIDES. "remove.ps1 does not call it" is an absence, and a broken
detector reports the same absence. So the detector must fire on a small fixed script with a call
planted in it, and stay quiet when the call is only in a comment. And the real `remove.ps1` must
still read as the script that runs `git worktree remove` after stripping, or the absence has no
subject.

WHAT THIS DOES NOT PROVE. It reads source; it runs no PowerShell. A call inside a string literal
counts as a call. The rest of each row -- which gate rules, what the reaper does -- is prose this
file does not check. The scratch-repository runs behind the comment are recorded in it, with a ref.

Run: python -m pytest tests -q     (or: python -m unittest discover -s tests -v)
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import _ccxtest as t

COMMON = t.REPO_ROOT / "scripts" / "coord" / "_common.ps1"
GUARD = "Test-CcxHarnessWorktreePath"

# The rows of the comment, and what each one claims.
CALLS = {"prune-merged.ps1": t.PRUNE_MERGED, "worktree_gate.ps1": t.GATE}
DOES_NOT = {"remove.ps1": t.WORKTREE_REMOVE}

# A fixed base rather than the real remove.ps1, so the control stays valid if that file ever
# legitimately gains the guard and moves to CALLS.
PLANT_BASE = (
    "param([string]$Name)\n"
    "$WorktreePath = Get-CcxWorktreePath -Name $Name\n"
    "& git worktree remove --force $WorktreePath\n"
)
PLANTED_CALL = "\nif (Test-CcxHarnessWorktreePath $WorktreePath) { throw 'harness-owned' }\n"
PLANTED_COMMENT = "\n# Test-CcxHarnessWorktreePath is deliberately not called here.\n"


# `function Name {` and `function Name([string]$x) {` alike. The inline parameter list is optional.
FUNCTION_OPEN = re.compile(r"(?im)^\s*function\s+([\w-]+)\s*(?:\([^{]*?\))?\s*\{")


def guard_reachers(common_code: str | None = None) -> list[str]:
    """The guard, plus every function in `_common.ps1` whose own code calls it."""
    src = t.ps_source(COMMON) if common_code is None else common_code
    names = [GUARD]
    for match in FUNCTION_OPEN.finditer(src):
        body = src[match.end():t.close_brace(src, match.end())]
        if match.group(1).lower() != GUARD.lower() and re.search(
            rf"\b{re.escape(GUARD)}\b", body, re.I
        ):
            names.append(match.group(1))
    return names


def reaches_guard(ps_code: str, names: list[str] | None = None) -> bool:
    """Does this comment-stripped PowerShell call the guard? Command names ignore case."""
    alternatives = "|".join(re.escape(n) for n in (names or guard_reachers()))
    return re.search(rf"\b(?:{alternatives})\b", ps_code, re.I) is not None


def detects(ps_text: str) -> bool:
    """The detector as the tests below apply it to a file: strip comments, then look."""
    return reaches_guard(t.strip_ps_comments(ps_text))


def calls_guard(path: Path) -> bool:
    return detects(t.read(path))


def worktree_path_comment() -> str:
    """The doc comment of Get-CcxWorktreePath, with whitespace flattened so a wrapped phrase matches."""
    match = re.search(r"function Get-CcxWorktreePath \{\s*<#(.*?)#>", t.read(COMMON), re.S)
    if match is None:
        raise AssertionError(
            f"{COMMON.name}: no doc comment found for Get-CcxWorktreePath. The function moved or "
            "was renamed, and every assertion below would then read an empty string."
        )
    return " ".join(match.group(1).split())


class TheHarnessGuardCommentMatchesItsCallers(unittest.TestCase):
    def test_the_comment_carries_a_row_for_each_script(self):
        comment = worktree_path_comment()
        self.assertGreater(len(comment), 500, "the extracted comment is too short to be the real one")
        for name in CALLS:
            with self.subTest(script=name):
                self.assertIn(f"{name} calls it", comment)
        for name in DOES_NOT:
            with self.subTest(script=name):
                self.assertIn(f"{name} does NOT call it", comment)

    def test_the_helper_list_is_derived_and_finds_the_known_wrapper(self):
        self.assertIn("Test-CcxSiblingWorktreePath", guard_reachers())

    def test_a_new_helper_is_found_and_a_call_through_it_counts(self):
        wrapper = (
            "\nfunction Assert-CcxRemovable([string]$Path) {\n"
            "    if (Test-CcxHarnessWorktreePath $Path) { throw 'harness-owned' }\n"
            "}\n"
        )
        names = guard_reachers(t.ps_source(COMMON) + wrapper)
        self.assertIn("Assert-CcxRemovable", names)
        self.assertTrue(reaches_guard(PLANT_BASE + "\nAssert-CcxRemovable $WorktreePath\n", names))
        self.assertFalse(reaches_guard(PLANT_BASE, names))

    def test_each_script_the_comment_says_calls_the_guard_does(self):
        for name, path in CALLS.items():
            with self.subTest(script=name):
                self.assertTrue(
                    calls_guard(path),
                    f"{name} no longer calls the harness guard in code, but the doc comment of "
                    "Get-CcxWorktreePath says it does. Correct the comment, or restore the call.",
                )

    def test_each_script_the_comment_says_skips_the_guard_does_not_call_it(self):
        for name, path in DOES_NOT.items():
            with self.subTest(script=name):
                code = t.ps_source(path)
                self.assertIn(
                    "worktree remove", code,
                    f"{name} no longer reads as the script that runs `git worktree remove` once "
                    "its comments are stripped, so an absence found in it measures nothing.",
                )
                self.assertFalse(
                    reaches_guard(code),
                    f"{name} now calls the harness guard, but the doc comment of "
                    "Get-CcxWorktreePath says it does not. That is a behaviour change: update the "
                    "comment and docs/WORKTREES.md, 'Two layouts coexist', in the same change.",
                )

    def test_the_detector_fires_on_a_planted_call(self):
        self.assertFalse(detects(PLANT_BASE), "precondition: the unplanted base reads clean")
        self.assertTrue(detects(PLANT_BASE + PLANTED_CALL))
        self.assertTrue(detects(PLANT_BASE + PLANTED_CALL.lower()))
        self.assertTrue(detects(PLANT_BASE + PLANTED_CALL.replace("Harness", "Sibling")))

    def test_the_detector_ignores_a_call_named_only_in_a_comment(self):
        self.assertFalse(detects(PLANT_BASE + PLANTED_COMMENT))
        self.assertFalse(detects(PLANT_BASE + "\n<#\n" + PLANTED_CALL + "\n#>\n"))


if __name__ == "__main__":
    unittest.main()
