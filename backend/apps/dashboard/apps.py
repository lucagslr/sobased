from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Read-only aggregations across apps (widgets, project overview) and the
    saved dashboard views. Sits on top of every other app (decision D1)."""

    name = "apps.dashboard"
