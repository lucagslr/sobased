"""Watermarks for shared media (SPEC §10, SPECIFICATIONS §6).

- image: the text repeated diagonally, semi-transparent, drawn by Pillow on
  a copy scaled down to WM_IMAGE_MAX px (a public page never needs the
  original resolution, and the smaller file is one more deterrent);
- audio: a sound tag (AUDIO_WATERMARK_TAG, else a generated discreet beep)
  mixed every AUDIO_WATERMARK_INTERVAL_S seconds by ffmpeg, into an MP3
  128 kbps stream.

Both are derivatives of the version, cached by params_hash (the text, or
the tag + interval), so the work is done once per version and recipient.
"""

from __future__ import annotations

import hashlib
import io
import math
import tempfile
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont, ImageOps

from apps.files import processing
from apps.files.models import AssetDerivative, AssetVersion

WM_IMAGE_MAX = 2048
WM_IMAGE_KIND = AssetDerivative.DerivativeKind.WM_IMAGE
WM_AUDIO_KIND = AssetDerivative.DerivativeKind.WM_AUDIO
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
]


def image_params_hash(text: str) -> str:
    return hashlib.sha256(f"image|{text}".encode()).hexdigest()


def audio_params_hash() -> str:
    tag = settings.AUDIO_WATERMARK_TAG or "beep"
    return hashlib.sha256(
        f"audio|{tag}|{settings.AUDIO_WATERMARK_INTERVAL_S}".encode()
    ).hexdigest()


def _font(size: int):
    for candidate in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def watermark_image(path: Path, text: str) -> bytes:
    """The image with `text` tiled at 30°, white with a dark halo, ~25 % opaque.
    Returned as WebP."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    image.thumbnail((WM_IMAGE_MAX, WM_IMAGE_MAX), Image.Resampling.LANCZOS)
    width, height = image.size
    # A layer larger than the image so that the rotated tiling covers corners.
    diagonal = int(math.hypot(width, height))
    layer = Image.new("RGBA", (diagonal, diagonal), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _font(max(18, min(width, height) // 18))
    box = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    step_x, step_y = text_w + text_h * 3, text_h * 5
    for row, y in enumerate(range(0, diagonal, step_y)):
        offset = (row % 2) * step_x // 2
        for x in range(-step_x, diagonal, step_x):
            position = (x + offset, y)
            draw.text(
                position,
                text,
                font=font,
                fill=(255, 255, 255, 70),
                stroke_width=2,
                stroke_fill=(0, 0, 0, 60),
            )
    layer = layer.rotate(30, resample=Image.Resampling.BICUBIC)
    left, top = (diagonal - width) // 2, (diagonal - height) // 2
    layer = layer.crop((left, top, left + width, top + height))
    image.alpha_composite(layer)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="WEBP", quality=82)
    return buffer.getvalue()


def _tag_file(folder: Path) -> Path:
    """The sound tag to mix: the configured file, else a short soft beep."""
    configured = settings.AUDIO_WATERMARK_TAG
    if configured and Path(configured).is_file():
        return Path(configured)
    beep = folder / "beep.wav"
    processing._run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1200:duration=0.18",
            "-af",
            "afade=t=in:d=0.02,afade=t=out:st=0.14:d=0.04,volume=0.25",
            "-y",
            str(beep),
        ]
    )
    return beep


def watermark_audio(path: Path) -> bytes:
    """MP3 128 kbps of the audio with the tag every N seconds.

    The tag is padded to one period, looped for ever, then mixed with the
    music; `duration=first` stops the mix at the end of the music.
    """
    interval = max(5, settings.AUDIO_WATERMARK_INTERVAL_S)
    with tempfile.TemporaryDirectory() as folder:
        tag = _tag_file(Path(folder))
        out = Path(folder) / "wm.mp3"
        period_samples = interval * 44100
        graph = (
            "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"apad=whole_len={period_samples},aloop=loop=-1:size={period_samples}[tag];"
            "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[music];"
            "[music][tag]amix=inputs=2:duration=first:dropout_transition=0:"
            "normalize=0[out]"
        )
        processing._run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-i",
                str(tag),
                "-filter_complex",
                graph,
                "-map",
                "[out]",
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                "-y",
                str(out),
            ]
        )
        return out.read_bytes()


# --- Derivative plumbing ----------------------------------------------------------


def get_or_build_image(version: AssetVersion, text: str) -> AssetDerivative:
    """Synchronous: Pillow is fast enough for a page load (capped at 2048 px)."""
    params = image_params_hash(text)
    found = version.derivatives.filter(kind=WM_IMAGE_KIND, params_hash=params).first()
    if found is not None and found.status == AssetDerivative.DerivativeStatus.READY:
        return found
    try:
        with processing.local_copy(version) as local:
            content = watermark_image(local, text)
    except Exception as exc:  # noqa: BLE001 - recorded on the derivative
        processing.fail_derivative(
            version, WM_IMAGE_KIND, processing.describe(exc), params_hash=params
        )
        raise
    return processing.store_derivative(
        version, WM_IMAGE_KIND, content, "webp", "image/webp", params_hash=params
    )


def build_audio(version: AssetVersion) -> AssetDerivative:
    """The Celery side (tasks.build_audio_watermark)."""
    params = audio_params_hash()
    try:
        with processing.local_copy(version) as local:
            content = watermark_audio(local)
    except Exception as exc:  # noqa: BLE001
        processing.fail_derivative(
            version, WM_AUDIO_KIND, processing.describe(exc), params_hash=params
        )
        raise
    return processing.store_derivative(
        version, WM_AUDIO_KIND, content, "mp3", "audio/mpeg", params_hash=params
    )


def audio_derivative(version: AssetVersion) -> AssetDerivative | None:
    return version.derivatives.filter(
        kind=WM_AUDIO_KIND, params_hash=audio_params_hash()
    ).first()


def request_audio(version: AssetVersion) -> AssetDerivative:
    """Make sure a watermarked stream exists or is being built; returns the
    derivative (pending, ready or failed) so the caller can tell the page."""
    from .tasks import build_audio_watermark  # tasks import this module

    derivative, created = AssetDerivative.objects.get_or_create(
        version=version, kind=WM_AUDIO_KIND, params_hash=audio_params_hash()
    )
    if created or derivative.status == AssetDerivative.DerivativeStatus.FAILED:
        derivative.status = AssetDerivative.DerivativeStatus.PENDING
        derivative.error = ""
        derivative.save(update_fields=["status", "error", "updated_at"])
        build_audio_watermark.delay(version.pk)
    return derivative
