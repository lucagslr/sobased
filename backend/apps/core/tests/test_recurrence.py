"""Recurrence engine: validation, daylight-saving time, window bounds."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from apps.core import recurrence

ZURICH = ZoneInfo("Europe/Zurich")


def local(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=ZURICH)


@pytest.mark.parametrize(
    "rule",
    [
        "FREQ=DAILY",
        "RRULE:FREQ=WEEKLY;BYDAY=MO,TH",
        "FREQ=MONTHLY;BYMONTHDAY=15",
        "FREQ=YEARLY",
        "FREQ=WEEKLY;INTERVAL=2;COUNT=5",
        "FREQ=DAILY;UNTIL=20261231T235959Z",
    ],
)
def test_accepted_rules(rule):
    assert "RRULE" not in recurrence.normalise_rrule(rule)


@pytest.mark.parametrize(
    "rule", ["", "   ", "FREQ=HOURLY", "FREQ=MINUTELY;INTERVAL=5", "n'importe quoi"]
)
def test_refused_rules(rule):
    with pytest.raises(recurrence.InvalidRecurrence):
        recurrence.normalise_rrule(rule)


def test_until_given_in_utc_is_stored_naive():
    rule = recurrence.normalise_rrule("FREQ=DAILY;UNTIL=20261231T235959Z")

    assert rule.endswith("UNTIL=20261231T235959")


def test_weekly_meeting_keeps_its_local_time_across_the_end_of_dst():
    """Summer time ends on 25.10.2026: 10:00 in Zurich is 08:00 UTC before,
    09:00 UTC after. The meeting must stay at 10:00 on the wall clock."""
    moments = recurrence.occurrences_between(
        "FREQ=WEEKLY",
        local(2026, 10, 12, 10),
        "Europe/Zurich",
        all_day=False,
        after=local(2026, 10, 12, 10),
        until=local(2026, 11, 3),
    )

    assert [m.astimezone(ZURICH).strftime("%d.%m %H:%M") for m in moments] == [
        "19.10 10:00",
        "26.10 10:00",
        "02.11 10:00",
    ]
    assert [m.hour for m in moments] == [8, 9, 9]  # in UTC


def test_weekly_meeting_across_the_start_of_dst():
    moments = recurrence.occurrences_between(
        "FREQ=WEEKLY",
        local(2027, 3, 22, 18, 30),
        "Europe/Zurich",
        all_day=False,
        after=local(2027, 3, 22, 18, 30),
        until=local(2027, 4, 6),
    )

    assert [m.astimezone(ZURICH).strftime("%d.%m %H:%M") for m in moments] == [
        "29.03 18:30",
        "05.04 18:30",
    ]


def test_all_day_items_stay_at_midnight_utc():
    start = datetime(2026, 10, 1, tzinfo=UTC)

    moments = recurrence.occurrences_between(
        "FREQ=MONTHLY",
        start,
        "Europe/Zurich",
        all_day=True,
        after=start,
        until=datetime(2027, 1, 1, tzinfo=UTC),
    )

    assert moments == [
        datetime(2026, 11, 1, tzinfo=UTC),
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2027, 1, 1, tzinfo=UTC),  # the upper bound is included
    ]


def test_lower_bound_is_excluded_so_a_second_run_creates_nothing_twice():
    start = datetime(2026, 10, 1, tzinfo=UTC)
    first = recurrence.occurrences_between(
        "FREQ=DAILY",
        start,
        "UTC",
        all_day=True,
        after=start,
        until=start.replace(day=4),
    )
    second = recurrence.occurrences_between(
        "FREQ=DAILY",
        start,
        "UTC",
        all_day=True,
        after=first[-1],
        until=start.replace(day=6),
    )

    assert [m.day for m in first] == [2, 3, 4]
    assert [m.day for m in second] == [5, 6]


def test_count_and_until_end_the_series():
    start = datetime(2026, 10, 1, tzinfo=UTC)
    far = datetime(2027, 10, 1, tzinfo=UTC)

    counted = recurrence.occurrences_between(
        "FREQ=WEEKLY;COUNT=3", start, "UTC", all_day=True, after=start, until=far
    )
    ended = recurrence.occurrences_between(
        recurrence.with_until("FREQ=WEEKLY;COUNT=50", date(2026, 10, 16)),
        start,
        "UTC",
        all_day=True,
        after=start,
        until=far,
    )

    assert len(counted) == 2  # the first of the 3 is dtstart itself
    assert [m.day for m in ended] == [8, 15]


def test_unknown_timezone_falls_back_to_zurich():
    moments = recurrence.occurrences_between(
        "FREQ=DAILY",
        local(2026, 10, 12, 10),
        "Mars/Olympus",
        all_day=False,
        after=local(2026, 10, 12, 10),
        until=local(2026, 10, 13, 12),
    )

    assert moments[0].astimezone(ZURICH).hour == 10


def test_a_runaway_rule_is_capped():
    start = datetime(2026, 1, 1, tzinfo=UTC)

    moments = recurrence.occurrences_between(
        "FREQ=DAILY",
        start,
        "UTC",
        all_day=True,
        after=start,
        until=datetime(2030, 1, 1, tzinfo=UTC),
    )

    assert len(moments) == recurrence.MAX_OCCURRENCES_PER_WINDOW
