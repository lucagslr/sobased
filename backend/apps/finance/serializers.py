from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer
from apps.contacts.models import Contact
from apps.events.models import Event
from apps.projects.access import member_user_ids
from apps.projects.models import Project
from apps.workspaces.models import Workspace

from .models import (
    DISPLAY_STATUS_CHOICES,
    BudgetLine,
    Category,
    Kind,
    RecurringExpense,
    Transaction,
)

User = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    workspace = serializers.PrimaryKeyRelatedField(queryset=Workspace.objects.all())

    class Meta:
        model = Category
        fields = ["id", "workspace", "name", "position"]

    def validate(self, attrs):
        workspace = attrs.get("workspace") or self.instance.workspace
        name = attrs.get("name", getattr(self.instance, "name", ""))
        clash = Category.objects.filter(workspace=workspace, name__iexact=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
            attrs.pop("workspace", None)  # a category never changes workspace
        if clash.exists():
            raise serializers.ValidationError({"name": "Cette catégorie existe déjà."})
        return attrs


class PayerSerializer(serializers.Serializer):
    """Who advanced the money: a user (by username) or a contact."""

    type = serializers.ChoiceField(choices=["user", "contact"])
    id = serializers.IntegerField(help_text="Contact id (users have none)")
    username = serializers.CharField(allow_null=True)
    name = serializers.CharField()


class TransactionSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_color = serializers.CharField(source="project.color", read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source="category.name", read_only=True)
    contact = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(), required=False, allow_null=True
    )
    contact_name = serializers.SerializerMethodField()
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.all(), required=False, allow_null=True
    )
    event_title = serializers.SerializerMethodField()
    # Write: who paid. Read: `payer`.
    paid_by_username = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    paid_by_contact = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(), required=False, allow_null=True
    )
    payer = serializers.SerializerMethodField()
    # Receipt: uploaded through multipart; read as metadata + URL.
    receipt = serializers.FileField(write_only=True, required=False, allow_null=True)
    has_receipt = serializers.SerializerMethodField()
    receipt_url = serializers.SerializerMethodField()
    needs_receipt = serializers.BooleanField(read_only=True)
    is_to_reimburse = serializers.BooleanField(read_only=True)
    display_status = serializers.SerializerMethodField()
    created_by = PublicUserSerializer(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "project",
            "project_name",
            "project_color",
            "kind",
            "amount",
            "date",
            "category",
            "category_name",
            "label",
            "vendor",
            "contact",
            "contact_name",
            "event",
            "event_title",
            "receipt",
            "has_receipt",
            "receipt_name",
            "receipt_content_type",
            "receipt_url",
            "payment_status",
            "paid_by_username",
            "paid_by_contact",
            "payer",
            "to_reimburse",
            "reimbursed_on",
            "recurring_expense",
            "period_key",
            "needs_receipt",
            "is_to_reimburse",
            "display_status",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "receipt_name",
            "receipt_content_type",
            "recurring_expense",
            "period_key",
            "created_at",
            "updated_at",
        ]

    # --- Computed fields -------------------------------------------------------------
    def get_contact_name(self, item) -> str | None:
        return item.contact.display_name if item.contact_id else None

    def get_event_title(self, item) -> str | None:
        return item.event.title if item.event_id else None

    @extend_schema_field(PayerSerializer(allow_null=True))
    def get_payer(self, item) -> dict | None:
        if item.paid_by_user_id:
            user = item.paid_by_user
            return {
                "type": "user",
                "id": 0,
                "username": user.username,
                "name": user.display_name,
            }
        if item.paid_by_contact_id:
            contact = item.paid_by_contact
            return {
                "type": "contact",
                "id": contact.pk,
                "username": None,
                "name": contact.display_name,
            }
        return None

    def get_has_receipt(self, item) -> bool:
        return bool(item.receipt)

    def get_receipt_url(self, item) -> str | None:
        return f"/api/transactions/{item.pk}/receipt/" if item.receipt else None

    @extend_schema_field(serializers.ChoiceField(choices=DISPLAY_STATUS_CHOICES))
    def get_display_status(self, item) -> str:
        return item.display_status

    # --- Validation ------------------------------------------------------------------
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à 0.")
        return value

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("project", None)  # a transaction never changes project
        project = attrs.get("project") or self.instance.project
        access_map = self.context["access_map"]
        visible = set(access_map.project_ids())

        category = attrs.get("category")
        if category is not None and category.workspace_id != project.workspace_id:
            raise serializers.ValidationError(
                {"category": "Cette catégorie n'est pas de cet espace."}
            )

        contact = attrs.get("contact")
        if contact is not None and not (
            contact.workspace_id == project.workspace_id
            and Contact.objects.for_user(self.context["request"])
            .filter(pk=contact.pk)
            .exists()
        ):
            raise serializers.ValidationError({"contact": "Contact introuvable."})

        event = attrs.get("event")
        if event is not None and (
            event.project_id not in visible
            or event.project.workspace_id != project.workspace_id
        ):
            raise serializers.ValidationError({"event": "RDV introuvable."})

        # Who paid: a project member (by username) or a contact, never both.
        if "paid_by_username" in attrs:
            username = (attrs.pop("paid_by_username") or "").lstrip("@").strip()
            if username:
                members = User.objects.filter(
                    pk__in=member_user_ids(project), is_active=True
                )
                user = next(
                    (u for u in members if u.username.lower() == username.lower()),
                    None,
                )
                if user is None:
                    raise serializers.ValidationError(
                        {"paid_by_username": "Ce membre est introuvable."}
                    )
                attrs["paid_by_user"] = user
                attrs["paid_by_contact"] = None
            else:
                attrs["paid_by_user"] = None
        payer_contact = attrs.get("paid_by_contact")
        if payer_contact is not None:
            if not Contact.objects.for_user(self.context["request"]).filter(
                pk=payer_contact.pk, workspace_id=project.workspace_id
            ):
                raise serializers.ValidationError(
                    {"paid_by_contact": "Contact introuvable."}
                )
            attrs["paid_by_user"] = None

        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        if kind == Kind.INCOME:
            # An income has no receipt to justify, nobody advanced it.
            attrs["to_reimburse"] = False
            attrs["reimbursed_on"] = None
            attrs["paid_by_user"] = None
            attrs["paid_by_contact"] = None
        if attrs.get("reimbursed_on") and not attrs.get(
            "to_reimburse", getattr(self.instance, "to_reimburse", False)
        ):
            raise serializers.ValidationError(
                {"reimbursed_on": "Cette dépense n'est pas une avance à rembourser."}
            )
        return attrs


class TransactionRowSerializer(TransactionSerializer):
    """Documentation of the list rows (same shape as the detail)."""


class RecurringExpenseSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_color = serializers.CharField(source="project.color", read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source="category.name", read_only=True)
    next_due = serializers.SerializerMethodField()

    class Meta:
        model = RecurringExpense
        fields = [
            "id",
            "project",
            "project_name",
            "project_color",
            "label",
            "amount",
            "category",
            "category_name",
            "vendor",
            "frequency",
            "day",
            "month",
            "start_date",
            "end_date",
            "is_active",
            "next_due",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_next_due(self, expense) -> str | None:
        return self.context.get("next_due", lambda e: None)(expense)

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("project", None)
        project = attrs.get("project") or self.instance.project
        category = attrs.get("category")
        if category is not None and category.workspace_id != project.workspace_id:
            raise serializers.ValidationError(
                {"category": "Cette catégorie n'est pas de cet espace."}
            )
        day = attrs.get("day", getattr(self.instance, "day", 1))
        month = attrs.get("month", getattr(self.instance, "month", 1))
        if not 1 <= day <= 31:
            raise serializers.ValidationError({"day": "Le jour va de 1 à 31."})
        if not 1 <= month <= 12:
            raise serializers.ValidationError({"month": "Le mois va de 1 à 12."})
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "La fin ne peut pas précéder le début."}
            )
        return attrs


class BudgetLineSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = BudgetLine
        fields = ["id", "project", "category", "category_name", "kind", "amount"]
        read_only_fields = ["id"]
        # No UniqueTogetherValidator: posting an existing line updates it.
        validators: list = []

    def validate(self, attrs):
        if self.instance is not None:
            for key in ("project", "category", "kind"):
                attrs.pop(key, None)
            return attrs
        project, category = attrs["project"], attrs["category"]
        if category.workspace_id != project.workspace_id:
            raise serializers.ValidationError(
                {"category": "Cette catégorie n'est pas de cet espace."}
            )
        return attrs


# --- Read-only shapes (documentation of the aggregations) ---------------------------


class MoneyByKeySerializer(serializers.Serializer):
    expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)


class CategoryTotalSerializer(MoneyByKeySerializer):
    category = serializers.IntegerField()
    name = serializers.CharField()


class ProjectTotalSerializer(MoneyByKeySerializer):
    project = serializers.IntegerField()


class MonthTotalSerializer(MoneyByKeySerializer):
    month = serializers.DateField(help_text="First day of the month")


class CountedTotalSerializer(serializers.Serializer):
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    count = serializers.IntegerField()


class FinanceSummarySerializer(serializers.Serializer):
    expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    count = serializers.IntegerField()
    needs_receipt = serializers.IntegerField()
    to_pay = CountedTotalSerializer()
    to_reimburse = CountedTotalSerializer()
    by_category = CategoryTotalSerializer(many=True)
    by_project = ProjectTotalSerializer(many=True)
    by_month = MonthTotalSerializer(many=True)


class BudgetEntrySerializer(serializers.Serializer):
    category = serializers.IntegerField()
    name = serializers.CharField()
    kind = serializers.ChoiceField(choices=Kind.choices)
    planned = serializers.DecimalField(max_digits=14, decimal_places=2)
    actual = serializers.DecimalField(max_digits=14, decimal_places=2)
    planned_with_children = serializers.DecimalField(max_digits=14, decimal_places=2)
    actual_with_children = serializers.DecimalField(max_digits=14, decimal_places=2)


class BudgetTotalsSerializer(serializers.Serializer):
    planned_expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    actual_expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    planned_income = serializers.DecimalField(max_digits=14, decimal_places=2)
    actual_income = serializers.DecimalField(max_digits=14, decimal_places=2)


class BudgetScopesSerializer(serializers.Serializer):
    own = BudgetTotalsSerializer()
    with_children = BudgetTotalsSerializer()


class BudgetSerializer(serializers.Serializer):
    lines = BudgetEntrySerializer(many=True)
    totals = BudgetScopesSerializer()


class AdvanceProjectSerializer(serializers.Serializer):
    project = serializers.IntegerField()
    project_name = serializers.CharField()
    project_color = serializers.CharField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    transactions = serializers.ListField(child=serializers.IntegerField())


class AdvanceSerializer(serializers.Serializer):
    payer_type = serializers.ChoiceField(choices=["user", "contact", "unknown"])
    payer_id = serializers.IntegerField()
    payer_name = serializers.CharField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    projects = AdvanceProjectSerializer(many=True)


class MarkReimbursedSerializer(serializers.Serializer):
    reimbursed_on = serializers.DateField(required=False)
    # Bulk: every open advance of a payer on a root project (« tout le solde »).
    transactions = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )
