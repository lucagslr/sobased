"""Dashboard summary, project overview and saved views."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.dashboard.models import WIDGET_KEYS, DashboardView
from apps.dashboard.serializers import (
    DashboardWidgetsSerializer,
    ProjectOverviewSerializer,
)
from apps.projects.tests.factories import TagFactory, Tree, grant
from apps.tasks.models import ChecklistItem
from apps.tasks.tests.conftest import TaskFactory, client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree():
    return Tree()


@pytest.fixture
def editor(tree):
    user = UserFactory(username="editor")
    grant(user, tree["R"], "editor")
    return user


@pytest.fixture
def api(editor):
    return client_for(editor)


def day(user, offset=0):
    """An all-day date `offset` days from the USER's today (midnight UTC)."""
    today = datetime.now(ZoneInfo(user.timezone)).date() + timedelta(days=offset)
    return datetime(today.year, today.month, today.day, tzinfo=UTC)


def titles(widget):
    return sorted(item["title"] for item in widget["items"])


def summary(client, query=""):
    response = client.get(f"/api/dashboard/summary/{query}")
    assert response.status_code == 200
    return response.data["widgets"]


# --- Shape ------------------------------------------------------------------------


def test_response_matches_its_documented_shape(api):
    response = api.get("/api/dashboard/summary/")

    assert set(response.data) == {"date", "widgets"}
    assert set(response.data["widgets"]) == set(DashboardWidgetsSerializer().fields)
    assert set(response.data["widgets"]) == set(WIDGET_KEYS)


def test_widgets_of_later_phases_are_flagged_unavailable(api):
    widgets = summary(api)

    for key in ("expenses_to_pay", "missing_receipts"):  # phase 7
        assert widgets[key] == {"available": False, "count": 0}
    assert widgets["meetings"] == {"available": True, "count": 0, "items": []}


# --- Widgets ------------------------------------------------------------------------


def test_each_task_lands_in_the_right_widget(tree, editor, api):
    project = tree["A"]
    TaskFactory(project=project, title="retard", due_at=day(editor, -2))
    TaskFactory(project=project, title="aujourdhui", due_at=day(editor))
    TaskFactory(
        project=project, title="commence", start_at=day(editor), due_at=day(editor, 30)
    )
    TaskFactory(project=project, title="demain", due_at=day(editor, 1))
    TaskFactory(project=project, title="j7", due_at=day(editor, 7))
    TaskFactory(project=project, title="j8", due_at=day(editor, 8))
    TaskFactory(project=project, title="fini", due_at=day(editor, -2), status="done")
    TaskFactory(project=project, title="sans date")

    widgets = summary(api)

    assert titles(widgets["overdue"]) == ["retard"]
    assert widgets["overdue"]["items"][0]["is_overdue"] is True
    assert titles(widgets["today"]) == ["aujourdhui", "commence"]
    assert titles(widgets["next7"]) == ["demain", "j7"]


def test_a_timed_task_due_earlier_today_is_late_not_today(tree, editor, api):
    now = timezone.now()
    TaskFactory(
        project=tree["A"],
        title="passée",
        all_day=False,
        due_at=now - timedelta(minutes=1),
    )
    later = now + timedelta(minutes=1)
    TaskFactory(project=tree["A"], title="à venir", all_day=False, due_at=later)

    widgets = summary(api)

    assert titles(widgets["overdue"]) == ["passée"]
    local_now = now.astimezone(ZoneInfo(editor.timezone))
    if later.astimezone(ZoneInfo(editor.timezone)).date() == local_now.date():
        assert titles(widgets["today"]) == ["à venir"]


def test_overdue_is_sorted_oldest_first_then_by_priority(tree, editor, api):
    TaskFactory(project=tree["A"], title="récent", due_at=day(editor, -1), priority=5)
    TaskFactory(project=tree["A"], title="vieux-p1", due_at=day(editor, -9), priority=1)
    TaskFactory(project=tree["A"], title="vieux-p5", due_at=day(editor, -9), priority=5)

    items = summary(api)["overdue"]["items"]

    assert [item["title"] for item in items] == ["vieux-p5", "vieux-p1", "récent"]


def test_today_depends_on_the_users_timezone(tree):
    """An all-day task dated "today in UTC" is already late for someone whose
    local date is ahead, and not for someone whose local date is behind."""
    ahead = UserFactory(username="kiritimati", timezone="Pacific/Kiritimati")  # UTC+14
    behind = UserFactory(username="niue", timezone="Pacific/Niue")  # UTC-11
    for user in (ahead, behind):
        grant(user, tree["R"], "viewer")
    utc_today = datetime.now(UTC).date()
    TaskFactory(
        project=tree["A"],
        title="t",
        due_at=datetime(utc_today.year, utc_today.month, utc_today.day, tzinfo=UTC),
    )

    def late_for(user):
        local = datetime.now(ZoneInfo(user.timezone)).date()
        return local > utc_today

    for user in (ahead, behind):
        overdue = summary(client_for(user))["overdue"]
        assert (overdue["count"] == 1) is late_for(user)


def test_pinned_todos(tree, editor, api):
    task = TaskFactory(project=tree["A"], title="Clip")
    ChecklistItem.objects.create(task=task, title="épinglée", pinned=True)
    ChecklistItem.objects.create(task=task, title="cochée", pinned=True, done=True)
    ChecklistItem.objects.create(task=task, title="normale")
    closed = TaskFactory(project=tree["A"], status="cancelled")
    ChecklistItem.objects.create(task=closed, title="tâche annulée", pinned=True)

    pinned = summary(api)["pinned"]

    assert pinned["count"] == 1
    assert pinned["items"][0]["title"] == "épinglée"
    assert pinned["items"][0]["task_title"] == "Clip"


def test_to_validate_lists_tasks_and_projects(tree, editor, api):
    TaskFactory(project=tree["A"], title="Cover v3", status="to_validate")
    tree["B"].status = "to_validate"
    tree["B"].save()

    widget = summary(api)["to_validate"]

    assert widget["count"] == 2
    assert {(i["kind"], i["title"]) for i in widget["items"]} == {
        ("task", "Cover v3"),
        ("project", "B"),
    }


def test_count_is_the_total_even_when_the_list_is_cut(tree, editor, api):
    for index in range(53):
        TaskFactory(project=tree["A"], title=f"t{index}", due_at=day(editor, -1))

    overdue = summary(api)["overdue"]

    assert overdue["count"] == 53
    assert len(overdue["items"]) == 50


# --- Rights -------------------------------------------------------------------------


def test_nothing_from_projects_i_cannot_see(tree):
    guest = UserFactory(username="guest")
    grant(guest, tree["A1"], "editor")
    TaskFactory(project=tree["A1"], title="visible", due_at=day(guest, -1))
    TaskFactory(project=tree["A"], title="coquille", due_at=day(guest, -1))
    TaskFactory(project=tree["B"], title="autre branche", due_at=day(guest, -1))
    TaskFactory(project=tree["Z"], title="autre espace", due_at=day(guest, -1))
    secret = TaskFactory(project=tree["B"])
    ChecklistItem.objects.create(task=secret, title="secret", pinned=True)
    tree["B"].status = "to_validate"
    tree["B"].save()

    widgets = summary(client_for(guest))

    assert titles(widgets["overdue"]) == ["visible"]
    assert widgets["pinned"]["count"] == 0
    assert widgets["to_validate"]["count"] == 0


def test_a_filter_cannot_widen_my_rights(tree):
    guest = UserFactory(username="guest")
    grant(guest, tree["A1"], "editor")
    TaskFactory(project=tree["B"], title="secret", due_at=day(guest, -1))
    client = client_for(guest)

    by_query = summary(client, f"?project={tree['B'].pk}&project={tree['R'].pk}")
    view = DashboardView.objects.create(
        user=guest, name="Pirate", filters={"projects": [tree["B"].pk, tree["R"].pk]}
    )
    by_view = summary(client, f"?view={view.pk}")

    assert by_query["overdue"]["count"] == 0
    assert by_view["overdue"]["count"] == 0


def test_summary_requires_authentication():
    from rest_framework.test import APIClient

    assert APIClient().get("/api/dashboard/summary/").status_code == 401


# --- Filters ------------------------------------------------------------------------


def test_filters(tree, editor, api):
    grant(editor, tree.other_workspace, "viewer")
    urgent = TagFactory(workspace=tree.workspace, name="urgent")
    in_a = TaskFactory(project=tree["A"], title="a", due_at=day(editor, -1))
    in_a.tags.add(urgent)
    in_a.assignees.add(editor)
    TaskFactory(project=tree["A1x"], title="a1x", due_at=day(editor, -1))
    TaskFactory(project=tree["B"], title="b", due_at=day(editor, -1))
    TaskFactory(project=tree["Z"], title="z", due_at=day(editor, -1))

    def late(query):
        return titles(summary(api, query)["overdue"])

    assert late("") == ["a", "a1x", "b", "z"]
    assert late(f"?workspace={tree.workspace.pk}") == ["a", "a1x", "b"]
    assert late(f"?project={tree['A'].pk}") == ["a", "a1x"]  # sub-projects included
    assert late(f"?project={tree['A'].pk}&project={tree['B'].pk}") == ["a", "a1x", "b"]
    assert late(f"?tag={urgent.pk}") == ["a"]
    assert late("?only_mine=true") == ["a"]
    assert late(f"?workspace={tree.other_workspace.pk}&only_mine=true") == []


def test_only_mine_does_not_hide_what_i_have_to_validate(tree, editor, api):
    TaskFactory(project=tree["A"], title="à valider", status="to_validate")

    assert summary(api, "?only_mine=true")["to_validate"]["count"] == 1


def test_saved_view_filters_are_applied(tree, editor, api):
    TaskFactory(project=tree["A"], title="a", due_at=day(editor, -1))
    TaskFactory(project=tree["B"], title="b", due_at=day(editor, -1))
    view = DashboardView.objects.create(
        user=editor, name="SHORTY", filters={"projects": [tree["B"].pk]}
    )
    someone_else = DashboardView.objects.create(user=tree.owner, name="Privée")

    assert titles(summary(api, f"?view={view.pk}")["overdue"]) == ["b"]
    assert api.get(f"/api/dashboard/summary/?view={someone_else.pk}").status_code == 404


# --- Project overview ---------------------------------------------------------------


def test_project_overview(tree, editor, api):
    TaskFactory(project=tree["A"], title="retard A", due_at=day(editor, -1))
    TaskFactory(project=tree["A1"], title="aujourdhui A1", due_at=day(editor))
    TaskFactory(project=tree["A1x"], title="jalon", due_at=day(editor, 5))
    TaskFactory(project=tree["B"], title="hors branche", due_at=day(editor, -1))
    local_today = datetime.now(ZoneInfo(editor.timezone)).date()
    tree["A2"].start_date = local_today + timedelta(days=2)
    tree["A2"].end_date = local_today + timedelta(days=20)
    tree["A2"].save()

    response = api.get(f"/api/projects/{tree['A'].pk}/overview/")

    assert response.status_code == 200
    assert set(response.data) == set(ProjectOverviewSerializer().fields)
    assert titles(response.data["overdue"]) == ["retard A"]
    assert titles(response.data["today"]) == ["aujourdhui A1"]
    assert [(m["kind"], m["title"]) for m in response.data["milestones"]] == [
        ("project_start", "A2"),
        ("task", "jalon"),
        ("project_end", "A2"),
    ]


def test_project_overview_of_a_shell_or_a_stranger_is_a_404(tree):
    guest = UserFactory(username="guest")
    grant(guest, tree["A1"], "admin")
    client = client_for(guest)

    assert client.get(f"/api/projects/{tree['A1'].pk}/overview/").status_code == 200
    assert client.get(f"/api/projects/{tree['A'].pk}/overview/").status_code == 404
    assert client.get(f"/api/projects/{tree['B'].pk}/overview/").status_code == 404
    assert client.get("/api/projects/999999/overview/").status_code == 404


# --- Saved views --------------------------------------------------------------------


def test_first_list_creates_my_default_view(api, editor):
    views = api.get("/api/dashboard/views/").data

    assert [(v["name"], v["is_default"]) for v in views] == [("Mon dashboard", True)]
    assert [w["key"] for w in views[0]["layout"]] == WIDGET_KEYS
    assert api.get("/api/dashboard/views/").data == views  # no duplicate


def test_layout_is_cleaned_and_overdue_stays_first_and_visible(api):
    view_id = api.get("/api/dashboard/views/").data[0]["id"]

    response = api.patch(
        f"/api/dashboard/views/{view_id}/",
        {
            "layout": [
                {"key": "today", "size": 9, "tall": True},
                {"key": "overdue", "hidden": True, "size": 0},
                {"key": "hacked", "size": 1},
                {"key": "today", "size": 1},
            ]
        },
        format="json",
    )

    layout = response.data["layout"]
    assert layout[0] == {"key": "overdue", "size": 1, "tall": False, "hidden": False}
    assert layout[1] == {"key": "today", "size": 3, "tall": True, "hidden": False}
    assert sorted(w["key"] for w in layout) == sorted(WIDGET_KEYS)  # nothing lost


def test_filters_are_reduced_to_lists_of_ids(api):
    response = api.post(
        "/api/dashboard/views/",
        {
            "name": "École",
            "filters": {"workspaces": ["3", 3, "x"], "only_mine": 1, "sql": "drop"},
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["filters"] == {
        "workspaces": [3],
        "projects": [],
        "tags": [],
        "only_mine": True,
    }


def test_only_one_default_view(api, editor):
    api.get("/api/dashboard/views/")

    created = api.post(
        "/api/dashboard/views/",
        {"name": "100SATIONS", "is_default": True},
        format="json",
    )

    assert created.status_code == 201
    defaults = DashboardView.objects.filter(user=editor, is_default=True)
    assert [v.name for v in defaults] == ["100SATIONS"]


def test_deleting_the_default_view_promotes_another(api, editor):
    first = api.get("/api/dashboard/views/").data[0]
    api.post("/api/dashboard/views/", {"name": "Perso"}, format="json")

    assert api.delete(f"/api/dashboard/views/{first['id']}/").status_code == 204

    assert DashboardView.objects.get(user=editor).is_default is True


def test_views_are_private(tree, api):
    theirs = DashboardView.objects.create(user=tree.owner, name="Privée")
    url = f"/api/dashboard/views/{theirs.pk}/"

    assert theirs.name not in [v["name"] for v in api.get("/api/dashboard/views/").data]
    assert api.get(url).status_code == 404
    assert api.patch(url, {"name": "x"}, format="json").status_code == 404
    assert api.delete(url).status_code == 404
