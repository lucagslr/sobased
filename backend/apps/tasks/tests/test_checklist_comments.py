"""Checklists, pinned todos, comments, mentions, and decision D6 (the assignee
may update the status and tick the checklist of THEIR tasks as a Commenter)."""

import pytest
from django.core import mail

from apps.tasks import services
from apps.tasks.models import ChecklistItem, TaskComment

from .conftest import TaskFactory, client_for

pytestmark = pytest.mark.django_db


# --- Decision D6 --------------------------------------------------------------------


@pytest.fixture
def assigned(tree, make_member):
    """(task, helder): helder is a COMMENTER of A and is assigned to the task."""
    helder = make_member("helder", "commenter", scope="A")
    task = TaskFactory(project=tree["A"])
    task.assignees.add(helder)
    ChecklistItem.objects.create(task=task, title="Exporter les stems")
    return task, helder


def test_assignee_commenter_can_change_the_status_only(assigned):
    task, helder = assigned
    client = client_for(helder)
    url = f"/api/tasks/{task.pk}/"

    assert client.patch(url, {"status": "done"}, format="json").status_code == 200
    assert client.patch(url, {"title": "Renommée"}, format="json").status_code == 403
    assert (
        client.patch(url, {"status": "todo", "priority": 5}, format="json").status_code
        == 403
    )
    assert client.delete(url).status_code == 403
    move = client.post(f"{url}move/", {"status": "todo", "position": 0}, format="json")
    assert move.status_code == 200


def test_assignee_commenter_can_tick_but_not_edit_the_checklist(assigned):
    task, helder = assigned
    client = client_for(helder)
    item = task.checklist.get()
    url = f"/api/checklist-items/{item.pk}/"

    ticked = client.patch(url, {"done": True}, format="json")
    assert ticked.status_code == 200 and ticked.data["done_at"] is not None
    item.refresh_from_db()
    assert item.done_by == helder

    assert client.patch(url, {"title": "Autre"}, format="json").status_code == 403
    assert client.patch(url, {"pinned": True}, format="json").status_code == 403
    assert client.delete(url).status_code == 403
    assert (
        client.post(f"/api/checklist-items/?task={task.pk}", {"title": "x"}).status_code
        == 403
    )


def test_the_shortcut_needs_both_the_assignment_and_the_commenter_role(
    tree, make_member, assigned
):
    task, _ = assigned
    bystander = client_for(make_member("bystander", "commenter", scope="A"))
    viewer = make_member("reader", "viewer", scope="A")
    task.assignees.add(viewer)
    url = f"/api/tasks/{task.pk}/"

    assert bystander.patch(url, {"status": "done"}, format="json").status_code == 403
    assert (
        client_for(viewer).patch(url, {"status": "done"}, format="json").status_code
        == 403
    )


# --- Checklist ----------------------------------------------------------------------


def test_checklist_crud_and_order(tree, editor_api):
    task = TaskFactory(project=tree["A"])
    url = f"/api/checklist-items/?task={task.pk}"

    first = editor_api.post(url, {"title": "Réserver le studio"}, format="json")
    second = editor_api.post(
        url, {"title": "Payer l'acompte", "pinned": True}, format="json"
    )

    assert (first.status_code, second.status_code) == (201, 201)
    assert [i["position"] for i in editor_api.get(url).data] == [0, 1]
    detail = editor_api.get(f"/api/tasks/{task.pk}/").data
    assert [i["title"] for i in detail["checklist"]] == [
        "Réserver le studio",
        "Payer l'acompte",
    ]

    item_url = f"/api/checklist-items/{first.data['id']}/"
    assert (
        editor_api.patch(item_url, {"done": True}, format="json").data["done"] is True
    )
    unticked = editor_api.patch(item_url, {"done": False}, format="json")
    assert unticked.data["done_at"] is None
    assert editor_api.delete(item_url).status_code == 204


def test_pinned_items_feed_the_dashboard_widget(tree, editor_api, make_member):
    open_task = TaskFactory(project=tree["A"], title="Clip")
    done_task = TaskFactory(project=tree["A"], status="done")
    hidden_task = TaskFactory(project=tree["Z"])
    wanted = ChecklistItem.objects.create(task=open_task, title="Valider", pinned=True)
    ChecklistItem.objects.create(task=open_task, title="Coché", pinned=True, done=True)
    ChecklistItem.objects.create(task=open_task, title="Pas épinglé")
    ChecklistItem.objects.create(task=done_task, title="Tâche finie", pinned=True)
    ChecklistItem.objects.create(task=hidden_task, title="Invisible", pinned=True)

    data = editor_api.get("/api/checklist-items/?pinned=true").data

    assert [item["id"] for item in data] == [wanted.pk]
    assert (data[0]["task_title"], data[0]["project_name"]) == ("Clip", "A")
    in_b = editor_api.get(f"/api/checklist-items/?pinned=true&project={tree['B'].pk}")
    assert in_b.data == []


def test_checklist_of_an_invisible_task_is_a_404(tree, make_member):
    task = TaskFactory(project=tree["B"])
    item = ChecklistItem.objects.create(task=task, title="Secret")
    client = client_for(make_member("guest", "editor", scope="A1"))

    assert client.get(f"/api/checklist-items/?task={task.pk}").data == []
    assert (
        client.patch(f"/api/checklist-items/{item.pk}/", {"done": True}).status_code
        == 404
    )
    assert (
        client.post(f"/api/checklist-items/?task={task.pk}", {"title": "x"}).status_code
        == 404
    )


# --- Comments and mentions ----------------------------------------------------------


def test_commenting_needs_the_commenter_role(tree, make_member):
    task = TaskFactory(project=tree["A"])
    url = f"/api/task-comments/?task={task.pk}"

    viewer = client_for(make_member("reader", "viewer"))
    commenter = client_for(make_member("helder", "commenter"))

    assert viewer.post(url, {"body": "Top"}, format="json").status_code == 403
    created = commenter.post(url, {"body": "Top"}, format="json")
    assert created.status_code == 201
    assert created.data["author"]["username"] == "helder"
    assert created.data["is_mine"] is True
    assert viewer.get(url).data[0]["is_mine"] is False
    assert commenter.post(url, {"body": "   "}, format="json").status_code == 400


def test_only_the_author_edits_and_an_admin_may_delete(tree, make_member):
    task = TaskFactory(project=tree["A"])
    author = make_member("helder", "commenter")
    comment = TaskComment.objects.create(task=task, author=author, body="v1")
    url = f"/api/task-comments/{comment.pk}/"
    editor = client_for(make_member("other", "editor"))
    admin = client_for(make_member("boss", "admin"))

    assert editor.patch(url, {"body": "hack"}, format="json").status_code == 403
    assert editor.delete(url).status_code == 403
    assert admin.patch(url, {"body": "hack"}, format="json").status_code == 403

    edited = client_for(author).patch(url, {"body": "v2"}, format="json")
    assert edited.data["edited_at"] is not None
    assert admin.delete(url).status_code == 204


def test_mentions_notify_members_only(tree, editor_api, make_member):
    helder = make_member("helder", "viewer")
    quiet = make_member("quiet", "viewer")
    quiet.email_on_mention = False
    quiet.save()
    make_member("outsider", "editor", scope="R2")  # not a member of A
    task = TaskFactory(project=tree["A"], title="Cover")

    editor_api.post(
        f"/api/task-comments/?task={task.pk}",
        {"body": "@Helder @quiet @outsider @ghost et @editor : avis ? mail@helder.ch"},
        format="json",
    )

    assert [m.to for m in mail.outbox] == [[helder.email]]
    assert "Cover" in mail.outbox[0].subject


@pytest.mark.parametrize(
    "body, expected",
    [
        ("Salut @helder.", ["helder"]),
        ("(@helder) et @HELDER", ["helder"]),
        ("helder@exemple.ch", []),  # an e-mail address is not a mention
        ("@he", []),  # too short to be a username
        ("", []),
    ],
)
def test_mention_parsing(tree, make_member, body, expected):
    make_member("helder", "viewer")

    found = services.mentioned_users(body, tree["A"])

    assert [user.username for user in found] == expected
