from django.apps import AppConfig


class ActivityConfig(AppConfig):
    """The activity journal: who did what, when, on which object
    (SPEC §14, SPECIFICATIONS §11). Written explicitly by the views."""

    name = "apps.activity"
