"""Inviting people and turning invitations into memberships.

Permission checks are done by the views; this module holds the rules that do
not depend on who is asking (SPECIFICATIONS §1.4):

- inviting a username, or the e-mail of a VERIFIED account, creates the
  membership right away (like Google Drive: no acceptance step);
- inviting any other e-mail creates a pending Invitation, valid 14 days;
- an e-mail address only ever receives memberships once it is proven to belong
  to the account (verification link, or the invitation link itself).
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core.emails import send_templated_email

from .access import Role
from .models import Invitation, Membership

User = get_user_model()


def _scope_kwargs(scope) -> dict:
    from apps.workspaces.models import Workspace

    return {"workspace": scope} if isinstance(scope, Workspace) else {"project": scope}


def _scope_url(scope) -> str:
    from apps.workspaces.models import Workspace

    if isinstance(scope, Workspace):
        return f"{settings.SITE_URL}/projets"
    return f"{settings.SITE_URL}/projets/{scope.pk}"


def grant(
    user,
    scope,
    *,
    role: str,
    can_view_finance: bool,
    can_edit_finance: bool,
    invited_by=None,
) -> Membership:
    """Give `user` a membership on `scope`, never lowering what they have.

    If a membership already exists on this exact scope, the higher role wins
    and finance flags are OR-ed, so re-inviting someone cannot demote them.
    """
    membership, created = Membership.objects.get_or_create(
        user=user,
        **_scope_kwargs(scope),
        defaults={
            "role": role,
            "can_view_finance": can_view_finance,
            "can_edit_finance": can_edit_finance,
            "invited_by": invited_by,
        },
    )
    if not created:
        if Role.from_stored(role) > Role.from_stored(membership.role):
            membership.role = role
        membership.can_view_finance |= can_view_finance
        membership.can_edit_finance |= can_edit_finance
        membership.save()
    return membership


@transaction.atomic
def invite(
    *, actor, scope, role, can_view_finance, can_edit_finance, username="", email=""
):
    """Returns ("membership", Membership) or ("invitation", Invitation).

    Raises ValueError with a user-facing message.
    """
    flags = {"can_view_finance": can_view_finance, "can_edit_finance": can_edit_finance}
    if username:
        user = User.objects.filter(
            username__iexact=username.lstrip("@"), is_active=True
        ).first()
        if user is None:
            raise ValueError("Aucun compte avec ce nom d'utilisateur.")
    else:
        email = email.strip().lower()
        # Only a VERIFIED e-mail identifies an account: otherwise anyone could
        # sign up with someone else's address and collect their invitations.
        user = User.objects.filter(
            email=email, is_active=True, email_verified_at__isnull=False
        ).first()

    if user is not None:
        if user.pk == actor.pk:
            raise ValueError("Tu as déjà accès à cet élément.")
        if Membership.objects.filter(user=user, **_scope_kwargs(scope)).exists():
            raise ValueError("Cette personne est déjà membre. Modifie son rôle.")
        membership = grant(user, scope, role=role, invited_by=actor, **flags)
        send_templated_email(
            to=user.email,
            subject=f"{actor.display_name} t'a ajouté à « {scope.name} »",
            template="member_added",
            context={
                "name": user.display_name,
                "actor": actor.display_name,
                "scope_name": scope.name,
                "role": membership.get_role_display(),
                "url": _scope_url(scope),
            },
        )
        return "membership", membership

    # One pending invitation per (e-mail, scope): inviting again refreshes it.
    Invitation.objects.filter(
        email=email, accepted_at__isnull=True, **_scope_kwargs(scope)
    ).delete()
    invitation = Invitation(
        email=email, role=role, invited_by=actor, **flags, **_scope_kwargs(scope)
    )
    token = invitation.issue_token()
    invitation.save()
    send_invitation_email(invitation, token)
    return "invitation", invitation


def send_invitation_email(invitation: Invitation, token: str) -> None:
    actor = invitation.invited_by
    actor_name = actor.display_name if actor else "Quelqu'un"
    send_templated_email(
        to=invitation.email,
        subject=f"{actor_name} t'invite sur « {invitation.scope.name} »",
        template="invitation",
        context={
            "actor": actor_name,
            "scope_name": invitation.scope.name,
            "role": invitation.get_role_display(),
            "url": f"{settings.SITE_URL}/invitation/{token}",
        },
    )


@transaction.atomic
def accept(invitation: Invitation, user) -> Membership:
    """Turn a pending invitation into a membership for `user`."""
    membership = grant(
        user,
        invitation.scope,
        role=invitation.role,
        can_view_finance=invitation.can_view_finance,
        can_edit_finance=invitation.can_edit_finance,
        invited_by=invitation.invited_by,
    )
    invitation.accepted_at = timezone.now()
    invitation.accepted_by = user
    invitation.save(update_fields=["accepted_at", "accepted_by", "updated_at"])
    return membership


def apply_pending_invitations(user) -> int:
    """Accept every pending invitation sent to the user's VERIFIED e-mail."""
    if not user.email_verified_at:
        return 0
    pending = Invitation.objects.filter(
        email=user.email, accepted_at__isnull=True, expires_at__gt=timezone.now()
    )
    count = 0
    for invitation in pending:
        accept(invitation, user)
        count += 1
    return count


def resolve_invitation_email(token: str) -> str | None:
    """E-mail a pending invitation token was sent to (hook used by sign-up).

    Referenced by settings.INVITATION_EMAIL_RESOLVER so that apps.accounts
    does not import this app.
    """
    invitation = Invitation.find_by_token(token) if token else None
    return invitation.email if invitation and invitation.is_pending else None
