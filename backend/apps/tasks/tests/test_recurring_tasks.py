"""Recurring tasks: materialisation over 90 days, "this" versus "following"."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.recurrence import WINDOW_DAYS
from apps.projects.tests.factories import TagFactory
from apps.tasks import services
from apps.tasks.models import Task, TaskSeries
from apps.tasks.tasks import materialise_all_series

from .conftest import day, iso

pytestmark = pytest.mark.django_db


def create_weekly(client, tree, **extra):
    payload = {
        "project": tree["A"].pk,
        "title": "Publier le planning",
        "due_at": iso(day(0)),
        "rrule": "FREQ=WEEKLY",
        **extra,
    }
    return client.post("/api/tasks/", payload, format="json")


def occurrences(series_id):
    return list(Task.objects.filter(series_id=series_id).order_by("occurrence_at"))


def test_creating_a_recurring_task_materialises_the_next_90_days(tree, editor_api):
    response = create_weekly(editor_api, tree)

    assert response.status_code == 201
    series_id = response.data["recurrence"]["series"]
    tasks = occurrences(series_id)
    # Today + one per week until the end of the window.
    assert len(tasks) == WINDOW_DAYS // 7 + 1
    assert tasks[0].pk == response.data["id"]
    gaps = {(b.due_at - a.due_at).days for a, b in zip(tasks, tasks[1:])}
    assert gaps == {7}
    assert all(t.status == "todo" and t.all_day for t in tasks)
    assert tasks[-1].due_at <= day(WINDOW_DAYS)


def test_occurrences_copy_the_template(tree, editor_api, make_member):
    make_member("helder", "commenter")
    tag = TagFactory(workspace=tree.workspace)
    first = create_weekly(
        editor_api,
        tree,
        priority=5,
        description="Chaque lundi",
        assignee_usernames=["helder"],
        tags=[tag.pk],
        start_at=iso(day(-2)),
    ).data

    later = occurrences(first["recurrence"]["series"])[3]

    assert (later.title, later.priority, later.description) == (
        "Publier le planning",
        5,
        "Chaque lundi",
    )
    assert [u.username for u in later.assignees.all()] == ["helder"]
    assert list(later.tags.all()) == [tag]
    assert later.due_at - later.start_at == timedelta(days=2)  # same lead time


def test_a_recurring_task_needs_a_date_and_a_sane_rule(tree, editor_api):
    no_date = editor_api.post(
        "/api/tasks/",
        {"project": tree["A"].pk, "title": "x", "rrule": "FREQ=DAILY"},
        format="json",
    )
    hourly = create_weekly(editor_api, tree, rrule="FREQ=HOURLY")

    assert no_date.status_code == 400 and "rrule" in no_date.data
    assert hourly.status_code == 400 and "rrule" in hourly.data
    assert not Task.objects.exists()


def test_materialising_twice_creates_nothing_twice(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    before = len(occurrences(series_id))
    series = TaskSeries.objects.get(pk=series_id)

    assert services.materialise(series) == 0
    # Even if the bookmark is lost, existing occurrences are not duplicated.
    series.generated_until = series.dtstart
    series.save()
    assert services.materialise(series) == 0
    assert len(occurrences(series_id)) == before


def test_the_nightly_job_extends_the_window(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    before = len(occurrences(series_id))
    series = TaskSeries.objects.get(pk=series_id)

    in_a_month = timezone.localdate() + timedelta(days=28)
    created = services.materialise(series, today=in_a_month)

    assert created == 4
    assert len(occurrences(series_id)) == before + 4
    assert materialise_all_series() == 0  # today's window is already covered


def test_editing_this_occurrence_only(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    second = occurrences(series_id)[1]

    response = editor_api.patch(
        f"/api/tasks/{second.pk}/", {"title": "Planning (férié)"}, format="json"
    )

    assert response.data["recurrence"]["is_exception"] is True
    titles = {t.title for t in occurrences(series_id)}
    assert titles == {"Publier le planning", "Planning (férié)"}


def test_editing_all_following_splits_the_series(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    tasks = occurrences(series_id)
    done, pivot = tasks[1], tasks[2]
    # A later occurrence already finished: it must never be touched.
    finished_later = tasks[4]
    Task.objects.filter(pk=finished_later.pk).update(status="done")
    Task.objects.filter(pk=done.pk).update(status="done")

    response = editor_api.patch(
        f"/api/tasks/{pivot.pk}/?scope=following",
        {"title": "Publier le planning + stories", "priority": 4},
        format="json",
    )

    assert response.status_code == 200
    new_series = response.data["recurrence"]["series"]
    assert new_series != series_id
    # Old series: what came before the pivot, plus the finished later one.
    old = occurrences(series_id)
    assert [t.pk for t in old] == [tasks[0].pk, done.pk, finished_later.pk]
    assert all(t.title == "Publier le planning" for t in old)
    assert "UNTIL=" in TaskSeries.objects.get(pk=series_id).rrule
    # New series: starts at the pivot, carries the new template.
    new = occurrences(new_series)
    assert new[0].pk == pivot.pk
    assert {t.title for t in new} == {"Publier le planning + stories"}
    assert {t.priority for t in new} == {4}
    # No date is served twice by the two series.
    open_dates = [t.due_at for t in Task.objects.filter(status="todo")]
    assert len(open_dates) == len(set(open_dates))


def test_changing_the_rule_for_all_following(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    pivot = occurrences(series_id)[1]

    response = editor_api.patch(
        f"/api/tasks/{pivot.pk}/?scope=following",
        {"rrule": "FREQ=WEEKLY;INTERVAL=2"},
        format="json",
    )

    new = occurrences(response.data["recurrence"]["series"])
    assert {(b.due_at - a.due_at).days for a, b in zip(new, new[1:])} == {14}


def test_stopping_the_recurrence_from_here(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    pivot = occurrences(series_id)[2]

    stop_here_only = editor_api.patch(
        f"/api/tasks/{pivot.pk}/", {"rrule": ""}, format="json"
    )
    assert stop_here_only.status_code == 400  # needs scope=following

    response = editor_api.patch(
        f"/api/tasks/{pivot.pk}/?scope=following", {"rrule": ""}, format="json"
    )

    assert response.data["recurrence"] is None
    assert Task.objects.count() == 3  # two before, and the pivot, now a plain task


def test_editing_following_from_the_first_occurrence_replaces_the_series(
    tree, editor_api
):
    first = create_weekly(editor_api, tree).data

    response = editor_api.patch(
        f"/api/tasks/{first['id']}/?scope=following",
        {"title": "Nouveau"},
        format="json",
    )

    assert not TaskSeries.objects.filter(pk=first["recurrence"]["series"]).exists()
    assert {t.title for t in Task.objects.all()} == {"Nouveau"}
    assert response.data["recurrence"]["series"] != first["recurrence"]["series"]


def test_deleting_this_or_all_following(tree, editor_api):
    series_id = create_weekly(editor_api, tree).data["recurrence"]["series"]
    tasks = occurrences(series_id)
    total = len(tasks)

    assert editor_api.delete(f"/api/tasks/{tasks[1].pk}/").status_code == 204
    assert len(occurrences(series_id)) == total - 1
    # The nightly job does not resurrect a deleted occurrence.
    assert services.materialise(TaskSeries.objects.get(pk=series_id)) == 0

    response = editor_api.delete(f"/api/tasks/{tasks[3].pk}/?scope=following")

    assert response.status_code == 204
    assert [t.pk for t in occurrences(series_id)] == [tasks[0].pk, tasks[2].pk]


def test_a_plain_task_can_become_recurring(tree, editor_api):
    plain = editor_api.post(
        "/api/tasks/",
        {"project": tree["A"].pk, "title": "RDV studio", "due_at": iso(day(1))},
        format="json",
    ).data

    response = editor_api.patch(
        f"/api/tasks/{plain['id']}/", {"rrule": "FREQ=MONTHLY"}, format="json"
    )

    assert response.data["recurrence"]["rrule"] == "FREQ=MONTHLY"
    assert Task.objects.count() in (3, 4)  # depends on the length of the months
