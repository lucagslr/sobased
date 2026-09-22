from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.files.models import AssetVersion

from . import watermark
from .models import ShareAccessLog

ACCESS_LOG_RETENTION_DAYS = 365


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


@shared_task
def purge_access_logs() -> int:
    """Beat, daily: access log entries older than 12 months (SPEC §10)."""
    limit = timezone.now() - timedelta(days=ACCESS_LOG_RETENTION_DAYS)
    deleted, _ = ShareAccessLog.objects.filter(created_at__lt=limit).delete()
    return deleted
