from django.db.models import F, Q
from django.utils import timezone
from django_filters import rest_framework as filters

from apps.projects.access import get_access_map

from .models import ShareLink


class ShareLinkFilter(filters.FilterSet):
    project = filters.NumberFilter(method="filter_project")
    include_descendants = filters.BooleanFilter(method="filter_noop")
    workspace = filters.NumberFilter(field_name="project__workspace_id")
    state = filters.CharFilter(method="filter_state")

    class Meta:
        model = ShareLink
        fields = ["project", "include_descendants", "workspace", "state"]

    def filter_noop(self, queryset, name, value):
        return queryset  # read by filter_project

    def filter_project(self, queryset, name, value):
        ids = [int(value)]
        if self.data.get("include_descendants") in ("true", "1", "True"):
            ids += get_access_map(self.request).descendants(int(value))
        return queryset.filter(project_id__in=ids)

    def filter_state(self, queryset, name, value):
        """The computed state, expressed in SQL (mirrors ShareLink.state)."""
        now = timezone.now()
        revoked = Q(revoked_at__isnull=False)
        expired = Q(expires_at__isnull=False, expires_at__lte=now)
        exhausted = Q(max_views__isnull=False, view_count__gte=F("max_views")) | Q(
            max_plays__isnull=False, play_count__gte=F("max_plays")
        )
        if value == "revoked":
            return queryset.filter(revoked)
        if value == "expired":
            return queryset.filter(~revoked & expired)
        if value == "exhausted":
            return queryset.filter(~revoked & ~expired & exhausted)
        if value == "active":
            return queryset.filter(~revoked & ~expired & ~exhausted)
        return queryset
