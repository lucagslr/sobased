"""Dashboard endpoints: widget data, project overview, saved views.

None of these is a ProjectScopedViewSet (they aggregate across projects), so
each is listed in apps/projects/tests/test_route_audit.py with its reason:
data always comes from `for_user(request)` querysets (services.py).
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.serializers import EventSerializer
from apps.finance.serializers import TransactionSerializer
from apps.projects.access import Role, effective_access, get_access_map
from apps.projects.models import Project
from apps.tasks.serializers import PinnedItemSerializer, TaskSerializer

from . import services
from .cards import build_cards
from .models import DashboardView, normalise_filters
from .serializers import (
    DashboardSummarySerializer,
    DashboardViewSerializer,
    OverviewBudgetSerializer,
    ProjectCardSerializer,
    ProjectOverviewSerializer,
)

DEFAULT_VIEW_NAME = "Mon dashboard"


def _ids(request, name: str) -> list[int]:
    return [
        int(value) for value in request.query_params.getlist(name) if value.isdigit()
    ]


def _task_context(request, scope) -> dict:
    return {
        "request": request,
        "access_map": get_access_map(request),
        "today": scope.today,
        "now": timezone.now(),
    }


def _task_widget(queryset, context) -> dict:
    return {
        "available": True,
        "count": queryset.count(),
        "items": TaskSerializer(
            queryset[: services.WIDGET_LIMIT], many=True, context=context
        ).data,
    }


class DashboardSummaryView(APIView):
    """Data of every widget in one call (one round trip, one consistent "now")."""

    @extend_schema(
        parameters=[
            OpenApiParameter("view", int, description="Filtres d'une vue enregistrée"),
            OpenApiParameter("workspace", int, many=True),
            OpenApiParameter(
                "project", int, many=True, description="Sous-projets inclus"
            ),
            OpenApiParameter("tag", int, many=True),
            OpenApiParameter("only_mine", bool),
        ],
        responses=DashboardSummarySerializer,
    )
    def get(self, request):
        view_id = request.query_params.get("view", "")
        if view_id.isdigit():
            view = get_object_or_404(DashboardView, pk=view_id, user=request.user)
            filters = view.filters
        else:
            filters = normalise_filters(
                {
                    "workspaces": _ids(request, "workspace"),
                    "projects": _ids(request, "project"),
                    "tags": _ids(request, "tag"),
                    "only_mine": request.query_params.get("only_mine") in ("true", "1"),
                }
            )
        scope = services.resolve_scope(request, filters)
        context = _task_context(request, scope)
        pinned = services.pinned_items(request, scope)
        to_validate = services.to_validate_items(request, scope)
        meetings = services.upcoming_events(request, scope)
        # Money widgets only list projects where I have can_view_finance;
        # without any such project they are hidden (available: false).
        money = get_access_map(request).project_ids(finance="view")
        to_pay = services.expenses_to_pay(request, scope)
        missing = services.missing_receipts(request, scope)
        return Response(
            {
                "date": scope.today,
                "widgets": {
                    "overdue": _task_widget(
                        services.overdue_tasks(request, scope), context
                    ),
                    "today": _task_widget(
                        services.today_tasks(request, scope), context
                    ),
                    "pinned": {
                        "available": True,
                        "count": pinned.count(),
                        "items": PinnedItemSerializer(
                            pinned[: services.WIDGET_LIMIT], many=True
                        ).data,
                    },
                    "next7": _task_widget(
                        services.next_days_tasks(request, scope), context
                    ),
                    "to_validate": {
                        "available": True,
                        "count": len(to_validate),
                        "items": to_validate,
                    },
                    "meetings": {
                        "available": True,
                        "count": meetings.count(),
                        "items": EventSerializer(
                            meetings[: services.WIDGET_LIMIT],
                            many=True,
                            context=context,
                        ).data,
                    },
                    "expenses_to_pay": self._money_widget(money, to_pay, context),
                    "missing_receipts": self._money_widget(money, missing, context),
                },
            }
        )

    @staticmethod
    def _money_widget(money_project_ids, queryset, context) -> dict:
        if not money_project_ids:
            return {"available": False, "count": 0}
        return {
            "available": True,
            "count": queryset.count(),
            "items": TransactionSerializer(
                queryset[: services.WIDGET_LIMIT], many=True, context=context
            ).data,
        }


class ProjectOverviewView(APIView):
    """Mini-dashboard of one project and its sub-projects (SPEC §15, page 3)."""

    @extend_schema(responses=ProjectOverviewSerializer)
    def get(self, request, pk):
        project = Project.objects.filter(pk=pk).first()
        # A shell has no content: same answer as a project that does not exist.
        if project is None or not effective_access(request, project).has(Role.VIEWER):
            raise NotFound()
        scope = services.resolve_scope(request, normalise_filters({"projects": [pk]}))
        context = _task_context(request, scope)
        access = effective_access(request, project)
        return Response(
            {
                "date": scope.today,
                "overdue": _task_widget(
                    services.overdue_tasks(request, scope), context
                ),
                "today": _task_widget(services.today_tasks(request, scope), context),
                "milestones": services.milestones(request, scope, project.pk),
                # Money only with can_view_finance: null otherwise, never zeros
                # that would look like "nothing spent".
                "budget": (
                    OverviewBudgetSerializer(
                        services.project_budget(request, project)
                    ).data
                    if access.can_view_finance
                    else None
                ),
            }
        )


class ProjectCardsView(APIView):
    """Cards mode of the Projects page: one card per root project (cards.py)."""

    @extend_schema(
        parameters=[OpenApiParameter("workspace", int, description="Un seul espace")],
        responses=ProjectCardSerializer(many=True),
    )
    def get(self, request):
        workspace = request.query_params.get("workspace", "")
        cards = build_cards(request, int(workspace) if workspace.isdigit() else None)
        return Response(ProjectCardSerializer(cards, many=True).data)


class DashboardViewViewSet(viewsets.ModelViewSet):
    """My saved views ("Perso", "100SATIONS", "École"): filters + layout.

    A user only ever sees and edits their own views. The first call creates
    "Mon dashboard", so that the layout can be saved before any view is named.
    """

    # Class-level queryset: only so that the OpenAPI generator can type the
    # path parameter. Every request goes through get_queryset() below.
    queryset = DashboardView.objects.all()
    serializer_class = DashboardViewSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        if not self.get_queryset().exists():
            DashboardView.objects.create(
                user=request.user, name=DEFAULT_VIEW_NAME, is_default=True
            )
        return super().list(request, *args, **kwargs)

    @transaction.atomic
    def _save(self, serializer, **extra):
        # One default per user (also enforced by a partial unique index):
        # clear the previous one first.
        if serializer.validated_data.get("is_default"):
            self.get_queryset().filter(is_default=True).update(is_default=False)
        serializer.save(**extra)

    def perform_create(self, serializer):
        self._save(
            serializer, user=self.request.user, position=self.get_queryset().count()
        )

    def perform_update(self, serializer):
        self._save(serializer)

    def perform_destroy(self, instance):
        was_default = instance.is_default
        instance.delete()
        # Never leave the user without a default view.
        if was_default:
            heir = self.get_queryset().first()
            if heir is not None:
                heir.is_default = True
                heir.save(update_fields=["is_default", "updated_at"])
