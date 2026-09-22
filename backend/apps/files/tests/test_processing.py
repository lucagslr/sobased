"""The Celery side: metadata, thumbnails, waveform peaks, MP3 stream.

ffmpeg parts are skipped where ffmpeg is missing (the Docker image and the
CI runner have it); the version then records why in `processing_error`.
"""

import json

import pytest

from apps.files import processing
from apps.files.models import AssetDerivative
from apps.files.tasks import process_version

from .conftest import make_asset, pdf_upload, png_upload, text_upload, wav_upload

pytestmark = pytest.mark.django_db
needs_ffmpeg = pytest.mark.skipif(
    not processing.ffmpeg_available(), reason="ffmpeg / ffprobe not installed"
)


def _derivatives(version) -> dict[str, AssetDerivative]:
    return {d.kind: d for d in version.derivatives.all()}


def test_image_metadata_and_thumbnail(tree, editor):
    asset = make_asset(tree["A"], editor, upload=png_upload(size=(1200, 600)))
    version = asset.latest_version
    process_version(version.pk)  # eager Celery: runs inline
    version.refresh_from_db()
    assert (version.width, version.height) == (1200, 600)
    assert len(version.sha256) == 64
    assert version.processed_at is not None and version.processing_error == ""
    thumb = _derivatives(version)["thumbnail"]
    assert thumb.status == "ready" and thumb.content_type == "image/webp"
    with thumb.file.open("rb") as handle:
        head = handle.read(12)
    assert head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    assert thumb.file.name.startswith(f"derived/{tree['A'].pk}/")


def test_pdf_page_count(tree, editor):
    asset = make_asset(tree["A"], editor, upload=pdf_upload(pages=4))
    version = asset.latest_version
    processing.process_version(version)
    version.refresh_from_db()
    assert version.page_count == 4
    assert not version.derivatives.exists()  # pdf.js renders in the browser


def test_other_kind_only_hashes(tree, editor):
    asset = make_asset(tree["A"], editor, upload=text_upload())
    version = asset.latest_version
    processing.process_version(version)
    version.refresh_from_db()
    assert version.sha256 and version.processed_at
    assert version.width is None and version.duration_ms is None


def test_processing_is_idempotent(tree, editor):
    asset = make_asset(tree["A"], editor, upload=png_upload())
    version = asset.latest_version
    processing.process_version(version)
    first = _derivatives(version)["thumbnail"].file.name
    processing.process_version(version)
    assert version.derivatives.count() == 1
    assert _derivatives(version)["thumbnail"].file.name != first  # rebuilt


def test_broken_image_is_recorded_not_fatal(tree, editor, monkeypatch):
    asset = make_asset(tree["A"], editor, upload=png_upload())
    version = asset.latest_version

    def boom(path):
        raise ValueError("corrupt")

    monkeypatch.setattr(processing, "image_thumbnail", boom)
    processing.process_version(version)
    version.refresh_from_db()
    assert "corrupt" in version.processing_error
    assert _derivatives(version)["thumbnail"].status == "failed"
    assert version.processed_at is not None


def test_without_ffmpeg_audio_is_marked(tree, editor, monkeypatch):
    monkeypatch.setattr(processing, "ffmpeg_available", lambda: False)
    asset = make_asset(tree["A"], editor, upload=wav_upload())
    version = asset.latest_version
    processing.process_version(version)
    version.refresh_from_db()
    assert version.processing_error == "ffmpeg absent"
    kinds = _derivatives(version)
    assert set(kinds) == {"peaks", "stream_mp3"}
    assert all(d.status == "failed" for d in kinds.values())


@needs_ffmpeg
def test_audio_peaks_stream_and_duration(tree, editor, viewer_api):
    asset = make_asset(tree["A"], editor, upload=wav_upload(seconds=0.5))
    version = asset.latest_version
    processing.process_version(version)
    version.refresh_from_db()
    assert 400 <= version.duration_ms <= 600
    assert version.processing_error == ""
    kinds = _derivatives(version)
    assert kinds["stream_mp3"].status == "ready"
    assert kinds["peaks"].status == "ready"
    with kinds["peaks"].file.open("rb") as handle:
        peaks = json.load(handle)
    assert 0 < len(peaks["points"]) <= processing.PEAKS_POINTS
    assert max(peaks["points"]) == 1.0 and min(peaks["points"]) >= 0
    assert 400 <= peaks["duration_ms"] <= 600

    detail = viewer_api.get(f"/api/asset-versions/{version.pk}/").data
    assert detail["derivatives"] == {
        "thumbnail_url": None,
        "stream_url": f"/api/asset-versions/{version.pk}/stream/",
        "peaks_url": f"/api/asset-versions/{version.pk}/peaks/",
        "pending": False,
    }
    stream = viewer_api.get(f"/api/asset-versions/{version.pk}/stream/")
    assert stream.status_code == 200 and stream["Content-Type"] == "audio/mpeg"
    assert stream["Cache-Control"] == "private, max-age=3600"
    served = viewer_api.get(f"/api/asset-versions/{version.pk}/peaks/")
    assert json.loads(b"".join(served.streaming_content)) == peaks


@needs_ffmpeg
def test_video_gets_a_thumbnail(tree, editor, tmp_path):
    import subprocess

    from django.core.files.uploadedfile import SimpleUploadedFile

    source = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x48:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    upload = SimpleUploadedFile("clip.mp4", source.read_bytes())
    asset = make_asset(tree["A"], editor, upload=upload)
    assert asset.kind == "video"
    version = asset.latest_version
    processing.process_version(version)
    version.refresh_from_db()
    assert (version.width, version.height) == (64, 48)
    assert 1500 <= version.duration_ms <= 2500
    kinds = _derivatives(version)
    assert {k for k, d in kinds.items() if d.status == "ready"} == {
        "peaks",
        "stream_mp3",
        "thumbnail",
    }
