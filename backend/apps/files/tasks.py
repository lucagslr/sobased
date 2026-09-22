from celery import shared_task

from . import processing
from .models import AssetVersion


@shared_task
def process_version(version_id: int) -> None:
    """After an upload: metadata, thumbnail, waveform, stream (processing.py)."""
    version = AssetVersion.objects.select_related("asset").filter(pk=version_id).first()
    if version is not None:
        processing.process_version(version)
