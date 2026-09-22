"""Tasks, checklists, comments and recurring series (SPEC §7).

Computed, never stored: "overdue" (see TaskQuerySet.overdue) and "blocked"
(a blocker that is neither done nor cancelled).

Dates: `start_at` / `due_at` are aware datetimes. When `all_day` is true they
sit at midnight UTC and only the date is meaningful, whatever the timezone.
"""

from datetime import UTC, datetime, time

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.projects.models import Project
from apps.projects.querysets import ProjectScopedQuerySet
from apps.workspaces.models import Tag


class TaskSeries(TimeStampedModel):
    """A recurring task: the rule, and the template its occurrences copy.

    Occurrences are real Task rows, created ahead of time up to
    `generated_until` (sliding 90-day window, extended nightly by Celery beat).
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="task_series"
    )
    rrule = models.TextField()
    # First occurrence: anchors the rule (weekday, time of day).
    dtstart = models.DateTimeField()
    # Timezone the rule is expanded in, so 10:00 stays 10:00 across DST.
    timezone = models.CharField(max_length=64, default="Europe/Zurich")
    all_day = models.BooleanField(default=False)
    generated_until = models.DateTimeField()
    # What every new occurrence starts from: see services.task_template().
    template = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.template.get('title', 'Série')} ({self.rrule})"


class TaskQuerySet(ProjectScopedQuerySet):
    OPEN = ("todo", "in_progress", "to_validate")

    def open(self):
        return self.filter(status__in=self.OPEN)

    def overdue(self, now=None, today=None):
        """Due date passed and still open (SPEC §7). Never auto-postponed.

        A timed task is late once its time has passed. An all-day task is late
        once its DAY is over: `due_at` (midnight UTC of that day) must be
        before midnight UTC of `today`, the user's local date.
        """
        now = now or timezone.now()
        today = today or timezone.localdate()
        today_midnight = datetime.combine(today, time.min, tzinfo=UTC)
        return self.open().filter(
            Q(all_day=False, due_at__lt=now)
            | Q(all_day=True, due_at__lt=today_midnight)
        )


class Task(TimeStampedModel):
    class Status(models.TextChoices):
        TODO = "todo", "À faire"
        IN_PROGRESS = "in_progress", "En cours"
        TO_VALIDATE = "to_validate", "À valider"
        DONE = "done", "Terminé"
        CANCELLED = "cancelled", "Annulé"

    CLOSED_STATUSES = (Status.DONE, Status.CANCELLED)

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)  # simple markdown
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.TODO
    )
    # 1 to 5, 5 = highest. Each level has its pastel colour in the front.
    priority = models.PositiveSmallIntegerField(default=3)
    start_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=True)
    # Order inside a kanban column (status).
    position = models.PositiveIntegerField(default=0)
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_tasks"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="tasks")
    # "This task is blocked by those". One field, nothing more (SPEC §7).
    blocked_by = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="blocking"
    )
    series = models.ForeignKey(
        TaskSeries,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="occurrences",
    )
    # Theoretical date of this occurrence in its series (makes generation
    # idempotent, even after the occurrence itself has been rescheduled).
    occurrence_at = models.DateTimeField(null=True, blank=True)
    # Edited on its own ("cette occurrence"): later series edits skip it.
    is_exception = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    # "Créer une tâche depuis ce RDV" (SPEC §8): the task keeps the link, the
    # meeting lists the tasks it produced. A string reference: apps.events
    # imports this app, not the other way round.
    source_event = models.ForeignKey(
        "events.Event",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["due_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(priority__gte=1) & Q(priority__lte=5),
                name="task_priority_between_1_and_5",
            ),
            models.UniqueConstraint(
                fields=["series", "occurrence_at"],
                condition=Q(series__isnull=False),
                name="task_unique_occurrence_per_series",
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Keep completed_at in step with the status, whoever changes it.
        if self.status == self.Status.DONE and self.completed_at is None:
            self.completed_at = timezone.now()
        elif self.status != self.Status.DONE:
            self.completed_at = None
        super().save(*args, **kwargs)

    @property
    def is_closed(self) -> bool:
        return self.status in self.CLOSED_STATUSES


# Importable path for drf-spectacular's ENUM_NAME_OVERRIDES.
TASK_STATUS_CHOICES = Task.Status.choices


class ChecklistItem(TimeStampedModel):
    class Scoped(ProjectScopedQuerySet):
        project_lookup = "task__project"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="checklist")
    title = models.CharField(max_length=240)
    done = models.BooleanField(default=False)
    # Pinned items feed the "Todo épinglées" dashboard widget (SPEC §7).
    pinned = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    done_at = models.DateTimeField(null=True, blank=True)

    objects = Scoped.as_manager()

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.title


class TaskComment(TimeStampedModel):
    class Scoped(ProjectScopedQuerySet):
        project_lookup = "task__project"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    # Kept when the account is deleted: shown as "Utilisateur supprimé".
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    body = models.TextField()  # simple markdown, "@username" mentions
    edited_at = models.DateTimeField(null=True, blank=True)

    objects = Scoped.as_manager()

    class Meta:
        ordering = ["created_at", "id"]
