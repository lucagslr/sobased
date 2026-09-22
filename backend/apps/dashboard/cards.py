"""Cards mode of the Projects page (SPEC §15, page 2).

One card per ROOT project, with its sub-projects sorted into three columns
(Passé / En cours / À venir), the next deadline and the progress of its tasks.

Rights: a card is built from the AccessMap and from `for_user()` querysets
only. When the root is a SHELL for me (I was invited to a sub-project), the
card keeps the root's name and colour, lists the top-most projects I can
really open, and its counts only cover what I can see. Nothing of the other
branches leaks, not even a total.

Progress = done / total, where cancelled tasks do not count, and neither do
the FUTURE occurrences of a recurring task: thirteen weekly meetings created
in advance are not work that is late or waiting.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core.localtime import all_day_moment, local_today, user_zone
from apps.finance.models import BudgetLine, Kind, Transaction
from apps.projects import tree
from apps.projects.access import get_access_map
from apps.projects.models import Project
from apps.tasks.models import Task

EMPTY_STATS = {"tasks_total": 0, "tasks_done": 0, "tasks_overdue": 0}


def _money_stats(request, project_ids: list[int]) -> dict[int, dict]:
    """Planned and spent (expenses) per project, for projects where I may
    see money. Roll-ups happen in build_cards, like the task counts."""
    stats: dict[int, dict] = {}
    planned = (
        BudgetLine.objects.for_user(request, finance="view")
        .filter(project_id__in=project_ids, kind=Kind.EXPENSE)
        .values("project_id")
        .annotate(total=Sum("amount"))
    )
    for row in planned:
        stats.setdefault(row["project_id"], {"planned": 0, "spent": 0})
        stats[row["project_id"]]["planned"] = row["total"]
    spent = (
        Transaction.objects.for_user(request, finance="view")
        .filter(project_id__in=project_ids, kind=Kind.EXPENSE)
        .values("project_id")
        .annotate(total=Sum("amount"))
    )
    for row in spent:
        stats.setdefault(row["project_id"], {"planned": 0, "spent": 0})
        stats[row["project_id"]]["spent"] = row["total"]
    return stats


def _own_stats(request, project_ids: list[int], today: date) -> dict[int, dict]:
    """Task counts per project (its own tasks, not its sub-projects')."""
    tasks = Task.objects.for_user(request).filter(project_id__in=project_ids)
    # "Not a future repetition": a single task, or an occurrence already due.
    counted = Q(series__isnull=True) | Q(
        due_at__lt=all_day_moment(today + timedelta(days=1))
    )
    rows = tasks.values("project_id").annotate(
        total=Count("id", filter=~Q(status=Task.Status.CANCELLED) & counted),
        done=Count("id", filter=Q(status=Task.Status.DONE) & counted),
    )
    stats = {
        row["project_id"]: {
            "tasks_total": row["total"],
            "tasks_done": row["done"],
            "tasks_overdue": 0,
        }
        for row in rows
    }
    late = (
        tasks.overdue(now=timezone.now(), today=today)
        .values("project_id")
        .annotate(n=Count("id"))
    )
    for row in late:
        stats.setdefault(row["project_id"], dict(EMPTY_STATS))["tasks_overdue"] = row[
            "n"
        ]
    return stats


def _next_due(request, project_ids: list[int], today: date) -> dict[int, dict]:
    """Per project: its next open deadline that is not already late."""
    zone = user_zone(request.user)
    tasks = Task.objects.for_user(request).filter(project_id__in=project_ids)
    late = tasks.overdue(now=timezone.now(), today=today).values("pk")
    upcoming = (
        tasks.open()
        .filter(due_at__isnull=False)
        .exclude(pk__in=late)
        .order_by("project_id", "due_at", "id")
        .distinct("project_id")  # PostgreSQL: the first row of each project
    )
    return {
        task.project_id: {
            "task": task.pk,
            "title": task.title,
            "date": (
                task.due_at.date()
                if task.all_day
                else task.due_at.astimezone(zone).date()
            ),
            "project": task.project_id,
        }
        for task in upcoming
    }


def build_cards(request, workspace_id: int | None = None) -> list[dict]:
    access_map = get_access_map(request)
    today = local_today(request.user)

    visible = Project.objects.filter(pk__in=access_map.visible_project_ids()).exclude(
        status=Project.Status.ARCHIVED
    )
    if workspace_id is not None:
        visible = visible.filter(workspace_id=workspace_id)
    # An archived project hides its whole branch: its children stay out of
    # `children` below because their parent is never walked.
    children: dict[int | None, list[Project]] = {}
    for project in visible.select_related("type").order_by("position", "name"):
        children.setdefault(project.parent_id, []).append(project)

    readable = set(access_map.project_ids())
    in_scope = [p.pk for group in children.values() for p in group if p.pk in readable]
    own = _own_stats(request, in_scope, today)
    due = _next_due(request, in_scope, today)
    money_ids = set(access_map.project_ids(finance="view"))
    money = _money_stats(request, [p for p in in_scope if p in money_ids])

    def branch(project: Project) -> list[Project]:
        """`project` and everything below it that I can see."""
        nodes = [project]
        for child in children.get(project.pk, []):
            nodes += branch(child)
        return nodes

    def rollup(project: Project) -> dict:
        totals = dict(EMPTY_STATS)
        for node in branch(project):
            for key, value in own.get(node.pk, EMPTY_STATS).items():
                totals[key] += value
        return totals

    def budget_of(project: Project) -> dict | None:
        """Expense budget over the branch, or None without can_view_finance
        on the project itself (a shell root gets None too)."""
        if project.pk not in money_ids:
            return None
        planned = spent = 0
        for node in branch(project):
            entry = money.get(node.pk)
            if entry:
                planned += entry["planned"]
                spent += entry["spent"]
        return {"planned": planned, "spent": spent}

    def entries(project: Project):
        """Top-most projects under `project` that I can really open."""
        for child in children.get(project.pk, []):
            if access_map.for_project(child.pk).is_shell:
                yield from entries(child)
            else:
                yield child

    def entry(project: Project) -> dict:
        return {
            "id": project.pk,
            "name": project.name,
            "color": project.color,
            "type_name": project.type.name,
            "status": project.status,
            "start_date": project.start_date,
            "end_date": project.end_date,
            "end_overdue": tree.end_overdue(project.status, project.end_date, today),
            "children_count": len(children.get(project.pk, [])),
            "budget": budget_of(project),
            **rollup(project),
        }

    cards = []
    for root in children.get(None, []):
        is_shell = access_map.for_project(root.pk).is_shell
        columns: dict[str, list[dict]] = {
            tree.PAST: [],
            tree.CURRENT: [],
            tree.UPCOMING: [],
        }
        for sub in entries(root):
            columns[tree.temporal(sub.status, sub.start_date, today)].append(entry(sub))
        # Past: most recent first. Current: closest end first. Upcoming:
        # closest start first. Undated projects go last, ties by name
        # (sorts are stable, so the name order survives the second pass).
        for column in columns.values():
            column.sort(key=lambda e: e["name"].lower())
        columns[tree.PAST].sort(key=lambda e: e["end_date"] or date.min, reverse=True)
        columns[tree.CURRENT].sort(key=lambda e: e["end_date"] or date.max)
        columns[tree.UPCOMING].sort(key=lambda e: e["start_date"] or date.max)
        deadlines = [due[node.pk] for node in branch(root) if node.pk in due]
        cards.append(
            {
                "id": root.pk,
                "workspace": root.workspace_id,
                "name": root.name,
                "color": root.color,
                "is_shell": is_shell,
                "type_name": None if is_shell else root.type.name,
                "status": None if is_shell else root.status,
                "start_date": None if is_shell else root.start_date,
                "end_date": None if is_shell else root.end_date,
                "temporal": (
                    None
                    if is_shell
                    else tree.temporal(root.status, root.start_date, today)
                ),
                "end_overdue": not is_shell
                and tree.end_overdue(root.status, root.end_date, today),
                "next_due": min(deadlines, key=lambda d: d["date"], default=None),
                "budget": budget_of(root),
                "past": columns[tree.PAST],
                "current": columns[tree.CURRENT],
                "upcoming": columns[tree.UPCOMING],
                **rollup(root),
            }
        )
    return cards
