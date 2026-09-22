"""Export of my data and deletion of my account (SPEC §16, SPECIFICATIONS §11)."""

import io
import json
import zipfile
from datetime import timedelta

import pytest
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.accounts import exports, services
from apps.accounts.models import DataExport
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.events.models import Event
from apps.files.tests.conftest import make_asset
from apps.finance.models import Category
from apps.finance.tests.conftest import make_transaction
from apps.integrations.google import REVOKE_URL
from apps.integrations.models import OAuthAccount
from apps.integrations.tests.conftest import fake_google  # noqa: F401  (fixture)
from apps.integrations.tests.conftest import connect_google
from apps.notifications.models import Notification
from apps.projects.models import Membership
from apps.projects.tests.factories import Tree, grant
from apps.tasks.models import Task, TaskComment
from apps.tasks.tests.conftest import client_for
from apps.workspaces.models import Workspace

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree(db):
    return Tree()


@pytest.fixture
def me(tree):
    user = UserFactory(username="me", first_name="Moi", last_name="Même")
    grant(user, tree["A"], "editor", can_view_finance=True, can_edit_finance=True)
    return user


@pytest.fixture
def api(me):
    return client_for(me)


# --- Export ---------------------------------------------------------------------------
def test_archive_contains_my_data_and_files(me, tree):
    other = UserFactory(username="other")
    mine = Task.objects.create(project=tree["A"], title="Ma tâche", created_by=me)
    assigned = Task.objects.create(
        project=tree["A"], title="Pour moi", created_by=other
    )
    assigned.assignees.add(me)
    Task.objects.create(project=tree["A"], title="Pas à moi", created_by=other)
    TaskComment.objects.create(task=mine, author=me, body="Note à moi")
    Event.objects.create(
        project=tree["A"],
        title="Séance",
        start=timezone.now(),
        end=timezone.now() + timedelta(hours=1),
        created_by=me,
    )
    Category.create_defaults(tree.workspace)
    category = Category.objects.filter(workspace=tree.workspace).first()
    make_transaction(tree["A"], category, label="Cachet", created_by=me)
    make_asset(tree["A"], me, name="Cover")
    make_asset(tree["A"], other, name="Pas la mienne")

    buffer = io.BytesIO()
    exports.write_archive(me, buffer)
    archive = zipfile.ZipFile(buffer)
    names = archive.namelist()
    assert {"LISEZMOI.txt", "profile.json", "tasks.json", "comments.json"} <= set(names)
    files = [n for n in names if n.startswith("fichiers/")]
    assert len(files) == 1 and files[0].endswith("-v1-cover.png")

    profile = json.loads(archive.read("profile.json"))
    assert profile["username"] == "me" and profile["email"] == me.email
    tasks = json.loads(archive.read("tasks.json"))
    assert sorted(t["title"] for t in tasks) == ["Ma tâche", "Pour moi"]
    assert [c["body"] for c in json.loads(archive.read("comments.json"))] == [
        "Note à moi"
    ]
    assert [e["title"] for e in json.loads(archive.read("events.json"))] == ["Séance"]
    [tx] = json.loads(archive.read("transactions.json"))
    assert tx["label"] == "Cachet" and tx["amount"] == "100.00"
    [membership] = json.loads(archive.read("memberships.json"))
    assert membership["scope_name"] == "A" and membership["role"] == "editor"


def test_export_endpoints(api, me, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = api.post("/api/me/exports/")
    assert response.status_code == 202
    export = DataExport.objects.get(pk=response.data["id"])
    assert export.status == "ready" and export.archive and export.size_bytes > 0
    assert export.expires_at > timezone.now() + timedelta(days=6)

    listing = api.get("/api/me/exports/").data
    assert listing[0]["id"] == export.pk and listing[0]["is_available"] is True
    download = api.get(f"/api/me/exports/{export.pk}/download/")
    assert download.status_code == 200
    assert download["Content-Disposition"].startswith("attachment")

    # One pending at a time; a stranger's export is a 404; expiry closes it.
    DataExport.objects.create(user=me)
    assert api.post("/api/me/exports/").status_code == 400
    stranger = client_for(UserFactory(username="stranger"))
    assert stranger.get(f"/api/me/exports/{export.pk}/download/").status_code == 404
    export.expires_at = timezone.now() - timedelta(minutes=1)
    export.save()
    assert api.get(f"/api/me/exports/{export.pk}/download/").status_code == 404


def test_purge_removes_the_archive_file(me, django_capture_on_commit_callbacks):
    from apps.accounts.tasks import purge_expired_exports

    export = DataExport.objects.create(user=me)
    exports.build(export)
    name = export.archive.name
    assert default_storage.exists(name)
    DataExport.objects.filter(pk=export.pk).update(
        expires_at=timezone.now() - timedelta(days=1)
    )
    assert purge_expired_exports() == 1
    assert not default_storage.exists(name)


# --- Deletion -------------------------------------------------------------------------
def test_deletion_is_blocked_while_owning_shared_scopes(tree):
    owner = tree.owner  # owns W, where others have projects
    other = UserFactory(username="other")
    grant(other, tree["A1"], "viewer")
    assert services.deletion_blockers(owner) == ["l'espace « W »"]

    lone = UserFactory(username="lone")
    grant(lone, tree.other_workspace, "editor")
    root = (
        client_for(lone)
        .post("/api/projects/", {"workspace": tree.other_workspace.pk, "name": "Solo"})
        .data
    )
    assert services.deletion_blockers(lone) == []  # nobody else in W2
    grant(other, tree.other_workspace, "viewer")
    assert services.deletion_blockers(lone) == ["le projet « Solo »"]
    Membership.objects.filter(user=other, workspace=tree.other_workspace).delete()
    grant(other, tree["Z"], "viewer")  # someone else in W2, but not on Solo's tree
    assert services.deletion_blockers(lone) == []
    assert root["name"] == "Solo"


def test_anonymize_wipes_everything_personal(me, tree, fake_google):  # noqa: F811
    connect_google(me)
    task = Task.objects.create(project=tree["A"], title="Assignée", created_by=me)
    task.assignees.add(me)
    comment = TaskComment.objects.create(task=task, author=me, body="Reste")
    Notification.objects.create(recipient=me, kind="mention")
    alone = Workspace.objects.create(name="Perso", created_by=me)
    grant(me, alone, "owner")

    services.anonymize(me)
    me.refresh_from_db()
    assert me.username == f"deleted-{me.pk}" and me.email.startswith("deleted-")
    assert me.first_name == "" and me.display_name == "Utilisateur supprimé"
    assert me.is_active is False and me.anonymized_at is not None
    assert not me.has_usable_password()
    assert not Membership.objects.filter(user=me).exists()
    assert not OAuthAccount.objects.filter(user=me).exists()
    assert any(url == REVOKE_URL for _, url, _ in fake_google.calls)
    assert not Notification.objects.filter(recipient=me).exists()
    assert not Workspace.objects.filter(pk=alone.pk).exists()
    assert list(task.assignees.all()) == []
    comment.refresh_from_db()
    assert comment.author == me  # the content stays, signed anonymously
    assert Task.objects.get(pk=task.pk).created_by == me


def test_delete_endpoint_needs_the_password_and_signs_out(api, me, tree):
    assert api.post("/api/me/delete/", {"password": "wrong"}).status_code == 400
    response = api.post("/api/me/delete/", {"password": DEFAULT_PASSWORD})
    assert response.status_code == 204
    assert api.get("/api/me/").status_code == 401
    me.refresh_from_db()
    assert me.anonymized_at is not None
    # Blocked case (someone else still in the workspace): the error names
    # what to transfer first.
    grant(UserFactory(username="other"), tree["B"], "viewer")
    owner_api = client_for(tree.owner)
    response = owner_api.post("/api/me/delete/", {"password": DEFAULT_PASSWORD})
    assert response.status_code == 400 and "« W »" in str(response.data["detail"])
