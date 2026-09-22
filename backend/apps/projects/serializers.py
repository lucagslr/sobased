from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.workspaces.models import FALLBACK_PROJECT_TYPE, ProjectType, Tag, Workspace

from . import tree
from .models import Invitation, Membership, Project, ProjectUserState
from .models import Role as StoredRole

# Roles that can be granted through an invitation. "owner" only changes hands
# through the transfer-ownership endpoints.
GRANTABLE_ROLES = [c for c in StoredRole.choices if c[0] != StoredRole.OWNER]


class BreadcrumbSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    color = serializers.CharField()
    is_shell = serializers.BooleanField()


class ProjectNodeSerializer(serializers.Serializer):
    """One node of GET /api/projects/tree/ (a flat list; the front nests it).

    For a SHELL node only id, workspace, parent, depth, name, color and
    is_shell are filled: every other field is null (SPECIFICATIONS §1.2).
    """

    id = serializers.IntegerField()
    workspace = serializers.IntegerField()
    parent = serializers.IntegerField(allow_null=True)
    depth = serializers.IntegerField()
    name = serializers.CharField()
    color = serializers.CharField()
    is_shell = serializers.BooleanField()
    type = serializers.IntegerField(allow_null=True)
    type_name = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=Project.Status.choices, allow_null=True)
    start_date = serializers.DateField(allow_null=True)
    end_date = serializers.DateField(allow_null=True)
    temporal = serializers.ChoiceField(
        choices=[tree.PAST, tree.CURRENT, tree.UPCOMING], allow_null=True
    )
    end_overdue = serializers.BooleanField()
    tags = serializers.ListField(child=serializers.IntegerField())
    position = serializers.IntegerField()
    my_role = serializers.ChoiceField(choices=StoredRole.choices, allow_null=True)
    can_view_finance = serializers.BooleanField()
    can_edit_finance = serializers.BooleanField()


def project_node(project: Project, access, today=None) -> dict:
    """Build a tree node. `access` decides how much of the project is exposed."""
    node = {
        "id": project.pk,
        "workspace": project.workspace_id,
        "parent": project.parent_id,
        "depth": project.depth,
        "name": project.name,
        "color": project.color,
        "is_shell": access.is_shell,
        "type": None,
        "type_name": None,
        "status": None,
        "start_date": None,
        "end_date": None,
        "temporal": None,
        "end_overdue": False,
        "tags": [],
        "position": project.position,
        "my_role": None,
        "can_view_finance": False,
        "can_edit_finance": False,
    }
    if access.role is None:
        return node
    today = today or timezone.localdate()
    node.update(
        type=project.type_id,
        type_name=project.type.name,
        status=project.status,
        start_date=project.start_date,
        end_date=project.end_date,
        temporal=tree.temporal(project.status, project.start_date, today),
        end_overdue=tree.end_overdue(project.status, project.end_date, today),
        tags=[tag.pk for tag in project.tags.all()],
        my_role=access.role.stored,
        can_view_finance=access.can_view_finance,
        can_edit_finance=access.can_edit_finance,
    )
    return node


class ProjectSerializer(serializers.ModelSerializer):
    """Create / read / update a project the user has a real role on."""

    workspace = serializers.PrimaryKeyRelatedField(
        queryset=Workspace.objects.all(), required=False
    )
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    type = serializers.PrimaryKeyRelatedField(
        queryset=ProjectType.objects.all(), required=False
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )
    type_name = serializers.CharField(source="type.name", read_only=True)
    temporal = serializers.SerializerMethodField()
    end_overdue = serializers.SerializerMethodField()
    breadcrumb = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()
    can_view_finance = serializers.SerializerMethodField()
    can_edit_finance = serializers.SerializerMethodField()
    is_shell = serializers.SerializerMethodField()
    my_tasks_view = serializers.SerializerMethodField()
    # Google Drive (SPEC §11): creation asks for a folder (default yes when the
    # creator has Drive connected); the state is read-only, drive_status says
    # why an action is unavailable (owner disconnected, no folder).
    create_drive_folder = serializers.BooleanField(write_only=True, required=False)
    drive_status = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "workspace",
            "parent",
            "depth",
            "name",
            "description",
            "type",
            "type_name",
            "status",
            "start_date",
            "end_date",
            "color",
            "tags",
            "position",
            "temporal",
            "end_overdue",
            "breadcrumb",
            "my_role",
            "can_view_finance",
            "can_edit_finance",
            "is_shell",
            "my_tasks_view",
            "drive_folder_id",
            "drive_folder_url",
            "drive_share_with_members",
            "drive_status",
            "create_drive_folder",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "depth",
            "drive_folder_id",
            "drive_folder_url",
            "created_at",
            "updated_at",
        ]

    # --- Computed fields ----------------------------------------------------------
    @extend_schema_field(
        serializers.ChoiceField(
            choices=["none", "ok", "owner_disconnected", "parent_missing"]
        )
    )
    def get_drive_status(self, project) -> str:
        """none: no folder; ok: folder usable; owner_disconnected: folder exists
        but its Google account is gone or needs re-auth; parent_missing: a
        sub-project whose parent has no folder yet."""
        from apps.integrations import drive

        if project.drive_folder_id:
            try:
                drive.folder_owner(project)
            except drive.DriveUnavailable:
                return "owner_disconnected"
            return "ok"
        if project.parent_id and not project.parent.drive_folder_id:
            return "parent_missing"
        return "none"

    def _access(self, project):
        return self.context["access_map"].for_project(project.pk)

    def _today(self):
        # The view passes the user's local date; the server date is a fallback.
        return self.context.get("today") or timezone.localdate()

    @extend_schema_field(
        serializers.ChoiceField(choices=[tree.PAST, tree.CURRENT, tree.UPCOMING])
    )
    def get_temporal(self, project) -> str:
        return tree.temporal(project.status, project.start_date, self._today())

    def get_end_overdue(self, project) -> bool:
        return tree.end_overdue(project.status, project.end_date, self._today())

    @extend_schema_field(BreadcrumbSerializer(many=True))
    def get_breadcrumb(self, project) -> list[dict]:
        access_map = self.context["access_map"]
        return [
            {
                "id": ancestor.pk,
                "name": ancestor.name,
                "color": ancestor.color,
                "is_shell": access_map.for_project(ancestor.pk).is_shell,
            }
            for ancestor in tree.ancestors(project)
        ]

    @extend_schema_field(
        serializers.ChoiceField(choices=StoredRole.choices, allow_null=True)
    )
    def get_my_role(self, project) -> str | None:
        role = self._access(project).role
        return role.stored if role else None

    def get_can_view_finance(self, project) -> bool:
        return self._access(project).can_view_finance

    def get_can_edit_finance(self, project) -> bool:
        return self._access(project).can_edit_finance

    def get_is_shell(self, project) -> bool:
        return False

    @extend_schema_field(
        serializers.ChoiceField(choices=ProjectUserState.TasksView.choices)
    )
    def get_my_tasks_view(self, project) -> str:
        """The task view I used last on this project (SPEC §15: remembered
        per project, and per user: it follows me across devices)."""
        request = self.context.get("request")
        saved = (
            ProjectUserState.objects.filter(user=request.user, project=project)
            .values_list("tasks_view", flat=True)
            .first()
            if request is not None
            else None
        )
        return saved or ProjectUserState.TasksView.LIST

    # --- Validation ------------------------------------------------------------------
    def validate(self, attrs):
        if self.instance is None:
            attrs = self._validate_placement(attrs)
        else:
            # Moving is a dedicated endpoint with its own permission rule.
            attrs.pop("workspace", None)
            attrs.pop("parent", None)
        workspace = attrs.get("workspace") or self.instance.workspace

        project_type = attrs.get("type")
        if project_type is None and self.instance is None:
            attrs["type"] = (
                ProjectType.objects.filter(
                    workspace=workspace, name__iexact=FALLBACK_PROJECT_TYPE
                ).first()
                or ProjectType.objects.filter(workspace=workspace).first()
            )
            if attrs["type"] is None:
                raise serializers.ValidationError(
                    {"type": "Cet espace n'a aucun type de projet."}
                )
        elif project_type is not None and project_type.workspace_id != workspace.pk:
            raise serializers.ValidationError(
                {"type": "Ce type n'est pas de cet espace."}
            )

        for tag in attrs.get("tags", []):
            if tag.workspace_id != workspace.pk:
                raise serializers.ValidationError(
                    {"tags": "Ce tag n'est pas de cet espace."}
                )

        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "La fin ne peut pas précéder le début."}
            )
        return attrs

    def _validate_placement(self, attrs):
        parent = attrs.get("parent")
        if parent is not None:
            # The 4-level limit is enforced by the view, after the permission
            # check: someone without rights must get 403, not a hint about depth.
            attrs["workspace"] = parent.workspace
        elif attrs.get("workspace") is None:
            raise serializers.ValidationError(
                {"workspace": "Indique l'espace (ou le projet parent)."}
            )
        return attrs


class OverdueProjectSerializer(serializers.ModelSerializer):
    """What the "fin dépassée" modal needs: « MARCHIOLY devait se terminer le … »."""

    class Meta:
        model = Project
        fields = ["id", "name", "color", "end_date", "status"]
        read_only_fields = fields


class MyProjectStateSerializer(serializers.ModelSerializer):
    """PATCH /api/projects/{id}/my-state/: my own preferences on a project."""

    class Meta:
        model = ProjectUserState
        fields = ["tasks_view"]


class ShellProjectSerializer(serializers.Serializer):
    """All a shell member may learn about an ancestor project."""

    id = serializers.IntegerField()
    workspace = serializers.IntegerField(source="workspace_id")
    parent = serializers.IntegerField(source="parent_id", allow_null=True)
    depth = serializers.IntegerField()
    name = serializers.CharField()
    color = serializers.CharField()
    is_shell = serializers.BooleanField(default=True)
    breadcrumb = BreadcrumbSerializer(many=True)


class MoveProjectSerializer(serializers.Serializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), allow_null=True
    )


# --- Memberships --------------------------------------------------------------------


class InheritedGrantSerializer(serializers.Serializer):
    scope_type = serializers.ChoiceField(choices=["workspace", "project"])
    scope_id = serializers.IntegerField()
    scope_name = serializers.CharField()
    role = serializers.ChoiceField(choices=StoredRole.choices)


class DirectMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "role", "can_view_finance", "can_edit_finance"]


class EffectiveMemberSerializer(serializers.Serializer):
    """One person with access to a scope: effective rights and where they come from."""

    user = PublicUserSerializer()
    role = serializers.ChoiceField(choices=StoredRole.choices)
    can_view_finance = serializers.BooleanField()
    can_edit_finance = serializers.BooleanField()
    # Membership on THIS scope (editable here), or null if purely inherited.
    direct = DirectMembershipSerializer(allow_null=True)
    inherited_from = InheritedGrantSerializer(many=True)


class MembershipCreateSerializer(serializers.Serializer):
    """Invite by username (existing account) or by e-mail."""

    workspace = serializers.PrimaryKeyRelatedField(
        queryset=Workspace.objects.all(), required=False
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False
    )
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=GRANTABLE_ROLES)
    can_view_finance = serializers.BooleanField(
        required=False, allow_null=True, default=None
    )
    can_edit_finance = serializers.BooleanField(
        required=False, allow_null=True, default=None
    )

    def validate(self, attrs):
        if bool(attrs.get("workspace")) == bool(attrs.get("project")):
            raise serializers.ValidationError("Indique un espace OU un projet.")
        if bool(attrs.get("username")) == bool(attrs.get("email")):
            raise serializers.ValidationError(
                "Indique un nom d'utilisateur OU un e-mail."
            )
        # SPEC §6: finance options default to true for admins, false otherwise.
        default = Membership.default_finance_flag(attrs["role"])
        for flag in ("can_view_finance", "can_edit_finance"):
            if attrs.get(flag) is None:
                attrs[flag] = default
        if attrs["can_edit_finance"]:
            attrs["can_view_finance"] = True
        return attrs


class MembershipUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=GRANTABLE_ROLES, required=False)

    class Meta:
        model = Membership
        fields = ["id", "role", "can_view_finance", "can_edit_finance"]


class InvitationSerializer(serializers.ModelSerializer):
    invited_by = PublicUserSerializer(read_only=True)
    is_pending = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invitation
        fields = [
            "id",
            "email",
            "workspace",
            "project",
            "role",
            "can_view_finance",
            "can_edit_finance",
            "invited_by",
            "expires_at",
            "is_pending",
            "created_at",
        ]
        read_only_fields = fields


class InvitationLookupSerializer(serializers.Serializer):
    """What the (public) acceptance page shows about an invitation."""

    email = serializers.EmailField()
    scope_type = serializers.ChoiceField(choices=["workspace", "project"])
    scope_name = serializers.CharField()
    role = serializers.ChoiceField(choices=StoredRole.choices)
    invited_by = serializers.CharField(allow_null=True)
    is_pending = serializers.BooleanField()


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
