import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory

from .factories import Tree


@pytest.fixture
def tree(db):
    return Tree()


@pytest.fixture
def member(db):
    """The user whose rights are under test. Starts with no membership."""
    return UserFactory(username="member")


@pytest.fixture
def member_api(member):
    client = APIClient()
    client.force_login(member)
    return client


@pytest.fixture
def owner_api(tree):
    client = APIClient()
    client.force_login(tree.owner)
    return client
