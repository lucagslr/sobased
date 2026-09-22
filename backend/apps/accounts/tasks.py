"""Celery tasks of the accounts app: data exports and their expiry."""

from celery import shared_task
from django.utils import timezone

from . import exports
from .models import DataExport


@shared_task
def build_export(export_id: int) -> None:
    """Build the ZIP of one export request (exports.build)."""
    export = DataExport.objects.select_related("user").filter(pk=export_id).first()
    if export is not None and export.status == DataExport.Status.PENDING:
        exports.build(export)


@shared_task
def purge_expired_exports() -> int:
    """Beat, daily: archives past their 7 days (post_delete removes the file)."""
    deleted, _ = DataExport.objects.filter(expires_at__lt=timezone.now()).delete()
    return deleted
