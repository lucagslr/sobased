"""Writing the journal.

`log()` is the single writer; `snapshot()` / `diff()` turn the key fields of
an object into the `changes` of an "updated" entry. Values are stored in a
form the front can display without knowing the model: strings, numbers,
booleans, ISO dates, names of related objects, lists of names for
many-to-many fields, `true` / `false` for the presence of a file.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db import models
from django.db.models.fields.files import FieldFile
from django.utils import timezone

from .models import ActivityEntry, Verb

RETENTION_DAYS = 365


def _serialise(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, FieldFile):
        return bool(value)
    if isinstance(value, models.Manager):  # many-to-many: the names, sorted
        return sorted(_serialise(item) for item in value.all())
    if isinstance(value, models.Model):
        for attr in ("display_name", "name", "title"):
            label = getattr(value, attr, None)
            if label:
                return str(label)
        return str(value)
    return str(value)


def snapshot(obj, fields) -> dict:
    """The key fields of `obj`, serialised."""
    return {field: _serialise(getattr(obj, field)) for field in fields}


def diff(before: dict, after: dict) -> dict:
    """{field: [old, new]} for the fields that changed."""
    return {
        field: [before.get(field), value]
        for field, value in after.items()
        if before.get(field) != value
    }


def label_of(obj) -> str:
    for attr in ("title", "name", "label", "display_name"):
        value = getattr(obj, attr, None)
        if value:
            return str(value)[:240]
    return str(obj)[:240]


def log(
    actor,
    verb: str,
    target=None,
    *,
    target_type: str = "",
    target_id: int | None = None,
    label: str = "",
    project=None,
    workspace=None,
    changes: dict | None = None,
) -> ActivityEntry:
    """One row. `target` fills type, id and label unless given explicitly;
    the project comes from the target (`.project`) unless given, and the
    workspace from the project (or from the target for workspace objects)."""
    if target is not None:
        target_type = target_type or type(target).__name__.lower()
        target_id = target_id if target_id is not None else target.pk
        label = label or label_of(target)
        if project is None:
            project = getattr(target, "project", None)
    if workspace is None:
        workspace = (
            getattr(project, "workspace", None)
            if project is not None
            else getattr(target, "workspace", None)
        )
    if workspace is None:
        raise ValueError("An activity entry needs a workspace.")
    return ActivityEntry.objects.create(
        workspace=workspace,
        project=project,
        actor=actor if getattr(actor, "pk", None) else None,
        verb=verb,
        target_type=target_type,
        target_id=target_id,
        target_label=label[:240],
        changes=changes or {},
    )


def log_update(
    actor, target, before: dict, after: dict, **kwargs
) -> ActivityEntry | None:
    """An "updated" entry (or "status_changed" when `status` moved) with the
    fields that differ; nothing when nothing changed."""
    changes = diff(before, after)
    if not changes:
        return None
    verb = Verb.STATUS_CHANGED if "status" in changes else Verb.UPDATED
    return log(actor, verb, target, changes=changes, **kwargs)


def purge(days: int = RETENTION_DAYS) -> int:
    """SPEC §14: 12 months of retention."""
    limit = timezone.now() - dt.timedelta(days=days)
    deleted, _ = ActivityEntry.objects.filter(created_at__lt=limit).delete()
    return deleted
