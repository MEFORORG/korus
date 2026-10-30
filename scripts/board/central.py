"""US Central time for the board, with daylight saving, and no tz database.

The board first fixed Central as UTC-5 ("Sept 2026 is CDT"), which reads an hour wrong from the
first Sunday in November to the second Sunday in March. `zoneinfo` would be the obvious fix, but
on Windows it needs the `tzdata` package, and the stock Python the refresh runs under has none:
`ZoneInfo("America/Chicago")` raises there. The US rule has held since 2007, so it is coded here.
"""
import datetime as dt

_STD = dt.timedelta(hours=-6)
_HOUR = dt.timedelta(hours=1)


def _nth_sunday(year, month, n):
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


def _bounds_local(year):
    """DST starts at 02:00 local standard time and ends at 02:00 local daylight time."""
    start = dt.datetime.combine(_nth_sunday(year, 3, 2), dt.time(2))
    end = dt.datetime.combine(_nth_sunday(year, 11, 1), dt.time(2))
    return start, end


class _Central(dt.tzinfo):
    def dst(self, d):
        if d is None:
            return dt.timedelta(0)
        start, end = _bounds_local(d.year)
        naive = d.replace(tzinfo=None)
        if start <= naive < end - _HOUR:
            return _HOUR
        if end - _HOUR <= naive < end:
            # The repeated hour: fold=0 is its first pass, still daylight time.
            return dt.timedelta(0) if d.fold else _HOUR
        return dt.timedelta(0)

    def utcoffset(self, d):
        return _STD + self.dst(d)

    def tzname(self, d):
        return "CDT" if self.dst(d) else "CST"

    def fromutc(self, d):
        naive = d.replace(tzinfo=None)
        start, end = _bounds_local(naive.year)
        start_utc, end_utc = start - _STD, end - _STD - _HOUR
        if start_utc <= naive < end_utc:
            return (naive + _STD + _HOUR).replace(tzinfo=self)
        local = naive + _STD
        fold = 1 if end - _HOUR <= local < end else 0
        return local.replace(tzinfo=self, fold=fold)


CT = _Central()
