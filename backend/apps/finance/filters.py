"""Query-string filters of GET /api/transactions/, also used by the
summaries and the exports so that a report covers exactly what is listed.

Rights are NOT handled here: the queryset received is already limited to the
projects where the user may see money.
"""

import django_filters
from django.db.models import Q

from apps.projects.access import get_access_map

from .models import Kind, Transaction


class TransactionFilter(django_filters.FilterSet):
    project = django_filters.NumberFilter(method="by_project")
    # Only meaningful with ?project= : also include its sub-projects.
    include_descendants = django_filters.BooleanFilter(method="noop")
    workspace = django_filters.NumberFilter(field_name="project__workspace_id")
    kind = django_filters.ChoiceFilter(choices=Kind.choices)
    category = django_filters.NumberFilter(field_name="category_id")
    # Inclusive period: "du 1er janvier au 31 décembre".
    date_after = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    payment_status = django_filters.ChoiceFilter(
        choices=Transaction.PaymentStatus.choices
    )
    needs_receipt = django_filters.BooleanFilter(method="by_needs_receipt")
    # Open advances (to reimburse and not yet reimbursed).
    to_reimburse = django_filters.BooleanFilter(method="by_to_reimburse")
    reimbursed = django_filters.BooleanFilter(method="by_reimbursed")
    paid_by = django_filters.CharFilter(method="by_paid_by")
    paid_by_contact = django_filters.NumberFilter(field_name="paid_by_contact_id")
    event = django_filters.NumberFilter(field_name="event_id")
    search = django_filters.CharFilter(method="by_search")

    class Meta:
        model = Transaction
        fields: list[str] = []

    def noop(self, queryset, name, value):
        return queryset

    def by_project(self, queryset, name, value):
        ids = [int(value)]
        if self.data.get("include_descendants") in ("true", "1", "True"):
            ids += get_access_map(self.request).descendants(int(value))
        return queryset.filter(project_id__in=ids)

    def by_needs_receipt(self, queryset, name, value):
        missing = Q(kind=Kind.EXPENSE, receipt="")
        return queryset.filter(missing) if value else queryset.exclude(missing)

    def by_to_reimburse(self, queryset, name, value):
        pending = Q(to_reimburse=True, reimbursed_on__isnull=True)
        return queryset.filter(pending) if value else queryset.exclude(pending)

    def by_reimbursed(self, queryset, name, value):
        done = Q(to_reimburse=True, reimbursed_on__isnull=False)
        return queryset.filter(done) if value else queryset.exclude(done)

    def by_paid_by(self, queryset, name, value):
        if value == "me":
            return queryset.filter(paid_by_user=self.request.user)
        return queryset.filter(paid_by_user__username__iexact=value.lstrip("@"))

    def by_search(self, queryset, name, value):
        return queryset.filter(Q(label__icontains=value) | Q(vendor__icontains=value))
