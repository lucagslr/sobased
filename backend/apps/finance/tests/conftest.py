"""Bookkeeping fixtures: the reference tree with a treasurer (editor of R with
both finance flags), an editor WITHOUT finance rights, and a viewer with
finance view only.

Reference tree (apps/projects/tests/factories.py):
W: R > (A > (A1 > A1x, A2), B), R2      W2: Z
"""

import io
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.tests.factories import UserFactory
from apps.finance.models import Category, Kind, Transaction
from apps.projects.tests.factories import Tree, grant
from apps.tasks.tests.conftest import client_for  # noqa: F401  (re-exported)

TODAY = date.today()


@pytest.fixture
def tree(db):
    return Tree()


@pytest.fixture
def categories(tree):
    """The default categories of both workspaces, by name (for W).

    The test factories build bare workspaces (no create_defaults()): seed
    them here, the way WorkspaceViewSet does on creation.
    """
    for workspace in (tree.workspace, tree.other_workspace):
        if not workspace.categories.exists():
            Category.create_defaults(workspace)
    return {c.name: c for c in Category.objects.filter(workspace=tree.workspace)}


@pytest.fixture
def treasurer(tree):
    user = UserFactory(username="treasurer")
    grant(user, tree["R"], "editor", can_view_finance=True, can_edit_finance=True)
    return user


@pytest.fixture
def treasurer_api(treasurer):
    return client_for(treasurer)


@pytest.fixture
def blind_editor(tree):
    """Editor of R who may not see money."""
    user = UserFactory(username="blind")
    grant(user, tree["R"], "editor")
    return user


@pytest.fixture
def finance_viewer(tree):
    """Viewer of R who may see money but not touch it."""
    user = UserFactory(username="fviewer")
    grant(user, tree["R"], "viewer", can_view_finance=True)
    return user


def make_transaction(project, category, **fields):
    fields.setdefault("kind", Kind.EXPENSE)
    fields.setdefault("amount", Decimal("100.00"))
    fields.setdefault("date", TODAY)
    fields.setdefault("label", "Location studio")
    return Transaction.objects.create(project=project, category=category, **fields)


def days(offset: int) -> date:
    return TODAY + timedelta(days=offset)


def png_upload(name="ticket.png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def pdf_upload(name="facture.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name, b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF", content_type="application/pdf"
    )
