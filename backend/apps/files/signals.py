"""Files on disk follow their rows: Django never deletes a FileField's file
by itself, so a cascade (asset, project, workspace) would leave originals
and derivatives behind."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import AssetDerivative, AssetVersion


@receiver(post_delete, sender=AssetVersion)
def delete_version_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


@receiver(post_delete, sender=AssetDerivative)
def delete_derivative_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
