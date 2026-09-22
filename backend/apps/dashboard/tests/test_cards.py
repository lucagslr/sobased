"""Cards mode of the Projects page: GET /api/projects/cards/.

Reference tree (apps/projects/tests/factories.py):
W: R > (A > (A1 > A1x, A2), B), R2      W2: Z
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.dashboard.serializers import CardEntrySerializer, ProjectCardSerializer
from apps.projects.models import Project
from apps.projects.tests.factories import ProjectFactory, Tree, grant
from apps.tasks.models import TaskSeries
from apps.tasks.tests.conftest import TaskFactory, client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree():
    tree = Tree()
    # A new project is "planned"; without a start date that means "upcoming".
    # These tests want a tree that is under way.
    Project.objects.update(status="in_progress")
    for node in tree.nodes.values():
        node.refresh_from_db()
    return tree


@pytest.fixture
def editor(tree):
    user = UserFactory(username="editor")
    grant(user, tree["R"], "editor")
    return user


@pytest.fixture
def api(editor):
    return client_for(editor)


def local_date(user, offset=0):
    return datetime.now(ZoneInfo(user.timezone)).date() + timedelta(days=offset)


def day(user, offset=0):
    """An all-day date `offset` days from the USER's today (midnight UTC)."""
    target = local_date(user, offset)
    return datetime(target.year, target.month, target.day, tzinfo=UTC)


def cards(client, query=""):
    response = client.get(f"/api/projects/cards/{query}")
    assert response.status_code == 200
    return {card["name"]: card for card in response.data}


def names(entries):
    return [entry["name"] for entry in entries]


# --- Shape and routing ----------------------------------------------------------------


def test_route_is_not_swallowed_by_the_project_detail_route(api):
    # /api/projects/<pk>/ would answer 404 for pk="cards".
    assert api.get("/api/projects/cards/").status_code == 200


def test_response_matches_its_documented_shape(tree, api):
    card = cards(api)["R"]

    assert set(card) == set(ProjectCardSerializer().fields)
    assert set(card["current"][0]) == set(CardEntrySerializer().fields)


def test_anonymous_is_rejected(tree):
    from rest_framework.test import APIClient

    assert APIClient().get("/api/projects/cards/").status_code == 401


# --- Content ------------------------------------------------------------------------


def test_one_card_per_root_project_with_its_direct_children(tree, editor, api):
    result = cards(api)

    # The editor of R sees neither R2 nor Z (no membership there).
    assert list(result) == ["R"]
    card = result["R"]
    assert card["is_shell"] is False
    assert names(card["current"]) == ["A", "B"]
    assert card["past"] == [] and card["upcoming"] == []
    assert {e["name"]: e["children_count"] for e in card["current"]} == {"A": 2, "B": 0}


def test_children_are_sorted_into_past_current_upcoming(tree, editor, api):
    a, b = tree["A"], tree["B"]
    a.status = "done"
    a.save()
    b.start_date = local_date(editor, 10)
    b.save()
    a2 = tree["A2"]  # depth 3: never listed on the card of R

    result = cards(api)["R"]

    assert names(result["past"]) == ["A"]
    assert names(result["upcoming"]) == ["B"]
    assert result["current"] == []
    assert a2.name not in names(result["past"] + result["upcoming"])


def test_columns_are_ordered_by_date_undated_last(tree, editor, api):
    def child(name, status="in_progress", **fields):
        return ProjectFactory(
            workspace=tree.workspace,
            parent=tree["R2"],
            name=name,
            status=status,
            **fields,
        )

    grant(editor, tree["R2"], "editor")
    child("soon", end_date=local_date(editor, 3))
    child("later", end_date=local_date(editor, 30))
    child("undated")
    child("old", status="done", end_date=local_date(editor, -300))
    child("recent", status="done", end_date=local_date(editor, -3))
    child("next", status="planned", start_date=local_date(editor, 5))
    child("far", status="planned", start_date=local_date(editor, 90))
    child("idea", status="idea")

    card = cards(api)["R2"]

    assert names(card["current"]) == ["soon", "later", "undated"]
    assert names(card["past"]) == ["recent", "old"]
    assert names(card["upcoming"]) == ["next", "far", "idea"]


def test_archived_projects_and_their_branch_are_left_out(tree, editor, api):
    tree["A"].status = "archived"
    tree["A"].save()
    TaskFactory(project=tree["A1"], due_at=day(editor, -1))  # below the archive

    card = cards(api)["R"]

    assert names(card["current"]) == ["B"]
    assert card["tasks_total"] == 0 and card["tasks_overdue"] == 0


def test_an_end_date_in_the_past_is_flagged(tree, editor, api):
    tree["B"].end_date = local_date(editor, -1)
    tree["B"].save()

    card = cards(api)["R"]

    flags = {e["name"]: e["end_overdue"] for e in card["current"]}
    assert flags == {"A": False, "B": True}


# --- Task counts --------------------------------------------------------------------


def test_counts_roll_up_from_sub_projects(tree, editor, api):
    TaskFactory(project=tree["R"], status="done")
    TaskFactory(project=tree["A"], due_at=day(editor, -2))  # late
    TaskFactory(project=tree["A1x"], status="done")  # 3 levels below A
    TaskFactory(project=tree["A1x"], status="cancelled")  # never counted
    TaskFactory(project=tree["B"])

    card = cards(api)["R"]
    entries = {e["name"]: e for e in card["current"]}

    assert (card["tasks_total"], card["tasks_done"], card["tasks_overdue"]) == (4, 2, 1)
    assert (entries["A"]["tasks_total"], entries["A"]["tasks_done"]) == (2, 1)
    assert entries["A"]["tasks_overdue"] == 1
    assert (entries["B"]["tasks_total"], entries["B"]["tasks_done"]) == (1, 0)


def test_future_repetitions_do_not_dilute_the_progress(tree, editor, api):
    series = TaskSeries.objects.create(
        project=tree["B"],
        rrule="FREQ=WEEKLY",
        all_day=True,
        template={"title": "Point hebdo"},
        dtstart=day(editor, -7),
        generated_until=day(editor, 90),
    )

    def occurrence(offset, **fields):
        moment = day(editor, offset)
        TaskFactory(
            project=tree["B"],
            series=series,
            occurrence_at=moment,
            due_at=moment,
            **fields,
        )

    occurrence(-7, status="done")
    occurrence(0)
    for week in (1, 2, 3):
        occurrence(7 * week)

    entry = next(e for e in cards(api)["R"]["current"] if e["name"] == "B")

    # The past one and today's count; the three future ones do not.
    assert (entry["tasks_total"], entry["tasks_done"]) == (2, 1)


def test_next_due_is_the_closest_open_deadline_that_is_not_late(tree, editor, api):
    TaskFactory(project=tree["A"], title="en retard", due_at=day(editor, -1))
    TaskFactory(project=tree["A1"], title="fait", due_at=day(editor, 1), status="done")
    TaskFactory(project=tree["A1"], title="bientôt", due_at=day(editor, 2))
    TaskFactory(project=tree["B"], title="plus tard", due_at=day(editor, 9))

    card = cards(api)["R"]

    assert card["next_due"]["title"] == "bientôt"
    assert card["next_due"]["date"] == local_date(editor, 2).isoformat()
    assert card["next_due"]["project"] == tree["A1"].pk


def test_next_due_is_null_without_any_deadline(tree, api):
    assert cards(api)["R"]["next_due"] is None


# --- Rights --------------------------------------------------------------------------


def test_a_guest_of_a_sub_project_gets_a_shell_card_with_only_their_branch(tree):
    guest = UserFactory(username="guest")
    grant(guest, tree["A1"], "viewer")
    # Tasks the guest must never hear about, not even as a total.
    TaskFactory(project=tree["R"])
    TaskFactory(project=tree["A2"], due_at=day(guest, -1))
    TaskFactory(project=tree["B"], due_at=day(guest, 1))
    # Tasks of their own branch.
    TaskFactory(project=tree["A1"], status="done")
    TaskFactory(project=tree["A1x"], title="à moi", due_at=day(guest, 4))

    result = cards(client_for(guest))

    assert list(result) == ["R"]
    card = result["R"]
    assert card["is_shell"] is True
    # Nothing about the root itself beyond its name and colour.
    for field in ("type_name", "status", "start_date", "end_date", "temporal"):
        assert card[field] is None
    assert card["end_overdue"] is False
    # A (a shell too) is skipped: the entry is the first project they can open.
    assert names(card["current"]) == ["A1"]
    assert card["current"][0]["children_count"] == 1
    assert (card["tasks_total"], card["tasks_done"], card["tasks_overdue"]) == (2, 1, 0)
    assert card["next_due"]["title"] == "à moi"


def test_a_workspace_member_sees_every_root_of_the_workspace(tree):
    member = UserFactory(username="member")
    grant(member, tree.workspace, "viewer")

    assert list(cards(client_for(member))) == ["R", "R2"]


def test_workspace_filter(tree, editor):
    grant(editor, tree["Z"], "viewer")
    client = client_for(editor)

    assert sorted(cards(client)) == ["R", "Z"]
    assert list(cards(client, f"?workspace={tree.other_workspace.pk}")) == ["Z"]
    assert list(cards(client, f"?workspace={tree.workspace.pk}")) == ["R"]
    # A workspace I am not part of: nothing, and no error that would reveal it.
    assert cards(client, "?workspace=999999") == {}


def test_query_count_does_not_grow_with_the_tree(
    tree, editor, api, django_assert_max_num_queries
):
    for node in ("R", "A", "A1", "A1x", "A2", "B"):
        TaskFactory(project=tree[node], due_at=day(editor, 3))

    # session + user, access map (3), projects, counts, late counts, next due.
    with django_assert_max_num_queries(10):
        api.get("/api/projects/cards/")
