"""Contacts (SPEC §14): the address book of a workspace.

A contact is a person OUTSIDE the app (a booker, a graphic designer, a
teacher...). It belongs to one workspace and may be linked to projects, with
the role it plays there ("réalisateur du clip"). No interaction history.

Who sees a contact (SPECIFICATIONS §1.3, API_DOCUMENTATION §5):
- a real member of the workspace sees the whole address book;
- a guest of one project only sees the contacts LINKED to the projects they
  can open. The rest of the address book does not exist for them.
`ContactQuerySet.for_user()` is the single implementation of that rule.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.projects.access import get_access_map
from apps.projects.models import Project
from apps.projects.querysets import ProjectScopedQuerySet
from apps.workspaces.models import Tag, Workspace


class ContactQuerySet(models.QuerySet):
    def for_user(self, actor):
        """Contacts `actor` (a user or a request) is allowed to see."""
        access_map = get_access_map(actor)
        member_of = [
            workspace_id
            for workspace_id, access in access_map.workspaces.items()
            if access.role is not None  # a shell workspace grants nothing
        ]
        return self.filter(
            Q(workspace_id__in=member_of)
            | Q(project_links__project_id__in=access_map.project_ids())
        ).distinct()


class Contact(TimeStampedModel):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="contacts"
    )
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    organization = models.CharField(max_length=120, blank=True)
    # Free text on purpose: programmateur, graphiste, réalisateur, prof...
    job = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    instagram = models.CharField(max_length=60, blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="contacts")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = ContactQuerySet.as_manager()

    class Meta:
        ordering = ["last_name", "first_name", "organization", "id"]
        indexes = [models.Index(fields=["workspace", "last_name", "first_name"])]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self) -> str:
        """ "Prénom Nom", or the organization for a contact without a name."""
        return f"{self.first_name} {self.last_name}".strip() or self.organization


class ProjectContact(TimeStampedModel):
    """A contact attached to a project, with its role there."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="contact_links"
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="project_links"
    )
    role_label = models.CharField(max_length=80, blank=True)

    objects = ProjectScopedQuerySet.as_manager()

    class Meta:
        ordering = ["contact__last_name", "contact__first_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "contact"], name="projectcontact_unique_pair"
            )
        ]

    def __str__(self):
        return f"{self.contact} @ {self.project}"
