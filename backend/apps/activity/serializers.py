from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer

from .models import ActivityEntry, Verb


class ActivityEntrySerializer(serializers.ModelSerializer):
    verb = serializers.ChoiceField(choices=Verb.choices, read_only=True)
    actor = PublicUserSerializer(read_only=True, allow_null=True)
    project_name = serializers.SerializerMethodField()

    class Meta:
        model = ActivityEntry
        fields = [
            "id",
            "verb",
            "actor",
            "project",
            "project_name",
            "target_type",
            "target_id",
            "target_label",
            "changes",
            "created_at",
        ]
        read_only_fields = fields

    def get_project_name(self, entry) -> str | None:
        return entry.project.name if entry.project_id else None
