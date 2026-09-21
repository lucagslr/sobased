"""The user's own clock.

Everything is stored in UTC, but "today", "overdue" and "this project should
have ended yesterday" are LOCAL notions: they depend on where the user lives.
These helpers are the only place that turns a user's timezone into dates.
"""

import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

FALLBACK_ZONE = "Europe/Zurich"


def user_zone(user) -> zoneinfo.ZoneInfo:
    try:
        return zoneinfo.ZoneInfo(getattr(user, "timezone", "") or FALLBACK_ZONE)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return zoneinfo.ZoneInfo(FALLBACK_ZONE)


def local_today(user) -> date:
    """Today's date where the user lives."""
    return datetime.now(user_zone(user)).date()


def all_day_moment(day: date) -> datetime:
    """How an all-day date is stored: midnight UTC (see DATABASE_SCHEMA.md)."""
    return datetime.combine(day, time.min, tzinfo=UTC)


def local_day_bounds(user, day: date) -> tuple[datetime, datetime]:
    """[start, end) of a local calendar day, as aware datetimes.

    Used for TIMED items: "due today" means between local midnight and the
    next local midnight, which is not a UTC day.
    """
    zone = user_zone(user)
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return start, end
