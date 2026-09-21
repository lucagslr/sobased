from datetime import UTC, datetime, time

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.core import recurrence
from apps.projects.access import member_user_ids
from apps.projects.models import Project
from apps.workspaces.models import Tag

from . import services
from .models import ChecklistItem, Task, TaskComment

User = get_user_model()


class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ["id", "task", "title", "done", "pinned", "position", "done_at"]
        read_only_fields = ["id", "task", "done_at"]


class PinnedItemSerializer(ChecklistItemSerializer):
    """A pinned item with enough context for the dashboard widget."""

    task_title = serializers.CharField(source="task.title", read_only=True)
    project = serializers.IntegerField(source="task.project_id", read_only=True)
    project_name = serializers.CharField(source="task.project.name", read_only=True)
    project_color = serializers.CharField(source="task.project.color", read_only=True)

    class Meta(ChecklistItemSerializer.Meta):
        fields = [
            *ChecklistItemSerializer.Meta.fields,
            "task_title",
            "project",
            "project_name",
            "project_color",
        ]


class BlockerSerializer(serializers.Serializer):
    """A task blocking another one. For a blocker the user cannot see, only
    `id` and `is_open` are filled: enough for the padlock, nothing more."""

    id = serializers.IntegerField()
    visible = serializers.BooleanField()
    title = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=Task.Status.choices, allow_null=True)
    project_name = serializers.CharField(allow_null=True)
    is_open = serializers.BooleanField()


class RecurrenceSerializer(serializers.Serializer):
    series = serializers.IntegerField()
    rrule = serializers.CharField()
    is_exception = serializers.BooleanField()


class TaskSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_color = serializers.CharField(source="project.color", read_only=True)
    assignees = PublicUserSerializer(many=True, read_only=True)
    # Users are identified by username in the API (no numeric id is exposed).
    assignee_usernames = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )
    blocked_by = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(), many=True, required=False
    )
    blockers = serializers.SerializerMethodField()
    is_blocked = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    checklist = ChecklistItemSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    # Write: an RRULE ("" stops the recurrence). Read: see `recurrence`.
    rrule = serializers.CharField(write_only=True, required=False, allow_blank=True)
    recurrence = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "project_name",
            "project_color",
            "title",
            "description",
            "status",
            "priority",
            "start_at",
            "due_at",
            "all_day",
            "position",
            "assignees",
            "assignee_usernames",
            "tags",
            "blocked_by",
            "blockers",
            "is_blocked",
            "is_overdue",
            "checklist",
            "comments_count",
            "rrule",
            "recurrence",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "position",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    # --- Computed fields -------------------------------------------------------------
    def _open_blockers(self, task):
        return [
            b for b in task.blocked_by.all() if b.status not in Task.CLOSED_STATUSES
        ]

    @extend_schema_field(BlockerSerializer(many=True))
    def get_blockers(self, task) -> list[dict]:
        visible_ids = set(self.context["access_map"].project_ids())
        result = []
        for blocker in task.blocked_by.all():
            visible = blocker.project_id in visible_ids
            result.append(
                {
                    "id": blocker.pk,
                    "visible": visible,
                    "title": blocker.title if visible else None,
                    "status": blocker.status if visible else None,
                    "project_name": blocker.project.name if visible else None,
                    "is_open": blocker.status not in Task.CLOSED_STATUSES,
                }
            )
        return result

    def get_is_blocked(self, task) -> bool:
        return bool(self._open_blockers(task))

    def get_is_overdue(self, task) -> bool:
        if task.due_at is None or task.is_closed:
            return False
        if task.all_day:
            today = self.context["today"]
            return task.due_at < datetime.combine(today, time.min, tzinfo=UTC)
        return task.due_at < self.context["now"]

    def get_comments_count(self, task) -> int:
        annotated = getattr(task, "comments_total", None)
        return annotated if annotated is not None else task.comments.count()

    @extend_schema_field(RecurrenceSerializer(allow_null=True))
    def get_recurrence(self, task) -> dict | None:
        if not task.series_id:
            return None
        return {
            "series": task.series_id,
            "rrule": task.series.rrule,
            "is_exception": task.is_exception,
        }

    # --- Validation ------------------------------------------------------------------
    def validate_priority(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("La priorité va de 1 à 5.")
        return value

    def validate_rrule(self, value):
        if not value:
            return ""
        try:
            return recurrence.normalise_rrule(value)
        except recurrence.InvalidRecurrence as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("project", None)  # a task never changes project
        project = attrs.get("project") or self.instance.project

        start = attrs.get("start_at", getattr(self.instance, "start_at", None))
        due = attrs.get("due_at", getattr(self.instance, "due_at", None))
        if start and due and due < start:
            raise serializers.ValidationError(
                {"due_at": "L'échéance ne peut pas précéder le début."}
            )
        if attrs.get("rrule") and not (start or due):
            raise serializers.ValidationError(
                {"rrule": "Une tâche récurrente a besoin d'une date."}
            )

        for tag in attrs.get("tags", []):
            if tag.workspace_id != project.workspace_id:
                raise serializers.ValidationError(
                    {"tags": "Ce tag n'est pas de cet espace."}
                )

        if "assignee_usernames" in attrs:
            attrs["assignee_users"] = self._resolve_assignees(
                attrs.pop("assignee_usernames"), project
            )

        if "blocked_by" in attrs:
            # Only tasks the user can see may be picked as blockers.
            visible = set(self.context["access_map"].project_ids())
            for blocker in attrs["blocked_by"]:
                if blocker.project_id not in visible:
                    raise serializers.ValidationError(
                        {"blocked_by": "Tâche introuvable."}
                    )
            candidate = self.instance or Task(project=project)
            try:
                services.validate_blockers(candidate, attrs["blocked_by"])
            except ValueError as exc:
                raise serializers.ValidationError({"blocked_by": str(exc)}) from exc
        return attrs

    def _resolve_assignees(self, usernames, project):
        """Usernames -> users, who must all be members of the project."""
        wanted = {name.lstrip("@").lower() for name in usernames if name.strip()}
        members = User.objects.filter(pk__in=member_user_ids(project), is_active=True)
        found = [user for user in members if user.username.lower() in wanted]
        if len(found) != len(wanted):
            raise serializers.ValidationError(
                {"assignee_usernames": "On ne peut assigner que des membres du projet."}
            )
        return found


class TaskCommentSerializer(serializers.ModelSerializer):
    author = PublicUserSerializer(read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = TaskComment
        fields = ["id", "task", "author", "body", "is_mine", "edited_at", "created_at"]
        read_only_fields = ["id", "task", "edited_at", "created_at"]

    def get_is_mine(self, comment) -> bool:
        return comment.author_id == self.context["request"].user.pk

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le commentaire est vide.")
        return value


class MoveTaskSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Task.Status.choices)
    position = serializers.IntegerField(min_value=0)


class BlockerCandidateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    status = serializers.ChoiceField(choices=Task.Status.choices)
    project_name = serializers.CharField(source="project.name")
