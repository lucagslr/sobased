"""The journal (SPEC §14): every wrapped verb writes a row with the key
fields that changed, the API is per project for editors and up, money
entries need the finance flag, old rows are purged."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.activity import services
from apps.activity.models import ActivityEntry, Verb
from apps.files.tests.conftest import make_asset
from apps.finance.models import Category
from apps.projects.tests.factories import Tree, grant
from apps.tasks.tests.conftest import client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree(db):
    return Tree()


@pytest.fixture
def editor(tree):
    user = UserFactory(username="editor")
    grant(user, tree.workspace, "editor", can_view_finance=True, can_edit_finance=True)
    return user


@pytest.fixture
def api(editor):
    return client_for(editor)


def entries(project=None, **filters):
    queryset = ActivityEntry.objects.filter(**filters)
    if project is not None:
        queryset = queryset.filter(project=project)
    return list(queryset.order_by("id"))


# --- Writing --------------------------------------------------------------------------
def test_task_lifecycle_is_journaled(api, editor, tree):
    colleague = UserFactory(username="colleague")
    grant(colleague, tree["A"], "editor")
    created = api.post(
        "/api/tasks/",
        {"project": tree["A"].pk, "title": "Brief", "priority": 2},
        format="json",
    ).data
    api.patch(
        f"/api/tasks/{created['id']}/",
        {"title": "Brief radio", "assignee_usernames": ["colleague"]},
        format="json",
    )
    api.patch(f"/api/tasks/{created['id']}/", {"status": "done"}, format="json")
    api.patch(f"/api/tasks/{created['id']}/", {"status": "done"}, format="json")
    api.delete(f"/api/tasks/{created['id']}/")

    rows = entries(tree["A"], target_type="task")
    assert [row.verb for row in rows] == [
        Verb.CREATED,
        Verb.UPDATED,
        Verb.STATUS_CHANGED,
        Verb.DELETED,
    ]
    assert rows[0].actor == editor and rows[0].target_label == "Brief"
    assert rows[1].changes == {
        "title": ["Brief", "Brief radio"],
        "assignees": [[], ["Prénom " + colleague.last_name]],
    }
    assert rows[2].changes == {"status": ["todo", "done"]}
    assert rows[3].target_id == created["id"] and rows[3].target_label == "Brief radio"
    assert rows[3].workspace == tree.workspace


def test_project_move_delete_and_rights(tree, editor):
    owner_api = client_for(tree.owner)
    sub = owner_api.post(
        "/api/projects/",
        {"workspace": tree.workspace.pk, "parent": tree["A"].pk, "name": "Clip"},
        format="json",
    ).data
    assert entries(target_type="project", target_id=sub["id"])[0].verb == Verb.CREATED
    owner_api.post(f"/api/projects/{sub['id']}/move/", {"parent": tree["B"].pk})
    [moved] = entries(verb=Verb.UPDATED, target_type="project")
    assert moved.changes == {"parent": ["A", "B"]}

    # Rights: granting, changing and removing a membership on the project.
    newcomer = UserFactory(username="newcomer")
    owner_api.post(
        "/api/memberships/",
        {"project": sub["id"], "username": "newcomer", "role": "viewer"},
        format="json",
    )
    membership = newcomer.memberships.get()
    owner_api.patch(f"/api/memberships/{membership.pk}/", {"role": "editor"})
    owner_api.delete(f"/api/memberships/{membership.pk}/")
    rights = entries(verb=Verb.ACCESS_CHANGED, target_type="membership")
    assert [r.changes["role"] for r in rights] == [
        [None, "Lecteur"],
        ["Lecteur", "Éditeur"],
        ["Éditeur", None],
    ]
    assert all(r.target_label == newcomer.display_name for r in rights)

    # Deleting a sub-project is journaled against its parent.
    owner_api.delete(f"/api/projects/{sub['id']}/")
    [deleted] = entries(verb=Verb.DELETED, target_type="project")
    assert deleted.project == tree["B"] and deleted.target_label == "Clip"
    # Its own history survives, attached to the workspace alone.
    orphans = ActivityEntry.objects.filter(project__isnull=True)
    assert orphans.count() == 5 and all(o.workspace == tree.workspace for o in orphans)


def test_workspace_membership_belongs_to_the_workspace_alone(tree):
    owner_api = client_for(tree.owner)
    newcomer = UserFactory(username="newcomer")
    owner_api.post(
        "/api/memberships/",
        {"workspace": tree.workspace.pk, "username": "newcomer", "role": "editor"},
        format="json",
    )
    [row] = entries(verb=Verb.ACCESS_CHANGED)
    assert row.project is None and row.workspace == tree.workspace
    assert row.target_label == newcomer.display_name


def test_asset_status_versions_and_share_link(api, editor, tree):
    asset = make_asset(tree["A"], editor, name="Cover")
    api.post(f"/api/assets/{asset.pk}/status/", {"status": "to_validate"})
    api.post(f"/api/assets/{asset.pk}/status/", {"status": "to_validate"})
    from apps.files.tests.conftest import png_upload

    api.post(f"/api/assets/{asset.pk}/versions/", {"file": png_upload("v2.png")})
    link = api.post(
        "/api/share-links/",
        {"target_type": "asset", "asset": asset.pk, "title": "Écoute"},
        format="json",
    ).data
    api.post(f"/api/share-links/{link['id']}/revoke/")

    rows = entries(tree["A"])
    assert [(r.verb, r.target_type) for r in rows] == [
        (Verb.STATUS_CHANGED, "asset"),
        (Verb.UPDATED, "asset"),
        (Verb.SHARED, "share_link"),
        (Verb.STATUS_CHANGED, "share_link"),
    ]
    assert rows[0].changes == {"status": ["draft", "to_validate"]}
    assert rows[1].changes == {"version": [1, 2]}
    assert rows[3].changes == {"status": ["active", "revoked"]}


# --- Reading --------------------------------------------------------------------------
def test_listing_needs_editor_and_hides_money_without_the_flag(api, editor, tree):
    Category.create_defaults(tree.workspace)
    category = Category.objects.filter(workspace=tree.workspace).first()
    api.post(
        "/api/tasks/", {"project": tree["A1"].pk, "title": "Sous-tâche"}, format="json"
    )
    api.post(
        "/api/transactions/",
        {
            "project": tree["A"].pk,
            "kind": "expense",
            "amount": "250.00",
            "date": "2026-09-01",
            "label": "Cachet",
            "category": category.pk,
        },
        format="json",
    )
    assert ActivityEntry.objects.filter(target_type="transaction").exists()

    # Editor with finance: both; descendants only when asked.
    response = api.get("/api/activity/", {"project": tree["A"].pk})
    assert [e["target_type"] for e in response.data["results"]] == ["transaction"]
    response = api.get(
        "/api/activity/", {"project": tree["A"].pk, "include_descendants": "true"}
    )
    assert sorted(e["target_type"] for e in response.data["results"]) == [
        "task",
        "transaction",
    ]
    assert response.data["results"][0]["actor"]["username"] == "editor"
    assert response.data["results"][0]["project_name"] in ("A", "A1")

    # Editor without finance: the transaction entry disappears.
    blind = UserFactory(username="blind")
    grant(blind, tree["A"], "editor")
    response = client_for(blind).get(
        "/api/activity/", {"project": tree["A"].pk, "include_descendants": "1"}
    )
    assert [e["target_type"] for e in response.data["results"]] == ["task"]

    # Viewer: 403 (the project is visible, the journal is not); stranger: 404.
    viewer = UserFactory(username="viewer")
    grant(viewer, tree["A"], "viewer")
    assert (
        client_for(viewer).get("/api/activity/", {"project": tree["A"].pk}).status_code
        == 403
    )
    stranger = UserFactory(username="stranger")
    assert (
        client_for(stranger)
        .get("/api/activity/", {"project": tree["A"].pk})
        .status_code
        == 404
    )
    assert api.get("/api/activity/").status_code == 400

    # Filters.
    response = api.get("/api/activity/", {"project": tree["A"].pk, "verb": "deleted"})
    assert response.data["results"] == []
    response = api.get(
        "/api/activity/",
        {"project": tree["A"].pk, "include_descendants": "1", "actor": "EDITOR"},
    )
    assert response.data["count"] == 2


# --- Services -------------------------------------------------------------------------
def test_snapshot_serialises_values_for_display(tree, editor):
    asset = make_asset(tree["A"], editor)
    snap = services.snapshot(asset, ("name", "created_by", "followers", "created_at"))
    assert snap["name"] == "Cover" and snap["created_by"] == editor.display_name
    assert snap["followers"] == [editor.display_name]
    assert snap["created_at"] == asset.created_at.isoformat()
    assert services._serialise(Decimal("12.50")) == "12.50"
    assert services.diff({"a": 1, "b": 2}, {"a": 1, "b": 3}) == {"b": [2, 3]}


def test_purge_keeps_twelve_months(tree, editor):
    old = services.log(editor, Verb.CREATED, tree["A"], target_type="project")
    ActivityEntry.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=366)
    )
    services.log(editor, Verb.CREATED, tree["B"], target_type="project")
    assert services.purge() == 1
    assert ActivityEntry.objects.count() == 1
