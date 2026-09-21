"""Tree helpers and computed project state.

No tree library and no materialised path (SPEC §5): a chain has at most 4
nodes and a whole workspace tree is small enough to load in one query.
Temporality and "end overdue" are always computed, never stored.
"""

from datetime import date

from .models import MAX_DEPTH, Project

PAST, CURRENT, UPCOMING = "past", "current", "upcoming"


def temporal(status: str, start_date: date | None, today: date) -> str:
    """Passé / En cours / À venir (SPECIFICATIONS §2).

    A project whose end date has passed WITHOUT being closed stays "current":
    until someone answers the overdue modal, nobody knows whether it is over.
    """
    if status in Project.CLOSED_STATUSES:
        return PAST
    if start_date and start_date > today:
        return UPCOMING
    if not start_date and status in (Project.Status.IDEA, Project.Status.PLANNED):
        return UPCOMING
    return CURRENT


def end_overdue(status: str, end_date: date | None, today: date) -> bool:
    """True when the end date has passed and the project is still open."""
    return bool(end_date and end_date < today and status not in Project.CLOSED_STATUSES)


def ancestors(project: Project) -> list[Project]:
    """[root, ..., parent]: at most 3 projects, fetched with at most 3 queries."""
    chain = []
    current = project.parent
    while current is not None:
        chain.append(current)
        current = current.parent
    return list(reversed(chain))


def subtree(project: Project) -> list[Project]:
    """`project` and all its descendants, parents first."""
    nodes = list(Project.objects.filter(workspace_id=project.workspace_id))
    children: dict[int | None, list[Project]] = {}
    for node in nodes:
        children.setdefault(node.parent_id, []).append(node)
    ordered, queue = [], [project]
    while queue:
        current = queue.pop(0)
        ordered.append(current)
        queue.extend(children.get(current.pk, []))
    return ordered


def move(project: Project, new_parent: Project | None) -> None:
    """Re-parent `project` inside its workspace and fix the depth of its subtree.

    Raises ValueError with a user-facing message when the move is impossible.
    Permissions are the caller's job.
    """
    nodes = subtree(project)
    if new_parent is not None:
        if new_parent.workspace_id != project.workspace_id:
            raise ValueError("Le projet doit rester dans le même espace.")
        if new_parent.pk in {node.pk for node in nodes}:
            raise ValueError("Un projet ne peut pas être déplacé dans lui-même.")
    new_depth = new_parent.depth + 1 if new_parent else 1
    height = max(node.depth for node in nodes) - project.depth  # levels below
    if new_depth + height > MAX_DEPTH:
        raise ValueError(f"Ce déplacement dépasserait {MAX_DEPTH} niveaux.")

    shift = new_depth - project.depth
    project.parent = new_parent
    project.save()  # recomputes its own depth
    if shift:
        for node in nodes[1:]:
            Project.objects.filter(pk=node.pk).update(depth=node.depth + shift)
