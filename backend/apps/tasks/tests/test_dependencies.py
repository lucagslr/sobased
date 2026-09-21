"""`blocked_by`: same root project, no cycles, nothing leaks (SPEC §7)."""

import pytest

from apps.tasks import services

from .conftest import TaskFactory, client_for

pytestmark = pytest.mark.django_db


def block(client, task, *blockers):
    return client.patch(
        f"/api/tasks/{task.pk}/",
        {"blocked_by": [b.pk for b in blockers]},
        format="json",
    )


def test_blocked_until_every_blocker_is_closed(tree, editor_api):
    shooting = TaskFactory(project=tree["A1x"], title="Tournage")
    editing = TaskFactory(project=tree["A1"], title="Montage")

    response = block(editor_api, editing, shooting)

    assert response.status_code == 200
    assert response.data["is_blocked"] is True
    assert response.data["blockers"] == [
        {
            "id": shooting.pk,
            "visible": True,
            "title": "Tournage",
            "status": "todo",
            "project_name": "A1x",
            "is_open": True,
        }
    ]
    for closed in ("done", "cancelled"):
        shooting.status = closed
        shooting.save()
        assert editor_api.get(f"/api/tasks/{editing.pk}/").data["is_blocked"] is False


def test_a_blocker_must_share_the_root_project(tree, editor_api, editor):
    from apps.projects.tests.factories import grant

    grant(editor, tree["R2"], "editor")
    task = TaskFactory(project=tree["A"])
    elsewhere = TaskFactory(project=tree["R2"])

    response = block(editor_api, task, elsewhere)

    assert response.status_code == 400
    assert "projet racine" in str(response.data["blocked_by"])


@pytest.mark.parametrize("length", [1, 2, 4])
def test_cycles_are_refused_whatever_their_length(tree, editor_api, length):
    """t0 <- t1 <- ... <- tn, then trying to make t0 blocked by tn."""
    chain = [TaskFactory(project=tree["A"]) for _ in range(length + 1)]
    for blocked, blocker in zip(chain[1:], chain[:-1]):
        blocked.blocked_by.add(blocker)  # chain[i+1] waits for chain[i]

    response = block(editor_api, chain[0], chain[-1])

    assert response.status_code == 400
    assert "boucle" in str(response.data["blocked_by"])
    assert not chain[0].blocked_by.exists()


def test_a_task_cannot_block_itself(tree, editor_api):
    task = TaskFactory(project=tree["A"])

    assert block(editor_api, task, task).status_code == 400


def test_a_diamond_is_not_a_cycle(tree, editor_api):
    top, left, right, bottom = (TaskFactory(project=tree["A"]) for _ in range(4))
    left.blocked_by.add(top)
    right.blocked_by.add(top)

    assert block(editor_api, bottom, left, right).status_code == 200
    assert not services.would_create_cycle(bottom, top)


def test_blockers_can_be_set_at_creation(tree, editor_api):
    blocker = TaskFactory(project=tree["A"])

    response = editor_api.post(
        "/api/tasks/",
        {"project": tree["B"].pk, "title": "Après", "blocked_by": [blocker.pk]},
        format="json",
    )

    assert response.status_code == 201 and response.data["is_blocked"] is True


def test_an_invisible_blocker_shows_only_a_padlock(tree, make_member):
    """The guest of A1 sees that the task is blocked, not by what."""
    secret = TaskFactory(project=tree["B"], title="Négociation confidentielle")
    task = TaskFactory(project=tree["A1"])
    task.blocked_by.add(secret)
    client = client_for(make_member("guest", "editor", scope="A1"))

    data = client.get(f"/api/tasks/{task.pk}/").data

    assert data["is_blocked"] is True
    assert data["blockers"] == [
        {
            "id": secret.pk,
            "visible": False,
            "title": None,
            "status": None,
            "project_name": None,
            "is_open": True,
        }
    ]


def test_cannot_pick_a_blocker_i_cannot_see(tree, make_member):
    secret = TaskFactory(project=tree["B"])
    task = TaskFactory(project=tree["A1"])
    client = client_for(make_member("guest", "editor", scope="A1"))

    assert block(client, task, secret).status_code == 400


def test_candidates_are_visible_same_root_and_cycle_free(tree, editor_api, editor):
    from apps.projects.tests.factories import grant

    grant(editor, tree["R2"], "editor")
    task = TaskFactory(project=tree["A"], title="Cible")
    waiting = TaskFactory(project=tree["A"], title="Attend la cible")
    waiting.blocked_by.add(task)  # picking it would close a loop
    already = TaskFactory(project=tree["A"], title="Déjà bloqueur")
    task.blocked_by.add(already)
    TaskFactory(project=tree["B"], title="Mixage voix")
    TaskFactory(project=tree["A1x"], title="Mixage instru")
    TaskFactory(project=tree["R2"], title="Mixage autre racine")

    found = editor_api.get(f"/api/tasks/blocker-candidates/?task={task.pk}&q=mixage")
    everything = editor_api.get(f"/api/tasks/blocker-candidates/?task={task.pk}")

    assert sorted(c["title"] for c in found.data) == ["Mixage instru", "Mixage voix"]
    assert "Attend la cible" not in [c["title"] for c in everything.data]
    assert "Déjà bloqueur" not in [c["title"] for c in everything.data]


def test_candidates_never_include_invisible_tasks(tree, make_member):
    task = TaskFactory(project=tree["A1"])
    TaskFactory(project=tree["B"], title="Secret")
    TaskFactory(project=tree["A1x"], title="Visible")
    client = client_for(make_member("guest", "editor", scope="A1"))

    found = client.get(f"/api/tasks/blocker-candidates/?task={task.pk}").data

    assert [c["title"] for c in found] == ["Visible"]
