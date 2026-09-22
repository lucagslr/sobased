"""Project tree rules: creation, depth limit, tree endpoint, move, computed state."""

from datetime import date, timedelta

import pytest

from apps.projects import tree as tree_module
from apps.projects.models import Membership, Project
from apps.workspaces.models import ProjectType

from .factories import ProjectFactory, TagFactory, grant

pytestmark = pytest.mark.django_db
TODAY = date(2026, 9, 21)


# --- Creation -------------------------------------------------------------------


def test_root_project_creator_becomes_its_owner(tree, member, member_api):
    grant(member, tree.workspace, "editor")

    response = member_api.post(
        "/api/projects/",
        {"workspace": tree.workspace.pk, "name": "SHORTY7G"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["depth"] == 1
    assert response.data["my_role"] == "owner"
    assert response.data["type_name"] == "Autre"  # fallback type
    project = Project.objects.get(name="SHORTY7G")
    assert project.created_by == member
    assert Membership.objects.filter(
        project=project, user=member, role="owner"
    ).exists()


def test_sub_project_inherits_workspace_and_depth_and_creates_no_owner(
    tree, member, member_api
):
    grant(member, tree["A"], "editor")

    response = member_api.post(
        "/api/projects/", {"parent": tree["A"].pk, "name": "Clip"}, format="json"
    )

    assert response.status_code == 201
    assert (response.data["depth"], response.data["workspace"]) == (
        3,
        tree.workspace.pk,
    )
    assert response.data["my_role"] == "editor"
    assert [crumb["name"] for crumb in response.data["breadcrumb"]] == ["R", "A"]
    assert not Membership.objects.filter(project_id=response.data["id"]).exists()


def test_a_fifth_level_is_refused(tree, owner_api):
    response = owner_api.post(
        "/api/projects/", {"parent": tree["A1x"].pk, "name": "Trop"}, format="json"
    )

    assert response.status_code == 400
    assert "4 niveaux" in str(response.data["parent"])


def test_database_refuses_a_fifth_level_even_without_the_api(tree):
    """Last line of defence: the CHECK constraint on `depth`."""
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        ProjectFactory(workspace=tree.workspace, parent=tree["A1x"])


def test_workspace_viewer_cannot_create_a_root_project(tree, member, member_api):
    grant(member, tree.workspace, "viewer")

    response = member_api.post(
        "/api/projects/", {"workspace": tree.workspace.pk, "name": "X"}, format="json"
    )
    assert response.status_code == 403


def test_cannot_create_in_a_workspace_i_do_not_belong_to(tree, member, member_api):
    grant(member, tree.workspace, "admin")

    response = member_api.post(
        "/api/projects/",
        {"workspace": tree.other_workspace.pk, "name": "X"},
        format="json",
    )
    assert response.status_code == 404


def test_type_and_tags_must_belong_to_the_workspace(tree, owner_api):
    foreign_type = ProjectType.objects.get(workspace=tree.other_workspace)
    foreign_tag = TagFactory(workspace=tree.other_workspace)

    bad_type = owner_api.post(
        "/api/projects/",
        {"workspace": tree.workspace.pk, "name": "X", "type": foreign_type.pk},
        format="json",
    )
    bad_tag = owner_api.patch(
        f"/api/projects/{tree['A'].pk}/", {"tags": [foreign_tag.pk]}, format="json"
    )

    assert bad_type.status_code == 400 and "type" in bad_type.data
    assert bad_tag.status_code == 400 and "tags" in bad_tag.data


def test_end_date_cannot_precede_start_date(tree, owner_api):
    response = owner_api.patch(
        f"/api/projects/{tree['A'].pk}/",
        {"start_date": "2026-10-12", "end_date": "2026-10-01"},
        format="json",
    )
    assert response.status_code == 400 and "end_date" in response.data


def test_patch_cannot_move_a_project(tree, owner_api):
    owner_api.patch(
        f"/api/projects/{tree['A1'].pk}/", {"parent": tree["B"].pk}, format="json"
    )

    tree["A1"].refresh_from_db()
    assert tree["A1"].parent == tree["A"]


# --- Tree endpoint ------------------------------------------------------------------


def test_tree_for_a_full_member(tree, owner_api):
    nodes = owner_api.get("/api/projects/tree/").data

    assert {node["name"] for node in nodes} == {"R", "A", "A1", "A1x", "A2", "B", "R2"}
    root = next(node for node in nodes if node["name"] == "R")
    assert (root["my_role"], root["is_shell"], root["status"]) == (
        "owner",
        False,
        "planned",
    )
    assert root["can_view_finance"] is True


def test_tree_for_a_sub_project_guest_shows_only_the_branch(tree, member, member_api):
    """SPEC §6: the root appears in the navigation with only their branch."""
    grant(member, tree["A1"], "commenter")
    tree["R"].status = "in_progress"
    tree["R"].end_date = date(2020, 1, 1)
    tree["R"].save()
    tree["R"].tags.add(TagFactory(workspace=tree.workspace))

    nodes = {node["name"]: node for node in member_api.get("/api/projects/tree/").data}

    assert set(nodes) == {"R", "A", "A1", "A1x"}
    for name in ("R", "A"):
        shell = nodes[name]
        assert shell["is_shell"] is True and shell["my_role"] is None
        leaked = [
            shell[key]
            for key in (
                "type",
                "type_name",
                "status",
                "start_date",
                "end_date",
                "temporal",
            )
        ]
        assert leaked == [None] * 6
        assert shell["tags"] == [] and shell["end_overdue"] is False
    assert nodes["A1"]["my_role"] == "commenter"
    assert nodes["A1x"]["my_role"] == "commenter"  # inherited


def test_tree_hides_archived_projects_unless_asked(tree, owner_api):
    tree["B"].status = "archived"
    tree["B"].save()

    default = {n["name"] for n in owner_api.get("/api/projects/tree/").data}
    full = {
        n["name"]
        for n in owner_api.get("/api/projects/tree/?include_archived=true").data
    }

    assert "B" not in default and "B" in full


def test_an_archived_project_hides_its_whole_branch(tree, owner_api):
    # Without this, A1, A1x and A2 would show up as roots (parent missing).
    tree["A"].status = "archived"
    tree["A"].save()

    default = {n["name"] for n in owner_api.get("/api/projects/tree/").data}
    full = {
        n["name"]
        for n in owner_api.get("/api/projects/tree/?include_archived=true").data
    }

    assert default == {"R", "B", "R2"}
    assert full == {"R", "A", "A1", "A1x", "A2", "B", "R2"}


def test_tree_can_be_limited_to_one_workspace(tree, member, member_api):
    grant(member, tree.workspace, "viewer")
    grant(member, tree.other_workspace, "viewer")

    nodes = member_api.get(f"/api/projects/tree/?workspace={tree.other_workspace.pk}")

    assert [node["name"] for node in nodes.data] == ["Z"]


# --- Move ---------------------------------------------------------------------------


def test_move_updates_the_depth_of_the_whole_subtree(tree, owner_api):
    response = owner_api.post(
        f"/api/projects/{tree['A1'].pk}/move/", {"parent": tree["R2"].pk}, format="json"
    )

    assert response.status_code == 200
    assert response.data["depth"] == 2
    tree["A1x"].refresh_from_db()
    assert tree["A1x"].depth == 3


@pytest.mark.parametrize(
    "project, new_parent, message",
    [
        ("A", "A1", "lui-même"),  # into its own subtree
        ("A", "A", "lui-même"),
        ("A", "B", "4 niveaux"),  # A spans 3 levels: under depth 2 that makes 5
        ("A", "Z", "même espace"),
    ],
)
def test_impossible_moves_are_refused(
    tree, member, member_api, project, new_parent, message
):
    grant(member, tree.workspace, "admin")
    grant(member, tree.other_workspace, "admin")

    response = member_api.post(
        f"/api/projects/{tree[project].pk}/move/",
        {"parent": tree[new_parent].pk},
        format="json",
    )

    assert response.status_code == 400
    assert message in str(response.data["parent"])
    tree[project].refresh_from_db()
    assert tree[project].depth == 2


def test_move_to_root_level(tree, owner_api):
    response = owner_api.post(
        f"/api/projects/{tree['B'].pk}/move/", {"parent": None}, format="json"
    )

    assert response.status_code == 200
    assert (response.data["parent"], response.data["depth"]) == (None, 1)


# --- Deletion and ownership ---------------------------------------------------------


def test_deleting_a_project_deletes_its_subtree(tree, owner_api):
    assert owner_api.delete(f"/api/projects/{tree['A'].pk}/").status_code == 204

    assert set(
        Project.objects.filter(workspace=tree.workspace).values_list("name", flat=True)
    ) == {
        "R",
        "B",
        "R2",
    }


def test_transfer_ownership_of_a_root_project(tree, member, member_api):
    from apps.accounts.tests.factories import UserFactory

    heir = UserFactory(username="heir")
    grant(member, tree["R2"], "owner")
    grant(heir, tree["R2"], "editor")

    response = member_api.post(
        f"/api/projects/{tree['R2'].pk}/transfer-ownership/",
        {"username": "heir"},
        format="json",
    )

    assert response.status_code == 200
    roles = dict(
        Membership.objects.filter(project=tree["R2"]).values_list(
            "user__username", "role"
        )
    )
    assert roles == {"heir": "owner", "member": "admin"}


def test_transfer_needs_a_direct_member(tree, member, member_api):
    grant(member, tree["R2"], "owner")

    response = member_api.post(
        f"/api/projects/{tree['R2'].pk}/transfer-ownership/",
        {"username": "wsowner"},  # has access through the workspace only
        format="json",
    )
    assert response.status_code == 400


# --- Computed state (pure functions) ------------------------------------------------


@pytest.mark.parametrize(
    "status, start, expected",
    [
        ("done", None, "past"),
        ("cancelled", TODAY + timedelta(days=5), "past"),
        ("archived", None, "past"),
        ("in_progress", TODAY + timedelta(days=1), "upcoming"),
        ("idea", None, "upcoming"),
        ("planned", None, "upcoming"),
        ("planned", TODAY - timedelta(days=1), "current"),
        ("in_progress", None, "current"),
        ("to_validate", TODAY, "current"),
    ],
)
def test_temporal(status, start, expected):
    assert tree_module.temporal(status, start, TODAY) == expected


@pytest.mark.parametrize(
    "status, end, expected",
    [
        ("in_progress", TODAY - timedelta(days=1), True),
        ("in_progress", TODAY, False),  # the last day is not overdue yet
        ("in_progress", None, False),
        ("done", TODAY - timedelta(days=30), False),
        ("archived", TODAY - timedelta(days=30), False),
    ],
)
def test_end_overdue(status, end, expected):
    assert tree_module.end_overdue(status, end, TODAY) is expected


def test_overdue_open_project_stays_current_not_past():
    """Until someone answers the overdue modal, it is not "past"."""
    assert (
        tree_module.temporal("in_progress", TODAY - timedelta(days=90), TODAY)
        == "current"
    )
