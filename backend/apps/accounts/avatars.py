"""Avatar processing: whatever is uploaded becomes a 256x256 WebP."""

import secrets
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

AVATAR_SIZE = 256


class InvalidImage(ValueError):
    pass


def build_avatar(uploaded_file) -> ContentFile:
    """Validate and normalise an uploaded image.

    Re-encoding drops EXIF metadata (GPS position of a phone photo) and
    guarantees that what we store really is an image.
    """
    try:
        image = Image.open(uploaded_file)
        image = ImageOps.exif_transpose(image)  # honour the phone's rotation flag
        image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImage("not an image") from exc

    image = ImageOps.fit(image, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=85)
    # Random name: the URL of an old avatar never resolves to the new one.
    return ContentFile(buffer.getvalue(), name=f"{secrets.token_hex(8)}.webp")
