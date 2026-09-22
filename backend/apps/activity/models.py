"""The activity journal (DATABASE_SCHEMA §7).

One row per action on a project object. The target is referenced by type,
id and a snapshot of its label rather than by a generic foreign key: the
journal must survive the deletion of the object (and of the project: the
row then only belongs to the workspace). Entries are purged after 12
months (tasks.purge_old_entries).
"""

from django.conf import settings
from django.db import models

from apps.projects.querysets import ProjectScopedQuerySet


class Verb(models.TextChoices):
    CREATED = "created", "Création"
    UPDATED = "updated", "Modification"
    STATUS_CHANGED = "status_changed", "Statut"
    DELETED = "deleted", "Suppression"
    SHARED = "shared", "Partage"
    ACCESS_CHANGED = "access_changed", "Droits"


VERB_CHOICES = Verb.choices

# Entries about these targets carry amounts: only readers with the finance
# flag on the project get them (views.py).
FINANCE_TARGETS = ("transaction", "recurring_expense", "budget_line")


class ActivityEntry(models.Model):
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.CASCADE, related_name="activity"
    )
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    verb = models.CharField(max_length=20, choices=Verb.choices)
    target_type = models.CharField(max_length=30)  # "task", "asset", "membership"...
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    target_label = models.CharField(max_length=240)  # snapshot of the name
    changes = models.JSONField(default=dict, blank=True)  # {field: [old, new]}
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProjectScopedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["project", "created_at"]),
            models.Index(fields=["workspace", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.verb} {self.target_type} {self.target_label}"
