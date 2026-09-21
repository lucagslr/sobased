"""Sign-up, e-mail verification, login, logout, password reset and change."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail, signing
from rest_framework.test import APIClient

from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.accounts.tokens import make_email_token

User = get_user_model()
pytestmark = pytest.mark.django_db

REGISTER = {
    "username": "helder",
    "email": "Helder@Example.org",
    "password": "un-mot-de-passe-solide",
    "accept_privacy": True,
}


# --- Session probe ------------------------------------------------------------


def test_session_probe_never_fails_and_sets_the_csrf_cookie(api, user):
    response = api.get("/api/auth/session/")
    assert response.status_code == 200
    assert response.data == {"user": None}
    assert "csrftoken" in response.cookies

    api.force_login(user)
    assert api.get("/api/auth/session/").data["user"]["username"] == "luca"


# --- Registration -------------------------------------------------------------


def test_register_creates_user_logs_in_and_sends_verification(api):
    response = api.post("/api/auth/register/", REGISTER)

    assert response.status_code == 201
    user = User.objects.get(username="helder")
    assert user.email == "helder@example.org"  # stored lower-cased
    assert user.privacy_accepted_at is not None
    assert user.email_verified_at is None
    assert user.password.startswith("md5$") or user.password.startswith("argon2")
    assert "password" not in response.data
    # The session is open right away.
    assert api.get("/api/me/").status_code == 200
    # One e-mail with a verification link, in both text and HTML.
    assert len(mail.outbox) == 1
    assert "/verifier-email/" in mail.outbox[0].body
    assert mail.outbox[0].alternatives[0][1] == "text/html"


@pytest.mark.parametrize(
    "override, field",
    [
        ({"username": "LUCA"}, "username"),  # case-insensitive duplicate
        ({"email": "LUCA@example.org"}, "email"),
        ({"username": "a b"}, "username"),  # invalid characters
        ({"username": "me@home"}, "username"),  # "@" would break mentions
        ({"password": "court"}, "password"),
        ({"password": "12345678901234"}, "password"),  # numeric only
        ({"accept_privacy": False}, "accept_privacy"),
    ],
)
def test_register_rejects_invalid_input(api, user, override, field):
    response = api.post("/api/auth/register/", {**REGISTER, **override})

    assert response.status_code == 400
    assert field in response.data


def test_register_closed(api, settings):
    settings.REGISTRATION_OPEN = False

    assert api.post("/api/auth/register/", REGISTER).status_code == 403
    assert not User.objects.exists()


# --- E-mail verification --------------------------------------------------------


def test_verify_email(api):
    user = UserFactory(email_verified_at=None)

    response = api.post("/api/auth/verify-email/", {"token": make_email_token(user)})

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.email_verified


def test_verify_email_rejects_garbage_and_expired_tokens(api, settings):
    user = UserFactory(email_verified_at=None)
    assert api.post("/api/auth/verify-email/", {"token": "nope"}).status_code == 400

    settings.EMAIL_VERIFICATION_MAX_AGE = -1
    token = make_email_token(user)
    assert api.post("/api/auth/verify-email/", {"token": token}).status_code == 400
    user.refresh_from_db()
    assert not user.email_verified


def test_verification_token_dies_when_email_changes(api):
    user = UserFactory(email_verified_at=None)
    token = make_email_token(user)
    user.email = "other@example.org"
    user.save()

    assert api.post("/api/auth/verify-email/", {"token": token}).status_code == 400


def test_token_signed_with_another_salt_is_rejected(api):
    user = UserFactory(email_verified_at=None)
    forged = signing.dumps({"uid": user.pk, "email": user.email}, salt="other")

    assert api.post("/api/auth/verify-email/", {"token": forged}).status_code == 400


def test_resend_verification(auth_api, user):
    user.email_verified_at = None
    user.save()

    assert auth_api.post("/api/auth/verify-email/resend/").status_code == 200
    assert len(mail.outbox) == 1


# --- Login / logout ---------------------------------------------------------------


def test_login_is_case_insensitive_and_opens_a_session(api, user):
    response = api.post(
        "/api/auth/login/", {"username": "LUCA", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    assert response.data["username"] == "luca"
    assert api.get("/api/me/").status_code == 200


def test_login_with_wrong_password(api, user):
    response = api.post("/api/auth/login/", {"username": "luca", "password": "nope"})

    assert response.status_code == 400
    assert api.get("/api/me/").status_code == 401


def test_login_locks_a_username_after_too_many_failures(api, user, settings):
    settings.LOGIN_MAX_FAILURES_PER_HOUR = 3
    # Lift the per-IP throttle so that this test isolates the per-username lock.
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "login": "1000/min",
        },
    }
    for _ in range(3):
        api.post("/api/auth/login/", {"username": "luca", "password": "nope"})

    # Even the right password is refused while the lock is active...
    response = api.post(
        "/api/auth/login/", {"username": "Luca", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 429
    # ...and another account is not affected.
    UserFactory(username="noam")
    response = api.post(
        "/api/auth/login/", {"username": "noam", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200


def test_login_is_throttled_per_ip(api, user):
    codes = [
        api.post("/api/auth/login/", {"username": f"x{i}", "password": "y"}).status_code
        for i in range(6)
    ]

    assert codes[:5] == [400] * 5
    assert codes[5] == 429


def test_login_requires_csrf_token(user):
    strict = APIClient(enforce_csrf_checks=True)

    response = strict.post(
        "/api/auth/login/", {"username": "luca", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["detail"].startswith("Session expirée")

    # With the cookie from /api/auth/csrf/ echoed in the header, it works.
    strict.get("/api/auth/csrf/")
    token = strict.cookies["csrftoken"].value
    response = strict.post(
        "/api/auth/login/",
        {"username": "luca", "password": DEFAULT_PASSWORD},
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200


def test_inactive_user_cannot_login(api, user):
    user.is_active = False
    user.save()

    response = api.post(
        "/api/auth/login/", {"username": "luca", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 400


def test_logout(auth_api):
    assert auth_api.post("/api/auth/logout/").status_code == 200
    assert auth_api.get("/api/me/").status_code == 401


# --- Password reset and change -------------------------------------------------------


def _reset_link_parts(body: str) -> tuple[str, str]:
    match = re.search(r"/reinitialiser/([^/\s]+)/([^/\s]+)", body)
    return match.group(1), match.group(2)


def test_password_reset_flow(api, user):
    assert (
        api.post("/api/auth/password/reset/", {"email": "LUCA@example.org"}).status_code
        == 200
    )
    assert len(mail.outbox) == 1
    uid, token = _reset_link_parts(mail.outbox[0].body)

    payload = {"uid": uid, "token": token, "new_password": "nouveau-passe-solide"}
    assert api.post("/api/auth/password/reset/confirm/", payload).status_code == 200
    user.refresh_from_db()
    assert user.check_password("nouveau-passe-solide")
    # The link works only once.
    assert api.post("/api/auth/password/reset/confirm/", payload).status_code == 400


def test_password_reset_does_not_reveal_unknown_emails(api):
    response = api.post("/api/auth/password/reset/", {"email": "ghost@example.org"})

    assert response.status_code == 200
    assert mail.outbox == []


def test_password_reset_confirm_rejects_bad_token_and_weak_password(api, user):
    api.post("/api/auth/password/reset/", {"email": user.email})
    uid, token = _reset_link_parts(mail.outbox[0].body)

    bad = {"uid": uid, "token": "bad-token", "new_password": "nouveau-passe-solide"}
    assert api.post("/api/auth/password/reset/confirm/", bad).status_code == 400
    weak = {"uid": uid, "token": token, "new_password": "court"}
    response = api.post("/api/auth/password/reset/confirm/", weak)
    assert response.status_code == 400
    assert "new_password" in response.data


def test_password_change_keeps_the_current_session(auth_api, user):
    wrong = {"current_password": "nope", "new_password": "nouveau-passe-solide"}
    assert auth_api.post("/api/auth/password/change/", wrong).status_code == 400

    right = {**wrong, "current_password": DEFAULT_PASSWORD}
    assert auth_api.post("/api/auth/password/change/", right).status_code == 200
    assert auth_api.get("/api/me/").status_code == 200
    user.refresh_from_db()
    assert user.check_password("nouveau-passe-solide")
