import pytest

pytestmark = pytest.mark.django_db


def test_health(api):
    response = api.get("/api/health/")

    assert response.status_code == 200
    assert response.data == {"status": "ok"}


def test_openapi_schema_is_generated_without_errors(auth_api):
    response = auth_api.get("/api/schema/")

    assert response.status_code == 200
    assert b"/api/auth/login/" in response.content


def test_site_info_is_public_and_reflects_settings(api, settings):
    settings.HOSTING_LOCATION = "eu"
    settings.HOSTING_PROVIDER = "LWS (France)"
    settings.PRIVACY_CONTACT_EMAIL = "contact@example.org"
    response = api.get("/api/site/")
    assert response.status_code == 200
    assert response.data == {
        "name": "Faiblegraine",
        "hosting_location": "eu",
        "hosting_provider": "LWS (France)",
        "contact_email": "contact@example.org",
    }
