"""Root URL configuration. Every API route lives under /api/."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from apps.core.views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.workspaces.urls")),
    # Before apps.projects: /api/projects/cards/ would otherwise be read by the
    # projects router as the detail of a project whose id is "cards".
    path("api/", include("apps.dashboard.urls")),
    path("api/", include("apps.projects.urls")),
    path("api/", include("apps.tasks.urls")),
    path("api/", include("apps.contacts.urls")),
    path("api/", include("apps.events.urls")),
    path("api/", include("apps.finance.urls")),
    path("api/", include("apps.files.urls")),
    path("api/", include("apps.sharing.urls")),
    path("api/", include("apps.integrations.urls")),
]
