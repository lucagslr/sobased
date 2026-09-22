"""Projects, memberships and invitations endpoints.

Every rights decision goes through access.py: ProjectViewSet via the
ProjectScopedViewSet mixin, the membership and invitation views via
`_require()` below, which is a thin wrapper around the same two functions.
"""

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.signals import email_verified
from apps.core.localtime import local_today
from apps.workspaces.models import Workspace

from . import services, tree
from .access import (
    Role,
    effective_access,
    get_access_map,
    invalidate_access_map,
    workspace_access,
)
from .models import MAX_DEPTH, Invitation, Membership, Project, ProjectUserState
from .models import Role as StoredRole
from .permissions import ProjectScopedViewSet
from .serializers import (
    EffectiveMemberSerializer,
    InvitationAcceptSerializer,
    InvitationLookupSerializer,
    InvitationSerializer,
    MembershipCreateSerializer,
    MembershipUpdateSerializer,
    MoveProjectSerializer,
    MyProjectStateSerializer,
    OverdueProjectSerializer,
    ProjectNodeSerializer,
    ProjectSerializer,
    ShellProjectSerializer,
    project_node,
)

# --- Shared helpers ------------------------------------------------------------------


def _scope_access(request, scope):
    if isinstance(scope, Workspace):
        return workspace_access(request, scope)
    return effective_access(request, scope)


def _require(request, scope, minimum: Role):
    """404 if `scope` is invisible (or only a shell), 403 if the role is too low."""
    access = _scope_access(request, scope)
    if access.role is None:
        raise NotFound()
    if not access.has(minimum):
        raise PermissionDenied("Ton rôle ne permet pas cette action.")
    return access


def _require_container(request, container, minimum: Role):
    """Role needed on the PLACE an already-visible object lives in or moves to.

    Always 403, never 404: the user is acting on an object they can see, so
    "this does not exist" would be a confusing answer when the parent (or the
    workspace) happens to be a shell for them.
    """
    if not _scope_access(request, container).has(minimum):
        raise PermissionDenied(
            "Il faut être au moins éditeur de l'élément parent pour faire ça."
        )


def _scope_from_query(request):
    """Resolve ?workspace=<id> or ?project=<id> to the scope object."""
    workspace_id = request.query_params.get("workspace")
    project_id = request.query_params.get("project")
    if bool(workspace_id) == bool(project_id):
        raise ValidationError("Indique ?workspace= ou ?project=.")
    model, pk = (Workspace, workspace_id) if workspace_id else (Project, project_id)
    scope = model.objects.filter(pk=pk).first() if str(pk).isdigit() else None
    if scope is None:
        raise NotFound()
    return scope


SCOPE_PARAMETERS = [
    OpenApiParameter("workspace", int, description="Portée : un espace"),
    OpenApiParameter("project", int, description="Portée : un projet"),
]


# --- Projects -----------------------------------------------------------------------


class ProjectViewSet(
    ProjectScopedViewSet,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Projects. There is no flat list: navigation uses the `tree` action."""

    queryset = Project.objects.select_related("type", "parent").prefetch_related("tags")
    serializer_class = ProjectSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    action_roles = {
        "move": Role.ADMIN,
        "transfer_ownership": Role.OWNER,
        "snooze_overdue": Role.EDITOR,
        # A personal preference, not a change of the project: readers too.
        "my_state": Role.VIEWER,
    }

    def get_project(self, obj):
        return obj

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "access_map": get_access_map(self.request),
            "today": local_today(self.request.user),
        }

    # --- Read ---------------------------------------------------------------------
    @extend_schema(
        parameters=[
            OpenApiParameter("workspace", int, description="Limiter à un espace"),
            OpenApiParameter("include_archived", bool),
        ],
        responses={200: ProjectNodeSerializer(many=True)},
    )
    @action(detail=False, pagination_class=None)
    def tree(self, request):
        """Every node the user can see, shells included, as a flat list."""
        access_map = get_access_map(request)
        queryset = self.queryset.filter(pk__in=access_map.visible_project_ids())
        workspace_id = request.query_params.get("workspace", "")
        if workspace_id.isdigit():
            queryset = queryset.filter(workspace_id=workspace_id)
        if request.query_params.get("include_archived") not in ("true", "1"):
            # An archived project takes its whole branch with it: its children
            # would otherwise show up as roots, their parent being absent.
            archived = set(
                queryset.filter(status=Project.Status.ARCHIVED).values_list(
                    "pk", flat=True
                )
            )
            hidden = [
                pid
                for pid in access_map.visible_project_ids()
                if pid in archived
                or any(parent in archived for parent in access_map.ancestors(pid))
            ]
            queryset = queryset.exclude(pk__in=hidden)
        today = local_today(request.user)
        nodes = [
            project_node(project, access_map.for_project(project.pk), today)
            for project in queryset.order_by("depth", "position", "name")
        ]
        return Response(ProjectNodeSerializer(nodes, many=True).data)

    @extend_schema(responses={200: OverdueProjectSerializer(many=True)})
    @action(detail=False, pagination_class=None)
    def overdue(self, request):
        """Queue of the "fin dépassée" modal (SPEC §5).

        Projects whose end date has passed (in MY timezone) while still open,
        where I may edit, and that I have not snoozed until tomorrow. Oldest
        first. As soon as any editor answers "Terminé" or "Reprogrammer" the
        project leaves everybody's queue, because the project itself changed.
        """
        today = local_today(request.user)
        editable = get_access_map(request).project_ids(Role.EDITOR)
        snoozed = ProjectUserState.objects.filter(
            user=request.user, overdue_snoozed_until__gte=today
        ).values("project_id")
        projects = (
            Project.objects.filter(pk__in=editable, end_date__lt=today)
            .exclude(status__in=Project.CLOSED_STATUSES)
            .exclude(pk__in=snoozed)
            .order_by("end_date", "id")
        )
        return Response(OverdueProjectSerializer(projects, many=True).data)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"], url_path="snooze-overdue")
    def snooze_overdue(self, request, pk=None):
        """ "Me rappeler demain": hides the modal for ME until tomorrow."""
        project = self.get_object()  # editor or more, see action_roles
        ProjectUserState.objects.update_or_create(
            user=request.user,
            project=project,
            defaults={"overdue_snoozed_until": local_today(request.user)},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=MyProjectStateSerializer, responses={200: MyProjectStateSerializer}
    )
    @action(detail=True, methods=["patch"], url_path="my-state")
    def my_state(self, request, pk=None):
        """Remember MY task view (list / kanban / calendar / gantt) on this
        project. Stored on the server so that it follows me across devices."""
        project = self.get_object()
        serializer = MyProjectStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ProjectUserState.objects.update_or_create(
            user=request.user, project=project, defaults=serializer.validated_data
        )
        return Response(serializer.data)

    @extend_schema(responses={200: ProjectSerializer})
    def retrieve(self, request, *args, **kwargs):
        """Full project, or the reduced "shell" view of an ancestor."""
        project = self.queryset.filter(pk=kwargs["pk"]).first()
        access = effective_access(request, project) if project else None
        if project is None or not access.visible:
            raise NotFound()
        if access.is_shell:
            access_map = get_access_map(request)
            shell = {
                "id": project.pk,
                "workspace_id": project.workspace_id,
                "parent_id": project.parent_id,
                "depth": project.depth,
                "name": project.name,
                "color": project.color,
                "is_shell": True,
                "breadcrumb": [
                    {
                        "id": ancestor.pk,
                        "name": ancestor.name,
                        "color": ancestor.color,
                        "is_shell": access_map.for_project(ancestor.pk).is_shell,
                    }
                    for ancestor in tree.ancestors(project)
                ],
            }
            return Response(ShellProjectSerializer(shell).data)
        return Response(self.get_serializer(project).data)

    # --- Write --------------------------------------------------------------------
    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        parent = data.get("parent")
        if parent is not None:
            # A sub-project is content of its parent: editors may add one.
            self.check_project_access(parent, Role.EDITOR)
            if parent.depth >= MAX_DEPTH:
                raise ValidationError(
                    {"parent": f"Un projet ne peut pas dépasser {MAX_DEPTH} niveaux."}
                )
        else:
            _require(self.request, data["workspace"], Role.EDITOR)
        siblings = Project.objects.filter(workspace=data["workspace"], parent=parent)
        wants_folder = data.pop("create_drive_folder", None)
        project = serializer.save(
            created_by=self.request.user, position=siblings.count()
        )
        self._queue_drive_folder(project, wants_folder)
        if parent is None:
            # Like a Drive file: whoever creates a root project owns it (D5).
            Membership.objects.create(
                user=self.request.user, project=project, role=StoredRole.OWNER
            )
        invalidate_access_map(self.request)
        serializer.context["access_map"] = get_access_map(self.request)

    def _queue_drive_folder(self, project, wants_folder):
        """SPEC §11: a root project gets a Drive folder when the creator has
        Drive connected (option checked by default); a sub-project gets one
        under its parent's folder. Done after the commit, in Celery: a slow
        or failing Google never blocks the creation."""
        from apps.integrations import drive
        from apps.integrations.tasks import create_project_folder

        account = drive.drive_account(self.request.user)
        if project.parent_id:
            if wants_folder is False or not project.parent.drive_folder_id:
                return
            account_id = None
        else:
            if account is None or wants_folder is False:
                return
            account_id = account.pk
        transaction.on_commit(
            lambda: create_project_folder.delay(project.pk, account_id)
        )

    def perform_update(self, serializer):
        before = serializer.instance.drive_share_with_members
        serializer.validated_data.pop("create_drive_folder", None)
        project = serializer.save()
        if project.drive_share_with_members and not before and project.drive_folder_id:
            from apps.integrations.tasks import share_project_folder

            transaction.on_commit(lambda: share_project_folder.delay(project.pk))

    def destroy(self, request, *args, **kwargs):
        """Sub-project: editor of the PARENT. Root project: owner (D5)."""
        project = self.get_object()  # 404 unless readable
        if project.parent_id:
            _require_container(request, project.parent, Role.EDITOR)
        else:
            self.check_project_access(project, Role.OWNER)
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def check_object_permissions(self, request, obj):
        # destroy() applies its own rule (it depends on the parent).
        if self.action == "destroy":
            self.check_project_access(obj, Role.VIEWER)
            return
        super().check_object_permissions(request, obj)

    @extend_schema(request=MoveProjectSerializer, responses={200: ProjectSerializer})
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def move(self, request, pk=None):
        """Re-parent inside the workspace: admin here, editor on the target."""
        project = self.get_object()
        serializer = MoveProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_parent = serializer.validated_data["parent"]
        _require_container(request, new_parent or project.workspace, Role.EDITOR)
        try:
            tree.move(project, new_parent)
        except ValueError as exc:
            raise ValidationError({"parent": str(exc)}) from exc
        invalidate_access_map(request)
        project.refresh_from_db()
        context = {
            **self.get_serializer_context(),
            "access_map": get_access_map(request),
        }
        return Response(ProjectSerializer(project, context=context).data)

    @extend_schema(
        request=inline_serializer(
            "TransferProjectOwnership", {"username": serializers.CharField()}
        ),
        responses={200: ProjectSerializer},
    )
    @action(detail=True, methods=["post"], url_path="transfer-ownership")
    @transaction.atomic
    def transfer_ownership(self, request, pk=None):
        """Root projects only: hand ownership to someone with direct access."""
        project = self.get_object()
        if project.parent_id:
            raise ValidationError("Seul un projet racine a un propriétaire.")
        target = Membership.objects.filter(
            project=project, user__username__iexact=request.data.get("username", "")
        ).first()
        if target is None or target.user_id == request.user.pk:
            raise ValidationError(
                {"username": "Choisis un membre direct de ce projet."}
            )
        current = Membership.objects.filter(
            project=project, role=StoredRole.OWNER
        ).first()
        if current is not None:  # demote first: one owner per project
            current.role = StoredRole.ADMIN
            current.save()
        target.role = StoredRole.OWNER
        target.save()
        invalidate_access_map(request)
        return Response(self.get_serializer(project).data)


# --- Memberships --------------------------------------------------------------------


def _effective_members(scope) -> list[dict]:
    """Everyone with access to `scope`, with effective rights and their origin."""
    if isinstance(scope, Workspace):
        chain, workspace = [], scope
    else:
        chain, workspace = [*tree.ancestors(scope), scope], scope.workspace
    memberships = (
        Membership.objects.filter(workspace=workspace)
        | Membership.objects.filter(project__in=chain)
    ).select_related("user", "workspace", "project")

    by_user: dict[int, dict] = {}
    for membership in memberships:
        entry = by_user.setdefault(
            membership.user_id,
            {
                "user": membership.user,
                "rank": Role.from_stored(membership.role),
                "can_view_finance": False,
                "can_edit_finance": False,
                "direct": None,
                "inherited_from": [],
            },
        )
        entry["rank"] = max(entry["rank"], Role.from_stored(membership.role))
        entry["can_view_finance"] |= membership.can_view_finance
        entry["can_edit_finance"] |= membership.can_edit_finance
        if membership.scope == scope:
            entry["direct"] = membership
        else:
            entry["inherited_from"].append(
                {
                    "scope_type": "workspace" if membership.workspace_id else "project",
                    "scope_id": membership.scope.pk,
                    "scope_name": membership.scope.name,
                    "role": membership.role,
                }
            )
    members = sorted(
        by_user.values(), key=lambda e: (-e["rank"], e["user"].username.lower())
    )
    for entry in members:
        entry["role"] = entry.pop("rank").stored
    return members


class MembershipViewSet(viewsets.GenericViewSet):
    """Who has access to a workspace or a project, and managing it.

    - list: any real member of the scope (viewer and up). Shells see nothing.
    - create / update / delete: admins of the scope the membership is on.
      An admin may change or remove another admin, never the owner, and nobody
      can grant "owner" here (SPEC §6).
    - anyone may delete their own membership, except the owner.
    """

    queryset = Membership.objects.select_related("workspace", "project", "user")
    serializer_class = MembershipUpdateSerializer
    pagination_class = None

    def _get_membership(self, pk):
        membership = self.queryset.filter(pk=pk).first()
        if (
            membership is None
            or _scope_access(self.request, membership.scope).role is None
        ):
            raise NotFound()
        return membership

    def _check_finance_grant(self, access, data):
        # Nobody can hand out a finance right they do not hold themselves.
        for flag in ("can_view_finance", "can_edit_finance"):
            if data.get(flag) and not getattr(access, flag):
                raise PermissionDenied(
                    "Tu ne peux pas donner un droit compta que tu n'as pas."
                )

    @extend_schema(
        parameters=SCOPE_PARAMETERS,
        responses={200: EffectiveMemberSerializer(many=True)},
    )
    def list(self, request):
        scope = _scope_from_query(request)
        _require(request, scope, Role.VIEWER)
        return Response(
            EffectiveMemberSerializer(_effective_members(scope), many=True).data
        )

    @extend_schema(
        request=MembershipCreateSerializer,
        responses={
            201: inline_serializer(
                "InviteResult",
                {
                    "kind": serializers.ChoiceField(
                        choices=["membership", "invitation"]
                    ),
                    "detail": serializers.CharField(),
                },
            )
        },
    )
    def create(self, request):
        serializer = MembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        scope = data.get("workspace") or data.get("project")
        access = _require(request, scope, Role.ADMIN)
        self._check_finance_grant(access, data)
        if not request.user.email_verified:
            raise PermissionDenied("Confirme ton adresse e-mail avant d'inviter.")
        try:
            kind, _ = services.invite(
                actor=request.user,
                scope=scope,
                role=data["role"],
                can_view_finance=data["can_view_finance"],
                can_edit_finance=data["can_edit_finance"],
                username=data.get("username", ""),
                email=data.get("email", ""),
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        detail = (
            "Accès donné."
            if kind == "membership"
            else "Invitation envoyée par e-mail (valable 14 jours)."
        )
        code = (
            status.HTTP_201_CREATED
            if kind == "membership"
            else status.HTTP_202_ACCEPTED
        )
        return Response({"kind": kind, "detail": detail}, status=code)

    @extend_schema(
        request=MembershipUpdateSerializer, responses=MembershipUpdateSerializer
    )
    def partial_update(self, request, pk=None):
        membership = self._get_membership(pk)
        access = _require(request, membership.scope, Role.ADMIN)
        if membership.role == StoredRole.OWNER:
            raise PermissionDenied("Le rôle du propriétaire ne se modifie pas.")
        serializer = MembershipUpdateSerializer(
            membership, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        self._check_finance_grant(access, serializer.validated_data)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(responses={204: None})
    def destroy(self, request, pk=None):
        membership = self._get_membership(pk)
        if membership.role == StoredRole.OWNER:
            raise PermissionDenied("Le propriétaire ne peut pas être retiré.")
        if membership.user_id != request.user.pk:  # leaving is always allowed
            _require(request, membership.scope, Role.ADMIN)
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Invitations --------------------------------------------------------------------


class InvitationViewSet(viewsets.GenericViewSet):
    """Pending invitations of a scope. Admins only (they contain e-mails)."""

    queryset = Invitation.objects.select_related("workspace", "project", "invited_by")
    serializer_class = InvitationSerializer
    pagination_class = None

    def _get_invitation(self, pk):
        invitation = self.queryset.filter(pk=pk, accepted_at__isnull=True).first()
        if invitation is None:
            raise NotFound()
        _require(self.request, invitation.scope, Role.ADMIN)
        return invitation

    @extend_schema(
        parameters=SCOPE_PARAMETERS, responses=InvitationSerializer(many=True)
    )
    def list(self, request):
        scope = _scope_from_query(request)
        _require(request, scope, Role.ADMIN)
        key = "workspace" if isinstance(scope, Workspace) else "project"
        pending = self.queryset.filter(accepted_at__isnull=True, **{key: scope})
        return Response(InvitationSerializer(pending, many=True).data)

    @extend_schema(responses={204: None})
    def destroy(self, request, pk=None):
        self._get_invitation(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses=InvitationSerializer)
    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        """New link, new 14 days. The previous link stops working."""
        invitation = self._get_invitation(pk)
        token = invitation.issue_token()
        invitation.save()
        services.send_invitation_email(invitation, token)
        return Response(InvitationSerializer(invitation).data)

    @extend_schema(request=InvitationAcceptSerializer, responses={200: None})
    @action(detail=False, methods=["post"])
    def accept(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = Invitation.find_by_token(serializer.validated_data["token"])
        if invitation is None or not invitation.is_pending:
            raise ValidationError({"detail": "Invitation invalide ou expirée."})
        services.accept(invitation, request.user)
        # Opening a link received at this address proves the address is theirs.
        if invitation.email == request.user.email and not request.user.email_verified:
            request.user.email_verified_at = timezone.now()
            request.user.save(update_fields=["email_verified_at"])
            email_verified.send(sender=type(request.user), user=request.user)
        scope = invitation.scope
        return Response(
            {
                "scope_type": "workspace" if invitation.workspace_id else "project",
                "scope_id": scope.pk,
            }
        )


class InvitationLookupView(APIView):
    """Public: what the acceptance page shows before sign-in or sign-up."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invitation_lookup"

    @extend_schema(responses={200: InvitationLookupSerializer})
    def get(self, request, token):
        invitation = Invitation.find_by_token(token)
        if invitation is None or invitation.accepted_at is not None:
            raise NotFound()
        inviter = invitation.invited_by
        return Response(
            InvitationLookupSerializer(
                {
                    "email": invitation.email,
                    "scope_type": "workspace" if invitation.workspace_id else "project",
                    "scope_name": invitation.scope.name,
                    "role": invitation.role,
                    "invited_by": inviter.display_name if inviter else None,
                    "is_pending": invitation.is_pending,
                }
            ).data
        )
