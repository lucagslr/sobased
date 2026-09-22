"""In-app notifications (SPEC §14).

One row per recipient and event. `payload` keeps the labels needed to show
the line even after the object changed or vanished (title, project name,
actor name); `url` is the front route to open. `emailed_at` says whether a
mail went out for it (the preference decides, see services.notify()).
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.projects.models import Project


class Kind(models.TextChoices):
    ASSIGNMENT = "assignment", "Tâche assignée"
    MENTION = "mention", "Mention"
    ASSET_STATUS = "asset_status", "Statut d'un fichier"
    INVITATION = "invitation", "Ajout à un projet"
    SHARE_OPENED = "share_opened", "Lien partagé ouvert"


class Notification(TimeStampedModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    payload = models.JSONField(default=dict, blank=True)
    url = models.CharField(max_length=300, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["recipient", "read_at"])]

    def __str__(self):
        return f"{self.kind} → {self.recipient}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


NOTIFICATION_KIND_CHOICES = Kind.choices
