from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("drive-links", views.DriveLinkViewSet, basename="drive-link")
router.register("projects", views.ProjectDriveViewSet, basename="project-drive")

urlpatterns = router.urls + [
    path("integrations/", views.IntegrationsStateView.as_view(), name="integrations"),
    path(
        "integrations/google/connect/",
        views.GoogleConnectView.as_view(),
        name="google-connect",
    ),
    path(
        "integrations/google/callback/",
        views.GoogleCallbackView.as_view(),
        name="google-callback",
    ),
    path(
        "integrations/google/",
        views.GoogleDisconnectView.as_view(),
        name="google-disconnect",
    ),
    path(
        "integrations/google/picker-config/",
        views.PickerConfigView.as_view(),
        name="google-picker-config",
    ),
]
