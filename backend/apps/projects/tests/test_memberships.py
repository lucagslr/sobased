"""Inviting, changing roles, removing members (SPEC §6, SPECIFICATIONS §1.3-1.4)."""

import pytest
from django.core import mail

from apps.accounts.tests.factories import UserFactory
from apps.projects.models import Invitation, Membership

from .factories import grant

pytestmark = pytest.mark.django_db


def invite(client, **payload):
    return client.post("/api/memberships/", payload, format="json")


# --- Inviting -------------------------------------------------------------------


def test_invite_by_username_gives_access_at_once_and_notifies(tree, owner_api):
    helder = UserFactory(username="helder")

    response = invite(
        owner_api, project=tree["A"].pk, username="@Helder", role="editor"
    )

    assert response.status_code == 201
    assert response.data["kind"] == "membership"
    membership = Membership.objects.get(user=helder, project=tree["A"])
    assert (membership.role, membership.invited_by) == ("editor", tree.owner)
    assert mail.outbox[0].to == [helder.email]
    assert "A" in mail.outbox[0].subject


def test_invite_by_verified_email_gives_access_at_once(tree, owner_api):
    noam = UserFactory(email="noam@example.org")

    response = invite(
        owner_api, workspace=tree.workspace.pk, email="NOAM@example.org", role="viewer"
    )

    assert response.status_code == 201
    assert Membership.objects.filter(user=noam, workspace=tree.workspace).exists()
    assert not Invitation.objects.exists()


def test_invite_unknown_email_creates_a_pending_invitation(tree, owner_api):
    response = invite(
        owner_api, project=tree["A"].pk, email="new@example.org", role="commenter"
    )

    assert response.status_code == 202
    assert response.data["kind"] == "invitation"
    invitation = Invitation.objects.get()
    assert (invitation.email, invitation.role, invitation.is_pending) == (
        "new@example.org",
        "commenter",
        True,
    )
    assert "/invitation/" in mail.outbox[0].body
    # Only the hash is stored: the link cannot be rebuilt from the database.
    token = mail.outbox[0].body.split("/invitation/")[1].split()[0]
    assert token not in invitation.token_hash
    assert Invitation.find_by_token(token) == invitation


def test_unverified_account_email_is_not_trusted(tree, owner_api):
    """Otherwise anyone could sign up with a victim's address and collect
    the invitations meant for them."""
    squatter = UserFactory(email="victim@example.org", email_verified_at=None)

    response = invite(
        owner_api, project=tree["A"].pk, email="victim@example.org", role="admin"
    )

    assert response.status_code == 202
    assert not Membership.objects.filter(user=squatter).exists()


def test_inviting_the_same_email_twice_keeps_one_invitation(tree, owner_api):
    invite(owner_api, project=tree["A"].pk, email="new@example.org", role="viewer")
    invite(owner_api, project=tree["A"].pk, email="new@example.org", role="editor")

    assert list(Invitation.objects.values_list("role", flat=True)) == ["editor"]


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ghost", "role": "viewer"},  # unknown user
        {"username": "wsowner", "role": "viewer"},  # myself
        {"username": "helder", "email": "h@example.org", "role": "viewer"},  # both
        {"role": "viewer"},  # neither
        {"username": "helder", "role": "owner"},  # owner cannot be granted
        {"username": "helder", "role": "boss"},
    ],
)
def test_invalid_invitations(tree, owner_api, payload):
    UserFactory(username="helder")

    assert invite(owner_api, project=tree["A"].pk, **payload).status_code == 400
    assert Membership.objects.filter(project=tree["A"]).count() == 0


def test_scope_must_be_a_workspace_or_a_project_not_both(tree, owner_api):
    UserFactory(username="helder")

    response = invite(
        owner_api,
        project=tree["A"].pk,
        workspace=tree.workspace.pk,
        username="helder",
        role="viewer",
    )
    assert response.status_code == 400


def test_already_a_member_is_refused(tree, owner_api):
    helder = UserFactory(username="helder")
    grant(helder, tree["A"], "viewer")

    assert (
        invite(
            owner_api, project=tree["A"].pk, username="helder", role="admin"
        ).status_code
        == 400
    )


def test_finance_flags_default_by_role_and_can_be_chosen(tree, owner_api):
    for name in ("adm", "edi", "cho"):
        UserFactory(username=name)
    invite(owner_api, project=tree["A"].pk, username="adm", role="admin")
    invite(owner_api, project=tree["A"].pk, username="edi", role="editor")
    invite(
        owner_api,
        project=tree["A"].pk,
        username="cho",
        role="viewer",
        can_edit_finance=True,
    )

    flags = {
        m.user.username: (m.can_view_finance, m.can_edit_finance)
        for m in Membership.objects.filter(project=tree["A"])
    }
    assert flags == {"adm": (True, True), "edi": (False, False), "cho": (True, True)}


def test_cannot_grant_a_finance_right_you_do_not_have(tree, member, member_api):
    UserFactory(username="helder")
    grant(member, tree["A"], "admin", can_view_finance=False, can_edit_finance=False)

    refused = invite(
        member_api,
        project=tree["A"].pk,
        username="helder",
        role="viewer",
        can_view_finance=True,
    )
    allowed = invite(
        member_api,
        project=tree["A"].pk,
        username="helder",
        role="viewer",
        can_view_finance=False,
        can_edit_finance=False,
    )

    assert refused.status_code == 403
    assert allowed.status_code == 201


def test_unverified_user_cannot_invite(tree, member, member_api):
    UserFactory(username="helder")
    grant(member, tree["A"], "admin")
    member.email_verified_at = None
    member.save()

    assert (
        invite(
            member_api, project=tree["A"].pk, username="helder", role="viewer"
        ).status_code
        == 403
    )


def test_project_admin_cannot_invite_at_workspace_level(tree, member, member_api):
    UserFactory(username="helder")
    grant(member, tree["R"], "admin")

    response = invite(
        member_api, workspace=tree.workspace.pk, username="helder", role="viewer"
    )
    assert response.status_code == 404  # the workspace is only a shell for them


# --- Listing -----------------------------------------------------------------------


def test_effective_members_show_where_each_right_comes_from(tree, owner_api):
    helder = UserFactory(username="helder", first_name="Helder", last_name="S")
    grant(helder, tree["R"], "viewer")
    direct = grant(helder, tree["A1"], "editor", can_view_finance=True)

    members = owner_api.get(f"/api/memberships/?project={tree['A1'].pk}").data

    by_name = {m["user"]["username"]: m for m in members}
    assert set(by_name) == {"wsowner", "helder"}
    assert members[0]["user"]["username"] == "wsowner"  # highest role first
    assert "email" not in by_name["helder"]["user"]
    assert by_name["helder"]["role"] == "editor"
    assert by_name["helder"]["can_view_finance"] is True
    assert by_name["helder"]["direct"]["id"] == direct.pk
    assert by_name["helder"]["inherited_from"] == [
        {
            "scope_type": "project",
            "scope_id": tree["R"].pk,
            "scope_name": "R",
            "role": "viewer",
        }
    ]
    assert by_name["wsowner"]["direct"] is None
    assert by_name["wsowner"]["inherited_from"][0]["scope_type"] == "workspace"


def test_members_of_a_sub_project_are_not_listed_on_its_parent(tree, owner_api):
    grant(UserFactory(username="helder"), tree["A1"], "editor")

    members = owner_api.get(f"/api/memberships/?project={tree['A'].pk}").data

    assert [m["user"]["username"] for m in members] == ["wsowner"]


def test_listing_needs_exactly_one_scope(tree, owner_api):
    assert owner_api.get("/api/memberships/").status_code == 400


# --- Changing and removing ----------------------------------------------------------


def test_admin_can_change_and_remove_another_admin(tree, member, member_api):
    grant(member, tree["A"], "admin")
    other = grant(UserFactory(username="other"), tree["A"], "admin")

    changed = member_api.patch(
        f"/api/memberships/{other.pk}/", {"role": "viewer"}, format="json"
    )
    assert changed.status_code == 200
    other.refresh_from_db()
    assert other.role == "viewer"

    assert member_api.delete(f"/api/memberships/{other.pk}/").status_code == 204


def test_nobody_can_touch_the_owner_row_or_grant_owner(tree, member, member_api):
    grant(member, tree.workspace, "admin")
    owner_row = Membership.objects.get(workspace=tree.workspace, role="owner")
    other = grant(UserFactory(username="other"), tree.workspace, "viewer")

    assert (
        member_api.patch(
            f"/api/memberships/{owner_row.pk}/", {"role": "viewer"}, format="json"
        ).status_code
        == 403
    )
    assert member_api.delete(f"/api/memberships/{owner_row.pk}/").status_code == 403
    assert (
        member_api.patch(
            f"/api/memberships/{other.pk}/", {"role": "owner"}, format="json"
        ).status_code
        == 400
    )


def test_editor_cannot_manage_members(tree, member, member_api):
    grant(member, tree["A"], "editor")
    other = grant(UserFactory(username="other"), tree["A"], "viewer")

    assert (
        member_api.patch(
            f"/api/memberships/{other.pk}/", {"role": "admin"}, format="json"
        ).status_code
        == 403
    )
    assert member_api.delete(f"/api/memberships/{other.pk}/").status_code == 403


def test_anyone_can_leave_except_the_owner(tree, member, member_api, owner_api):
    mine = grant(member, tree["A"], "viewer")
    owner_row = Membership.objects.get(workspace=tree.workspace, role="owner")

    assert member_api.delete(f"/api/memberships/{mine.pk}/").status_code == 204
    assert owner_api.delete(f"/api/memberships/{owner_row.pk}/").status_code == 403


def test_membership_of_an_invisible_scope_is_a_404(tree, member_api):
    hidden = grant(UserFactory(username="other"), tree["A"], "viewer")

    assert member_api.delete(f"/api/memberships/{hidden.pk}/").status_code == 404
