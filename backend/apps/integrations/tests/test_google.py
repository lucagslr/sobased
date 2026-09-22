"""OAuth round trip, token storage, refresh, disconnection, Picker config."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.integrations import google
from apps.integrations.google import DriveClient, GoogleError
from apps.integrations.models import SCOPE_DRIVE, OAuthAccount

from .conftest import client_for, connect_google

pytestmark = pytest.mark.django_db


def test_disabled_without_credentials(editor_api, settings):
    settings.GOOGLE_ENABLED = False
    state = editor_api.get("/api/integrations/").data
    assert state["google"] == {
        "enabled": False,
        "connected": False,
        "email": "",
        "features": [],
        "status": "",
        "picker": False,
    }
    assert editor_api.get("/api/integrations/google/connect/").status_code == 400


def test_connect_url_and_callback(editor_api, editor, fake_google):
    response = editor_api.get("/api/integrations/google/connect/?features=drive")
    assert response.status_code == 200
    url = response.data["url"]
    assert url.startswith(google.AUTH_URL)
    assert "access_type=offline" in url and "include_granted_scopes=true" in url
    assert "drive.file" in url and "userinfo.email" in url
    state = parse_qs(urlparse(url).query)["state"][0]
    assert google.read_state(state)["u"] == editor.pk

    back = editor_api.get(
        "/api/integrations/google/callback/", {"code": "abc", "state": state}
    )
    assert back.status_code == 302 and back["Location"].endswith("?google=ok")
    account = OAuthAccount.objects.get(user=editor, provider="google")
    assert account.account_email == "demo@gmail.com"
    assert account.access_token == "at-1" and account.refresh_token == "rt-1"
    # Nothing readable in the stored columns.
    assert (
        "at-1" not in account.access_token_enc
        and "rt-1" not in account.refresh_token_enc
    )
    assert account.has_feature("drive") and not account.has_feature("calendar")
    state_data = editor_api.get("/api/integrations/").data["google"]
    assert state_data["connected"] and state_data["email"] == "demo@gmail.com"
    assert state_data["features"] == ["drive"] and state_data["picker"] is True


def test_callback_refuses_a_foreign_or_stale_state(editor_api, editor, fake_google):
    other = UserFactory(username="other")
    url = google.authorization_url(other, [SCOPE_DRIVE])
    state = parse_qs(urlparse(url).query)["state"][0]
    back = editor_api.get(
        "/api/integrations/google/callback/", {"code": "abc", "state": state}
    )
    assert back["Location"].endswith("?google=refus")
    assert not OAuthAccount.objects.filter(user=editor).exists()
    bad = editor_api.get(
        "/api/integrations/google/callback/", {"code": "abc", "state": "x"}
    )
    assert bad["Location"].endswith("?google=refus")


def test_refresh_when_expired_and_needs_reauth(fake_google, editor):
    account = connect_google(editor)
    account.token_expires_at = timezone.now() - timedelta(minutes=1)
    account.save()
    assert google.valid_access_token(account) == "at-1"  # refreshed
    assert not account.token_expired
    # A 401 from Drive triggers one refresh then a retry.
    fake_google.unauthorized_once = True
    fake_google.add_file("cover.png", "image/png", file_id="pick1")
    data = DriveClient(account).get_file("pick1")
    assert data["name"] == "cover.png"
    assert account.access_token == "at-2"
    # Google refuses the refresh token: the account asks for a new consent.
    fake_google.fail_refresh = True
    account.token_expires_at = timezone.now() - timedelta(minutes=1)
    account.save()
    with pytest.raises(GoogleError):
        google.valid_access_token(account)
    account.refresh_from_db()
    assert account.status == "needs_reauth" and not account.usable


def test_disconnect_revokes_and_forgets(editor_api, editor, fake_google):
    connect_google(editor)
    response = editor_api.delete("/api/integrations/google/")
    assert response.status_code == 204
    assert not OAuthAccount.objects.filter(user=editor).exists()
    assert any(url == google.REVOKE_URL for _, url, _ in fake_google.calls)


def test_picker_config(editor_api, editor, fake_google):
    assert editor_api.get("/api/integrations/google/picker-config/").status_code == 400
    connect_google(editor)
    data = editor_api.get("/api/integrations/google/picker-config/").data
    assert data == {
        "api_key": "api-key",
        "client_id": "client-id",
        "app_id": "123456",
        "access_token": "at-0",
    }


def test_one_google_account_per_user(editor):
    connect_google(editor)
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        connect_google(editor, email="second@gmail.com")


def test_accounts_are_private(editor, fake_google):
    connect_google(editor)
    stranger = client_for(UserFactory(username="stranger"))
    assert stranger.get("/api/integrations/").data["google"]["connected"] is False
