"""Workspace endpoints.

Dependency note: the models of this app sit BELOW apps.projects (a project
points to a workspace), but these views sit ABOVE it, because rights are
resolved by apps.projects.access. Nothing in workspaces/models.py may import
from apps.projects.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import RestrictedError
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.projects.access import Role, get_access_map, invalidate_access_map
from apps.projects.models import Membership
from apps.projects.models import Role as StoredRole
from apps.projects.permissions import WorkspaceScopedViewSet

from .models import FALLBACK_PROJECT_TYPE, ProjectType, Tag, Workspace
from .serializers import ProjectTypeSerializer, TagSerializer, WorkspaceSerializer

User = get_user_model()


class WorkspaceViewSet(WorkspaceScopedViewSet, viewsets.ModelViewSet):
    """CRUD on workspaces. Any signed-in user may create one and owns it."""

    queryset = Workspace.objects.all()
    serializer_class = WorkspaceSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    write_role = Role.ADMIN
    action_roles = {
        "destroy": Role.OWNER,
        "transfer_ownership": Role.OWNER,
        "leave": Role.VIEWER,  # any direct member may leave
    }

    def get_workspace(self, obj):
        return obj

    def get_queryset(self):
        return Workspace.objects.filter(pk__in=self.visible_workspace_ids())

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "access_map": get_access_map(self.request),
        }

    @transaction.atomic
    def perform_create(self, serializer):
        workspace = serializer.save(created_by=self.request.user)
        Membership.objects.create(
            user=self.request.user, workspace=workspace, role=StoredRole.OWNER
        )
        workspace.create_defaults()
        invalidate_access_map(self.request)
        # The response must show the rights the creator has just received.
        serializer.context["access_map"] = get_access_map(self.request)

    @extend_schema(
        request=inline_serializer(
            "TransferOwnership", {"username": serializers.CharField()}
        ),
        responses={200: WorkspaceSerializer},
    )
    @action(detail=True, methods=["post"], url_path="transfer-ownership")
    @transaction.atomic
    def transfer_ownership(self, request, pk=None):
        """The owner hands the workspace over to a member and becomes admin."""
        workspace = self.get_object()  # owner only, see action_roles
        target = Membership.objects.filter(
            workspace=workspace, user__username__iexact=request.data.get("username", "")
        ).first()
        if target is None or target.user_id == request.user.pk:
            raise ValidationError({"username": "Choisis un autre membre de l'espace."})
        mine = Membership.objects.get(workspace=workspace, user=request.user)
        # Demote first: the database allows a single owner per workspace.
        mine.role = StoredRole.ADMIN
        mine.save()
        target.role = StoredRole.OWNER
        target.save()
        invalidate_access_map(request)
        return Response(self.get_serializer(workspace).data)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        workspace = self.get_object()
        membership = Membership.objects.filter(
            workspace=workspace, user=request.user
        ).first()
        if membership is None:
            raise ValidationError("Tu n'es pas membre direct de cet espace.")
        if membership.role == StoredRole.OWNER:
            raise PermissionDenied("Transfère d'abord la propriété de l'espace.")
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class _WorkspaceListFilterMixin:
    """?workspace=<id> narrows a per-workspace list."""

    def filter_by_workspace(self, queryset):
        workspace_id = self.request.query_params.get("workspace")
        if workspace_id and workspace_id.isdigit():
            queryset = queryset.filter(workspace_id=workspace_id)
        return queryset


class ProjectTypeViewSet(
    _WorkspaceListFilterMixin, WorkspaceScopedViewSet, viewsets.ModelViewSet
):
    """Project types of a workspace. Read: anyone in it. Write: admins."""

    queryset = ProjectType.objects.all()
    serializer_class = ProjectTypeSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    write_role = Role.ADMIN

    def get_queryset(self):
        return self.filter_by_workspace(super().get_queryset())

    def perform_destroy(self, instance):
        """A type in use is replaced by ?replace_with=<id>, or by "Autre"."""
        others = ProjectType.objects.filter(workspace=instance.workspace).exclude(
            pk=instance.pk
        )
        replacement = (
            others.filter(pk=self.request.query_params.get("replace_with") or 0).first()
            or others.filter(name__iexact=FALLBACK_PROJECT_TYPE).first()
        )
        if instance.projects.exists():
            if replacement is None:
                raise ValidationError(
                    "Ce type est utilisé : indique un type de remplacement."
                )
            instance.projects.update(type=replacement)
        try:
            instance.delete()
        except RestrictedError as exc:  # raced with a project creation
            raise ValidationError("Ce type est encore utilisé.") from exc


class TagViewSet(
    _WorkspaceListFilterMixin, WorkspaceScopedViewSet, viewsets.ModelViewSet
):
    """Tags of a workspace.

    Read: anyone in the workspace. Create: editors of the workspace or of any
    of its projects (they tag their own content). Rename / delete: workspace
    editors only, because it affects everybody's content.
    """

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    write_role = Role.EDITOR

    def get_queryset(self):
        return self.filter_by_workspace(super().get_queryset())

    def perform_create(self, serializer):
        workspace = serializer.validated_data["workspace"]
        access_map = get_access_map(self.request)
        edits_a_project = any(
            access_map.project_workspace.get(pid) == workspace.pk
            for pid in access_map.project_ids(Role.EDITOR)
        )
        if not edits_a_project:
            self.check_workspace_access(workspace)  # raises 404 / 403
        serializer.save()
