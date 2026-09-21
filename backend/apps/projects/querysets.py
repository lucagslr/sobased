"""The queryset filter every project-bound model uses (SPEC §6).

Lives in its own module because models.py needs it, while access.py (which it
calls) needs models.py: the access import is therefore done lazily.
"""

from django.db import models


class ProjectScopedQuerySet(models.QuerySet):
    """QuerySet for any model that belongs to a project.

    Set `project_lookup` when the model is not directly attached to a project,
    e.g. "task__project" for a checklist item. For Project itself it is "pk".
    """

    project_lookup = "project"

    def for_user(self, actor, minimum=None, *, finance: str = ""):
        """Rows in projects where `actor` (a user or a request) has `minimum`.

        finance="view" / "edit" additionally requires the finance flag.
        This is the ONLY sanctioned way to filter rows by access rights.
        """
        from .access import Role, get_access_map

        ids = get_access_map(actor).project_ids(minimum or Role.VIEWER, finance=finance)
        return self.filter(**{f"{self.project_lookup}__in": ids})


class ProjectQuerySet(ProjectScopedQuerySet):
    project_lookup = "pk"

    def visible_to(self, actor):
        """Projects the user can see at all, shells included (navigation only)."""
        from .access import get_access_map

        return self.filter(pk__in=get_access_map(actor).visible_project_ids())
