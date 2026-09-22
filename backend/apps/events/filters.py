"""Query-string filters of GET /api/events/.

Rights are NOT handled here: the queryset received is already limited to what
the user can read (ProjectScopedViewSet.get_queryset).
"""

import django_filters

from apps.projects.access import get_access_map

from .models import Event


class EventFilter(django_filters.FilterSet):
    project = django_filters.NumberFilter(method="by_project")
    # Only meaningful with ?project= : also include its sub-projects.
    include_descendants = django_filters.BooleanFilter(method="noop")
    workspace = django_filters.NumberFilter(field_name="project__workspace_id")
    type = django_filters.MultipleChoiceFilter(choices=Event.Type.choices)
    participant = django_filters.CharFilter(method="by_participant")
    contact = django_filters.NumberFilter(field_name="contacts")
    tag = django_filters.NumberFilter(field_name="tags")
    # Calendars: events that cross [window_start, window_end[ (same meaning
    # as on /api/tasks/).
    window_start = django_filters.IsoDateTimeFilter(field_name="end", lookup_expr="gte")
    window_end = django_filters.IsoDateTimeFilter(field_name="start", lookup_expr="lt")
    search = django_filters.CharFilter(field_name="title", lookup_expr="icontains")

    class Meta:
        model = Event
        fields: list[str] = []

    def noop(self, queryset, name, value):
        return queryset

    def by_project(self, queryset, name, value):
        ids = [int(value)]
        if self.data.get("include_descendants") in ("true", "1", "True"):
            ids += get_access_map(self.request).descendants(int(value))
        return queryset.filter(project_id__in=ids)

    def by_participant(self, queryset, name, value):
        if value == "me":
            return queryset.filter(participants=self.request.user)
        return queryset.filter(participants__username__iexact=value.lstrip("@"))
