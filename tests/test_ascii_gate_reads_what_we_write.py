"""The ASCII gate must read every file this repository writes.

THE DEFECT THIS PINS, measured 2026-09-06. `check-ascii.ps1 -ExcludeDir` matches a LEAF directory
name at ANY depth (`scripts/quality/check-ascii.ps1`, `Split-Path $d -Leaf` then `-ieq`). CI passed
`-ExcludeDir skills,'.specify'` to skip vendored Spec Kit output, and that pruned all of
`.claude/skills` and all of `.specify` -- hiding 20 files, 19 of them authored here.

IT WAS PROVEN WITH A PLANTED CONTROL rather than inferred. An em dash written into an authored skill
left CI reporting `EXIT 0 -- 209 file(s), all ASCII`. The gate was not weak; it was not looking.

WHY THE EXCLUSION IS ENUMERATED AND THE INCLUSION IS NOT. The second CI step names the VENDORED
directories and scans everything else, so a new authored skill is covered the day it lands. Naming
the authored set instead would fail toward silence, which is the failure that produced this test.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
WORKFLOW = _REPO / ".github" / "workflows" / "gates.yml"
SKILLS = _REPO / ".claude" / "skills"

#: Spec Kit 0.16.4 install output. `metadata.author` reads `github-spec-kit` in each.
VENDOR_PREFIX = "speckit-"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def excluded_in_the_authored_step() -> set[str]:
    """The directory names the second ASCII step skips."""
    for line in workflow_text().splitlines():
        if "check-ascii.ps1" in line and "-Path .claude/skills" in line:
            m = re.search(r"-ExcludeDir ([^\"]+)", line)
            if m:
                return {p.strip() for p in m.group(1).split(",") if p.strip()}
    return set()


def vendored_on_disk() -> set[str]:
    return {p.name for p in SKILLS.iterdir() if p.is_dir() and p.name.startswith(VENDOR_PREFIX)}


def authored_on_disk() -> set[str]:
    return {p.name for p in SKILLS.iterdir() if p.is_dir() and not p.name.startswith(VENDOR_PREFIX)}


class TheAuthoredStepExists(unittest.TestCase):
    def test_a_second_ascii_step_scans_the_skills_tree(self):
        self.assertIn(
            "-Path .claude/skills",
            workflow_text(),
            "no ASCII step reads `.claude/skills`. The first step prunes it by leaf name, so "
            "without this one nothing checks 18 authored playbook skills.",
        )

    def test_it_also_reaches_the_constitution(self):
        self.assertIn(
            ".specify/memory",
            workflow_text(),
            "`.specify/memory/constitution.md` is written here and sits under a pruned tree.",
        )


class TheExclusionNamesTheVendoredSetAndNothingElse(unittest.TestCase):
    """The direction of the list is the whole control.

    Excluding the vendored set means a new AUTHORED skill is scanned by default. Excluding by
    naming the authored set would mean a new one is skipped until somebody remembers it, which is
    exactly how 19 files went unread.
    """

    def test_every_excluded_directory_is_vendored(self):
        stray = sorted(d for d in excluded_in_the_authored_step() if not d.startswith(VENDOR_PREFIX))
        self.assertEqual(
            [],
            stray,
            f"the authored ASCII step excludes directories that are not vendored: {stray}. "
            "Anything named here stops being checked.",
        )

    def test_no_authored_skill_is_excluded(self):
        hidden = sorted(excluded_in_the_authored_step() & authored_on_disk())
        self.assertEqual([], hidden, f"authored skills excluded from the ASCII gate: {hidden}")

    def test_the_exclusion_matches_the_tree(self):
        """A vendored directory added or renamed upstream must force a decision, not drift."""
        self.assertEqual(
            vendored_on_disk(),
            excluded_in_the_authored_step(),
            "the vendored skills on disk and the ones the workflow excludes have diverged. "
            "Add the new one to the step, or drop the stale name.",
        )

    def test_the_scan_actually_found_an_exclusion_list(self):
        """The empty-corpus guard. Every assertion above passes trivially against an empty set."""
        self.assertTrue(
            excluded_in_the_authored_step(),
            "no exclusion list was parsed out of the workflow, so the three checks above compared "
            "nothing against nothing and reported success.",
        )


class TheAuthoredCorpusIsNotEmpty(unittest.TestCase):
    def test_there_are_authored_skills_to_protect(self):
        self.assertGreaterEqual(
            len(authored_on_disk()),
            10,
            "fewer authored skills than expected; this test's subject may have moved.",
        )

    def test_there_are_vendored_skills_to_exclude(self):
        self.assertTrue(vendored_on_disk(), "no vendored skills found, so the exclusion means nothing")


class TheDocumentedCommandDoesNotExitOne(unittest.TestCase):
    """`CLAUDE.md` published a bare invocation that exits 1 on a clean checkout.

    A published command that always fails trains its readers to ignore it, and it was read as
    evidence that the gate itself was red. It was not: CI passes, in two steps.
    """

    def test_claude_md_does_not_publish_a_bare_tree_scan(self):
        text = (_REPO / "CLAUDE.md").read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("pwsh") and "check-ascii.ps1" in stripped:
                self.assertIn(
                    "-Path",
                    stripped,
                    f"CLAUDE.md publishes {stripped!r}, which scans the vendored trees and exits 1 "
                    "on a clean checkout.",
                )


class TheDocumentedCommandKeepsItsExitCode(unittest.TestCase):
    """The published invocation has to survive TWO traps with OPPOSITE remedies.

    TRAP 1, THE ARGUMENT BINDING. `pwsh -File` passes arguments literally, so `-Path a,b` arrives as
    one directory name matching nothing and `-Path a b` binds `b` to the positional `-MaxReport`.
    `-Command` parses the array, which is why the line uses it.

    TRAP 2, THE EXIT CODE. A script invoked as the last thing `-Command` does returns 1 for any
    non-zero code. `check-ascii.ps1` exits 2 for NOTHING WAS SCANNED so a run that measured nothing
    cannot read as a clean one, and that 2 then arrives as 1 -- the code for a real violation.
    `-Command` itself collapses nothing: `-Command "exit N"` propagates 0, 1, 2 and 3 unchanged.

    TRAP 3 IS THE ONE THE FIX INTRODUCES. Inside DOUBLE quotes the calling shell expands
    `$LASTEXITCODE` before the inner pwsh sees it, so the line runs `exit 0` after any successful
    command and a real violation reports SUCCESS. Single quotes are what make the clause safe.

    MEASURED 2026-09-17 on pwsh 7.6.6 at 9379109. The single-quoted line: 0 over the five published
    paths, 1 on `.claude/skills`, 2 on `-Path 'no-such-dir-xyzzy'`. Double-quoted after
    `cmd /c exit 7`, over a clean `docs`: 7 -- the caller's code, not the gate's.
    """

    REEXPORT = "; exit $LASTEXITCODE"

    def command_lines(self) -> list[str]:
        text = (_REPO / "CLAUDE.md").read_text(encoding="utf-8")
        return [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith("pwsh")
            and "-Command" in line
            and "check-ascii.ps1" in line
        ]

    def test_every_published_command_form_reexports_the_code(self):
        for line in self.command_lines():
            self.assertIn(
                self.REEXPORT,
                line,
                f"CLAUDE.md publishes {line!r}. A script invoked as the last thing `-Command` does "
                "returns 1 for any non-zero code, so the gate's exit 2 for NOTHING WAS SCANNED "
                "reads as an ordinary violation.",
            )

    def test_the_command_string_is_single_quoted(self):
        for line in self.command_lines():
            if self.REEXPORT not in line:
                continue
            self.assertIn(
                "-Command '",
                line,
                f"CLAUDE.md publishes {line!r} with a double-quoted -Command string. The calling "
                "shell expands $LASTEXITCODE before the inner pwsh runs, so the line exits with "
                "the CALLER's code and a real violation reports success.",
            )

    def test_there_is_a_command_form_to_check(self):
        """The empty-corpus guard. Both assertions above pass trivially against no lines."""
        self.assertTrue(
            self.command_lines(),
            "no `pwsh -Command` invocation of check-ascii.ps1 was parsed out of CLAUDE.md, so the "
            "checks above examined nothing and reported success.",
        )


if __name__ == "__main__":
    unittest.main()
