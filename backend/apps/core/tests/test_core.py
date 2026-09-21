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
