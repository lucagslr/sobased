"""Profile, preferences, avatar and user search."""

from io import BytesIO

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def _png(width=800, height=400) -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "#c8e6c9").save(buffer, format="PNG")
    return SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")


# --- /api/me/ -------------------------------------------------------------------


def test_me_requires_authentication(api):
    assert api.get("/api/me/").status_code == 401


def test_me_returns_profile_and_defaults(auth_api):
    data = auth_api.get("/api/me/").data

    assert data["username"] == "luca"
    assert data["email_verified"] is True
    assert data["timezone"] == "Europe/Zurich"
    assert data["theme"] == "system"
    assert data["daily_digest_enabled"] is True
    assert data["daily_digest_time"] == "08:00:00"
    assert data["avatar_url"] is None
    assert "password" not in data


def test_me_update_preferences(auth_api, user):
    response = auth_api.patch(
        "/api/me/",
        {
            "first_name": "Luca",
            "theme": "dark",
            "timezone": "America/Montreal",
            "daily_digest_time": "07:30",
            "email_on_mention": False,
        },
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert (user.theme, user.timezone) == ("dark", "America/Montreal")
    assert user.daily_digest_time.isoformat() == "07:30:00"
    assert user.email_on_mention is False


@pytest.mark.parametrize(
    "payload", [{"timezone": "Mars/Olympus"}, {"theme": "neon"}, {"email": "nope"}]
)
def test_me_rejects_invalid_values(auth_api, payload):
    assert auth_api.patch("/api/me/", payload, format="json").status_code == 400


def test_username_cannot_be_changed(auth_api, user):
    auth_api.patch("/api/me/", {"username": "other"}, format="json")

    user.refresh_from_db()
    assert user.username == "luca"


def test_email_change_needs_password_and_resets_verification(auth_api, user):
    response = auth_api.patch("/api/me/", {"email": "new@example.org"}, format="json")
    assert response.status_code == 400
    assert "current_password" in response.data

    response = auth_api.patch(
        "/api/me/",
        {"email": "New@Example.org", "current_password": DEFAULT_PASSWORD},
        format="json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.email == "new@example.org"
    assert user.email_verified_at is None
    assert mail.outbox[0].to == ["new@example.org"]


def test_email_change_refuses_an_address_already_used(auth_api):
    UserFactory(email="taken@example.org")

    response = auth_api.patch(
        "/api/me/",
        {"email": "TAKEN@example.org", "current_password": DEFAULT_PASSWORD},
        format="json",
    )
    assert response.status_code == 400


# --- Avatar -----------------------------------------------------------------------


def test_avatar_upload_is_normalised_and_served_to_signed_in_users(auth_api, user, api):
    response = auth_api.put("/api/me/avatar/", {"avatar": _png()}, format="multipart")

    assert response.status_code == 200
    url = response.data["avatar_url"]
    assert url.startswith("/api/users/luca/avatar/?v=")
    user.refresh_from_db()
    with Image.open(user.avatar.path) as stored:
        assert stored.format == "WEBP"
        assert stored.size == (256, 256)

    served = auth_api.get(url)
    assert served.status_code == 200
    assert served["Content-Type"] == "image/webp"
    assert served["X-Content-Type-Options"] == "nosniff"
    # Anonymous visitors get nothing.
    api.logout()
    assert api.get(url).status_code == 401


def test_avatar_replacement_deletes_the_old_file(auth_api, user):
    auth_api.put("/api/me/avatar/", {"avatar": _png()}, format="multipart")
    user.refresh_from_db()
    old_path = user.avatar.path

    auth_api.put("/api/me/avatar/", {"avatar": _png(300, 300)}, format="multipart")
    user.refresh_from_db()

    import os

    assert not os.path.exists(old_path)
    assert os.path.exists(user.avatar.path)


def test_avatar_rejects_non_images(auth_api):
    fake = SimpleUploadedFile("evil.png", b"<script>alert(1)</script>", "image/png")

    response = auth_api.put("/api/me/avatar/", {"avatar": fake}, format="multipart")
    assert response.status_code == 400


def test_avatar_delete(auth_api, user):
    auth_api.put("/api/me/avatar/", {"avatar": _png()}, format="multipart")

    response = auth_api.delete("/api/me/avatar/")
    assert response.status_code == 200
    assert response.data["avatar_url"] is None


def test_accel_redirect_header_behind_the_proxy(auth_api, settings):
    auth_api.put("/api/me/avatar/", {"avatar": _png()}, format="multipart")
    settings.PROTECTED_MEDIA_ACCEL = True

    response = auth_api.get("/api/users/luca/avatar/")

    # Django sends no body: Caddy streams the file named by this header.
    assert response["X-Accel-Redirect"].startswith("/avatars/")
    assert response.content == b""


# --- User search --------------------------------------------------------------------


def test_user_search_exposes_only_public_fields(auth_api):
    UserFactory(username="helder", first_name="Helder", last_name="S", phone="079")
    UserFactory(username="hidden", is_active=False)

    response = auth_api.get("/api/users/search/?q=he")

    assert response.status_code == 200
    assert response.data == [
        {"username": "helder", "display_name": "Helder S", "avatar_url": None}
    ]


def test_user_search_matches_names_and_ignores_at_sign(auth_api):
    UserFactory(username="shorty7g", first_name="Noam", last_name="Antonio")

    assert len(auth_api.get("/api/users/search/?q=noa").data) == 1
    assert len(auth_api.get("/api/users/search/?q=@short").data) == 1


def test_user_search_needs_two_characters_and_excludes_me(auth_api):
    assert auth_api.get("/api/users/search/?q=l").data == []
    assert auth_api.get("/api/users/search/?q=luca").data == []


def test_user_search_requires_authentication(api):
    assert api.get("/api/users/search/?q=lu").status_code == 401
