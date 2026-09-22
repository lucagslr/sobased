"""Anchored comments, threads, resolution; status changes with history;
followers; the dashboard "À valider" widget."""

import pytest

from apps.files.models import AssetComment, Kind
from apps.files.services import change_status

from .conftest import make_asset, pdf_upload, wav_upload

pytestmark = pytest.mark.django_db


def _post_comment(api, version, **payload):
    return api.post(
        f"/api/asset-versions/{version.pk}/comments/", payload, format="json"
    )


# --- Anchors ---------------------------------------------------------------------
def test_image_rectangle_in_percent(commenter_api, asset):
    version = asset.latest_version
    response = _post_comment(
        commenter_api,
        version,
        body="Le logo est trop bas",
        rect_x="10.5",
        rect_y="20",
        rect_w="30",
        rect_h="15.25",
        timestamp_ms=4000,  # ignored: not an audio
        page=2,  # ignored: not a document
    )
    assert response.status_code == 201, response.data
    data = response.data
    assert data["rect_x"] == "10.500" and data["rect_h"] == "15.250"
    assert data["timestamp_ms"] is None and data["page"] is None
    assert data["is_mine"] is True and data["is_resolved"] is False
    assert data["author"]["username"] == "commenter"


@pytest.mark.parametrize(
    "rect",
    [
        {"rect_x": "10", "rect_y": "10"},  # incomplete
        {"rect_x": "-1", "rect_y": "10", "rect_w": "10", "rect_h": "10"},
        {"rect_x": "95", "rect_y": "10", "rect_w": "10", "rect_h": "10"},  # x+w>100
        {"rect_x": "10", "rect_y": "10", "rect_w": "0", "rect_h": "10"},
    ],
)
def test_rectangle_outside_the_image_is_rejected(commenter_api, asset, rect):
    response = _post_comment(commenter_api, asset.latest_version, body="?", **rect)
    assert response.status_code == 400


def test_audio_timestamp_within_duration(commenter_api, tree, editor):
    asset = make_asset(tree["A"], editor, upload=wav_upload())
    version = asset.latest_version
    version.duration_ms = 30_000
    version.save(update_fields=["duration_ms"])
    ok = _post_comment(
        commenter_api, version, body="Basse trop forte", timestamp_ms=12_500
    )
    assert ok.status_code == 201 and ok.data["timestamp_ms"] == 12_500
    assert ok.data["rect_x"] is None
    late = _post_comment(commenter_api, version, body="?", timestamp_ms=31_000)
    assert late.status_code == 400 and "timestamp_ms" in late.data
    general = _post_comment(commenter_api, version, body="Globalement bien")
    assert general.status_code == 201 and general.data["timestamp_ms"] is None


def test_pdf_page_must_exist(commenter_api, tree, editor):
    asset = make_asset(tree["A"], editor, upload=pdf_upload(pages=3))
    version = asset.latest_version
    version.page_count = 3
    version.save(update_fields=["page_count"])
    ok = _post_comment(commenter_api, version, body="Faute page 2", page=2)
    assert ok.status_code == 201 and ok.data["page"] == 2
    missing = _post_comment(commenter_api, version, body="?", page=4)
    assert missing.status_code == 400 and "page" in missing.data


def test_empty_body_is_rejected(commenter_api, asset):
    assert (
        _post_comment(commenter_api, asset.latest_version, body="   ").status_code
        == 400
    )


# --- Threads ---------------------------------------------------------------------
def test_reply_joins_the_thread_without_anchor(commenter_api, editor_api, asset):
    version = asset.latest_version
    root = _post_comment(
        commenter_api,
        version,
        body="Trop sombre",
        rect_x="0",
        rect_y="0",
        rect_w="50",
        rect_h="50",
    ).data
    reply = _post_comment(
        editor_api, version, body="Je corrige", parent=root["id"], rect_x="1"
    )
    assert reply.status_code == 201, reply.data
    assert reply.data["parent"] == root["id"] and reply.data["rect_x"] is None
    # A reply to a reply stays in the same (one-level) thread.
    nested = _post_comment(
        commenter_api, version, body="Merci", parent=reply.data["id"]
    )
    assert nested.data["parent"] == root["id"]
    listing = commenter_api.get(f"/api/asset-versions/{version.pk}/comments/").data
    assert [c["body"] for c in listing] == ["Trop sombre", "Je corrige", "Merci"]
    detail = commenter_api.get(f"/api/asset-versions/{version.pk}/").data
    assert detail["comments_count"] == 3 and detail["open_threads"] == 1


def test_reply_to_a_comment_of_another_version_is_rejected(commenter_api, editor, tree):
    first = make_asset(tree["A"], editor)
    second = make_asset(tree["A"], editor, name="Autre")
    root = _post_comment(commenter_api, first.latest_version, body="ok").data
    bad = _post_comment(
        commenter_api, second.latest_version, body="?", parent=root["id"]
    )
    assert bad.status_code == 400 and "parent" in bad.data


def test_resolve_and_reopen_rights(commenter_api, editor_api, viewer_api, asset, tree):
    version = asset.latest_version
    root = _post_comment(commenter_api, version, body="À revoir").data
    reply = _post_comment(editor_api, version, body="Fait", parent=root["id"]).data

    # A viewer sees the thread but may not resolve it.
    assert (
        viewer_api.post(f"/api/asset-comments/{root['id']}/resolve/").status_code == 403
    )
    # Resolving through the reply resolves the root.
    done = editor_api.post(f"/api/asset-comments/{reply['id']}/resolve/")
    assert done.status_code == 200 and done.data["id"] == root["id"]
    assert done.data["is_resolved"] is True
    assert done.data["resolved_by"]["username"] == "editor"
    detail = commenter_api.get(f"/api/asset-versions/{version.pk}/").data
    assert detail["open_threads"] == 0
    # The thread's author may reopen it.
    back = commenter_api.post(f"/api/asset-comments/{root['id']}/reopen/")
    assert back.status_code == 200 and back.data["is_resolved"] is False

    # Another commenter is neither the author nor an editor.
    from apps.accounts.tests.factories import UserFactory
    from apps.projects.tests.factories import grant
    from apps.tasks.tests.conftest import client_for

    other = UserFactory(username="other")
    grant(other, tree["R"], "commenter")
    denied = client_for(other).post(f"/api/asset-comments/{root['id']}/resolve/")
    assert denied.status_code == 403


def test_edit_and_delete_rights(commenter_api, editor_api, viewer_api, asset, tree):
    version = asset.latest_version
    mine = _post_comment(
        commenter_api,
        version,
        body="v1",
        rect_x="0",
        rect_y="0",
        rect_w="10",
        rect_h="10",
    ).data
    # Only the body moves, the anchor stays.
    edited = commenter_api.patch(
        f"/api/asset-comments/{mine['id']}/",
        {"body": "v2", "rect_x": "50"},
        format="json",
    )
    assert edited.status_code == 200
    assert edited.data["body"] == "v2" and edited.data["rect_x"] == "0.000"
    assert edited.data["edited_at"] is not None
    # An editor is not the author: no edit, no delete (not admin).
    assert (
        editor_api.patch(
            f"/api/asset-comments/{mine['id']}/", {"body": "x"}, format="json"
        )
    ).status_code == 403
    assert editor_api.delete(f"/api/asset-comments/{mine['id']}/").status_code == 403
    # The workspace owner is admin everywhere: may delete.
    from apps.tasks.tests.conftest import client_for

    owner_api = client_for(tree.owner)
    assert owner_api.delete(f"/api/asset-comments/{mine['id']}/").status_code == 204
    assert not AssetComment.objects.filter(pk=mine["id"]).exists()
    # Viewers cannot comment at all.
    assert _post_comment(viewer_api, version, body="?").status_code == 403


def test_commenting_makes_a_follower(commenter_api, commenter, asset):
    assert commenter not in asset.followers.all()
    _post_comment(commenter_api, asset.latest_version, body="Bien")
    assert commenter in asset.followers.all()


def test_comments_are_invisible_with_the_asset(stranger_api, commenter_api, asset):
    version = asset.latest_version
    root = _post_comment(commenter_api, version, body="secret").data
    assert (
        stranger_api.get(f"/api/asset-versions/{version.pk}/comments/").status_code
        == 404
    )
    assert (
        stranger_api.patch(
            f"/api/asset-comments/{root['id']}/", {"body": "x"}, format="json"
        )
    ).status_code == 404


# --- Statuses --------------------------------------------------------------------
def test_status_change_with_history(editor_api, viewer_api, asset, editor):
    response = editor_api.post(
        f"/api/assets/{asset.pk}/status/",
        {"status": "to_validate", "note": "Prêt pour relecture"},
        format="json",
    )
    assert response.status_code == 200 and response.data["status"] == "to_validate"
    editor_api.post(
        f"/api/assets/{asset.pk}/status/", {"status": "approved"}, format="json"
    )
    history = viewer_api.get(f"/api/assets/{asset.pk}/status-history/").data
    assert [(h["from_status"], h["to_status"]) for h in history] == [
        ("to_validate", "approved"),
        ("draft", "to_validate"),
    ]
    assert history[1]["note"] == "Prêt pour relecture"
    assert history[1]["changed_by"]["username"] == "editor"


def test_status_reserved_to_editors(viewer_api, commenter_api, asset):
    for api in (viewer_api, commenter_api):
        response = api.post(
            f"/api/assets/{asset.pk}/status/", {"status": "approved"}, format="json"
        )
        assert response.status_code == 403
    asset.refresh_from_db()
    assert asset.status == "draft"


def test_unknown_status_is_rejected(editor_api, asset):
    response = editor_api.post(
        f"/api/assets/{asset.pk}/status/", {"status": "published"}, format="json"
    )
    assert response.status_code == 400
    with pytest.raises(ValueError):
        change_status(asset, "published", None)


def test_follow_and_unfollow(viewer_api, viewer, asset):
    followed = viewer_api.post(f"/api/assets/{asset.pk}/follow/")
    assert followed.status_code == 200 and followed.data["is_following"] is True
    assert viewer in asset.followers.all()
    left = viewer_api.delete(f"/api/assets/{asset.pk}/follow/")
    assert left.status_code == 200 and left.data["is_following"] is False


# --- Dashboard -------------------------------------------------------------------
def test_to_validate_widget_lists_assets(editor_api, viewer_api, tree, editor):
    waiting = make_asset(tree["A"], editor, name="Cover à valider")
    change_status(waiting, "to_validate", editor)
    make_asset(tree["A"], editor, name="Brouillon")
    response = editor_api.get("/api/dashboard/summary/")
    assert response.status_code == 200, response.data
    items = response.data["widgets"]["to_validate"]["items"]
    assets = [i for i in items if i["kind"] == "asset"]
    assert [a["title"] for a in assets] == ["Cover à valider"]
    assert assets[0]["id"] == waiting.pk and assets[0]["project"] == tree["A"].pk


def test_asset_kind_label(asset):
    assert Kind(asset.kind).label == "Image"
