"""The "fin dépassée" queue (SPEC §5): who is asked, about what, until when."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.projects.models import ProjectUserState

from .factories import grant

pytestmark = pytest.mark.django_db


def today_of(user):
    return datetime.now(ZoneInfo(user.timezone)).date()


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def expire(project, days_ago, status="in_progress"):
    project.end_date = today_of(UserFactory.build()) - timedelta(days=days_ago)
    project.status = status
    project.save()


def queue(client):
    response = client.get("/api/projects/overdue/")
    assert response.status_code == 200
    return [item["name"] for item in response.data]


def test_queue_lists_open_projects_past_their_end_oldest_first(tree, owner_api):
    expire(tree["A"], 3)
    expire(tree["A1x"], 10)  # a level-4 sub-project counts too
    expire(tree["B"], 0)  # ends today: not late yet
    expire(tree["R2"], 5, status="done")
    expire(tree["A2"], 5, status="archived")

    response = owner_api.get("/api/projects/overdue/")

    assert [item["name"] for item in response.data] == ["A1x", "A"]
    assert set(response.data[0]) == {"id", "name", "color", "end_date", "status"}


@pytest.mark.parametrize(
    "role, asked", [("viewer", False), ("commenter", False), ("editor", True)]
)
def test_only_people_who_may_edit_are_asked(tree, member, member_api, role, asked):
    expire(tree["A"], 3)
    grant(member, tree["A"], role)

    assert queue(member_api) == (["A"] if asked else [])


def test_a_shell_is_never_in_the_queue(tree, member, member_api):
    expire(tree["A"], 3)
    expire(tree["A1"], 3)
    grant(member, tree["A1"], "admin")  # A is only a shell for them

    assert queue(member_api) == ["A1"]


def test_remind_me_tomorrow_is_personal_and_lasts_one_day(tree, member, member_api):
    expire(tree["A"], 3)
    grant(member, tree["R"], "editor")
    other = client_for(tree.owner)

    response = member_api.post(f"/api/projects/{tree['A'].pk}/snooze-overdue/")

    assert response.status_code == 204
    assert queue(member_api) == []
    assert queue(other) == ["A"]  # the owner has not answered
    # The next day, the question comes back.
    ProjectUserState.objects.filter(user=member).update(
        overdue_snoozed_until=today_of(member) - timedelta(days=1)
    )
    assert queue(member_api) == ["A"]


def test_snoozing_twice_keeps_a_single_row(tree, owner_api):
    expire(tree["A"], 3)
    url = f"/api/projects/{tree['A'].pk}/snooze-overdue/"

    assert owner_api.post(url).status_code == 204
    assert owner_api.post(url).status_code == 204
    assert ProjectUserState.objects.count() == 1


def test_marking_done_or_rescheduling_answers_for_everybody(tree, member, member_api):
    expire(tree["A"], 3)
    expire(tree["B"], 3)
    grant(member, tree["R"], "editor")
    other = client_for(tree.owner)

    member_api.patch(
        f"/api/projects/{tree['A'].pk}/", {"status": "done"}, format="json"
    )
    new_end = (today_of(member) + timedelta(days=30)).isoformat()
    member_api.patch(
        f"/api/projects/{tree['B'].pk}/", {"end_date": new_end}, format="json"
    )

    assert queue(member_api) == []
    assert queue(other) == []


def test_snooze_needs_the_editor_role(tree, member, member_api):
    expire(tree["A"], 3)
    url = f"/api/projects/{tree['A'].pk}/snooze-overdue/"

    assert member_api.post(url).status_code == 404  # not visible at all
    grant(member, tree["A"], "commenter")
    assert member_api.post(url).status_code == 403


def test_queue_requires_authentication():
    assert APIClient().get("/api/projects/overdue/").status_code == 401
