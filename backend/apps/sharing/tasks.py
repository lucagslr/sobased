from celery import shared_task

from apps.files.models import AssetVersion

from . import watermark


@shared_task
def build_audio_watermark(version_id: int) -> None:
    """ffmpeg mixes the sound tag into the version (watermark.py)."""
    version = AssetVersion.objects.select_related("asset").filter(pk=version_id).first()
    if version is None or not version.file:
        return
    try:
        watermark.build_audio(version)
    except Exception:  # noqa: BLE001 - already recorded on the derivative
        return
