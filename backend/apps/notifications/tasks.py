from celery import shared_task

from . import digest


@shared_task
def send_daily_digests() -> int:
    """Beat, every 15 minutes: the users whose local digest time has passed."""
    return digest.send_due_digests()
