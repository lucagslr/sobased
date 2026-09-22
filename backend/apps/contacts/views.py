"""Contacts and their links to projects.

Reading goes through Contact.objects.for_user() (see models.py): the whole
address book for a member of the workspace, only the linked contacts for a
guest of a project.

Writing (SPECIFICATIONS §1.3):
- create in a workspace, edit, delete: Editor of the WORKSPACE;
- an Editor of a project who is not a member of the workspace may still add a
  contact, through `project`: it is created in the project's workspace and
  linked to that project at once. They may later edit what they created;
- linking / unlinking / relabelling on a project: Editor of that project.
"""

from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.projects.access import (
    Role,
    effective_access,
    get_access_map,
    workspace_access,
)
from apps.projects.permissions import ProjectScopedViewSet, WorkspaceScopedViewSet

from .models import Contact, ProjectContact
from .serializers import ContactSerializer, ProjectContactSerializer


def contact_context(request) -> dict:
    """Serializer context shared by both viewsets."""

    def can_edit(contact) -> bool:
        return (
            workspace_access(request, contact.workspace_id).has(Role.EDITOR)
            or contact.created_by_id == request.user.pk
        )

    return {"access_map": get_access_map(request), "can_edit": can_edit}


class ContactViewSet(WorkspaceScopedViewSet, viewsets.ModelViewSet):
    queryset = Contact.objects.select_related("workspace").prefetch_related(
        "tags", "project_links__project"
    )
    serializer_class = ContactSerializer
    pagination_class = None  # an address book is listed and searched whole
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    write_role = Role.EDITOR

    def get_serializer_context(self):
        return {**super().get_serializer_context(), **contact_context(self.request)}

    def get_queryset(self):
        # Stricter than the mixin's default (every contact of a visible
        # workspace): a guest only gets the contacts linked to their projects.
        visible = Contact.objects.for_user(self.request).values("pk")
        queryset = self.queryset.filter(pk__in=visible)
        params = self.request.query_params
        if params.get("workspace", "").isdigit():
            queryset = queryset.filter(workspace_id=params["workspace"])
        if params.get("project", "").isdigit():
            project_id = int(params["project"])
            access_map = get_access_map(self.request)
            branch = [project_id, *access_map.descendants(project_id)]
            readable = set(access_map.project_ids())
            queryset = queryset.filter(
                project_links__project_id__in=[p for p in branch if p in readable]
            ).distinct()
        if params.get("tag", "").isdigit():
            queryset = queryset.filter(tags=params["tag"])
        if params.get("job"):
            queryset = queryset.filter(job__iexact=params["job"])
        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(organization__icontains=search)
                | Q(job__icontains=search)
                | Q(email__icontains=search)
            )
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter("workspace", int),
            OpenApiParameter("project", int, description="Sous-projets inclus"),
            OpenApiParameter("tag", int),
            OpenApiParameter("job", str),
            OpenApiParameter("search", str),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def check_object_permissions(self, request, obj):
        # Skip the mixin's rule (workspace role only): the creator of a
        # contact may be a project guest. DRF's own checks still run.
        super(WorkspaceScopedViewSet, self).check_object_permissions(request, obj)
        if self.action in self.SAFE_ACTIONS:
            return
        if not contact_context(request)["can_edit"](obj):
            raise PermissionDenied(
                "Il faut être éditeur de l'espace, ou avoir créé ce contact."
            )

    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        project = data.pop("project", None)
        role_label = data.pop("role_label", "")
        if project is not None:
            access = effective_access(self.request, project)
            if access.role is None:  # invisible or shell: same answer
                raise ValidationError({"project": "Projet introuvable."})
            if not access.has(Role.EDITOR):
                raise PermissionDenied("Il faut être éditeur du projet.")
        else:
            self.check_workspace_access(data["workspace"])
        contact = serializer.save(created_by=self.request.user)
        if project is not None:
            ProjectContact.objects.create(
                project=project, contact=contact, role_label=role_label
            )


class ProjectContactViewSet(
    ProjectScopedViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Contacts of a project (`?project=`), each with its role there."""

    queryset = ProjectContact.objects.select_related(
        "project", "contact__workspace"
    ).prefetch_related("contact__tags", "contact__project_links__project")
    serializer_class = ProjectContactSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_context(self):
        return {**super().get_serializer_context(), **contact_context(self.request)}

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("project", "").isdigit():
            ids = [int(params["project"])]
            if params.get("include_descendants") in ("true", "1"):
                ids += get_access_map(self.request).descendants(ids[0])
            queryset = queryset.filter(project_id__in=ids)
        if params.get("contact", "").isdigit():
            queryset = queryset.filter(contact_id=params["contact"])
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter("project", int),
            OpenApiParameter("include_descendants", bool),
            OpenApiParameter("contact", int),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
