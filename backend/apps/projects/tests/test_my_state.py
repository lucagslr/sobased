"""PATCH /api/projects/{id}/my-state/: the task view I used last on a project
(SPEC §15: "choix mémorisé par projet"). Personal, so a reader may set it."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.projects.models import ProjectUserState

from .factories import Tree, grant

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree():
    return Tree()


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def member(tree, username, role, scope="R"):
    user = UserFactory(username=username)
    grant(user, tree[scope], role)
    return user


def test_default_view_is_the_list(tree):
    client = client_for(member(tree, "reader", "viewer"))

    response = client.get(f"/api/projects/{tree['A'].pk}/")

    assert response.data["my_tasks_view"] == "list"


def test_a_reader_can_remember_their_view(tree):
    reader = member(tree, "reader", "viewer")
    client = client_for(reader)
    url = f"/api/projects/{tree['A'].pk}/my-state/"

    response = client.patch(url, {"tasks_view": "kanban"}, format="json")

    assert response.status_code == 200
    assert response.data == {"tasks_view": "kanban"}
    assert client.get(f"/api/projects/{tree['A'].pk}/").data["my_tasks_view"] == (
        "kanban"
    )
    # Saved again: still one row per (user, project).
    client.patch(url, {"tasks_view": "gantt"}, format="json")
    states = ProjectUserState.objects.filter(user=reader, project=tree["A"])
    assert [state.tasks_view for state in states] == ["gantt"]


def test_the_choice_is_per_user_and_per_project(tree):
    first = client_for(member(tree, "first", "editor"))
    second = client_for(member(tree, "second", "editor"))
    first.patch(
        f"/api/projects/{tree['A'].pk}/my-state/",
        {"tasks_view": "calendar"},
        format="json",
    )

    assert first.get(f"/api/projects/{tree['A'].pk}/").data["my_tasks_view"] == (
        "calendar"
    )
    assert first.get(f"/api/projects/{tree['B'].pk}/").data["my_tasks_view"] == "list"
    assert second.get(f"/api/projects/{tree['A'].pk}/").data["my_tasks_view"] == "list"


def test_it_does_not_erase_the_snooze_of_the_end_date_modal(tree):
    editor = member(tree, "editor", "editor")
    client = client_for(editor)
    client.post(f"/api/projects/{tree['A'].pk}/snooze-overdue/")

    client.patch(
        f"/api/projects/{tree['A'].pk}/my-state/",
        {"tasks_view": "kanban"},
        format="json",
    )

    state = ProjectUserState.objects.get(user=editor, project=tree["A"])
    assert state.tasks_view == "kanban"
    assert state.overdue_snoozed_until is not None


def test_unknown_view_is_refused(tree):
    client = client_for(member(tree, "reader", "viewer"))

    response = client.patch(
        f"/api/projects/{tree['A'].pk}/my-state/",
        {"tasks_view": "mindmap"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.parametrize("node", ["R", "A", "B", "Z"])
def test_shells_and_invisible_projects_answer_404(tree, node):
    # Guest of A1: R and A are shells, B and Z do not exist for them.
    client = client_for(member(tree, "guest", "editor", scope="A1"))

    response = client.patch(
        f"/api/projects/{tree[node].pk}/my-state/",
        {"tasks_view": "kanban"},
        format="json",
    )

    assert response.status_code == 404
    assert not ProjectUserState.objects.exists()
