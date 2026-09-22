"""What is this upload, really? (SPECIFICATIONS §5: type checked by the file's
signature, never by its extension alone.)

Returns the kind (audio / image / video / document / other) and a MIME type
from the first bytes; images are additionally opened with Pillow so that a
renamed script can never pass for a picture.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .models import Kind


@dataclass(frozen=True)
class Sniffed:
    kind: str
    mime_type: str


# (magic bytes at offset 0, kind, mime)
_SIGNATURES: list[tuple[bytes, str, str]] = [
    (b"%PDF-", Kind.DOCUMENT, "application/pdf"),
    (b"ID3", Kind.AUDIO, "audio/mpeg"),
    (b"\xff\xfb", Kind.AUDIO, "audio/mpeg"),
    (b"\xff\xf3", Kind.AUDIO, "audio/mpeg"),
    (b"\xff\xf2", Kind.AUDIO, "audio/mpeg"),
    (b"fLaC", Kind.AUDIO, "audio/flac"),
    (b"OggS", Kind.AUDIO, "audio/ogg"),
    (b"\x1a\x45\xdf\xa3", Kind.VIDEO, "video/webm"),
]
_IMAGE_MIMES = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
}
# ISO base media (MP4 family): the brand at bytes 8-12 tells audio from video.
_AUDIO_BRANDS = (b"M4A ", b"M4B ", b"mp42")


def _riff(head: bytes) -> Sniffed | None:
    if head[:4] != b"RIFF" or len(head) < 12:
        return None
    if head[8:12] == b"WAVE":
        return Sniffed(Kind.AUDIO, "audio/wav")
    if head[8:12] == b"AVI ":
        return Sniffed(Kind.VIDEO, "video/x-msvideo")
    if head[8:12] == b"WEBP":
        return None  # let Pillow confirm it
    return None


def _iso_media(head: bytes) -> Sniffed | None:
    if len(head) < 12 or head[4:8] != b"ftyp":
        return None
    brand = head[8:12]
    if brand.startswith(b"qt"):
        return Sniffed(Kind.VIDEO, "video/quicktime")
    if brand in _AUDIO_BRANDS:
        return Sniffed(Kind.AUDIO, "audio/mp4")
    return Sniffed(Kind.VIDEO, "video/mp4")


def kind_of_mime(mime_type: str) -> str | None:
    """The kind a MIME type belongs to, or None when it says nothing."""
    if mime_type.startswith("image/"):
        return Kind.IMAGE
    if mime_type.startswith("audio/"):
        return Kind.AUDIO
    if mime_type.startswith("video/"):
        return Kind.VIDEO
    if mime_type == "application/pdf":
        return Kind.DOCUMENT
    return None


def sniff(upload) -> Sniffed:
    """Kind and MIME of an uploaded file, from its content. Never raises:
    anything unknown is "other" (application/octet-stream)."""
    head = upload.read(16)
    upload.seek(0)
    for signature, kind, mime in _SIGNATURES:
        if head.startswith(signature):
            return Sniffed(kind, mime)
    for probe in (_riff, _iso_media):
        found = probe(head)
        if found:
            return found
    try:
        with Image.open(upload) as image:
            image.verify()
            fmt = (image.format or "").lower()
        return Sniffed(Kind.IMAGE, _IMAGE_MIMES.get(fmt, f"image/{fmt}"))
    except Exception:  # noqa: BLE001 - Pillow raises SyntaxError on a bad PNG
        return Sniffed(Kind.OTHER, "application/octet-stream")
    finally:
        upload.seek(0)
