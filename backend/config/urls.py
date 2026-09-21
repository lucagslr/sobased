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
    path("api/", include("apps.projects.urls")),
]
