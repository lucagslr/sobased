"""Events endpoints. A plain ProjectScopedViewSet: reading needs the Viewer
role on the project, writing the Editor role (SPECIFICATIONS §1.3).

Recurring events: `?scope=this` (default) edits or deletes one occurrence,
`?scope=following` this one and all the next (the series is split).
"""

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter

from apps.projects.access import get_access_map
from apps.projects.permissions import ProjectScopedViewSet

from . import services
from .filters import EventFilter
from .models import Event
from .serializers import EventSerializer

STOP_NEEDS_FOLLOWING = (
    "Pour arrêter la récurrence, applique le changement à toutes les suivantes."
)
SCOPE_PARAMETER = OpenApiParameter(
    "scope",
    str,
    enum=["this", "following"],
    description="Récurrence : cette occurrence, ou toutes les suivantes",
)


class EventViewSet(ProjectScopedViewSet, viewsets.ModelViewSet):
    queryset = Event.objects.select_related("project", "series").prefetch_related(
        "participants", "contacts", "tags", "tasks"
    )
    serializer_class = EventSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = EventFilter
    ordering_fields = ["start", "created_at"]
    ordering = ["start", "id"]

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "access_map": get_access_map(self.request),
        }

    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        self.check_project_access(data["project"])
        rule = data.pop("rrule", "")
        participants = data.pop("participant_users", None)
        event = serializer.save(created_by=self.request.user)
        if participants is not None:
            event.participants.set(participants)
        if rule:
            self._start_series(event, rule)

    @transaction.atomic
    def perform_update(self, serializer):
        event = serializer.instance
        data = serializer.validated_data
        rule = data.pop("rrule", None)  # None: untouched, "": stop recurring
        participants = data.pop("participant_users", None)

        event = serializer.save()
        if participants is not None:
            event.participants.set(participants)

        scope = self.request.query_params.get("scope", "this")
        if event.series_id and scope == "following":
            services.apply_to_following(event, rule, self.request.user.timezone)
        elif event.series_id:
            # "Cette occurrence": later edits of the series will skip it.
            Event.objects.filter(pk=event.pk).update(is_exception=True)
            if rule == "":
                raise ValidationError({"rrule": STOP_NEEDS_FOLLOWING})
        elif rule:
            self._start_series(event, rule)

    def _start_series(self, event, rule):
        try:
            services.start_series(event, rule, self.request.user.timezone)
        except ValueError as exc:
            raise ValidationError({"rrule": str(exc)}) from exc

    def perform_destroy(self, instance):
        if self.request.query_params.get("scope") == "following":
            services.delete_with_following(instance)
        else:
            instance.delete()

    @extend_schema(parameters=[SCOPE_PARAMETER])
    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        return self._fresh(response, kwargs["pk"])

    @extend_schema(parameters=[SCOPE_PARAMETER])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return self._fresh(response, response.data["id"])

    def _fresh(self, response, pk):
        """Re-read the event: series and participants were set after save()."""
        response.data = self.get_serializer(self.queryset.get(pk=pk)).data
        return response
