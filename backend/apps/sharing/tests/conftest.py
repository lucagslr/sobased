"""Sharing fixtures: an editor with a cover (PNG) and a mix (WAV) in project A,
a viewer, a stranger, and an anonymous client for the public page."""

import pytest
from django.test import Client

from apps.files.tests.conftest import (  # noqa: F401,F811  (re-exported)
    client_for,
    editor,
    editor_api,
    make_asset,
    pdf_upload,
    png_upload,
    stranger_api,
    tree,
    viewer,
    viewer_api,
    wav_upload,
)
from apps.sharing.models import ShareLink


@pytest.fixture
def cover(tree, editor):  # noqa: F811
    return make_asset(
        tree["A"], editor, name="Cover", upload=png_upload(size=(640, 480))
    )


@pytest.fixture
def mix(tree, editor):  # noqa: F811
    return make_asset(tree["A"], editor, name="Mix", upload=wav_upload(seconds=0.5))


@pytest.fixture
def visitor():
    """Someone with no account: a plain Django client (its own session)."""
    return Client()


def create_link(api, **payload) -> dict:
    response = api.post("/api/share-links/", payload, format="json")
    assert response.status_code == 201, response.data
    return response.data


def token_of(data: dict) -> str:
    return data["url"].rsplit("/", 1)[-1]


def link_of(data: dict) -> ShareLink:
    return ShareLink.objects.get(pk=data["id"])
