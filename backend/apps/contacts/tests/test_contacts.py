"""Contacts: who sees what, who may write, links to projects.

Reference tree (apps/projects/tests/factories.py):
W: R > (A > (A1 > A1x, A2), B), R2      W2: Z
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.contacts.models import Contact, ProjectContact
from apps.projects.tests.factories import TagFactory, Tree, grant

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree():
    return Tree()


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def member(tree, username, role, scope=None):
    user = UserFactory(username=username)
    grant(user, tree[scope] if scope else tree.workspace, role)
    return user


def contact(tree, last_name, workspace=None, **fields):
    return Contact.objects.create(
        workspace=workspace or tree.workspace, last_name=last_name, **fields
    )


def names(response):
    return sorted(item["last_name"] for item in response.data)


# --- Visibility -----------------------------------------------------------------------


def test_a_workspace_member_sees_the_whole_address_book(tree):
    contact(tree, "Booker")
    contact(tree, "Graphiste")
    contact(tree, "Ailleurs", workspace=tree.other_workspace)
    client = client_for(member(tree, "viewer", "viewer"))

    assert names(client.get("/api/contacts/")) == ["Booker", "Graphiste"]


def test_a_project_guest_only_sees_contacts_linked_to_their_projects(tree):
    linked = contact(tree, "Realisateur")
    below = contact(tree, "Monteur")
    elsewhere = contact(tree, "Booker")
    contact(tree, "Jamais lié")
    ProjectContact.objects.create(project=tree["A1"], contact=linked)
    ProjectContact.objects.create(project=tree["A1x"], contact=below)  # inherited
    ProjectContact.objects.create(project=tree["B"], contact=elsewhere)
    client = client_for(member(tree, "guest", "viewer", scope="A1"))

    assert names(client.get("/api/contacts/")) == ["Monteur", "Realisateur"]
    assert client.get(f"/api/contacts/{elsewhere.pk}/").status_code == 404


def test_a_guest_never_learns_about_links_to_projects_they_cannot_open(tree):
    shared = contact(tree, "Realisateur")
    ProjectContact.objects.create(project=tree["A1"], contact=shared, role_label="Clip")
    ProjectContact.objects.create(project=tree["B"], contact=shared, role_label="Live")
    client = client_for(member(tree, "guest", "viewer", scope="A1"))

    links = client.get(f"/api/contacts/{shared.pk}/").data["links"]

    assert [(link["project_name"], link["role_label"]) for link in links] == [
        ("A1", "Clip")
    ]


def test_strangers_and_anonymous(tree):
    contact(tree, "Booker")
    outsider = client_for(UserFactory(username="outsider"))

    assert outsider.get("/api/contacts/").data == []
    assert APIClient().get("/api/contacts/").status_code == 401


def test_filters(tree):
    urgent = TagFactory(workspace=tree.workspace, name="presse")
    booker = contact(tree, "Booker", job="Programmateur", organization="L'Usine")
    booker.tags.add(urgent)
    designer = contact(tree, "Graphiste", first_name="Lea", job="Graphiste")
    ProjectContact.objects.create(project=tree["A1"], contact=designer)
    client = client_for(member(tree, "viewer", "viewer"))

    get = client.get
    assert names(get(f"/api/contacts/?workspace={tree.workspace.pk}")) == [
        "Booker",
        "Graphiste",
    ]
    assert names(get(f"/api/contacts/?workspace={tree.other_workspace.pk}")) == []
    assert names(get(f"/api/contacts/?tag={urgent.pk}")) == ["Booker"]
    assert names(get("/api/contacts/?job=programmateur")) == ["Booker"]
    assert names(get("/api/contacts/?search=usine")) == ["Booker"]
    assert names(get("/api/contacts/?search=lea")) == ["Graphiste"]
    # A project filter includes its sub-projects.
    assert names(get(f"/api/contacts/?project={tree['A'].pk}")) == ["Graphiste"]
    assert names(get(f"/api/contacts/?project={tree['B'].pk}")) == []


# --- Writing --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role, expected",
    [("viewer", 403), ("commenter", 403), ("editor", 201), ("admin", 201)],
)
def test_creating_in_a_workspace_needs_the_editor_role(tree, role, expected):
    client = client_for(member(tree, "someone", role))

    response = client.post(
        "/api/contacts/",
        {"workspace": tree.workspace.pk, "last_name": "Booker"},
        format="json",
    )

    assert response.status_code == expected


def test_a_project_editor_adds_a_contact_through_their_project(tree):
    guest = member(tree, "guest", "editor", scope="A1")
    client = client_for(guest)

    # Not through the workspace: they are not a member of it.
    refused = client.post(
        "/api/contacts/",
        {"workspace": tree.workspace.pk, "last_name": "Monteur"},
        format="json",
    )
    created = client.post(
        "/api/contacts/",
        {
            "project": tree["A1"].pk,
            "role_label": "Monteur du clip",
            "first_name": "Sam",
            "last_name": "Monteur",
            "instagram": "@sam.cuts",
        },
        format="json",
    )

    assert refused.status_code == 403
    assert created.status_code == 201
    saved = Contact.objects.get(pk=created.data["id"])
    assert saved.workspace == tree.workspace and saved.created_by == guest
    assert saved.instagram == "sam.cuts"
    assert created.data["display_name"] == "Sam Monteur"
    assert created.data["links"][0]["role_label"] == "Monteur du clip"
    assert created.data["can_edit"] is True
    # The creator may fix a typo later, a fellow guest may not.
    assert (
        client.patch(
            f"/api/contacts/{saved.pk}/", {"phone": "079"}, format="json"
        ).status_code
        == 200
    )
    other = client_for(member(tree, "other", "editor", scope="A1"))
    assert other.get(f"/api/contacts/{saved.pk}/").data["can_edit"] is False
    assert (
        other.patch(
            f"/api/contacts/{saved.pk}/", {"phone": "078"}, format="json"
        ).status_code
        == 403
    )


def test_creating_through_a_project_needs_editor_on_that_project(tree):
    commenter = client_for(member(tree, "commenter", "commenter", scope="A1"))
    editor = client_for(member(tree, "guest", "editor", scope="A1"))

    def post(client, scope):
        return client.post(
            "/api/contacts/",
            {"project": tree[scope].pk, "last_name": "X"},
            format="json",
        )

    assert post(commenter, "A1").status_code == 403
    # B (another branch), A (a shell) and Z (another workspace) do not exist
    # for a guest of A1: same answer for the three.
    for scope in ("B", "A", "Z"):
        assert post(editor, scope).status_code == 400
    assert not Contact.objects.exists()


def test_validation(tree):
    client = client_for(member(tree, "editor", "editor"))
    foreign_tag = TagFactory(workspace=tree.other_workspace)

    def post(**fields):
        return client.post(
            "/api/contacts/", {"workspace": tree.workspace.pk, **fields}, format="json"
        )

    assert post(job="Graphiste").status_code == 400  # no name, no organization
    assert post(organization="L'Usine").status_code == 201  # a venue is a contact
    assert post(last_name="X", tags=[foreign_tag.pk]).status_code == 400
    assert post(last_name="X", email="pas-un-email").status_code == 400
    assert client.post("/api/contacts/", {"last_name": "X"}).status_code == 400


def test_a_contact_never_changes_workspace(tree):
    editor = member(tree, "editor", "editor")
    grant(editor, tree.other_workspace, "editor")
    booker = contact(tree, "Booker")

    client_for(editor).patch(
        f"/api/contacts/{booker.pk}/",
        {"workspace": tree.other_workspace.pk},
        format="json",
    )

    booker.refresh_from_db()
    assert booker.workspace == tree.workspace


def test_deleting_needs_the_editor_role(tree):
    booker = contact(tree, "Booker")
    viewer = client_for(member(tree, "viewer", "viewer"))
    editor = client_for(member(tree, "editor", "editor"))

    assert viewer.delete(f"/api/contacts/{booker.pk}/").status_code == 403
    assert editor.delete(f"/api/contacts/{booker.pk}/").status_code == 204


# --- Links contact <-> project --------------------------------------------------------


def test_linking_a_contact_to_a_project(tree):
    booker = contact(tree, "Booker")
    client = client_for(member(tree, "editor", "editor"))

    created = client.post(
        "/api/project-contacts/",
        {"project": tree["B"].pk, "contact": booker.pk, "role_label": "Programmateur"},
        format="json",
    )
    again = client.post(
        "/api/project-contacts/",
        {"project": tree["B"].pk, "contact": booker.pk},
        format="json",
    )

    assert created.status_code == 201
    assert created.data["contact_detail"]["last_name"] == "Booker"
    assert again.status_code == 400  # already linked
    listed = client.get(f"/api/project-contacts/?project={tree['B'].pk}")
    assert [link["role_label"] for link in listed.data] == ["Programmateur"]
    # Seen from the parent project too, on request.
    assert client.get(f"/api/project-contacts/?project={tree['R'].pk}").data == []
    below = client.get(
        f"/api/project-contacts/?project={tree['R'].pk}&include_descendants=true"
    )
    assert len(below.data) == 1


def test_link_rights(tree):
    booker = contact(tree, "Booker")
    foreign = contact(tree, "Ailleurs", workspace=tree.other_workspace)
    link = ProjectContact.objects.create(project=tree["A1"], contact=booker)
    viewer = client_for(member(tree, "viewer", "viewer", scope="A1"))
    editor = client_for(member(tree, "guest", "editor", scope="A1"))

    def post(client, project, contact_id):
        return client.post(
            "/api/project-contacts/",
            {"project": tree[project].pk, "contact": contact_id},
            format="json",
        )

    assert post(viewer, "A1x", booker.pk).status_code == 403
    assert post(editor, "A1x", booker.pk).status_code == 201  # a contact they see
    assert post(editor, "B", booker.pk).status_code == 404  # not their project
    assert post(editor, "A1", foreign.pk).status_code == 400  # another workspace
    hidden = contact(tree, "Invisible")  # in the workspace, linked nowhere
    assert post(editor, "A1", hidden.pk).status_code == 400
    assert (
        viewer.patch(
            f"/api/project-contacts/{link.pk}/", {"role_label": "x"}, format="json"
        ).status_code
        == 403
    )
    assert (
        editor.patch(
            f"/api/project-contacts/{link.pk}/", {"role_label": "Real"}, format="json"
        ).status_code
        == 200
    )
    assert editor.delete(f"/api/project-contacts/{link.pk}/").status_code == 204
    # Unlinking does not delete the contact.
    assert Contact.objects.filter(pk=booker.pk).exists()
