from datetime import timedelta

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.contacts.models import Contact
from apps.core import recurrence
from apps.projects.access import member_user_ids
from apps.projects.models import Project
from apps.tasks.models import Task
from apps.tasks.serializers import RecurrenceSerializer
from apps.workspaces.models import Tag

from .models import Event

User = get_user_model()

MAX_DECISIONS = 50


class EventContactSerializer(serializers.Serializer):
    """A contact taking part in an event. Part of the event's content: shown
    to whoever can see the event, even without access to the address book."""

    id = serializers.IntegerField()
    display_name = serializers.CharField()
    organization = serializers.CharField()
    job = serializers.CharField()


class EventTaskSerializer(serializers.Serializer):
    """A task created from this meeting."""

    id = serializers.IntegerField()
    title = serializers.CharField()
    status = serializers.ChoiceField(choices=Task.Status.choices)


class EventSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_color = serializers.CharField(source="project.color", read_only=True)
    # Optional on creation: start + 1 hour (the same day for an all-day event).
    end = serializers.DateTimeField(required=False)
    participants = PublicUserSerializer(many=True, read_only=True)
    # Users are identified by username in the API (no numeric id is exposed).
    participant_usernames = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    contacts = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(), many=True, required=False
    )
    contact_details = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )
    # Blank lines are dropped (validate_decisions), not refused: the form
    # sends the list as typed.
    decisions = serializers.ListField(
        child=serializers.CharField(max_length=500, allow_blank=True),
        required=False,
        max_length=MAX_DECISIONS,
    )
    tasks = serializers.SerializerMethodField()
    # Write: an RRULE ("" stops the recurrence). Read: see `recurrence`.
    rrule = serializers.CharField(write_only=True, required=False, allow_blank=True)
    recurrence = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "project",
            "project_name",
            "project_color",
            "type",
            "title",
            "start",
            "end",
            "all_day",
            "location",
            "prep_notes",
            "report",
            "decisions",
            "participants",
            "participant_usernames",
            "contacts",
            "contact_details",
            "tags",
            "tasks",
            "rrule",
            "recurrence",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    # --- Computed fields -------------------------------------------------------------
    @extend_schema_field(EventContactSerializer(many=True))
    def get_contact_details(self, event) -> list[dict]:
        return [
            {
                "id": contact.pk,
                "display_name": contact.display_name,
                "organization": contact.organization,
                "job": contact.job,
            }
            for contact in event.contacts.all()
        ]

    @extend_schema_field(EventTaskSerializer(many=True))
    def get_tasks(self, event) -> list[dict]:
        visible = set(self.context["access_map"].project_ids())
        return [
            {"id": task.pk, "title": task.title, "status": task.status}
            for task in event.tasks.all()
            if task.project_id in visible
        ]

    @extend_schema_field(RecurrenceSerializer(allow_null=True))
    def get_recurrence(self, event) -> dict | None:
        if not event.series_id:
            return None
        return {
            "series": event.series_id,
            "rrule": event.series.rrule,
            "is_exception": event.is_exception,
        }

    # --- Validation ------------------------------------------------------------------
    def validate_rrule(self, value):
        if not value:
            return ""
        try:
            return recurrence.normalise_rrule(value)
        except recurrence.InvalidRecurrence as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_decisions(self, value):
        return [line.strip() for line in value if line.strip()]

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("project", None)  # an event never changes project
        project = attrs.get("project") or self.instance.project

        start = attrs.get("start", getattr(self.instance, "start", None))
        all_day = attrs.get("all_day", getattr(self.instance, "all_day", False))
        if "end" not in attrs and self.instance is None:
            attrs["end"] = start if all_day else start + timedelta(hours=1)
        elif "end" not in attrs and "start" in attrs:
            # Only the start moved (a drag, a new time): the meeting keeps
            # its duration, like in any agenda.
            attrs["end"] = start + (self.instance.end - self.instance.start)
        end = attrs.get("end", getattr(self.instance, "end", None))
        if end < start:
            raise serializers.ValidationError(
                {"end": "La fin ne peut pas précéder le début."}
            )

        for tag in attrs.get("tags", []):
            if tag.workspace_id != project.workspace_id:
                raise serializers.ValidationError(
                    {"tags": "Ce tag n'est pas de cet espace."}
                )

        if "participant_usernames" in attrs:
            attrs["participant_users"] = self._resolve_participants(
                attrs.pop("participant_usernames"), project
            )

        if "contacts" in attrs:
            # Contacts of the project's workspace that I can see myself; the
            # ones already on the event stay allowed (someone else added them).
            wanted = {contact.pk for contact in attrs["contacts"]}
            already = (
                set(self.instance.contacts.values_list("pk", flat=True))
                if self.instance
                else set()
            )
            allowed = set(
                Contact.objects.for_user(self.context["request"])
                .filter(workspace_id=project.workspace_id, pk__in=wanted)
                .values_list("pk", flat=True)
            )
            if wanted - allowed - already:
                raise serializers.ValidationError({"contacts": "Contact introuvable."})
        return attrs

    def _resolve_participants(self, usernames, project):
        """Usernames -> users, who must all be members of the project."""
        wanted = {name.lstrip("@").lower() for name in usernames if name.strip()}
        members = User.objects.filter(pk__in=member_user_ids(project), is_active=True)
        found = [user for user in members if user.username.lower() in wanted]
        if len(found) != len(wanted):
            raise serializers.ValidationError(
                {
                    "participant_usernames": (
                        "Seuls des membres du projet peuvent participer. "
                        "Pour une personne extérieure, ajoute un contact."
                    )
                }
            )
        return found
