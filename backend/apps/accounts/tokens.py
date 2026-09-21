"""Signed, expiring tokens for e-mail verification.

The token carries the user id and the e-mail it was issued for, so a token sent
to an old address stops working once the user changes e-mail. Nothing is
stored in the database. Password reset uses Django's own token generator.
"""

from django.conf import settings
from django.core import signing

_SALT = "accounts.verify-email"


def make_email_token(user) -> str:
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=_SALT)


def read_email_token(token: str) -> dict | None:
    """Return {"uid", "email"} or None if the token is invalid or expired."""
    try:
        return signing.loads(
            token, salt=_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE
        )
    except signing.BadSignature:  # SignatureExpired is a subclass
        return None
