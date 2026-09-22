"""Editors' API: creation per target, rights, state, revocation, journal."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core import crypto
from apps.sharing import services
from apps.sharing.models import ShareLink

from .conftest import create_link, link_of, make_asset, token_of

pytestmark = pytest.mark.django_db


def test_create_for_an_asset(editor_api, cover, tree):
    data = create_link(
        editor_api, target_type="asset", asset=cover.pk, recipient_label="Radio X"
    )
    assert data["project"] == tree["A"].pk
    assert (
        data["title"] == "Cover" and data["target_label"] == "Cover (dernière version)"
    )
    assert data["state"] == "active" and data["has_password"] is False
    assert data["watermark"] is True and data["allow_download"] is False
    assert data["url"].startswith("http://localhost:8080/s/")
    token = token_of(data)
    assert len(token) >= 43
    link = link_of(data)
    # The token is never stored in clear: a hash for lookups, a copy that
    # only the Fernet key can read.
    assert token not in link.token_hash and token not in link.token_encrypted
    assert link.token_hash == services.token_hash(token)
    assert crypto.decrypt(link.token_encrypted) == token
    assert services.find_by_token(token) == link


def test_create_for_a_version_and_a_playlist(editor_api, cover, mix, tree):
    version = cover.latest_version
    data = create_link(editor_api, target_type="version", version=version.pk)
    assert data["version"] == version.pk and data["asset"] is None
    assert data["target_label"] == "Cover (v1)"

    inside = make_asset(tree["A1"], cover.created_by, name="Bonus")
    playlist = create_link(
        editor_api,
        target_type="playlist",
        project=tree["A"].pk,
        assets=[mix.pk, cover.pk, inside.pk],
        title="Écoute privée",
    )
    assert [item["asset"] for item in playlist["items"]] == [
        mix.pk,
        cover.pk,
        inside.pk,
    ]
    assert playlist["target_label"] == "Sélection de 3 fichiers"


def test_playlist_assets_must_belong_to_the_branch(editor_api, cover, tree, editor):
    elsewhere = make_asset(tree["B"], editor, name="Ailleurs")
    response = editor_api.post(
        "/api/share-links/",
        {"target_type": "playlist", "project": tree["A"].pk, "assets": [elsewhere.pk]},
        format="json",
    )
    assert response.status_code == 400 and "assets" in response.data
    empty = editor_api.post(
        "/api/share-links/",
        {"target_type": "playlist", "project": tree["A"].pk, "assets": []},
        format="json",
    )
    assert empty.status_code == 400


def test_password_expiry_and_quotas(editor_api, cover):
    later = (timezone.now() + timedelta(days=7)).isoformat()
    data = create_link(
        editor_api,
        target_type="asset",
        asset=cover.pk,
        password="secret",
        expires_at=later,
        max_views=10,
        max_plays=3,
        allow_download=True,
        watermark=False,
    )
    assert data["has_password"] is True and "password" not in data
    link = link_of(data)
    # Hashed like a user password (Argon2 in production; the test settings
    # swap in MD5 for speed, so the check is on the configured hasher).
    from django.contrib.auth.hashers import identify_hasher

    assert (
        identify_hasher(link.password_hash).algorithm
        == identify_hasher(link.created_by.password).algorithm
    )
    assert "secret" not in link.password_hash
    assert services.check_link_password(link, "secret")
    assert not services.check_link_password(link, "wrong")
    # Removing the password.
    cleared = editor_api.patch(
        f"/api/share-links/{link.pk}/", {"password": ""}, format="json"
    )
    assert cleared.status_code == 200 and cleared.data["has_password"] is False
    past = editor_api.patch(
        f"/api/share-links/{link.pk}/",
        {"expires_at": (timezone.now() - timedelta(minutes=1)).isoformat()},
        format="json",
    )
    assert past.status_code == 400
    short = editor_api.post(
        "/api/share-links/",
        {"target_type": "asset", "asset": cover.pk, "password": "abc"},
        format="json",
    )
    assert short.status_code == 400 and "password" in short.data


def test_target_never_changes(editor_api, cover, mix):
    data = create_link(editor_api, target_type="asset", asset=cover.pk)
    response = editor_api.patch(
        f"/api/share-links/{data['id']}/",
        {"asset": mix.pk, "target_type": "version", "title": "Renommé"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["asset"] == cover.pk and response.data["title"] == "Renommé"


def test_states_and_filter(editor_api, cover):
    active = link_of(create_link(editor_api, target_type="asset", asset=cover.pk))
    expired = link_of(create_link(editor_api, target_type="asset", asset=cover.pk))
    ShareLink.objects.filter(pk=expired.pk).update(
        expires_at=timezone.now() - timedelta(hours=1)
    )
    exhausted = link_of(
        create_link(editor_api, target_type="asset", asset=cover.pk, max_views=2)
    )
    ShareLink.objects.filter(pk=exhausted.pk).update(view_count=2)
    revoked = link_of(create_link(editor_api, target_type="asset", asset=cover.pk))
    assert editor_api.post(f"/api/share-links/{revoked.pk}/revoke/").status_code == 200

    for state, expected in (
        ("active", active),
        ("expired", expired),
        ("exhausted", exhausted),
        ("revoked", revoked),
    ):
        listing = editor_api.get("/api/share-links/", {"state": state}).data["results"]
        assert [row["id"] for row in listing] == [expected.pk], state
        assert listing[0]["state"] == state
    everything = editor_api.get("/api/share-links/", {"project": cover.project_id})
    assert everything.data["count"] == 4


def test_rights(viewer_api, stranger_api, editor_api, cover, tree):
    data = create_link(editor_api, target_type="asset", asset=cover.pk)
    # A viewer of the project sees no link at all: they are editors' business.
    assert viewer_api.get("/api/share-links/").data["results"] == []
    assert viewer_api.get(f"/api/share-links/{data['id']}/").status_code == 404
    denied = viewer_api.post(
        "/api/share-links/", {"target_type": "asset", "asset": cover.pk}, format="json"
    )
    assert denied.status_code == 400  # the asset is not one they may share
    assert stranger_api.get(f"/api/share-links/{data['id']}/").status_code == 404
    assert (
        stranger_api.post(f"/api/share-links/{data['id']}/revoke/").status_code == 404
    )


def test_delete_takes_the_journal(editor_api, cover, visitor):
    data = create_link(editor_api, target_type="asset", asset=cover.pk)
    assert visitor.get(f"/api/public/share/{token_of(data)}/").status_code == 200
    log = editor_api.get(f"/api/share-links/{data['id']}/access-log/").data
    assert [entry["event"] for entry in log] == ["view"]
    assert editor_api.delete(f"/api/share-links/{data['id']}/").status_code == 204
    assert not ShareLink.objects.filter(pk=data["id"]).exists()


def test_deleting_the_asset_deletes_its_links(editor_api, cover):
    data = create_link(editor_api, target_type="asset", asset=cover.pk)
    assert editor_api.delete(f"/api/assets/{cover.pk}/").status_code == 204
    assert not ShareLink.objects.filter(pk=data["id"]).exists()


def test_truncated_ips():
    assert services.truncate_ip("192.168.34.217") == "192.168.34.0"
    assert services.truncate_ip("2a02:1210:abcd:ef01:1:2:3:4") == "2a02:1210:abcd::"
    assert services.truncate_ip("not-an-ip") == ""
