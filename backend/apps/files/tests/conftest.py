"""Files fixtures: the reference tree, one member per role on R, and tiny
generated uploads (PNG, PDF, WAV) so that no binary fixture lives in git.

Reference tree (apps/projects/tests/factories.py):
W: R > (A > (A1 > A1x, A2), B), R2      W2: Z
"""

import io
import math
import struct
import wave

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.tests.factories import UserFactory
from apps.files import services
from apps.files.models import Asset
from apps.projects.tests.factories import Tree, grant
from apps.tasks.tests.conftest import client_for  # noqa: F401  (re-exported)


@pytest.fixture
def tree(db):
    return Tree()


@pytest.fixture
def editor(tree):
    user = UserFactory(username="editor")
    grant(user, tree["R"], "editor")
    return user


@pytest.fixture
def editor_api(editor):
    return client_for(editor)


@pytest.fixture
def commenter(tree):
    user = UserFactory(username="commenter")
    grant(user, tree["R"], "commenter")
    return user


@pytest.fixture
def commenter_api(commenter):
    return client_for(commenter)


@pytest.fixture
def viewer(tree):
    user = UserFactory(username="viewer")
    grant(user, tree["R"], "viewer")
    return user


@pytest.fixture
def viewer_api(viewer):
    return client_for(viewer)


@pytest.fixture
def stranger_api(db):
    """Logged in, member of nothing."""
    return client_for(UserFactory(username="stranger"))


def png_upload(name="cover.png", size=(64, 48)) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, "orange").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def pdf_upload(name="dossier.pdf", pages=3) -> SimpleUploadedFile:
    body = b"%PDF-1.4\n"
    for index in range(pages):
        body += f"{index + 1} 0 obj<</Type /Page>>endobj\n".encode()
    body += b"9 0 obj<</Type /Pages>>endobj\n%%EOF"
    return SimpleUploadedFile(name, body, content_type="application/pdf")


def wav_upload(name="mix.wav", seconds=0.5, rate=8000) -> SimpleUploadedFile:
    """A short 440 Hz sine: enough for ffmpeg to find a duration and peaks."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / rate)))
            for i in range(int(rate * seconds))
        )
        handle.writeframes(frames)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="audio/wav")


def text_upload(name="notes.txt") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"just words\n", content_type="text/plain")


def make_asset(project, author, name="Cover", upload=None, **fields):
    """An asset with its v1, the way the API creates it (no Celery run)."""
    asset = Asset.objects.create(
        project=project, name=name, created_by=author, **fields
    )
    services.add_version(asset, upload or png_upload(), author)
    asset.refresh_from_db()
    return asset


@pytest.fixture
def asset(tree, editor):
    return make_asset(tree["A"], editor)
