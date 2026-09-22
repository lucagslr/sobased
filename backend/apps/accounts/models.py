"""Custom user model.

Login is by username + password. The e-mail is mandatory (invitations,
notifications, password reset) and must be verified before it can be used to
receive invitations: see SPECIFICATIONS.md §1.4.
"""

import secrets
from datetime import time

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

# Letters, digits, dot, dash, underscore: keeps "@username" mentions unambiguous
# (Django's default validator also allows "@" and "+").
username_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_.-]{3,30}$",
    message=(
        "3 à 30 caractères : lettres sans accent, chiffres, point, tiret "
        "ou underscore."
    ),
)


class SobasedUserManager(UserManager):
    def get_by_natural_key(self, username):
        # Case-insensitive login: "Luca" and "luca" are the same account.
        return self.get(username__iexact=username)


class User(AbstractUser):
    class Theme(models.TextChoices):
        LIGHT = "light", "Clair"
        DARK = "dark", "Sombre"
        SYSTEM = "system", "Système"

    username = models.CharField(
        "nom d'utilisateur",
        max_length=30,
        unique=True,
        validators=[username_validator],
        error_messages={"unique": "Ce nom d'utilisateur est déjà pris."},
    )
    # Always stored lower-cased (see save()), so unique=True is case-insensitive.
    email = models.EmailField(
        "e-mail",
        unique=True,
        error_messages={"unique": "Un compte existe déjà avec cet e-mail."},
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)

    avatar = models.ImageField(upload_to="avatars/", blank=True)
    phone = models.CharField(max_length=30, blank=True)
    timezone = models.CharField(max_length=64, default="Europe/Zurich")
    theme = models.CharField(max_length=10, choices=Theme.choices, default=Theme.SYSTEM)

    # Notification preferences (SPEC §4). The digest itself arrives in phase 12.
    daily_digest_enabled = models.BooleanField(default=True)
    daily_digest_time = models.TimeField(default=time(8, 0))
    last_digest_sent_on = models.DateField(null=True, blank=True)
    email_on_mention = models.BooleanField(default=True)
    email_on_assignment = models.BooleanField(default=True)

    privacy_accepted_at = models.DateTimeField(null=True, blank=True)
    # Set when the account is deleted: the row stays (authorship of shared
    # content) but every personal field is wiped (services.anonymize).
    anonymized_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SobasedUserManager()

    class Meta:
        constraints = [
            # unique=True on username is case-sensitive; this one is not.
            models.UniqueConstraint(Lower("username"), name="user_username_ci_unique"),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        """Full name when known, username otherwise; a deleted account keeps
        signing its content, anonymously (SPEC §16)."""
        if self.anonymized_at:
            return "Utilisateur supprimé"
        return self.get_full_name().strip() or self.username

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


def export_path(export, filename: str) -> str:
    """exports/<user>/<random>.zip: the URL never reveals anything."""
    return f"exports/{export.user_id}/{secrets.token_hex(12)}.zip"


class DataExport(models.Model):
    """One request of "export my data" (SPEC §16): built by Celery, kept 7
    days, served through protected_file_response() only."""

    class Status(models.TextChoices):
        PENDING = "pending", "En préparation"
        READY = "ready", "Prêt"
        FAILED = "failed", "Échec"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="data_exports"
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    archive = models.FileField(upload_to=export_path, blank=True, max_length=200)
    size_bytes = models.BigIntegerField(default=0)
    error = models.CharField(max_length=200, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_available(self) -> bool:
        return (
            self.status == self.Status.READY
            and bool(self.archive)
            and self.expires_at is not None
            and self.expires_at > timezone.now()
        )
