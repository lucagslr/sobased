from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.events.serializers import EventSerializer
from apps.projects import tree
from apps.projects.models import Project
from apps.tasks.serializers import PinnedItemSerializer, TaskSerializer

from .models import WIDGET_KEYS, DashboardView, normalise_filters, normalise_layout


class ViewFiltersSerializer(serializers.Serializer):
    """Shape of DashboardView.filters (documentation only)."""

    workspaces = serializers.ListField(child=serializers.IntegerField())
    projects = serializers.ListField(
        child=serializers.IntegerField(), help_text="Sub-projects are included"
    )
    tags = serializers.ListField(child=serializers.IntegerField())
    only_mine = serializers.BooleanField()


class WidgetLayoutSerializer(serializers.Serializer):
    """One entry of DashboardView.layout (documentation only)."""

    key = serializers.ChoiceField(choices=WIDGET_KEYS)
    size = serializers.IntegerField(min_value=1, max_value=3)
    tall = serializers.BooleanField()
    hidden = serializers.BooleanField()


# The columns are JSON; these two fields only give them a type in the OpenAPI
# schema, so that the front does not receive `unknown`.
@extend_schema_field(ViewFiltersSerializer)
class FiltersField(serializers.JSONField):
    pass


@extend_schema_field(WidgetLayoutSerializer(many=True))
class LayoutField(serializers.JSONField):
    pass


class DashboardViewSerializer(serializers.ModelSerializer):
    filters = FiltersField(required=False)
    layout = LayoutField(required=False)

    class Meta:
        model = DashboardView
        fields = ["id", "name", "filters", "layout", "is_default", "position"]
        read_only_fields = ["id"]

    # Whatever the client sends is reduced to the shape we understand.
    def validate_filters(self, value):
        return normalise_filters(value)

    def validate_layout(self, value):
        return normalise_layout(value)


# --- Summary (documentation of the response shape) ------------------------------
# The view builds plain dicts; these serializers describe them for OpenAPI, so
# that the front gets exact TypeScript types. tests/test_dashboard.py checks
# that both stay in step.


class TaskWidgetSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    count = serializers.IntegerField(help_text="Total, even beyond the listed items")
    items = TaskSerializer(many=True)


class PinnedWidgetSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    count = serializers.IntegerField()
    items = PinnedItemSerializer(many=True)


class ValidateItemSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["task", "project", "asset"])
    id = serializers.IntegerField()
    title = serializers.CharField()
    project = serializers.IntegerField()
    project_name = serializers.CharField()
    project_color = serializers.CharField()


class ValidateWidgetSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    count = serializers.IntegerField()
    items = ValidateItemSerializer(many=True)


class MeetingsWidgetSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    count = serializers.IntegerField()
    items = EventSerializer(many=True)


class PendingWidgetSerializer(serializers.Serializer):
    """A widget whose feature is not built yet: the front hides it."""

    available = serializers.BooleanField()
    count = serializers.IntegerField()


class DashboardWidgetsSerializer(serializers.Serializer):
    overdue = TaskWidgetSerializer()
    today = TaskWidgetSerializer()
    pinned = PinnedWidgetSerializer()
    next7 = TaskWidgetSerializer()
    to_validate = ValidateWidgetSerializer()
    meetings = MeetingsWidgetSerializer()
    expenses_to_pay = PendingWidgetSerializer()
    missing_receipts = PendingWidgetSerializer()


class DashboardSummarySerializer(serializers.Serializer):
    date = serializers.DateField(help_text="Today, on the user's clock")
    widgets = DashboardWidgetsSerializer()


class MilestoneSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=["task", "event", "project_start", "project_end"]
    )
    id = serializers.IntegerField()
    date = serializers.DateField()
    title = serializers.CharField()
    project = serializers.IntegerField()
    color = serializers.CharField()


class ProjectOverviewSerializer(serializers.Serializer):
    date = serializers.DateField()
    overdue = TaskWidgetSerializer()
    today = TaskWidgetSerializer()
    milestones = MilestoneSerializer(many=True)


# --- Cards mode of the Projects page (documentation of cards.build_cards) -------


class CardStatsSerializer(serializers.Serializer):
    """Task counts of a project AND of the sub-projects I can see."""

    tasks_total = serializers.IntegerField(
        help_text="Cancelled tasks and future repetitions excluded"
    )
    tasks_done = serializers.IntegerField()
    tasks_overdue = serializers.IntegerField()


class NextDueSerializer(serializers.Serializer):
    task = serializers.IntegerField()
    title = serializers.CharField()
    date = serializers.DateField()
    project = serializers.IntegerField()


class CardEntrySerializer(CardStatsSerializer):
    """A sub-project inside one of the three columns of a card."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    color = serializers.CharField()
    type_name = serializers.CharField()
    status = serializers.ChoiceField(choices=Project.Status.choices)
    start_date = serializers.DateField(allow_null=True)
    end_date = serializers.DateField(allow_null=True)
    end_overdue = serializers.BooleanField()
    children_count = serializers.IntegerField()


class ProjectCardSerializer(CardStatsSerializer):
    """One root project. When the root is a SHELL for me, only its id,
    workspace, name and colour are filled; the rest covers my branches."""

    id = serializers.IntegerField()
    workspace = serializers.IntegerField()
    name = serializers.CharField()
    color = serializers.CharField()
    is_shell = serializers.BooleanField()
    type_name = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=Project.Status.choices, allow_null=True)
    start_date = serializers.DateField(allow_null=True)
    end_date = serializers.DateField(allow_null=True)
    temporal = serializers.ChoiceField(
        choices=[tree.PAST, tree.CURRENT, tree.UPCOMING], allow_null=True
    )
    end_overdue = serializers.BooleanField()
    next_due = NextDueSerializer(allow_null=True)
    past = CardEntrySerializer(many=True)
    current = CardEntrySerializer(many=True)
    upcoming = CardEntrySerializer(many=True)
