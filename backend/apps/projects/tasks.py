"""Periodic housekeeping of the projects app."""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Invitation

EXPIRED_INVITATION_RETENTION_DAYS = 30


@shared_task
def purge_expired_invitations() -> int:
    """Beat, daily: invitations expired for more than 30 days (schema §7).
    Accepted ones stay: they document who invited whom."""
    limit = timezone.now() - timedelta(days=EXPIRED_INVITATION_RETENTION_DAYS)
    deleted, _ = Invitation.objects.filter(
        accepted_at__isnull=True, expires_at__lt=limit
    ).delete()
    return deleted
