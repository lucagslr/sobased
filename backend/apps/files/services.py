"""Asset rules that do not depend on who is asking: creating versions,
changing statuses, following."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import sniff
from .models import Asset, AssetStatusChange, AssetVersion, Kind, Status


class UploadTooLarge(ValueError):
    pass


def check_size(upload) -> None:
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    if upload.size > limit:
        raise UploadTooLarge(f"Fichier trop lourd ({settings.MAX_UPLOAD_MB} Mo max).")


@transaction.atomic
def add_version(
    asset: Asset, upload, author, label: str = "", note: str = ""
) -> AssetVersion:
    """Store `upload` as the next version of `asset`. The number is taken
    under a row lock so that two simultaneous uploads never collide."""
    check_size(upload)
    locked = Asset.objects.select_for_update().get(pk=asset.pk)
    last = locked.versions.aggregate(top=Max("number"))["top"] or 0
    sniffed = sniff.sniff(upload)
    version = AssetVersion(
        asset=locked,
        number=last + 1,
        label=label[:120],
        note=note,
        original_filename=(upload.name or "")[:255],
        size_bytes=upload.size,
        mime_type=sniffed.mime_type,
        author=author,
    )
    version.file.save(upload.name or "file", upload, save=False)
    version.save()
    # The asset's kind follows its first file (editable afterwards).
    if last == 0 and locked.kind == Kind.OTHER and sniffed.kind != Kind.OTHER:
        locked.kind = sniffed.kind
    locked.followers.add(author)
    locked.save(update_fields=["kind", "updated_at"])
    from .tasks import process_version  # imported here: tasks import models

    transaction.on_commit(lambda: process_version.delay(version.pk))
    return version


@transaction.atomic
def change_status(
    asset: Asset, to_status: str, actor, note: str = ""
) -> AssetStatusChange:
    """Free transitions for editors (SPECIFICATIONS §5), every one recorded."""
    if to_status not in Status.values:
        raise ValueError("Statut inconnu.")
    change = AssetStatusChange.objects.create(
        asset=asset,
        from_status=asset.status,
        to_status=to_status,
        note=note,
        changed_by=actor,
    )
    asset.status = to_status
    asset.updated_at = timezone.now()
    asset.save(update_fields=["status", "updated_at"])
    asset.followers.add(actor)
    # Notifications to the followers arrive with phase 12 (in-app bell).
    return change
