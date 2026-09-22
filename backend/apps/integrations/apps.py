from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    """External accounts (Google, Microsoft), Drive folders and links
    (SPEC §11), calendar sync (SPEC §12, phase 11)."""

    name = "apps.integrations"
