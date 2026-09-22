"""Signals other apps subscribe to, so that accounts never imports them,
and the receivers of this app (connected by AccountsConfig.ready)."""

from django.db.models.signals import post_delete
from django.dispatch import Signal, receiver

from .models import DataExport

# Sent with `user` once an e-mail address is proven to belong to the account.
email_verified = Signal()


@receiver(post_delete, sender=DataExport)
def delete_export_archive(sender, instance, **kwargs):
    """Purges and account deletions go through bulk deletes: the storage
    is cleaned here, never left to chance."""
    if instance.archive:
        instance.archive.delete(save=False)
