from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.core import crypto
from apps.files.models import Asset, AssetVersion
from apps.projects.access import Role, get_access_map
from apps.projects.models import Project

from . import services
from .models import Event, ShareAccessLog, ShareLink, ShareLinkItem, State, Target


class ShareItemSerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source="asset.name", read_only=True)
    asset_kind = serializers.CharField(source="asset.kind", read_only=True)

    class Meta:
        model = ShareLinkItem
        fields = ["asset", "asset_name", "asset_kind", "position"]


class ShareLinkSerializer(serializers.ModelSerializer):
    """Editors' view of a link. The target is fixed at creation; everything
    else may change. `password` is write-only: "" or null removes it."""

    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False
    )
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_color = serializers.CharField(source="project.color", read_only=True)
    target_type = serializers.ChoiceField(choices=Target.choices)
    version = serializers.PrimaryKeyRelatedField(
        queryset=AssetVersion.objects.all(), required=False, allow_null=True
    )
    asset = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.all(), required=False, allow_null=True
    )
    assets = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.all(), many=True, required=False, write_only=True
    )
    items = ShareItemSerializer(many=True, read_only=True)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    has_password = serializers.BooleanField(read_only=True)
    state = serializers.ChoiceField(choices=State.choices, read_only=True)
    url = serializers.SerializerMethodField()
    created_by = PublicUserSerializer(read_only=True, allow_null=True)
    target_label = serializers.SerializerMethodField()

    class Meta:
        model = ShareLink
        fields = [
            "id",
            "project",
            "project_name",
            "project_color",
            "target_type",
            "version",
            "asset",
            "assets",
            "items",
            "title",
            "target_label",
            "password",
            "has_password",
            "expires_at",
            "max_views",
            "max_plays",
            "view_count",
            "play_count",
            "allow_download",
            "watermark",
            "recipient_label",
            "notify_on_open",
            "state",
            "url",
            "first_opened_at",
            "last_opened_at",
            "revoked_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "view_count",
            "play_count",
            "first_opened_at",
            "last_opened_at",
            "revoked_at",
            "created_at",
        ]

    def get_url(self, link) -> str | None:
        return services.public_url(link)

    @extend_schema_field(serializers.CharField())
    def get_target_label(self, link) -> str:
        if link.target_type == Target.VERSION and link.version_id:
            version = link.version
            label = f"v{version.number}" + (
                f" · {version.label}" if version.label else ""
            )
            return f"{version.asset.name} ({label})"
        if link.target_type == Target.ASSET and link.asset_id:
            return f"{link.asset.name} (dernière version)"
        count = link.items.count()
        return f"Sélection de {count} fichier{'s' if count > 1 else ''}"

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("La date d'expiration est déjà passée.")
        return value

    def validate_password(self, value):
        if value and len(value) < 4:
            raise serializers.ValidationError("Au moins 4 caractères.")
        return value

    def _visible_project_ids(self):
        return set(get_access_map(self.context["request"]).project_ids(Role.EDITOR))

    def validate(self, attrs):
        if self.instance is not None:
            # The target never changes: make another link instead.
            for key in ("project", "target_type", "version", "asset", "assets"):
                attrs.pop(key, None)
            return attrs

        target = attrs["target_type"]
        version, asset = attrs.get("version"), attrs.get("asset")
        assets = attrs.get("assets") or []
        editable = self._visible_project_ids()
        if target == Target.VERSION:
            if version is None or version.asset.project_id not in editable:
                raise serializers.ValidationError({"version": "Version introuvable."})
            attrs["project"] = version.asset.project
            attrs["asset"] = None
            attrs.setdefault("title", version.asset.name)
        elif target == Target.ASSET:
            if asset is None or asset.project_id not in editable:
                raise serializers.ValidationError({"asset": "Fichier introuvable."})
            attrs["project"] = asset.project
            attrs["version"] = None
            attrs.setdefault("title", asset.name)
        else:
            project = attrs.get("project")
            if project is None or project.pk not in editable:
                raise serializers.ValidationError({"project": "Projet introuvable."})
            if not assets:
                raise serializers.ValidationError(
                    {"assets": "Choisis au moins un fichier."}
                )
            allowed = {
                project.pk,
                *get_access_map(self.context["request"]).descendants(project.pk),
            }
            for item in assets:
                if item.project_id not in allowed:
                    raise serializers.ValidationError(
                        {"assets": "Un fichier n'appartient pas à ce projet."}
                    )
            attrs["version"] = None
            attrs["asset"] = None
            attrs.setdefault("title", "Sélection")
        if not attrs.get("title"):
            attrs["title"] = "Partage"
        return attrs

    def create(self, validated):
        password = validated.pop("password", None)
        assets = validated.pop("assets", [])
        token = services.new_token()
        link = ShareLink(
            **validated,
            token_hash=services.token_hash(token),
            token_encrypted=crypto.encrypt(token),
            created_by=self.context["request"].user,
        )
        services.set_password(link, password)
        link.save()
        ShareLinkItem.objects.bulk_create(
            ShareLinkItem(share_link=link, asset=asset, position=position)
            for position, asset in enumerate(assets)
        )
        return link

    def update(self, link, validated):
        if "password" in validated:
            services.set_password(link, validated.pop("password"))
        for key, value in validated.items():
            setattr(link, key, value)
        link.save()
        return link


class AccessLogSerializer(serializers.ModelSerializer):
    event = serializers.ChoiceField(choices=Event.choices, read_only=True)
    version_number = serializers.IntegerField(
        source="version.number", read_only=True, allow_null=True
    )

    class Meta:
        model = ShareAccessLog
        fields = [
            "id",
            "event",
            "version",
            "version_number",
            "ip_truncated",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields


# --- Public page --------------------------------------------------------------------
class PublicItemSerializer(serializers.Serializer):
    """One playable / viewable thing of the public page."""

    version_id = serializers.IntegerField()
    name = serializers.CharField()
    kind = serializers.CharField()
    label = serializers.CharField()
    number = serializers.IntegerField()
    mime_type = serializers.CharField()
    duration_ms = serializers.IntegerField(allow_null=True)
    width = serializers.IntegerField(allow_null=True)
    height = serializers.IntegerField(allow_null=True)
    page_count = serializers.IntegerField(allow_null=True)
    media_url = serializers.CharField(allow_null=True)
    download_url = serializers.CharField(allow_null=True)
    peaks_url = serializers.CharField(allow_null=True)
    thumbnail_url = serializers.CharField(allow_null=True)
    ready = serializers.BooleanField(help_text="False while a watermark is being built")
    error = serializers.CharField(allow_blank=True)


class PublicShareSerializer(serializers.Serializer):
    title = serializers.CharField()
    requires_password = serializers.BooleanField()
    target_type = serializers.ChoiceField(choices=Target.choices)
    allow_download = serializers.BooleanField()
    watermark = serializers.BooleanField()
    expires_at = serializers.DateTimeField(allow_null=True)
    items = PublicItemSerializer(many=True)


class UnlockSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=200)
