from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    """Project tree, memberships, invitations and the access-rights engine."""

    name = "apps.projects"

    def ready(self):
        from apps.accounts.signals import email_verified

        from .services import apply_pending_invitations

        def on_email_verified(sender, user, **kwargs):
            # Invitations sent to this address before it was verified.
            apply_pending_invitations(user)

        # dispatch_uid keeps the (closure) receiver alive and unique.
        email_verified.connect(
            on_email_verified, weak=False, dispatch_uid="projects.apply_invitations"
        )
