"""Two-way calendar sync against the fakes: push, echo, pull, rights,
conflicts, detachment, displayed calendars, resync, Microsoft."""

from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.events.models import Event
from apps.integrations import sync
from apps.integrations.models import (
    ExternalCalendar,
    ExternalEvent,
    SyncConflict,
    SyncMapping,
)
from apps.projects.tests.factories import grant
from apps.tasks.models import Task
from apps.tasks.tests.conftest import day

from .conftest import client_for, connect_google

pytestmark = pytest.mark.django_db


@pytest.fixture
def google_account(editor, fake_google):
    return connect_google(editor, features=("drive", "calendar"))


@pytest.fixture
def target(google_account):
    """The primary Google calendar as target (as the settings would set it)."""
    calendars = sync.refresh_calendars(google_account)
    primary = next(c for c in calendars if c.is_primary)
    sync.set_target(primary)
    primary.refresh_from_db()
    return primary


def make_task(project, user, title="Rendre le TP", offset=3, **fields):
    fields.setdefault("due_at", day(offset))
    task = Task.objects.create(project=project, title=title, **fields)
    task.assignees.add(user)
    return task


def make_event(project, user, title="Réunion", **fields):
    start = fields.pop(
        "start", timezone.now().replace(microsecond=0) + timedelta(days=2)
    )
    event = Event.objects.create(
        project=project,
        title=title,
        start=start,
        end=fields.pop("end", start + timedelta(hours=1)),
        created_by=user,
        **fields,
    )
    return event


# --- Calendars list and target --------------------------------------------------------
def test_refresh_and_single_target(editor_api, google_account, fake_google):
    response = editor_api.post("/api/integrations/calendars/refresh/")
    assert response.status_code == 200, response.data
    names = {c["name"]: c for c in response.data}
    assert set(names) == {"Perso", "Horaire HEG"}
    assert names["Perso"]["is_primary"] and names["Perso"]["provider"] == "google"
    perso, heg = names["Perso"]["id"], names["Horaire HEG"]["id"]
    assert editor_api.patch(
        f"/api/integrations/calendars/{perso}/", {"is_target": True}, format="json"
    ).data["is_target"]
    editor_api.patch(
        f"/api/integrations/calendars/{heg}/", {"is_target": True}, format="json"
    )
    targets = [
        c["id"]
        for c in editor_api.get("/api/integrations/calendars/").data
        if c["is_target"]
    ]
    assert targets == [heg]  # one target per user
    shown = editor_api.patch(
        f"/api/integrations/calendars/{heg}/", {"is_displayed": True}, format="json"
    )
    assert shown.data["is_displayed"] is True
    # Someone else's calendars are invisible.
    stranger = client_for(UserFactory(username="stranger"))
    assert stranger.get("/api/integrations/calendars/").data == []
    assert (
        stranger.patch(
            f"/api/integrations/calendars/{heg}/", {"is_displayed": True}
        ).status_code
        == 404
    )


# --- Push -----------------------------------------------------------------------------
def test_push_tasks_and_events(editor, tree, target, fake_google, google_account):
    all_day = make_task(tree["A"], editor, "Rendre le TP")
    timed = make_task(
        tree["A"],
        editor,
        "Appel",
        all_day=False,
        due_at=datetime(2026, 10, 1, 14, 0, tzinfo=UTC),
    )
    event = make_event(tree["A"], editor, "Réunion label")
    make_task(tree["A"], editor, "Annulée", status="cancelled")  # not pushed
    make_task(tree["B"], UserFactory(username="other"), "Pas à moi")  # not pushed
    Task.objects.create(
        project=tree["A"], title="Sans échéance", due_at=None
    ).assignees.add(editor)

    stats = sync.sync_account(google_account)
    assert stats["pushed"] == {"created": 3, "updated": 0, "deleted": 0}
    pushed = {e["summary"]: e for e in fake_google.events["primary"].values()}
    assert set(pushed) == {"☐ Rendre le TP", "☐ Appel", "Réunion label"}
    assert pushed["☐ Rendre le TP"]["start"] == {
        "date": all_day.due_at.date().isoformat()
    }
    assert pushed["☐ Rendre le TP"]["end"] == {
        "date": (all_day.due_at.date() + timedelta(days=1)).isoformat()
    }
    assert pushed["☐ Appel"]["start"]["dateTime"] == "2026-10-01T13:30:00+00:00"
    assert pushed["☐ Appel"]["end"]["dateTime"] == "2026-10-01T14:00:00+00:00"
    assert pushed["Réunion label"]["end"]["dateTime"] == event.end.isoformat()
    assert SyncMapping.objects.filter(calendar=target, state="active").count() == 3

    # Nothing changed: a second sync sends nothing.
    assert sync.sync_account(google_account)["pushed"] == {
        "created": 0,
        "updated": 0,
        "deleted": 0,
    }
    # Done, then cancelled: title updated, then removed.
    timed.status = "done"
    timed.save()
    assert sync.sync_account(google_account)["pushed"]["updated"] == 1
    mapping = SyncMapping.objects.get(object_type="task", object_id=timed.pk)
    assert fake_google.events["primary"][mapping.external_id]["summary"] == "☑ Appel"
    timed.status = "cancelled"
    timed.save()
    assert sync.sync_account(google_account)["pushed"]["deleted"] == 1
    assert fake_google.events["primary"][mapping.external_id]["status"] == "cancelled"
    assert not SyncMapping.objects.filter(pk=mapping.pk).exists()
    # Unassigned: removed too. Deleted event: removed.
    all_day.assignees.clear()
    event.delete()
    assert sync.sync_account(google_account)["pushed"]["deleted"] == 2


# --- Pull -----------------------------------------------------------------------------
def test_external_change_comes_back_and_echo_is_ignored(
    editor, tree, target, fake_google, google_account
):
    task = make_task(tree["A"], editor, "Rendre le TP")
    event = make_event(tree["A"], editor, "Réunion")
    sync.sync_account(google_account)
    task_map = SyncMapping.objects.get(object_type="task", object_id=task.pk)
    event_map = SyncMapping.objects.get(object_type="event", object_id=event.pk)

    # The editor moves the task and renames the event in Google.
    fake_google.change_externally(
        "primary",
        task_map.external_id,
        summary="☐ Rendre le TP (v2)",
        start={"date": "2026-11-05"},
        end={"date": "2026-11-06"},
    )
    new_start = (event.start + timedelta(hours=3)).isoformat()
    new_end = (event.end + timedelta(hours=3)).isoformat()
    fake_google.change_externally(
        "primary",
        event_map.external_id,
        summary="Réunion déplacée",
        start={"dateTime": new_start, "timeZone": "UTC"},
        end={"dateTime": new_end, "timeZone": "UTC"},
    )
    stats = sync.sync_account(google_account)
    assert stats["pulled"] >= 2 and not stats["errors"]
    task.refresh_from_db()
    event.refresh_from_db()
    assert task.title == "Rendre le TP (v2)"  # prefix stripped
    assert task.due_at == datetime(2026, 11, 5, tzinfo=UTC) and task.all_day
    assert event.title == "Réunion déplacée"
    assert event.start.isoformat() == new_start and event.end.isoformat() == new_end
    assert not SyncConflict.objects.exists()
    # The change was absorbed: the next push sends nothing back (no loop).
    assert sync.sync_account(google_account)["pushed"]["updated"] == 0


def test_external_deletion_only_detaches(
    editor, tree, target, fake_google, google_account
):
    task = make_task(tree["A"], editor)
    sync.sync_account(google_account)
    mapping = SyncMapping.objects.get(object_type="task", object_id=task.pk)
    fake_google.change_externally("primary", mapping.external_id, status="cancelled")
    sync.sync_account(google_account)
    mapping.refresh_from_db()
    assert mapping.state == "detached"
    assert Task.objects.filter(pk=task.pk).exists()  # never deleted locally
    # Detached: never pushed again, even after a local change.
    task.title = "Changée"
    task.save()
    assert sync.sync_account(google_account)["pushed"] == {
        "created": 0,
        "updated": 0,
        "deleted": 0,
    }


def test_without_rights_the_local_values_win(tree, fake_google):
    """An assignee who is only a viewer may move the date, not the title."""
    viewer = UserFactory(username="viewer")
    grant(viewer, tree["A"], "viewer")
    account = connect_google(viewer, features=("drive", "calendar"))
    calendars = sync.refresh_calendars(account)
    sync.set_target(next(c for c in calendars if c.is_primary))
    task = make_task(tree["A"], viewer, "Titre officiel")
    sync.sync_account(account)
    mapping = SyncMapping.objects.get(object_type="task", object_id=task.pk)
    fake_google.change_externally(
        "primary",
        mapping.external_id,
        summary="☐ Titre pirate",
        start={"date": "2026-12-01"},
        end={"date": "2026-12-02"},
    )
    sync.sync_account(account)
    task.refresh_from_db()
    assert task.title == "Titre officiel"  # title kept
    assert task.due_at == datetime(2026, 12, 1, tzinfo=UTC)  # date moved
    # The calendar is put back in line with SOBASED at that same sync.
    external = fake_google.events["primary"][mapping.external_id]
    assert external["summary"] == "☐ Titre officiel"


def test_conflict_most_recent_wins(editor, tree, target, fake_google, google_account):
    event = make_event(tree["A"], editor, "Réunion")
    sync.sync_account(google_account)
    mapping = SyncMapping.objects.get(object_type="event", object_id=event.pk)
    # External change first, then a local one (more recent): local wins.
    fake_google.change_externally("primary", mapping.external_id, summary="Externe")
    event.title = "Local"
    event.save()
    SyncMapping.objects.filter(pk=mapping.pk).update(
        pushed_at=timezone.now() - timedelta(minutes=5)
    )
    sync.sync_account(google_account)
    event.refresh_from_db()
    assert event.title == "Local"
    conflict = SyncConflict.objects.get()
    assert conflict.winner == "local"
    assert conflict.details["external"]["title"] == "Externe"
    assert fake_google.events["primary"][mapping.external_id]["summary"] == "Local"


def test_displayed_calendar_is_mirrored_read_only(
    editor_api, editor, tree, google_account, fake_google
):
    calendars = sync.refresh_calendars(google_account)
    heg = next(c for c in calendars if c.name == "Horaire HEG")
    heg.is_displayed = True
    heg.save()
    fake_google.add_external_event(
        "heg", "Cours BPMN", "2026-10-06T08:15:00+00:00", "2026-10-06T10:00:00+00:00"
    )
    fake_google.add_external_event(
        "heg", "Examen", "2026-10-20", "2026-10-21", all_day=True
    )
    stats = sync.sync_account(google_account)
    assert stats["pulled"] == 2
    mirrored = {e.title: e for e in ExternalEvent.objects.filter(calendar=heg)}
    assert set(mirrored) == {"Cours BPMN", "Examen"}
    assert (
        mirrored["Examen"].all_day
        and mirrored["Examen"].start == mirrored["Examen"].end
    )
    response = editor_api.get(
        "/api/integrations/external-events/",
        {"start": "2026-10-01T00:00:00Z", "end": "2026-10-31T00:00:00Z"},
    )
    assert response.status_code == 200
    assert [e["title"] for e in response.data] == ["Cours BPMN", "Examen"]
    assert response.data[0]["calendar_name"] == "Horaire HEG"
    # Hidden again: nothing served. Deleted in Google: gone from the mirror.
    heg.is_displayed = False
    heg.save()
    assert (
        editor_api.get(
            "/api/integrations/external-events/",
            {"start": "2026-10-01T00:00:00Z", "end": "2026-10-31T00:00:00Z"},
        ).data
        == []
    )
    heg.is_displayed = True
    heg.save()
    fake_google.change_externally("heg", "x1", status="cancelled")
    sync.sync_account(google_account)
    assert not ExternalEvent.objects.filter(calendar=heg, title="Cours BPMN").exists()


def test_invalid_sync_token_resyncs(editor, tree, google_account, fake_google):
    calendars = sync.refresh_calendars(google_account)
    heg = next(c for c in calendars if c.name == "Horaire HEG")
    heg.is_displayed = True
    heg.save()
    fake_google.add_external_event(
        "heg", "Cours", "2026-10-06T08:15:00+00:00", "2026-10-06T10:00:00+00:00"
    )
    sync.sync_account(google_account)
    heg.refresh_from_db()
    assert heg.sync_cursor.startswith("tok-")
    fake_google.invalid_tokens.add(heg.sync_cursor)
    stats = sync.sync_account(google_account)
    assert not stats["errors"]
    heg.refresh_from_db()
    assert heg.sync_cursor not in fake_google.invalid_tokens
    assert ExternalEvent.objects.filter(calendar=heg).count() == 1


def test_provider_error_is_recorded_not_raised(
    editor, tree, target, fake_google, google_account
):
    fake_google.calendars.pop("primary")  # Google now answers 404
    stats = sync.sync_account(google_account)
    assert stats["errors"]
    target.refresh_from_db()
    assert "404" in target.last_error


def test_sync_now_and_conflicts_endpoints(editor_api, google_account, target):
    assert editor_api.post("/api/integrations/sync-now/").status_code == 202
    assert editor_api.get("/api/integrations/sync-conflicts/").data == []


def test_webhook_checks_the_channel_token(client, target):
    import hashlib

    target.watch_channel_id = "chan"
    target.watch_token_hash = hashlib.sha256(b"secret").hexdigest()
    target.save()
    ok = client.post(
        "/api/integrations/google/calendar/webhook/",
        HTTP_X_GOOG_CHANNEL_ID="chan",
        HTTP_X_GOOG_CHANNEL_TOKEN="secret",
    )
    assert ok.status_code == 200
    wrong = client.post(
        "/api/integrations/google/calendar/webhook/",
        HTTP_X_GOOG_CHANNEL_ID="chan",
        HTTP_X_GOOG_CHANNEL_TOKEN="nope",
    )
    assert wrong.status_code == 200  # never a hint to the caller


def test_watch_only_with_public_https(settings, target, fake_google):
    settings.SITE_URL = "http://localhost:8080"
    settings.SITE_IS_HTTPS = False
    sync.renew_watch(target)
    assert fake_google.watches == []
    settings.SITE_URL = "https://sobased.example.ch"
    settings.SITE_IS_HTTPS = True
    sync.renew_watch(target)
    target.refresh_from_db()
    assert len(fake_google.watches) == 1 and target.watch_channel_id
    assert fake_google.watches[0]["address"].endswith(
        "/api/integrations/google/calendar/webhook/"
    )


# --- Microsoft ------------------------------------------------------------------------
def test_microsoft_oauth_and_sync(editor_api, editor, tree, fake_graph):
    from urllib.parse import parse_qs, urlparse

    from apps.integrations import microsoft

    url = editor_api.get("/api/integrations/microsoft/connect/").data["url"]
    assert url.startswith(
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    )
    state = parse_qs(urlparse(url).query)["state"][0]
    back = editor_api.get(
        "/api/integrations/microsoft/callback/", {"code": "abc", "state": state}
    )
    assert back["Location"].endswith("?microsoft=ok")
    state_data = editor_api.get("/api/integrations/").data["microsoft"]
    assert state_data["connected"] and state_data["email"] == "luca@heg.ch"

    listing = editor_api.post("/api/integrations/calendars/refresh/").data
    assert [c["provider"] for c in listing] == ["microsoft"]
    cal_id = listing[0]["id"]
    editor_api.patch(
        f"/api/integrations/calendars/{cal_id}/",
        {"is_target": True, "is_displayed": True},
        format="json",
    )

    task = make_task(tree["A"], editor, "TP Outlook")
    event = make_event(tree["A"], editor, "Teams")
    account = editor.oauth_accounts.get(provider="microsoft")
    stats = sync.sync_account(account)
    assert stats["pushed"]["created"] == 2 and not stats["errors"]
    subjects = {e["subject"]: e for e in fake_graph.events.values()}
    assert subjects["☐ TP Outlook"]["isAllDay"] is True
    assert subjects["☐ TP Outlook"]["start"]["dateTime"].endswith("T00:00:00")
    assert subjects["Teams"]["isAllDay"] is False
    # Pull: our own events come back through the delta and are ignored (echo).
    assert sync.sync_account(account)["pushed"]["updated"] == 0
    assert ExternalEvent.objects.count() == 0  # mapped objects are not mirrored
    # An external deletion detaches.
    mapping = SyncMapping.objects.get(object_type="event", object_id=event.pk)
    fake_graph.events.pop(mapping.external_id)
    fake_graph.removed.append(mapping.external_id)
    sync.sync_account(account)
    mapping.refresh_from_db()
    assert mapping.state == "detached" and Event.objects.filter(pk=event.pk).exists()
    assert task.pk  # still there too
    assert editor_api.delete("/api/integrations/microsoft/").status_code == 204
    assert not ExternalCalendar.objects.filter(account__user=editor).exists()
    assert microsoft.enabled()


def test_calendar_disabled_without_scope(editor, tree, fake_google):
    """Drive only: no calendar sync attempted."""
    account = connect_google(editor, features=("drive",))
    assert sync.sync_account(account) == {"pushed": {}, "pulled": 0, "errors": []}
