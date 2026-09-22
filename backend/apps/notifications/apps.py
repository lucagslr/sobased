from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """In-app notifications (the bell), their e-mails, the daily digest
    (SPEC §14, SPECIFICATIONS §10)."""

    name = "apps.notifications"
