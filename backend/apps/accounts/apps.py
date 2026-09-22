from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Users: sign-up, login, password reset, profile, preferences, search,
    data export and account deletion."""

    name = "apps.accounts"

    def ready(self):
        from . import signals  # noqa: F401  (connects the receivers)
