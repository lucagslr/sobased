"""Read-only aggregations behind the dashboards (global and per project).

Rights: every queryset starts from `for_user(request)`, the central filter of
apps.projects. The filters of a saved view are applied ON TOP of it, so they
can only narrow what the user is already allowed to see.

Dates: "today", "overdue" and "the next 7 days" are evaluated on the user's
own clock (apps.core.localtime), with the two storage conventions of tasks:
all-day dates sit at midnight UTC, timed dates are real instants.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core.localtime import (
    all_day_moment,
    local_day_bounds,
    local_today,
    user_zone,
)
from apps.events.models import Event
from apps.files.models import Asset
from apps.files.models import Status as AssetStatus
from apps.finance.models import Transaction
from apps.projects.access import get_access_map
from apps.projects.models import Project
from apps.tasks.models import ChecklistItem, Task

# A widget is a glance, not a report: it lists the first items and the total.
WIDGET_LIMIT = 50
MILESTONE_LIMIT = 8
# "RDV à venir" looks two weeks ahead: far enough to prepare a meeting.
MEETINGS_DAYS = 14


def _money(request, scope: Scope):
    """Transactions of the scope I may see money of (can_view_finance)."""
    queryset = Transaction.objects.for_user(request, finance="view").filter(
        project_id__in=scope.project_ids
    )
    return queryset.select_related(
        "project", "category", "contact", "event", "paid_by_user", "paid_by_contact"
    )


def expenses_to_pay(request, scope: Scope):
    """« Frais à payer ce mois »: unpaid expenses due by the end of this
    month, overdue ones included. Oldest first."""
    first_next_month = (scope.today.replace(day=1) + timedelta(days=32)).replace(day=1)
    return (
        _money(request, scope)
        .filter(
            payment_status=Transaction.PaymentStatus.TO_PAY, date__lt=first_next_month
        )
        .order_by("date", "id")
    )


def missing_receipts(request, scope: Scope):
    """« Justificatifs manquants »: expenses without a receipt, oldest first."""
    return _money(request, scope).needing_receipt().order_by("date", "id")


def project_budget(request, project) -> dict:
    """Budget block of the project overview: planned versus actual (own and
    with the sub-projects I may see), plus what still needs attention."""
    from apps.finance import services as finance
    from apps.finance.models import BudgetLine

    readable = set(get_access_map(request).project_ids(finance="view"))
    transactions = Transaction.objects.for_user(request, finance="view")
    result = finance.budget(
        project,
        transactions,
        BudgetLine.objects.for_user(request, finance="view"),
        readable,
    )
    branch = [project.pk, *get_access_map(request).descendants(project.pk)]
    in_branch = transactions.filter(project_id__in=branch)
    return {
        **result["totals"],
        "needs_receipt": in_branch.needing_receipt().count(),
        "to_pay": in_branch.filter(
            payment_status=Transaction.PaymentStatus.TO_PAY
        ).aggregate(total=Sum("amount"))["total"]
        or 0,
    }


@dataclass
class Scope:
    """What a dashboard looks at, once rights and saved filters are combined."""

    project_ids: list[int]
    tag_ids: list[int]
    only_mine: bool
    today: date


def resolve_scope(request, filters: dict) -> Scope:
    """Accessible projects narrowed by the view's filters.

    `filters["projects"]` means "these projects AND their sub-projects".
    """
    access_map = get_access_map(request)
    project_ids = set(access_map.project_ids())
    if filters.get("workspaces"):
        wanted = set(filters["workspaces"])
        project_ids = {
            pid
            for pid in project_ids
            if access_map.project_workspace.get(pid) in wanted
        }
    if filters.get("projects"):
        branch: set[int] = set()
        for project_id in filters["projects"]:
            branch.add(project_id)
            branch.update(access_map.descendants(project_id))
        project_ids &= branch
    return Scope(
        project_ids=sorted(project_ids),
        tag_ids=list(filters.get("tags") or []),
        only_mine=bool(filters.get("only_mine")),
        today=local_today(request.user),
    )


def _tasks(request, scope: Scope, *, mine: bool | None = None):
    """Open tasks of the scope. `mine` overrides the view's "only mine"."""
    queryset = (
        Task.objects.for_user(request)
        .filter(project_id__in=scope.project_ids)
        .exclude(status__in=Task.CLOSED_STATUSES)
    )
    if scope.tag_ids:
        queryset = queryset.filter(tags__in=scope.tag_ids)
    if scope.only_mine if mine is None else mine:
        queryset = queryset.filter(assignees=request.user)
    return (
        queryset.distinct()
        .select_related("project", "series", "source_event")
        .prefetch_related("assignees", "tags", "checklist", "blocked_by__project")
        .annotate(comments_total=Count("comments", distinct=True))
    )


def _on_day(user, day: date, field: str) -> Q:
    """`field` (start_at / due_at) falls on local `day`, all-day or timed."""
    start, end = local_day_bounds(user, day)
    return Q(all_day=True, **{field: all_day_moment(day)}) | Q(
        all_day=False, **{f"{field}__gte": start, f"{field}__lt": end}
    )


def overdue_tasks(request, scope: Scope):
    """Late and still open: oldest first, then highest priority (SPEC §7)."""
    late = Task.objects.overdue(now=timezone.now(), today=scope.today).values("pk")
    return _tasks(request, scope).filter(pk__in=late).order_by("due_at", "-priority")


def today_tasks(request, scope: Scope):
    """Due today or starting today, and not already late."""
    late = Task.objects.overdue(now=timezone.now(), today=scope.today).values("pk")
    user = request.user
    return (
        _tasks(request, scope)
        .filter(
            _on_day(user, scope.today, "due_at")
            | _on_day(user, scope.today, "start_at")
        )
        .exclude(pk__in=late)
        .order_by("-priority", "due_at")
    )


def next_days_tasks(request, scope: Scope, days: int = 7):
    """Due from tomorrow to today + `days`, included."""
    last_day = scope.today + timedelta(days=days)
    _, tomorrow_start = local_day_bounds(request.user, scope.today)
    _, window_end = local_day_bounds(request.user, last_day)
    return (
        _tasks(request, scope)
        .filter(
            Q(
                all_day=True,
                due_at__gt=all_day_moment(scope.today),
                due_at__lte=all_day_moment(last_day),
            )
            | Q(all_day=False, due_at__gte=tomorrow_start, due_at__lt=window_end)
        )
        .order_by("due_at", "-priority")
    )


def pinned_items(request, scope: Scope):
    """Pinned, unticked checklist items of open tasks ("Todo épinglées")."""
    queryset = (
        ChecklistItem.objects.for_user(request)
        .filter(task__project_id__in=scope.project_ids, pinned=True, done=False)
        .exclude(task__status__in=Task.CLOSED_STATUSES)
    )
    if scope.tag_ids:
        queryset = queryset.filter(task__tags__in=scope.tag_ids)
    if scope.only_mine:
        queryset = queryset.filter(task__assignees=request.user)
    return (
        queryset.distinct()
        .select_related("task__project")
        .order_by("task__due_at", "position", "id")
    )


def upcoming_events(request, scope: Scope, days: int = MEETINGS_DAYS):
    """Events that are not over yet and start within `days` ("RDV à venir").

    "Only mine" keeps the events I take part in.
    """
    last_day = scope.today + timedelta(days=days)
    _, window_end = local_day_bounds(request.user, last_day)
    queryset = (
        Event.objects.for_user(request)
        .filter(project_id__in=scope.project_ids)
        .filter(
            Q(
                all_day=True,
                end__gte=all_day_moment(scope.today),
                start__lte=all_day_moment(last_day),
            )
            | Q(all_day=False, end__gte=timezone.now(), start__lt=window_end)
        )
    )
    if scope.tag_ids:
        queryset = queryset.filter(tags__in=scope.tag_ids)
    if scope.only_mine:
        queryset = queryset.filter(participants=request.user)
    return (
        queryset.distinct()
        .select_related("project", "series")
        .prefetch_related("participants", "contacts", "tags", "tasks")
        .order_by("start", "id")
    )


def to_validate_items(request, scope: Scope) -> list[dict]:
    """Everything waiting for a validation: tasks, projects and files
    "À valider".

    "Only mine" is ignored on purpose: the person who validates is usually
    not the person the task is assigned to.
    """
    items = [
        {
            "kind": "task",
            "id": task.pk,
            "title": task.title,
            "project": task.project_id,
            "project_name": task.project.name,
            "project_color": task.project.color,
        }
        for task in _tasks(request, scope, mine=False)
        .filter(status=Task.Status.TO_VALIDATE)
        .order_by("due_at", "id")[:WIDGET_LIMIT]
    ]
    projects = Project.objects.for_user(request).filter(
        pk__in=scope.project_ids, status=Project.Status.TO_VALIDATE
    )
    if scope.tag_ids:
        projects = projects.filter(tags__in=scope.tag_ids).distinct()
    items += [
        {
            "kind": "project",
            "id": project.pk,
            "title": project.name,
            "project": project.pk,
            "project_name": project.name,
            "project_color": project.color,
        }
        for project in projects.order_by("end_date", "name")[:WIDGET_LIMIT]
    ]
    assets = (
        Asset.objects.for_user(request)
        .filter(project_id__in=scope.project_ids, status=AssetStatus.TO_VALIDATE)
        .select_related("project")
    )
    if scope.tag_ids:
        assets = assets.filter(tags__in=scope.tag_ids).distinct()
    items += [
        {
            "kind": "asset",
            "id": asset.pk,
            "title": asset.name,
            "project": asset.project_id,
            "project_name": asset.project.name,
            "project_color": asset.project.color,
        }
        for asset in assets.order_by("-updated_at", "id")[:WIDGET_LIMIT]
    ]
    return items


def milestones(request, scope: Scope, root_project_id: int) -> list[dict]:
    """The next dated things of a project: task deadlines, events, and the
    start and end dates of its sub-projects. Shown in the project overview."""
    zone = user_zone(request.user)
    upcoming = (
        _tasks(request, scope, mine=False)
        .filter(due_at__gt=all_day_moment(scope.today))
        .order_by("due_at")[:MILESTONE_LIMIT]
    )
    found = [
        {
            "kind": "task",
            "id": task.pk,
            "date": (
                task.due_at.date()
                if task.all_day
                else task.due_at.astimezone(zone).date()
            ),
            "title": task.title,
            "project": task.project_id,
            "color": task.project.color,
        }
        for task in upcoming
    ]
    found += [
        {
            "kind": "event",
            "id": event.pk,
            "date": (
                event.start.date()
                if event.all_day
                else event.start.astimezone(zone).date()
            ),
            "title": event.title,
            "project": event.project_id,
            "color": event.project.color,
        }
        for event in upcoming_events(request, scope, days=365)[:MILESTONE_LIMIT]
    ]
    children = (
        Project.objects.for_user(request)
        .filter(pk__in=scope.project_ids)
        .exclude(pk=root_project_id)
        .exclude(status__in=Project.CLOSED_STATUSES)
    )
    for project in children:
        for kind, moment in (
            ("project_start", project.start_date),
            ("project_end", project.end_date),
        ):
            if moment and moment >= scope.today:
                found.append(
                    {
                        "kind": kind,
                        "id": project.pk,
                        "date": moment,
                        "title": project.name,
                        "project": project.pk,
                        "color": project.color,
                    }
                )
    found.sort(key=lambda item: (item["date"], item["title"]))
    return found[:MILESTONE_LIMIT]
