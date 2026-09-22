"""External accounts and Drive links (SPEC §11).

One Google account and one Microsoft account per user (D12). Tokens are
stored encrypted (Fernet, apps.core.crypto): a database dump alone gives
nothing. `scopes` says what the account may do (Drive, Calendar): scopes
are asked incrementally, feature by feature.

A DriveLink is a file the user picked in Google Picker and attached to a
project or a task. The application only ever sees files it created or the
user picked (scope drive.file, SPECIFICATIONS §7).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core import crypto
from apps.core.models import TimeStampedModel
from apps.projects.models import Project
from apps.projects.querysets import ProjectScopedQuerySet
from apps.tasks.models import Task

SCOPE_DRIVE = "https://www.googleapis.com/auth/drive.file"
SCOPE_CALENDAR = "https://www.googleapis.com/auth/calendar"
SCOPE_EMAIL = "https://www.googleapis.com/auth/userinfo.email"
FEATURE_SCOPES = {"drive": SCOPE_DRIVE, "calendar": SCOPE_CALENDAR}


class Provider(models.TextChoices):
    GOOGLE = "google", "Google"
    MICROSOFT = "microsoft", "Microsoft"


class AccountStatus(models.TextChoices):
    OK = "ok", "Connecté"
    NEEDS_REAUTH = "needs_reauth", "Reconnexion nécessaire"


class OAuthAccount(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oauth_accounts",
    )
    provider = models.CharField(max_length=10, choices=Provider.choices)
    account_email = models.CharField(max_length=254, blank=True)
    access_token_enc = models.TextField(blank=True)
    refresh_token_enc = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=14, choices=AccountStatus.choices, default=AccountStatus.OK
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider"], name="oauthaccount_one_per_provider"
            )
        ]

    def __str__(self):
        return f"{self.user} · {self.provider} · {self.account_email}"

    # --- Tokens (never stored in clear) --------------------------------------
    @property
    def access_token(self) -> str | None:
        return crypto.decrypt(self.access_token_enc) if self.access_token_enc else None

    @access_token.setter
    def access_token(self, value: str | None):
        self.access_token_enc = crypto.encrypt(value) if value else ""

    @property
    def refresh_token(self) -> str | None:
        return (
            crypto.decrypt(self.refresh_token_enc) if self.refresh_token_enc else None
        )

    @refresh_token.setter
    def refresh_token(self, value: str | None):
        self.refresh_token_enc = crypto.encrypt(value) if value else ""

    @property
    def token_expired(self) -> bool:
        return self.token_expires_at is None or self.token_expires_at <= timezone.now()

    def has_feature(self, feature: str) -> bool:
        return FEATURE_SCOPES.get(feature) in (self.scopes or [])

    @property
    def features(self) -> list[str]:
        return [name for name in FEATURE_SCOPES if self.has_feature(name)]

    @property
    def usable(self) -> bool:
        return self.status == AccountStatus.OK and bool(self.refresh_token_enc)


class DriveLink(TimeStampedModel):
    """A Drive file attached to a project (task optional). The project
    always carries the rights; `task` is a finer place to show it."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="drive_links"
    )
    task = models.ForeignKey(
        Task,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="drive_links",
    )
    drive_file_id = models.CharField(max_length=200)
    name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120, blank=True)
    icon_url = models.URLField(max_length=500, blank=True)
    web_view_url = models.URLField(max_length=500, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = ProjectScopedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "task", "drive_file_id"],
                name="drivelink_unique_file_per_place",
                nulls_distinct=False,
            )
        ]

    def __str__(self):
        return self.name


# Importable paths for drf-spectacular's ENUM_NAME_OVERRIDES.
PROVIDER_CHOICES = Provider.choices
ACCOUNT_STATUS_CHOICES = AccountStatus.choices
