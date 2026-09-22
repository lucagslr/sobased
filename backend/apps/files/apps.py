from django.apps import AppConfig


class FilesConfig(AppConfig):
    """Assets and their versions (SPEC §9): uploads, derivatives, anchored
    comments, validation statuses."""

    name = "apps.files"

    def ready(self):
        from . import signals  # noqa: F401  (connects the receivers)
