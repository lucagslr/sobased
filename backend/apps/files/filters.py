"""Query-string filters of GET /api/assets/. Rights are handled upstream."""

import django_filters

from apps.projects.access import get_access_map

from .models import Asset, Kind, Status


class AssetFilter(django_filters.FilterSet):
    project = django_filters.NumberFilter(method="by_project")
    include_descendants = django_filters.BooleanFilter(method="noop")
    workspace = django_filters.NumberFilter(field_name="project__workspace_id")
    kind = django_filters.ChoiceFilter(choices=Kind.choices)
    status = django_filters.ChoiceFilter(choices=Status.choices)
    tag = django_filters.NumberFilter(field_name="tags")
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = Asset
        fields: list[str] = []

    def noop(self, queryset, name, value):
        return queryset

    def by_project(self, queryset, name, value):
        ids = [int(value)]
        if self.data.get("include_descendants") in ("true", "1", "True"):
            ids += get_access_map(self.request).descendants(int(value))
        return queryset.filter(project_id__in=ids)
