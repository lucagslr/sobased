"""Workspaces, project types and tags."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.projects.models import Membership
from apps.projects.tests.factories import Tree, grant
from apps.workspaces.models import DEFAULT_PROJECT_TYPES, ProjectType, Tag, Workspace

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree():
    return Tree()


@pytest.fixture
def member():
    return UserFactory(username="member")


def login(user):
    client = APIClient()
    client.force_login(user)
    return client


# --- Workspaces -----------------------------------------------------------------


def test_anyone_can_create_a_workspace_and_owns_it(member):
    response = login(member).post(
        "/api/workspaces/", {"name": "100SATIONS", "color": "#FDE68A"}, format="json"
    )

    assert response.status_code == 201
    assert response.data["my_role"] == "owner"
    assert response.data["owner"]["username"] == "member"
    workspace = Workspace.objects.get(name="100SATIONS")
    assert Membership.objects.get(workspace=workspace).role == "owner"
    assert list(workspace.project_types.values_list("name", flat=True)) == (
        DEFAULT_PROJECT_TYPES
    )


def test_invalid_colour_is_refused(member):
    response = login(member).post(
        "/api/workspaces/", {"name": "X", "color": "red"}, format="json"
    )
    assert response.status_code == 400


def test_list_shows_my_workspaces_and_shells_only(tree, member):
    grant(member, tree["A1"], "editor")  # guest of a sub-project of W
    Workspace.objects.create(name="Secret")

    data = login(member).get("/api/workspaces/").data

    assert [(w["name"], w["is_shell"], w["my_role"], w["owner"]) for w in data] == [
        ("W", True, None, None)
    ]


def test_update_needs_admin_and_delete_needs_owner(tree, member):
    grant(member, tree.workspace, "admin")
    client = login(member)
    url = f"/api/workspaces/{tree.workspace.pk}/"

    assert client.patch(url, {"name": "Renommé"}, format="json").status_code == 200
    assert client.delete(url).status_code == 403
    assert login(tree.owner).delete(url).status_code == 204


def test_editor_cannot_rename_and_outsider_gets_404(tree, member):
    url = f"/api/workspaces/{tree.workspace.pk}/"
    assert login(member).patch(url, {"name": "X"}, format="json").status_code == 404

    grant(member, tree.workspace, "editor")
    assert login(member).patch(url, {"name": "X"}, format="json").status_code == 403


def test_transfer_ownership(tree, member):
    grant(member, tree.workspace, "viewer")
    url = f"/api/workspaces/{tree.workspace.pk}/transfer-ownership/"

    assert login(member).post(url, {"username": "wsowner"}).status_code == 403
    response = login(tree.owner).post(url, {"username": "member"}, format="json")

    assert response.status_code == 200
    roles = dict(
        Membership.objects.filter(workspace=tree.workspace).values_list(
            "user__username", "role"
        )
    )
    assert roles == {"member": "owner", "wsowner": "admin"}


def test_transfer_to_a_non_member_is_refused(tree):
    UserFactory(username="stranger")

    response = login(tree.owner).post(
        f"/api/workspaces/{tree.workspace.pk}/transfer-ownership/",
        {"username": "stranger"},
        format="json",
    )
    assert response.status_code == 400


def test_leave(tree, member):
    grant(member, tree.workspace, "editor")
    url = f"/api/workspaces/{tree.workspace.pk}/leave/"

    assert login(tree.owner).post(url).status_code == 403  # must transfer first
    assert login(member).post(url).status_code == 204
    assert not Membership.objects.filter(user=member).exists()


# --- Project types ----------------------------------------------------------------


def test_project_types_are_readable_by_a_shell_member_but_admin_only_to_write(
    tree, member
):
    grant(member, tree["A1"], "admin")  # admin of a sub-project, shell on W
    client = login(member)

    listed = client.get(f"/api/project-types/?workspace={tree.workspace.pk}")
    created = client.post(
        "/api/project-types/",
        {"workspace": tree.workspace.pk, "name": "Festival"},
        format="json",
    )

    assert [t["name"] for t in listed.data] == ["Autre"]
    assert created.status_code == 403


def test_types_of_a_foreign_workspace_are_invisible(tree, member):
    grant(member, tree.workspace, "admin")
    client = login(member)
    foreign = ProjectType.objects.get(workspace=tree.other_workspace)

    assert client.get(f"/api/project-types/{foreign.pk}/").status_code == 404
    assert (
        client.post(
            "/api/project-types/",
            {"workspace": tree.other_workspace.pk, "name": "X"},
            format="json",
        ).status_code
        == 404
    )


def test_duplicate_type_name_is_refused_case_insensitively(tree):
    response = login(tree.owner).post(
        "/api/project-types/",
        {"workspace": tree.workspace.pk, "name": "AUTRE"},
        format="json",
    )
    assert response.status_code == 400


def test_deleting_a_type_in_use_moves_projects_to_the_fallback(tree):
    clip = ProjectType.objects.create(workspace=tree.workspace, name="Clip")
    tree["A"].type = clip
    tree["A"].save()

    response = login(tree.owner).delete(f"/api/project-types/{clip.pk}/")

    assert response.status_code == 204
    tree["A"].refresh_from_db()
    assert tree["A"].type.name == "Autre"


def test_deleting_the_last_type_in_use_is_refused(tree):
    fallback = ProjectType.objects.get(workspace=tree.workspace)

    response = login(tree.owner).delete(f"/api/project-types/{fallback.pk}/")

    assert response.status_code == 400
    assert ProjectType.objects.filter(pk=fallback.pk).exists()


# --- Tags ---------------------------------------------------------------------------


def test_a_project_editor_can_create_tags_but_not_rename_them(tree, member):
    grant(member, tree["A"], "editor")
    client = login(member)

    created = client.post(
        "/api/tags/",
        {"workspace": tree.workspace.pk, "name": "urgent", "color": "#FECACA"},
        format="json",
    )
    renamed = client.patch(
        f"/api/tags/{created.data['id']}/", {"name": "pas urgent"}, format="json"
    )

    assert created.status_code == 201
    assert renamed.status_code == 403


def test_viewers_and_outsiders_cannot_create_tags(tree, member):
    client = login(member)
    payload = {"workspace": tree.workspace.pk, "name": "com"}
    assert client.post("/api/tags/", payload, format="json").status_code == 404

    grant(member, tree.workspace, "viewer")
    assert login(member).post("/api/tags/", payload, format="json").status_code == 403


def test_tag_names_are_unique_per_workspace(tree):
    Tag.objects.create(workspace=tree.workspace, name="Com")
    client = login(tree.owner)

    same = client.post(
        "/api/tags/", {"workspace": tree.workspace.pk, "name": "com"}, format="json"
    )
    assert same.status_code == 400
