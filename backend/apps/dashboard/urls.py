from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(
    "dashboard/views", views.DashboardViewViewSet, basename="dashboard-view"
)

urlpatterns = [
    path(
        "dashboard/summary/",
        views.DashboardSummaryView.as_view(),
        name="dashboard-summary",
    ),
    path(
        "projects/<int:pk>/overview/",
        views.ProjectOverviewView.as_view(),
        name="project-overview",
    ),
    *router.urls,
]
