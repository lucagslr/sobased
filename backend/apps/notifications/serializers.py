from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer

from .models import Kind, Notification


class NotificationSerializer(serializers.ModelSerializer):
    kind = serializers.ChoiceField(choices=Kind.choices, read_only=True)
    actor = PublicUserSerializer(read_only=True, allow_null=True)
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "actor",
            "project",
            "payload",
            "url",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class UnreadCountSerializer(serializers.Serializer):
    unread = serializers.IntegerField()
