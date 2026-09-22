"""Events and meetings (SPEC §8).

Same date convention as tasks: `start` / `end` are aware datetimes; when
`all_day` is true they sit at midnight UTC, only the date counts, and `end` is
INCLUSIVE (a two-day shooting on the 12th and 13th ends on the 13th).

Recurrence works like tasks (apps/tasks/models.py): occurrences are real rows,
created ahead of time on a sliding 90-day window.

The colour of an event is not stored: it is the colour of its project.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.contacts.models import Contact
from apps.core.models import TimeStampedModel
from apps.projects.models import Project
from apps.projects.querysets import ProjectScopedQuerySet
from apps.workspaces.models import Tag


class EventSeries(TimeStampedModel):
    """A recurring event: the rule, and the template its occurrences copy."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="event_series"
    )
    rrule = models.TextField()
    # First occurrence: anchors the rule (weekday, time of day).
    dtstart = models.DateTimeField()
    # Timezone the rule is expanded in, so 10:00 stays 10:00 across DST.
    timezone = models.CharField(max_length=64, default="Europe/Zurich")
    all_day = models.BooleanField(default=False)
    generated_until = models.DateTimeField()
    # What every new occurrence starts from: see services.event_template().
    template = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.template.get('title', 'Série')} ({self.rrule})"


class Event(TimeStampedModel):
    class Type(models.TextChoices):
        MEETING = "meeting", "RDV"
        LIVE = "live", "Date live"
        SHOOTING = "shooting", "Tournage"
        RELEASE = "release", "Release"
        RELEASE_PARTY = "release_party", "Release party"
        CLASS = "class", "Cours"
        EXAM = "exam", "Examen"
        OTHER = "other", "Autre"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="events"
    )
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.MEETING)
    title = models.CharField(max_length=240)
    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    location = models.CharField(max_length=240, blank=True)
    # Three separate texts (SPECIFICATIONS §4): before, after, what was decided.
    prep_notes = models.TextField(blank=True)  # simple markdown
    report = models.TextField(blank=True)  # simple markdown
    decisions = models.JSONField(default=list, blank=True)  # ordered list of strings
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="events"
    )
    contacts = models.ManyToManyField(Contact, blank=True, related_name="events")
    tags = models.ManyToManyField(Tag, blank=True, related_name="events")
    series = models.ForeignKey(
        EventSeries,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="occurrences",
    )
    # Theoretical start of this occurrence in its series (idempotent generation).
    occurrence_at = models.DateTimeField(null=True, blank=True)
    # Edited on its own ("cette occurrence"): later series edits skip it.
    is_exception = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = ProjectScopedQuerySet.as_manager()

    class Meta:
        ordering = ["start", "id"]
        indexes = [
            models.Index(fields=["project", "start"]),
            models.Index(fields=["start"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end__gte=F("start")), name="event_end_not_before_start"
            ),
            models.UniqueConstraint(
                fields=["series", "occurrence_at"],
                condition=Q(series__isnull=False),
                name="event_unique_occurrence_per_series",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def has_minutes(self) -> bool:
        """Something was written after the meeting: never delete it silently."""
        return bool(self.report.strip() or self.decisions)


# Importable path for drf-spectacular's ENUM_NAME_OVERRIDES.
EVENT_TYPE_CHOICES = Event.Type.choices
