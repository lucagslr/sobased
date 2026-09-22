from django.apps import AppConfig


class SharingConfig(AppConfig):
    """Protected share links (SPEC §10): public page, watermarks, access log."""

    name = "apps.sharing"
