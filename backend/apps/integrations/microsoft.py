"""Microsoft identity platform (OAuth v2.0) and the Graph calls for Outlook
calendars, in plain REST like google.py. No MSAL: the authorization-code
flow with a refresh token is three requests, and a single `transport`
keeps the tests offline (FakeGraph).
"""

from __future__ import annotations

import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.core import signing
from django.utils import timezone

from .models import AccountStatus, OAuthAccount

GRAPH_URL = "https://graph.microsoft.com/v1.0"
SCOPES = ["offline_access", "User.Read", "Calendars.ReadWrite"]
STATE_SALT = "integrations.microsoft.state"
TIMEOUT = 30

transport = requests.Session()


class MicrosoftError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def enabled() -> bool:
    return settings.MS_ENABLED


def _authority() -> str:
    return f"https://login.microsoftonline.com/{settings.MS_TENANT}/oauth2/v2.0"


def redirect_uri() -> str:
    return f"{settings.SITE_URL}/api/integrations/microsoft/callback/"


def authorization_url(user) -> str:
    state = signing.dumps(
        {"u": user.pk, "n": secrets.token_urlsafe(8)}, salt=STATE_SALT
    )
    params = {
        "client_id": settings.MS_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri(),
        "response_mode": "query",
        "scope": " ".join(SCOPES),
        "state": state,
    }
    return f"{_authority()}/authorize?{requests.compat.urlencode(params)}"


def read_state(state: str) -> dict | None:
    try:
        return signing.loads(state, salt=STATE_SALT, max_age=15 * 60)
    except (signing.BadSignature, signing.SignatureExpired):
        return None


def _token_request(data: dict) -> dict:
    response = transport.post(
        f"{_authority()}/token",
        data={
            **data,
            "client_id": settings.MS_CLIENT_ID,
            "client_secret": settings.MS_CLIENT_SECRET,
            "scope": " ".join(SCOPES),
        },
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        raise MicrosoftError(
            "Microsoft a refusé l'échange de jetons.", response.status_code
        )
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
    token = account.refresh_token
    if not token:
        raise MicrosoftError("Aucun jeton de rafraîchissement.", 401)
    try:
        data = _token_request({"refresh_token": token, "grant_type": "refresh_token"})
    except MicrosoftError:
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
    granted = (data.get("scope") or "").split()
    if granted:
        account.scopes = sorted(set(granted))
    account.status = AccountStatus.OK
    account.save()


def userinfo(access_token: str) -> dict:
    response = transport.get(
        f"{GRAPH_URL}/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        raise MicrosoftError(
            "Impossible de lire le compte Microsoft.", response.status_code
        )
    return response.json()


def valid_access_token(account: OAuthAccount) -> str:
    if account.token_expired or not account.access_token:
        refresh(account)
    return account.access_token or ""


class GraphClient:
    """Authenticated Graph calls, refreshing once on 401."""

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
            raise MicrosoftError(
                f"Microsoft Graph injoignable ({exc.__class__.__name__})."
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
            raise MicrosoftError(
                f"Microsoft Graph a répondu {response.status_code}. {detail}".strip(),
                response.status_code,
            )
        return response
