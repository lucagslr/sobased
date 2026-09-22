"""Bookkeeping (SPEC §13): CHF only, no VAT.

Computed, never stored (DATABASE_SCHEMA §6):
- "À justifier": an expense without a receipt (`needs_receipt`);
- "À rembourser": `to_reimburse` and not yet `reimbursed_on`;
- the display status of a transaction, by priority: to pay > to justify >
  to reimburse > ok (SPECIFICATIONS §9);
- budget roll-ups over the sub-projects.

Rights: every money-bearing model uses ProjectScopedQuerySet, and the views
declare `finance = "rw"`: reading needs `can_view_finance` (else 404),
writing `can_edit_finance`, on top of the project role.
"""

import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.contacts.models import Contact
from apps.core.models import TimeStampedModel
from apps.events.models import Event
from apps.projects.models import Project
from apps.projects.querysets import ProjectScopedQuerySet
from apps.workspaces.models import Workspace

# Seeded in every new workspace (SPEC §13), editable afterwards.
DEFAULT_CATEGORIES = [
    "Studio",
    "Logiciel",
    "Matériel",
    "Transport",
    "Communication",
    "Graphisme",
    "Tournage",
    "Location",
    "Frais admin",
    "Cachet",
    "Billetterie",
    "Subvention",
    "Streaming",
    "Merch",
    "Autre",
]
FALLBACK_CATEGORY = "Autre"

RECEIPT_MAX_MB = 20


class Category(TimeStampedModel):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=60)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"], name="category_unique_name_per_workspace"
            )
        ]

    def __str__(self):
        return self.name

    @classmethod
    def create_defaults(cls, workspace) -> None:
        cls.objects.bulk_create(
            cls(workspace=workspace, name=name, position=index)
            for index, name in enumerate(DEFAULT_CATEGORIES)
        )


class Kind(models.TextChoices):
    EXPENSE = "expense", "Dépense"
    INCOME = "income", "Recette"


def receipt_path(transaction, filename: str) -> str:
    """Random name under receipts/: the URL never reveals the original name,
    and an old receipt's path never resolves to a new one."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"receipts/{transaction.project_id}/{secrets.token_hex(12)}.{extension}"


class TransactionQuerySet(ProjectScopedQuerySet):
    def needing_receipt(self):
        """Expenses without a receipt: « À justifier » (SPEC §13)."""
        return self.filter(kind=Kind.EXPENSE, receipt="")

    def to_reimburse(self):
        return self.filter(to_reimburse=True, reimbursed_on__isnull=True)


class Transaction(TimeStampedModel):
    class PaymentStatus(models.TextChoices):
        TO_PAY = "to_pay", "À payer"
        PAID = "paid", "Payé"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="transactions"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    date = models.DateField()
    # RESTRICT, not PROTECT: a used category is replaced through the API
    # before deletion, but deleting the whole workspace must still cascade.
    category = models.ForeignKey(
        Category, on_delete=models.RESTRICT, related_name="transactions"
    )
    label = models.CharField(max_length=200)
    vendor = models.CharField(max_length=120, blank=True)  # free text
    contact = models.ForeignKey(
        Contact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    event = models.ForeignKey(
        Event,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    receipt = models.FileField(upload_to=receipt_path, blank=True, max_length=200)
    receipt_name = models.CharField(max_length=200, blank=True)  # as uploaded
    receipt_content_type = models.CharField(max_length=80, blank=True)
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PAID
    )
    # Expense advance: who paid out of their own pocket (at most one of the two).
    paid_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="advances",
    )
    paid_by_contact = models.ForeignKey(
        Contact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="advances",
    )
    to_reimburse = models.BooleanField(default=False)
    reimbursed_on = models.DateField(null=True, blank=True)
    recurring_expense = models.ForeignKey(
        "RecurringExpense",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    # "2026-09" (monthly) or "2026" (yearly): makes the nightly job idempotent.
    period_key = models.CharField(max_length=7, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = TransactionQuerySet.as_manager()

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=["project", "date"]),
            models.Index(fields=["date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="transaction_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(paid_by_user__isnull=True)
                | Q(paid_by_contact__isnull=True),
                name="transaction_single_payer",
            ),
            models.UniqueConstraint(
                fields=["recurring_expense", "period_key"],
                condition=Q(recurring_expense__isnull=False),
                name="transaction_unique_period_per_recurring_expense",
            ),
        ]

    def __str__(self):
        return f"{self.label} ({self.amount} CHF)"

    @property
    def needs_receipt(self) -> bool:
        return self.kind == Kind.EXPENSE and not self.receipt

    @property
    def is_to_reimburse(self) -> bool:
        return self.to_reimburse and self.reimbursed_on is None

    @property
    def display_status(self) -> str:
        """SPECIFICATIONS §9: to_pay > needs_receipt > to_reimburse > ok."""
        if self.payment_status == self.PaymentStatus.TO_PAY:
            return "to_pay"
        if self.needs_receipt:
            return "needs_receipt"
        if self.is_to_reimburse:
            return "to_reimburse"
        return "ok"


DISPLAY_STATUS_CHOICES = [
    ("to_pay", "À payer"),
    ("needs_receipt", "À justifier"),
    ("to_reimburse", "À rembourser"),
    ("ok", "OK"),
]


class RecurringExpense(TimeStampedModel):
    """Studio One, software, the bank card... (SPEC §13). Each period the
    nightly job creates one transaction "À payer" (services.generate_due)."""

    class Frequency(models.TextChoices):
        MONTHLY = "monthly", "Mensuel"
        YEARLY = "yearly", "Annuel"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="recurring_expenses"
    )
    label = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    category = models.ForeignKey(
        Category, on_delete=models.RESTRICT, related_name="recurring_expenses"
    )
    vendor = models.CharField(max_length=120, blank=True)
    frequency = models.CharField(
        max_length=10, choices=Frequency.choices, default=Frequency.MONTHLY
    )
    # Day of the period (1-31, clamped to the month's last day); month if yearly.
    day = models.PositiveSmallIntegerField(default=1)
    month = models.PositiveSmallIntegerField(default=1)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = ProjectScopedQuerySet.as_manager()

    class Meta:
        ordering = ["label", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(day__gte=1) & Q(day__lte=31),
                name="recurringexpense_day_between_1_and_31",
            ),
            models.CheckConstraint(
                condition=Q(month__gte=1) & Q(month__lte=12),
                name="recurringexpense_month_between_1_and_12",
            ),
        ]

    def __str__(self):
        return self.label


class BudgetLine(TimeStampedModel):
    """Planned amount per (project, category, kind). Actuals are computed."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="budget_lines"
    )
    category = models.ForeignKey(
        Category, on_delete=models.RESTRICT, related_name="budget_lines"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )

    objects = ProjectScopedQuerySet.as_manager()

    class Meta:
        ordering = ["kind", "category__position", "category__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "category", "kind"],
                name="budgetline_unique_per_project_category_kind",
            )
        ]

    def __str__(self):
        return f"{self.project} / {self.category} / {self.kind}: {self.amount}"


# Importable paths for drf-spectacular's ENUM_NAME_OVERRIDES.
KIND_CHOICES = Kind.choices
PAYMENT_STATUS_CHOICES = Transaction.PaymentStatus.choices
FREQUENCY_CHOICES = RecurringExpense.Frequency.choices
