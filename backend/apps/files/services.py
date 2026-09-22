"""Asset rules that do not depend on who is asking: creating versions,
changing statuses, following."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.integrations import drive
from apps.integrations.drive import DriveUnavailable
from apps.integrations.google import DriveClient, GoogleError

from . import sniff
from .models import Asset, AssetStatusChange, AssetVersion, Kind, Status

# What a Drive operation may raise: the views turn them into a 400.
DriveProblem = (DriveUnavailable, GoogleError)


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


def add_drive_version(
    asset: Asset, file_id: str, author, label: str = "", note: str = ""
) -> AssetVersion:
    """A version that lives on Google Drive (SPEC §9: "fichier stocké sur le
    serveur OU référence Drive"). Its metadata is read with the author's
    Google account, which the Picker just granted for that file."""
    account = drive.drive_account(author)
    if account is None:
        raise DriveUnavailable("Connecte Google Drive pour attacher un fichier.")
    # Google first, outside any transaction: a refusal must keep its mark
    # (needs_reauth) even though nothing else is written.
    data = DriveClient(account).get_file(file_id)
    with transaction.atomic():
        return _store_drive_version(asset, file_id, data, account, author, label, note)


def _store_drive_version(asset, file_id, data, account, author, label, note):
    locked = Asset.objects.select_for_update().get(pk=asset.pk)
    last = locked.versions.aggregate(top=Max("number"))["top"] or 0
    mime = data.get("mimeType", "")
    version = AssetVersion.objects.create(
        asset=locked,
        number=last + 1,
        label=label[:120],
        note=note,
        original_filename=(data.get("name") or "")[:255],
        size_bytes=int(data["size"]) if data.get("size") else 0,
        mime_type=mime[:120],
        drive_file_id=file_id,
        drive_meta={**drive.file_summary(data), "account_id": account.pk},
        author=author,
    )
    if last == 0 and locked.kind == Kind.OTHER:
        locked.kind = sniff.kind_of_mime(mime) or Kind.OTHER
    locked.followers.add(author)
    locked.save(update_fields=["kind", "updated_at"])
    return version


def import_from_drive(version: AssetVersion, actor) -> AssetVersion:
    """Copy the Drive file into the internal storage: the version becomes a
    normal one (streamable, shareable by link). The Drive reference stays in
    drive_meta for the record."""
    from apps.integrations.models import OAuthAccount

    if not version.is_drive:
        raise ValueError("Cette version n'est pas une référence Drive.")
    account_id = (version.drive_meta or {}).get("account_id")
    account = OAuthAccount.objects.filter(pk=account_id).first() or drive.drive_account(
        actor
    )
    if account is None or not account.usable:
        raise DriveUnavailable(
            "Aucun compte Google connecté ne peut lire ce fichier Drive."
        )
    response = DriveClient(account).download(version.drive_file_id)
    from django.core.files.base import ContentFile

    content = ContentFile(response.content)
    check_size(content)
    with transaction.atomic():
        return _store_imported(version, content)


def _store_imported(version: AssetVersion, content) -> AssetVersion:
    name = version.original_filename or "fichier"
    version.file.save(name, content, save=False)
    version.size_bytes = content.size
    sniffed = sniff.sniff(version.file)
    version.mime_type = sniffed.mime_type
    version.drive_file_id = ""
    version.processed_at = None
    version.save()
    from .tasks import process_version

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
    from apps.notifications import services as notifications

    notifications.asset_status_changed(asset, change, actor)
    return change
