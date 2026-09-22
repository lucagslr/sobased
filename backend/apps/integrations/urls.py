from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("drive-links", views.DriveLinkViewSet, basename="drive-link")
router.register("projects", views.ProjectDriveViewSet, basename="project-drive")
router.register(
    "integrations/calendars",
    views.ExternalCalendarViewSet,
    basename="external-calendar",
)

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
    path(
        "integrations/microsoft/connect/",
        views.MicrosoftConnectView.as_view(),
        name="microsoft-connect",
    ),
    path(
        "integrations/microsoft/callback/",
        views.MicrosoftCallbackView.as_view(),
        name="microsoft-callback",
    ),
    path(
        "integrations/microsoft/",
        views.MicrosoftDisconnectView.as_view(),
        name="microsoft-disconnect",
    ),
    path("integrations/sync-now/", views.SyncNowView.as_view(), name="sync-now"),
    path(
        "integrations/sync-conflicts/",
        views.SyncConflictsView.as_view(),
        name="sync-conflicts",
    ),
    path(
        "integrations/external-events/",
        views.ExternalEventsView.as_view(),
        name="external-events",
    ),
    path(
        "integrations/google/calendar/webhook/",
        views.GoogleCalendarWebhookView.as_view(),
        name="google-calendar-webhook",
    ),
]
