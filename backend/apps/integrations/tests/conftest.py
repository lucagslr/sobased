"""A fake Google, plugged in place of `google.transport`: it answers the
token, userinfo, revoke and Drive endpoints the application calls, records
every call, and can be told to fail. No network in the tests."""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.files.tests.conftest import client_for  # noqa: F401  (re-exported)
from apps.integrations import google, microsoft
from apps.integrations.models import (
    SCOPE_CALENDAR,
    SCOPE_DRIVE,
    SCOPE_EMAIL,
    OAuthAccount,
    Provider,
)
from apps.projects.tests.factories import Tree, grant  # noqa: F401

CAL_URL = "https://www.googleapis.com/calendar/v3"


class FakeResponse:
    def __init__(self, status_code=200, data=None, content=b""):
        self.status_code = status_code
        self._data = data if data is not None else {}
        self.content = content or json.dumps(self._data).encode()

    def json(self):
        return self._data


class FakeGoogle:
    """The subset of Google the app talks to, in memory."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.files: dict[str, dict] = {}
        self.permissions: list[tuple[str, str, str]] = []
        self.token_count = 0
        self.fail_refresh = False
        self.unauthorized_once = False
        self.email = "demo@gmail.com"
        self.contents: dict[str, bytes] = {}
        # Calendar: calendars and their events, a change log per calendar
        # (what an incremental syncToken read returns), invalid tokens.
        self.calendars: dict[str, dict] = {
            "primary": {
                "id": "primary",
                "summary": "Perso",
                "primary": True,
                "backgroundColor": "#9fe1cf",
                "accessRole": "owner",
            },
            "heg": {
                "id": "heg",
                "summary": "Horaire HEG",
                "primary": False,
                "backgroundColor": "#c7d2fe",
                "accessRole": "reader",
            },
        }
        self.events: dict[str, dict[str, dict]] = {"primary": {}, "heg": {}}
        self.event_count = 0
        self.token_count_cal = 0
        self.invalid_tokens: set[str] = set()
        self.watches: list[dict] = []
        self.grant_calendar = False  # what the consent screen granted

    # --- requests-like surface -------------------------------------------------
    def post(self, url, data=None, params=None, timeout=None, **kwargs):
        return self.request("POST", url, data=data, params=params, **kwargs)

    def get(self, url, headers=None, params=None, timeout=None, **kwargs):
        return self.request("GET", url, headers=headers, params=params, **kwargs)

    def request(self, method, url, headers=None, params=None, **kwargs):
        params = params or {}
        self.calls.append((method, url, {"params": params, **kwargs}))
        if url == google.TOKEN_URL:
            return self._token(kwargs.get("data") or {})
        if url == google.USERINFO_URL:
            return FakeResponse(200, {"email": self.email})
        if url == google.REVOKE_URL:
            return FakeResponse(200, {})
        if self.unauthorized_once:
            self.unauthorized_once = False
            return FakeResponse(401, {"error": {"message": "Invalid Credentials"}})
        if url.startswith(CAL_URL):
            return self._calendar(method, url[len(CAL_URL) :], params, kwargs)
        if url == google.UPLOAD_URL:
            files = kwargs["files"]
            metadata = json.loads(files["metadata"][1])
            name, content, mime = files["file"]
            body = content.read() if hasattr(content, "read") else content
            return FakeResponse(
                200, self._new_file(name, mime, metadata.get("parents"), body)
            )
        if url == f"{google.DRIVE_URL}/files" and method == "POST":
            body = kwargs["json"]
            return FakeResponse(
                200, self._new_file(body["name"], body["mimeType"], body.get("parents"))
            )
        if url.startswith(f"{google.DRIVE_URL}/files/"):
            rest = url[len(f"{google.DRIVE_URL}/files/") :]
            file_id, _, tail = rest.partition("/")
            if tail == "permissions":
                body = kwargs["json"]
                self.permissions.append((file_id, body["emailAddress"], body["role"]))
                return FakeResponse(200, {"id": "perm"})
            if file_id not in self.files:
                return FakeResponse(404, {"error": {"message": "File not found"}})
            if params.get("alt") == "media":
                return FakeResponse(200, {}, content=self.contents.get(file_id, b""))
            return FakeResponse(200, self.files[file_id])
        return FakeResponse(404, {"error": {"message": f"unexpected {url}"}})

    # --- Calendar API v3 ---------------------------------------------------------
    def _calendar(self, method, path, params, kwargs):
        from django.utils import timezone

        if path == "/users/me/calendarList":
            return FakeResponse(200, {"items": list(self.calendars.values())})
        if path == "/channels/stop":
            return FakeResponse(200, {})
        parts = path.strip("/").split("/")  # calendars/<id>/events[/<eid>|/watch]
        cal_id = parts[1]
        if cal_id not in self.calendars:
            return FakeResponse(404, {"error": {"message": "Not Found"}})
        store = self.events.setdefault(cal_id, {})
        tail = parts[3] if len(parts) > 3 else ""
        now = timezone.now().isoformat()
        if tail == "watch":
            self.watches.append({"calendar": cal_id, **kwargs["json"]})
            return FakeResponse(200, {"resourceId": "res-1", "expiration": "0"})
        if method == "POST" and not tail:
            self.event_count += 1
            event = {
                **kwargs["json"],
                "id": f"g{self.event_count}",
                "status": "confirmed",
                "updated": now,
                "etag": f"etag-{self.event_count}-1",
            }
            store[event["id"]] = event
            return FakeResponse(200, event)
        if method == "PATCH":
            event = store.get(tail)
            if event is None:
                return FakeResponse(404, {"error": {"message": "Not Found"}})
            event.update(kwargs["json"])
            event["updated"] = now
            event["etag"] = event["etag"].rsplit("-", 1)[0] + "-x"
            return FakeResponse(200, event)
        if method == "DELETE":
            if tail in store:
                store[tail]["status"] = "cancelled"
                store[tail]["updated"] = now
            return FakeResponse(204, {})
        if method == "GET" and not tail:
            token = params.get("syncToken")
            if token and token in self.invalid_tokens:
                return FakeResponse(
                    410, {"error": {"message": "Sync token is no longer valid"}}
                )
            self.token_count_cal += 1
            items = list(store.values())
            if token:
                since = int(token.split("-")[1])
                items = [e for e in items if e.get("seq", 0) > since]
            for event in store.values():
                event.setdefault("seq", 0)
            return FakeResponse(
                200,
                {
                    "items": items,
                    "nextSyncToken": f"tok-{self.mark()}-{self.token_count_cal}",
                },
            )
        return FakeResponse(404, {"error": {"message": f"unexpected {path}"}})

    def mark(self) -> int:
        """Every change bumps a sequence so that incremental reads work."""
        self._seq = getattr(self, "_seq", 0)
        return self._seq

    def change_externally(self, cal_id, event_id, **fields):
        """Something the user did in Google (title, dates, deletion)."""
        from django.utils import timezone

        self._seq = getattr(self, "_seq", 0) + 1
        event = self.events[cal_id][event_id]
        event.update(fields)
        event["updated"] = timezone.now().isoformat()
        event["etag"] = event.get("etag", "e") + "-u"
        event["seq"] = self._seq
        return event

    def add_external_event(
        self, cal_id, summary, start, end, all_day=False, event_id=None
    ):
        from django.utils import timezone

        self._seq = getattr(self, "_seq", 0) + 1
        self.event_count += 1
        event_id = event_id or f"x{self.event_count}"
        if all_day:
            body = {"start": {"date": start}, "end": {"date": end}}
        else:
            body = {"start": {"dateTime": start}, "end": {"dateTime": end}}
        self.events.setdefault(cal_id, {})[event_id] = {
            **body,
            "id": event_id,
            "summary": summary,
            "status": "confirmed",
            "updated": timezone.now().isoformat(),
            "etag": f"etag-{event_id}",
            "seq": self._seq,
        }
        return self.events[cal_id][event_id]

    # --- helpers -----------------------------------------------------------------
    def _token(self, data):
        if data.get("grant_type") == "refresh_token" and self.fail_refresh:
            return FakeResponse(400, {"error": "invalid_grant"})
        self.token_count += 1
        payload = {
            "access_token": f"at-{self.token_count}",
            "expires_in": 3600,
            "scope": " ".join(
                [SCOPE_EMAIL, SCOPE_DRIVE]
                + ([SCOPE_CALENDAR] if self.grant_calendar else [])
            ),
        }
        if data.get("grant_type") == "authorization_code":
            payload["refresh_token"] = "rt-1"
        return FakeResponse(200, payload)

    def _new_file(self, name, mime, parents=None, body=b""):
        file_id = f"f{len(self.files) + 1}"
        self.files[file_id] = {
            "id": file_id,
            "name": name,
            "mimeType": mime,
            "parents": parents or [],
            "iconLink": "https://drive-thirdparty.googleusercontent.com/16/type/"
            + mime,
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
            "thumbnailLink": "",
            "size": str(len(body)) if body else "",
        }
        if body:
            self.contents[file_id] = body
        return self.files[file_id]

    def add_file(self, name, mime, body=b"", file_id=None):
        """A file "already on the user's Drive" (as the Picker would return)."""
        data = self._new_file(name, mime, body=body)
        if file_id:
            generated = data["id"]
            self.files[file_id] = self.files.pop(generated)
            self.files[file_id]["id"] = file_id
            if generated in self.contents:
                self.contents[file_id] = self.contents.pop(generated)
            data = self.files[file_id]
        return data

    def folders(self):
        return [f for f in self.files.values() if f["mimeType"] == google.FOLDER_MIME]


@pytest.fixture
def fake_google(monkeypatch, settings):
    settings.GOOGLE_CLIENT_ID = "client-id"
    settings.GOOGLE_CLIENT_SECRET = "client-secret"
    settings.GOOGLE_API_KEY = "api-key"
    settings.GOOGLE_APP_ID = "123456"
    settings.GOOGLE_ENABLED = True
    fake = FakeGoogle()
    monkeypatch.setattr(google, "transport", fake)
    return fake


def connect_google(user, features=("drive",), email="demo@gmail.com") -> OAuthAccount:
    """An account as the OAuth callback would store it."""
    account = OAuthAccount.objects.create(
        user=user,
        provider=Provider.GOOGLE,
        account_email=email,
        scopes=[SCOPE_EMAIL]
        + [{"drive": SCOPE_DRIVE, "calendar": SCOPE_CALENDAR}[f] for f in features],
        token_expires_at=timezone.now() + timedelta(hours=1),
    )
    account.access_token = "at-0"
    account.refresh_token = "rt-0"
    account.save()
    return account


@pytest.fixture
def tree(db):
    return Tree()


@pytest.fixture
def editor(tree):
    """Editor of the whole workspace W: may create root projects in it."""
    user = UserFactory(username="editor")
    grant(user, tree.workspace, "editor")
    return user


@pytest.fixture
def editor_api(editor):
    return client_for(editor)


@pytest.fixture
def connected_editor(editor, fake_google):
    connect_google(editor)
    return editor


class FakeGraph:
    """Microsoft identity + Graph, the subset used (calendars, events, delta)."""

    def __init__(self):
        self.calls = []
        self.token_count = 0
        self.email = "luca@heg.ch"
        self.calendars = {
            "cal1": {
                "id": "cal1",
                "name": "Calendrier",
                "isDefaultCalendar": True,
                "hexColor": "#0078d4",
            },
        }
        self.events: dict[str, dict] = {}
        self.event_count = 0
        self.removed: list[str] = []
        self.deltas = 0

    def post(self, url, data=None, params=None, timeout=None, **kwargs):
        return self.request("POST", url, data=data, params=params, **kwargs)

    def get(self, url, headers=None, params=None, timeout=None, **kwargs):
        return self.request("GET", url, headers=headers, params=params, **kwargs)

    def request(self, method, url, headers=None, params=None, **kwargs):
        from django.utils import timezone

        self.calls.append((method, url))
        if url.endswith("/oauth2/v2.0/token"):
            self.token_count += 1
            return FakeResponse(
                200,
                {
                    "access_token": f"ms-at-{self.token_count}",
                    "refresh_token": "ms-rt",
                    "expires_in": 3600,
                    "scope": "offline_access User.Read Calendars.ReadWrite",
                },
            )
        if url == f"{microsoft.GRAPH_URL}/me":
            return FakeResponse(200, {"mail": self.email, "displayName": "Luca"})
        if url == f"{microsoft.GRAPH_URL}/me/calendars":
            return FakeResponse(200, {"value": list(self.calendars.values())})
        if url.startswith(f"{microsoft.GRAPH_URL}/me/calendars/") and url.endswith(
            "/events"
        ):
            self.event_count += 1
            event = {
                **kwargs["json"],
                "id": f"m{self.event_count}",
                "lastModifiedDateTime": timezone.now().isoformat(),
                "@odata.etag": f"W/{self.event_count}",
            }
            self.events[event["id"]] = event
            return FakeResponse(200, event)
        if "/calendarView/delta" in url or url.startswith("https://delta/"):
            self.deltas += 1
            value = list(self.events.values()) + [
                {"id": eid, "@removed": {"reason": "deleted"}} for eid in self.removed
            ]
            self.removed = []
            return FakeResponse(
                200,
                {"value": value, "@odata.deltaLink": f"https://delta/{self.deltas}"},
            )
        if url.startswith(f"{microsoft.GRAPH_URL}/me/events/"):
            eid = url.rsplit("/", 1)[1]
            if method == "PATCH":
                self.events[eid].update(kwargs["json"])
                self.events[eid]["lastModifiedDateTime"] = timezone.now().isoformat()
                return FakeResponse(200, self.events[eid])
            if method == "DELETE":
                self.events.pop(eid, None)
                self.removed.append(eid)
                return FakeResponse(204, {})
        return FakeResponse(404, {"error": {"message": f"unexpected {url}"}})


@pytest.fixture
def fake_graph(monkeypatch, settings):
    settings.MS_CLIENT_ID = "ms-client"
    settings.MS_CLIENT_SECRET = "ms-secret"
    settings.MS_ENABLED = True
    fake = FakeGraph()
    monkeypatch.setattr(microsoft, "transport", fake)
    return fake


def connect_microsoft(user, email="luca@heg.ch") -> OAuthAccount:
    account = OAuthAccount.objects.create(
        user=user,
        provider=Provider.MICROSOFT,
        account_email=email,
        scopes=["offline_access", "User.Read", "Calendars.ReadWrite"],
        token_expires_at=timezone.now() + timedelta(hours=1),
    )
    account.access_token = "ms-at-0"
    account.refresh_token = "ms-rt-0"
    account.save()
    return account
