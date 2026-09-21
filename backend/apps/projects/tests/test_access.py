"""Resolution of access rights (access.py): inheritance, shells, finance flags.

The expected result of each case comes from a hand-written oracle built on the
ANCESTORS table, not from the code under test.
"""

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.projects.access import (
    NO_ACCESS,
    Role,
    build_access_map,
    effective_access,
    workspace_access,
)
from apps.projects.models import Project

from .factories import ANCESTORS, grant

pytestmark = pytest.mark.django_db

ROLES = ["viewer", "commenter", "editor", "admin", "owner"]
NODES_IN_W = ["R", "A", "A1", "A1x", "A2", "B", "R2"]


def expected(grant_on: str, target: str) -> str:
    """'role', 'shell' or 'none' for a single grant placed on `grant_on`."""
    if target == "Z":  # another workspace: never reachable
        return "none"
    if grant_on == "W":
        return "role"
    if grant_on == target or grant_on in ANCESTORS[target]:
        return "role"
    if target in ANCESTORS[grant_on]:
        return "shell"
    return "none"


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("grant_on", ["W", "R", "A", "A1", "A1x"])
@pytest.mark.parametrize("target", [*NODES_IN_W, "Z"])
def test_single_grant_matrix(tree, member, role, grant_on, target):
    if role == "owner" and grant_on == "W":
        pytest.skip("the workspace already has its single owner")
    scope = tree.workspace if grant_on == "W" else tree[grant_on]
    grant(member, scope, role)

    access = effective_access(member, tree[target])

    outcome = expected(grant_on, target)
    if outcome == "role":
        assert access.role == Role.from_stored(role)
        assert not access.is_shell
    elif outcome == "shell":
        assert access.role is None and access.is_shell
    else:
        assert access == NO_ACCESS


def test_no_membership_means_nothing_is_visible(tree, member):
    access_map = build_access_map(member)

    assert access_map.projects == {} and access_map.workspaces == {}


def test_highest_role_wins_when_granted_lower_in_the_tree(tree, member):
    grant(member, tree["R"], "viewer")
    grant(member, tree["A1"], "admin")

    assert effective_access(member, tree["R"]).role == Role.VIEWER
    assert effective_access(member, tree["A"]).role == Role.VIEWER
    assert effective_access(member, tree["A1"]).role == Role.ADMIN
    assert effective_access(member, tree["A1x"]).role == Role.ADMIN  # inherited
    assert effective_access(member, tree["A2"]).role == Role.VIEWER


def test_a_lower_grant_never_reduces_an_inherited_right(tree, member):
    grant(member, tree.workspace, "admin", can_view_finance=True)
    grant(member, tree["A"], "viewer")

    access = effective_access(member, tree["A1"])

    assert access.role == Role.ADMIN
    assert access.can_view_finance


def test_finance_flags_are_ored_and_inherited(tree, member):
    grant(member, tree["R"], "editor")
    grant(member, tree["A"], "viewer", can_view_finance=True)
    grant(member, tree["A1"], "viewer", can_edit_finance=True)

    assert not effective_access(member, tree["R"]).can_view_finance
    assert not effective_access(member, tree["B"]).can_view_finance
    a = effective_access(member, tree["A"])
    assert (a.role, a.can_view_finance, a.can_edit_finance) == (
        Role.EDITOR,
        True,
        False,
    )
    a1x = effective_access(member, tree["A1x"])
    assert (a1x.can_view_finance, a1x.can_edit_finance) == (True, True)


def test_owner_always_has_finance_and_edit_implies_view(tree, member):
    owner = grant(member, tree["R2"], "owner")
    assert owner.can_view_finance and owner.can_edit_finance

    editor = grant(member, tree["B"], "editor", can_edit_finance=True)
    assert editor.can_view_finance


def test_shell_covers_ancestors_and_workspace_only(tree, member):
    grant(member, tree["A1"], "editor")
    access_map = build_access_map(member)

    visible = {tree.name_of(pid) for pid in access_map.projects}
    assert visible == {"R", "A", "A1", "A1x"}  # not A2, B, R2, Z
    assert access_map.for_project(tree["R"].pk).is_shell
    assert access_map.for_project(tree["A"].pk).is_shell
    assert workspace_access(member, tree.workspace).is_shell
    assert workspace_access(member, tree.other_workspace) == NO_ACCESS
    # A shell grants no content: it is never part of a rights filter.
    assert {tree.name_of(pid) for pid in access_map.project_ids()} == {"A1", "A1x"}


def test_a_real_role_replaces_the_shell(tree, member):
    grant(member, tree["A1"], "editor")
    grant(member, tree["R"], "viewer")

    assert effective_access(member, tree["R"]) == effective_access(member, tree["A"])
    assert not effective_access(member, tree["A"]).is_shell


def test_inactive_and_anonymous_users_have_no_access(tree, member):
    grant(member, tree.workspace, "admin")
    member.is_active = False
    member.save()

    assert build_access_map(member).projects == {}
    assert build_access_map(AnonymousUser()).projects == {}


def test_map_is_resolved_in_three_queries(tree, member, django_assert_max_num_queries):
    grant(member, tree["A1"], "editor")
    grant(member, tree.other_workspace, "viewer")

    with django_assert_max_num_queries(3):
        build_access_map(member)


def test_for_user_filters_by_role_and_finance(tree, member):
    grant(member, tree["R"], "viewer")
    grant(member, tree["A"], "editor", can_view_finance=True)

    def names(queryset):
        return {project.name for project in queryset}

    assert names(Project.objects.for_user(member)) == {"R", "A", "A1", "A1x", "A2", "B"}
    assert names(Project.objects.for_user(member, Role.EDITOR)) == {
        "A",
        "A1",
        "A1x",
        "A2",
    }
    assert names(Project.objects.for_user(member, finance="view")) == {
        "A",
        "A1",
        "A1x",
        "A2",
    }
    assert names(Project.objects.for_user(member, finance="edit")) == set()


def test_access_map_is_cached_per_request(tree, member, rf, django_assert_num_queries):
    grant(member, tree["R"], "viewer")
    request = rf.get("/")
    request.user = member

    effective_access(request, tree["A"])
    with django_assert_num_queries(0):
        assert effective_access(request, tree["B"]).role == Role.VIEWER
