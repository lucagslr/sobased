"""Custom user model.

Login is by username + password. The e-mail is mandatory (invitations,
notifications, password reset) and must be verified before it can be used to
receive invitations: see SPECIFICATIONS.md §1.4.
"""

from datetime import time

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

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
    # content) but every personal field is wiped. Implemented in phase 13.
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
        """Full name when known, username otherwise."""
        return self.get_full_name().strip() or self.username

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None
