"""Assets and versions through the API: rights, uploads, numbering, serving."""

import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.files import sniff
from apps.files.models import Asset, AssetVersion
from apps.workspaces.models import Tag

from .conftest import (
    client_for,
    make_asset,
    pdf_upload,
    png_upload,
    text_upload,
    wav_upload,
)

pytestmark = pytest.mark.django_db


# --- Sniffing ------------------------------------------------------------------
@pytest.mark.parametrize(
    "upload, kind, mime",
    [
        (png_upload(), "image", "image/png"),
        (pdf_upload(), "document", "application/pdf"),
        (wav_upload(), "audio", "audio/wav"),
        (text_upload(), "other", "application/octet-stream"),
        (
            SimpleUploadedFile("a.mp3", b"ID3\x04\x00" + b"\x00" * 20),
            "audio",
            "audio/mpeg",
        ),
        (
            SimpleUploadedFile("a.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8),
            "video",
            "video/mp4",
        ),
        (
            SimpleUploadedFile("a.m4a", b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 8),
            "audio",
            "audio/mp4",
        ),
    ],
)
def test_sniff_by_content(upload, kind, mime):
    assert sniff.sniff(upload) == sniff.Sniffed(kind, mime)


def test_sniff_never_raises_on_a_corrupt_image():
    """Pillow raises SyntaxError (not OSError) on a PNG with a bad chunk."""
    good = png_upload().read()
    corrupt = good[:40] + b"garbage" + good[47:]
    upload = SimpleUploadedFile("broken.png", corrupt, content_type="image/png")
    assert sniff.sniff(upload).kind == "other"


def test_sniff_ignores_the_extension():
    """A script renamed .png is not an image."""
    fake = SimpleUploadedFile(
        "x.png", b"#!/bin/sh\nrm -rf /\n", content_type="image/png"
    )
    assert sniff.sniff(fake).kind == "other"


# --- Creation and versions -----------------------------------------------------
def test_create_asset_uploads_v1(editor_api, editor, tree):
    response = editor_api.post(
        "/api/assets/",
        {
            "project": tree["A"].pk,
            "name": "Cover finale",
            "file": png_upload("Cover FINALE (1).png"),
            "label": "cover finale",
        },
        format="multipart",
    )
    assert response.status_code == 201, response.data
    data = response.data
    assert data["kind"] == "image"  # sniffed, not declared
    assert data["status"] == "draft"
    assert data["versions_count"] == 1 and data["is_following"] is True
    version = data["latest_version"]
    assert version["number"] == 1 and version["label"] == "cover finale"
    assert version["mime_type"] == "image/png"
    assert version["original_filename"] == "Cover FINALE (1).png"
    assert version["file_url"] == f"/api/asset-versions/{version['id']}/file/"
    assert version["derivatives"]["pending"] is True  # Celery has not run
    assert version["author"]["username"] == "editor"
    stored = AssetVersion.objects.get(pk=version["id"])
    # Random name under the project, nothing of the original filename.
    assert stored.file.name.startswith(f"assets/{tree['A'].pk}/")
    assert "Cover" not in stored.file.name and stored.file.name.endswith(".png")
    assert stored.size_bytes == stored.file.size > 0


def test_create_without_file_is_rejected(editor_api, tree):
    response = editor_api.post(
        "/api/assets/", {"project": tree["A"].pk, "name": "Vide"}, format="multipart"
    )
    assert response.status_code == 400
    assert "file" in response.data


def test_upload_size_limit(editor_api, tree, settings):
    settings.MAX_UPLOAD_MB = 1
    big = SimpleUploadedFile("big.bin", os.urandom(1024 * 1024 + 1))
    response = editor_api.post(
        "/api/assets/",
        {"project": tree["A"].pk, "name": "Trop lourd", "file": big},
        format="multipart",
    )
    assert response.status_code == 400
    assert "trop lourd" in response.data["file"][0].lower()
    assert not Asset.objects.exists()


def test_next_version_is_numbered_and_listed(editor_api, asset):
    response = editor_api.post(
        f"/api/assets/{asset.pk}/versions/",
        {"file": png_upload("v2.png"), "label": "retouches", "note": "logo déplacé"},
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert response.data["number"] == 2 and response.data["note"] == "logo déplacé"

    listing = editor_api.get(f"/api/assets/{asset.pk}/versions/")
    assert [v["number"] for v in listing.data] == [2, 1]  # newest first
    detail = editor_api.get(f"/api/assets/{asset.pk}/")
    assert detail.data["versions_count"] == 2
    assert detail.data["latest_version"]["number"] == 2


def test_kind_follows_the_first_file_only(editor_api, tree, editor):
    asset = make_asset(tree["A"], editor, upload=text_upload())
    assert asset.kind == "other"
    editor_api.post(
        f"/api/assets/{asset.pk}/versions/",
        {"file": png_upload()},
        format="multipart",
    )
    asset.refresh_from_db()
    assert asset.kind == "other"  # v2 does not silently change the kind
    editor_api.patch(f"/api/assets/{asset.pk}/", {"kind": "image"}, format="json")
    asset.refresh_from_db()
    assert asset.kind == "image"


def test_version_label_and_note_editable_file_not(editor_api, asset):
    version = asset.latest_version
    response = editor_api.patch(
        f"/api/asset-versions/{version.pk}/",
        {"label": "master", "number": 9, "mime_type": "text/html"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["label"] == "master"
    assert response.data["number"] == 1 and response.data["mime_type"] == "image/png"


def test_last_version_cannot_be_deleted(editor_api, asset):
    v1 = asset.latest_version
    assert editor_api.delete(f"/api/asset-versions/{v1.pk}/").status_code == 400
    editor_api.post(
        f"/api/assets/{asset.pk}/versions/", {"file": png_upload()}, format="multipart"
    )
    v2 = asset.versions.get(number=2)
    path = v2.file.path
    assert os.path.exists(path)
    assert editor_api.delete(f"/api/asset-versions/{v2.pk}/").status_code == 204
    assert not os.path.exists(path)  # the file left with the row
    assert asset.versions.count() == 1


def test_deleting_the_asset_removes_its_files(editor_api, asset):
    path = asset.latest_version.file.path
    assert editor_api.delete(f"/api/assets/{asset.pk}/").status_code == 204
    assert not os.path.exists(path)


def test_asset_never_changes_project(editor_api, asset, tree):
    response = editor_api.patch(
        f"/api/assets/{asset.pk}/", {"project": tree["B"].pk}, format="json"
    )
    assert response.status_code == 200
    asset.refresh_from_db()
    assert asset.project == tree["A"]


def test_tags_must_belong_to_the_workspace(editor_api, asset, tree):
    foreign = Tag.objects.create(workspace=tree.other_workspace, name="ailleurs")
    mine = Tag.objects.create(workspace=tree.workspace, name="visuel")
    bad = editor_api.patch(
        f"/api/assets/{asset.pk}/", {"tags": [foreign.pk]}, format="json"
    )
    assert bad.status_code == 400
    good = editor_api.patch(
        f"/api/assets/{asset.pk}/", {"tags": [mine.pk]}, format="json"
    )
    assert good.status_code == 200 and good.data["tags"] == [mine.pk]


# --- Listing and filters -------------------------------------------------------
def test_list_filters(editor_api, tree, editor):
    make_asset(tree["A"], editor, name="Cover", upload=png_upload())
    make_asset(tree["A1"], editor, name="Mix 1", upload=wav_upload())
    make_asset(tree["B"], editor, name="Dossier", upload=pdf_upload())

    only_a = editor_api.get("/api/assets/", {"project": tree["A"].pk}).data["results"]
    assert [a["name"] for a in only_a] == ["Cover"]
    branch = editor_api.get(
        "/api/assets/", {"project": tree["A"].pk, "include_descendants": "true"}
    ).data["results"]
    assert sorted(a["name"] for a in branch) == ["Cover", "Mix 1"]
    audio = editor_api.get("/api/assets/", {"kind": "audio"}).data["results"]
    assert [a["name"] for a in audio] == ["Mix 1"]
    found = editor_api.get("/api/assets/", {"search": "doss"}).data["results"]
    assert [a["name"] for a in found] == ["Dossier"]


# --- Rights --------------------------------------------------------------------
def test_viewer_reads_but_cannot_write(viewer_api, asset, tree):
    assert viewer_api.get(f"/api/assets/{asset.pk}/").status_code == 200
    assert viewer_api.get(f"/api/assets/{asset.pk}/versions/").status_code == 200
    denied = viewer_api.post(
        f"/api/assets/{asset.pk}/versions/", {"file": png_upload()}, format="multipart"
    )
    assert denied.status_code == 403
    assert (
        viewer_api.patch(f"/api/assets/{asset.pk}/", {"name": "x"}, format="json")
    ).status_code == 403
    create = viewer_api.post(
        "/api/assets/",
        {"project": tree["A"].pk, "name": "Nope", "file": png_upload()},
        format="multipart",
    )
    assert create.status_code == 403
    assert viewer_api.delete(f"/api/assets/{asset.pk}/").status_code == 403


def test_invisible_asset_is_404(stranger_api, asset, tree):
    assert stranger_api.get(f"/api/assets/{asset.pk}/").status_code == 404
    assert stranger_api.get("/api/assets/").data["results"] == []
    version = asset.latest_version
    assert stranger_api.get(f"/api/asset-versions/{version.pk}/").status_code == 404
    assert (
        stranger_api.get(f"/api/asset-versions/{version.pk}/file/").status_code == 404
    )
    create = stranger_api.post(
        "/api/assets/",
        {"project": tree["A"].pk, "name": "Nope", "file": png_upload()},
        format="multipart",
    )
    assert create.status_code == 404


def test_guest_of_a_subproject_sees_only_its_assets(tree, editor):
    from apps.accounts.tests.factories import UserFactory
    from apps.projects.tests.factories import grant

    make_asset(tree["A"], editor, name="Cover")
    inside = make_asset(tree["A1"], editor, name="Mix A1")
    guest = UserFactory(username="guest")
    grant(guest, tree["A1"], "viewer")
    api = client_for(guest)
    listing = api.get("/api/assets/").data["results"]
    assert [a["id"] for a in listing] == [inside.pk]


# --- Serving -------------------------------------------------------------------
def test_file_endpoint_streams_with_nosniff(viewer_api, asset):
    version = asset.latest_version
    response = viewer_api.get(f"/api/asset-versions/{version.pk}/file/")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Cache-Control"] == "private, no-store"
    assert response["Content-Disposition"].startswith("inline; filename*=UTF-8''")
    body = b"".join(response.streaming_content)
    assert body[:8] == b"\x89PNG\r\n\x1a\n"

    download = viewer_api.get(f"/api/asset-versions/{version.pk}/file/?download=1")
    assert download["Content-Disposition"].startswith("attachment;")


def test_file_endpoint_behind_caddy_uses_accel_redirect(viewer_api, asset, settings):
    settings.PROTECTED_MEDIA_ACCEL = True
    version = asset.latest_version
    response = viewer_api.get(f"/api/asset-versions/{version.pk}/file/")
    assert response.status_code == 200
    assert response["X-Accel-Redirect"] == "/" + version.file.name
    assert response.content == b""


def test_derivatives_are_404_until_ready(viewer_api, asset):
    version = asset.latest_version
    for action in ("thumbnail", "stream", "peaks"):
        response = viewer_api.get(f"/api/asset-versions/{version.pk}/{action}/")
        assert response.status_code == 404, action


def test_no_public_media_url(client, asset):
    """The stored path is not reachable without going through the API."""
    version = asset.latest_version
    response = client.get("/media/" + version.file.name)
    assert response.status_code in (404, 302)
    assert b"PNG" not in getattr(response, "content", b"")


def test_upload_keeps_the_real_size(editor, tree):
    """Regression guard: `size_bytes` is the real size, not 0."""
    content = png_upload().read()
    upload = SimpleUploadedFile("c.png", content)
    asset = make_asset(tree["A"], editor, upload=upload)
    assert asset.latest_version.size_bytes == len(content) > 0
