from celery import shared_task

from . import services


@shared_task
def generate_recurring_expenses() -> int:
    """Nightly: create this period's "À payer" transaction of every recurring
    expense whose day is reached (SPEC §13)."""
    return services.generate_due()
