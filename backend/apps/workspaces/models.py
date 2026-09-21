"""Workspaces and what they define for their projects: project types and tags.

A workspace has no `owner` column on purpose: its owner is the Membership row
with role=owner (apps.projects.models), so that access rights have a single
source of truth. `Workspace.owner` below is a read-only convenience.
"""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel

hex_color_validator = RegexValidator(
    regex=r"^#[0-9A-Fa-f]{6}$", message="Couleur attendue au format #RRGGBB."
)

# SPEC §5. Created with every new workspace, then editable per workspace.
DEFAULT_PROJECT_TYPES = [
    "Artiste",
    "Album",
    "Single",
    "Clip",
    "Feat",
    "Release",
    "Date live",
    "Release party",
    "Tournage",
    "Documentaire",
    "Communication",
    "Visuel",
    "Administratif",
    "Demande de fonds",
    "Cours",
    "TP",
    "Rendu",
    "Examen",
    "Travail de bachelor",
    "Mandat",
    "Autre",
]
# The type a project falls back to when its own type is deleted.
FALLBACK_PROJECT_TYPE = "Autre"


class Workspace(TimeStampedModel):
    name = models.CharField(max_length=120)
    color = models.CharField(
        max_length=7, default="#CBD5E1", validators=[hex_color_validator]
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    @property
    def owner(self):
        membership = (
            self.memberships.filter(role="owner").select_related("user").first()
        )
        return membership.user if membership else None

    def create_defaults(self):
        """Seed the per-workspace lists. Called once, right after creation."""
        ProjectType.objects.bulk_create(
            ProjectType(workspace=self, name=name, position=index)
            for index, name in enumerate(DEFAULT_PROJECT_TYPES)
        )


class ProjectType(TimeStampedModel):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="project_types"
    )
    name = models.CharField(max_length=60)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(
                "workspace", Lower("name"), name="projecttype_unique_name_per_workspace"
            )
        ]

    def __str__(self):
        return self.name


class Tag(TimeStampedModel):
    """Cross-cutting label (SPEC §14): usable on projects, tasks, events, assets."""

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="tags"
    )
    name = models.CharField(max_length=40)
    color = models.CharField(
        max_length=7, default="#E2E8F0", validators=[hex_color_validator]
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "workspace", Lower("name"), name="tag_unique_name_per_workspace"
            )
        ]

    def __str__(self):
        return self.name
