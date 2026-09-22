"""Google OAuth and the Drive REST calls the application needs.

Plain HTTPS through `requests` rather than google-api-python-client: the
handful of endpoints used here is small, the code stays readable, and the
tests swap `transport` for a fake that answers the same URLs. Everything
goes through request() so that a single place adds the bearer token,
refreshes it when Google says 401, and turns HTTP errors into GoogleError.
"""

from __future__ import annotations

import json
import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.core import signing
from django.utils import timezone

from .models import SCOPE_EMAIL, AccountStatus, OAuthAccount

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
DRIVE_URL = "https://www.googleapis.com/drive/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER_MIME = "application/vnd.google-apps.folder"
FILE_FIELDS = "id,name,mimeType,iconLink,webViewLink,thumbnailLink,size"
STATE_SALT = "integrations.google.state"
TIMEOUT = 30

# Swapped by the tests (apps/integrations/tests/conftest.py: FakeGoogle).
transport = requests.Session()


class GoogleError(Exception):
    """A Google answer the application cannot use (HTTP error, bad token)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def enabled() -> bool:
    return settings.GOOGLE_ENABLED


def redirect_uri() -> str:
    return f"{settings.SITE_URL}/api/integrations/google/callback/"


# --- OAuth -----------------------------------------------------------------------
def authorization_url(user, scopes: list[str]) -> str:
    """Incremental consent: Google merges new scopes with the granted ones.
    `state` is signed so that the callback can trust the user it names."""
    state = signing.dumps(
        {"u": user.pk, "n": secrets.token_urlsafe(8), "s": scopes}, salt=STATE_SALT
    )
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join([SCOPE_EMAIL, *scopes]),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{requests.compat.urlencode(params)}"


def read_state(state: str) -> dict | None:
    try:
        return signing.loads(state, salt=STATE_SALT, max_age=15 * 60)
    except (signing.BadSignature, signing.SignatureExpired):
        return None


def _token_request(data: dict) -> dict:
    response = transport.post(
        TOKEN_URL,
        data={
            **data,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
        },
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        raise GoogleError("Google a refusé l'échange de jetons.", response.status_code)
    return response.json()


def exchange_code(code: str) -> dict:
    return _token_request(
        {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(),
        }
    )


def refresh(account: OAuthAccount) -> None:
    """A new access token from the refresh token; on refusal the account
    needs a new consent (status needs_reauth, nothing is deleted)."""
    token = account.refresh_token
    if not token:
        raise GoogleError("Aucun jeton de rafraîchissement.", 401)
    try:
        data = _token_request({"refresh_token": token, "grant_type": "refresh_token"})
    except GoogleError:
        account.status = AccountStatus.NEEDS_REAUTH
        account.save(update_fields=["status", "updated_at"])
        raise
    store_tokens(account, data)


def store_tokens(account: OAuthAccount, data: dict) -> None:
    account.access_token = data.get("access_token")
    if data.get("refresh_token"):
        account.refresh_token = data["refresh_token"]
    account.token_expires_at = timezone.now() + timedelta(
        seconds=int(data.get("expires_in", 3600)) - 60
    )
    if data.get("scope"):
        account.scopes = sorted(set(data["scope"].split()))
    account.status = AccountStatus.OK
    account.save()


def userinfo(access_token: str) -> dict:
    response = transport.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        raise GoogleError("Impossible de lire le compte Google.", response.status_code)
    return response.json()


def revoke(account: OAuthAccount) -> None:
    """Best effort: a revocation that fails must not block the disconnection."""
    token = account.refresh_token or account.access_token
    if not token:
        return
    try:
        transport.post(REVOKE_URL, params={"token": token}, timeout=TIMEOUT)
    except requests.RequestException:
        pass


def valid_access_token(account: OAuthAccount) -> str:
    if account.token_expired or not account.access_token:
        refresh(account)
    return account.access_token or ""


# --- Drive -------------------------------------------------------------------------
class DriveClient:
    """The Drive calls, made as one account (the folder owner's, or the
    user's for the files they picked)."""

    def __init__(self, account: OAuthAccount):
        self.account = account

    def request(self, method: str, url: str, *, retry: bool = True, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {valid_access_token(self.account)}"
        try:
            response = transport.request(
                method, url, headers=headers, timeout=TIMEOUT, **kwargs
            )
        except requests.RequestException as exc:
            raise GoogleError(
                f"Google Drive injoignable ({exc.__class__.__name__})."
            ) from exc
        if response.status_code == 401 and retry:
            refresh(self.account)
            return self.request(method, url, retry=False, headers=headers, **kwargs)
        if response.status_code >= 400:
            detail = ""
            try:
                detail = response.json().get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                pass
            raise GoogleError(
                f"Google Drive a répondu {response.status_code}. {detail}".strip(),
                response.status_code,
            )
        return response

    def get_file(self, file_id: str) -> dict:
        return self.request(
            "GET", f"{DRIVE_URL}/files/{file_id}", params={"fields": FILE_FIELDS}
        ).json()

    def create_folder(self, name: str, parent_id: str | None = None) -> dict:
        body = {"name": name, "mimeType": FOLDER_MIME}
        if parent_id:
            body["parents"] = [parent_id]
        return self.request(
            "POST", f"{DRIVE_URL}/files", params={"fields": FILE_FIELDS}, json=body
        ).json()

    def upload(self, name: str, mime_type: str, content, parent_id: str) -> dict:
        """Multipart upload (metadata + bytes in one request)."""
        metadata = json.dumps({"name": name, "parents": [parent_id]})
        files = {
            "metadata": ("metadata", metadata, "application/json; charset=UTF-8"),
            "file": (name, content, mime_type or "application/octet-stream"),
        }
        return self.request(
            "POST",
            UPLOAD_URL,
            params={"uploadType": "multipart", "fields": FILE_FIELDS},
            files=files,
        ).json()

    def share(self, file_id: str, email: str, role: str) -> None:
        """role: reader or writer. Google mails no notification here."""
        self.request(
            "POST",
            f"{DRIVE_URL}/files/{file_id}/permissions",
            params={"sendNotificationEmail": "false"},
            json={"type": "user", "role": role, "emailAddress": email},
        )

    def download(self, file_id: str):
        """Streamed response of the file's bytes (alt=media)."""
        return self.request(
            "GET", f"{DRIVE_URL}/files/{file_id}", params={"alt": "media"}, stream=True
        )
