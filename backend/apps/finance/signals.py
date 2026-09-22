"""Django never deletes a FileField's file by itself: a transaction removed
through a cascade (its project or workspace is deleted) would leave its
receipt on disk forever. This receiver cleans up after every deletion."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Transaction


@receiver(post_delete, sender=Transaction)
def delete_receipt_file(sender, instance, **kwargs):
    if instance.receipt:
        instance.receipt.delete(save=False)
