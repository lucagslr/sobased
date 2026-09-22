"""Projects (a tree of at most 4 levels), memberships and invitations.

Access rights are NOT computed here: see access.py (one resolution function)
and permissions.py (the DRF mixin and the queryset filter built on it).
"""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.workspaces.models import ProjectType, Tag, Workspace, hex_color_validator

from .querysets import ProjectQuerySet

MAX_DEPTH = 4
INVITATION_LIFETIME = timedelta(days=14)


class Role(models.TextChoices):
    """Stored role. Ranking and comparison live in access.py (RANK)."""

    VIEWER = "viewer", "Lecteur"
    COMMENTER = "commenter", "Commentateur"
    EDITOR = "editor", "Éditeur"
    ADMIN = "admin", "Admin"
    OWNER = "owner", "Propriétaire"


class Project(TimeStampedModel):
    class Status(models.TextChoices):
        IDEA = "idea", "Idée"
        PLANNED = "planned", "Planifié"
        IN_PROGRESS = "in_progress", "En cours"
        TO_VALIDATE = "to_validate", "À valider"
        DONE = "done", "Terminé"
        CANCELLED = "cancelled", "Annulé"
        ARCHIVED = "archived", "Archivé"

    # A project in one of these statuses is over: no overdue modal, "Passé".
    CLOSED_STATUSES = (Status.DONE, Status.CANCELLED, Status.ARCHIVED)

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="projects"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    # Denormalised from the parent chain; kept right by save() and move().
    depth = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    # RESTRICT, not PROTECT: a type in use cannot be deleted on its own, but
    # deleting the whole workspace (projects AND types) must still cascade.
    type = models.ForeignKey(
        ProjectType, on_delete=models.RESTRICT, related_name="projects"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLANNED
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    color = models.CharField(
        max_length=7, default="#BFDBFE", validators=[hex_color_validator]
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="projects")
    position = models.PositiveIntegerField(default=0)
    drive_folder_id = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["position", "name", "id"]
        indexes = [
            models.Index(fields=["workspace", "parent"]),
            models.Index(fields=["end_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(depth__gte=1) & Q(depth__lte=MAX_DEPTH),
                name="project_depth_between_1_and_4",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent_id:
            if self.parent.workspace_id != self.workspace_id:
                raise ValidationError("Le parent doit être dans le même espace.")
            if self.parent.depth >= MAX_DEPTH:
                raise ValidationError(
                    f"Un projet ne peut pas dépasser {MAX_DEPTH} niveaux."
                )
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "La fin ne peut pas précéder le début."})

    def save(self, *args, **kwargs):
        self.depth = self.parent.depth + 1 if self.parent_id else 1
        super().save(*args, **kwargs)


# Importable path for drf-spectacular's ENUM_NAME_OVERRIDES (it cannot resolve
# a nested class such as Project.Status).
PROJECT_STATUS_CHOICES = Project.Status.choices


class Membership(TimeStampedModel):
    """A user's role on ONE scope: a workspace, or a project.

    Exactly one of `workspace` / `project` is set. Rights then flow down the
    tree (see access.py). The owner of a scope is simply the row with
    role=owner, and there is at most one per scope.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    workspace = models.ForeignKey(
        Workspace,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=12, choices=Role.choices)
    can_view_finance = models.BooleanField(default=False)
    can_edit_finance = models.BooleanField(default=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(workspace__isnull=False, project__isnull=True)
                    | Q(workspace__isnull=True, project__isnull=False)
                ),
                name="membership_exactly_one_scope",
            ),
            models.UniqueConstraint(
                fields=["user", "workspace"],
                condition=Q(workspace__isnull=False),
                name="membership_unique_user_workspace",
            ),
            models.UniqueConstraint(
                fields=["user", "project"],
                condition=Q(project__isnull=False),
                name="membership_unique_user_project",
            ),
            models.UniqueConstraint(
                fields=["workspace"],
                condition=Q(role="owner", workspace__isnull=False),
                name="membership_single_owner_per_workspace",
            ),
            models.UniqueConstraint(
                fields=["project"],
                condition=Q(role="owner", project__isnull=False),
                name="membership_single_owner_per_project",
            ),
        ]

    def save(self, *args, **kwargs):
        # An owner always has full finance rights; editing implies viewing.
        if self.role == Role.OWNER:
            self.can_view_finance = self.can_edit_finance = True
        if self.can_edit_finance:
            self.can_view_finance = True
        super().save(*args, **kwargs)

    @property
    def scope(self):
        return self.workspace if self.workspace_id else self.project

    @staticmethod
    def default_finance_flag(role: str) -> bool:
        """SPEC §6: true by default for admins and owners, false otherwise."""
        return role in (Role.ADMIN, Role.OWNER)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Invitation(TimeStampedModel):
    """Pending invitation of an e-mail address that has no (verified) account.

    Only the SHA-256 of the token is stored: a database leak does not leak
    working invitation links. The clear token exists only in the e-mail.
    """

    email = models.EmailField()
    workspace = models.ForeignKey(
        Workspace,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    role = models.CharField(max_length=12, choices=Role.choices)
    can_view_finance = models.BooleanField(default=False)
    can_edit_finance = models.BooleanField(default=False)
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(workspace__isnull=False, project__isnull=True)
                    | Q(workspace__isnull=True, project__isnull=False)
                ),
                name="invitation_exactly_one_scope",
            ),
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def scope(self):
        return self.workspace if self.workspace_id else self.project

    @property
    def is_pending(self) -> bool:
        return self.accepted_at is None and self.expires_at > timezone.now()

    def issue_token(self) -> str:
        """Set a fresh token and expiry. Returns the clear token (to e-mail)."""
        token = secrets.token_urlsafe(32)
        self.token_hash = hash_token(token)
        self.expires_at = timezone.now() + INVITATION_LIFETIME
        return token

    @classmethod
    def find_by_token(cls, token: str):
        return cls.objects.filter(token_hash=hash_token(token)).first()


class ProjectUserState(TimeStampedModel):
    """What ONE user remembers about ONE project (nothing shared).

    - `overdue_snoozed_until`: "Me rappeler demain" in the end-date modal.
      The answer is personal; "Terminé" and "Reprogrammer" change the project
      itself and therefore apply to everybody.
    - `tasks_view`: the task view last used on this project (phase 5).
    """

    class TasksView(models.TextChoices):
        LIST = "list", "Liste"
        KANBAN = "kanban", "Kanban"
        CALENDAR = "calendar", "Calendrier"
        GANTT = "gantt", "Gantt"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_states",
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="user_states"
    )
    tasks_view = models.CharField(
        max_length=10, choices=TasksView.choices, default=TasksView.LIST
    )
    overdue_snoozed_until = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "project"], name="projectuserstate_unique_user_project"
            )
        ]


# Importable path for drf-spectacular's ENUM_NAME_OVERRIDES.
TASKS_VIEW_CHOICES = ProjectUserState.TasksView.choices
