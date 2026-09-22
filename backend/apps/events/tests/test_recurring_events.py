"""Recurring events: the same mechanics as recurring tasks, plus one rule of
their own: an occurrence that carries minutes is never deleted by a series
operation. The engine itself is covered by apps/core/tests/test_recurrence.py."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.recurrence import WINDOW_DAYS
from apps.events import services
from apps.events.models import Event, EventSeries
from apps.events.tasks import materialise_all_series
from apps.tasks.tests.conftest import iso

from .test_events import at

pytestmark = pytest.mark.django_db


def create_weekly(client, tree, **extra):
    payload = {
        "project": tree["A"].pk,
        "title": "Point hebdo",
        "type": "meeting",
        "start": iso(at(0, 10)),
        "end": iso(at(0, 11)),
        "location": "Studio",
        "prep_notes": "Ordre du jour permanent",
        "rrule": "FREQ=WEEKLY",
        **extra,
    }
    return client.post("/api/events/", payload, format="json")


def occurrences(series_id):
    return list(Event.objects.filter(series_id=series_id).order_by("occurrence_at"))


def test_creating_a_recurring_event_materialises_the_next_90_days(tree, editor_api):
    response = create_weekly(editor_api, tree)

    assert response.status_code == 201
    series_id = response.data["recurrence"]["series"]
    events = occurrences(series_id)
    assert len(events) == WINDOW_DAYS // 7 + 1
    assert events[0].pk == response.data["id"]
    gaps = {(b.start - a.start).days for a, b in zip(events, events[1:])}
    assert gaps == {7}
    # Duration, place and standing agenda follow; minutes never do.
    later = events[4]
    assert later.end - later.start == timedelta(hours=1)
    assert (later.location, later.prep_notes) == ("Studio", "Ordre du jour permanent")
    assert later.report == "" and later.decisions == []


def test_occurrences_copy_participants_contacts_and_tags(tree, editor_api, make_member):
    from apps.contacts.models import Contact, ProjectContact
    from apps.projects.tests.factories import TagFactory

    make_member("helder", "viewer", scope="A")
    booker = Contact.objects.create(workspace=tree.workspace, last_name="Booker")
    ProjectContact.objects.create(project=tree["A"], contact=booker)
    tag = TagFactory(workspace=tree.workspace)

    first = create_weekly(
        editor_api,
        tree,
        participant_usernames=["helder"],
        contacts=[booker.pk],
        tags=[tag.pk],
    ).data
    later = occurrences(first["recurrence"]["series"])[3]

    assert [u.username for u in later.participants.all()] == ["helder"]
    assert list(later.contacts.all()) == [booker]
    assert list(later.tags.all()) == [tag]


def test_materialising_is_idempotent_and_the_nightly_job_extends(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    before = len(occurrences(series_id))
    series = EventSeries.objects.get(pk=series_id)

    assert services.materialise(series) == 0
    series.generated_until = series.dtstart
    series.save()
    assert services.materialise(series) == 0
    assert len(occurrences(series_id)) == before

    in_a_month = timezone.localdate() + timedelta(days=28)
    assert services.materialise(series, today=in_a_month) == 4
    assert materialise_all_series() == 0


def test_editing_this_occurrence_only(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    third = occurrences(series_id)[2]

    response = editor_api.patch(
        f"/api/events/{third.pk}/",
        {"location": "Chez Ana", "start": iso(third.start + timedelta(hours=2))},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["recurrence"]["is_exception"] is True
    others = [e for e in occurrences(series_id) if e.pk != third.pk]
    assert all(e.location == "Studio" for e in others)
    assert len(occurrences(series_id)) == WINDOW_DAYS // 7 + 1


def test_editing_this_and_following_splits_the_series(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    before = occurrences(series_id)
    third = before[2]
    # Minutes on a LATER occurrence: it must survive the split.
    later = before[5]
    later.report = "On a décidé plein de choses"
    later.save()

    response = editor_api.patch(
        f"/api/events/{third.pk}/?scope=following",
        {"location": "Chez Ana"},
        format="json",
    )

    assert response.status_code == 200
    new_series_id = response.data["recurrence"]["series"]
    assert new_series_id != series_id
    old = occurrences(series_id)
    new = occurrences(new_series_id)
    # Old series: the two occurrences before the split, plus the one with minutes.
    assert [e.pk for e in old] == [before[0].pk, before[1].pk, later.pk]
    assert all(e.location == "Studio" for e in old)
    assert EventSeries.objects.get(pk=series_id).rrule.upper().count("UNTIL=") == 1
    # New series: from the third on, same weekday, new place.
    assert new[0].pk == third.pk
    assert all(e.location == "Chez Ana" for e in new)
    assert {(b.start - a.start).days for a, b in zip(new, new[1:])} == {7}
    # No date is served twice across both series (the kept minutes aside).
    starts = [e.start for e in old + new]
    assert len(starts) == len(set(starts)) + 1


def test_changing_the_rule_or_stopping_applies_to_following(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    second = occurrences(series_id)[1]

    refused = editor_api.patch(
        f"/api/events/{second.pk}/", {"rrule": ""}, format="json"
    )
    stopped = editor_api.patch(
        f"/api/events/{second.pk}/?scope=following", {"rrule": ""}, format="json"
    )

    assert refused.status_code == 400 and "rrule" in refused.data
    assert stopped.status_code == 200 and stopped.data["recurrence"] is None
    assert [e.pk for e in occurrences(series_id)] != []  # the first one stays
    assert Event.objects.filter(project=tree["A"]).count() == 2


def test_deleting_this_or_following(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    events = occurrences(series_id)

    assert editor_api.delete(f"/api/events/{events[3].pk}/").status_code == 204
    assert len(occurrences(series_id)) == len(events) - 1
    assert (
        editor_api.delete(f"/api/events/{events[1].pk}/?scope=following").status_code
        == 204
    )
    assert [e.pk for e in occurrences(series_id)] == [events[0].pk]


def test_a_simple_event_can_become_recurring(tree, editor_api):
    single = create_weekly(editor_api, tree, rrule="").data
    assert single["recurrence"] is None

    response = editor_api.patch(
        f"/api/events/{single['id']}/", {"rrule": "FREQ=MONTHLY"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["recurrence"]["rrule"].startswith("FREQ=MONTHLY")
    assert len(occurrences(response.data["recurrence"]["series"])) >= 3
