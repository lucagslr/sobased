"""Assets and versions (SPEC §9), Untitled-style, for any kind of file.

An Asset is the thing ("cover finale", "mix titre 3"); an AssetVersion is one
file of it, numbered v1, v2... A version's file is never replaced: one makes
the next version. Comments hang on a version and carry an anchor that
depends on the kind: a time (audio, video), a rectangle in percent (image)
or a page (PDF). Derivatives (stream MP3, waveform peaks, thumbnail) are
computed by Celery after the upload and cached per version.

Files are never served through a public URL: views check the rights, then
apps.core.files.protected_file_response() delegates to Caddy (or streams).

Drive-referenced versions (`drive_file_id`) arrive with phase 10; the
columns exist so that the API shape does not change.
"""

import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.projects.models import Project
from apps.projects.querysets import ProjectScopedQuerySet
from apps.workspaces.models import Tag


class Kind(models.TextChoices):
    AUDIO = "audio", "Audio"
    IMAGE = "image", "Image"
    VIDEO = "video", "Vidéo"
    DOCUMENT = "document", "PDF / document"
    OTHER = "other", "Autre"


class Status(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    TO_VALIDATE = "to_validate", "À valider"
    APPROVED = "approved", "Validé"
    REJECTED = "rejected", "Refusé"


def version_path(version, filename: str) -> str:
    """assets/<project>/<random>.<ext>: nothing of the original name in the
    path (kept in `original_filename`), and no guessable URL."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    extension = "".join(c for c in extension if c.isalnum())[:8] or "bin"
    return f"assets/{version.asset.project_id}/{secrets.token_hex(12)}.{extension}"


def derivative_path(derivative, filename: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return (
        f"derived/{derivative.version.asset.project_id}/"
        f"{derivative.version_id}-{derivative.kind}-{secrets.token_hex(6)}.{extension}"
    )


class Asset(TimeStampedModel):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="assets"
    )
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.OTHER)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="assets")
    # Notified of status changes (phase 12): creator, version authors and
    # commenters join automatically (SPECIFICATIONS §5).
    followers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="followed_assets"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = ProjectScopedQuerySet.as_manager()

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["project", "status"])]

    def __str__(self):
        return self.name

    @property
    def latest_version(self):
        return self.versions.order_by("-number").first()


class AssetVersionQuerySet(ProjectScopedQuerySet):
    project_lookup = "asset__project"


class AssetVersion(TimeStampedModel):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()  # v1, v2... automatic, immutable
    label = models.CharField(max_length=120, blank=True)  # "mix 2", "master"
    file = models.FileField(upload_to=version_path, blank=True, max_length=200)
    original_filename = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    mime_type = models.CharField(max_length=120, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    # Filled by the processing task (None until then, or when unknown).
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.CharField(max_length=200, blank=True)
    # Phase 10: a Google Drive file instead of an uploaded one.
    drive_file_id = models.CharField(max_length=200, blank=True)
    drive_meta = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="asset_versions",
    )

    objects = AssetVersionQuerySet.as_manager()

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "number"], name="assetversion_unique_number_per_asset"
            ),
            # Exactly one of: an uploaded file, a Drive reference.
            models.CheckConstraint(
                condition=(Q(file="") & ~Q(drive_file_id=""))
                | (~Q(file="") & Q(drive_file_id="")),
                name="assetversion_file_xor_drive",
            ),
        ]

    def __str__(self):
        return f"{self.asset} v{self.number}"

    @property
    def is_drive(self) -> bool:
        return bool(self.drive_file_id)

    @property
    def kind(self) -> str:
        """What this version really is: a PNG uploaded as v2 of a video asset
        is viewed (and annotated) as an image."""
        from .sniff import kind_of_mime  # sniff imports Kind from here

        return kind_of_mime(self.mime_type) or self.asset.kind


class AssetDerivative(TimeStampedModel):
    """A file computed from a version: cached, re-creatable, never the source."""

    class DerivativeKind(models.TextChoices):
        STREAM_MP3 = "stream_mp3", "MP3 128 kbps"
        PEAKS = "peaks", "Forme d'onde"
        THUMBNAIL = "thumbnail", "Miniature"
        WM_IMAGE = "wm_image", "Image filigranée"  # phase 9
        WM_AUDIO = "wm_audio", "Audio filigrané"  # phase 9

    class DerivativeStatus(models.TextChoices):
        PENDING = "pending", "En attente"
        READY = "ready", "Prêt"
        FAILED = "failed", "Échec"

    version = models.ForeignKey(
        AssetVersion, on_delete=models.CASCADE, related_name="derivatives"
    )
    kind = models.CharField(max_length=12, choices=DerivativeKind.choices)
    # Watermark text, interval...: "" for the plain derivatives.
    params_hash = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=10,
        choices=DerivativeStatus.choices,
        default=DerivativeStatus.PENDING,
    )
    file = models.FileField(upload_to=derivative_path, blank=True, max_length=200)
    content_type = models.CharField(max_length=80, blank=True)
    error = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "kind", "params_hash"],
                name="assetderivative_unique_per_version_kind_params",
            )
        ]

    def __str__(self):
        return f"{self.version} {self.kind}"


class AssetCommentQuerySet(ProjectScopedQuerySet):
    project_lookup = "version__asset__project"


class AssetComment(TimeStampedModel):
    """A comment anchored on a version (SPEC §9). A thread = a root comment
    (parent null) and its replies; "resolved" lives on the root."""

    version = models.ForeignKey(
        AssetVersion, on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="asset_comments",
    )
    body = models.TextField()  # simple markdown
    # Anchors, by kind of asset. Percentages keep image annotations right
    # whatever the display size (SPEC §9).
    timestamp_ms = models.PositiveIntegerField(null=True, blank=True)
    rect_x = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    rect_y = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    rect_w = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    rect_h = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    page = models.PositiveIntegerField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    edited_at = models.DateTimeField(null=True, blank=True)

    objects = AssetCommentQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.body[:40]

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None


class AssetStatusChange(TimeStampedModel):
    """Who changed the status, when, from what to what (SPEC §9)."""

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="status_changes"
    )
    from_status = models.CharField(max_length=12, choices=Status.choices)
    to_status = models.CharField(max_length=12, choices=Status.choices)
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.asset}: {self.from_status} -> {self.to_status}"


# Importable paths for drf-spectacular's ENUM_NAME_OVERRIDES.
ASSET_KIND_CHOICES = Kind.choices
ASSET_STATUS_CHOICES = Status.choices
DERIVATIVE_STATUS_CHOICES = AssetDerivative.DerivativeStatus.choices
