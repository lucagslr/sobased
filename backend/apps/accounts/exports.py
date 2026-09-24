"""Building "my data" (SPEC §16, SPECIFICATIONS §11): a ZIP with JSON files
and the files the user deposited.

Contents: profile.json, memberships.json, tasks.json (created by me or
assigned to me), comments.json (task and file comments), events.json
(created by me), transactions.json (entered by me), the versions I uploaded
under fichiers/, the receipts I attached under justificatifs/, my avatar.
Everything is read through the storage API, so it works with S3 too.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import timedelta
from tempfile import NamedTemporaryFile

from django.core.files import File
from django.utils import timezone

from apps.events.models import Event
from apps.files.models import AssetComment, AssetVersion
from apps.finance.models import Transaction
from apps.projects.models import Membership
from apps.tasks.models import Task, TaskComment

from .models import DataExport

EXPORT_LIFETIME = timedelta(days=7)

README = """Export de tes données Faiblegraine

profile.json        ton profil et tes préférences
memberships.json    tes accès aux espaces et projets
tasks.json          les tâches que tu as créées ou qui te sont assignées
comments.json       tes commentaires (tâches et fichiers)
events.json         les RDV et événements que tu as créés
transactions.json   les écritures compta que tu as saisies
fichiers/           les versions de fichiers que tu as déposées
justificatifs/      les justificatifs que tu as joints
avatar.*            ta photo de profil

Les dates sont en UTC (ISO 8601).
"""


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _safe(name: str) -> str:
    keep = "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()
    return keep[:80] or "fichier"


def profile(user) -> dict:
    return {
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "timezone": user.timezone,
        "theme": user.theme,
        "daily_digest_enabled": user.daily_digest_enabled,
        "daily_digest_time": user.daily_digest_time,
        "email_on_mention": user.email_on_mention,
        "email_on_assignment": user.email_on_assignment,
        "email_verified_at": user.email_verified_at,
        "privacy_accepted_at": user.privacy_accepted_at,
        "date_joined": user.date_joined,
    }


def memberships(user) -> list[dict]:
    rows = Membership.objects.filter(user=user).select_related("workspace", "project")
    return [
        {
            "scope_type": "workspace" if m.workspace_id else "project",
            "scope_name": m.scope.name,
            "role": m.role,
            "can_view_finance": m.can_view_finance,
            "can_edit_finance": m.can_edit_finance,
            "since": m.created_at,
        }
        for m in rows
    ]


def tasks(user) -> list[dict]:
    rows = Task.objects.filter(created_by=user) | Task.objects.filter(assignees=user)
    return [
        {
            "id": t.pk,
            "project": t.project.name,
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "start_at": t.start_at,
            "due_at": t.due_at,
            "all_day": t.all_day,
            "assignees": sorted(u.username for u in t.assignees.all()),
            "created_by_me": t.created_by_id == user.pk,
            "created_at": t.created_at,
        }
        for t in rows.distinct().select_related("project").prefetch_related("assignees")
    ]


def comments(user) -> list[dict]:
    on_tasks = TaskComment.objects.filter(author=user).select_related("task__project")
    on_files = AssetComment.objects.filter(author=user).select_related(
        "version__asset__project"
    )
    return [
        {
            "kind": "task",
            "project": c.task.project.name,
            "about": c.task.title,
            "body": c.body,
            "created_at": c.created_at,
        }
        for c in on_tasks
    ] + [
        {
            "kind": "file",
            "project": c.version.asset.project.name,
            "about": f"{c.version.asset.name} · v{c.version.number}",
            "body": c.body,
            "created_at": c.created_at,
        }
        for c in on_files
    ]


def events(user) -> list[dict]:
    rows = Event.objects.filter(created_by=user).select_related("project")
    return [
        {
            "id": e.pk,
            "project": e.project.name,
            "type": e.type,
            "title": e.title,
            "start": e.start,
            "end": e.end,
            "all_day": e.all_day,
            "location": e.location,
            "prep_notes": e.prep_notes,
            "report": e.report,
            "decisions": e.decisions,
            "created_at": e.created_at,
        }
        for e in rows
    ]


def transactions(user) -> list[dict]:
    rows = Transaction.objects.filter(created_by=user).select_related(
        "project", "category"
    )
    return [
        {
            "id": t.pk,
            "project": t.project.name,
            "kind": t.kind,
            "date": t.date,
            "label": t.label,
            "amount": t.amount,
            "category": t.category.name if t.category_id else None,
            "vendor": t.vendor,
            "payment_status": t.payment_status,
            "has_receipt": bool(t.receipt),
            "created_at": t.created_at,
        }
        for t in rows
    ]


def _copy(archive: zipfile.ZipFile, field_file, name: str) -> None:
    with field_file.open("rb") as source, archive.open(name, "w") as target:
        shutil.copyfileobj(source, target)


def write_archive(user, target) -> None:
    """Write the ZIP of `user` to the writable binary file `target`."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("LISEZMOI.txt", README)
        archive.writestr("profile.json", _dump(profile(user)))
        archive.writestr("memberships.json", _dump(memberships(user)))
        archive.writestr("tasks.json", _dump(tasks(user)))
        archive.writestr("comments.json", _dump(comments(user)))
        archive.writestr("events.json", _dump(events(user)))
        archive.writestr("transactions.json", _dump(transactions(user)))
        versions = (
            AssetVersion.objects.filter(author=user)
            .exclude(file="")
            .select_related("asset")
        )
        for version in versions:
            base = version.original_filename or version.asset.name
            _copy(
                archive,
                version.file,
                f"fichiers/{version.asset_id}-v{version.number}-{_safe(base)}",
            )
        receipts = Transaction.objects.filter(created_by=user).exclude(receipt="")
        for tx in receipts:
            extension = tx.receipt.name.rsplit(".", 1)[-1]
            _copy(archive, tx.receipt, f"justificatifs/{tx.date}-{tx.pk}.{extension}")
        if user.avatar:
            _copy(archive, user.avatar, f"avatar.{user.avatar.name.rsplit('.', 1)[-1]}")


def build(export: DataExport) -> None:
    """Fill `export` (status, archive, expiry); errors are recorded on it."""
    with NamedTemporaryFile(suffix=".zip") as tmp:
        try:
            write_archive(export.user, tmp)
        except Exception as exc:  # noqa: BLE001 - reported to the user
            export.status = DataExport.Status.FAILED
            export.error = str(exc)[:200]
            export.save(update_fields=["status", "error"])
            return
        tmp.flush()
        export.size_bytes = tmp.tell()
        tmp.seek(0)
        export.archive.save("export.zip", File(tmp), save=False)
    export.status = DataExport.Status.READY
    export.expires_at = timezone.now() + EXPORT_LIFETIME
    export.error = ""
    export.save()
