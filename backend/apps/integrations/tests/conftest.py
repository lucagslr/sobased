"""A fake Google, plugged in place of `google.transport`: it answers the
token, userinfo, revoke and Drive endpoints the application calls, records
every call, and can be told to fail. No network in the tests."""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.files.tests.conftest import client_for  # noqa: F401  (re-exported)
from apps.integrations import google
from apps.integrations.models import (
    SCOPE_CALENDAR,
    SCOPE_DRIVE,
    SCOPE_EMAIL,
    OAuthAccount,
    Provider,
)
from apps.projects.tests.factories import Tree, grant  # noqa: F401


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

    # --- helpers -----------------------------------------------------------------
    def _token(self, data):
        if data.get("grant_type") == "refresh_token" and self.fail_refresh:
            return FakeResponse(400, {"error": "invalid_grant"})
        self.token_count += 1
        payload = {
            "access_token": f"at-{self.token_count}",
            "expires_in": 3600,
            "scope": " ".join([SCOPE_EMAIL, SCOPE_DRIVE]),
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
