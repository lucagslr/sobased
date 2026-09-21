from datetime import UTC, datetime, timedelta

import factory
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.projects.tests.factories import Tree, grant
from apps.tasks.models import Task


class TaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Task

    title = factory.Sequence(lambda n: f"Tâche {n}")


def day(offset: int = 0) -> datetime:
    """Midnight UTC, `offset` days from today: an all-day date."""
    today = timezone.localdate()
    return datetime(today.year, today.month, today.day, tzinfo=UTC) + timedelta(
        days=offset
    )


def iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def tree(db):
    return Tree()


@pytest.fixture
def editor(tree):
    """Editor of the root project R (so of A, A1, A1x, A2, B too)."""
    user = UserFactory(username="editor")
    grant(user, tree["R"], "editor")
    return user


@pytest.fixture
def editor_api(editor):
    return client_for(editor)


@pytest.fixture
def make_member(tree):
    def _make(username, role, scope="R"):
        user = UserFactory(username=username)
        grant(user, tree[scope], role)
        return user

    return _make
