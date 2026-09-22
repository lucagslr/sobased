"""Bookkeeping endpoints.

Money is only ever read through `for_user(request, finance="view")` and
written with `finance="edit"` (ProjectScopedViewSet with `finance = "rw"`):
without `can_view_finance` a transaction does not exist (404), without
`can_edit_finance` it cannot be changed (403). The cross-project views
(summary, budget, advances, exports) build on the same querysets and are
allow-listed in apps/projects/tests/test_route_audit.py.
"""

from datetime import date

from django.db import transaction as db_transaction
from django.db.models import RestrictedError
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, NotFound, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.activity.mixins import ActivityMixin
from apps.core.files import protected_file_response
from apps.core.localtime import local_today
from apps.projects.access import Role, effective_access, get_access_map
from apps.projects.models import Project
from apps.projects.permissions import ProjectScopedViewSet, WorkspaceScopedViewSet

from . import exports, services
from .filters import TransactionFilter
from .models import (
    FALLBACK_CATEGORY,
    RECEIPT_MAX_MB,
    BudgetLine,
    Category,
    RecurringExpense,
    Transaction,
)
from .serializers import (
    AdvanceSerializer,
    BudgetLineSerializer,
    BudgetSerializer,
    CategorySerializer,
    FinanceSummarySerializer,
    MarkReimbursedSerializer,
    RecurringExpenseSerializer,
    TransactionSerializer,
)

FILTER_PARAMETERS = [
    OpenApiParameter("project", int),
    OpenApiParameter("include_descendants", bool),
    OpenApiParameter("workspace", int),
    OpenApiParameter("kind", str, enum=["expense", "income"]),
    OpenApiParameter("category", int),
    OpenApiParameter("date_after", date),
    OpenApiParameter("date_before", date),
    OpenApiParameter("payment_status", str, enum=["to_pay", "paid"]),
    OpenApiParameter("needs_receipt", bool),
    OpenApiParameter("to_reimburse", bool, description="Avances ouvertes"),
    OpenApiParameter("reimbursed", bool),
    OpenApiParameter("paid_by", str, description="`me` ou nom d'utilisateur"),
    OpenApiParameter("paid_by_contact", int),
    OpenApiParameter("event", int),
    OpenApiParameter("search", str),
]


def _filtered(request, queryset):
    """Apply the transaction filters of the query string to `queryset`."""
    filterset = TransactionFilter(
        request.query_params, queryset=queryset, request=request
    )
    if not filterset.is_valid():
        raise ValidationError(filterset.errors)
    return filterset.qs


def _readable(request):
    return Transaction.objects.for_user(request, finance="view").select_related(
        "project", "category"
    )


# --- Categories -----------------------------------------------------------------------


class CategoryViewSet(WorkspaceScopedViewSet, viewsets.ModelViewSet):
    """Bookkeeping categories of a workspace. Read: anyone in it (they are
    just names). Write: admins."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    write_role = Role.ADMIN

    @extend_schema(parameters=[OpenApiParameter("workspace", int)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        workspace = self.request.query_params.get("workspace", "")
        return (
            queryset.filter(workspace_id=workspace) if workspace.isdigit() else queryset
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "replace_with", int, description="Catégorie de remplacement si utilisée"
            )
        ]
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @db_transaction.atomic
    def perform_destroy(self, instance):
        """A category in use is replaced by ?replace_with=<id>, or by "Autre"."""
        others = Category.objects.filter(workspace=instance.workspace).exclude(
            pk=instance.pk
        )
        replacement = (
            others.filter(pk=self.request.query_params.get("replace_with") or 0).first()
            or others.filter(name__iexact=FALLBACK_CATEGORY).first()
        )
        used = (
            instance.transactions.exists()
            or instance.budget_lines.exists()
            or instance.recurring_expenses.exists()
        )
        if used:
            if replacement is None:
                raise ValidationError(
                    "Cette catégorie est utilisée : indique une catégorie "
                    "de remplacement."
                )
            instance.transactions.update(category=replacement)
            instance.recurring_expenses.update(category=replacement)
            # Budget lines are unique per (project, category, kind): merge.
            for line in instance.budget_lines.all():
                services.upsert_budget_line(
                    line.project,
                    replacement,
                    line.kind,
                    line.amount
                    + (
                        BudgetLine.objects.filter(
                            project=line.project, category=replacement, kind=line.kind
                        )
                        .values_list("amount", flat=True)
                        .first()
                        or 0
                    ),
                )
                line.delete()
        try:
            instance.delete()
        except RestrictedError as exc:  # raced with a new transaction
            raise ValidationError("Cette catégorie est encore utilisée.") from exc


# --- Transactions ---------------------------------------------------------------------


class _FinanceScopedViewSet(ProjectScopedViewSet):
    """ProjectScopedViewSet whose custom GET actions (receipt...) only need
    the reading side of the finance rights."""

    finance = "rw"

    def required_role(self):
        if self.request.method in SAFE_METHODS:
            return self.read_role
        return super().required_role()

    def _finance_mode(self):
        return "view" if self.request.method in SAFE_METHODS else "edit"


class TransactionViewSet(ActivityMixin, _FinanceScopedViewSet, viewsets.ModelViewSet):
    activity_type = "transaction"
    activity_fields = (
        "label",
        "kind",
        "amount",
        "date",
        "category",
        "payment_status",
        "receipt",
    )
    queryset = Transaction.objects.select_related(
        "project",
        "category",
        "contact",
        "event",
        "paid_by_user",
        "paid_by_contact",
        "created_by",
    )
    serializer_class = TransactionSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    # "put" only for the receipt action: a full PUT on a transaction is refused.
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TransactionFilter
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-date", "-id"]

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "access_map": get_access_map(self.request),
        }

    @extend_schema(parameters=FILTER_PARAMETERS)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not kwargs.get("partial"):
            raise MethodNotAllowed("PUT")
        return super().update(request, *args, **kwargs)

    def _take_receipt(self, data) -> tuple[bool, object, str]:
        """Pop the receipt from validated data: (touched, upload, content type)."""
        if "receipt" not in data:
            return False, None, ""
        upload = data.pop("receipt")
        if upload is None:
            return True, None, ""
        if upload.size > RECEIPT_MAX_MB * 1024 * 1024:
            raise ValidationError(
                {"receipt": [f"Justificatif trop lourd ({RECEIPT_MAX_MB} Mo max)."]}
            )
        try:
            content_type = services.validate_receipt(upload)
        except services.InvalidReceipt as exc:
            raise ValidationError({"receipt": [str(exc)]}) from exc
        return True, upload, content_type

    @db_transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        self.check_project_access(data["project"])
        touched, upload, content_type = self._take_receipt(data)
        item = serializer.save(created_by=self.request.user)
        if touched and upload is not None:
            services.attach_receipt(item, upload, content_type)
            item.save(update_fields=["receipt", "receipt_name", "receipt_content_type"])

    @db_transaction.atomic
    def perform_update(self, serializer):
        touched, upload, content_type = self._take_receipt(serializer.validated_data)
        item = serializer.save()
        if touched:
            if upload is None:
                services.remove_receipt(item)
            else:
                services.attach_receipt(item, upload, content_type)
            item.save(update_fields=["receipt", "receipt_name", "receipt_content_type"])

    def perform_destroy(self, instance):
        services.remove_receipt(instance)
        instance.delete()

    # --- Receipt ---------------------------------------------------------------------
    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"receipt": {"type": "string", "format": "binary"}},
            }
        },
        responses={200: TransactionSerializer},
    )
    @action(
        detail=True, methods=["get", "put", "delete"], parser_classes=[MultiPartParser]
    )
    def receipt(self, request, pk=None):
        """GET: the file itself (served after the rights check). PUT: replace.
        DELETE: remove (the expense becomes « À justifier » again)."""
        item = self.get_object()
        if request.method == "GET":
            if not item.receipt:
                raise NotFound()
            return protected_file_response(
                item.receipt,
                content_type=item.receipt_content_type or "application/octet-stream",
                filename=item.receipt_name or None,
            )
        if request.method == "DELETE":
            services.remove_receipt(item)
        else:
            upload = request.FILES.get("receipt")
            if upload is None:
                raise ValidationError({"receipt": ["Aucun fichier reçu."]})
            _, upload, content_type = self._take_receipt({"receipt": upload})
            services.attach_receipt(item, upload, content_type)
        item.save(update_fields=["receipt", "receipt_name", "receipt_content_type"])
        return Response(self.get_serializer(item).data)

    # --- Status shortcuts -------------------------------------------------------------
    @extend_schema(request=None, responses={200: TransactionSerializer})
    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        item = self.get_object()
        item.payment_status = Transaction.PaymentStatus.PAID
        item.save(update_fields=["payment_status", "updated_at"])
        return Response(self.get_serializer(item).data)

    @extend_schema(
        request=MarkReimbursedSerializer, responses={200: TransactionSerializer}
    )
    @action(detail=True, methods=["post"], url_path="mark-reimbursed")
    def mark_reimbursed(self, request, pk=None):
        item = self.get_object()
        if not item.to_reimburse:
            raise ValidationError("Cette dépense n'est pas une avance à rembourser.")
        serializer = MarkReimbursedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item.reimbursed_on = serializer.validated_data.get(
            "reimbursed_on"
        ) or local_today(request.user)
        item.save(update_fields=["reimbursed_on", "updated_at"])
        return Response(self.get_serializer(item).data)


# --- Budget lines and recurring expenses ----------------------------------------------


class BudgetLineViewSet(
    ActivityMixin,
    _FinanceScopedViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Planned amounts of a project (`?project=`), one per category and kind."""

    activity_type = "budget_line"
    activity_fields = ("amount",)
    queryset = BudgetLine.objects.select_related("project", "category")
    serializer_class = BudgetLineSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    @extend_schema(parameters=[OpenApiParameter("project", int)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        project = self.request.query_params.get("project", "")
        return queryset.filter(project_id=project) if project.isdigit() else queryset

    def activity_label(self, obj):
        return f"{obj.category.name} · {obj.get_kind_display()}"

    def perform_create(self, serializer):
        data = serializer.validated_data
        self.check_project_access(data["project"])
        # Creating a line that exists updates it: the form is a grid, not a list.
        serializer.instance = services.upsert_budget_line(
            data["project"], data["category"], data["kind"], data["amount"]
        )


class RecurringExpenseViewSet(
    ActivityMixin, _FinanceScopedViewSet, viewsets.ModelViewSet
):
    activity_type = "recurring_expense"
    activity_fields = ("label", "amount", "frequency", "is_active")
    queryset = RecurringExpense.objects.select_related("project", "category")
    serializer_class = RecurringExpenseSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_context(self):
        today = local_today(self.request.user)

        def next_due(expense):
            if not expense.is_active:
                return None
            due = services.due_date(expense, today)
            if due < today:
                due = services.due_date(
                    expense, services.next_period_start(expense, today)
                )
            if expense.end_date and due > expense.end_date:
                return None
            return due.isoformat()

        return {**super().get_serializer_context(), "next_due": next_due}

    @extend_schema(
        parameters=[
            OpenApiParameter("project", int),
            OpenApiParameter("include_descendants", bool),
            OpenApiParameter("workspace", int),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("project", "").isdigit():
            ids = [int(params["project"])]
            if params.get("include_descendants") in ("true", "1"):
                ids += get_access_map(self.request).descendants(ids[0])
            queryset = queryset.filter(project_id__in=ids)
        if params.get("workspace", "").isdigit():
            queryset = queryset.filter(project__workspace_id=params["workspace"])
        return queryset

    def perform_create(self, serializer):
        self.check_project_access(serializer.validated_data["project"])
        serializer.save(created_by=self.request.user)


# --- Cross-project reads --------------------------------------------------------------


class FinanceSummaryView(APIView):
    """Totals by category, project and month of the filtered transactions."""

    @extend_schema(parameters=FILTER_PARAMETERS, responses=FinanceSummarySerializer)
    def get(self, request):
        data = services.summary(_filtered(request, _readable(request)))
        # Through the serializer: Decimals become "123.45", like model fields.
        return Response(FinanceSummarySerializer(data).data)


class FinanceBudgetView(APIView):
    """Planned versus actual of one project, own and with its sub-projects."""

    @extend_schema(
        parameters=[
            OpenApiParameter("project", int, required=True),
            OpenApiParameter("date_after", date),
            OpenApiParameter("date_before", date),
        ],
        responses=BudgetSerializer,
    )
    def get(self, request):
        project_id = request.query_params.get("project", "")
        project = (
            Project.objects.filter(pk=project_id).first()
            if project_id.isdigit()
            else None
        )
        access = effective_access(request, project) if project else None
        if project is None or not (access.has(Role.VIEWER) and access.can_view_finance):
            raise NotFound()
        transactions = _readable(request)
        for key in ("date_after", "date_before"):
            value = request.query_params.get(key)
            if value:
                lookup = "date__gte" if key == "date_after" else "date__lte"
                transactions = transactions.filter(**{lookup: value})
        readable_ids = set(get_access_map(request).project_ids(finance="view"))
        data = services.budget(
            project,
            transactions,
            BudgetLine.objects.for_user(request, finance="view"),
            readable_ids,
        )
        return Response(BudgetSerializer(data).data)


class FinanceAdvancesView(APIView):
    """« Qui doit quoi à qui » (SPEC §13)."""

    @extend_schema(
        parameters=[
            OpenApiParameter("workspace", int),
            OpenApiParameter("project", int, description="Sous-projets inclus"),
        ],
        responses=AdvanceSerializer(many=True),
    )
    def get(self, request):
        transactions = _readable(request)
        workspace = request.query_params.get("workspace", "")
        if workspace.isdigit():
            transactions = transactions.filter(project__workspace_id=workspace)
        project = request.query_params.get("project", "")
        if project.isdigit():
            branch = [int(project), *get_access_map(request).descendants(int(project))]
            transactions = transactions.filter(project_id__in=branch)
        return Response(
            AdvanceSerializer(services.advances(transactions), many=True).data
        )

    @extend_schema(
        request=MarkReimbursedSerializer,
        responses={
            200: {"type": "object", "properties": {"updated": {"type": "integer"}}}
        },
    )
    def post(self, request):
        """Mark several advances reimbursed at once (« tout le solde »)."""
        serializer = MarkReimbursedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data.get("transactions") or []
        when = serializer.validated_data.get("reimbursed_on") or local_today(
            request.user
        )
        updated = (
            Transaction.objects.for_user(request, finance="edit")
            .to_reimburse()
            .filter(pk__in=ids)
            .update(reimbursed_on=when, updated_at=timezone.now())
        )
        return Response({"updated": updated})


# --- Exports --------------------------------------------------------------------------

EXPORT_PARAMETERS = [
    OpenApiParameter("project", int),
    OpenApiParameter("include_descendants", bool),
    OpenApiParameter("workspace", int),
    OpenApiParameter("date_after", date),
    OpenApiParameter("date_before", date),
]


class _ExportView(APIView):
    """Downloads always cover the filtered, rights-limited transactions."""

    content_type = "application/octet-stream"
    extension = "bin"

    def build(self, request, transactions) -> bytes:  # pragma: no cover - abstract
        raise NotImplementedError

    @extend_schema(
        parameters=EXPORT_PARAMETERS,
        responses={200: {"type": "string", "format": "binary"}},
    )
    def get(self, request):
        transactions = _filtered(request, _readable(request)).order_by("date", "id")
        payload = self.build(request, transactions)
        response = HttpResponse(payload, content_type=self.content_type)
        stamp = local_today(request.user).isoformat()
        response["Content-Disposition"] = (
            f'attachment; filename="sobased-compta-{stamp}.{self.extension}"'
        )
        response["Cache-Control"] = "private, no-store"
        return response


class ExportXlsxView(_ExportView):
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    extension = "xlsx"

    def build(self, request, transactions):
        return exports.build_xlsx(transactions, exports.period_of(request))


class ExportPdfView(_ExportView):
    content_type = "application/pdf"
    extension = "pdf"

    def build(self, request, transactions):
        return exports.build_pdf(transactions, exports.period_of(request), request.user)


class ExportReceiptsView(_ExportView):
    content_type = "application/zip"
    extension = "zip"

    def build(self, request, transactions):
        return exports.build_receipts_zip(transactions)
