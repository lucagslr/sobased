from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("categories", views.CategoryViewSet, basename="category")
router.register("transactions", views.TransactionViewSet, basename="transaction")
router.register("budget-lines", views.BudgetLineViewSet, basename="budget-line")
router.register(
    "recurring-expenses", views.RecurringExpenseViewSet, basename="recurring-expense"
)

urlpatterns = [
    path(
        "finance/summary/", views.FinanceSummaryView.as_view(), name="finance-summary"
    ),
    path("finance/budget/", views.FinanceBudgetView.as_view(), name="finance-budget"),
    path(
        "finance/advances/",
        views.FinanceAdvancesView.as_view(),
        name="finance-advances",
    ),
    path("finance/export.xlsx", views.ExportXlsxView.as_view(), name="finance-xlsx"),
    path("finance/export.pdf", views.ExportPdfView.as_view(), name="finance-pdf"),
    path(
        "finance/export-receipts.zip",
        views.ExportReceiptsView.as_view(),
        name="finance-receipts-zip",
    ),
    *router.urls,
]
