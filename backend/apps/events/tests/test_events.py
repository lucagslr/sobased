"""Events and meetings: rights, validation, participants, minutes, filters,
the link task <-> meeting, and what the dashboards show.

Reference tree (apps/projects/tests/factories.py):
W: R > (A > (A1 > A1x, A2), B), R2      W2: Z
"""

from datetime import UTC, datetime, timedelta

import pytest

from apps.contacts.models import Contact, ProjectContact
from apps.events.models import Event
from apps.projects.tests.factories import TagFactory
from apps.tasks.tests.conftest import client_for, day, iso

pytestmark = pytest.mark.django_db


def at(days: int, hour: int = 10) -> datetime:
    """`hour` o'clock (UTC), `days` from today. Built on day() so that timed
    and all-day dates of a test share the same "today", even around midnight."""
    return day(days) + timedelta(hours=hour)


def make_event(project, title="RDV", start=None, **fields):
    start = start or at(1)
    fields.setdefault("end", start + timedelta(hours=1))
    return Event.objects.create(project=project, title=title, start=start, **fields)


def create(client, project, **fields):
    payload = {"project": project.pk, "title": "RDV label", "start": iso(at(2))}
    return client.post("/api/events/", {**payload, **fields}, format="json")


def titles(response):
    return sorted(event["title"] for event in response.data["results"])


# --- Rights ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role, expected",
    [("viewer", 403), ("commenter", 403), ("editor", 201), ("admin", 201)],
)
def test_creating_needs_the_editor_role(tree, make_member, role, expected):
    client = client_for(make_member("someone", role))

    assert create(client, tree["A"]).status_code == expected


def test_events_of_invisible_projects_do_not_exist(tree, make_member):
    hidden = make_event(tree["B"])
    shown = make_event(tree["A1x"], title="visible")
    client = client_for(make_member("guest", "editor", scope="A1"))

    assert titles(client.get("/api/events/")) == ["visible"]
    assert client.get(f"/api/events/{hidden.pk}/").status_code == 404
    assert client.get(f"/api/events/{shown.pk}/").status_code == 200
    # A shell (A) or another branch (B): creating there answers "not found".
    assert create(client, tree["A"]).status_code == 404
    assert create(client, tree["B"]).status_code == 404


def test_viewer_reads_everything_but_changes_nothing(tree, make_member):
    event = make_event(tree["A"], report="On sort le 12.10", decisions=["Master v3"])
    client = client_for(make_member("viewer", "viewer"))

    shown = client.get(f"/api/events/{event.pk}/")

    assert shown.data["report"] == "On sort le 12.10"
    assert shown.data["decisions"] == ["Master v3"]
    assert (
        client.patch(
            f"/api/events/{event.pk}/", {"report": "x"}, format="json"
        ).status_code
        == 403
    )
    assert client.delete(f"/api/events/{event.pk}/").status_code == 403


# --- Creation and validation ----------------------------------------------------------


def test_create_with_defaults(tree, editor_api, editor):
    response = create(editor_api, tree["A"])

    assert response.status_code == 201
    data = response.data
    assert data["type"] == "meeting" and data["all_day"] is False
    assert data["project_name"] == "A" and data["project_color"]
    event = Event.objects.get(pk=data["id"])
    assert event.end - event.start == timedelta(hours=1)  # SPECIFICATIONS §4
    assert event.created_by == editor
    assert data["participants"] == [] and data["contact_details"] == []
    assert data["decisions"] == [] and data["tasks"] == []
    assert data["recurrence"] is None


def test_an_all_day_event_defaults_to_a_single_day(tree, editor_api):
    response = create(editor_api, tree["A"], start=iso(day(3)), all_day=True)

    event = Event.objects.get(pk=response.data["id"])
    assert event.start == event.end == day(3)


def test_end_cannot_precede_start(tree, editor_api):
    response = create(editor_api, tree["A"], start=iso(at(2, 14)), end=iso(at(2, 13)))
    event = make_event(tree["A"])
    moved = editor_api.patch(
        f"/api/events/{event.pk}/",
        {"end": iso(event.start - timedelta(minutes=1))},
        format="json",
    )

    assert response.status_code == 400 and "end" in response.data
    assert moved.status_code == 400


def test_moving_the_start_alone_keeps_the_duration(tree, editor_api):
    event = make_event(tree["A"], start=at(2, 10), end=at(2, 12))

    response = editor_api.patch(
        f"/api/events/{event.pk}/", {"start": iso(at(3, 15))}, format="json"
    )

    assert response.status_code == 200
    event.refresh_from_db()
    assert (event.start, event.end) == (at(3, 15), at(3, 17))


def test_invalid_fields(tree, editor_api):
    foreign_tag = TagFactory(workspace=tree.other_workspace)

    assert create(editor_api, tree["A"], title="").status_code == 400
    assert create(editor_api, tree["A"], type="apero").status_code == 400
    assert create(editor_api, tree["A"], tags=[foreign_tag.pk]).status_code == 400
    assert create(editor_api, tree["A"], decisions=["x" * 501]).status_code == 400
    assert create(editor_api, tree["A"], rrule="FREQ=HOURLY").status_code == 400


def test_an_event_never_changes_project(tree, editor_api):
    event = make_event(tree["A"])

    editor_api.patch(
        f"/api/events/{event.pk}/", {"project": tree["B"].pk}, format="json"
    )

    event.refresh_from_db()
    assert event.project == tree["A"]


def test_decisions_are_a_clean_ordered_list(tree, editor_api):
    event = make_event(tree["A"])

    response = editor_api.patch(
        f"/api/events/{event.pk}/",
        {"decisions": ["  Sortie le 12.10 ", "   ", "Budget clip : 3000"]},
        format="json",
    )

    assert response.data["decisions"] == ["Sortie le 12.10", "Budget clip : 3000"]


# --- Participants: members of the project, and contacts -------------------------------


def test_participants_must_be_members_of_the_project(tree, editor_api, make_member):
    make_member("helder", "viewer", scope="A1")
    make_member("stranger", "viewer", scope="B")

    ok = create(editor_api, tree["A1"], participant_usernames=["@Helder", "editor"])
    refused = create(editor_api, tree["A1"], participant_usernames=["stranger"])

    assert ok.status_code == 201
    assert sorted(p["username"] for p in ok.data["participants"]) == [
        "editor",
        "helder",
    ]
    assert refused.status_code == 400
    assert "contact" in refused.data["participant_usernames"][0]


def test_contacts_take_part_as_outside_people(tree, editor_api):
    booker = Contact.objects.create(
        workspace=tree.workspace, first_name="Ana", last_name="Booker", job="Prog"
    )
    foreign = Contact.objects.create(workspace=tree.other_workspace, last_name="X")

    # The editor of R is not a member of the workspace: the booker is only
    # visible to them once linked to one of their projects.
    unseen = create(editor_api, tree["A"], contacts=[booker.pk])
    refused = create(editor_api, tree["A"], contacts=[foreign.pk])
    ProjectContact.objects.create(project=tree["A"], contact=booker)
    ok = create(editor_api, tree["A"], contacts=[booker.pk])

    assert unseen.status_code == 400
    assert ok.status_code == 201
    assert ok.data["contact_details"] == [
        {
            "id": booker.pk,
            "display_name": "Ana Booker",
            "organization": "",
            "job": "Prog",
        }
    ]
    assert refused.status_code == 400


def test_contacts_added_by_someone_else_survive_my_edit(tree, editor_api):
    hidden = Contact.objects.create(workspace=tree.workspace, last_name="Agent")
    event = make_event(tree["A"])
    event.contacts.add(hidden)  # added by a workspace member

    response = editor_api.patch(
        f"/api/events/{event.pk}/",
        {"title": "RDV déplacé", "contacts": [hidden.pk]},
        format="json",
    )

    assert response.status_code == 200
    # I see them on the event, even without access to the address book.
    assert [c["display_name"] for c in response.data["contact_details"]] == ["Agent"]


# --- Filters --------------------------------------------------------------------------


def test_filters(tree, editor_api, editor, make_member):
    other = make_member("other", "viewer")
    press = TagFactory(workspace=tree.workspace, name="presse")
    live = make_event(tree["A"], title="a-live", type="live", start=at(3))
    live.participants.add(editor)
    live.tags.add(press)
    rdv = make_event(tree["A1"], title="a1-rdv", start=at(10))
    rdv.participants.add(other)
    make_event(tree["B"], title="b-past", start=at(-20))
    make_event(tree["Z"], title="z-hidden")

    get = editor_api.get
    assert titles(get("/api/events/")) == ["a-live", "a1-rdv", "b-past"]
    assert titles(get("/api/events/?participant=me")) == ["a-live"]
    assert titles(get("/api/events/?participant=other")) == ["a1-rdv"]
    assert titles(get(f"/api/events/?project={tree['A'].pk}")) == ["a-live"]
    assert titles(
        get(f"/api/events/?project={tree['A'].pk}&include_descendants=true")
    ) == ["a-live", "a1-rdv"]
    assert titles(get("/api/events/?type=live&type=exam")) == ["a-live"]
    assert titles(get(f"/api/events/?tag={press.pk}")) == ["a-live"]
    assert titles(get("/api/events/?search=RDV")) == ["a1-rdv"]
    assert titles(get(f"/api/events/?workspace={tree.other_workspace.pk}")) == []
    # Oldest first by default: what a calendar and an agenda expect.
    assert [e["title"] for e in get("/api/events/").data["results"]] == [
        "b-past",
        "a-live",
        "a1-rdv",
    ]


def test_window_filter_keeps_events_that_cross_the_period(tree, editor_api):
    project = tree["A"]
    make_event(project, title="before", start=at(-5))
    make_event(project, title="ends-inside", start=at(-1, 23), end=at(0, 1))
    make_event(project, title="inside", start=at(2))
    make_event(project, title="covers", start=at(-3), end=at(9), all_day=False)
    make_event(project, title="after", start=at(8))
    make_event(
        project, title="all-day-last-day", start=day(-2), end=day(0), all_day=True
    )

    window = f"window_start={iso(day(0))}&window_end={iso(day(7))}"
    response = editor_api.get(f"/api/events/?{window}".replace("+", "%2B"))

    assert titles(response) == ["all-day-last-day", "covers", "ends-inside", "inside"]


# --- Task created from a meeting (SPEC §8) --------------------------------------------


def test_a_task_keeps_the_link_to_its_meeting(tree, editor_api):
    event = make_event(tree["A"], title="RDV label")

    created = editor_api.post(
        "/api/tasks/",
        {
            "project": tree["A"].pk,
            "title": "Envoyer le master",
            "source_event": event.pk,
        },
        format="json",
    )

    assert created.status_code == 201
    assert created.data["source_event_detail"]["id"] == event.pk
    assert created.data["source_event_detail"]["title"] == "RDV label"
    shown = editor_api.get(f"/api/events/{event.pk}/")
    assert shown.data["tasks"] == [
        {"id": created.data["id"], "title": "Envoyer le master", "status": "todo"}
    ]


def test_the_meeting_must_be_in_the_same_project_and_visible(tree, make_member):
    elsewhere = make_event(tree["B"])
    hidden = make_event(tree["Z"])
    client = client_for(make_member("editor2", "editor"))

    for event in (elsewhere, hidden):
        response = client.post(
            "/api/tasks/",
            {"project": tree["A"].pk, "title": "x", "source_event": event.pk},
            format="json",
        )
        assert response.status_code == 400


def test_the_link_is_set_once_and_survives_the_meeting(tree, editor_api):
    first, second = make_event(tree["A"]), make_event(tree["A"])
    task_id = editor_api.post(
        "/api/tasks/",
        {"project": tree["A"].pk, "title": "x", "source_event": first.pk},
        format="json",
    ).data["id"]

    editor_api.patch(
        f"/api/tasks/{task_id}/", {"source_event": second.pk}, format="json"
    )
    assert (
        editor_api.get(f"/api/tasks/{task_id}/").data["source_event_detail"]["id"]
        == first.pk
    )
    # Deleting the meeting keeps the task, without its link.
    editor_api.delete(f"/api/events/{first.pk}/")
    assert editor_api.get(f"/api/tasks/{task_id}/").data["source_event_detail"] is None


# --- Dashboards -----------------------------------------------------------------------


def test_upcoming_meetings_widget(tree, editor_api, editor):
    mine = make_event(tree["A"], title="mine", start=at(1))
    mine.participants.add(editor)
    make_event(tree["A1"], title="theirs", start=at(5))
    make_event(tree["A"], title="over", start=at(-1))
    make_event(tree["A"], title="too far", start=at(30))
    make_event(tree["Z"], title="hidden", start=at(1))
    make_event(
        tree["B"], title="festival", start=day(-1), end=day(1), all_day=True
    )  # started yesterday, still on

    widget = editor_api.get("/api/dashboard/summary/").data["widgets"]["meetings"]
    only_mine = editor_api.get("/api/dashboard/summary/?only_mine=true").data[
        "widgets"
    ]["meetings"]

    assert widget["available"] is True and widget["count"] == 3
    assert [e["title"] for e in widget["items"]] == ["festival", "mine", "theirs"]
    assert [e["title"] for e in only_mine["items"]] == ["mine"]


def test_events_are_milestones_of_the_project_overview(tree, editor_api):
    make_event(tree["A1"], title="Tournage", type="shooting", start=at(4))
    make_event(tree["B"], title="ailleurs", start=at(2))

    overview = editor_api.get(f"/api/projects/{tree['A'].pk}/overview/").data

    events = [m for m in overview["milestones"] if m["kind"] == "event"]
    assert [m["title"] for m in events] == ["Tournage"]
    assert events[0]["project"] == tree["A1"].pk


def test_all_day_convention(tree, editor_api):
    """Midnight UTC, inclusive end: a two-day shooting ends on its second day."""
    response = create(
        editor_api,
        tree["A"],
        title="Tournage",
        type="shooting",
        all_day=True,
        start=iso(day(5)),
        end=iso(day(6)),
    )

    event = Event.objects.get(pk=response.data["id"])
    assert event.start == datetime.combine(day(5).date(), datetime.min.time(), UTC)
    assert event.end == day(6)
