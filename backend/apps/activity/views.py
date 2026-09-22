"""GET /api/activity/?project=<id>: the journal of a project, for editors
and up (SPEC §14). Entries about money (transactions, budget, recurring
expenses) are only returned on projects where the reader has the finance
flag: the journal must never leak an amount."""

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.exceptions import NotFound, ValidationError

from apps.projects import tree
from apps.projects.access import Role, get_access_map
from apps.projects.models import Project
from apps.projects.permissions import ProjectScopedViewSet

from .models import FINANCE_TARGETS, ActivityEntry, Verb
from .serializers import ActivityEntrySerializer

PARAMETERS = [
    OpenApiParameter("project", int, required=True),
    OpenApiParameter("include_descendants", bool),
    OpenApiParameter("verb", str, enum=[verb.value for verb in Verb]),
    OpenApiParameter("target_type", str),
    OpenApiParameter("actor", str, description="username"),
]


class ActivityViewSet(
    ProjectScopedViewSet, mixins.ListModelMixin, viewsets.GenericViewSet
):
    queryset = ActivityEntry.objects.select_related("actor", "project")
    serializer_class = ActivityEntrySerializer
    # A viewer sees the project (404 otherwise) but not its journal (403).
    read_role = Role.VIEWER
    action_roles = {"list": Role.EDITOR}

    def _project(self) -> Project:
        raw = self.request.query_params.get("project", "")
        if not raw.isdigit():
            raise ValidationError({"project": "Ce paramètre est obligatoire."})
        project = Project.objects.filter(pk=int(raw)).first()
        if project is None:
            raise NotFound()
        self.check_project_access(project)  # 404 invisible, 403 below editor
        return project

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ActivityEntry.objects.none()
        params = self.request.query_params
        project = self._project()
        if params.get("include_descendants") in ("true", "1"):
            ids = [node.pk for node in tree.subtree(project)]
        else:
            ids = [project.pk]
        # Rights inherit downwards, but the filter stays the sanctioned one.
        queryset = self.queryset.for_user(self.request, Role.EDITOR).filter(
            project__in=ids
        )
        money = get_access_map(self.request).project_ids(finance="view")
        queryset = queryset.exclude(
            Q(target_type__in=FINANCE_TARGETS) & ~Q(project__in=money)
        )
        if params.get("verb"):
            queryset = queryset.filter(verb=params["verb"])
        if params.get("target_type"):
            queryset = queryset.filter(target_type=params["target_type"])
        if params.get("actor"):
            queryset = queryset.filter(actor__username__iexact=params["actor"])
        return queryset

    @extend_schema(parameters=PARAMETERS)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
