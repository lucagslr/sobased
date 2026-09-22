from celery import shared_task

from . import services
from .models import EventSeries


@shared_task
def materialise_all_series() -> int:
    """Nightly: keep every recurring event generated 90 days ahead."""
    return sum(services.materialise(series) for series in EventSeries.objects.all())
