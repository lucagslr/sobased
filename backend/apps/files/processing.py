"""What happens to a version after its upload (SPECIFICATIONS §5), in Celery:

- metadata: duration (audio, video), dimensions (image, video), page count
  (PDF), all read once here so the browser never decodes a 500 MB file;
- thumbnail: image (Pillow), video (one frame with ffmpeg), PDF (none: the
  browser renders the first page with pdf.js);
- waveform peaks: JSON of normalised amplitudes, for wavesurfer;
- stream: MP3 128 kbps for in-app playback of audio and video sound.

ffmpeg / ffprobe are optional at runtime: without them the file is still
usable (original download, no waveform), and the version records why.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageOps

from .models import AssetDerivative, AssetVersion, Kind

THUMBNAIL_SIZE = 512
PEAKS_POINTS = 800
PEAKS_RATE = 8000  # Hz, mono: plenty for a waveform, cheap to decode
STREAM_BITRATE = "128k"
FFMPEG_TIMEOUT = 600  # seconds: a long video on a small VPS


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, capture_output=True, check=True, timeout=FFMPEG_TIMEOUT
    )


def probe(path: Path) -> dict:
    """ffprobe as JSON: format duration, first video stream dimensions."""
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    data = json.loads(result.stdout or b"{}")
    info: dict = {}
    duration = float((data.get("format") or {}).get("duration") or 0)
    if duration:
        info["duration_ms"] = int(duration * 1000)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and stream.get("width"):
            info["width"] = int(stream["width"])
            info["height"] = int(stream["height"])
            break
    return info


def image_metadata(path: Path) -> dict:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        return {"width": image.width, "height": image.height}


def pdf_page_count(path: Path) -> int | None:
    """Count the page objects of a PDF. Good enough for a badge; pdf.js gives
    the exact figure in the browser."""
    with open(path, "rb") as handle:
        data = handle.read()
    found = len(re.findall(rb"/Type\s*/Page(?![s/\w])", data))
    return found or None


# --- Derivatives ---------------------------------------------------------------


def _store(version: AssetVersion, kind: str, content: bytes, ext: str, mime: str):
    derivative, _ = AssetDerivative.objects.get_or_create(version=version, kind=kind)
    if derivative.file:
        derivative.file.delete(save=False)
    derivative.file.save(f"d.{ext}", ContentFile(content), save=False)
    derivative.content_type = mime
    derivative.status = AssetDerivative.DerivativeStatus.READY
    derivative.error = ""
    derivative.save()
    return derivative


def describe(exc: Exception) -> str:
    """A short, readable reason (the full ffmpeg command is not for users)."""
    if isinstance(exc, subprocess.CalledProcessError):
        stderr = (exc.stderr or b"").decode(errors="replace").strip().splitlines()
        detail = stderr[-1][:120] if stderr else f"code {exc.returncode}"
        return f"ffmpeg : {detail}"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "ffmpeg : délai dépassé"
    return f"{type(exc).__name__}: {str(exc)[:120]}"


def _fail(version: AssetVersion, kind: str, error: str):
    derivative, _ = AssetDerivative.objects.get_or_create(version=version, kind=kind)
    derivative.status = AssetDerivative.DerivativeStatus.FAILED
    derivative.error = error[:200]
    derivative.save()


def image_thumbnail(path: Path) -> bytes:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="WEBP", quality=80)
        return buffer.getvalue()


def video_thumbnail(path: Path) -> bytes:
    with tempfile.TemporaryDirectory() as folder:
        frame = Path(folder) / "frame.png"
        _run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                "1",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={THUMBNAIL_SIZE}:-2",
                "-y",
                str(frame),
            ]
        )
        return image_thumbnail(frame)


def waveform_peaks(path: Path) -> bytes:
    """PEAKS_POINTS normalised amplitudes (0..1), as JSON. The audio is decoded
    to 8 kHz mono 16-bit PCM by ffmpeg, then bucketed here."""
    result = _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(PEAKS_RATE),
            "-f",
            "s16le",
            "-",
        ]
    )
    samples = memoryview(result.stdout).cast("h")
    total = len(samples)
    if total == 0:
        return json.dumps({"points": [], "duration_ms": 0}).encode()
    bucket = max(1, total // PEAKS_POINTS)
    peaks = []
    for start in range(0, total, bucket):
        chunk = samples[start : start + bucket]
        peaks.append(max(abs(value) for value in chunk))
    top = max(peaks) or 1
    points = [round(value / top, 3) for value in peaks[:PEAKS_POINTS]]
    duration_ms = int(total / PEAKS_RATE * 1000)
    return json.dumps({"points": points, "duration_ms": duration_ms}).encode()


def stream_mp3(path: Path) -> bytes:
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / "stream.mp3"
        _run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                STREAM_BITRATE,
                "-y",
                str(out),
            ]
        )
        return out.read_bytes()


# --- The task body -------------------------------------------------------------


def process_version(version: AssetVersion) -> None:
    """Fill the metadata and build the derivatives of an uploaded version.
    Idempotent: running it again recomputes everything."""
    if not version.file:
        return
    kind = version.kind
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        # Work on a local copy: the storage may be S3 in production.
        local = Path(folder) / ("source." + version.file.name.rsplit(".", 1)[-1])
        with version.file.open("rb") as source, open(local, "wb") as target:
            shutil.copyfileobj(source, target)
        version.sha256 = version.sha256 or sha256_of(local)

        if kind == Kind.IMAGE:
            try:
                version.__dict__.update(image_metadata(local))
                _store(
                    version, "thumbnail", image_thumbnail(local), "webp", "image/webp"
                )
            except Exception as exc:  # noqa: BLE001 - recorded, never fatal
                errors.append(f"image: {describe(exc)}")
                _fail(version, "thumbnail", describe(exc))
        elif kind == Kind.DOCUMENT:
            version.page_count = pdf_page_count(local)
        elif kind in (Kind.AUDIO, Kind.VIDEO):
            if not ffmpeg_available():
                errors.append("ffmpeg absent")
                for name in ("peaks", "stream_mp3", "thumbnail")[
                    : 3 if kind == Kind.VIDEO else 2
                ]:
                    _fail(version, name, "ffmpeg absent")
            else:
                try:
                    version.__dict__.update(probe(local))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"probe: {describe(exc)}")
                for name, builder, ext, mime in (
                    ("peaks", waveform_peaks, "json", "application/json"),
                    ("stream_mp3", stream_mp3, "mp3", "audio/mpeg"),
                ):
                    try:
                        _store(version, name, builder(local), ext, mime)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{name}: {describe(exc)}")
                        _fail(version, name, describe(exc))
                if kind == Kind.VIDEO:
                    try:
                        _store(
                            version,
                            "thumbnail",
                            video_thumbnail(local),
                            "webp",
                            "image/webp",
                        )
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"thumbnail: {describe(exc)}")
                        _fail(version, "thumbnail", describe(exc))
    version.processed_at = timezone.now()
    version.processing_error = "; ".join(errors)[:200]
    version.save(
        update_fields=[
            "sha256",
            "duration_ms",
            "width",
            "height",
            "page_count",
            "processed_at",
            "processing_error",
            "updated_at",
        ]
    )
