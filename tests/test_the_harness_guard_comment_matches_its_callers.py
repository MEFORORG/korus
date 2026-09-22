"""Hold the harness-guard rows in `Get-CcxWorktreePath`'s doc comment to the scripts they name.

THE FAILURE THIS EXISTS FOR. Until 2026-09-22 that comment said any `.claude/worktrees/` path "is
excluded from destructive operations unconditionally". `scripts/worktree/remove.ps1` is destructive
and never called `Test-CcxHarnessWorktreePath`, so under the `nested` layout it removed exactly such
a path. A ledger row in another repository relied on the comment and published a false conclusion.

The comment now names which scripts consult the guard and which one does not. This file reads each
named script's CODE, comments stripped, and fails the moment a row stops being true. Adding the guard
to `remove.ps1` fails it too. That would be a design change, and the comment has to follow it.

ARMED BY A PLANTED CONTROL. "remove.ps1 does not call it" is an absence, and a broken detector
reports the same absence. So the detector runs against a small fixed script with a call planted in
it, and must fire; and against the same script with the call only in a comment, and must not.

WHAT THIS DOES NOT PROVE. It reads source; it runs no PowerShell. A call inside a string literal
would count as a call. The scratch-repository run that proved the behaviour is recorded in the
comment itself, with its ref.

Run: python -m pytest tests -q     (or: python -m unittest discover -s tests -v)
"""

from __future__ import annotations

import re
import unittest

import _ccxtest as t

COMMON = t.REPO_ROOT / "scripts" / "coord" / "_common.ps1"

# `Test-CcxSiblingWorktreePath` applies the guard inside itself, so calling it consults the guard.
REACHES_GUARD = re.compile(r"\bTest-Ccx(?:Harness|Sibling)WorktreePath\b")

# The rows of the comment, and what each one claims.
CONSULTS = {
    "worktree_gate.ps1": t.REPO_ROOT / "scripts" / "hooks" / "worktree_gate.ps1",
    "prune-merged.ps1": t.PRUNE_MERGED,
}
DOES_NOT = {"remove.ps1": t.WORKTREE_REMOVE}

# A fixed base rather than the real remove.ps1, so the control stays valid if that file ever
# legitimately gains the guard and moves to CONSULTS.
PLANT_BASE = (
    "param([string]$Name)\n"
    "$WorktreePath = Get-CcxWorktreePath -Name $Name\n"
    "& git worktree remove --force $WorktreePath\n"
)
PLANTED_CALL = "\nif (Test-CcxHarnessWorktreePath $WorktreePath) { throw 'harness-owned' }\n"
PLANTED_COMMENT = "\n# Test-CcxHarnessWorktreePath is deliberately not called here.\n"


def consults_guard(ps_text: str) -> bool:
    return bool(REACHES_GUARD.search(t.strip_ps_comments(ps_text)))


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
        for name in CONSULTS:
            with self.subTest(script=name):
                self.assertIn(f"{name} consults it", comment)
        for name in DOES_NOT:
            with self.subTest(script=name):
                self.assertIn(f"{name} does NOT consult it", comment)

    def test_each_script_the_comment_says_consults_the_guard_calls_it(self):
        for name, path in CONSULTS.items():
            with self.subTest(script=name):
                self.assertTrue(
                    consults_guard(t.read(path)),
                    f"{name} no longer calls the harness guard in code, but the doc comment of "
                    "Get-CcxWorktreePath says it does. Correct the comment, or restore the call.",
                )

    def test_each_script_the_comment_says_skips_the_guard_does_not_call_it(self):
        for name, path in DOES_NOT.items():
            with self.subTest(script=name):
                self.assertFalse(
                    consults_guard(t.read(path)),
                    f"{name} now calls the harness guard, but the doc comment of "
                    "Get-CcxWorktreePath says it does not. That is a behaviour change: update the "
                    "comment and docs/WORKTREES.md, 'Two layouts coexist', in the same change.",
                )

    def test_the_detector_fires_on_a_planted_call(self):
        self.assertFalse(consults_guard(PLANT_BASE), "precondition: the unplanted base reads clean")
        self.assertTrue(consults_guard(PLANT_BASE + PLANTED_CALL))
        self.assertTrue(consults_guard(PLANT_BASE + PLANTED_CALL.replace("Harness", "Sibling")))

    def test_the_detector_ignores_a_call_named_only_in_a_comment(self):
        self.assertFalse(consults_guard(PLANT_BASE + PLANTED_COMMENT))
        self.assertFalse(consults_guard(PLANT_BASE + "\n<#\n" + PLANTED_CALL + "\n#>\n"))


if __name__ == "__main__":
    unittest.main()
