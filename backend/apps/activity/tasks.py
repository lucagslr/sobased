from celery import shared_task

from . import services


@shared_task
def purge_old_entries() -> int:
    """Beat, daily: entries older than 12 months (SPEC §14)."""
    return services.purge()
