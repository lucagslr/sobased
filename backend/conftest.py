import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _clean_cache():
    """Throttle counters and login-failure counters live in the cache."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _media_tmpdir(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user(db):
    from apps.accounts.tests.factories import UserFactory

    return UserFactory(username="luca", email="luca@example.org")


@pytest.fixture
def auth_api(api, user):
    api.force_authenticate(user=None)  # make sure we use a real session
    api.force_login(user)
    return api
