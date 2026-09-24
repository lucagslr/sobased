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


class ProjectCategory(models.TextChoices):
    """The broad family a project type belongs to. Fixed in code: the form
    asks for the family first, then for the type (editable per workspace).
    Written for independents: labels, producers, film makers, students,
    freelancers."""

    STRUCTURE = "structure", "Artistes & structures"
    MUSIC = "music", "Production musicale"
    VIDEO = "video", "Audiovisuel"
    LIVE = "live", "Live & événements"
    RELEASE = "release", "Sortie & promotion"
    COMMUNICATION = "communication", "Communication & contenu"
    ADMIN = "admin", "Administratif & financement"
    STUDIES = "studies", "Études"
    CLIENT = "client", "Mandats & clients"
    PERSONAL = "personal", "Personnel"
    OTHER = "other", "Autre"


PROJECT_CATEGORY_CHOICES = ProjectCategory.choices

# SPEC §5, widened on 24.09.2026: (category, name), created with every new
# workspace in this order, then editable per workspace.
DEFAULT_PROJECT_TYPES = [
    (ProjectCategory.STRUCTURE, "Artiste"),
    (ProjectCategory.STRUCTURE, "Groupe"),
    (ProjectCategory.STRUCTURE, "Label"),
    (ProjectCategory.STRUCTURE, "Collectif"),
    (ProjectCategory.STRUCTURE, "Compagnie"),
    (ProjectCategory.MUSIC, "Album"),
    (ProjectCategory.MUSIC, "EP"),
    (ProjectCategory.MUSIC, "Single"),
    (ProjectCategory.MUSIC, "Mixtape"),
    (ProjectCategory.MUSIC, "Feat"),
    (ProjectCategory.MUSIC, "Remix"),
    (ProjectCategory.MUSIC, "Beat / instru"),
    (ProjectCategory.MUSIC, "Bande originale"),
    (ProjectCategory.MUSIC, "Session studio"),
    (ProjectCategory.MUSIC, "Mixage"),
    (ProjectCategory.MUSIC, "Mastering"),
    (ProjectCategory.MUSIC, "Pressage"),
    (ProjectCategory.VIDEO, "Clip"),
    (ProjectCategory.VIDEO, "Court-métrage"),
    (ProjectCategory.VIDEO, "Long-métrage"),
    (ProjectCategory.VIDEO, "Documentaire"),
    (ProjectCategory.VIDEO, "Série"),
    (ProjectCategory.VIDEO, "Tournage"),
    (ProjectCategory.VIDEO, "Montage"),
    (ProjectCategory.VIDEO, "Teaser"),
    (ProjectCategory.VIDEO, "Captation live"),
    (ProjectCategory.VIDEO, "Aftermovie"),
    (ProjectCategory.LIVE, "Date live"),
    (ProjectCategory.LIVE, "Tournée"),
    (ProjectCategory.LIVE, "Festival"),
    (ProjectCategory.LIVE, "Release party"),
    (ProjectCategory.LIVE, "Showcase"),
    (ProjectCategory.LIVE, "Résidence"),
    (ProjectCategory.LIVE, "Soirée"),
    (ProjectCategory.LIVE, "Exposition"),
    (ProjectCategory.RELEASE, "Release"),
    (ProjectCategory.RELEASE, "Campagne de sortie"),
    (ProjectCategory.RELEASE, "Distribution"),
    (ProjectCategory.RELEASE, "Playlisting"),
    (ProjectCategory.RELEASE, "Relations presse"),
    (ProjectCategory.RELEASE, "Radio / TV"),
    (ProjectCategory.COMMUNICATION, "Communication"),
    (ProjectCategory.COMMUNICATION, "Réseaux sociaux"),
    (ProjectCategory.COMMUNICATION, "Site web"),
    (ProjectCategory.COMMUNICATION, "Newsletter"),
    (ProjectCategory.COMMUNICATION, "Visuel"),
    (ProjectCategory.COMMUNICATION, "Identité visuelle"),
    (ProjectCategory.COMMUNICATION, "Photo"),
    (ProjectCategory.COMMUNICATION, "Merch"),
    (ProjectCategory.COMMUNICATION, "Affiche / flyer"),
    (ProjectCategory.ADMIN, "Administratif"),
    (ProjectCategory.ADMIN, "Demande de fonds"),
    (ProjectCategory.ADMIN, "Subvention"),
    (ProjectCategory.ADMIN, "Budget"),
    (ProjectCategory.ADMIN, "Comptabilité"),
    (ProjectCategory.ADMIN, "Contrat"),
    (ProjectCategory.ADMIN, "Droits d'auteur"),
    (ProjectCategory.ADMIN, "Assurance"),
    (ProjectCategory.ADMIN, "Recrutement"),
    (ProjectCategory.STUDIES, "Cours"),
    (ProjectCategory.STUDIES, "TP"),
    (ProjectCategory.STUDIES, "Révision"),
    (ProjectCategory.STUDIES, "Examen"),
    (ProjectCategory.STUDIES, "Rendu"),
    (ProjectCategory.STUDIES, "Projet de semestre"),
    (ProjectCategory.STUDIES, "Travail de bachelor"),
    (ProjectCategory.STUDIES, "Travail de master"),
    (ProjectCategory.STUDIES, "Mémoire"),
    (ProjectCategory.STUDIES, "Stage"),
    (ProjectCategory.CLIENT, "Mandat"),
    (ProjectCategory.CLIENT, "Devis"),
    (ProjectCategory.CLIENT, "Prestation"),
    (ProjectCategory.CLIENT, "Livraison"),
    (ProjectCategory.CLIENT, "Suivi client"),
    (ProjectCategory.PERSONAL, "Projet perso"),
    (ProjectCategory.PERSONAL, "Voyage"),
    (ProjectCategory.PERSONAL, "Maison"),
    (ProjectCategory.PERSONAL, "Santé"),
    (ProjectCategory.OTHER, "Autre"),
]
DEFAULT_PROJECT_TYPE_NAMES = [name for _, name in DEFAULT_PROJECT_TYPES]
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
        from apps.finance.models import Category  # sits above this app

        ProjectType.objects.bulk_create(
            ProjectType(workspace=self, name=name, category=category, position=index)
            for index, (category, name) in enumerate(DEFAULT_PROJECT_TYPES)
        )
        Category.create_defaults(self)


class ProjectType(TimeStampedModel):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="project_types"
    )
    name = models.CharField(max_length=60)
    category = models.CharField(
        max_length=20, choices=ProjectCategory.choices, default=ProjectCategory.OTHER
    )
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
