"""Drive work done after the commit, out of the request."""

import logging

from celery import shared_task
from django.db.models import Q

from apps.projects.models import Project

from . import drive, sync
from .google import GoogleError
from .models import ExternalCalendar, OAuthAccount, Provider

log = logging.getLogger(__name__)


@shared_task
def create_project_folder(project_id: int, account_id: int | None) -> None:
    """The folder of a new project (root: with the creator's account and the
    type sub-folders; sub-project: under the parent's folder)."""
    project = Project.objects.filter(pk=project_id).select_related("parent").first()
    if project is None or project.drive_folder_id:
        return
    account = OAuthAccount.objects.filter(pk=account_id).first() if account_id else None
    try:
        drive.create_folder(project, account)
    except (drive.DriveUnavailable, GoogleError) as exc:
        # Nothing to retry blindly: the settings tab offers "Créer le dossier".
        log.warning("Drive folder for project %s not created: %s", project_id, exc)


@shared_task
def share_project_folder(project_id: int) -> None:
    project = Project.objects.filter(pk=project_id).first()
    if project is None:
        return
    try:
        drive.share_with_members(project)
    except (drive.DriveUnavailable, GoogleError) as exc:
        log.warning("Drive folder of project %s not shared: %s", project_id, exc)


# --- Calendars (SPEC §12) -------------------------------------------------------------
def _calendars_in_use():
    return ExternalCalendar.objects.filter(Q(is_target=True) | Q(is_displayed=True))


@shared_task
def sync_calendar_account(account_id: int) -> None:
    account = OAuthAccount.objects.filter(pk=account_id).select_related("user").first()
    if account is not None:
        sync.sync_account(account)


@shared_task
def sync_all_calendars() -> None:
    """Beat, every 5 minutes: every account with a target or displayed calendar."""
    for account_id in set(_calendars_in_use().values_list("account_id", flat=True)):
        sync_calendar_account.delay(account_id)


@shared_task
def renew_calendar_watches() -> None:
    """Beat, daily: Google push channels of the calendars in use."""
    calendars = _calendars_in_use().filter(account__provider=Provider.GOOGLE)
    for calendar in calendars.select_related("account"):
        sync.renew_watch(calendar)
