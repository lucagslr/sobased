from celery import shared_task

from . import services
from .models import TaskSeries


@shared_task
def materialise_all_series() -> int:
    """Nightly: keep every recurring series generated 90 days ahead."""
    return sum(services.materialise(series) for series in TaskSeries.objects.all())
