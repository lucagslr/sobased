"""The two building blocks every project-bound endpoint MUST use (SPEC §6).

- ProjectScopedQuerySet.for_user(): the only way to filter rows by rights.
- ProjectScopedViewSet: the DRF mixin that applies it and checks the role
  required by each action.

No view filters rights by hand. `tests/test_route_audit.py` fails the build if
an API view is neither based on a scoped mixin nor explicitly allow-listed.

Status codes: an object the user cannot see is a 404 (its existence is not
revealed); 403 means "you can see it, but this action needs a higher role".
"""

from rest_framework.exceptions import NotFound, PermissionDenied

from .access import Role, effective_access, get_access_map, workspace_access
from .querysets import ProjectScopedQuerySet  # noqa: F401  (re-exported)


class ProjectScopedViewSet:
    """Mixin for viewsets whose objects belong to a project.

    Declare roles with:
        read_role   = Role.VIEWER   (list, retrieve)
        write_role  = Role.EDITOR   (create, update, partial_update, destroy)
        action_roles = {"resolve": Role.COMMENTER}   (per-action overrides)
        finance = "" | "rw"  ("rw": reads need can_view_finance, writes
                              need can_edit_finance, on top of the role)

    The model's default manager must come from ProjectScopedQuerySet.
    """

    read_role = Role.VIEWER
    write_role = Role.EDITOR
    action_roles: dict[str, Role] = {}
    finance = ""
    SAFE_ACTIONS = ("list", "retrieve", "metadata")

    # --- Which role does this action need? ------------------------------------
    def required_role(self) -> Role:
        action = getattr(self, "action", None)
        if action in self.action_roles:
            return self.action_roles[action]
        return self.read_role if action in self.SAFE_ACTIONS else self.write_role

    def _finance_mode(self) -> str:
        if not self.finance:
            return ""
        return "view" if getattr(self, "action", None) in self.SAFE_ACTIONS else "edit"

    # --- Hooks ---------------------------------------------------------------------
    def get_project(self, obj):
        """The project an object belongs to. Override for indirect models."""
        return obj.project

    def get_queryset(self):
        # Everything the user can READ. A higher role needed by the action is
        # checked per object below, so that the answer is 403 and not 404.
        finance = "view" if self.finance else ""
        return (
            super()
            .get_queryset()
            .for_user(self.request, self.read_role, finance=finance)
        )

    def check_project_access(self, project, role: Role | None = None):
        """Raise 404 / 403 unless the user has `role` on `project`."""
        access = effective_access(self.request, project)
        mode = self._finance_mode()
        if not access.has(self.read_role) or (mode and not access.can_view_finance):
            raise NotFound()
        if not access.has(role or self.required_role()):
            raise PermissionDenied("Ton rôle sur ce projet ne permet pas cette action.")
        if mode == "edit" and not access.can_edit_finance:
            raise PermissionDenied("Tu n'as pas le droit de modifier la compta.")
        return access

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        self.check_project_access(self.get_project(obj))

    def perform_create(self, serializer):
        # The target project comes from the payload: check it before saving.
        project = serializer.validated_data.get("project")
        if project is not None:
            self.check_project_access(project)
        super().perform_create(serializer)


class WorkspaceScopedViewSet:
    """Same idea for objects that belong to a workspace (types, tags...).

    Reading only needs *any* presence in the workspace, shell included: a
    guest of one sub-project still needs the tag names shown on its tasks.
    """

    write_role = Role.ADMIN
    action_roles: dict[str, Role] = {}
    SAFE_ACTIONS = ("list", "retrieve", "metadata")

    def get_workspace(self, obj):
        return obj.workspace

    def visible_workspace_ids(self) -> list[int]:
        return list(get_access_map(self.request).workspaces)

    def get_queryset(self):
        return super().get_queryset().filter(workspace__in=self.visible_workspace_ids())

    def check_workspace_access(self, workspace, role: Role | None = None):
        access = workspace_access(self.request, workspace)
        if not access.visible:
            raise NotFound()
        if not access.has(role or self.write_role):
            raise PermissionDenied(
                "Ton rôle dans cet espace ne permet pas cette action."
            )
        return access

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        action = getattr(self, "action", None)
        if action not in self.SAFE_ACTIONS:
            self.check_workspace_access(
                self.get_workspace(obj), self.action_roles.get(action)
            )

    def perform_create(self, serializer):
        workspace = serializer.validated_data.get("workspace")
        if workspace is not None:
            self.check_workspace_access(workspace)
        super().perform_create(serializer)
