"""Deleting an account (SPEC §16, SPECIFICATIONS §11).

The row stays so that shared content keeps an author ("Utilisateur
supprimé"), but everything personal goes: identity fields, avatar, OAuth
tokens (revoked first, best effort), memberships, notifications, sessions,
exports, saved views, assignments. Blocked while the user owns a workspace
or a root project that other people can access: transfer or delete first.
Workspaces the user owns alone are deleted with them.
"""

from __future__ import annotations

from importlib import import_module

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.projects import tree
from apps.projects.models import Invitation, Membership
from apps.projects.models import Role as StoredRole


def _others_in_workspace(workspace, user) -> bool:
    return (
        Membership.objects.filter(
            Q(workspace=workspace) | Q(project__workspace=workspace)
        )
        .exclude(user=user)
        .exists()
    )


def deletion_blockers(user) -> list[str]:
    """Human-readable list of what must be transferred or deleted first."""
    blockers = []
    owned = Membership.objects.filter(user=user, role=StoredRole.OWNER).select_related(
        "workspace", "project__workspace"
    )
    for membership in owned:
        if membership.workspace_id:
            if _others_in_workspace(membership.workspace, user):
                blockers.append(f"l'espace « {membership.workspace.name} »")
        else:
            project = membership.project
            nodes = [node.pk for node in tree.subtree(project)]
            others = (
                Membership.objects.filter(
                    Q(project__in=nodes) | Q(workspace=project.workspace)
                )
                .exclude(user=user)
                .exists()
            )
            if others:
                blockers.append(f"le projet « {project.name} »")
    return blockers


def _revoke_tokens(user) -> None:
    """Outside any transaction: a slow provider must not hold a lock."""
    from apps.integrations import google
    from apps.integrations.models import OAuthAccount, Provider

    for account in OAuthAccount.objects.filter(user=user):
        if account.provider == Provider.GOOGLE:
            google.revoke(account)


def _delete_sessions(user) -> None:
    """Every session of the user, in the database AND in the cache (the
    cached_db backend serves a cached session without reading the row)."""
    engine = import_module(settings.SESSION_ENGINE)
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if session.get_decoded().get(SESSION_KEY) == str(user.pk):
            engine.SessionStore(session_key=session.session_key).delete()


def anonymize(user) -> None:
    """Irreversible. Raises ValueError with the blockers when refused."""
    blockers = deletion_blockers(user)
    if blockers:
        raise ValueError("Transfère ou supprime d'abord " + ", ".join(blockers) + ".")
    _revoke_tokens(user)
    from apps.events.models import Event
    from apps.files.models import Asset
    from apps.integrations.models import OAuthAccount
    from apps.tasks.models import Task

    with transaction.atomic():
        # Workspaces the user owns alone (blockers ruled out the others).
        for membership in Membership.objects.filter(
            user=user, role=StoredRole.OWNER, workspace__isnull=False
        ).select_related("workspace"):
            membership.workspace.delete()

        OAuthAccount.objects.filter(user=user).delete()  # calendars, mappings
        Membership.objects.filter(user=user).delete()
        Invitation.objects.filter(email=user.email, accepted_at__isnull=True).delete()
        user.notifications.all().delete()
        user.data_exports.all().delete()
        user.dashboard_views.all().delete()
        user.project_states.all().delete()
        Task.assignees.through.objects.filter(user=user).delete()
        Event.participants.through.objects.filter(user=user).delete()
        Asset.followers.through.objects.filter(user=user).delete()
        if user.avatar:
            user.avatar.delete(save=False)

        user.username = f"deleted-{user.pk}"
        user.email = f"deleted-{user.pk}@anonymized.invalid"
        user.first_name = ""
        user.last_name = ""
        user.phone = ""
        user.email_verified_at = None
        user.daily_digest_enabled = False
        user.is_active = False
        user.anonymized_at = timezone.now()
        user.set_unusable_password()
        user.save()
    _delete_sessions(user)
