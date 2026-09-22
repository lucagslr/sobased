from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.projects.models import Project
from apps.tasks.models import Task

from .models import AccountStatus, DriveLink


class ProviderStateSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(help_text="Configured on the server")
    connected = serializers.BooleanField()
    email = serializers.CharField(allow_blank=True)
    features = serializers.ListField(child=serializers.CharField())
    status = serializers.ChoiceField(choices=AccountStatus.choices, allow_blank=True)
    picker = serializers.BooleanField(required=False, help_text="Google Picker usable")


class IntegrationsStateSerializer(serializers.Serializer):
    google = ProviderStateSerializer()
    microsoft = ProviderStateSerializer()


class ConnectUrlSerializer(serializers.Serializer):
    url = serializers.URLField()


class PickerConfigSerializer(serializers.Serializer):
    api_key = serializers.CharField()
    client_id = serializers.CharField()
    app_id = serializers.CharField()
    access_token = serializers.CharField()


class DriveLinkSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    task = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(), required=False, allow_null=True, default=None
    )
    added_by = PublicUserSerializer(read_only=True, allow_null=True)

    class Meta:
        model = DriveLink
        fields = [
            "id",
            "project",
            "task",
            "drive_file_id",
            "name",
            "mime_type",
            "icon_url",
            "web_view_url",
            "thumbnail_url",
            "size_bytes",
            "added_by",
            "created_at",
        ]
        # Attaching the same file twice to the same place updates the link:
        # DRF's validator built from the unique constraint would refuse it.
        validators: list = []
        # Everything but the target and the file id comes from Drive itself.
        read_only_fields = [
            "id",
            "name",
            "mime_type",
            "icon_url",
            "web_view_url",
            "thumbnail_url",
            "size_bytes",
            "created_at",
        ]

    def validate(self, attrs):
        task = attrs.get("task")
        if task is not None and task.project_id != attrs["project"].pk:
            raise serializers.ValidationError(
                {"task": "Cette tâche n'est pas du projet."}
            )
        return attrs


class DriveFolderSerializer(serializers.Serializer):
    drive_folder_id = serializers.CharField()
    drive_folder_url = serializers.CharField(allow_blank=True)
    drive_status = serializers.CharField()
