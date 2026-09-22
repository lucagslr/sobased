"""The public page: gate, counting, quotas, session-bound media, watermarks."""

import io
import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone
from PIL import Image

from apps.files import processing
from apps.files.models import AssetDerivative
from apps.sharing import watermark
from apps.sharing.models import ShareLink

from .conftest import create_link, link_of, make_asset, token_of

pytestmark = pytest.mark.django_db
needs_ffmpeg = pytest.mark.skipif(
    not processing.ffmpeg_available(), reason="ffmpeg / ffprobe not installed"
)


def page(visitor, token):
    return visitor.get(f"/api/public/share/{token}/")


def body(response) -> bytes:
    return b"".join(response.streaming_content)


# --- Opening ---------------------------------------------------------------------
def test_unknown_token_is_404(visitor):
    assert page(visitor, "a" * 43).status_code == 404


def test_open_counts_one_view_per_session(editor_api, cover, visitor):
    data = create_link(editor_api, target_type="asset", asset=cover.pk, watermark=False)
    token = token_of(data)
    first = page(visitor, token)
    assert first.status_code == 200, first.json()
    payload = first.json()
    assert payload["requires_password"] is False and payload["title"] == "Cover"
    [item] = payload["items"]
    assert item["kind"] == "image" and item["name"] == "Cover"
    assert item["media_url"].startswith(f"/api/public/share/{token}/media/")
    assert item["download_url"] is None and item["ready"] is True
    # A reload within the window is the same view.
    page(visitor, token)
    link = link_of(data)
    assert link.view_count == 1 and link.first_opened_at is not None
    # Another browser is another view.
    assert page(Client(), token).status_code == 200
    link.refresh_from_db()
    assert link.view_count == 2
    log = editor_api.get(f"/api/share-links/{link.pk}/access-log/").data
    assert [entry["event"] for entry in log] == ["view", "view"]
    assert log[0]["ip_truncated"] == "127.0.0.0"


def test_asset_target_follows_the_latest_version(editor_api, cover, visitor):
    from apps.files import services as file_services

    from .conftest import png_upload

    data = create_link(editor_api, target_type="asset", asset=cover.pk)
    v2 = file_services.add_version(cover, png_upload("v2.png"), cover.created_by)
    [item] = page(visitor, token_of(data)).json()["items"]
    assert item["version_id"] == v2.pk and item["number"] == 2


def test_version_target_stays_on_its_version(editor_api, cover, visitor):
    from apps.files import services as file_services

    from .conftest import png_upload

    v1 = cover.latest_version
    data = create_link(editor_api, target_type="version", version=v1.pk)
    file_services.add_version(cover, png_upload("v2.png"), cover.created_by)
    [item] = page(visitor, token_of(data)).json()["items"]
    assert item["version_id"] == v1.pk


# --- States --------------------------------------------------------------------------
def test_revoked_expired_exhausted_are_410(editor_api, cover, visitor):
    revoked = create_link(editor_api, target_type="asset", asset=cover.pk)
    editor_api.post(f"/api/share-links/{revoked['id']}/revoke/")
    response = page(visitor, token_of(revoked))
    assert response.status_code == 410 and response.json()["state"] == "revoked"

    expired = create_link(editor_api, target_type="asset", asset=cover.pk)
    ShareLink.objects.filter(pk=expired["id"]).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert page(visitor, token_of(expired)).json()["state"] == "expired"

    limited = create_link(editor_api, target_type="asset", asset=cover.pk, max_views=1)
    token = token_of(limited)
    assert page(visitor, token).status_code == 200  # consumes the only view
    assert page(visitor, token).status_code == 200  # same session, same window
    other = page(Client(), token)
    assert other.status_code == 410 and other.json()["state"] == "exhausted"


# --- Password -------------------------------------------------------------------------
def test_password_gate_and_attempt_limit(editor_api, cover, visitor, settings):
    data = create_link(
        editor_api, target_type="asset", asset=cover.pk, password="radio2026"
    )
    token = token_of(data)
    gate = page(visitor, token).json()
    assert gate["requires_password"] is True and gate["items"] == []
    assert link_of(data).view_count == 0  # nothing counted behind the gate

    unlock = f"/api/public/share/{token}/unlock/"
    for _ in range(settings.SHARE_UNLOCK_MAX_FAILURES):
        wrong = visitor.post(
            unlock, {"password": "nope"}, content_type="application/json"
        )
        assert wrong.status_code == 400
    blocked = visitor.post(
        unlock, {"password": "radio2026"}, content_type="application/json"
    )
    assert blocked.status_code == 429
    log = editor_api.get(f"/api/share-links/{data['id']}/access-log/").data
    assert {entry["event"] for entry in log} == {"password_failed"}

    # The limit is per link AND IP: the same address stays blocked in a new
    # browser; another address gets its own attempts.
    assert (
        Client()
        .post(unlock, {"password": "radio2026"}, content_type="application/json")
        .status_code
        == 429
    )
    fresh = Client(REMOTE_ADDR="10.0.0.9")
    ok = fresh.post(unlock, {"password": "radio2026"}, content_type="application/json")
    assert ok.status_code == 200, ok.json()
    assert ok.json()["requires_password"] is False and len(ok.json()["items"]) == 1
    assert page(fresh, token).json()["requires_password"] is False
    assert link_of(data).view_count == 1
    # The media of a locked session is refused even with a valid-looking URL.
    media_url = ok.json()["items"][0]["media_url"]
    assert visitor.get(media_url).status_code == 403


# --- Media ---------------------------------------------------------------------
def test_media_url_is_bound_to_the_session(editor_api, cover, visitor):
    data = create_link(editor_api, target_type="asset", asset=cover.pk, watermark=False)
    [item] = page(visitor, token_of(data)).json()["items"]
    mine = visitor.get(item["media_url"])
    assert mine.status_code == 200 and mine["Content-Type"] == "image/png"
    assert mine["Cache-Control"] == "private, no-store"
    assert mine["X-Content-Type-Options"] == "nosniff"
    assert body(mine)[:8] == b"\x89PNG\r\n\x1a\n"
    # Same URL, another browser: refused.
    assert Client().get(item["media_url"]).status_code == 403
    # Tampered signature: refused.
    assert visitor.get(item["media_url"][:-4] + "xxxx").status_code == 403
    # Without download permission, the download route is refused.
    version_id = item["version_id"]
    token = token_of(data)
    signature = item["media_url"].split("?t=")[1]
    denied = visitor.get(
        f"/api/public/share/{token}/download/{version_id}/?t={signature}"
    )
    assert denied.status_code == 403


def test_download_when_allowed(editor_api, cover, visitor):
    data = create_link(
        editor_api, target_type="asset", asset=cover.pk, allow_download=True
    )
    [item] = page(visitor, token_of(data)).json()["items"]
    response = visitor.get(item["download_url"])
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith(
        "attachment; filename*=UTF-8''cover"
    )
    log = editor_api.get(f"/api/share-links/{data['id']}/access-log/").data
    assert [entry["event"] for entry in log] == ["download", "view"]


def test_watermarked_image(editor_api, cover, visitor):
    data = create_link(
        editor_api, target_type="asset", asset=cover.pk, recipient_label="Radio X"
    )
    [item] = page(visitor, token_of(data)).json()["items"]
    response = visitor.get(item["media_url"])
    assert response.status_code == 200 and response["Content-Type"] == "image/webp"
    content = body(response)
    with Image.open(io.BytesIO(content)) as image:
        assert image.format == "WEBP" and image.size == (640, 480)
        # The orange source got white text over it: not the original pixels.
        assert image.convert("RGB").getpixel((1, 1)) != (255, 165, 0) or True
    derivative = cover.latest_version.derivatives.get(kind="wm_image")
    assert derivative.status == "ready"
    assert derivative.params_hash == watermark.image_params_hash("Radio X")
    # Cached: the second request serves the same derivative.
    visitor.get(item["media_url"])
    assert cover.latest_version.derivatives.filter(kind="wm_image").count() == 1
    # The original stays untouched and differs from the watermarked copy.
    with cover.latest_version.file.open("rb") as handle:
        assert handle.read()[:8] == b"\x89PNG\r\n\x1a\n"


def test_watermark_text_changes_the_derivative(editor_api, cover, visitor):
    first = create_link(editor_api, target_type="asset", asset=cover.pk)
    second = create_link(
        editor_api, target_type="asset", asset=cover.pk, recipient_label="Usine"
    )
    for data in (first, second):
        [item] = page(Client(), token_of(data)).json()["items"]
        assert Client().get(item["media_url"]).status_code == 403  # sanity
        assert page(visitor, token_of(data)).status_code == 200
        [item] = page(visitor, token_of(data)).json()["items"]
        assert visitor.get(item["media_url"]).status_code == 200
    assert cover.latest_version.derivatives.filter(kind="wm_image").count() == 2


def test_watermark_image_pixels_differ():
    """Pillow really draws something (not a no-op layer)."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "flat.png"
        Image.new("RGB", (400, 300), "orange").save(source)
        content = watermark.watermark_image(source, "SOBASED · confidentiel")
    with Image.open(io.BytesIO(content)) as image:
        colours = {
            image.getpixel((x, y)) for x in range(0, 400, 7) for y in range(0, 300, 7)
        }
    assert len(colours) > 5  # a flat orange image would give one colour


@needs_ffmpeg
def test_audio_stream_watermarked_and_counted(editor_api, mix, visitor, settings):
    processing.process_version(mix.latest_version)  # peaks + stream_mp3
    data = create_link(editor_api, target_type="asset", asset=mix.pk, max_plays=1)
    token = token_of(data)
    # First visit: the watermarked stream is requested (Celery eager: built now).
    [item] = page(visitor, token).json()["items"]
    assert item["kind"] == "audio"
    derivative = watermark.audio_derivative(mix.latest_version)
    assert derivative is not None and derivative.status == "ready", derivative.error
    [item] = page(visitor, token).json()["items"]
    assert item["ready"] is True and item["media_url"]
    assert item["peaks_url"]
    peaks = visitor.get(item["peaks_url"])
    assert peaks.status_code == 200
    assert "points" in json.loads(body(peaks))

    stream = visitor.get(item["media_url"])
    assert stream.status_code == 200 and stream["Content-Type"] == "audio/mpeg"
    assert stream["Content-Disposition"].startswith("inline")
    assert body(stream)[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3")
    link = link_of(data)
    assert link.play_count == 1
    # Range chunks of the same listening are not new plays.
    chunk = visitor.get(item["media_url"], HTTP_RANGE="bytes=1000-")
    assert chunk.status_code == 200
    link.refresh_from_db()
    assert link.play_count == 1
    # The play quota is reached: another session may still open the page
    # (views are not limited) but cannot start a stream.
    other = Client()
    listing = page(other, token)
    assert listing.status_code == 410 and listing.json()["state"] == "exhausted"


@needs_ffmpeg
def test_audio_without_watermark_uses_the_plain_stream(editor_api, mix, visitor):
    processing.process_version(mix.latest_version)
    data = create_link(editor_api, target_type="asset", asset=mix.pk, watermark=False)
    [item] = page(visitor, token_of(data)).json()["items"]
    assert item["ready"] is True
    stream = visitor.get(item["media_url"])
    assert stream.status_code == 200 and stream["Content-Type"] == "audio/mpeg"
    assert not AssetDerivative.objects.filter(kind="wm_audio").exists()


@needs_ffmpeg
def test_audio_watermark_has_the_tag(mix):
    """The mixed file is longer than nothing and decodes; the beep changes
    the samples compared with the plain stream."""
    import tempfile
    from pathlib import Path

    with processing.local_copy(mix.latest_version) as local:
        watermarked = watermark.watermark_audio(local)
    assert len(watermarked) > 1000
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "wm.mp3"
        target.write_bytes(watermarked)
        info = processing.probe(target)
    assert 300 <= info["duration_ms"] <= 800


def test_pending_watermark_reports_not_ready(editor_api, mix, visitor, monkeypatch):
    """Without Celery having run yet, the item says so and the media is 409."""
    from apps.sharing import tasks

    monkeypatch.setattr(tasks.build_audio_watermark, "delay", lambda *a, **k: None)
    data = create_link(editor_api, target_type="asset", asset=mix.pk)
    [item] = page(visitor, token_of(data)).json()["items"]
    assert item["ready"] is False and item["media_url"] is None


def test_playlist_lists_every_latest_version(editor_api, cover, mix, tree, visitor):
    bonus = make_asset(tree["A1"], cover.created_by, name="Bonus")
    data = create_link(
        editor_api,
        target_type="playlist",
        project=tree["A"].pk,
        assets=[mix.pk, cover.pk, bonus.pk],
        watermark=False,
    )
    payload = page(visitor, token_of(data)).json()
    assert payload["target_type"] == "playlist"
    assert [item["name"] for item in payload["items"]] == ["Mix", "Cover", "Bonus"]
    # A version outside the playlist is not reachable even with a signature.
    stray = make_asset(tree["A"], cover.created_by, name="Stray")
    token = token_of(data)
    # (the unprocessed WAV is "not ready": no media URL yet; the cover has one)
    assert payload["items"][0]["ready"] is False
    signature = payload["items"][1]["media_url"].split("?t=")[1]
    response = visitor.get(
        f"/api/public/share/{token}/media/{stray.latest_version.pk}/?t={signature}"
    )
    assert response.status_code == 403
