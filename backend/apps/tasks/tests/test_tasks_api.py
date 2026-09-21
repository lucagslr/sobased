"""Tasks: CRUD, validation, computed state, filters, kanban order."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.projects.tests.factories import TagFactory
from apps.tasks.models import Task

from .conftest import TaskFactory, client_for, day, iso

pytestmark = pytest.mark.django_db


def create(client, project, **fields):
    payload = {"project": project.pk, "title": "Mixer le titre 1", **fields}
    return client.post("/api/tasks/", payload, format="json")


# --- Rights (the full matrix lives in apps/projects) -------------------------------


@pytest.mark.parametrize(
    "role, expected", [("viewer", 403), ("commenter", 403), ("editor", 201)]
)
def test_creating_needs_the_editor_role(tree, make_member, role, expected):
    client = client_for(make_member("someone", role))

    assert create(client, tree["A"]).status_code == expected


def test_tasks_of_invisible_projects_do_not_exist(tree, make_member):
    hidden = TaskFactory(project=tree["B"])
    client = client_for(make_member("guest", "editor", scope="A1"))

    assert client.get(f"/api/tasks/{hidden.pk}/").status_code == 404
    assert client.get("/api/tasks/").data["count"] == 0
    assert create(client, tree["B"]).status_code == 404
    # A is only a shell for this guest: no content there either.
    assert create(client, tree["A"]).status_code == 404


def test_viewer_can_read_but_not_write(tree, make_member):
    task = TaskFactory(project=tree["A"])
    client = client_for(make_member("reader", "viewer"))

    assert client.get(f"/api/tasks/{task.pk}/").status_code == 200
    assert client.patch(f"/api/tasks/{task.pk}/", {"title": "x"}).status_code == 403
    assert client.delete(f"/api/tasks/{task.pk}/").status_code == 403


# --- Creation and validation --------------------------------------------------------


def test_create_with_defaults(tree, editor_api, editor):
    response = create(editor_api, tree["A"])

    assert response.status_code == 201
    data = response.data
    assert (data["status"], data["priority"], data["all_day"]) == ("todo", 3, True)
    assert (data["project_name"], data["is_overdue"], data["is_blocked"]) == (
        "A",
        False,
        False,
    )
    assert Task.objects.get(pk=data["id"]).created_by == editor


def test_new_tasks_are_appended_to_their_column(tree, editor_api):
    positions = [create(editor_api, tree["A"]).data["position"] for _ in range(3)]

    assert positions == [0, 1, 2]


@pytest.mark.parametrize(
    "fields, error",
    [
        ({"priority": 0}, "priority"),
        ({"priority": 6}, "priority"),
        ({"title": ""}, "title"),
        ({"status": "bof"}, "status"),
    ],
)
def test_invalid_fields(tree, editor_api, fields, error):
    response = create(editor_api, tree["A"], **fields)

    assert response.status_code == 400 and error in response.data


def test_due_date_cannot_precede_start(tree, editor_api):
    response = create(editor_api, tree["A"], start_at=iso(day(3)), due_at=iso(day(1)))

    assert response.status_code == 400 and "due_at" in response.data


def test_tags_must_belong_to_the_workspace(tree, editor_api):
    foreign = TagFactory(workspace=tree.other_workspace)
    own = TagFactory(workspace=tree.workspace)

    assert create(editor_api, tree["A"], tags=[foreign.pk]).status_code == 400
    assert create(editor_api, tree["A"], tags=[own.pk]).data["tags"] == [own.pk]


def test_a_task_never_changes_project(tree, editor_api):
    task = TaskFactory(project=tree["A"])

    editor_api.patch(f"/api/tasks/{task.pk}/", {"project": tree["B"].pk}, format="json")

    task.refresh_from_db()
    assert task.project == tree["A"]


# --- Assignees ----------------------------------------------------------------------


def test_assignees_are_project_members_and_get_an_email(tree, editor_api, make_member):
    helder = make_member("helder", "commenter", scope="A")

    response = create(editor_api, tree["A1"], assignee_usernames=["@Helder", "editor"])

    assert response.status_code == 201
    assert {u["username"] for u in response.data["assignees"]} == {"helder", "editor"}
    assert "email" not in response.data["assignees"][0]
    # The author is not notified about their own assignment.
    assert [m.to for m in mail.outbox] == [[helder.email]]
    assert "Mixer le titre 1" in mail.outbox[0].subject


def test_cannot_assign_someone_outside_the_project(tree, editor_api, make_member):
    make_member("sibling", "editor", scope="B")  # member of B, not of A

    response = create(editor_api, tree["A"], assignee_usernames=["sibling"])

    assert response.status_code == 400 and "assignee_usernames" in response.data


def test_assignment_email_respects_the_preference(tree, editor_api, make_member):
    quiet = make_member("quiet", "viewer")
    quiet.email_on_assignment = False
    quiet.save()

    create(editor_api, tree["A"], assignee_usernames=["quiet"])

    assert mail.outbox == []


def test_reassigning_only_notifies_newcomers(tree, editor_api, make_member):
    make_member("first", "viewer")
    second = make_member("second", "viewer")
    task_id = create(editor_api, tree["A"], assignee_usernames=["first"]).data["id"]
    mail.outbox.clear()

    editor_api.patch(
        f"/api/tasks/{task_id}/",
        {"assignee_usernames": ["first", "second"]},
        format="json",
    )

    assert [m.to for m in mail.outbox] == [[second.email]]


# --- Overdue (SPEC §7) --------------------------------------------------------------


def test_overdue_all_day_means_the_day_is_over(tree, editor_api):
    yesterday = TaskFactory(project=tree["A"], due_at=day(-1))
    today = TaskFactory(project=tree["A"], due_at=day(0))
    done = TaskFactory(project=tree["A"], due_at=day(-5), status="done")
    cancelled = TaskFactory(project=tree["A"], due_at=day(-5), status="cancelled")

    late = editor_api.get("/api/tasks/?overdue=true").data["results"]
    state = {
        t["id"]: t["is_overdue"] for t in editor_api.get("/api/tasks/").data["results"]
    }

    assert [t["id"] for t in late] == [yesterday.pk]
    assert state == {
        yesterday.pk: True,
        today.pk: False,
        done.pk: False,
        cancelled.pk: False,
    }


def test_overdue_timed_task_is_late_as_soon_as_its_time_has_passed(tree, editor_api):
    past = TaskFactory(
        project=tree["A"], all_day=False, due_at=timezone.now() - timedelta(minutes=5)
    )
    future = TaskFactory(
        project=tree["A"], all_day=False, due_at=timezone.now() + timedelta(minutes=5)
    )

    late = editor_api.get("/api/tasks/?overdue=true").data["results"]

    assert [t["id"] for t in late] == [past.pk]
    assert editor_api.get(f"/api/tasks/{future.pk}/").data["is_overdue"] is False


def test_nothing_is_ever_postponed_automatically(tree, editor_api):
    task = TaskFactory(project=tree["A"], due_at=day(-30))

    editor_api.get("/api/tasks/?overdue=true")

    task.refresh_from_db()
    assert task.due_at == day(-30)


def test_completed_at_follows_the_status(tree, editor_api):
    task = TaskFactory(project=tree["A"])

    done = editor_api.patch(f"/api/tasks/{task.pk}/", {"status": "done"}, format="json")
    assert done.data["completed_at"] is not None

    reopened = editor_api.patch(
        f"/api/tasks/{task.pk}/", {"status": "in_progress"}, format="json"
    )
    assert reopened.data["completed_at"] is None


# --- Filters ------------------------------------------------------------------------


def titles(response):
    return sorted(task["title"] for task in response.data["results"])


def test_filters(tree, editor_api, editor, make_member):
    other = make_member("other", "viewer")
    urgent = TagFactory(workspace=tree.workspace, name="urgent")
    mine = TaskFactory(project=tree["A"], title="a-mine", due_at=day(2), priority=5)
    mine.assignees.add(editor)
    mine.tags.add(urgent)
    theirs = TaskFactory(project=tree["A1"], title="a1-theirs", status="in_progress")
    theirs.assignees.add(other)
    TaskFactory(project=tree["B"], title="b-done", status="done", due_at=day(10))
    TaskFactory(project=tree["Z"], title="z-hidden")

    get = editor_api.get
    assert titles(get("/api/tasks/")) == ["a-mine", "a1-theirs", "b-done"]
    assert titles(get("/api/tasks/?assignee=me")) == ["a-mine"]
    assert titles(get("/api/tasks/?assignee=other")) == ["a1-theirs"]
    assert titles(get(f"/api/tasks/?project={tree['A'].pk}")) == ["a-mine"]
    assert titles(
        get(f"/api/tasks/?project={tree['A'].pk}&include_descendants=true")
    ) == [
        "a-mine",
        "a1-theirs",
    ]
    assert titles(get("/api/tasks/?status=in_progress&status=done")) == [
        "a1-theirs",
        "b-done",
    ]
    assert titles(get("/api/tasks/?open=true")) == ["a-mine", "a1-theirs"]
    assert titles(get("/api/tasks/?no_date=true")) == ["a1-theirs"]
    assert titles(get(f"/api/tasks/?tag={urgent.pk}")) == ["a-mine"]
    assert titles(get("/api/tasks/?priority=5")) == ["a-mine"]
    assert titles(get("/api/tasks/?search=THEIRS")) == ["a1-theirs"]
    assert titles(get(f"/api/tasks/?due_before={iso(day(5))}")) == ["a-mine"]
    assert titles(get(f"/api/tasks/?workspace={tree.other_workspace.pk}")) == []


def test_filtering_on_a_project_i_cannot_see_returns_nothing(tree, make_member):
    TaskFactory(project=tree["B"])
    client = client_for(make_member("guest", "editor", scope="A1"))

    response = client.get(
        f"/api/tasks/?project={tree['B'].pk}&include_descendants=true"
    )

    assert response.data["count"] == 0


# --- Kanban -------------------------------------------------------------------------


def test_move_reorders_both_columns_and_warns_when_blocked(tree, editor_api):
    a, b, c = (TaskFactory(project=tree["A"], position=i) for i in range(3))
    blocker = TaskFactory(project=tree["A"], status="in_progress", position=0)
    c.blocked_by.add(blocker)

    response = editor_api.post(
        f"/api/tasks/{c.pk}/move/",
        {"status": "in_progress", "position": 0},
        format="json",
    )

    assert response.status_code == 200
    assert "bloquée" in response.data["warning"]  # allowed, but said (SPEC §7)

    def column(status):
        return list(
            Task.objects.filter(status=status)
            .order_by("position")
            .values_list("pk", "position")
        )

    assert column("in_progress") == [(c.pk, 0), (blocker.pk, 1)]
    assert column("todo") == [(a.pk, 0), (b.pk, 1)]


def test_move_without_blocker_has_no_warning(tree, editor_api):
    task = TaskFactory(project=tree["A"])

    response = editor_api.post(
        f"/api/tasks/{task.pk}/move/", {"status": "done", "position": 99}, format="json"
    )

    assert "warning" not in response.data
    assert response.data["position"] == 0
