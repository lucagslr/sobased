"""Symmetric encryption for secrets that must be read back (Fernet).

Used for the copy of a share-link token (editors need to re-display the
URL) and, from phase 10, for OAuth refresh tokens. The key comes from
FERNET_KEY; a missing or malformed key fails loudly at first use rather
than storing something unreadable.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@lru_cache(maxsize=1)
def fernet() -> Fernet:
    key = (settings.FERNET_KEY or "").strip()
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            "FERNET_KEY is missing or invalid. Generate one with: python -c "
            '"import base64,os; print(base64.urlsafe_b64encode(os.urandom(32))'
            '.decode())"'
        ) from exc


def encrypt(text: str) -> str:
    return fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str | None:
    """None when the value was encrypted with another key (or tampered)."""
    try:
        return fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
