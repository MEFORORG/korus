"""Seat declaration: the moment a session learns which seat it holds.

WHAT THIS EXISTS FOR. `role-card-inject.ps1` injects a card at SessionStart when a marker already
exists, and `scripts/coord/seat.ps1 -Declare` writes that marker. Nothing connected the two. A
harness-created worktree is born seatless, the seat arrives as an ordinary chat turn, and the card
never loads for the session that was actually told its seat.

WHAT THE WIDENING IS, AND WHAT IT IS NOT. Owner ruling 2026-09-19: a prompt whose WHOLE text is a
roster label is a DECLARATION, not a guess. `special` declares. `claude/special-d4c4b4` does not,
and neither does `I think the special seat should handle this`. The line is exactness, and the
tests below are mostly about where it falls.

THE INVARIANT THIS MUST NOT BREAK. `TheHookNeverGuessesASeat` in `tests/test_role_cards.py` pins
that no rung reads a branch or directory name, because a card is injected at working-agreement
weight and a WRONG card outranks the document the session should be reading. The widening adds a
rung that reads the PROMPT. It does not add one that reads a name, and `test_the_hook_reads_no_ref`
below re-pins that for the new source.

EVERY ABSENCE CHECK IS PAIRED WITH A PLANTED CONTROL. A scan that reads nothing passes silently.
Six user-home paths and two private artifact URLs reached `main` here past a gate that returned
zero, twice, which is why a bare zero is not reportable in this tree.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

TIMEOUT_SECONDS = 120

HOOK = t.REPO_ROOT / "scripts" / "hooks" / "seat-declare.ps1"
CARD_HOOK = t.REPO_ROOT / "scripts" / "hooks" / "role-card-inject.ps1"
SEATS_JSON = t.REPO_ROOT / "docs" / "roles" / "seats.json"
SKILL = t.REPO_ROOT / ".claude" / "skills" / "seat" / "SKILL.md"
SETTINGS_EXAMPLE = t.REPO_ROOT / ".claude" / "settings.example.json"

MARKER_RELPATH = ".claude/seat.local.txt"

#: A phrase that appears in every card and in no refusal, so it separates "a card was injected"
#: from "the hook explained why it did not".
CARD_TOKEN = "What this seat owns"


def seats() -> dict:
    return json.loads(SEATS_JSON.read_text(encoding="utf-8"))


class SeatDeclarationHookBase(unittest.TestCase):
    """Shared harness. Each test gets a throwaway worktree root with no marker in it."""

    def setUp(self):
        pwsh = t.find_pwsh()
        if not pwsh:
            self.skipTest("pwsh is not on PATH, so the hook cannot be executed here")
        self.pwsh: str = pwsh
        self.tmp = tempfile.TemporaryDirectory(prefix="ccx-seatdecl-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".claude").mkdir(parents=True)

    def run_hook(self, prompt: str, *, marker: str | None = None, raw_stdin: str | None = None):
        """Run the hook with `prompt` as the user's whole turn.

        `raw_stdin` overrides the payload entirely, for the malformed-input tests.
        """
        if marker is not None:
            (self.root / ".claude" / "seat.local.txt").write_text(marker, encoding="ascii")
        payload = raw_stdin if raw_stdin is not None else json.dumps({"prompt": prompt})
        env = dict(os.environ)
        env.pop("KORUS_SEAT", None)
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(HOOK), "-WorktreeRoot", str(self.root)],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(self.root),
            timeout=TIMEOUT_SECONDS,
        )

    def marker(self) -> str | None:
        p = self.root / ".claude" / "seat.local.txt"
        return p.read_text(encoding="utf-8").strip() if p.exists() else None


class AWholePromptRosterLabelDeclaresTheSeat(SeatDeclarationHookBase):
    """The widening itself. An exact roster label, alone on the turn, is a declaration."""

    def test_a_bare_live_seat_name_writes_the_marker(self):
        r = self.run_hook("special")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("special", self.marker())

    def test_a_bare_live_seat_name_injects_the_card_in_the_same_turn(self):
        """The whole point. A marker with no card is the state this change exists to end."""
        r = self.run_hook("special")
        self.assertIn(CARD_TOKEN, r.stdout)

    def test_every_live_seat_declares_from_its_own_bare_name(self):
        for seat in sorted(seats()["live"]):
            with self.subTest(seat=seat):
                self.setUp()
                r = self.run_hook(seat)
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertEqual(seat, self.marker())

    def test_an_alias_resolves_to_its_canonical_seat(self):
        r = self.run_hook("adhoc")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("special", self.marker())

    def test_case_and_surrounding_whitespace_do_not_matter(self):
        r = self.run_hook("  SPECIAL \n")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("special", self.marker())

    def test_the_explicit_command_form_declares_too(self):
        r = self.run_hook("/seat special")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("special", self.marker())


class NothingShortOfAnExactMatchDeclaresAnything(SeatDeclarationHookBase):
    """Where the line falls. These are the controls for the widening.

    Without them the rule reads "a prompt mentioning a seat sets that seat", which is the guess the
    whole subsystem is built to refuse. Each case below MUST leave no marker.
    """

    def test_a_prompt_that_merely_contains_a_seat_name_declares_nothing(self):
        r = self.run_hook("I think the special seat should handle this")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIsNone(self.marker())
        self.assertNotIn(CARD_TOKEN, r.stdout)

    def test_a_branch_name_containing_a_seat_declares_nothing(self):
        """The trap rung, restated for the prompt. A branch name is still a name."""
        r = self.run_hook("claude/special-d4c4b4")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIsNone(self.marker())

    def test_a_seat_name_with_a_trailing_word_declares_nothing(self):
        r = self.run_hook("special seat")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIsNone(self.marker())

    def test_a_question_about_a_seat_declares_nothing(self):
        r = self.run_hook("what does the lander do?")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIsNone(self.marker())

    def test_an_unknown_single_word_declares_nothing(self):
        r = self.run_hook("archivist")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIsNone(self.marker())
        self.assertNotIn(CARD_TOKEN, r.stdout)

    def test_an_ordinary_prompt_is_silent_rather_than_chatty(self):
        """A hook that comments on every turn gets ignored, and then its real output is missed."""
        r = self.run_hook("please rebase this branch onto main")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("", r.stdout.strip())


class ARetiredLabelSaysSoAndSetsNothing(SeatDeclarationHookBase):
    """A retired label resolves to no card ANYWHERE, and must not reach the marker either.

    Silence would send the reader looking for a card that was deliberately removed.
    """

    def test_every_retired_label_refuses_and_writes_no_marker(self):
        for label in sorted(seats()["retired"]):
            with self.subTest(label=label):
                self.setUp()
                r = self.run_hook(label)
                self.assertEqual(0, r.returncode, r.stderr)
                self.assertIn("retired", r.stdout.lower())
                self.assertIsNone(self.marker())
                self.assertNotIn(CARD_TOKEN, r.stdout)


class TheHookNeverFailsATurn(SeatDeclarationHookBase):
    """A UserPromptSubmit hook that fails can block the user's prompt outright."""

    def test_malformed_stdin_exits_zero(self):
        r = self.run_hook("", raw_stdin="not json at all {{{")
        self.assertEqual(0, r.returncode, r.stderr)

    def test_empty_stdin_exits_zero(self):
        r = self.run_hook("", raw_stdin="")
        self.assertEqual(0, r.returncode, r.stderr)

    def test_a_payload_with_no_prompt_key_exits_zero(self):
        r = self.run_hook("", raw_stdin=json.dumps({"session_id": "x"}))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIsNone(self.marker())

    def test_a_worktree_with_no_claude_directory_exits_zero_and_still_declares(self):
        """The hook runs in every worktree, including one that has never held a marker."""
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        env = dict(os.environ)
        env.pop("KORUS_SEAT", None)
        r = subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(HOOK), "-WorktreeRoot", str(bare)],
            input=json.dumps({"prompt": "special"}),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(bare),
            timeout=TIMEOUT_SECONDS,
        )
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(
            "special",
            (bare / ".claude" / "seat.local.txt").read_text(encoding="utf-8").strip(),
        )


class ReDeclaringIsIdempotent(SeatDeclarationHookBase):
    """A seat already set must not re-inject its card on every later prompt."""

    def test_the_same_seat_again_is_silent(self):
        r = self.run_hook("special", marker="special")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("special", self.marker())
        self.assertNotIn(CARD_TOKEN, r.stdout)

    def test_a_different_seat_replaces_the_marker_and_says_it_changed(self):
        r = self.run_hook("lander", marker="special")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual("lander", self.marker())
        self.assertIn("changed", r.stdout.lower())
        self.assertIn(CARD_TOKEN, r.stdout)


class TheHookReadsNoRef(unittest.TestCase):
    """The invariant the widening must not break, re-pinned against the new source.

    `test_role_cards.py` rejects hook source containing `rev-parse`, `symbolic-ref` or `git branch`.
    The same ban applies here: this hook reads the PROMPT, and a prompt is something the user typed
    this turn. A branch name is a creation-time label that nothing keeps current.
    """

    FORBIDDEN = ("rev-parse", "symbolic-ref", "git branch", "--show-current")

    def test_the_source_reads_no_branch_or_ref(self):
        src = t.ps_source(HOOK)
        for needle in self.FORBIDDEN:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, src)

    def test_the_control_fires_on_a_source_that_does_read_one(self):
        """Without this, a scan over an empty or unreadable file passes identically."""
        planted = "$b = & git rev-parse --abbrev-ref HEAD\n"
        hits = [n for n in self.FORBIDDEN if n in planted]
        self.assertIn("rev-parse", hits)


class TheSeatSkillIsInstalledAndShaped(unittest.TestCase):
    """The `/seat` command itself. It is the explicit half of the same feature."""

    def test_the_skill_file_exists(self):
        self.assertTrue(SKILL.is_file(), f"{SKILL} is missing")

    def test_the_skill_declares_itself_user_invocable(self):
        head = SKILL.read_text(encoding="utf-8")[:600]
        self.assertIn("user-invocable: true", head)

    def test_the_skill_names_all_three_verification_grades(self):
        """A skill that declares a seat and does not check the card is the gap this closes."""
        text = SKILL.read_text(encoding="utf-8").lower()
        for grade in ("marker set", "card emitted", "context set"):
            with self.subTest(grade=grade):
                self.assertIn(grade, text)

    def test_the_skill_requires_a_readback(self):
        """The only grade that can fail while the other two pass."""
        self.assertIn("readback", SKILL.read_text(encoding="utf-8").lower())

    def test_the_skill_is_ascii(self):
        raw = SKILL.read_bytes()
        bad = [(i, b) for i, b in enumerate(raw) if b > 0x7F]
        self.assertEqual([], bad, f"non-ASCII bytes at {bad[:5]}")


class TheHookIsWiredInTheExample(unittest.TestCase):
    """Merging a hook does not install one. The example must show the wiring.

    PR 130 removed the `UserPromptSubmit` key entirely when `context-budget.ps1` went, so this
    creates the key rather than editing it.
    """

    def settings(self) -> dict:
        return json.loads(SETTINGS_EXAMPLE.read_text(encoding="utf-8"))

    def test_the_example_has_a_user_prompt_submit_key(self):
        self.assertIn("UserPromptSubmit", self.settings().get("hooks", {}))

    def test_the_example_wires_this_hook(self):
        self.assertIn("seat-declare.ps1", SETTINGS_EXAMPLE.read_text(encoding="utf-8"))

    def test_the_control_shows_the_other_keys_are_still_there(self):
        """Without this, a settings file emptied by accident passes the test above by luck."""
        hooks = self.settings().get("hooks", {})
        for key in ("SessionStart", "PreToolUse", "Stop"):
            with self.subTest(key=key):
                self.assertIn(key, hooks)


class TheCardEmittedGradeCanActuallyFail(SeatDeclarationHookBase):
    """The planted control for the verification itself.

    A check that cannot go red measures nothing. This proves the card-emitted grade distinguishes
    an injected card from a missing one, using the injector the skill calls.
    """

    def run_card_hook(self, marker: str, *, repo_root: Path | None = None):
        (self.root / ".claude" / "seat.local.txt").write_text(marker, encoding="ascii")
        env = dict(os.environ)
        env.pop("KORUS_SEAT", None)
        return subprocess.run(
            [self.pwsh, "-NoProfile", "-File", str(CARD_HOOK), "-WorktreeRoot", str(self.root)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(self.root),
            timeout=TIMEOUT_SECONDS,
        )

    def test_a_real_seat_emits_the_card_token(self):
        r = self.run_card_hook("special")
        self.assertIn(CARD_TOKEN, r.stdout)

    def test_an_unknown_seat_does_not_emit_the_card_token(self):
        """The control. Same instrument, a subject that must NOT satisfy it."""
        r = self.run_card_hook("archivist")
        self.assertNotIn(CARD_TOKEN, r.stdout)


if __name__ == "__main__":
    unittest.main()
