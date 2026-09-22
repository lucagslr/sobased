"""The bell: every event of SPECIFICATIONS §10 writes a row (never for
oneself), e-mails follow the table, the API is per user."""

import pytest
from django.core import mail

from apps.accounts.tests.factories import UserFactory
from apps.files.services import change_status
from apps.files.tests.conftest import make_asset
from apps.notifications.models import Notification
from apps.projects.tests.factories import Tree, grant
from apps.sharing.tests.conftest import create_link, token_of
from apps.tasks.tests.conftest import TaskFactory, client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree(db):
    return Tree()


@pytest.fixture
def editor(tree):
    user = UserFactory(username="editor")
    grant(user, tree.workspace, "editor")
    return user


@pytest.fixture
def editor_api(editor):
    return client_for(editor)


@pytest.fixture
def colleague(tree):
    user = UserFactory(username="colleague")
    grant(user, tree["A"], "editor")
    return user


def rows(user):
    return list(Notification.objects.filter(recipient=user))


# --- Events ---------------------------------------------------------------------------
def test_assignment_notifies_in_app_and_by_email_if_wanted(
    editor_api, editor, colleague, tree
):
    silent = UserFactory(username="silent", email_on_assignment=False)
    grant(silent, tree["A"], "commenter")
    response = editor_api.post(
        "/api/tasks/",
        {
            "project": tree["A"].pk,
            "title": "Brief",
            "assignee_usernames": ["colleague", "silent", "editor"],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert rows(editor) == []  # never oneself
    [colleague_row] = rows(colleague)
    assert colleague_row.kind == "assignment" and colleague_row.emailed_at is not None
    assert colleague_row.payload["title"] == "Brief"
    assert (
        colleague_row.url
        == f"/projets/{tree['A'].pk}/taches?tache={response.data['id']}"
    )
    [silent_row] = rows(silent)
    assert silent_row.emailed_at is None  # in-app only, as preferred
    assert [m.to for m in mail.outbox] == [[colleague.email]]


def test_mention_and_member_added(editor_api, editor, colleague, tree):
    task = TaskFactory(project=tree["A"], title="Mix")
    editor_api.post(
        f"/api/task-comments/?task={task.pk}",
        {"body": "@colleague tu regardes ?"},
        format="json",
    )
    [row] = rows(colleague)
    assert row.kind == "mention" and row.payload["excerpt"].startswith("@colleague")
    assert row.emailed_at is not None
    newcomer = UserFactory(username="newcomer")
    mail.outbox.clear()
    owner_api = client_for(tree.owner)  # adding members needs an admin
    response = owner_api.post(
        "/api/memberships/",
        {"project": tree["A"].pk, "username": "newcomer", "role": "viewer"},
        format="json",
    )
    assert response.status_code in (200, 201), response.data
    [added] = rows(newcomer)
    assert added.kind == "invitation" and added.payload["scope_name"] == "A"
    assert added.emailed_at is not None and len(mail.outbox) == 1


def test_asset_status_notifies_followers_only_in_app(editor, colleague, tree):
    asset = make_asset(tree["A"], editor, name="Cover")
    asset.followers.add(colleague)
    change_status(asset, "to_validate", editor, note="Prête")
    assert rows(editor) == []
    [row] = rows(colleague)
    assert row.kind == "asset_status" and row.payload["to_status"] == "to_validate"
    assert row.payload["note"] == "Prête" and row.emailed_at is None
    assert mail.outbox == []


def test_share_link_first_opening(editor_api, editor, tree):
    from django.test import Client

    asset = make_asset(tree["A"], editor, name="Cover")
    data = create_link(
        editor_api,
        target_type="asset",
        asset=asset.pk,
        notify_on_open=True,
        recipient_label="Radio X",
    )
    silent = create_link(editor_api, target_type="asset", asset=asset.pk)
    visitor = Client()
    assert visitor.get(f"/api/public/share/{token_of(data)}/").status_code == 200
    visitor.get(f"/api/public/share/{token_of(data)}/")  # same session: no second row
    Client().get(
        f"/api/public/share/{token_of(data)}/"
    )  # second opening: not the first
    Client().get(f"/api/public/share/{token_of(silent)}/")
    [row] = rows(editor)
    assert row.kind == "share_opened" and row.payload["recipient_label"] == "Radio X"
    assert row.url == f"/projets/{tree['A'].pk}/liens"


# --- API ------------------------------------------------------------------------------
def test_list_count_and_read(editor_api, editor, colleague, tree):
    api = client_for(colleague)
    for title in ("Un", "Deux", "Trois"):
        editor_api.post(
            "/api/tasks/",
            {
                "project": tree["A"].pk,
                "title": title,
                "assignee_usernames": ["colleague"],
            },
            format="json",
        )
    assert api.get("/api/notifications/unread-count/").data == {"unread": 3}
    listing = api.get("/api/notifications/").data["results"]
    assert [n["payload"]["title"] for n in listing] == ["Trois", "Deux", "Un"]
    assert (
        listing[0]["actor"]["username"] == "editor" and listing[0]["is_read"] is False
    )
    first = listing[0]["id"]
    assert api.post(f"/api/notifications/{first}/read/").data["is_read"] is True
    assert api.get("/api/notifications/unread-count/").data == {"unread": 2}
    unread = api.get("/api/notifications/", {"unread": "true"}).data["results"]
    assert len(unread) == 2
    assert api.post("/api/notifications/read-all/").status_code == 204
    assert api.get("/api/notifications/unread-count/").data == {"unread": 0}
    # Someone else's rows are invisible.
    assert editor_api.post(f"/api/notifications/{first}/read/").status_code == 404
    assert editor_api.get("/api/notifications/").data["results"] == []
