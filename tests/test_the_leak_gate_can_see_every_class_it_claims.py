"""Every structural detector in the leak gate, proved against a line it MUST flag and one it must not.

THE DEFECT THIS EXISTS FOR, and it is a measured one rather than a worry. Commit `a3df144` brought
two private artifact URLs into the tracked tree, at `roles/LANDER.md:4027` and
`roles/retired/PM.md:200`. The gate ran over both and exited `0`. They came out again in PR #48
because a person read the diff -- the same review the gate exists to make cheaper, doing the entire
job unaided. Nothing about that run looked wrong: the receipt said `structural=8`, the scan counted
every file, and the exit code was the one a clean tree produces.

That is the failure this directory is about, in the one script whose only job is to prevent it.
`docs/LEAK-GATE.md` states the rule the gate could not keep for itself:

    A green gate is evidence only if you have proved it can SEE that class.

Until this file existed, `scripts/security/scan_forbidden.py` had no test of any kind. Every green
run it had ever produced was unfalsifiable -- a detector that never compiled, a regex quietly
narrowed, a whole branch deleted: all three exit `0` and print a healthy receipt.

TWO CORPORA PER DETECTOR, BECAUSE ONE PROVES HALF. A detector hard-wired to fire passes the planted
case perfectly. A detector hard-wired to stay silent -- or one whose reader found no files -- passes
the clean case perfectly. Only running both rules out both, which is the rule
`test_every_validation_check_is_proven_by_a_control.py` already imposes on `scripts/validation/`.
This file brings `scripts/security/` under the same one.

THE TABLE IS DRIVEN OFF THE DETECTOR COUNT, so tomorrow's detector is covered the day it is added.
`_STRUCTURAL_COUNT` is the number the gate prints on its own receipt; a detector added without a
planted line makes `TheTableCoversEveryDetectorTheGateClaims` fail, rather than quietly shipping a
column nobody proved. A control pinned to one detector is a control the next detector is written
without.

EVERY FIXTURE IS ASSEMBLED FROM FRAGMENTS, and that is load-bearing rather than a matter of taste.
The gate scans this repository, `tests/` included. A planted home path or artifact URL written as
one literal would make this file a hit -- the control would break the gate it exists to prove, and
the obvious repair is an allowlist line, which is a per-line veto over every other detector on that
line. So no single source line here is a violation; only the joined value is.
`ThePlantedFixturesNeverBecomeALeakThemselves` keeps that true under editing, instead of trusting
that whoever adds the next fixture notices.

AND IT HAS CAUGHT THREE AUTHORS ON THAT RULE, which is why it is a control and not a convention.
The artifact fixture that exercised half a character class; a docstring quoting measured output
with a live address in it; a comment explaining why a home path must never be written as one
literal, which contained one. Every time the author was writing ABOUT the detector. That is the
pattern worth naming: prose describing a detector wants to contain an example of what the detector
catches, and the wanting does not announce itself.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

GATE = t.REPO_ROOT / "scripts" / "security" / "scan_forbidden.py"


def load_gate():
    """Import the gate by path. It is a script, not a package, and deliberately has no __init__."""
    spec = importlib.util.spec_from_file_location("ccx_scan_forbidden", GATE)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {GATE} as a module -- the control cannot measure it")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ccx_scan_forbidden"] = module
    spec.loader.exec_module(module)
    return module


#: An obviously synthetic UUID: version-4 shaped, and deterministic, so a failure names a detector
#: rather than a random draw.
#:
#: IT SPANS a-f ON PURPOSE, AND THE FIRST VERSION OF THIS FILE DID NOT. The fixture shipped as
#: `00000000-0000-4000-8000-000000000000` -- every character a decimal digit. So the `a-f` half of
#: the detector's `[0-9a-f]` class was exercised zero times, and narrowing the detector to `[0-9]`
#: left all seven cases here green while the gate went blind to every real artifact URL. Measured:
#: the narrowed gate catches the old fixture and MISSES a real-shaped id.
#:
#: Both URLs PR #48 removed contain hex letters, and an all-digit v4 UUID has a probability of
#: roughly 1 in 2.7 million -- so the single input the control proved was the one input that never
#: arrives. That is this file's own stated failure, committed inside the file that exists to
#: prevent it: a green run that proves nothing about the class it names.
#:
#: `.upper()` must also CHANGE it, or the uppercase row is a duplicate of the row above it and
#: `re.IGNORECASE` is unproven too. `TheFixtureSpansTheClassItProves` pins both properties, so the
#: lesson survives the next person editing this constant.
FAKE_UUID = "abcdefab-cdef-4abc-8def-abcdefabcdef"

#: The OS account name planted in the home-path fixture, shared with `FIRES` so the control
#: that proves the hit stays bare asserts on the value the fixture actually plants. A second
#: copy here could drift out of step with the table and still pass, which is the exact shape
#: of failure this file exists to refuse.
FAKE_ACCOUNT = "ccxleak"

#: The other end of the same class, kept as its own planted form. Narrowing the detector to `[a-f]`
#: is the mirror of the defect above, and this is what fails when someone does it.
DIGIT_UUID = "00000000-0000-4000-8000-000000000000"

#: Four spellings of ONE Windows path, naming one file and one OS account. Windows compares paths
#: case-insensitively, so a change of case is not a change of file, of account, or of disclosure.
#:
#: The detector read only the canonical spelling until this table existed. The other three exited
#: `0` under a healthy receipt -- the failure this whole file is written against, in the class the
#: gate's own docstring calls the one that actually fires.
#:
#: NONE OF THESE IS CONTRIVED. PowerShell's `Resolve-Path` normalises the drive letter and leaves
#: the rest of the path as typed, so the lowercase form is what the shell itself hands back. A
#: traceback echoes whatever the caller wrote. Both are arrival vectors the gate's own docstring
#: names by hand: pasted terminal output, a traceback, a tool's error message.
#:
#: THE DRIVE LETTER VARIES TOO, and that is not decoration. The pattern matches `[A-Za-z]:`, so a
#: table that only ever spelt `c:` would prove nothing about the class. Measured: with every row on
#: `c:`, narrowing the detector to `[Cc]:` left the ENTIRE suite green. Two cases below pin both
#: properties -- the casing of the segment, and the spread of the drive letter -- so a later
#: tidy-up cannot collapse them and leave the suite green over a narrowed detector.
HOME_PATH_FORMS: tuple[tuple[str, ...], ...] = (
    ("C:", r"\Users", "\\" + FAKE_ACCOUNT, r"\run.py"),
    ("c:", r"\users", "\\" + FAKE_ACCOUNT, r"\run.py"),
    ("C:", r"\USERS", "\\" + FAKE_ACCOUNT, r"\run.py"),
    ("d:", "/users", "/" + FAKE_ACCOUNT, "/run.py"),
)

#: One row per structural detector: (label, reason substring the hit must carry, line fragments).
#: The fragments are joined to build the planted line. The module docstring says why they are
#: fragments: written as single literals, these would make this file a leak.
FIRES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "private artifact URL",
        "private artifact URL",
        ("https://claude.ai/code/", "artifact/", FAKE_UUID),
    ),
    (
        "absolute user-home path",
        "absolute user-home path",
        ("C:", r"\Users", "\\" + FAKE_ACCOUNT, r"\notes.md"),
    ),
    (
        "routable IPv4",
        "routable IP address",
        # RFC 2544 benchmarking range: it routes nowhere, so the fixture names no real host, and it
        # sits outside every range _ALLOWED_IP excuses, so the detector must read it as routable.
        ("198.18.", "0.1"),
    ),
    ("private key block", "private key block", ("-----BEGIN ", "PRIVATE KEY-----")),
    ("cloud access key id", "cloud access key id", ("AKIA", "EXAMPLEKEY000000")),
    ("forge access token (classic)", "forge access token", ("ghp_", "A" * 36)),
    ("forge access token (fine-grained)", "forge access token", ("github_pat_", "A" * 22)),
    ("chat platform token", "chat platform token", ("xoxb-", "A" * 12)),
    ("model API key", "model API key", ("sk-ant-", "A" * 32)),
)

#: Near misses. Each is a line a detector could plausibly over-reach onto, and must not. A gate that
#: fires on these earns an allowlist entry, and an allowlist entry vetoes every detector on the
#: lines it covers -- so a false positive here costs more than the coverage it buys.
QUIET: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "the placeholder form the documentation has to print. A detector whose own manual trips it "
        "earns an allowlist line, and that line switches off every detector on those lines",
        ("https://claude.ai/code/", "artifact/", "<uuid>"),
    ),
    (
        "a deliberately shared artifact: that path segment is plural, and a published URL is not a "
        "disclosure",
        ("https://claude.ai/public/", "artifacts/", FAKE_UUID),
    ),
    (
        "a bare UUID, which the gate deliberately does not detect. It names no host, no account and "
        "no project, and becomes a capability only when something says what it addresses. This case "
        "is that recorded decision made executable, so a later widening has to face it",
        (FAKE_UUID,),
    ),
    (
        "an ordinary claude.ai link with no artifact path. "
        "roles/retired/SEAT-RETIRED-2026-09-12.md carries one",
        ("https://claude.ai/", "code"),
    ),
    # THE THREE BELOW ARE THE ONLY NEAR MISSES WITH WIDTH DISCRIMINATION, and without them a
    # path-widened detector passes this whole table. Every other quiet case here uses a `<uuid>`
    # PLACEHOLDER, so it stays silent under any widening of the PATH -- a widened pattern still
    # demands a real UUID. Only the right host carrying a real UUID on the wrong path refuses it.
    # Measured: widening the path arm to `[a-z]+/` is caught by these three and by nothing else.
    (
        "the right host and a real UUID, on a path that is not an artifact",
        ("https://claude.ai/", "chat/", FAKE_UUID),
    ),
    (
        "the same, on the recents route",
        ("https://claude.ai/", "recents/", FAKE_UUID),
    ),
    (
        "the same, one level deeper, so `code/` alone is not enough to fire",
        ("https://claude.ai/code/", "project/", FAKE_UUID),
    ),
    (
        "a UUID-bearing subdomain on a host that is not the artifact content host",
        ("https://", FAKE_UUID, ".frame.example.com/"),
    ),
    (
        "the artifact content host with no UUID in front of it",
        ("https://cdn", ".frame.claudeusercontent.com/"),
    ),
    # THE HOST ARM'S NEAR MISSES, measured by the serene-bhabha-7decd7 session against the widened
    # pattern and taken with attribution. Each is a shape that a later loosening of the host arm
    # would newly match, so together they bound it from the outside rather than trusting its text.
    (
        "the staging lookalike: a real subdomain shape on a host nobody owns here",
        ("https://", FAKE_UUID, ".frame.staging.example.com/"),
    ),
    (
        "the right host name under the wrong TLD",
        ("https://", FAKE_UUID, ".frame.staging.claudeusercontent.NET/"),
    ),
    (
        "a UUID-shaped run that is one character short in its last group, on the real host",
        ("https://", FAKE_UUID[:-1], ".frame.claudeusercontent.com/"),
    ),
    (
        "the real host with a subdomain label that is not `frame`",
        ("https://", FAKE_UUID, ".preview.claudeusercontent.com/"),
    ),
    (
        "a hostile domain that merely CONTAINS the content host's name, with the UUID in its path",
        ("https://evil-claudeusercontent.com/", FAKE_UUID),
    ),
    (
        "a home path written with the placeholder the detector exempts",
        ("C:", r"\Users", r"\<name>", r"\notes.md"),
    ),
    (
        "the Windows shared account, in the LOWER-CASE spelling the drive branch newly reaches. "
        "This is the near miss with teeth, and the placeholder row above is not: `<name>` is held "
        "out twice over, by the lookahead AND by the `[A-Za-z]` start class, so it stays quiet "
        "even with the lookahead scoped away. A stand-in starts with a letter, so ONLY the "
        "lookahead exempts it -- measured. Widening the case must not widen past the exemptions, "
        "and every other guard on that widening is a `/users/` route with no drive letter at all",
        ("c:", r"\users", r"\Public", r"\Desktop"),
    ),
    (
        "the well-known CI account, which is not a person's login",
        ("/home", "/runner", "/work"),
    ),
    (
        "a REST route, which is where `/users/` overwhelmingly appears. The bare `/Users` and "
        "`/home` alternatives must stay CASE-SENSITIVE: flipping the whole pattern to "
        "re.IGNORECASE catches the Windows spellings and this line with them, because the "
        "exemption list needs a trailing separator and end-of-line does not supply one",
        ("GET ", "/users", "/me"),
    ),
    (
        "the macOS home path in lowercase -- a KNOWN MISS, recorded here rather than closed. It "
        "cannot be told apart from the REST route above by shape, and the route is by far the "
        "commoner string, so the gate takes this false negative over a false positive on every "
        "API path in the tree. Stated as a limit in docs/LEAK-GATE.md, not left to be rediscovered",
        ("/users", "/" + FAKE_ACCOUNT, "/Library"),
    ),
    ("an RFC1918 private address, which identifies no host on the internet", ("192.168.", "1.1")),
    ("a dotted OID, which the IPv4 look-arounds exist to keep out", ("1.3.6.", "1.4.1")),
)


def scan_line(gate, text: str, *, show_context: bool = False) -> list[str]:
    """Write one line to a file OUTSIDE the repository and return the gate's hits on it.

    Outside on purpose, and for the reason `docs/LEAK-GATE.md` gives when it tells a person to plant
    a violation by hand: a fixture written inside the tree is a fixture that has to be cleaned up,
    and the run that forgets is the run that commits it.
    """
    with tempfile.TemporaryDirectory(prefix="ccx-leakgate-") as tmp:
        planted = Path(tmp) / "planted.md"
        planted.write_text(text + "\n", encoding="utf-8")
        return gate.scan_file(planted, show_context=show_context)


class EveryDetectorFiresOnItsPlantedLine(unittest.TestCase):
    """The half `a3df144` failed. Without it every green run the gate produces is unfalsifiable."""

    def setUp(self):
        self.gate = load_gate()

    def test_each_structural_detector_flags_a_line_planted_for_it(self):
        for label, reason, parts in FIRES:
            with self.subTest(detector=label):
                hits = scan_line(self.gate, "".join(parts))
                self.assertTrue(
                    any(reason in h for h in hits),
                    f"the {label} detector did not fire on a line planted for it. Hits: {hits!r}. "
                    "A detector that cannot fire is not an instrument, and every clean run it has "
                    "ever produced means nothing.",
                )

    def test_the_artifact_detector_sees_every_form_of_the_same_capability(self):
        """`a3df144` used the /code/ form. The others address the same artifact."""
        for parts in (
            ("https://claude.ai/code/", "artifact/", FAKE_UUID),
            ("https://claude.ai/", "artifact/", FAKE_UUID),
            ("claude.ai/code/", "artifact/", FAKE_UUID.upper()),
            ("https://claude.ai/code/", "artifact/", DIGIT_UUID),
            ("[the handoff](https://claude.ai/code/", "artifact/", FAKE_UUID + ")"),
            # `frame` is a sibling path of `artifact` in the vendor's own route grammar.
            ("https://claude.ai/code/", "frame/", FAKE_UUID),
            ("https://claude.ai/", "frame/", FAKE_UUID),
            # The vanity slug. This is what the ADDRESS BAR produces, so of every form here it is
            # the likeliest one to be pasted into a note -- and it was the one reported clean.
            ("https://claude.ai/code/", "artifact/", "q4-migration-plan-" + FAKE_UUID),
            ("https://claude.ai/code/", "frame/", "my_draft-2-" + FAKE_UUID),
            # The vendor writes the slug `[A-Za-z0-9_-]*`, so a ZERO-LENGTH one parses, leaving a
            # bare hyphen. It addresses the same artifact. A `{1,64}` bound reported this clean.
            ("https://claude.ai/code/", "artifact/", "-" + FAKE_UUID),
            # The content host: the UUID is a SUBDOMAIN and `claude.ai` never appears at all.
            ("https://", FAKE_UUID, ".frame.claudeusercontent.com/"),
            ("https://", FAKE_UUID, ".frame.staging.claudeusercontent.com/"),
            # THE SUBDOMAIN ARM'S OWN CASE. Every other row on this arm is lower-case, so the single
            # shared `re.IGNORECASE` was proved only through the PATH arm. This row was argued for
            # and initially refused, on the grounds that narrowing one arm's case alone was not a
            # realistic edit. That was wrong, and the counter-example is in this same file:
            # `_HOME_PATH` scopes case-blindness to its Windows branch by inlining the class,
            # precisely because one shared flag is too coarse. It is the likeliest future edit here.
            # Measured: a mutant that inlines case into the path arm and drops the shared flag
            # passes every other row above and fails only this one.
            ("https://", FAKE_UUID.upper(), ".FRAME.CLAUDEUSERCONTENT.COM/"),
        ):
            with self.subTest(form="".join(parts)[:36]):
                hits = scan_line(self.gate, "".join(parts))
                self.assertTrue(
                    any("private artifact URL" in h for h in hits),
                    f"no artifact-URL hit on {''.join(parts)!r}. Hits: {hits!r}",
                )

    def test_the_home_path_detector_reads_the_windows_drive_form_case_blind(self):
        """Windows compares paths case-insensitively. These four name one file and one account.

        Only the canonical spelling fired until this case existed, so a home path pasted out of
        PowerShell or echoed by a traceback scanned clean -- exit `0`, healthy receipt, no
        FORBIDDEN block. That is the silent-miss shape, in the detector the gate leans on most.

        The fix is scoped to the drive-letter branch. `/home` and `/Users` stay case-sensitive,
        which `QUIET` holds in place: `re.IGNORECASE` over the whole pattern would catch these
        four and every `/users/` REST route with them.
        """
        for parts in HOME_PATH_FORMS:
            planted = "".join(parts)
            with self.subTest(form=planted):
                hits = scan_line(self.gate, planted)
                self.assertTrue(
                    any("absolute user-home path" in h for h in hits),
                    f"no home-path hit on {planted!r}. Hits: {hits!r}. Windows resolves this to "
                    "the same file as the canonical spelling, so it discloses the same OS account "
                    "-- and a gate that reads only one spelling of a case-insensitive path reports "
                    "a clean tree over a leak.",
                )


class TheFixtureSpansTheClassItProves(unittest.TestCase):
    """A fixture that exercises half a character class proves half a detector, and reads as proof.

    This case exists because the first version of this file failed it. Everything else here can be
    green while the detector is blind, if the planted value never reaches the part of the pattern
    that matters -- and nothing about that is visible in a passing run.
    """

    def test_the_uuid_fixture_covers_the_letter_half_of_the_hex_class(self):
        letters = set("abcdef") & set(FAKE_UUID.lower())
        self.assertEqual(
            set("abcdef"),
            letters,
            f"FAKE_UUID is {FAKE_UUID!r}, which does not use every hex letter. The detector matches "
            "`[0-9a-f]`, so a fixture missing the letters proves only the digit half: narrowing the "
            "pattern to `[0-9]` would keep this suite green while the gate went blind to real "
            "artifact URLs, which is exactly what shipped once.",
        )

    def test_the_digit_fixture_covers_the_other_half(self):
        self.assertTrue(
            set("0123456789") & set(DIGIT_UUID),
            f"DIGIT_UUID is {DIGIT_UUID!r} and carries no digits, so narrowing the detector to "
            "`[a-f]` would go unnoticed.",
        )

    def test_uppercasing_the_fixture_changes_it(self):
        self.assertNotEqual(
            FAKE_UUID,
            FAKE_UUID.upper(),
            f"FAKE_UUID is {FAKE_UUID!r}, and uppercasing it is a no-op. The uppercase form in "
            "`test_the_artifact_detector_sees_every_form_of_the_same_capability` is then a "
            "duplicate of the row above it, and `re.IGNORECASE` on the detector is unproven -- "
            "deleting the flag would leave this suite green.",
        )

    def test_the_home_path_forms_span_the_case_of_the_users_segment(self):
        segments = {parts[1].lstrip("\\/") for parts in HOME_PATH_FORMS}
        self.assertLess(
            len({segment.lower() for segment in segments}),
            len(segments),
            f"HOME_PATH_FORMS spells the segment {sorted(segments)!r}, and no two of those differ "
            "only by case. The detector matches `[Uu][Ss][Ee][Rr][Ss]`, so a table of one casing "
            "proves only the spelling it happens to use: reverting the pattern to a "
            "case-sensitive `Users` would leave this suite green while the gate went blind to "
            "every home path a shell or a traceback spells in lower case.",
        )

    def test_the_rest_route_near_miss_ends_at_the_exempt_name(self):
        """Its teeth are one character wide, and nothing on the line says so.

        `me` is on the exemption list, but the list requires a TRAILING separator after the name.
        At end of line there is none, so the widened pattern matches and the row catches the
        mutation. Measured: `GET /users/me` fires under `re.IGNORECASE`, `GET /users/me ` does
        not. Append anything and the row keeps reading as a near miss while proving nothing.
        """
        route = next(
            "".join(parts) for why, parts in QUIET if why.startswith("a REST route")
        )
        self.assertTrue(
            route.endswith("/me"),
            f"the REST-route near miss is {route!r}, which does not end at the exempt name. The "
            "exemption needs a trailing separator, so a name at end of line is NOT exempt and the "
            "row catches an `re.IGNORECASE` over-reach. Give it a trailing character and the "
            "exemption applies, the row goes quiet under the mutation too, and it silently stops "
            "being a control -- #52 shipped exactly that line as suppression bait and measured it "
            "baiting nothing.",
        )

    def test_the_home_path_forms_span_more_than_one_drive_letter(self):
        letters = {parts[0].rstrip(":").lower() for parts in HOME_PATH_FORMS}
        self.assertGreater(
            len(letters),
            1,
            f"every row of HOME_PATH_FORMS sits on drive {sorted(letters)!r}. The detector matches "
            "`[A-Za-z]:`, so one letter leaves that class unexercised -- measured, narrowing it to "
            "`[Cc]:` left this entire suite green. That is the `FAKE_UUID` defect in a second "
            "place: a fixture that reads as proof of a class it never spans.",
        )


class EveryDetectorStaysQuietOnItsNearMiss(unittest.TestCase):
    """The other half. A detector that fires on everything is as useless as one firing on nothing."""

    def setUp(self):
        self.gate = load_gate()

    def test_no_detector_fires_on_a_line_that_discloses_nothing(self):
        for why, parts in QUIET:
            with self.subTest(case=why[:48]):
                hits = scan_line(self.gate, "".join(parts))
                self.assertEqual(
                    [],
                    hits,
                    f"the gate flagged a line it must not: {why}. Hits: {hits!r}",
                )


class TheTableCoversEveryDetectorTheGateClaims(unittest.TestCase):
    """A control pinned to one detector is a control the next detector is written without."""

    def test_there_is_one_planted_line_per_structural_detector(self):
        gate = load_gate()
        self.assertEqual(
            gate._STRUCTURAL_COUNT,
            len(FIRES),
            f"the gate reports structural={gate._STRUCTURAL_COUNT} on every receipt it prints, and "
            f"this file plants {len(FIRES)} line(s). The mismatch means a detector was added or "
            "removed without its control, so the printed count is no longer backed by evidence. "
            "Add the planted line and its near miss to FIRES/QUIET rather than editing this number.",
        )


class ThePlantedFixturesNeverBecomeALeakThemselves(unittest.TestCase):
    """This file is scanned by the gate it tests. A fixture written as one literal breaks CI."""

    def test_this_control_file_is_clean_under_the_gate_it_proves(self):
        gate = load_gate()
        hits = gate.scan_file(Path(__file__), rel_posix="tests/" + Path(__file__).name)
        self.assertEqual(
            [],
            hits,
            f"this control file is itself a leak-gate hit: {hits!r}. A fixture was written as one "
            "source line instead of joined fragments. Split it -- do NOT allowlist this file, "
            "because an allowlist entry vetoes every detector on the lines it covers.",
        )


class AnArtifactHitNeverEchoesTheCapability(unittest.TestCase):
    """The URL is the artifact. Printing it into a log publishes what the hit is reporting."""

    def test_show_context_does_not_print_the_url(self):
        gate = load_gate()
        planted = "".join(("https://claude.ai/code/", "artifact/", FAKE_UUID))
        hits = scan_line(gate, planted, show_context=True)
        artifact_hits = [h for h in hits if "private artifact URL" in h]
        self.assertTrue(artifact_hits, f"no artifact hit to check. Hits: {hits!r}")
        for hit in artifact_hits:
            self.assertNotIn(
                FAKE_UUID,
                hit,
                "--show-context echoed the artifact UUID into the hit line. Anyone reading that log "
                "can then fetch the artifact, so the report would publish the capability it exists "
                "to report, to a wider audience than the tree it was found in.",
            )


class AHomePathHitNeverEchoesTheAccountName(unittest.TestCase):
    """The account name is the disclosure. Printing it into a log publishes what the hit reports.

    Same rule as the artifact hit above, and the harder one to keep. This branch appended the
    trimmed line under `--show-context` for as long as the detector existed, while the comment
    directly over it read "Reason only, never the value" -- so the code and its own comment
    disagreed in the tree, and `docs/LEAK-GATE.md` sided with the comment. Nothing ran the two
    against each other. This is that comparison, run.
    """

    def test_show_context_does_not_print_the_account_name(self):
        gate = load_gate()
        planted = "".join(("C:", r"\Users", "\\" + FAKE_ACCOUNT, r"\notes.md"))
        hits = scan_line(gate, planted, show_context=True)
        home_hits = [h for h in hits if "absolute user-home path" in h]
        self.assertTrue(home_hits, f"no home-path hit to check. Hits: {hits!r}")
        for hit in home_hits:
            self.assertNotIn(
                FAKE_ACCOUNT,
                hit,
                "--show-context echoed the OS account name into the hit line. That name is the "
                "whole disclosure the hit reports, so the triage output becomes a second copy "
                "of the leak -- in a log, a ticket or a pull request comment, each a wider "
                "audience than the tree it was found in.",
            )


class NoHitEchoesALineThatCarriesADisclosure(unittest.TestCase):
    """Bare is a property of the LINE, not of the branch that matched the value.

    THE TWO CONTROLS ABOVE CANNOT SEE THIS, and that is the point of adding a third. Each filters to
    its own hit and asserts THAT one is clean -- true, and unfalsifiable against this failure.
    Measured 2026-09-05 on `f1a0e8b`: one line holding an artifact URL and a routable IP printed the
    whole capability in the IP hit's context, while the artifact hit beside it was correctly bare.

        p.md:1: routable IP address (<the address>): ... /artifact/<the whole uuid> on <the address>
        p.md:1: private artifact URL (capability)

    Suppressing context only on the branch that matched leaves every OTHER detector on that line
    free to publish the value. Home paths and credentials measured the same way. So the rule the
    gate has to keep is per line, and `_VALUE_IS_THE_DISCLOSURE` is where it keeps it.

    EACH CASE ASSERTS BOTH DETECTORS FIRED before it inspects the output. Without that, a case
    passes when neither runs -- the same hole this file exists to refuse, in a new place.
    """

    #: A routable address dropped onto the same line as the co-occurring hit. It is chosen because
    #: its branch appends context, so it is the one that would print the value it sits beside.
    CO_OCCURRING = " on " + "".join(("198.18.", "0.1"))

    def setUp(self):
        self.gate = load_gate()

    def assert_no_hit_echoes(self, planted, secret, reason):
        hits = scan_line(self.gate, planted, show_context=True)
        self.assertTrue(
            any("routable IP" in h for h in hits),
            f"the co-occurring IP detector did not fire, so this case proves nothing: {hits!r}",
        )
        self.assertTrue(
            any(reason in h for h in hits),
            f"the {reason!r} detector did not fire, so this case proves nothing: {hits!r}",
        )
        for hit in hits:
            self.assertNotIn(
                secret,
                hit,
                f"a hit on this line printed the value it was meant to withhold: {hit!r}. Bare has "
                "to hold for the whole LINE. A detector that suppresses context only on its own "
                "branch leaves every other detector on that line free to publish what it hid.",
            )

    def test_no_hit_echoes_a_home_path(self):
        planted = "".join(("C:", r"\Users", "\\" + FAKE_ACCOUNT, r"\notes.md"))
        self.assert_no_hit_echoes(
            planted + self.CO_OCCURRING, FAKE_ACCOUNT, "absolute user-home path"
        )

    def test_no_hit_echoes_an_artifact_url(self):
        planted = "".join(("https://claude.ai/code/", "artifact/", FAKE_UUID))
        self.assert_no_hit_echoes(planted + self.CO_OCCURRING, FAKE_UUID, "private artifact URL")

    def test_no_hit_echoes_a_credential(self):
        planted = "".join(("sk-ant-", "A" * 32))
        self.assert_no_hit_echoes(planted + self.CO_OCCURRING, planted, "model API key")


class ContextSurvivesOnALineThatDisclosesNothing(unittest.TestCase):
    """The other corpus for the suppression rule, and one line of it was not enough.

    WHY IT EXISTS. Every other control here asserts a value is ABSENT from the output. All of them
    pass against a gate that suppresses context unconditionally -- `ctx = ""` with the branch
    deleted reddens nothing. So this pins the COST of `_VALUE_IS_THE_DISCLOSURE` rather than its
    benefit: a line carrying none of those classes keeps the context a person asked for.

    WHY IT IS A TABLE, and this is the measured part. The first version planted one line, `the host
    is <address>`, and its docstring claimed "widen a pattern in that tuple until it matches
    ordinary text and this is what reddens". That was false. Measured 2026-09-05: `re.IGNORECASE`
    over the whole `_HOME_PATH` -- which newly matches `GET /users/me` and every other `/users/`
    route -- reddened NOTHING in this file. The fixture carried no `/users/`, no drive letter and
    nothing home-path shaped, so no widening of that pattern could reach it however far it went.

    A pattern in the tuple has TWO jobs, detection and suppression. Over-reach is loud in the first
    and SILENT in the second, so the bait has to be chosen per class: ordinary text that the
    plausible widening of THAT pattern would newly match. One line cannot bait three classes.

    Each row carries a co-occurring routable address, which is what produces a hit to inspect. The
    address is that detector's own finding rather than a capability, so its line is not withheld.
    """

    #: One row per suppression class: (which widening it baits, fragments of the ordinary line).
    #: Fragments rather than literals for the reason the module docstring gives -- this file is
    #: scanned by the gate it tests.
    SUPPRESSION_BAIT: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "_HOME_PATH under re.IGNORECASE, which reaches a /users/ route. That is the "
            "obvious repair for the lower-case drive path, and the wrong one. `profile` is "
            "chosen over `me` on purpose, and NOT because `me` is simply exempt: the "
            "exemption needs a SEPARATOR after the name, so `/users/me` at end of line "
            "FIRES while `/users/me ` and `/users/me HTTP/1.1` stay quiet. Same six "
            "characters, opposite behaviour, decided by what follows them. Bait must not "
            "depend on where the line happens to end; `profile` fires either way",
            ("GET ", "/users", "/profile"),
        ),
        (
            "_ARTIFACT_URL widened to bare UUIDs. The QUIET table records the decision NOT to "
            "detect those, so it is the widening someone actually argues for",
            ("an id like ", FAKE_UUID),
        ),
        (
            "a credential pattern relaxed on length, which reaches the documented prefix rather "
            "than a key",
            ("the ", "sk-ant-", " prefix is documented"),
        ),
        (
            "_ARTIFACT_URL widened to any claude.ai link, or to any URL at all. Measured against "
            "#51's own mutations: the bare-UUID row above does NOT redden on either, because it "
            "carries no URL. One class can need more than one bait",
            ("see ", "https://claude.ai/", "code", " for the docs"),
        ),
    )

    CO_OCCURRING = " from " + "".join(("198.18.", "0.1"))

    def setUp(self):
        self.gate = load_gate()

    def test_ordinary_text_keeps_its_context(self):
        for baits, fragments in self.SUPPRESSION_BAIT:
            planted = "".join(fragments) + self.CO_OCCURRING
            with self.subTest(baits=baits):
                hits = scan_line(self.gate, planted, show_context=True)
                self.assertEqual(1, len(hits), f"expected exactly one hit to inspect: {hits!r}")
                self.assertIn(
                    "".join(fragments),
                    hits[0],
                    "--show-context printed no context on a line that discloses nothing. "
                    f"Suppression has over-reached, and the pattern this baits is: {baits}.",
                )

    def test_the_default_prints_no_context(self):
        for baits, fragments in self.SUPPRESSION_BAIT:
            planted = "".join(fragments) + self.CO_OCCURRING
            with self.subTest(baits=baits):
                hits = scan_line(self.gate, planted)
                self.assertEqual(1, len(hits), f"expected exactly one hit to inspect: {hits!r}")
                self.assertNotIn(
                    "".join(fragments),
                    hits[0],
                    "the DEFAULT output carried the line. That output goes to public CI logs.",
                )

    def test_the_home_path_bait_does_not_depend_on_where_the_line_ends(self):
        """The bait row's comment claims four behaviours. This is what makes them checkable.

        The comment says `profile` was chosen over `me` because the exemption needs a separator
        after the name, so `me` bait works only at end of line. Prose, until now -- and prose about
        a fixture's teeth is the thing that goes stale silently, because nothing re-reads it.

        The widened pattern is derived from the gate's own source rather than retyped, so it cannot
        drift away from the pattern it is meant to mirror.
        """
        widened = re.compile(self.gate._HOME_PATH.pattern, re.IGNORECASE)
        route = "".join(("GET ", "/users", "/"))
        cases = (
            (f"{route}profile", True, "the bait name is not exempt, so it fires"),
            (f"{route}profile ", True, "and it fires with a separator after it too"),
            (f"{route}me", True, "`me` at END OF LINE has no separator, so it is NOT exempt"),
            (f"{route}me ", False, "one trailing space exempts it -- this is why bait 1 failed"),
            (f"{route}me HTTP/1.1", False, "and tidying it into a log line exempts it as well"),
        )
        for line, should_fire, why in cases:
            with self.subTest(line=line):
                self.assertEqual(
                    should_fire,
                    bool(widened.search(line)),
                    f"{line!r}: expected fire={should_fire}. {why}. The bait row's comment states "
                    "this behaviour; if the exemption list or its separator class changed, the "
                    "comment is now wrong and the bait may no longer reach the over-reach.",
                )

    def test_every_suppression_class_has_a_bait_row(self):
        """A class added to the tuple without bait is a silent failure mode with no control."""
        gate = self.gate
        self.assertEqual(
            [gate._HOME_PATH, gate._ARTIFACT_URL, *(pat for pat, _label in gate._CREDENTIALS)],
            list(gate._VALUE_IS_THE_DISCLOSURE),
            "_VALUE_IS_THE_DISCLOSURE changed shape. Every class in it silences context on the "
            "lines it matches, and a class with no row in SUPPRESSION_BAIT has nothing that "
            "reddens when its pattern over-reaches -- which is the half nothing else here can "
            "see. Add the bait row first, then update this assertion.",
        )


class SuppressionReachesExactlyWhatTheJoinReaches(unittest.TestCase):
    """A wrapped disclosure spans two lines. Both must go bare -- and ONLY when the join fires.

    THE DEFECT. The join detects an artifact URL that prose reflow broke in half. Neither raw line
    matches, so a suppression rule written against the raw line withholds nothing, and any other
    detector on those two lines prints the halves one line apart. Measured on the merge: the gate
    detected the capability, refused to print it, and printed it in two pieces.

    WHY THIS ASSERTS AN EQUIVALENCE RATHER THAN A VALUE, which is the whole design. The obvious
    control plants a marker-prefixed continuation and asserts its context survives. That works
    today and goes misleading the moment anyone changes what the join reaches: mutating the join to
    strip markers moves DETECTION and SUPPRESSION together, so a value-asserting control reddens
    beside the join's own marker test, and a reader gets two red tests, one cause, and nothing
    saying which moved.

    So this pins the RELATION. Context is withheld on a line if and only if the gate reported a
    wrapped hit spanning it. A mutation that moves both reaches in step leaves this GREEN and reds
    only the join's own test, which is the single cause it is. A mutation that moves suppression
    alone -- dropping the neighbour guard, dropping a join direction -- reds this and nothing else.

    The residuals are here as rows rather than as prose because both reaches will move if anyone
    touches them, and a row that moves with the code is worth more than a sentence that does not.
    """

    #: (label, the two planted lines). Every row carries a routable address on BOTH lines, because
    #: an unsuppressed line only proves anything if some hit exists to carry its context.
    PAIRS: tuple[tuple[str, str, str], ...] = (
        (
            "a genuine reflow: the join fires, so BOTH lines must go bare",
            "host " + "".join(("198.18.", "0.1")) + " see https://claude.ai/code/artifact/" + FAKE_UUID[:24],
            FAKE_UUID[24:] + " is the id, host " + "".join(("198.18.", "0.2")),
        ),
        (
            "a marker-prefixed continuation: a documented residual, so the join does NOT fire and "
            "these lines keep the context a person asked for",
            "host " + "".join(("198.18.", "0.1")) + " see https://claude.ai/code/artifact/" + FAKE_UUID[:24],
            "# " + FAKE_UUID[24:] + " is the id, host " + "".join(("198.18.", "0.2")),
        ),
        (
            "the neighbour carries a whole URL, so it reports itself and this line discloses "
            "nothing. Without the join's own guard this suppressed the innocent line",
            "an ordinary sentence, host " + "".join(("198.18.", "0.1")),
            "https://claude.ai/code/artifact/" + FAKE_UUID + " host " + "".join(("198.18.", "0.2")),
        ),
        (
            "ordinary prose either side of a line break",
            "the first host is " + "".join(("198.18.", "0.1")),
            "the second host is " + "".join(("198.18.", "0.2")),
        ),
    )

    def setUp(self):
        self.gate = load_gate()

    def scan_pair(self, first, second):
        with tempfile.TemporaryDirectory(prefix="ccx-leakgate-reach-") as tmp:
            planted = Path(tmp) / "planted.md"
            planted.write_text(first + "\n" + second + "\n", encoding="utf-8")
            return self.gate.scan_file(planted, rel_posix="<file>", show_context=True)

    def test_context_is_withheld_on_exactly_the_lines_a_wrapped_hit_spans(self):
        for label, first, second in self.PAIRS:
            with self.subTest(case=label):
                hits = self.scan_pair(first, second)
                wrapped = [h for h in hits if "wrapped onto the next line" in h]
                for lineno, text in ((1, first), (2, second)):
                    carrying = [h for h in hits if h.startswith(f"<file>:{lineno}:")]
                    self.assertTrue(
                        carrying, f"no hit on line {lineno} to inspect, so this row proves nothing"
                    )
                    printed = any(text.strip()[:40] in h for h in carrying)
                    spanned = bool(wrapped) or any(
                        p.search(text) for p in self.gate._VALUE_IS_THE_DISCLOSURE
                    )
                    self.assertEqual(
                        not spanned,
                        printed,
                        f"line {lineno} of this pair: the gate {'reported' if spanned else 'did not report'} "
                        f"a disclosure spanning it, but context was {'printed' if printed else 'withheld'}. "
                        "Suppression must reach exactly what the join reaches -- withholding more "
                        "silences lines the gate never flagged, withholding less prints half a "
                        "capability beside the other half.",
                    )

    def test_neither_half_of_a_wrapped_capability_appears_anywhere(self):
        """The end the defect was actually about: no hit on the file may carry either half."""
        label, first, second = self.PAIRS[0]
        hits = self.scan_pair(first, second)
        self.assertTrue(
            any("wrapped onto the next line" in h for h in hits),
            f"the join did not fire, so this case proves nothing: {hits!r}",
        )
        for half in (FAKE_UUID[:24], FAKE_UUID[24:]):
            for hit in hits:
                self.assertNotIn(
                    half,
                    hit,
                    f"a hit printed {half!r}. Both halves in one report reassemble the capability "
                    "for whoever reads it, which is the disclosure the wrapped hit exists to "
                    "withhold.",
                )


class TheGateExitsNonZeroOverAPlantedFile(unittest.TestCase):
    """End to end. `scan_file` returning hits proves nothing if the exit code stays 0."""

    def test_a_planted_artifact_url_exits_1_and_the_placeholder_form_exits_0(self):
        with tempfile.TemporaryDirectory(prefix="ccx-leakgate-e2e-") as tmp:
            leaky = Path(tmp) / "leaky.md"
            leaky.write_text(
                "".join(("https://claude.ai/code/", "artifact/", FAKE_UUID)) + "\n",
                encoding="utf-8",
            )
            clean = Path(tmp) / "clean.md"
            clean.write_text(
                "".join(("https://claude.ai/code/", "artifact/", "<uuid>")) + "\n",
                encoding="utf-8",
            )

            refused = subprocess.run(
                [sys.executable, str(GATE), str(leaky)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
            )
            self.assertEqual(
                1,
                refused.returncode,
                "the gate did not exit 1 over a planted artifact URL.\n"
                f"exit: {refused.returncode}\nstdout:\n{refused.stdout}\nstderr:\n{refused.stderr}",
            )
            self.assertIn("private artifact URL", refused.stdout + refused.stderr)

            passed = subprocess.run(
                [sys.executable, str(GATE), str(clean)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
            )
            self.assertEqual(
                0,
                passed.returncode,
                "the gate refused the placeholder form, so the documentation describing this "
                "detector could not be committed.\n"
                f"stdout:\n{passed.stdout}\nstderr:\n{passed.stderr}",
            )


def scan_lines(gate, *lines: str) -> list[str]:
    """`scan_line` for more than one line. The wrap cases need a real line boundary, not a longer
    string: the defect they pin is that the boundary is where the detector stopped looking."""
    with tempfile.TemporaryDirectory(prefix="ccx-leakgate-wrap-") as tmp:
        planted = Path(tmp) / "planted.md"
        planted.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return gate.scan_file(planted)


class AWrappedUrlIsStillTheCapability(unittest.TestCase):
    """A text formatter that reflows a pasted link does not make the artifact unreachable.

    Every detector in the gate is line-based, so a URL broken at a column limit matched nothing and
    the run said nothing -- the worst shape a gate can have, because it is indistinguishable from
    clean. Markdown prose is where `a3df144` put two of these, and Markdown prose is exactly what a
    wrapping editor reflows.
    """

    def setUp(self):
        self.gate = load_gate()

    def test_a_url_broken_across_two_lines_still_fires(self):
        for label, first, second in (
            # Mid-UUID: what a hard column limit does to a 36-character token.
            ("mid-UUID", "see https://claude.ai/code/" + "artifact/" + FAKE_UUID[:9], FAKE_UUID[9:] + " for the plan"),
            # After the last slash, which is where a wrapper that breaks on punctuation lands.
            ("after the last slash", "see https://claude.ai/code/" + "artifact/", FAKE_UUID + " for the plan"),
            ("mid-vanity-slug", "see https://claude.ai/code/" + "artifact/q4-migration-", "plan-" + FAKE_UUID),
            ("frame path", "see https://claude.ai/" + "frame/", FAKE_UUID + " ok"),
            # The content host wraps too, and its arm shares none of the path arm's text.
            ("content host", "see https://" + FAKE_UUID, ".frame." + "claudeusercontent.com/ ok"),
            # An indented continuation is the common Markdown case, so the join strips whitespace.
            ("indented continuation", "see https://claude.ai/code/" + "artifact/", "    " + FAKE_UUID + " ok"),
        ):
            with self.subTest(wrap=label):
                hits = scan_lines(self.gate, first, second)
                self.assertTrue(
                    any("private artifact URL" in h for h in hits),
                    f"a URL wrapped {label} was reported clean. Hits: {hits!r}",
                )

    def test_the_wrapped_hit_names_the_first_line_and_says_it_wrapped(self):
        """A reader who greps the reported line must be told why no URL is on it."""
        hits = scan_lines(
            self.gate,
            "intro paragraph with nothing in it",
            "see https://claude.ai/code/" + "artifact/",
            FAKE_UUID + " for the plan",
        )
        artifact = [h for h in hits if "private artifact URL" in h]
        self.assertEqual(1, len(artifact), f"expected exactly one hit. Hits: {hits!r}")
        self.assertIn(":2:", artifact[0], f"the hit did not name the line the URL starts on: {artifact[0]!r}")
        self.assertIn("wrapped", artifact[0], f"the hit did not say it wrapped: {artifact[0]!r}")

    def test_the_wrapped_hit_stays_as_bare_as_the_unwrapped_one(self):
        """The URL is the capability whether or not a formatter broke it."""
        hits = scan_lines(self.gate, "see https://claude.ai/code/" + "artifact/", FAKE_UUID + " ok")
        for hit in (h for h in hits if "private artifact URL" in h):
            self.assertNotIn(FAKE_UUID, hit, f"the wrapped hit echoed the UUID: {hit!r}")
            self.assertNotIn(FAKE_UUID[:8], hit, f"the wrapped hit echoed part of the UUID: {hit!r}")

    def test_joining_lines_does_not_fabricate_a_hit(self):
        """The join is over-reach's cheapest opportunity, so the near misses are re-run across it.

        WHAT THESE SIX ROWS DO AND DO NOT PROVE, measured rather than asserted, because "17 tests,
        all green" averages them together with rows that are pinned. Five mutants, and the tests
        each one reds:

            A  delete the wrap branch          the 6 firing forms, and the line-number test
            B  drop the double-report guard    the report-once test
            C  join a three-line window        the three-line residual, and the line-number test
            D  strip markers in the join       the marker residual, and ONLY that
            E  widen _ARTIFACT_URL to any      THESE SIX -- and their line-level twins in
               non-space run                   EveryDetectorStaysQuietOnItsNearMiss, together

        So these rows are red under exactly one mutant, and that mutant reds the line-level table
        in the same run. They add NO INDEPENDENT SIGNAL against pattern over-reach; what they add
        is that the same near misses survive a line boundary. No join-level mutant reds them --
        the join direction is guarded by the marker test below, not by these.
        """
        for label, first, second in (
            # The self-documentation property has to survive wrapping too, or this file and
            # docs/LEAK-GATE.md stop being committable the moment a formatter touches them.
            ("the placeholder form", "see https://claude.ai/code/" + "artifact/", "<uuid> for the shape"),
            ("the placeholder frame form", "see https://claude.ai/code/" + "frame/", "<uuid> for the shape"),
            ("a deliberately shared link", "see https://claude.ai/public/" + "artifacts/", FAKE_UUID + " ok"),
            ("a lookalike content host", "see https://" + FAKE_UUID, ".frame." + "example.com/ ok"),
            ("two unrelated paragraphs", "the release notes end here", "and the next paragraph starts"),
            ("a bare session id and prose", "session " + FAKE_UUID, "finished cleanly"),
        ):
            with self.subTest(near_miss=label):
                hits = scan_lines(self.gate, first, second)
                self.assertEqual(
                    [], [h for h in hits if "private artifact URL" in h],
                    f"joining lines fabricated an artifact hit on {label}.",
                )

    def test_a_whole_url_on_the_second_line_is_reported_once_not_twice(self):
        """Otherwise one capability is filed under two line numbers and the count stops meaning
        anything."""
        hits = scan_lines(
            self.gate,
            "intro paragraph with nothing in it",
            "see https://claude.ai/code/" + "artifact/" + FAKE_UUID + " ok",
        )
        artifact = [h for h in hits if "private artifact URL" in h]
        self.assertEqual(1, len(artifact), f"one URL produced {len(artifact)} hits: {artifact!r}")
        self.assertIn(":2:", artifact[0])
        self.assertNotIn("wrapped", artifact[0], "an unwrapped URL was reported as wrapped")

    def test_a_wrap_across_three_lines_is_a_documented_residual_not_a_claim(self):
        """Only adjacent pairs are joined. Pinning the residual keeps the next reader from
        believing the class is closed, which is the mistake that produced the one-arm pattern."""
        hits = scan_lines(
            self.gate,
            "https://claude.ai/code/" + "artifact/" + FAKE_UUID[:9],
            FAKE_UUID[9:22],
            FAKE_UUID[22:],
        )
        self.assertEqual(
            [], [h for h in hits if "private artifact URL" in h],
            "a three-line wrap now fires. That is an improvement -- delete this test and say so in "
            "docs/LEAK-GATE.md, which currently records it as a known miss.",
        )

    def test_a_marker_prefixed_continuation_is_a_documented_residual_not_a_claim(self):
        """The join strips whitespace and nothing else, and that is a DECISION, not an oversight.

        It is the one residual whose "fix" is a one-line change somebody will reach for on purpose,
        because catching a URL wrapped inside a list item or a blockquote sounds like a straight
        improvement. Measured: adding `.lstrip("|->*# ")` to the join turns all three markers below
        from quiet to firing, and every other test in this file stays green. So without this row a
        deliberate call is reversible by accident, which is the shape of defect this whole file
        exists to catch -- and it is the argument for pinning a decision, not only a behaviour.

        IT IS THE ONLY GUARD ON THE JOIN'S GREED. That mutant reds this test and nothing else --
        not one of the six near-miss rows above, which are re-runs of the line-level table across
        a boundary and cannot see a change to how the boundary is crossed.
        """
        for marker in ("> ", "# ", "* "):
            with self.subTest(marker=marker):
                hits = scan_lines(
                    self.gate,
                    "https://claude.ai/code/" + "artifact/" + FAKE_UUID[:12],
                    marker + FAKE_UUID[12:],
                )
                self.assertEqual(
                    [], [h for h in hits if "private artifact URL" in h],
                    f"a {marker!r} continuation now fires. If that was deliberate, delete this test "
                    "and update docs/LEAK-GATE.md, which records it as a known miss. Stripping "
                    "markers fabricates adjacency between lines a reader sees as separate.",
                )
