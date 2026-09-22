"""Tasks, checklist items and comments endpoints.

All three viewsets are ProjectScopedViewSet: visibility and roles come from
apps.projects.access. The only twist is decision D6 (SPECIFICATIONS §1.3): a
member who is ASSIGNED to a task may change its status and tick its checklist
with the Commenter role, without being an Editor of the whole project.
"""

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.activity.mixins import ActivityMixin
from apps.core.localtime import local_today
from apps.projects.access import Role, effective_access, get_access_map
from apps.projects.permissions import ProjectScopedViewSet

from . import services
from .filters import TaskFilter
from .models import ChecklistItem, Task, TaskComment
from .serializers import (
    BlockerCandidateSerializer,
    ChecklistItemSerializer,
    MoveTaskSerializer,
    PinnedItemSerializer,
    TaskCommentSerializer,
    TaskSerializer,
)

STOP_NEEDS_FOLLOWING = (
    "Pour arrêter la récurrence, applique le changement à toutes les suivantes."
)


def _renumber(project_id: int, column: str, moved: Task | None = None, index: int = 0):
    """Rewrite the positions of a kanban column, inserting `moved` at `index`."""
    tasks = list(
        Task.objects.filter(project_id=project_id, status=column)
        .exclude(pk=moved.pk if moved else None)
        .order_by("position", "id")
    )
    if moved is not None:
        tasks.insert(min(index, len(tasks)), moved)
    for position, task in enumerate(tasks):
        if task.position != position:
            Task.objects.filter(pk=task.pk).update(position=position)
            task.position = position


class TaskViewSet(ActivityMixin, ProjectScopedViewSet, viewsets.ModelViewSet):
    activity_type = "task"
    activity_fields = ("title", "status", "priority", "start_at", "due_at", "assignees")
    queryset = (
        Task.objects.select_related("project", "series", "source_event")
        .prefetch_related("assignees", "tags", "checklist", "blocked_by__project")
        .annotate(comments_total=Count("comments", distinct=True))
    )
    serializer_class = TaskSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TaskFilter
    ordering_fields = ["due_at", "start_at", "priority", "position", "created_at"]
    ordering = ["position", "id"]
    # Fields an assignee with the Commenter role may change on their own task.
    ASSIGNEE_FIELDS = {"status", "position"}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Used by the "overdue" filter and by is_overdue in the serializer.
        request.local_today = local_today(request.user)

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "access_map": get_access_map(self.request),
            "today": getattr(self.request, "local_today", timezone.localdate()),
            "now": timezone.now(),
        }

    # --- Decision D6 ---------------------------------------------------------------
    def _assignee_shortcut(self, task) -> bool:
        if self.action not in ("partial_update", "move"):
            return False
        if not set(self.request.data) <= self.ASSIGNEE_FIELDS:
            return False
        if not effective_access(self.request, task.project).has(Role.COMMENTER):
            return False
        return task.assignees.filter(pk=self.request.user.pk).exists()

    def check_object_permissions(self, request, obj):
        if self._assignee_shortcut(obj):
            return
        super().check_object_permissions(request, obj)

    # --- Create / update / delete ----------------------------------------------------
    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        self.check_project_access(data["project"])
        rule = data.pop("rrule", "")
        assignees = data.pop("assignee_users", None)
        task = serializer.save(
            created_by=self.request.user,
            position=Task.objects.filter(
                project=data["project"], status=data.get("status", Task.Status.TODO)
            ).count(),
        )
        if assignees is not None:
            task.assignees.set(assignees)
            services.notify_assignment(task, assignees, self.request.user)
        if rule:
            self._start_series(task, rule)

    @transaction.atomic
    def perform_update(self, serializer):
        task = serializer.instance
        data = serializer.validated_data
        rule = data.pop("rrule", None)  # None: untouched, "": stop recurring
        assignees = data.pop("assignee_users", None)
        before = set(task.assignees.all()) if assignees is not None else set()
        status_changed = "status" in data and data["status"] != task.status
        old_column = task.status

        task = serializer.save()
        if assignees is not None:
            task.assignees.set(assignees)
            services.notify_assignment(
                task, [u for u in assignees if u not in before], self.request.user
            )
        if status_changed:  # joins the end of its new kanban column
            _renumber(task.project_id, task.status, task, index=10**6)
            _renumber(task.project_id, old_column)

        scope = self.request.query_params.get("scope", "this")
        if task.series_id and scope == "following":
            services.apply_to_following(task, rule, self.request.user.timezone)
        elif task.series_id:
            # "Cette occurrence": later edits of the series will skip it.
            Task.objects.filter(pk=task.pk).update(is_exception=True)
            if rule == "":
                raise ValidationError({"rrule": STOP_NEEDS_FOLLOWING})
        elif rule:
            self._start_series(task, rule)

    def _start_series(self, task, rule):
        try:
            services.start_series(task, rule, self.request.user.timezone)
        except ValueError as exc:
            raise ValidationError({"rrule": str(exc)}) from exc

    def perform_destroy(self, instance):
        if self.request.query_params.get("scope") == "following":
            services.delete_with_following(instance)
        else:
            instance.delete()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "scope",
                str,
                enum=["this", "following"],
                description="Récurrence : cette occurrence, ou toutes les suivantes",
            )
        ]
    )
    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        return self._fresh(response, kwargs["pk"])

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return self._fresh(response, response.data["id"])

    def _fresh(self, response, pk):
        """Re-read the task: series, assignees and positions were set after save()."""
        task = self.queryset.get(pk=pk)
        response.data = self.get_serializer(task).data
        return response

    # --- Kanban ----------------------------------------------------------------------
    @extend_schema(request=MoveTaskSerializer, responses=TaskSerializer)
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def move(self, request, pk=None):
        """Drop a card in a column at a position. Warns if it is still blocked."""
        task = self.get_object()
        serializer = MoveTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_column = task.status
        task.status = serializer.validated_data["status"]
        task.save()
        _renumber(
            task.project_id, task.status, task, serializer.validated_data["position"]
        )
        if old_column != task.status:
            _renumber(task.project_id, old_column)
        data = self.get_serializer(self.queryset.get(pk=task.pk)).data
        if task.status == Task.Status.IN_PROGRESS and data["is_blocked"]:
            # Allowed on purpose (SPEC §7): the front shows it as a toast.
            data["warning"] = "Cette tâche est encore bloquée par une autre."
        return Response(data)

    @extend_schema(
        parameters=[OpenApiParameter("task", int), OpenApiParameter("q", str)],
        responses=BlockerCandidateSerializer(many=True),
    )
    @action(detail=False, url_path="blocker-candidates", pagination_class=None)
    def blocker_candidates(self, request):
        """Search for the "Bloquée par" field: tasks of the same root project
        that I can see and that would not create a loop."""
        task = get_object_or_404(
            self.get_queryset(), pk=request.query_params.get("task")
        )
        root = services.root_project_id(task.project)
        access_map = get_access_map(request)
        in_root = [root, *access_map.descendants(root)]
        candidates = (
            self.get_queryset()
            .filter(project_id__in=in_root)
            .exclude(pk=task.pk)
            .exclude(pk__in=task.blocked_by.values("pk"))
            .select_related("project")
        )
        query = request.query_params.get("q", "").strip()
        if query:
            candidates = candidates.filter(title__icontains=query)
        safe = [c for c in candidates[:40] if not services.would_create_cycle(task, c)]
        return Response(BlockerCandidateSerializer(safe[:15], many=True).data)


class ChecklistItemViewSet(
    ProjectScopedViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Checklist items. `?task=` lists a checklist, `?pinned=true` feeds the
    "Todo épinglées" widget (open items of open tasks)."""

    queryset = ChecklistItem.objects.select_related("task__project")
    serializer_class = ChecklistItemSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_project(self, obj):
        return obj.task.project

    def get_serializer_class(self):
        pinned = self.request.query_params.get("pinned") in ("true", "1")
        return (
            PinnedItemSerializer
            if self.action == "list" and pinned
            else super().get_serializer_class()
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("task", "").isdigit():
            queryset = queryset.filter(task_id=params["task"])
        if params.get("pinned") in ("true", "1"):
            queryset = queryset.filter(pinned=True, done=False).exclude(
                task__status__in=Task.CLOSED_STATUSES
            )
        if params.get("project", "").isdigit():
            ids = [int(params["project"])]
            ids += get_access_map(self.request).descendants(ids[0])
            queryset = queryset.filter(task__project_id__in=ids)
        return queryset

    def check_object_permissions(self, request, obj):
        # D6: the assignee may tick items (and nothing else) as a Commenter.
        only_ticks = self.action == "partial_update" and set(request.data) <= {"done"}
        if (
            only_ticks
            and effective_access(request, obj.task.project).has(Role.COMMENTER)
            and obj.task.assignees.filter(pk=request.user.pk).exists()
        ):
            return
        super().check_object_permissions(request, obj)

    @extend_schema(parameters=[OpenApiParameter("task", int, required=True)])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        task = get_object_or_404(
            Task.objects.for_user(self.request),
            pk=self.request.query_params.get("task"),
        )
        self.check_project_access(task.project)
        serializer.save(task=task, position=task.checklist.count())

    def perform_update(self, serializer):
        item = serializer.instance
        becoming_done = serializer.validated_data.get("done")
        extra = {}
        if becoming_done is True and not item.done:
            extra = {"done_by": self.request.user, "done_at": timezone.now()}
        elif becoming_done is False:
            extra = {"done_by": None, "done_at": None}
        serializer.save(**extra)


class TaskCommentViewSet(
    ProjectScopedViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Comments of a task (`?task=`). Writing needs the Commenter role;
    editing is for the author, deleting for the author or an admin."""

    queryset = TaskComment.objects.select_related("task__project", "author")
    serializer_class = TaskCommentSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    write_role = Role.COMMENTER

    def get_project(self, obj):
        return obj.task.project

    def get_queryset(self):
        queryset = super().get_queryset()
        task_id = self.request.query_params.get("task", "")
        return queryset.filter(task_id=task_id) if task_id.isdigit() else queryset

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if (
            self.action in ("partial_update", "destroy")
            and obj.author_id != request.user.pk
        ):
            is_admin = effective_access(request, obj.task.project).has(Role.ADMIN)
            if not (self.action == "destroy" and is_admin):
                raise PermissionDenied("Seul l'auteur peut modifier ce commentaire.")

    @extend_schema(parameters=[OpenApiParameter("task", int, required=True)])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        task = get_object_or_404(
            Task.objects.for_user(self.request),
            pk=self.request.query_params.get("task"),
        )
        self.check_project_access(task.project)
        comment = serializer.save(task=task, author=self.request.user)
        services.notify_mentions(comment, self.request.user)

    def perform_update(self, serializer):
        serializer.save(edited_at=timezone.now())

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
