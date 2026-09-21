"""Query-string filters of GET /api/tasks/ (API_DOCUMENTATION §4).

Rights are NOT handled here: the queryset received is already limited to what
the user can read (ProjectScopedViewSet.get_queryset).
"""

import django_filters
from django.db.models import Q

from apps.projects.access import get_access_map

from .models import Task


class TaskFilter(django_filters.FilterSet):
    project = django_filters.NumberFilter(method="by_project")
    # Only meaningful with ?project= : also include its sub-projects.
    include_descendants = django_filters.BooleanFilter(method="noop")
    workspace = django_filters.NumberFilter(field_name="project__workspace_id")
    assignee = django_filters.CharFilter(method="by_assignee")
    status = django_filters.MultipleChoiceFilter(choices=Task.Status.choices)
    priority = django_filters.NumberFilter()
    tag = django_filters.ModelMultipleChoiceFilter(
        field_name="tags", queryset=lambda request: _tags(request)
    )
    overdue = django_filters.BooleanFilter(method="by_overdue")
    open = django_filters.BooleanFilter(method="by_open")
    due_after = django_filters.IsoDateTimeFilter(field_name="due_at", lookup_expr="gte")
    due_before = django_filters.IsoDateTimeFilter(field_name="due_at", lookup_expr="lt")
    no_date = django_filters.BooleanFilter(method="by_no_date")
    search = django_filters.CharFilter(field_name="title", lookup_expr="icontains")

    class Meta:
        model = Task
        fields: list[str] = []

    def noop(self, queryset, name, value):
        return queryset

    def by_project(self, queryset, name, value):
        ids = [int(value)]
        if self.data.get("include_descendants") in ("true", "1", "True"):
            ids += get_access_map(self.request).descendants(int(value))
        return queryset.filter(project_id__in=ids)

    def by_assignee(self, queryset, name, value):
        if value == "me":
            return queryset.filter(assignees=self.request.user)
        return queryset.filter(assignees__username__iexact=value.lstrip("@"))

    def by_overdue(self, queryset, name, value):
        late = Task.objects.overdue(today=self.request.local_today).values("pk")
        return queryset.filter(pk__in=late) if value else queryset.exclude(pk__in=late)

    def by_open(self, queryset, name, value):
        closed = Q(status__in=Task.CLOSED_STATUSES)
        return queryset.exclude(closed) if value else queryset.filter(closed)

    def by_no_date(self, queryset, name, value):
        undated = Q(due_at__isnull=True, start_at__isnull=True)
        return queryset.filter(undated) if value else queryset.exclude(undated)


def _tags(request):
    from apps.workspaces.models import Tag

    if request is None:
        return Tag.objects.none()
    return Tag.objects.filter(workspace__in=list(get_access_map(request).workspaces))
