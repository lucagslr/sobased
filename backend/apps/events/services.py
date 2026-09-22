"""Recurring events: same mechanics as recurring tasks (apps/tasks/services.py),
on top of the shared engine apps/core/recurrence.py.

- "Cette occurrence": only that event changes; it is flagged `is_exception`.
- "Celle-ci et toutes les suivantes": the series is SPLIT. The old one gets an
  UNTIL the day before, its following occurrences are deleted, and a new
  series starts from the edited event.
- An occurrence that carries minutes (a report or decisions) is never deleted
  by a series operation: what was decided in a meeting must not vanish because
  someone rescheduled the next ones.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core import recurrence

from .models import Event, EventSeries

User = get_user_model()


def event_template(event: Event) -> dict:
    """What the next occurrences of a series copy from `event`.

    Minutes (report, decisions) belong to one meeting and are never copied;
    preparation notes are, since they often hold a standing agenda.
    """
    saved = bool(event.pk)
    return {
        "type": event.type,
        "title": event.title,
        "location": event.location,
        "prep_notes": event.prep_notes,
        "duration_seconds": int((event.end - event.start).total_seconds()),
        "participants": (
            list(event.participants.values_list("pk", flat=True)) if saved else []
        ),
        "contacts": list(event.contacts.values_list("pk", flat=True)) if saved else [],
        "tags": list(event.tags.values_list("pk", flat=True)) if saved else [],
    }


@transaction.atomic
def start_series(event: Event, rule: str, tz_name: str) -> EventSeries:
    """Make `event` the first occurrence of a new series and create the next ones."""
    rule = recurrence.normalise_rrule(rule)
    series = EventSeries.objects.create(
        project=event.project,
        rrule=rule,
        dtstart=event.start,
        timezone=tz_name,
        all_day=event.all_day,
        generated_until=event.start,
        template=event_template(event),
    )
    event.series = series
    event.occurrence_at = event.start
    event.is_exception = False
    event.save(update_fields=["series", "occurrence_at", "is_exception", "updated_at"])
    materialise(series)
    return series


def materialise(series: EventSeries, today=None) -> int:
    """Create the missing occurrences up to the end of the 90-day window.

    Idempotent: safe to run every night, or twice in a row.
    """
    horizon = recurrence.window_end(today or timezone.localdate())
    if horizon <= series.generated_until:
        return 0
    moments = recurrence.occurrences_between(
        series.rrule,
        series.dtstart,
        series.timezone,
        all_day=series.all_day,
        after=series.generated_until,
        until=horizon,
    )
    template = series.template
    duration = timedelta(seconds=template.get("duration_seconds", 3600))
    created = 0
    for moment in moments:
        if Event.objects.filter(series=series, occurrence_at=moment).exists():
            continue
        event = Event.objects.create(
            project=series.project,
            type=template.get("type", Event.Type.MEETING),
            title=template.get("title", ""),
            location=template.get("location", ""),
            prep_notes=template.get("prep_notes", ""),
            start=moment,
            end=moment + duration,
            all_day=series.all_day,
            series=series,
            occurrence_at=moment,
        )
        event.participants.set(
            User.objects.filter(pk__in=template.get("participants", []), is_active=True)
        )
        event.contacts.set(template.get("contacts", []))
        event.tags.set(template.get("tags", []))
        created += 1
    series.generated_until = horizon
    series.save(update_fields=["generated_until", "updated_at"])
    return created


def _close_series_before(event: Event) -> None:
    """End the event's series just before this occurrence.

    Following occurrences are deleted, except those that carry minutes.
    An emptied series is removed.
    """
    series = event.series
    Event.objects.filter(
        series=series, occurrence_at__gt=event.occurrence_at, report="", decisions=[]
    ).delete()
    if event.occurrence_at <= series.dtstart:
        event.series = None
        event.save(update_fields=["series", "updated_at"])
        if not series.occurrences.exists():
            series.delete()
        return
    last_day = event.occurrence_at.date() - timedelta(days=1)
    series.rrule = recurrence.with_until(series.rrule, last_day)
    series.save(update_fields=["rrule", "updated_at"])


def _without_end(rule: str) -> str:
    return ";".join(
        part
        for part in rule.split(";")
        if not part.upper().startswith(("UNTIL=", "COUNT="))
    )


@transaction.atomic
def apply_to_following(event: Event, rule: str | None, tz_name: str) -> None:
    """ "Toutes les suivantes": split the series at this (already edited) event.

    `rule`: None keeps the current rule, "" stops the recurrence here.
    """
    old_series = event.series
    current_rule = old_series.rrule if old_series else ""
    if old_series is not None:
        _close_series_before(event)
        event.series = None
        event.occurrence_at = None
    event.is_exception = False
    event.save()
    new_rule = current_rule if rule is None else rule
    if new_rule:
        # The old rule may carry the UNTIL we just added: start clean.
        start_series(
            event, _without_end(new_rule) if rule is None else new_rule, tz_name
        )


@transaction.atomic
def delete_with_following(event: Event) -> None:
    if event.series_id:
        _close_series_before(event)
    event.delete()
