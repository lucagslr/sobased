"""API permission matrix (SPEC §6): role x action x tree depth x origin of the
access (direct, inherited from the root project, inherited from the workspace),
plus the shell and outsider cases.

`expected_status()` is the permission table of SPECIFICATIONS §1.3 written as
code. It knows nothing about the implementation: it only reasons on the role,
the depth, and whether the role also applies to the container of the target
(its parent, or the workspace for a root project).
"""

import pytest

from apps.accounts.tests.factories import UserFactory

from .factories import BY_DEPTH, grant

pytestmark = pytest.mark.django_db

ROLES = ["viewer", "commenter", "editor", "admin", "owner"]
RANK = {role: index for index, role in enumerate(ROLES)}
ACTIONS = [
    "retrieve",
    "list_members",
    "update",
    "create_child",
    "invite",
    "move",
    "delete",
    "transfer",
]
DEPTHS = [1, 2, 3, 4]
# Where the membership is placed, relative to the target project.
ORIGINS = ["direct", "root", "workspace"]


def at_least(role: str, minimum: str) -> bool:
    return RANK[role] >= RANK[minimum]


def expected_status(role: str, action: str, depth: int, origin: str) -> int:
    # Does the same role also apply to the target's container (its parent, or
    # the workspace for a root project)? Only when the grant sits above it.
    if origin == "workspace":
        on_container = True
    elif origin == "root":
        on_container = depth > 1  # a grant on R covers the parents of A, A1, A1x
    else:
        on_container = False  # direct grant: the container is only a shell

    if action in ("retrieve", "list_members"):
        return 200
    if action == "update":
        return 200 if at_least(role, "editor") else 403
    if action == "create_child":
        if not at_least(role, "editor"):
            return 403
        return 400 if depth == 4 else 201  # level 5 does not exist
    if action == "invite":
        return 201 if at_least(role, "admin") else 403
    if action == "move":
        if not at_least(role, "admin"):
            return 403
        return 200 if on_container else 403
    if action == "delete":
        if depth == 1:
            return 204 if role == "owner" else 403
        return 204 if on_container and at_least(role, "editor") else 403
    if action == "transfer":
        if role != "owner":
            return 403
        return 200 if depth == 1 else 400  # only root projects have an owner
    raise AssertionError(action)


def perform(client, action: str, target, guest):
    """Send the request for `action` on `target`; returns the HTTP status."""
    url = f"/api/projects/{target.pk}/"
    if action == "retrieve":
        return client.get(url).status_code
    if action == "list_members":
        return client.get(f"/api/memberships/?project={target.pk}").status_code
    if action == "update":
        return client.patch(url, {"name": "Renommé"}, format="json").status_code
    if action == "create_child":
        payload = {"parent": target.pk, "name": "Enfant"}
        return client.post("/api/projects/", payload, format="json").status_code
    if action == "invite":
        # Someone with no access yet ("guest" is already a member of R).
        newcomer = UserFactory(username="newcomer")
        payload = {
            "project": target.pk,
            "username": newcomer.username,
            "role": "viewer",
        }
        return client.post("/api/memberships/", payload, format="json").status_code
    if action == "move":  # same parent: a permission check without side effect
        payload = {"parent": target.parent_id}
        return client.post(f"{url}move/", payload, format="json").status_code
    if action == "delete":
        return client.delete(url).status_code
    if action == "transfer":
        payload = {"username": guest.username}
        return client.post(
            f"{url}transfer-ownership/", payload, format="json"
        ).status_code
    raise AssertionError(action)


@pytest.fixture
def guest(tree):
    """A third user: invited by the tests, and a direct member of R so that
    ownership of R can be transferred to them."""
    user = UserFactory(username="guest")
    grant(user, tree["R"], "viewer")
    return user


def place_membership(tree, member, role, depth, origin):
    target = tree[BY_DEPTH[depth]]
    if origin == "workspace":
        if role == "owner":
            # A workspace has one owner: hand it over to the member under test.
            tree.workspace.memberships.filter(role="owner").update(role="admin")
        grant(member, tree.workspace, role)
    elif origin == "root":
        grant(member, tree["R"], role)
    else:
        grant(member, target, role)
    return target


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("origin", ORIGINS)
@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("role", ROLES)
def test_matrix(tree, member, member_api, guest, role, depth, origin, action):
    if origin == "root" and depth == 1:
        pytest.skip("same case as a direct grant on the root project")
    target = place_membership(tree, member, role, depth, origin)

    status = perform(member_api, action, target, guest)

    assert status == expected_status(role, action, depth, origin)


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("depth", [1, 2, 3])
def test_shell_gets_nothing_but_the_reduced_view(
    tree, member, member_api, guest, depth, action
):
    """Admin of a CHILD only: the target is a shell for them."""
    target = tree[BY_DEPTH[depth]]
    grant(member, tree[BY_DEPTH[depth + 1]], "admin")

    status = perform(member_api, action, target, guest)

    if action == "retrieve":
        assert status == 200
    elif action == "create_child":
        assert status in (403, 404)  # never created
    else:
        assert status == 404


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("depth", DEPTHS)
def test_outsider_sees_nothing(tree, member_api, guest, depth, action):
    target = tree[BY_DEPTH[depth]]

    assert perform(member_api, action, target, guest) == 404


@pytest.mark.parametrize("action", ACTIONS)
def test_anonymous_is_rejected(tree, api, guest, action):
    assert perform(api, action, tree["A"], guest) == 401


def test_shell_view_leaks_no_content(tree, member, member_api):
    grant(member, tree["A1"], "editor")
    tree["R"].description = "secret"
    tree["R"].save()

    data = member_api.get(f"/api/projects/{tree['R'].pk}/").data

    assert data["is_shell"] is True
    assert set(data) == {
        "id",
        "workspace",
        "parent",
        "depth",
        "name",
        "color",
        "is_shell",
        "breadcrumb",
    }


def test_sibling_branch_of_a_shell_member_is_invisible(tree, member, member_api):
    grant(member, tree["A1"], "editor")

    assert member_api.get(f"/api/projects/{tree['A2'].pk}/").status_code == 404
    assert member_api.get(f"/api/projects/{tree['B'].pk}/").status_code == 404
    assert member_api.get(f"/api/projects/{tree['Z'].pk}/").status_code == 404
