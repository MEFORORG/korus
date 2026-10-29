"""The board's Central clock follows daylight saving.

WHAT THIS EXISTS FOR. build.py and series.py fixed Central as UTC-5 ("Sept 2026 is CDT"). From the
first Sunday in November to the second Sunday in March every clock, chart label and hour bucket on
the board would have read one hour late. Found by the Lander's review of korus PR 253; daylight
saving ended 2026-11-01. `zoneinfo` is not used because the stock Windows Python the refresh runs
under has no `tzdata`, so central.py codes the US rule, and these cases pin it.
"""
import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("board_central", ROOT / "scripts/board/central.py")
central = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = central
SPEC.loader.exec_module(central)
CT = central.CT
U = dt.timezone.utc


def at(y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=U).astimezone(CT)


class CentralTimeFollowsDaylightSaving(unittest.TestCase):

    def test_summer_is_utc_minus_five(self):
        t = at(2026, 9, 20, 18)
        self.assertEqual((t.hour, t.tzname()), (13, "CDT"))

    def test_winter_is_utc_minus_six(self):
        """The case the fixed offset got wrong."""
        t = at(2026, 12, 1, 18)
        self.assertEqual((t.hour, t.tzname()), (12, "CST"))

    def test_the_autumn_change_repeats_one_am(self):
        # 2026-11-01: 06:30Z is 01:30 CDT, 07:30Z is 01:30 CST.
        a, b = at(2026, 11, 1, 6, 30), at(2026, 11, 1, 7, 30)
        self.assertEqual((a.hour, a.minute, a.tzname()), (1, 30, "CDT"))
        self.assertEqual((b.hour, b.minute, b.tzname()), (1, 30, "CST"))
        self.assertEqual(at(2026, 11, 1, 6, 59).tzname(), "CDT")
        self.assertEqual(at(2026, 11, 1, 7, 0).tzname(), "CST")

    def test_the_spring_change_skips_two_am(self):
        # 2027-03-14: 07:59Z is 01:59 CST, 08:00Z is 03:00 CDT.
        a, b = at(2027, 3, 14, 7, 59), at(2027, 3, 14, 8, 0)
        self.assertEqual((a.hour, a.minute, a.tzname()), (1, 59, "CST"))
        self.assertEqual((b.hour, b.minute, b.tzname()), (3, 0, "CDT"))

    def test_a_round_trip_returns_the_same_instant(self):
        u = dt.datetime(2026, 1, 1, tzinfo=U)
        for _ in range(24 * 800):
            self.assertEqual(u.astimezone(CT).astimezone(U), u)
            u += dt.timedelta(hours=1)

    def test_every_hour_agrees_with_the_tz_database_where_one_exists(self):
        try:
            from zoneinfo import ZoneInfo
            ref = ZoneInfo("America/Chicago")
        except Exception:  # no tz database on this Python: the cases above still pin the rule
            self.skipTest("no tz database for America/Chicago")
        u = dt.datetime(2026, 1, 1, tzinfo=U)
        while u.year < 2029:
            a, b = u.astimezone(CT), u.astimezone(ref)
            self.assertEqual((a.replace(tzinfo=None), a.utcoffset()),
                             (b.replace(tzinfo=None), b.utcoffset()), u)
            u += dt.timedelta(minutes=30)


if __name__ == "__main__":
    unittest.main()
