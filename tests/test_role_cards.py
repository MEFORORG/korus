"""Role cards: a seat's rules belong to the worktree, not to the session that was told them.

WHAT THIS EXISTS FOR. A session is told its seat in its first message. That instruction is an
ordinary user turn, so it competes with everything else in the context and it does not survive a
compaction. Binding the seat to the worktree instead, and injecting the card at SessionStart,
makes the rules present for every session that opens in that tree.

THE FAILURE THESE TESTS PIN. A card injected at CLAUDE.md weight is load-bearing, so a WRONG one
is worse than none. The resolution order must therefore be able to stay SILENT, and the silence
is what most of this file measures. A branch or directory name is a creation-time label that
nothing keeps current -- this repository has one right now whose name describes a question its
session answered in two minutes -- so no rung may read one.

THE LEAK HALF IS NOT DECORATION. These cards are derived from playbooks that came out of a private
vault, and that transfer has already put six user-home paths and two private artifact URLs into
this public tree past a gate that returned zero. Every absence check below is therefore paired
with a planted control that MUST fire, because a scan that reads nothing passes silently.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120

HOOK = t.REPO_ROOT / "scripts" / "hooks" / "role-card-inject.ps1"
SEATS_JSON = t.REPO_ROOT / "docs" / "roles" / "seats.json"
CARD_DIR = t.REPO_ROOT / "docs" / "roles"
SETTINGS_EXAMPLE = t.REPO_ROOT / ".claude" / "settings.example.json"
AGREEMENT = t.REPO_ROOT / "CLAUDE.md"

#: The marker and the injected copy. BOTH MUST BE GIT-IGNORED HERE, and the paths differ from the
#: ones a sibling project uses because this repository's ignore rules are the inverse of that
#: project's: `.claude/` is deliberately TRACKED here, and machine-local files are named `.local.`.
MARKER_RELPATH = ".claude/seat.local.txt"
ROLE_COPY_RELPATH = ".claude/ROLE.local.md"

#: The seat table in the working agreement governs the roster. SIX seats since 2026-09-19, when
#: the owner retired the REGULATOR and nothing replaced it. No seat now attributes a red check.
#:
#: SEVEN earlier the same day,
#: when the owner added `watchdog`: a seat that watches another seat work and files findings,
#: and does not do the work it watches. It did NOT inherit the Regulator, retired the same day:
#: no seat attributes a red check now.
#:
#: SIX from 2026-09-16, when the
#: owner added `special`: a seat for work outside the other five, which reads COMMON.md and stands by
#: rather than announcing on arrival.
#:
#: FIVE from 2026-09-12, when one of the six retired and NOTHING replaced it: the review gate it fed
#: was retired 2026-09-04, so a pull request merges on `gates (ubuntu-latest)` and
#: `gates (windows-latest)` with no review step.
#:
#: SIX before that, from 2026-09-10, when the Console retired and the Manager took its work. The
#: Manager arrived 2026-09-04 as an alternative to the Console, ran alongside it for six days, and is
#: now the only seat that writes a brief.
EXPECTED_SEATS = frozenset(
    {"manager", "builder", "steward", "lander", "special", "watchdog"}
)

#: Retired seats whose card page an ARCHIVE still links to. The page stays and becomes a tombstone.
#:
#: WHY THIS IS NOT A HOLE IN THE TWO TESTS BELOW. What must never happen is a retired seat resolving
#: to a card. That is enforced by the ROSTER, not by the file's absence: neither `console` nor
#: `reviewer` is live or an alias in `docs/roles/seats.json`, so `role-card-inject.ps1` prints the
#: retired message and never builds a card path at all. `test_a_retired_label_says_it_was_retired`
#: pins that behaviour.
#:
#: WHY THE FILES STAY. `docs/PLAYBOOKS.old.md` is a published archive, its bytes are hash-pinned in
#: `docs/_data/page-revisions.json`, and it links to `roles/console.card.md`. Deleting the target
#: breaks that link, and `test_internal_links_resolve` fails on exactly this. The same reasoning
#: `test_redirect_covers_every_page` is built on applies: a reader following an old link must not
#: get a 404, which reads as "this page never existed".
#:
#: `reviewer` JOINED ON 2026-09-12 for the same reason and one more: `docs/REVISIONS.md` is the
#: site's index of current-and-archived pages, and it carries a row pointing at both
#: `roles/reviewer.card.md` and its `.old.md` archive. The archive is hash-pinned like the Console's.
#:
#: IT IS A NAMED SET, NOT A PATTERN, for the reason `AUTHORED_VERBATIM` is: adding to it has to be a
#: visible diff somebody approves. A tombstone still carries every required section, stays inside
#: both budgets, and is read by the leak and ASCII scans -- it leaves only the two roster tests.
TOMBSTONE_SEATS = frozenset({"console", "reviewer", "regulator"})

#: Each card carries all five. A card missing one is a card that answers a question by omission.
REQUIRED_SECTIONS = (
    "What this seat owns",
    "What it must not do",
    "Its authority",
    "On arrival",
    "The full playbook",
)

CARD_MAX_LINES = 150

#: RAISED 2026-09-19 from 6 KB, by the Owner's pairing ruling, and the raise is recorded rather
#: than silent. That ruling gave the Lander and the Watchdog five standing blocks the other cards
#: do not carry: spawn in a pair, spawn the missing partner, wake by CCD messaging and never by
#: mail, read the partner's transcript, and a four-step escalation that replaces AskUserQuestion.
#: Measured after that edit: lander 7,176 bytes and watchdog 7,528, against a next-largest card of
#: 4,248. The old cap could only be met by deleting measured rules from the two seats the ruling
#: was about.
#:
#: CARD_MAX_LINES did NOT move. The budget's argument is unchanged -- one card is injected per
#: session, so the cost is one card -- and a cap raised to fit whatever was just written is not a
#: cap. Cut before raising this again.
#:
#: CORRECTED 2026-09-21: the line above read "CARD_MAX_LINES ... is now the binding cap for both:
#: 142 and 146 of 150". That flipped as the two cards grew. Measured at this commit with
#: `wc -l -c docs/roles/*.card.md`: lander 136 lines and 7,874 bytes, watchdog 137 and 8,055. So
#: lander has 14 lines of room against 318 bytes, and watchdog 13 against 137. BYTES bind for both,
#: and a reader trimming lines to make room would not gain any.
#:
#: The Lander card was compacted this commit and the Watchdog card was not, so watchdog is the
#: tighter of the two. Both sit near the cap because the 2026-09-19 ruling put five standing
#: blocks in them, so the next squeeze is a choice between raising this and moving a block to the
#: playbook. That is the Owner's call, not a test's.
CARD_MAX_BYTES = 8 * 1024


def seats() -> dict:
    return json.loads(t.read(SEATS_JSON))


def card_paths() -> list[Path]:
    return sorted(CARD_DIR.glob("*.card.md"))


class TheRosterIsGovernedByTheWorkingAgreement(unittest.TestCase):
    """CLAUDE.md governs, and `roles/README.md` is the copy that has drifted before.

    That README came across from a private vault and describes itself as a snapshot of a moving
    set, so a roster derived from it would hand a session rules for a seat that no longer exists.

    RETRACTED 2026-09-10. This docstring read "It still lists seven RETIRED seats as live", and
    that was false. Measured at `5de5594`, extracting that README's section *1a. The live seats* and
    grepping it for the seven retired names, the count was 1 and the match was the Console row's
    *Replaces the Dispatcher* -- a mention, not a live listing. Control over section *1b. The
    retired seats*: 2. CLAUDE.md, *The seats*, carries the command.
    """

    def test_seats_json_lists_exactly_the_live_seats(self):
        self.assertEqual(EXPECTED_SEATS, set(seats()["live"]))

    def test_every_live_seat_has_a_card(self):
        missing = sorted(s for s in EXPECTED_SEATS if not (CARD_DIR / f"{s}.card.md").is_file())
        self.assertEqual([], missing, f"live seats with no card: {missing}")

    def test_no_card_exists_for_a_seat_that_is_not_live(self):
        allowed = EXPECTED_SEATS | TOMBSTONE_SEATS
        stray = sorted(p.name for p in card_paths() if p.name[: -len(".card.md")] not in allowed)
        self.assertEqual([], stray, f"cards for seats that are not live: {stray}")

    def test_the_working_agreement_names_every_live_seat(self):
        """The roster in CLAUDE.md and the roster in seats.json cannot drift apart silently."""
        text = t.read(AGREEMENT).lower()
        absent = sorted(s for s in EXPECTED_SEATS if f"| {s} |" not in text)
        self.assertEqual([], absent, f"seats.json declares these but CLAUDE.md's table omits them: {absent}")

    def test_the_agreement_states_which_document_wins(self):
        """A reader who finds the two rosters disagreeing must be told which one governs."""
        text = t.read(AGREEMENT)
        self.assertIn("This table governs the roster.", text)


class RetiredSeatsResolveToNothingAndSayWhy(unittest.TestCase):
    """A retired label must not silently behave like an unknown one.

    Ten worktree records in the sibling project still declare seats that were retired. Resolving
    one to silence is correct; resolving it to silence WITHOUT saying it was retired sends the
    reader looking for a card that was deliberately removed.
    """

    def test_every_retired_seat_carries_a_reason(self):
        reasonless = sorted(k for k, v in seats()["retired"].items() if not str(v).strip())
        self.assertEqual([], reasonless, f"retired seats with no reason: {reasonless}")

    def test_no_retired_seat_is_also_live(self):
        both = sorted(set(seats()["retired"]) & set(seats()["live"]))
        self.assertEqual([], both, f"declared retired AND live: {both}")

    def test_no_retired_seat_has_a_card(self):
        present = sorted(
            s
            for s in seats()["retired"]
            if s not in TOMBSTONE_SEATS and (CARD_DIR / f"{s}.card.md").is_file()
        )
        self.assertEqual([], present, f"retired seats that still have a card: {present}")

    def test_every_tombstone_page_reads_as_one(self):
        """The carve-out pays for itself: a tombstone must announce the retirement and the successor.

        Without this the exemption would let a retired seat's LIVE card sit on the site unchanged,
        which is the failure the two tests above exist to prevent.
        """
        offenders = []
        for seat in sorted(TOMBSTONE_SEATS):
            path = CARD_DIR / f"{seat}.card.md"
            if not path.is_file():
                offenders.append(f"{seat}: no tombstone page at {path.name}")
                continue
            text = t.read(path)
            if "RETIRED" not in text:
                offenders.append(f"{path.name} does not say RETIRED")
            if not any(f"{live}.card.md" in text for live in EXPECTED_SEATS):
                offenders.append(f"{path.name} names no live seat's card to go to instead")
        self.assertEqual([], offenders, "\n  ".join(offenders))

    def test_a_tombstone_seat_is_declared_retired_in_the_roster(self):
        """The exemption may not be used to keep a LIVE seat's card out of the roster tests."""
        undeclared = sorted(TOMBSTONE_SEATS - set(seats()["retired"]))
        self.assertEqual([], undeclared, f"tombstoned but not retired in seats.json: {undeclared}")

    def test_a_tombstone_seat_is_not_live_and_is_not_an_alias(self):
        """The whole safety argument: the hook can never build a card path for a tombstone."""
        reachable = sorted(
            TOMBSTONE_SEATS & (set(seats()["live"]) | set(seats()["aliases"].values()))
        )
        self.assertEqual([], reachable, f"tombstoned seats the hook could still resolve: {reachable}")


class TheAliasMapCollapsesDrift(unittest.TestCase):
    """46 distinct role strings for a six-seat roster were counted in the sibling project.

    Eight of them were spellings of one seat. An alias map is the only thing that lets an
    instrument group by seat, because 46 labels do not group.
    """

    def test_every_alias_resolves_to_a_live_seat(self):
        live = set(seats()["live"])
        broken = sorted(f"{k} -> {v}" for k, v in seats()["aliases"].items() if v not in live)
        self.assertEqual([], broken, f"aliases pointing at no live seat: {broken}")

    def test_the_known_builder_spellings_all_collapse(self):
        aliases = seats()["aliases"]
        for spelling in ("builder1", "builder2", "builder-2", "builder3", "BUILDER1", "Builder"):
            with self.subTest(spelling=spelling):
                self.assertEqual("builder", aliases.get(spelling.lower(), spelling.lower()))

    def test_an_alias_never_shadows_a_live_seat_name(self):
        """`builder` must not appear as an alias key. A canonical name resolves to itself."""
        shadow = sorted(set(seats()["aliases"]) & set(seats()["live"]))
        self.assertEqual([], shadow, f"alias keys that are already canonical seat names: {shadow}")


class EveryCardStaysWithinItsBudget(unittest.TestCase):
    """A budget that is not enforced drifts.

    Only one card is ever injected, so the cost to a session is one card. The cap is what keeps
    that true as cards are edited by sessions that cannot see the other six.
    """

    def test_no_card_exceeds_the_line_cap(self):
        over = [
            f"{p.name}: {len(t.read(p).splitlines())} lines"
            for p in card_paths()
            if len(t.read(p).splitlines()) > CARD_MAX_LINES
        ]
        self.assertEqual([], over, f"cards over {CARD_MAX_LINES} lines: {over}")

    def test_no_card_exceeds_the_byte_cap(self):
        over = [f"{p.name}: {p.stat().st_size} bytes" for p in card_paths() if p.stat().st_size > CARD_MAX_BYTES]
        self.assertEqual([], over, f"cards over {CARD_MAX_BYTES} bytes: {over}")

    def test_the_two_copies_of_the_byte_cap_agree(self):
        """The hook's cap DECIDES; this constant only reports. Nothing bound them until 2026-09-19.

        A card between the two numbers passes the suite and is then refused by the hook, so the
        seat runs with no card and the only notice is one line in a SessionStart banner. Found by
        raising this constant to 8 KB and watching a 7,176-byte card go uninjected against the
        hook's 6 KB.
        """
        import re

        m = re.search(r"^\s*\$maxBytes\s*=\s*(\d+)\s*\*\s*(\d+)\s*$", t.read(HOOK), re.M)
        self.assertIsNotNone(
            m,
            "no `$maxBytes = <n> * <n>` line in role-card-inject.ps1. If the hook stopped "
            "enforcing a cap, this test measures nothing and must be rewritten, not deleted.",
        )
        self.assertEqual(
            int(m.group(1)) * int(m.group(2)),
            CARD_MAX_BYTES,
            "role-card-inject.ps1 and CARD_MAX_BYTES disagree. The HOOK is the one that decides "
            "whether a card loads, so change it first and follow with this constant.",
        )

    def test_every_card_carries_every_required_section(self):
        offenders = []
        for p in card_paths():
            text = t.read(p)
            for section in REQUIRED_SECTIONS:
                if section not in text:
                    offenders.append(f"{p.name} is missing '{section}'")
        self.assertEqual([], offenders, "\n  ".join(offenders))

    def test_every_card_names_the_marker_that_selected_it(self):
        """A reader who did not expect this card must be able to find out why it arrived."""
        silent = [p.name for p in card_paths() if MARKER_RELPATH not in t.read(p)]
        self.assertEqual([], silent, f"cards that do not say what selected them: {silent}")

    def test_the_card_scan_actually_reads_cards(self):
        """The empty-corpus guard. Every absence test above passes trivially against no cards."""
        self.assertGreaterEqual(len(card_paths()), len(EXPECTED_SEATS))


class NoCardCarriesPrivateContent(unittest.TestCase):
    """These cards derive from a private vault, and that transfer has leaked twice already.

    Each check below is paired with a planted control in
    `test_each_leak_pattern_fires_on_a_planted_example`. Without it a broken pattern and a clean
    corpus are indistinguishable, which is exactly how six user-home paths reached this tree.
    """

    PATTERNS = {
        "artifact URL": r"claude\.ai/(?:code/)?artifact",
        "bare UUID": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "user home path": r"(?:[A-Za-z]:[\\/]Users|/home|/Users)[\\/][A-Za-z]",
    }

    def test_no_card_carries_a_leak_pattern(self):
        import re

        offenders = []
        for p in card_paths():
            text = t.read(p)
            for label, pattern in self.PATTERNS.items():
                for m in re.finditer(pattern, text, re.I):
                    offenders.append(f"{p.name}: {label}: {m.group(0)!r}")
        self.assertEqual([], offenders, "\n  ".join(offenders))

    def test_each_leak_pattern_fires_on_a_planted_example(self):
        """The armed half. A pattern that matches nothing would pass the test above in silence."""
        planted = {
            "artifact URL": "see https://claude.ai/code/artifact/<uuid>",
            "bare UUID": "id aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee here",
            # `example` is one of the placeholder names scripts/security/scan_forbidden.py
            # allowlists. A name it does not allowlist makes THIS file trip the leak gate, which is
            # how that was found: the planted control fired the real gate, not just this pattern.
            "user home path": r"C:\Users\example\vault",
        }
        for label, pattern in self.PATTERNS.items():
            with self.subTest(label=label):
                self.assertRegex(planted[label], pattern)

    def test_no_card_points_at_a_vault_absolute_path(self):
        offenders = [p.name for p in card_paths() if "<vault>/" not in t.read(p) and "vault/" in t.read(p).lower()]
        self.assertEqual([], offenders, f"cards naming a vault path outside the <vault> placeholder: {offenders}")

    def test_every_card_is_ascii(self):
        offenders = []
        for p in card_paths():
            for n, line in enumerate(t.read(p).splitlines(), 1):
                if any(ord(c) > 127 for c in line):
                    offenders.append(f"{p.name}:{n}")
        self.assertEqual([], offenders, f"non-ASCII in cards: {offenders}")


class TheMarkerCannotRideIntoACommit(unittest.TestCase):
    """Both generated paths must be ignored BY THIS REPOSITORY'S OWN RULES, which are unusual.

    `.gitignore` states at the top of the file that `.claude/` is DELIBERATELY NOT IGNORED, and
    that anything tracked under it must carry `.example.` in its name. Machine-local files are
    ignored by `*.local.*` instead. A path copied from a project that ignores `.claude/**` would
    be untracked here and could be committed by a blanket stage.
    """

    def check_ignored(self, relpath: str) -> bool:
        return (
            subprocess.run(
                ["git", "check-ignore", "-q", relpath],
                cwd=t.REPO_ROOT,
                capture_output=True,
                timeout=TIMEOUT_SECONDS,
            ).returncode
            == 0
        )

    def test_the_marker_is_ignored(self):
        self.assertTrue(self.check_ignored(MARKER_RELPATH), f"{MARKER_RELPATH} is not ignored")

    def test_the_injected_copy_is_ignored(self):
        self.assertTrue(self.check_ignored(ROLE_COPY_RELPATH), f"{ROLE_COPY_RELPATH} is not ignored")

    def test_the_check_can_report_a_path_that_is_not_ignored(self):
        """The armed half. `check_ignored` returning True for everything would pass both tests."""
        self.assertFalse(self.check_ignored("README.md"))

    def test_a_marker_without_a_trailing_segment_would_not_be_ignored(self):
        """`*.local.*` needs a segment AFTER `.local.`, so `.claude/seat.local` is TRACKED.

        This is the near-miss that makes the chosen filename look arbitrary. It is not.
        """
        self.assertFalse(self.check_ignored(".claude/seat.local"))


class TheHookIsWiredAndNeverBreaksATurn(unittest.TestCase):
    def test_the_hook_exists(self):
        self.assertTrue(HOOK.is_file(), f"{HOOK} is missing")

    def test_the_example_settings_wire_it_at_session_start(self):
        wired = json.loads(t.read(SETTINGS_EXAMPLE))
        commands = [
            h.get("command", "")
            for entry in wired.get("hooks", {}).get("SessionStart", [])
            for h in entry.get("hooks", [])
        ]
        self.assertTrue(
            any("role-card-inject.ps1" in c for c in commands),
            f"SessionStart does not run the hook; found {commands}",
        )

    def test_the_example_settings_stay_inert(self):
        """An example file that could be loaded is a control that looks installed.

        `.gitignore` states the rule: anything tracked under `.claude/` carries `.example.`, and
        the harness loads `settings.json` and `settings.local.json` only.
        """
        self.assertIn(".example.", SETTINGS_EXAMPLE.name)


class TheHookNeverGuessesASeat(unittest.TestCase):
    """The resolution order must be able to end in SILENCE.

    A wrong card is injected at the weight of the working agreement, so it outranks the thing a
    session should have been reading. Silence costs one printed command; a wrong card costs a
    session that confidently follows the wrong rules.
    """

    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so the hook cannot be executed here")
        self.pwsh: str = pwsh
        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-rolecard-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".claude").mkdir(parents=True)

    def run_hook(self, *, marker: str | None = None, env_seat: str | None = None):
        if marker is not None:
            (self.root / ".claude" / "seat.local.txt").write_text(marker, encoding="ascii")
        env = dict(os.environ)
        env.pop("KORUS_SEAT", None)
        if env_seat is not None:
            env["KORUS_SEAT"] = env_seat
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(HOOK), "-WorktreeRoot", str(self.root)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(self.root),
            timeout=TIMEOUT_SECONDS,
        )

    def test_a_missing_marker_exits_zero_and_injects_no_card(self):
        r = self.run_hook()
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotIn("What this seat owns", r.stdout)

    def test_a_missing_marker_prints_the_command_that_sets_one(self):
        r = self.run_hook()
        self.assertIn("seat.local.txt", r.stdout)

    def test_an_unknown_label_exits_zero_and_injects_no_card(self):
        r = self.run_hook(marker="archivist")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotIn("What this seat owns", r.stdout)

    def test_a_retired_label_says_it_was_retired(self):
        retired = next(iter(seats()["retired"]))
        r = self.run_hook(marker=retired)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("retired", r.stdout.lower())

    def test_every_retired_label_says_it_was_retired_and_injects_no_card(self):
        """One label per retired spelling, because a spelling left out reads as a typo.

        `console1` was measured returning "MATCHES NO SEAT" before it got its own row, which sends
the reader looking for a card rather than telling them the seat went away. Another seat's
        five spellings were added on 2026-09-12 for the same reason.
        """
        for label in sorted(seats()["retired"]):
            with self.subTest(label=label):
                r = self.run_hook(marker=label)
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertIn("retired", r.stdout.lower())
                self.assertNotIn("What this seat owns", r.stdout)

    def test_a_retired_reviewer_marker_resolves_to_no_card(self):
        """The Reviewer retired 2026-09-12 with no successor, and every spelling must say so.

        Until that day `reviewer`, `reviewer1`, `reviewer2`, `reviewer-1`, `review` and `reviewers`
        all resolved to a LIVE card telling the session to read a diff and post findings. A card is
        injected at the weight of the working agreement, so that card would outrank the roster.
        """
        for label in ("reviewer", "reviewer1", "reviewer2", "reviewer-1", "review", "reviewers"):
            with self.subTest(label=label):
                r = self.run_hook(marker=label)
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertIn("retired", r.stdout.lower())
                self.assertNotIn("What this seat owns", r.stdout)

    def test_a_branch_that_looks_like_a_seat_yields_no_card(self):
        """No rung reads a branch or directory name. This is the trap rung, and it stays unbuilt.

        The temporary root is created inside a directory named for a seat, which is the strongest
        form of the hint a name-reading rung would have taken.
        """
        seatish = self.root / "claude" / "lander-x"
        (seatish / ".claude").mkdir(parents=True)
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(HOOK), "-WorktreeRoot", str(seatish)],
            input="{}",
            capture_output=True,
            text=True,
            env={k: v for k, v in os.environ.items() if k != "KORUS_SEAT"},
            cwd=str(seatish),
            timeout=TIMEOUT_SECONDS,
        )
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertNotIn("What this seat owns", r.stdout)

    def test_the_hook_source_reads_no_branch_name(self):
        """Pins the absence at the source, not only in behaviour.

        The behavioural test above passes against a hook that reads a branch and happens to find
        nothing. This one fails if the rung is ever added.
        """
        source = t.strip_ps_comments(t.read(HOOK))
        for forbidden in ("rev-parse", "symbolic-ref", "git branch"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


class TheHookResolvesInOrder(unittest.TestCase):
    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so the hook cannot be executed here")
        self.pwsh: str = pwsh
        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-rolecard-order-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".claude").mkdir(parents=True)

    def run_hook(self, *, marker=None, env_seat=None):
        if marker is not None:
            (self.root / ".claude" / "seat.local.txt").write_text(marker, encoding="ascii")
        env = dict(os.environ)
        env.pop("KORUS_SEAT", None)
        if env_seat is not None:
            env["KORUS_SEAT"] = env_seat
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(HOOK), "-WorktreeRoot", str(self.root)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(self.root),
            timeout=TIMEOUT_SECONDS,
        )

    def test_a_marker_injects_that_seats_card(self):
        r = self.run_hook(marker="steward")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("What this seat owns", r.stdout)
        self.assertIn("Steward", r.stdout)

    def test_a_marker_is_case_and_space_insensitive(self):
        r = self.run_hook(marker="  Steward\n")
        self.assertIn("Steward", r.stdout)

    def test_an_alias_injects_the_canonical_card(self):
        r = self.run_hook(marker="builder2")
        self.assertIn("Builder", r.stdout)

    def test_the_env_var_is_used_when_no_marker_exists(self):
        r = self.run_hook(env_seat="lander")
        self.assertIn("Lander", r.stdout)

    def test_the_marker_outranks_the_env_var(self):
        r = self.run_hook(marker="steward", env_seat="lander")
        self.assertIn("Steward", r.stdout)
        self.assertNotIn("| Lander --", r.stdout)

    def test_the_card_is_written_where_a_compacted_session_can_re_read_it(self):
        self.run_hook(marker="steward")
        copy = self.root / ".claude" / "ROLE.local.md"
        self.assertTrue(copy.is_file(), "the hook did not write the re-readable copy")
        self.assertIn("What this seat owns", copy.read_text(encoding="utf-8"))


class RetiredRulesDoNotSurviveInACard(unittest.TestCase):
    """A retired SEAT resolving to silence is already guarded above. A retired RULE is not.

    The distinction cost something. Two cards reached `main` asserting the `reviewed` label as a
    live merge gate, which the owner removed on 2026-09-04. `roles/COMMON.md`, `roles/LANDER.md`,
    `roles/BUILDER.md` and `roles/MANAGER.md` all carry it as a RETIRED row; the cards carried it
    as a rule, and one of them as a MUST NOT.

    That direction is the expensive one: a Lander reading its own card holds a merge it is entitled
    to make, and the card supplies an authoritative-sounding reason. `docs/ROLE-CARDS.md` names the
    mechanism -- a card is injected at SessionStart, so it outranks the document that corrects it.

    NARROW ON PURPOSE. This guards one retired rule by name rather than pretending to a general
    test, because no registry of retired rules exists to check against. Widen it by adding a row
    when the next rule retires, and the pair below keeps it honest meanwhile.
    """

    #: (pattern, why it is retired). Matched case-insensitively, line by line.
    RETIRED = [
        ("reviewed", "the `reviewed` merge gate was removed 2026-09-04; an unlabelled PR merges"),
    ]

    def _live_hits(self, text: str) -> list[str]:
        """Lines naming a retired rule without marking it retired."""
        out = []
        for line in text.splitlines():
            low = line.lower()
            for pattern, _ in self.RETIRED:
                if pattern in low and "retired" not in low and "read *\"" not in line:
                    out.append(line.strip())
        return out

    def test_no_card_asserts_a_retired_rule_as_live(self):
        offenders = {}
        for path in card_paths():
            hits = self._live_hits(path.read_text(encoding="utf-8"))
            if hits:
                offenders[path.name] = hits
        self.assertEqual(
            {},
            offenders,
            "a role card names a retired rule without marking it retired:\n"
            + "\n".join(f"  {name}: {h}" for name, hs in offenders.items() for h in hs)
            + "\n\nThe reasons: "
            + "; ".join(why for _, why in self.RETIRED),
        )

    def test_the_scan_fires_on_the_shape_it_exists_to_catch(self):
        """The positive control. Without it, a pattern that matches nothing passes silently."""
        planted = "- **Merge an unlabelled PR.** `reviewed` is the gate, so re-check after any push."
        self.assertTrue(
            self._live_hits(planted),
            "the scan did not fire on the exact line that shipped to main, so it guards nothing",
        )

    def test_the_scan_accepts_a_correctly_retracted_line(self):
        """The negative arm. A retraction names the rule on purpose and must not be flagged."""
        retracted = "- **Wait for a `reviewed` label. RETIRED 2026-09-04.** An unlabelled PR merges."
        self.assertFalse(
            self._live_hits(retracted),
            "the scan flagged a correct retraction, which would make retracting in place impossible",
        )


if __name__ == "__main__":
    unittest.main()
