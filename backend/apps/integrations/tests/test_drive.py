"""Project folders (D8), sharing with members, uploads, picked files, Drive
versions of assets and their import."""

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.files.models import Asset, AssetVersion
from apps.files.tests.conftest import make_asset, png_upload
from apps.integrations import drive
from apps.integrations.models import DriveLink
from apps.projects.models import Project
from apps.projects.tests.factories import grant
from apps.tasks.tests.conftest import TaskFactory

from .conftest import client_for, connect_google

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_project(django_capture_on_commit_callbacks):
    """POST a project and run what waits for the commit (the Drive task):
    inside the test transaction, on_commit callbacks never fire by themselves."""

    def _create(api, **fields):
        with django_capture_on_commit_callbacks(execute=True):
            response = api.post("/api/projects/", fields, format="json")
        assert response.status_code == 201, response.data
        return response.data

    return _create


@pytest.fixture
def patch_project(django_capture_on_commit_callbacks):
    def _patch(api, project_id, **fields):
        with django_capture_on_commit_callbacks(execute=True):
            response = api.patch(f"/api/projects/{project_id}/", fields, format="json")
        assert response.status_code == 200, response.data
        return response.data

    return _patch


# --- Folders -------------------------------------------------------------------
def test_root_project_gets_a_folder_with_subfolders(
    editor_api, connected_editor, tree, fake_google, create_project
):
    data = create_project(editor_api, workspace=tree.workspace.pk, name="Album X")
    # Celery is eager but on_commit callbacks wait for the transaction: the
    # test client wraps nothing, so the task ran at once.
    project = Project.objects.get(pk=data["id"])
    assert project.drive_folder_id == "f1"
    assert project.drive_account.user == connected_editor
    assert project.drive_folder_url.endswith("/f1/view")
    names = sorted(f["name"] for f in fake_google.folders())
    assert names == sorted(["Album X", *drive.SUBFOLDERS])
    subfolder_parents = {f["parents"][0] for f in fake_google.folders() if f["parents"]}
    assert subfolder_parents == {"f1"}
    detail = editor_api.get(f"/api/projects/{project.pk}/").data
    assert detail["drive_status"] == "ok" and detail["drive_folder_url"]


def test_option_unchecked_or_no_account_means_no_folder(
    editor_api, editor, tree, fake_google, create_project
):
    connect_google(editor)
    data = create_project(
        editor_api,
        workspace=tree.workspace.pk,
        name="Sans dossier",
        create_drive_folder=False,
    )
    assert Project.objects.get(pk=data["id"]).drive_folder_id == ""
    # No Google account at all: nothing is attempted, the project still exists.
    other = UserFactory(username="nodrive")
    grant(other, tree.workspace, "admin")
    api = client_for(other)
    data = create_project(api, workspace=tree.workspace.pk, name="Sans Google")
    assert Project.objects.get(pk=data["id"]).drive_folder_id == ""
    assert api.get(f"/api/projects/{data['id']}/").data["drive_status"] == "none"


def test_subproject_folder_under_the_parent_with_the_owner_account(
    editor_api, connected_editor, tree, fake_google, create_project
):
    root = create_project(editor_api, workspace=tree.workspace.pk, name="Racine")
    # Another editor, WITHOUT Google, adds a sub-project: the folder is still
    # created, with the root owner's account (rule D8).
    other = UserFactory(username="other")
    grant(other, tree.workspace, "editor")
    child = create_project(client_for(other), parent=root["id"], name="Clip")
    project = Project.objects.get(pk=child["id"])
    assert project.drive_folder_id and project.drive_account_id is None
    folder = fake_google.files[project.drive_folder_id]
    assert folder["parents"] == ["f1"] and folder["name"] == "Clip"
    assert drive.folder_owner(project).user == connected_editor


def test_create_folder_afterwards_and_parent_missing(
    editor_api, editor, tree, fake_google, create_project
):
    root = create_project(editor_api, workspace=tree.workspace.pk, name="Tard")
    child = create_project(editor_api, parent=root["id"], name="Enfant")
    assert Project.objects.get(pk=root["id"]).drive_folder_id == ""  # no account yet
    assert (
        editor_api.get(f"/api/projects/{child['id']}/").data["drive_status"]
        == "parent_missing"
    )
    denied = editor_api.post(f"/api/projects/{child['id']}/drive/create-folder/")
    assert denied.status_code == 400 and "parent" in denied.data["detail"]

    connect_google(editor)
    created = editor_api.post(f"/api/projects/{root['id']}/drive/create-folder/")
    assert created.status_code == 200, created.data
    assert created.data["drive_status"] == "ok" and created.data["drive_folder_id"]
    again = editor_api.post(f"/api/projects/{root['id']}/drive/create-folder/")
    assert again.status_code == 400
    child_created = editor_api.post(f"/api/projects/{child['id']}/drive/create-folder/")
    assert (
        child_created.status_code == 200 and child_created.data["drive_status"] == "ok"
    )


def test_owner_disconnected_disables_drive_actions(
    editor_api, connected_editor, tree, fake_google, create_project
):
    root = create_project(editor_api, workspace=tree.workspace.pk, name="Racine")
    assert editor_api.delete("/api/integrations/google/").status_code == 204
    detail = editor_api.get(f"/api/projects/{root['id']}/").data
    assert detail["drive_status"] == "owner_disconnected"
    assert detail["drive_folder_url"]  # the link stays
    child = create_project(editor_api, parent=root["id"], name="Enfant")
    assert Project.objects.get(pk=child["id"]).drive_folder_id == ""
    upload = editor_api.post(
        f"/api/projects/{root['id']}/drive/upload/",
        {"file": png_upload()},
        format="multipart",
    )
    assert upload.status_code == 400 and "déconnecté" in upload.data["detail"]


def test_folder_actions_need_an_editor(
    editor_api, connected_editor, tree, fake_google, create_project
):
    root = create_project(editor_api, workspace=tree.workspace.pk, name="Racine")
    viewer = UserFactory(username="viewer")
    grant(viewer, tree.workspace, "viewer")
    api = client_for(viewer)
    assert (
        api.post(f"/api/projects/{root['id']}/drive/create-folder/").status_code == 403
    )
    stranger = client_for(UserFactory(username="stranger"))
    assert (
        stranger.post(f"/api/projects/{root['id']}/drive/create-folder/").status_code
        == 404
    )


# --- Sharing with members ------------------------------------------------------
def test_share_with_members(
    editor_api, connected_editor, tree, fake_google, create_project, patch_project
):
    viewer = UserFactory(username="viewer")
    grant(viewer, tree.workspace, "viewer")
    connect_google(viewer, email="viewer@gmail.com")
    admin = UserFactory(username="admin")
    grant(admin, tree.workspace, "admin")
    connect_google(admin, email="admin@gmail.com")
    UserFactory(username="nogoogle")  # member without Google: skipped
    root = create_project(
        editor_api,
        workspace=tree.workspace.pk,
        name="Partagé",
        drive_share_with_members=True,
    )
    shared = {(email, role) for _, email, role in fake_google.permissions}
    assert shared == {("viewer@gmail.com", "reader"), ("admin@gmail.com", "writer")}
    # Switching the option on later shares too; re-applying is idempotent.
    later = create_project(editor_api, workspace=tree.workspace.pk, name="Plus tard")
    fake_google.permissions.clear()
    patch_project(editor_api, later["id"], drive_share_with_members=True)
    assert len(fake_google.permissions) == 2
    fake_google.permissions.clear()
    response = editor_api.post(f"/api/projects/{root['id']}/drive/share/")
    assert response.status_code == 200 and response.data["shared_with"] == 2


# --- Uploads and picked files -------------------------------------------------------
def test_upload_to_the_project_folder(
    editor_api, connected_editor, tree, fake_google, create_project
):
    root = create_project(editor_api, workspace=tree.workspace.pk, name="Racine")
    response = editor_api.post(
        f"/api/projects/{root['id']}/drive/upload/",
        {"file": png_upload("brief.png")},
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert (
        response.data["name"] == "brief.png"
        and response.data["mime_type"] == "image/png"
    )
    assert response.data["web_view_url"].startswith("https://drive.google.com/")
    uploaded = fake_google.files[response.data["drive_file_id"]]
    assert uploaded["parents"] == ["f1"]
    links = editor_api.get("/api/drive-links/", {"project": root["id"]}).data
    assert [link["id"] for link in links] == [response.data["id"]]


def test_attach_a_picked_file_to_a_task(
    editor_api, connected_editor, tree, fake_google, create_project
):
    fake_google.add_file("Contrat.pdf", "application/pdf", file_id="pick1")
    task = TaskFactory(project=tree["A"], title="Signer")
    response = editor_api.post(
        "/api/drive-links/",
        {"project": tree["A"].pk, "task": task.pk, "drive_file_id": "pick1"},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["name"] == "Contrat.pdf" and response.data["task"] == task.pk
    assert response.data["icon_url"].startswith(
        "https://drive-thirdparty.googleusercontent.com/"
    )
    # Same file attached twice to the same place: one link.
    again = editor_api.post(
        "/api/drive-links/",
        {"project": tree["A"].pk, "task": task.pk, "drive_file_id": "pick1"},
        format="json",
    )
    assert again.status_code == 201 and DriveLink.objects.count() == 1
    by_task = editor_api.get("/api/drive-links/", {"task": task.pk}).data
    assert len(by_task) == 1
    # A task of another project is refused; an unknown file is a clear 400.
    elsewhere = TaskFactory(project=tree["B"], title="Ailleurs")
    bad = editor_api.post(
        "/api/drive-links/",
        {"project": tree["A"].pk, "task": elsewhere.pk, "drive_file_id": "pick1"},
        format="json",
    )
    assert bad.status_code == 400 and "task" in bad.data
    missing = editor_api.post(
        "/api/drive-links/",
        {"project": tree["A"].pk, "drive_file_id": "nope"},
        format="json",
    )
    assert missing.status_code == 400 and "404" in missing.data["detail"]
    assert (
        editor_api.delete(f"/api/drive-links/{response.data['id']}/").status_code == 204
    )


def test_drive_links_follow_the_project_rights(
    editor_api, connected_editor, tree, fake_google, create_project
):
    fake_google.add_file("Doc", "application/pdf", file_id="pick1")
    editor_api.post(
        "/api/drive-links/",
        {"project": tree["A"].pk, "drive_file_id": "pick1"},
        format="json",
    )
    viewer = UserFactory(username="viewer")
    grant(viewer, tree["A"], "viewer")
    api = client_for(viewer)
    assert len(api.get("/api/drive-links/", {"project": tree["A"].pk}).data) == 1
    denied = api.post(
        "/api/drive-links/",
        {"project": tree["A"].pk, "drive_file_id": "pick1"},
        format="json",
    )
    assert denied.status_code == 403
    stranger = client_for(UserFactory(username="stranger"))
    assert stranger.get("/api/drive-links/", {"project": tree["A"].pk}).data == []


def test_attach_needs_google(editor_api, editor, tree, fake_google, create_project):
    response = editor_api.post(
        "/api/drive-links/",
        {"project": tree["A"].pk, "drive_file_id": "pick1"},
        format="json",
    )
    assert response.status_code == 400 and "Connecte Google" in response.data["detail"]


# --- Drive versions of assets ----------------------------------------------------
def test_drive_version_then_import(
    editor_api, connected_editor, tree, fake_google, create_project
):
    body = png_upload().read()
    fake_google.add_file("cover-v2.png", "image/png", body=body, file_id="pick1")
    asset = make_asset(tree["A"], connected_editor, name="Cover")
    response = editor_api.post(
        f"/api/assets/{asset.pk}/versions/",
        {"drive_file_id": "pick1", "label": "sur Drive"},
        format="json",
    )
    assert response.status_code == 201, response.data
    version = response.data
    assert version["number"] == 2 and version["is_drive"] is True
    assert version["file_url"] is None and version["mime_type"] == "image/png"
    assert version["drive_meta"]["web_view_url"].startswith("https://drive.google.com/")
    assert version["original_filename"] == "cover-v2.png"
    # Not streamable and not shareable as long as it lives on Drive only.
    assert (
        editor_api.get(f"/api/asset-versions/{version['id']}/file/").status_code == 404
    )

    imported = editor_api.post(
        f"/api/asset-versions/{version['id']}/import-from-drive/"
    )
    assert imported.status_code == 200, imported.data
    assert imported.data["is_drive"] is False and imported.data["file_url"]
    stored = AssetVersion.objects.get(pk=version["id"])
    assert stored.file and stored.drive_file_id == ""
    assert stored.drive_meta["drive_file_id"] == "pick1"  # kept for the record
    with stored.file.open("rb") as handle:
        assert handle.read() == body
    served = editor_api.get(f"/api/asset-versions/{version['id']}/file/")
    assert served.status_code == 200
    again = editor_api.post(f"/api/asset-versions/{version['id']}/import-from-drive/")
    assert again.status_code == 400


def test_drive_version_as_first_version_sets_the_kind(
    editor_api, connected_editor, tree, fake_google, create_project
):
    fake_google.add_file("mix.mp3", "audio/mpeg", file_id="pick1")
    asset = Asset.objects.create(
        project=tree["A"], name="Mix", created_by=connected_editor
    )
    response = editor_api.post(
        f"/api/assets/{asset.pk}/versions/", {"drive_file_id": "pick1"}, format="json"
    )
    assert response.status_code == 201, response.data
    asset.refresh_from_db()
    assert asset.kind == "audio" and response.data["kind"] == "audio"


def test_refused_refresh_marks_the_account_even_when_the_action_fails(
    editor_api, editor, tree, fake_google, create_project
):
    """Found in the browser: the needs_reauth mark was rolled back with the
    failed folder creation. The Google calls now happen outside the
    transaction, so the mark survives and the settings say "Reconnecter"."""
    from apps.integrations.models import OAuthAccount

    connect_google(editor)
    root = create_project(
        editor_api,
        workspace=tree.workspace.pk,
        name="Racine",
        create_drive_folder=False,
    )
    fake_google.unauthorized_once = True
    fake_google.fail_refresh = True
    response = editor_api.post(f"/api/projects/{root['id']}/drive/create-folder/")
    assert response.status_code == 400
    account = OAuthAccount.objects.get(user=editor)
    assert account.status == "needs_reauth"
    assert (
        editor_api.get("/api/integrations/").data["google"]["status"] == "needs_reauth"
    )
    assert editor_api.get(f"/api/projects/{root['id']}/").data["drive_status"] == "none"
