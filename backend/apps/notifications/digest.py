"""The daily digest (SPECIFICATIONS §10).

Beat every 15 minutes: every user whose local time has passed their
`daily_digest_time` and who has not received today's digest gets it (a
missed run is caught up by the next one). Sections come from the same
services as the dashboard widgets, computed for the user alone (no saved
view): overdue, today, today's meetings, to validate, expenses to pay this
week, missing receipts (money only with can_view_finance). Nothing is sent
when every section is empty.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.emails import send_templated_email
from apps.core.localtime import local_day_bounds, local_today, user_zone
from apps.dashboard import services
from apps.dashboard.services import Scope
from apps.projects.access import get_access_map

User = get_user_model()


def _actor(user):
    """The dashboard services read `.user` off a request: a shim does."""
    return SimpleNamespace(user=user)


def _scope(actor, user) -> Scope:
    access_map = get_access_map(actor)
    return Scope(
        project_ids=sorted(access_map.project_ids()),
        tag_ids=[],
        only_mine=False,
        today=local_today(user),
    )


def _task_lines(queryset) -> list[dict]:
    return [
        {
            "title": task.title,
            "project": task.project.name,
            "url": f"/projets/{task.project_id}/taches?tache={task.pk}",
        }
        for task in queryset.select_related("project")[:20]
    ]


def build(user) -> dict | None:
    """The sections of the user's digest, or None when there is nothing."""
    actor = _actor(user)
    scope = _scope(actor, user)
    if not scope.project_ids:
        return None
    today = scope.today
    _, day_end = local_day_bounds(user, today)

    overdue = _task_lines(services.overdue_tasks(actor, scope).filter(assignees=user))
    todays = _task_lines(services.today_tasks(actor, scope).filter(assignees=user))
    meetings = [
        {
            "title": event.title,
            "project": event.project.name,
            "when": (
                "toute la journée"
                if event.all_day
                else timezone.localtime(event.start, user_zone(user)).strftime("%H:%M")
            ),
            "url": f"/projets/{event.project_id}/rdv?rdv={event.pk}",
        }
        for event in services.upcoming_events(actor, scope, days=0)
        .filter(start__lt=day_end)
        .select_related("project")[:20]
    ]
    to_validate = [
        {
            "title": item["title"],
            "project": item["project_name"],
            "url": (
                f"/projets/{item['project']}/taches?tache={item['id']}"
                if item["kind"] == "task"
                else (
                    f"/projets/{item['project']}/fichiers/{item['id']}"
                    if item["kind"] == "asset"
                    else f"/projets/{item['id']}"
                )
            ),
        }
        for item in services.to_validate_items(actor, scope)[:20]
    ]
    money = get_access_map(actor).project_ids(finance="view")
    to_pay, missing = [], []
    if money:
        week_end = today + timedelta(days=7)
        to_pay = [
            {
                "title": tx.label,
                "project": tx.project.name,
                "amount": str(tx.amount),
                "url": f"/projets/{tx.project_id}/compta?ecriture={tx.pk}",
            }
            for tx in services.expenses_to_pay(actor, scope)
            .filter(date__lte=week_end)
            .select_related("project")[:20]
        ]
        missing = [
            {
                "title": tx.label,
                "project": tx.project.name,
                "amount": str(tx.amount),
                "url": f"/projets/{tx.project_id}/compta?ecriture={tx.pk}",
            }
            for tx in services.missing_receipts(actor, scope).select_related("project")[
                :20
            ]
        ]
    sections = {
        "overdue": overdue,
        "today": todays,
        "meetings": meetings,
        "to_validate": to_validate,
        "to_pay": to_pay,
        "missing_receipts": missing,
    }
    if not any(sections.values()):
        return None
    return {"date": today, "sections": sections}


def due_now(user, now: datetime | None = None) -> bool:
    """Local time past the chosen hour, and nothing sent yet today."""
    if not user.daily_digest_enabled or not user.email_verified_at:
        return False
    now = now or timezone.now()
    local = now.astimezone(user_zone(user))
    if local.time() < user.daily_digest_time:
        return False
    return user.last_digest_sent_on != local.date()


def send(user, now: datetime | None = None) -> bool:
    """Build and send; the day is stamped even when there was nothing to
    say, so that a run 15 minutes later does not try again. The stamp uses
    the same instant as the decision (due_now), never a second "today"."""
    digest = build(user)
    now = now or timezone.now()
    today = now.astimezone(user_zone(user)).date()
    if digest is not None:
        send_templated_email(
            to=user.email,
            subject=f"Faiblegraine · ton résumé du {today.strftime('%d.%m.%Y')}",
            template="daily_digest",
            context={"name": user.display_name, "day": today, **digest["sections"]},
        )
    user.last_digest_sent_on = today
    user.save(update_fields=["last_digest_sent_on"])
    return digest is not None


def send_due_digests(now: datetime | None = None) -> int:
    sent = 0
    users = User.objects.filter(
        is_active=True, daily_digest_enabled=True, email_verified_at__isnull=False
    )
    for user in users.iterator():
        if due_now(user, now) and send(user, now):
            sent += 1
    return sent
