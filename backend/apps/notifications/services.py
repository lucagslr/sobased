"""Creating notifications (and their e-mails), in one place.

Every event of SPECIFICATIONS §10 calls notify(): the in-app row is always
written (never for oneself), the e-mail goes out only when the table says
so (always for an invitation, preference for assignment and mention,
never for the others). E-mails are rendered here and sent by Celery.
"""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from apps.core.emails import send_templated_email

from .models import Kind, Notification


def notify(
    recipient,
    kind: str,
    *,
    actor=None,
    project=None,
    payload: dict | None = None,
    url: str = "",
    email: dict | None = None,
) -> Notification | None:
    """`email`: {"subject", "template", "context"} to also send a mail.
    Returns None when recipient is the actor (nobody notifies themselves)."""
    if actor is not None and recipient.pk == actor.pk:
        return None
    if not recipient.is_active:
        return None
    notification = Notification.objects.create(
        recipient=recipient,
        kind=kind,
        actor=actor,
        project=project,
        payload=payload or {},
        url=url[:300],
    )
    if email and recipient.email:
        send_templated_email(
            to=recipient.email,
            subject=email["subject"],
            template=email["template"],
            context={"name": recipient.display_name, **email.get("context", {})},
        )
        notification.emailed_at = timezone.now()
        notification.save(update_fields=["emailed_at", "updated_at"])
    return notification


def unread_count(user) -> int:
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def absolute(url: str) -> str:
    return f"{settings.SITE_URL}{url}" if url.startswith("/") else url


# --- The events (SPECIFICATIONS §10) -------------------------------------------------
def task_assigned(task, users, actor) -> None:
    url = f"/projets/{task.project_id}/taches?tache={task.pk}"
    for user in users:
        notify(
            user,
            Kind.ASSIGNMENT,
            actor=actor,
            project=task.project,
            payload={
                "title": task.title,
                "project_name": task.project.name,
                "actor_name": actor.display_name,
            },
            url=url,
            email=(
                {
                    "subject": f"Nouvelle tâche : {task.title}",
                    "template": "task_assigned",
                    "context": {
                        "actor": actor.display_name,
                        "task_title": task.title,
                        "project_name": task.project.name,
                        "url": absolute(url),
                    },
                }
                if user.email_on_assignment
                else None
            ),
        )


def mentioned(comment, users, actor) -> None:
    task = comment.task
    url = f"/projets/{task.project_id}/taches?tache={task.pk}"
    for user in users:
        notify(
            user,
            Kind.MENTION,
            actor=actor,
            project=task.project,
            payload={
                "title": task.title,
                "excerpt": comment.body[:140],
                "actor_name": actor.display_name,
            },
            url=url,
            email=(
                {
                    "subject": (
                        f"{actor.display_name} t'a mentionné dans « {task.title} »"
                    ),
                    "template": "task_mention",
                    "context": {
                        "actor": actor.display_name,
                        "task_title": task.title,
                        "excerpt": comment.body[:300],
                        "url": absolute(url),
                    },
                }
                if user.email_on_mention
                else None
            ),
        )


def member_added(user, scope, membership, actor, url: str) -> None:
    """Added to a workspace or a project: in-app + e-mail, always."""
    project = scope if scope.__class__.__name__ == "Project" else None
    notify(
        user,
        Kind.INVITATION,
        actor=actor,
        project=project,
        payload={
            "scope_name": scope.name,
            "role": membership.get_role_display(),
            "actor_name": actor.display_name,
        },
        url=url,
        email={
            "subject": f"{actor.display_name} t'a ajouté à « {scope.name} »",
            "template": "member_added",
            "context": {
                "actor": actor.display_name,
                "scope_name": scope.name,
                "role": membership.get_role_display(),
                "url": absolute(url),
            },
        },
    )


def asset_status_changed(asset, change, actor) -> None:
    """Followers of the asset (in-app only)."""
    url = f"/projets/{asset.project_id}/fichiers/{asset.pk}"
    for user in asset.followers.all():
        notify(
            user,
            Kind.ASSET_STATUS,
            actor=actor,
            project=asset.project,
            payload={
                "title": asset.name,
                "from_status": change.from_status,
                "to_status": change.to_status,
                "note": change.note[:140],
                "actor_name": actor.display_name,
            },
            url=url,
        )


def share_link_opened(link) -> None:
    """First opening of a link whose creator asked to know (in-app only)."""
    if not link.notify_on_open or link.created_by is None:
        return
    notify(
        link.created_by,
        Kind.SHARE_OPENED,
        project=link.project,
        payload={
            "title": link.title,
            "recipient_label": link.recipient_label,
        },
        url=f"/projets/{link.project_id}/liens",
    )
