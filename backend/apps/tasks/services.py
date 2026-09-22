"""Business rules of tasks that do not depend on who is asking.

- dependencies: same root project, no cycles;
- recurring series: creation, materialisation, "this occurrence" versus
  "this and all following" (SPECIFICATIONS §3);
- mentions and assignment e-mails (in-app notifications arrive in phase 12).
"""

from __future__ import annotations

import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.core import recurrence
from apps.projects import tree
from apps.projects.access import member_user_ids

from .models import ChecklistItem, Task, TaskSeries

User = get_user_model()


# --- Dependencies ----------------------------------------------------------------


def root_project_id(project) -> int:
    chain = tree.ancestors(project)
    return chain[0].pk if chain else project.pk


def would_create_cycle(task: Task, blocker: Task) -> bool:
    """True if making `task` blocked by `blocker` closes a loop.

    That happens when `blocker` is already (directly or not) waiting for
    `task`: walk up the blockers of `blocker` and look for `task`.
    """
    if task.pk == blocker.pk:
        return True
    seen, stack = set(), [blocker.pk]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        upstream = Task.blocked_by.through.objects.filter(
            from_task_id=current
        ).values_list("to_task_id", flat=True)
        for blocker_id in upstream:
            if blocker_id == task.pk:
                return True
            stack.append(blocker_id)
    return False


def validate_blockers(task: Task, blockers: list[Task]) -> None:
    """Raise ValueError (user-facing) if a blocker is not acceptable."""
    if not blockers:
        return
    root = root_project_id(task.project)
    for blocker in blockers:
        if root_project_id(blocker.project) != root:
            raise ValueError("Le bloqueur doit être une tâche du même projet racine.")
        if task.pk and would_create_cycle(task, blocker):
            raise ValueError("Cette dépendance créerait une boucle.")


# --- Recurring series ---------------------------------------------------------------


def _anchor(task: Task):
    """The date the recurrence rule moves: the due date, else the start."""
    return task.due_at or task.start_at


def task_template(task: Task) -> dict:
    """What the next occurrences of a series copy from `task`."""
    lead = None
    if task.due_at and task.start_at:
        lead = int((task.due_at - task.start_at).total_seconds())
    return {
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "anchor": "due" if task.due_at else "start",
        # Seconds between start and due, kept for every occurrence.
        "lead_seconds": lead,
        "assignees": (
            list(task.assignees.values_list("pk", flat=True)) if task.pk else []
        ),
        "tags": list(task.tags.values_list("pk", flat=True)) if task.pk else [],
        "checklist": (
            [
                {"title": item.title, "pinned": item.pinned}
                for item in task.checklist.all()
            ]
            if task.pk
            else []
        ),
    }


@transaction.atomic
def start_series(task: Task, rule: str, tz_name: str) -> TaskSeries:
    """Make `task` the first occurrence of a new series and create the next ones."""
    anchor = _anchor(task)
    if anchor is None:
        raise ValueError(
            "Une tâche récurrente a besoin d'une date (début ou échéance)."
        )
    rule = recurrence.normalise_rrule(rule)
    series = TaskSeries.objects.create(
        project=task.project,
        rrule=rule,
        dtstart=anchor,
        timezone=tz_name,
        all_day=task.all_day,
        generated_until=anchor,
        template=task_template(task),
    )
    task.series = series
    task.occurrence_at = anchor
    task.is_exception = False
    task.save(update_fields=["series", "occurrence_at", "is_exception", "updated_at"])
    materialise(series)
    return series


def materialise(series: TaskSeries, today=None) -> int:
    """Create the missing occurrences up to the end of the 90-day window.

    Idempotent: safe to run every night, or twice in a row.
    """
    horizon = recurrence.window_end(today or timezone.localdate())
    if horizon <= series.generated_until:
        return 0
    moments = recurrence.occurrences_between(
        series.rrule,
        series.dtstart,
        series.timezone,
        all_day=series.all_day,
        after=series.generated_until,
        until=horizon,
    )
    template = series.template
    lead = template.get("lead_seconds")
    created = 0
    for moment in moments:
        if Task.objects.filter(series=series, occurrence_at=moment).exists():
            continue
        due, start = (
            (moment, None) if template.get("anchor") == "due" else (None, moment)
        )
        if due and lead is not None:
            start = due - timedelta(seconds=lead)
        task = Task.objects.create(
            project=series.project,
            title=template.get("title", ""),
            description=template.get("description", ""),
            priority=template.get("priority", 3),
            start_at=start,
            due_at=due,
            all_day=series.all_day,
            series=series,
            occurrence_at=moment,
            position=Task.objects.filter(project=series.project, status="todo").count(),
        )
        task.assignees.set(
            User.objects.filter(pk__in=template.get("assignees", []), is_active=True)
        )
        task.tags.set(template.get("tags", []))
        ChecklistItem.objects.bulk_create(
            ChecklistItem(
                task=task,
                title=item["title"],
                pinned=item.get("pinned", False),
                position=i,
            )
            for i, item in enumerate(template.get("checklist", []))
        )
        created += 1
    series.generated_until = horizon
    series.save(update_fields=["generated_until", "updated_at"])
    return created


def _close_series_before(task: Task) -> None:
    """End the task's series just before this occurrence.

    Following occurrences that are still open are deleted; finished ones are
    never touched. An emptied series is removed.
    """
    series = task.series
    Task.objects.filter(series=series, occurrence_at__gt=task.occurrence_at).exclude(
        status__in=Task.CLOSED_STATUSES
    ).delete()
    if task.occurrence_at <= series.dtstart:
        task.series = None
        task.save(update_fields=["series", "updated_at"])
        if not series.occurrences.exists():
            series.delete()
        return
    last_day = task.occurrence_at.date() - timedelta(days=1)
    series.rrule = recurrence.with_until(series.rrule, last_day)
    series.save(update_fields=["rrule", "updated_at"])


@transaction.atomic
def apply_to_following(task: Task, rule: str | None, tz_name: str) -> None:
    """ "Toutes les suivantes": split the series at this (already edited) task.

    `rule`: None keeps the current rule, "" stops the recurrence here.
    """
    old_series = task.series
    current_rule = old_series.rrule if old_series else ""
    if old_series is not None:
        _close_series_before(task)
        task.series = None
        task.occurrence_at = None
    task.is_exception = False
    task.save()
    new_rule = current_rule if rule is None else rule
    if new_rule:
        # The old rule may carry the UNTIL we just added: start clean.
        start_series(
            task, _without_end(new_rule) if rule is None else new_rule, tz_name
        )


def _without_end(rule: str) -> str:
    return ";".join(
        part
        for part in rule.split(";")
        if not part.upper().startswith(("UNTIL=", "COUNT="))
    )


@transaction.atomic
def delete_with_following(task: Task) -> None:
    if task.series_id:
        _close_series_before(task)
    task.delete()


# --- Mentions and e-mails -----------------------------------------------------------

MENTION = re.compile(r"(?<![\w@.])@([A-Za-z0-9_.-]{3,30})")


def mentioned_users(body: str, project) -> list:
    """Users mentioned as @username who really are members of the project.

    Anything else stays plain text: mentioning cannot be used to probe who
    exists, nor to notify someone outside the project.
    """
    usernames = {name.rstrip(".").lower() for name in MENTION.findall(body or "")}
    if not usernames:
        return []
    members = User.objects.filter(pk__in=member_user_ids(project), is_active=True)
    return [user for user in members if user.username.lower() in usernames]


def notify_assignment(task: Task, users, actor) -> None:
    """In-app for every new assignee, e-mail if they asked (phase 12)."""
    from apps.notifications import services as notifications

    notifications.task_assigned(task, users, actor)


def notify_mentions(comment, actor) -> None:
    from apps.notifications import services as notifications

    notifications.mentioned(
        comment, mentioned_users(comment.body, comment.task.project), actor
    )
