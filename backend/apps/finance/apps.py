from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """Bookkeeping in CHF: categories, transactions, receipts, expense
    advances, recurring expenses, budgets, exports (SPEC §13)."""

    name = "apps.finance"

    def ready(self):
        from . import signals  # noqa: F401  (connects the receivers)
