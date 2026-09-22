"""Protected share links (SPEC §10).

A ShareLink points at one version, one asset (always its latest version at
opening time) or an ordered list of assets (playlist). Its secret is a
32-byte token that only ever travels in the URL: the database keeps its
SHA-256 (for lookups) and a Fernet-encrypted copy (so that editors can see
the URL again). Optional password (Argon2, like user passwords), expiry,
view / play quotas, download switch, watermark switch, recipient label
(used in the watermark text), revocation.

Every access is journaled with a truncated IP (nLPD/RGPD).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.files.models import Asset, AssetVersion
from apps.projects.models import Project
from apps.projects.querysets import ProjectScopedQuerySet


class Target(models.TextChoices):
    VERSION = "version", "Une version précise"
    ASSET = "asset", "Un fichier (dernière version)"
    PLAYLIST = "playlist", "Une sélection de fichiers"


class State(models.TextChoices):
    ACTIVE = "active", "Actif"
    EXPIRED = "expired", "Expiré"
    EXHAUSTED = "exhausted", "Épuisé"
    REVOKED = "revoked", "Révoqué"


class Event(models.TextChoices):
    VIEW = "view", "Ouverture"
    PLAY = "play", "Écoute"
    DOWNLOAD = "download", "Téléchargement"
    PASSWORD_FAILED = "password_failed", "Mot de passe refusé"


class ShareLink(TimeStampedModel):
    # The project carries the rights (editors of it manage the link); every
    # targeted asset belongs to it or to one of its descendants.
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="share_links"
    )
    target_type = models.CharField(max_length=10, choices=Target.choices)
    version = models.ForeignKey(
        AssetVersion,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    asset = models.ForeignKey(
        Asset,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    title = models.CharField(max_length=200)
    token_hash = models.CharField(max_length=64, unique=True)
    token_encrypted = models.TextField()
    password_hash = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_views = models.PositiveIntegerField(null=True, blank=True)
    max_plays = models.PositiveIntegerField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    play_count = models.PositiveIntegerField(default=0)
    allow_download = models.BooleanField(default=False)
    watermark = models.BooleanField(default=True)
    recipient_label = models.CharField(max_length=120, blank=True)
    notify_on_open = models.BooleanField(default=False)
    first_opened_at = models.DateTimeField(null=True, blank=True)
    last_opened_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = ProjectScopedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    @property
    def state(self) -> str:
        """Computed, never stored (SPECIFICATIONS §6)."""
        if self.revoked_at is not None:
            return State.REVOKED
        if self.expires_at is not None and self.expires_at <= timezone.now():
            return State.EXPIRED
        if self.max_views is not None and self.view_count >= self.max_views:
            return State.EXHAUSTED
        if self.max_plays is not None and self.play_count >= self.max_plays:
            return State.EXHAUSTED
        return State.ACTIVE

    @property
    def is_active(self) -> bool:
        return self.state == State.ACTIVE

    @property
    def watermark_text(self) -> str:
        return self.recipient_label or "SOBASED · confidentiel"


class ShareLinkItem(models.Model):
    """One asset of a playlist, in order."""

    share_link = models.ForeignKey(
        ShareLink, on_delete=models.CASCADE, related_name="items"
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="+")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["share_link", "asset"], name="sharelinkitem_unique_asset"
            )
        ]


class ShareAccessLog(models.Model):
    """Who opened what, without identifying anyone: truncated IP, user agent."""

    share_link = models.ForeignKey(
        ShareLink, on_delete=models.CASCADE, related_name="access_log"
    )
    version = models.ForeignKey(
        AssetVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    event = models.CharField(max_length=16, choices=Event.choices)
    ip_truncated = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["share_link", "created_at"])]


# Importable paths for drf-spectacular's ENUM_NAME_OVERRIDES.
SHARE_TARGET_CHOICES = Target.choices
SHARE_STATE_CHOICES = State.choices
SHARE_EVENT_CHOICES = Event.choices
