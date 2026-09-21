"""Account e-mails. Links point to front-end routes (French slugs)."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.core.emails import send_templated_email

from .tokens import make_email_token


def send_verification_email(user):
    url = f"{settings.SITE_URL}/verifier-email/{make_email_token(user)}"
    send_templated_email(
        to=user.email,
        subject="Confirme ton adresse e-mail",
        template="verify_email",
        context={"name": user.display_name, "url": url},
    )


def send_password_reset_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = f"{settings.SITE_URL}/reinitialiser/{uid}/{token}"
    send_templated_email(
        to=user.email,
        subject="Réinitialisation de ton mot de passe",
        template="password_reset",
        context={"name": user.display_name, "username": user.username, "url": url},
    )
