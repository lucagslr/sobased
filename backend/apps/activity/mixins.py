"""The view-layer hook that writes the journal (SPECIFICATIONS §11: "written
explicitly by the view layer, with a list of key fields per model; no global
signals").

    class TaskViewSet(ActivityMixin, ProjectScopedViewSet, ModelViewSet):
        activity_type = "task"
        activity_fields = ("title", "status", "priority", "due_at")

The HTTP-level create() / update() / destroy() are wrapped, not perform_*:
the viewsets keep their own perform_* logic untouched. A viewset that
defines one of the three itself must call super() or log explicitly
(services.log); custom actions (status change, move, revoke...) always log
explicitly.
"""

from . import services
from .models import Verb


class ActivityMixin:
    activity_type = ""
    activity_fields: tuple[str, ...] = ()
    activity_create_verb = Verb.CREATED  # SHARED for share links

    # --- Hooks ---------------------------------------------------------------------
    def activity_label(self, obj) -> str:
        return services.label_of(obj)

    def activity_project(self, obj):
        """ProjectScopedViewSet.get_project(); override for other models."""
        return self.get_project(obj)

    def activity_workspace(self, obj):
        project = self.activity_project(obj)
        return project.workspace if project is not None else obj.workspace

    def activity_snapshot(self, obj) -> dict:
        return services.snapshot(obj, self.activity_fields)

    def _activity_target(self, obj) -> dict:
        return {
            "target_type": self.activity_type or type(obj).__name__.lower(),
            "label": self.activity_label(obj),
            "project": self.activity_project(obj),
            "workspace": self.activity_workspace(obj),
        }

    def _activity_fresh(self, pk):
        """The object as it is after the action (relations included)."""
        return self.queryset.model._default_manager.filter(pk=pk).first()

    # --- Wrapped verbs -------------------------------------------------------------
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        pk = response.data.get("id") if isinstance(response.data, dict) else None
        obj = self._activity_fresh(pk) if pk else None
        if obj is not None:
            services.log(
                request.user,
                self.activity_create_verb,
                obj,
                **self._activity_target(obj),
            )
        return response

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        before = self.activity_snapshot(obj)
        response = super().update(request, *args, **kwargs)
        fresh = self._activity_fresh(obj.pk)
        if fresh is not None:
            services.log_update(
                request.user,
                fresh,
                before,
                self.activity_snapshot(fresh),
                **self._activity_target(fresh),
            )
        return response

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        target = {**self._activity_target(obj), "target_id": obj.pk}
        response = super().destroy(request, *args, **kwargs)
        services.log(request.user, Verb.DELETED, **target)
        return response
