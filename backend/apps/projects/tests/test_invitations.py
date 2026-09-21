"""Pending invitations: acceptance page, acceptance, sign-up through the link."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.accounts.tokens import make_email_token
from apps.projects.models import Invitation, Membership

pytestmark = pytest.mark.django_db


def make_invitation(tree, email="new@example.org", role="editor", scope="A", **extra):
    invitation = Invitation(
        email=email, role=role, project=tree[scope], invited_by=tree.owner, **extra
    )
    token = invitation.issue_token()
    invitation.save()
    return invitation, token


def login(user):
    client = APIClient()
    client.force_login(user)
    return client


REGISTER = {
    "username": "newbie",
    "email": "new@example.org",
    "password": "un-mot-de-passe-solide",
    "accept_privacy": True,
}


# --- Public acceptance page ---------------------------------------------------------


def test_lookup_shows_what_the_visitor_is_invited_to(tree, api):
    _, token = make_invitation(tree)

    response = api.get(f"/api/invitations/lookup/{token}/")

    assert response.status_code == 200
    assert response.data == {
        "email": "new@example.org",
        "scope_type": "project",
        "scope_name": "A",
        "role": "editor",
        "invited_by": tree.owner.display_name,
        "is_pending": True,
    }


def test_lookup_of_an_unknown_or_used_token_is_a_404(tree, api):
    invitation, token = make_invitation(tree)
    assert api.get("/api/invitations/lookup/nope/").status_code == 404

    invitation.accepted_at = timezone.now()
    invitation.save()
    assert api.get(f"/api/invitations/lookup/{token}/").status_code == 404


def test_lookup_flags_an_expired_invitation(tree, api):
    invitation, token = make_invitation(tree)
    Invitation.objects.filter(pk=invitation.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )

    assert api.get(f"/api/invitations/lookup/{token}/").data["is_pending"] is False


# --- Accepting while signed in ------------------------------------------------------


def test_accept_creates_the_membership_once(tree):
    _, token = make_invitation(tree, can_view_finance=True)
    user = UserFactory()
    client = login(user)

    first = client.post("/api/invitations/accept/", {"token": token}, format="json")
    second = client.post("/api/invitations/accept/", {"token": token}, format="json")

    assert first.status_code == 200
    assert first.data == {"scope_type": "project", "scope_id": tree["A"].pk}
    membership = Membership.objects.get(user=user, project=tree["A"])
    assert (membership.role, membership.can_view_finance) == ("editor", True)
    assert second.status_code == 400  # single use


def test_accept_expired_invitation_is_refused(tree):
    invitation, token = make_invitation(tree)
    Invitation.objects.filter(pk=invitation.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )

    response = login(UserFactory()).post(
        "/api/invitations/accept/", {"token": token}, format="json"
    )
    assert response.status_code == 400


def test_accepting_never_lowers_an_existing_role(tree):
    from .factories import grant

    _, token = make_invitation(tree, role="viewer")
    user = UserFactory()
    grant(user, tree["A"], "admin")

    login(user).post("/api/invitations/accept/", {"token": token}, format="json")

    assert Membership.objects.get(user=user, project=tree["A"]).role == "admin"


def test_accepting_with_the_invited_address_verifies_it(tree):
    _, token = make_invitation(tree, email="me@example.org")
    user = UserFactory(email="me@example.org", email_verified_at=None)

    login(user).post("/api/invitations/accept/", {"token": token}, format="json")

    user.refresh_from_db()
    assert user.email_verified


def test_accept_requires_authentication(tree, api):
    _, token = make_invitation(tree)

    assert api.post("/api/invitations/accept/", {"token": token}).status_code == 401


# --- Signing up through the link ----------------------------------------------------


def test_sign_up_with_the_invited_address_verifies_it_and_joins(tree, api):
    _, token = make_invitation(tree)

    response = api.post("/api/auth/register/", {**REGISTER, "invitation": token})

    assert response.status_code == 201
    assert response.data["email_verified"] is True
    assert Membership.objects.filter(
        user__username="newbie", project=tree["A"]
    ).exists()
    assert mail.outbox == []  # no verification e-mail needed


def test_sign_up_with_another_address_is_a_normal_sign_up(tree, api):
    _, token = make_invitation(tree)

    response = api.post(
        "/api/auth/register/",
        {**REGISTER, "email": "other@example.org", "invitation": token},
    )

    assert response.status_code == 201
    assert response.data["email_verified"] is False
    assert not Membership.objects.filter(user__username="newbie").exists()


def test_closed_registration_lets_invited_people_in_only(tree, api, settings):
    settings.REGISTRATION_OPEN = False
    _, token = make_invitation(tree)

    without_token = api.post("/api/auth/register/", REGISTER)
    wrong_address = api.post(
        "/api/auth/register/",
        {**REGISTER, "email": "other@example.org", "invitation": token},
    )
    invited = api.post("/api/auth/register/", {**REGISTER, "invitation": token})

    assert (without_token.status_code, wrong_address.status_code) == (403, 403)
    assert invited.status_code == 201


def test_verifying_an_email_applies_the_invitations_waiting_for_it(tree, api):
    make_invitation(tree, email="late@example.org", scope="A")
    make_invitation(tree, email="late@example.org", scope="R2", role="viewer")
    user = UserFactory(email="late@example.org", email_verified_at=None)

    api.post("/api/auth/verify-email/", {"token": make_email_token(user)})

    roles = dict(
        Membership.objects.filter(user=user).values_list("project__name", "role")
    )
    assert roles == {"A": "editor", "R2": "viewer"}
    assert not Invitation.objects.filter(accepted_at__isnull=True).exists()


# --- Managing pending invitations ---------------------------------------------------


def test_admins_list_cancel_and_resend(tree, owner_api):
    invitation, old_token = make_invitation(tree)

    listed = owner_api.get(f"/api/invitations/?project={tree['A'].pk}")
    assert [item["email"] for item in listed.data] == ["new@example.org"]

    resent = owner_api.post(f"/api/invitations/{invitation.pk}/resend/")
    assert resent.status_code == 200
    assert Invitation.find_by_token(old_token) is None  # the old link is dead
    assert "/invitation/" in mail.outbox[-1].body

    assert owner_api.delete(f"/api/invitations/{invitation.pk}/").status_code == 204
    assert not Invitation.objects.exists()


def test_invitations_are_hidden_from_non_admins(tree, member, member_api):
    from .factories import grant

    invitation, _ = make_invitation(tree)
    grant(member, tree["A"], "editor")

    assert (
        member_api.get(f"/api/invitations/?project={tree['A'].pk}").status_code == 403
    )
    assert member_api.delete(f"/api/invitations/{invitation.pk}/").status_code == 403
