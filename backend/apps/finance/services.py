"""Bookkeeping rules that do not depend on who is asking.

- receipts: what counts as a valid receipt (image or PDF, checked by content);
- summaries: totals by category, project and month;
- budget: planned versus actual, own and with the sub-projects;
- advances: who owes what to whom;
- recurring expenses: the nightly generation of "À payer" transactions.

Every function receives querysets already limited by rights (the views pass
`for_user(request, finance="view")` querysets): nothing here decides rights.
"""

from __future__ import annotations

import calendar
import secrets
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction as db_transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from PIL import Image, UnidentifiedImageError

from apps.projects import tree
from apps.projects.models import Project

from .models import BudgetLine, Kind, RecurringExpense, Transaction

ZERO = Decimal("0.00")

# --- Receipts -------------------------------------------------------------------------

RECEIPT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "application/pdf": "pdf",
}


class InvalidReceipt(ValueError):
    pass


def validate_receipt(upload) -> str:
    """Return the real content type of an uploaded receipt, or raise.

    The file is inspected, not trusted on its extension: a PDF starts with
    %PDF-, an image must open with Pillow. Images are stored as uploaded
    (a receipt must stay readable as evidence; no re-encoding).
    """
    head = upload.read(8)
    upload.seek(0)
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    try:
        with Image.open(upload) as image:
            image.verify()
            fmt = (image.format or "").lower()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidReceipt("Le justificatif doit être une image ou un PDF.") from exc
    finally:
        upload.seek(0)
    mapping = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    if fmt not in mapping:
        raise InvalidReceipt("Format d'image non pris en charge (JPEG, PNG, WebP).")
    return mapping[fmt]


def attach_receipt(transaction: Transaction, upload, content_type: str) -> None:
    """Store `upload` as the receipt of `transaction`, replacing any previous one."""
    if transaction.receipt:
        transaction.receipt.delete(save=False)
    extension = RECEIPT_TYPES[content_type]
    content = ContentFile(upload.read(), name=f"{secrets.token_hex(12)}.{extension}")
    transaction.receipt_name = upload.name[:200]
    transaction.receipt_content_type = content_type
    transaction.receipt.save(content.name, content, save=False)


def remove_receipt(transaction: Transaction) -> None:
    if transaction.receipt:
        transaction.receipt.delete(save=False)
    transaction.receipt = ""
    transaction.receipt_name = ""
    transaction.receipt_content_type = ""


# --- Summaries ------------------------------------------------------------------------


def _signed(rows, key: str) -> list[dict]:
    """Group expense / income totals per `key`, with the balance."""
    totals: dict = defaultdict(lambda: {"expense": ZERO, "income": ZERO})
    for row in rows:
        totals[row[key]][row["kind"]] = row["total"] or ZERO
    return [
        {
            key: value,
            "expense": amounts["expense"],
            "income": amounts["income"],
            "balance": amounts["income"] - amounts["expense"],
        }
        for value, amounts in totals.items()
    ]


def summary(transactions) -> dict:
    """Totals of a (rights-limited, period-filtered) queryset of transactions."""
    by_kind = {
        row["kind"]: row["total"] or ZERO
        for row in transactions.values("kind").annotate(total=Sum("amount"))
    }
    expense = by_kind.get(Kind.EXPENSE, ZERO)
    income = by_kind.get(Kind.INCOME, ZERO)
    by_category = _signed(
        transactions.values("category_id", "category__name", "kind").annotate(
            total=Sum("amount")
        ),
        "category_id",
    )
    names = {
        row["category_id"]: row["category__name"]
        for row in transactions.values("category_id", "category__name")
    }
    for entry in by_category:
        entry["category"] = entry.pop("category_id")
        entry["name"] = names[entry["category"]]
    by_project = _signed(
        transactions.values("project_id", "kind").annotate(total=Sum("amount")),
        "project_id",
    )
    for entry in by_project:
        entry["project"] = entry.pop("project_id")
    by_month = _signed(
        transactions.annotate(month=TruncMonth("date"))
        .values("month", "kind")
        .annotate(total=Sum("amount")),
        "month",
    )
    to_pay = transactions.filter(
        payment_status=Transaction.PaymentStatus.TO_PAY
    ).aggregate(total=Sum("amount"), n=Count("id"))
    to_reimburse = transactions.to_reimburse().aggregate(
        total=Sum("amount"), n=Count("id")
    )
    return {
        "expense": expense,
        "income": income,
        "balance": income - expense,
        "count": transactions.count(),
        "needs_receipt": transactions.needing_receipt().count(),
        "to_pay": {"total": to_pay["total"] or ZERO, "count": to_pay["n"]},
        "to_reimburse": {
            "total": to_reimburse["total"] or ZERO,
            "count": to_reimburse["n"],
        },
        "by_category": sorted(by_category, key=lambda e: e["name"].lower()),
        "by_project": by_project,
        "by_month": sorted(by_month, key=lambda e: e["month"]),
    }


# --- Budget ---------------------------------------------------------------------------


def budget(project: Project, transactions, lines, readable_ids: set[int]) -> dict:
    """Planned versus actual for `project`, own and with its sub-projects.

    `transactions` and `lines` are rights-limited querysets; `readable_ids`
    the projects the user may see money of. Sub-projects the user cannot see
    simply do not count: their money is not theirs to know.
    """
    branch = [p.pk for p in tree.subtree(project) if p.pk in readable_ids]
    planned: dict = defaultdict(lambda: {"own": ZERO, "with_children": ZERO})
    actual: dict = defaultdict(lambda: {"own": ZERO, "with_children": ZERO})
    names: dict[int, str] = {}
    for line in lines.filter(project_id__in=branch).select_related("category"):
        key = (line.category_id, line.kind)
        names[line.category_id] = line.category.name
        planned[key]["with_children"] += line.amount
        if line.project_id == project.pk:
            planned[key]["own"] += line.amount
    rows = (
        transactions.filter(project_id__in=branch)
        .values("project_id", "category_id", "category__name", "kind")
        .annotate(total=Sum("amount"))
    )
    for row in rows:
        key = (row["category_id"], row["kind"])
        names[row["category_id"]] = row["category__name"]
        actual[key]["with_children"] += row["total"]
        if row["project_id"] == project.pk:
            actual[key]["own"] += row["total"]

    entries = []
    for category_id, kind in sorted(
        set(planned) | set(actual), key=lambda k: (k[1], names[k[0]].lower())
    ):
        entries.append(
            {
                "category": category_id,
                "name": names[category_id],
                "kind": kind,
                "planned": planned[(category_id, kind)]["own"],
                "actual": actual[(category_id, kind)]["own"],
                "planned_with_children": planned[(category_id, kind)]["with_children"],
                "actual_with_children": actual[(category_id, kind)]["with_children"],
            }
        )

    def total(kind, field):
        return sum((e[field] for e in entries if e["kind"] == kind), ZERO)

    totals = {
        scope: {
            "planned_expense": total(Kind.EXPENSE, f"planned{suffix}"),
            "actual_expense": total(Kind.EXPENSE, f"actual{suffix}"),
            "planned_income": total(Kind.INCOME, f"planned{suffix}"),
            "actual_income": total(Kind.INCOME, f"actual{suffix}"),
        }
        for scope, suffix in (("own", ""), ("with_children", "_with_children"))
    }
    return {"lines": entries, "totals": totals}


# --- Expense advances: who owes what to whom ------------------------------------------


def advances(transactions) -> list[dict]:
    """Open advances grouped by payer, then by root project (SPEC §13)."""
    roots: dict[int, Project] = {}

    def root_of(project: Project) -> Project:
        if project.pk not in roots:
            chain = tree.ancestors(project)
            roots[project.pk] = chain[0] if chain else project
        return roots[project.pk]

    people: dict = {}
    for item in (
        transactions.to_reimburse()
        .select_related("project", "paid_by_user", "paid_by_contact")
        .order_by("date", "id")
    ):
        if item.paid_by_user_id:
            key = ("user", item.paid_by_user_id)
            name = item.paid_by_user.display_name
        elif item.paid_by_contact_id:
            key = ("contact", item.paid_by_contact_id)
            name = item.paid_by_contact.display_name
        else:
            key, name = ("unknown", 0), "Payeur non renseigné"
        person = people.setdefault(
            key,
            {
                "payer_type": key[0],
                "payer_id": key[1],
                "payer_name": name,
                "total": ZERO,
                "projects": {},
            },
        )
        root = root_of(item.project)
        entry = person["projects"].setdefault(
            root.pk,
            {
                "project": root.pk,
                "project_name": root.name,
                "project_color": root.color,
                "total": ZERO,
                "transactions": [],
            },
        )
        entry["total"] += item.amount
        entry["transactions"].append(item.pk)
        person["total"] += item.amount
    result = []
    for person in people.values():
        person["projects"] = sorted(
            person["projects"].values(), key=lambda p: p["project_name"].lower()
        )
        result.append(person)
    return sorted(result, key=lambda p: p["payer_name"].lower())


# --- Recurring expenses ---------------------------------------------------------------


def period_key(expense: RecurringExpense, today: date) -> str:
    if expense.frequency == RecurringExpense.Frequency.MONTHLY:
        return f"{today.year:04d}-{today.month:02d}"
    return f"{today.year:04d}"


def due_date(expense: RecurringExpense, today: date) -> date:
    """The day of the current period the expense falls on (day 31 -> last
    day of the month; 29 February -> 28 on a common year)."""
    month = (
        today.month
        if expense.frequency == RecurringExpense.Frequency.MONTHLY
        else expense.month
    )
    last = calendar.monthrange(today.year, month)[1]
    return date(today.year, month, min(expense.day, last))


def next_period_start(expense: RecurringExpense, today: date) -> date:
    """First day of the period after the one containing `today`."""
    if expense.frequency == RecurringExpense.Frequency.MONTHLY:
        year, month = (
            (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        )
        return date(year, month, 1)
    return date(today.year + 1, 1, 1)


def generate_due(today: date | None = None) -> int:
    """Nightly (Celery beat): create this period's transaction of every active
    recurring expense whose day is reached. Idempotent thanks to the unique
    (recurring_expense, period_key)."""
    today = today or date.today()
    created = 0
    for expense in RecurringExpense.objects.filter(is_active=True).select_related(
        "project"
    ):
        due = due_date(expense, today)
        if due > today or due < expense.start_date:
            continue
        if expense.end_date and due > expense.end_date:
            continue
        key = period_key(expense, today)
        if Transaction.objects.filter(
            recurring_expense=expense, period_key=key
        ).exists():
            continue
        with db_transaction.atomic():
            Transaction.objects.create(
                project=expense.project,
                kind=Kind.EXPENSE,
                amount=expense.amount,
                date=due,
                category=expense.category,
                label=expense.label,
                vendor=expense.vendor,
                payment_status=Transaction.PaymentStatus.TO_PAY,
                recurring_expense=expense,
                period_key=key,
                created_by=expense.created_by,
            )
        created += 1
    return created


# --- Budget lines helper --------------------------------------------------------------


def upsert_budget_line(project, category, kind, amount) -> BudgetLine:
    line, _ = BudgetLine.objects.update_or_create(
        project=project, category=category, kind=kind, defaults={"amount": amount}
    )
    return line
