"""`docs/SCRIPTS.md` is the published inventory of what this repository ships. Pin that it is whole.

THE FAILURE THIS EXISTS FOR, measured rather than imagined. At 9379109 the tree tracked 58 scripts
and the page carried rows for 47. Eleven had none: three shared modules, five hand-wired hooks,
`scripts/coord/mail.ps1`, `scripts/coord/seat.ps1` and `scripts/quality/expiry_audit.py`.

    git ls-files | grep -E '^(scripts|bin)/.*\\.(ps1|py)$' | wc -l      # 58
    grep -coE '^\\|[^|]*`(scripts|bin)/[a-zA-Z0-9._/-]+`' docs/SCRIPTS.md  # 47

Nothing signalled it, and the page is the thing a copier reads to find out what they are copying. An
absent row reads as "no such script", not as "nobody updated this", so the omission is worse than an
empty page: the reader gets a confident list and no reason to doubt it.

WHY A FLOOR COULD NOT SEE IT. `test_the_landing_page_stays_a_front_door.py` already asserts over this
table -- `assertGreaterEqual(len(rows), 25)` -- and it passed at 47 and would pass at 26. That is the
right check for what it is for, which is content being LOST when the landing page was split in two.
It is not a completeness check, and no count of one set can be one: a floor cannot compare the table
to the tree, because the tree is not in the comparison.

Both directions are checked. A row naming a script that has since been deleted or renamed is the same
defect pointing the other way, and it is the more dangerous half -- it is a claim with nothing behind
it, and the reader who follows it gets a 404 from the documentation site itself.

THE EXCLUSION LIST IS THE MECHANISM, NOT AN ESCAPE HATCH. It is empty today, and the shape is
borrowed from `test_no_hook_is_orphaned.py`: a script may legitimately be left off the page, but
adding a name below costs a sentence saying why, so the choice is a visible diff somebody approves
rather than the silent default.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import subprocess
import unittest

import _ccxtest as t

# The suffixes that make a file a script somebody could run or dot-source. STATED AS A DECISION
# rather than inherited from a glob: `scripts/` also tracks a `README.md`, an allowlist and 24
# validation fixtures, and none of those is a script the inventory owes a reader a row for.
SCRIPT_SUFFIXES = (".ps1", ".py")

# The two directories the page's own rows come from. `bin/` is in because two of its rows already
# are -- `ccx-doctor.ps1` and `ccx-steer.ps1` -- and a subject narrower than the table would let a
# row exist that this file calls an orphan.
SCRIPT_DIRS = ("scripts/", "bin/")

#: Shipped scripts deliberately left off `docs/SCRIPTS.md`, each with the reason. A name here is a
#: decision, not an oversight, and the cases below require the reason to be a real sentence.
#:
#: EMPTY IS THE HONEST STATE TODAY. Every script this repository ships has a row, the three
#: `_`-prefixed shared modules included -- the page carried rows for four of those before this file
#: existed, so omitting the rest would have contradicted its own precedent. It is also a dependency
#: list: the page tells a manual downloader to fetch the shared modules, and a downloader who takes
#: `mail.ps1` without `_mail.ps1` gets a script that throws on line 56.
EXCLUDED: dict[str, str] = {}


def shipped_scripts() -> set[str]:
    """Every tracked script under `scripts/` or `bin/`, as forward-slash repo-relative paths.

    READ FROM `git ls-files` RATHER THAN A DIRECTORY WALK. A walk would sweep in an untracked
    scratch script somebody left in the tree and redden a run over a file no copier ever receives,
    and the whole subject here is what this repository SHIPS.
    """
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=t.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        line.strip()
        for line in out.stdout.splitlines()
        if line.strip().startswith(SCRIPT_DIRS) and line.strip().endswith(SCRIPT_SUFFIXES)
    }


def unlisted(shipped: set[str], listed: set[str]) -> list[str]:
    """Shipped scripts with no row and no exemption. Passed its inputs so the mutation class can
    drive it against a page it has damaged on purpose."""
    return sorted(shipped - listed - set(EXCLUDED))


class TheInventoryNamesEveryScript(unittest.TestCase):
    def test_every_shipped_script_has_a_row(self):
        listed = t.inventory_paths(t.read(t.SCRIPTS_PAGE))
        missing = unlisted(shipped_scripts(), listed)
        self.assertEqual(
            [],
            missing,
            f"these scripts ship and have no row in docs/SCRIPTS.md: {missing}. Add one saying what "
            "the script does and linking the page that owns it, or add it to EXCLUDED in this file "
            "with the reason. An absent row reads as 'no such script'.",
        )

    def test_every_row_names_a_script_that_ships(self):
        listed = t.inventory_paths(t.read(t.SCRIPTS_PAGE))
        orphans = sorted(listed - shipped_scripts())
        self.assertEqual(
            [],
            orphans,
            f"docs/SCRIPTS.md has rows for paths that are not shipped scripts: {orphans}. A row for "
            "a deleted or renamed script is a claim with nothing behind it, and the site serves "
            "these paths itself, so the reader who follows it gets a 404 from the docs.",
        )

    def test_the_subject_is_not_empty(self):
        """The empty-corpus guard. With no scripts found, both directions above compare an empty set
        to an empty set and report agreement over nothing."""
        shipped = shipped_scripts()
        self.assertGreaterEqual(
            len(shipped),
            40,
            f"only {len(shipped)} shipped scripts found, which is far below the 58 measured at "
            "9379109. Either git ls-files failed or SCRIPT_DIRS and SCRIPT_SUFFIXES stopped "
            "describing this tree.",
        )

    def test_the_exclusion_list_names_only_scripts_that_ship(self):
        """A stale exemption silently re-opens the gap it was written to declare."""
        stale = sorted(set(EXCLUDED) - shipped_scripts())
        self.assertEqual([], stale, f"EXCLUDED names paths that do not ship: {stale}")

    def test_every_exclusion_carries_a_reason(self):
        reasonless = sorted(k for k, v in EXCLUDED.items() if len(str(v).strip()) < 40)
        self.assertEqual([], reasonless, f"excluded without a real reason: {reasonless}")


class TheCheckHasPower(unittest.TestCase):
    """The mutation half. A completeness check that cannot fail reports agreement forever, and this
    one is three lines of set arithmetic over a pattern -- exactly the shape that goes quiet after a
    reformat and keeps passing."""

    TARGET = "scripts/worktree/prune-merged.ps1"

    def test_deleting_a_row_makes_the_check_name_that_script(self):
        page = t.read(t.SCRIPTS_PAGE)
        self.assertIn(
            "`" + self.TARGET + "`",
            page,
            "the mutation target has no row, so damaging the page proves nothing",
        )
        damaged = "\n".join(
            line for line in page.splitlines() if "`" + self.TARGET + "`" not in line
        )
        missing = unlisted(shipped_scripts(), t.inventory_paths(damaged))
        self.assertIn(self.TARGET, missing, "removing a row did NOT redden the completeness check")

    def test_the_undamaged_page_reports_nothing_missing(self):
        """The other half. The mutation above means nothing if the baseline is already red."""
        self.assertEqual(
            [], unlisted(shipped_scripts(), t.inventory_paths(t.read(t.SCRIPTS_PAGE)))
        )

    def test_a_new_script_with_no_row_is_named(self):
        """The direction the defect actually arrives from.

        The case above damages the page; this one damages the tree, which is what really happens --
        somebody adds a script and nobody adds a row. Driven against the REAL row set rather than an
        empty one, so it cannot pass by everything looking missing at once."""
        arrival = "scripts/coord/just-landed.ps1"
        listed = t.inventory_paths(t.read(t.SCRIPTS_PAGE))
        missing = unlisted(shipped_scripts() | {arrival}, listed)
        self.assertEqual([arrival], missing, "a script with no row did NOT redden the check")

    def test_an_excluded_script_is_not_reported(self):
        """Proves EXCLUDED is consulted rather than every script happening to have a row.

        Driven through a synthetic entry because the real list is empty, which is the state this
        case has to keep measuring something in."""
        fake = "scripts/coord/never-shipped.ps1"
        shipped = shipped_scripts() | {fake}
        self.assertIn(fake, unlisted(shipped, set()))
        EXCLUDED[fake] = "planted by this test, and removed in the same method"
        try:
            self.assertNotIn(fake, unlisted(shipped, set()))
        finally:
            del EXCLUDED[fake]


class ThePatternCanTellARowFromAMention(unittest.TestCase):
    """Planted, for the capture direction. `test_the_landing_page_stays_a_front_door.py` proves the
    shared pattern fires on a row and declines a prose mention; these prove it hands back the PATH,
    and that a path in a later cell is not one."""

    def test_it_captures_the_path_and_not_the_row(self):
        row = "| `scripts/coord/claim.ps1` | Take, release or list a claim | [Coordination](x.md) |"
        self.assertEqual({"scripts/coord/claim.ps1"}, t.inventory_paths(row))

    def test_a_path_in_a_later_cell_is_a_mention(self):
        """`alloc.ps1`'s row names `seq_check.py` in its Does cell as the other half of a pair.

        Counting that as a row would let one script's prose satisfy a second script's row, and the
        completeness check would go quiet about the file that actually has none."""
        row = "| `scripts/coord/alloc.ps1` | `seq_check.py` is the other half | [x](y.md) |"
        self.assertEqual({"scripts/coord/alloc.ps1"}, t.inventory_paths(row))

    def test_it_declines_a_script_named_in_prose(self):
        prose = "The reaper is `scripts/worktree/prune-merged.ps1`, and it declines rather than guessing."
        with self.assertRaises(AssertionError):
            t.inventory_paths(prose)

    def test_an_empty_page_raises_rather_than_reporting_agreement(self):
        """The guard that makes every set comparison above meaningful."""
        with self.assertRaises(AssertionError):
            t.inventory_paths("")


if __name__ == "__main__":
    unittest.main()
