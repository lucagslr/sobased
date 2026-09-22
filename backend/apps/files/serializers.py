from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.projects.models import Project
from apps.workspaces.models import Tag

from .models import (
    Asset,
    AssetComment,
    AssetDerivative,
    AssetStatusChange,
    AssetVersion,
    Kind,
    Status,
)

READY = AssetDerivative.DerivativeStatus.READY


class DerivativesSerializer(serializers.Serializer):
    """Which derivatives are ready for a version (URLs of the endpoints)."""

    thumbnail_url = serializers.CharField(allow_null=True)
    stream_url = serializers.CharField(allow_null=True)
    peaks_url = serializers.CharField(allow_null=True)
    pending = serializers.BooleanField(help_text="Processing not finished yet")


class AssetVersionSerializer(serializers.ModelSerializer):
    author = PublicUserSerializer(read_only=True, allow_null=True)
    file_url = serializers.SerializerMethodField()
    derivatives = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    open_threads = serializers.SerializerMethodField()
    kind = serializers.ChoiceField(choices=Kind.choices, read_only=True)

    class Meta:
        model = AssetVersion
        fields = [
            "id",
            "asset",
            "number",
            "label",
            "note",
            "original_filename",
            "size_bytes",
            "mime_type",
            "sha256",
            "duration_ms",
            "width",
            "height",
            "page_count",
            "processed_at",
            "processing_error",
            "kind",
            "drive_file_id",
            "drive_meta",
            "is_drive",
            "file_url",
            "derivatives",
            "comments_count",
            "open_threads",
            "author",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [f for f in fields if f not in ("label", "note")]

    def get_file_url(self, version) -> str | None:
        return f"/api/asset-versions/{version.pk}/file/" if version.file else None

    @extend_schema_field(DerivativesSerializer)
    def get_derivatives(self, version) -> dict:
        ready = {d.kind for d in version.derivatives.all() if d.status == READY}
        pending = any(
            d.status == AssetDerivative.DerivativeStatus.PENDING
            for d in version.derivatives.all()
        ) or (bool(version.file) and version.processed_at is None)
        base = f"/api/asset-versions/{version.pk}"
        return {
            "thumbnail_url": f"{base}/thumbnail/" if "thumbnail" in ready else None,
            "stream_url": f"{base}/stream/" if "stream_mp3" in ready else None,
            "peaks_url": f"{base}/peaks/" if "peaks" in ready else None,
            "pending": pending,
        }

    def get_comments_count(self, version) -> int:
        annotated = getattr(version, "comments_total", None)
        return annotated if annotated is not None else version.comments.count()

    def get_open_threads(self, version) -> int:
        annotated = getattr(version, "open_threads_total", None)
        if annotated is not None:
            return annotated
        return version.comments.filter(
            parent__isnull=True, resolved_at__isnull=True
        ).count()


class AssetSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_color = serializers.CharField(source="project.color", read_only=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )
    created_by = PublicUserSerializer(read_only=True, allow_null=True)
    latest_version = serializers.SerializerMethodField()
    versions_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    # Creation only, multipart: the file becomes v1.
    file = serializers.FileField(write_only=True, required=False)
    label = serializers.CharField(write_only=True, required=False, allow_blank=True)
    note = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "project",
            "project_name",
            "project_color",
            "name",
            "kind",
            "status",
            "tags",
            "latest_version",
            "versions_count",
            "is_following",
            "created_by",
            "file",
            "label",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    @extend_schema_field(AssetVersionSerializer(allow_null=True))
    def get_latest_version(self, asset) -> dict | None:
        versions = list(asset.versions.all())  # prefetched, ordered by -number
        if not versions:
            return None
        return AssetVersionSerializer(versions[0], context=self.context).data

    def get_versions_count(self, asset) -> int:
        return len(asset.versions.all())

    def get_is_following(self, asset) -> bool:
        user = self.context["request"].user
        return any(f.pk == user.pk for f in asset.followers.all())

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("project", None)  # an asset never changes project
            for key in ("file", "label", "note"):
                attrs.pop(key, None)
        elif "file" not in attrs:
            raise serializers.ValidationError({"file": "Envoie un fichier (v1)."})
        project = attrs.get("project") or self.instance.project
        for tag in attrs.get("tags", []):
            if tag.workspace_id != project.workspace_id:
                raise serializers.ValidationError(
                    {"tags": "Ce tag n'est pas de cet espace."}
                )
        return attrs


class StatusChangeSerializer(serializers.ModelSerializer):
    changed_by = PublicUserSerializer(read_only=True, allow_null=True)

    class Meta:
        model = AssetStatusChange
        fields = ["id", "from_status", "to_status", "note", "changed_by", "created_at"]
        read_only_fields = fields


class ChangeStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class AssetCommentSerializer(serializers.ModelSerializer):
    author = PublicUserSerializer(read_only=True, allow_null=True)
    resolved_by = PublicUserSerializer(read_only=True, allow_null=True)
    is_mine = serializers.SerializerMethodField()
    is_resolved = serializers.BooleanField(read_only=True)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=AssetComment.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = AssetComment
        fields = [
            "id",
            "version",
            "parent",
            "author",
            "body",
            "timestamp_ms",
            "rect_x",
            "rect_y",
            "rect_w",
            "rect_h",
            "page",
            "is_resolved",
            "resolved_at",
            "resolved_by",
            "is_mine",
            "edited_at",
            "created_at",
        ]
        read_only_fields = ["id", "version", "resolved_at", "edited_at", "created_at"]

    def get_is_mine(self, comment) -> bool:
        return comment.author_id == self.context["request"].user.pk

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le commentaire est vide.")
        return value

    def validate(self, attrs):
        if self.instance is not None:
            # Only the text of an existing comment moves; anchors are fixed.
            return {"body": attrs["body"]} if "body" in attrs else {}
        version = self.context["version"]
        parent = attrs.get("parent")
        if parent is not None:
            if parent.version_id != version.pk:
                raise serializers.ValidationError({"parent": "Fil introuvable."})
            if parent.parent_id is not None:
                # One level: a reply to a reply joins the same thread.
                attrs["parent"] = parent.parent
            # A reply has no anchor of its own: it is where the thread is.
            for key in ("timestamp_ms", "rect_x", "rect_y", "rect_w", "rect_h", "page"):
                attrs.pop(key, None)
            return attrs
        kind = version.kind  # by the file's MIME, the asset's kind as fallback
        rect = [attrs.get(k) for k in ("rect_x", "rect_y", "rect_w", "rect_h")]
        if kind == Kind.IMAGE and any(v is not None for v in rect):
            if any(v is None for v in rect):
                raise serializers.ValidationError(
                    {"rect_x": "Une zone a besoin de x, y, largeur et hauteur."}
                )
            x, y, w, h = rect
            hundred = Decimal("100")
            if not (0 <= x <= hundred and 0 <= y <= hundred and 0 < w and 0 < h):
                raise serializers.ValidationError({"rect_x": "Zone hors de l'image."})
            if x + w > hundred or y + h > hundred:
                raise serializers.ValidationError({"rect_w": "Zone hors de l'image."})
        elif kind != Kind.IMAGE:
            for key in ("rect_x", "rect_y", "rect_w", "rect_h"):
                attrs.pop(key, None)
        if kind not in (Kind.AUDIO, Kind.VIDEO):
            attrs.pop("timestamp_ms", None)
        elif attrs.get("timestamp_ms") is not None and version.duration_ms:
            if attrs["timestamp_ms"] > version.duration_ms:
                raise serializers.ValidationError(
                    {"timestamp_ms": "Au-delà de la fin du fichier."}
                )
        if kind != Kind.DOCUMENT:
            attrs.pop("page", None)
        elif attrs.get("page") is not None and version.page_count:
            if not 1 <= attrs["page"] <= version.page_count:
                raise serializers.ValidationError({"page": "Page inexistante."})
        return attrs
