"""Recurrence rules (RFC 5545 RRULE), shared by tasks and, later, events.

Two conventions make recurrence predictable:

- A series is expanded in ITS OWN timezone: "every Monday at 10:00" stays at
  10:00 local time across daylight-saving changes (it moves in UTC, as it
  should). Expanding in UTC would shift the meeting by one hour twice a year.
- All-day items are anchored at midnight UTC and only their date matters
  (see DATABASE_SCHEMA.md): they are expanded in UTC, untouched.

Rules are always evaluated on NAIVE local datetimes (dateutil refuses to mix
naive and aware values), so an UNTIL given in UTC ("...Z") is stored naive.

Occurrences are materialised as real rows over a sliding window (SPEC §7), so
this module only ever answers "which dates fall between A and B?".
"""

from __future__ import annotations

import re
import zoneinfo
from datetime import UTC, date, datetime, time, timedelta

from dateutil.rrule import DAILY, MONTHLY, WEEKLY, YEARLY, rrulestr

# How far ahead occurrences exist as rows. Celery beat extends it every night.
WINDOW_DAYS = 90
# Hourly or faster rules make no sense for tasks and would flood the database.
ALLOWED_FREQUENCIES = {DAILY, WEEKLY, MONTHLY, YEARLY}
MAX_OCCURRENCES_PER_WINDOW = 120


class InvalidRecurrence(ValueError):
    """The rule cannot be parsed or is not acceptable. Message is user-facing."""


def normalise_rrule(rule: str) -> str:
    """Validate a rule; return it without "RRULE:" and with a naive UNTIL."""
    rule = (rule or "").strip()
    if rule.upper().startswith("RRULE:"):
        rule = rule[6:]
    rule = re.sub(r"(UNTIL=\d{8}T\d{6})Z", r"\1", rule, flags=re.I)
    if not rule:
        raise InvalidRecurrence("Règle de récurrence vide.")
    try:
        parsed = rrulestr(rule, dtstart=datetime(2026, 1, 1))
    except (ValueError, TypeError) as exc:
        raise InvalidRecurrence("Règle de récurrence illisible.") from exc
    if getattr(parsed, "_freq", None) not in ALLOWED_FREQUENCIES:
        raise InvalidRecurrence(
            "Fréquence acceptée : quotidienne, hebdomadaire, mensuelle ou annuelle."
        )
    return rule


def _zone(tz_name: str, all_day: bool):
    if all_day:
        return UTC
    try:
        return zoneinfo.ZoneInfo(tz_name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return zoneinfo.ZoneInfo("Europe/Zurich")


def occurrences_between(
    rule: str,
    dtstart: datetime,
    tz_name: str,
    *,
    all_day: bool,
    after: datetime,
    until: datetime,
) -> list[datetime]:
    """Occurrences (aware, UTC) with after < occurrence <= until.

    `dtstart` is the first occurrence of the series. All arguments are aware.
    Timed items are expanded on the local wall clock of `tz_name`, so 10:00
    stays 10:00 whatever the UTC offset of that day is.
    """
    zone = _zone(tz_name, all_day)

    def local(moment: datetime) -> datetime:
        return moment.astimezone(zone).replace(tzinfo=None)

    lower = local(after)
    found = rrulestr(rule, dtstart=local(dtstart)).between(
        lower, local(until), inc=True
    )
    found = [moment for moment in found if moment > lower]
    return [
        moment.replace(tzinfo=zone).astimezone(UTC)
        for moment in found[:MAX_OCCURRENCES_PER_WINDOW]
    ]


def window_end(today: date) -> datetime:
    """End of the materialisation window, as an aware UTC datetime."""
    return datetime.combine(today + timedelta(days=WINDOW_DAYS), time.max, tzinfo=UTC)


def with_until(rule: str, last_day: date) -> str:
    """Return `rule` ending on `last_day` (used when a series is split)."""
    parts = [
        part
        for part in rule.split(";")
        if not part.upper().startswith(("UNTIL=", "COUNT="))
    ]
    parts.append(f"UNTIL={last_day:%Y%m%d}T235959")
    return ";".join(parts)
