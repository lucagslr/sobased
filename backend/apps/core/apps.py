from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Shared utilities used by every other app. No business models here."""

    name = "apps.core"

    def ready(self):
        # Registers the OpenAPI extension (import side effect).
        from . import schema  # noqa: F401
