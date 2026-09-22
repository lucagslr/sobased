"""Two-way calendar sync (SPEC §12, SPECIFICATIONS §8).

Push (site → target calendar of a user): the events they take part in or
created, and the tasks assigned to them with a due date. Tasks become
"☐ Title" (30 minutes ending at the due time, or all-day), "☑ Title" once
done; cancelled or unassigned tasks are removed from the calendar.

Pull (external → site): for mapped objects, title and dates come back when
the user may change them (Editor on the project; an assignee may move the
date of their task); an external deletion only detaches the mapping. For
displayed calendars, other events are mirrored read-only (ExternalEvent).

Echoes: what was last pushed is fingerprinted; an incoming change with the
same fingerprint is ignored. Conflicts: both sides changed since the last
push → the most recent wins, the other values are kept in SyncConflict.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.events.models import Event
from apps.projects.access import Role, effective_access
from apps.tasks.models import Task

from .calendars import (
    CursorInvalid,
    ProviderError,
    feature_enabled,
    provider_for,
    window,
)
from .models import (
    ExternalCalendar,
    ExternalEvent,
    MappingState,
    OAuthAccount,
    SyncConflict,
    SyncMapping,
)

log = logging.getLogger(__name__)
TASK_SLOT = timedelta(minutes=30)
TODO, DONE = "☐ ", "☑ "


# --- What a local object looks like in a calendar -------------------------------------
def task_payload(task: Task) -> dict:
    prefix = DONE if task.status == "done" else TODO
    if task.all_day:
        start = end = task.due_at
    else:
        end = task.due_at
        start = end - TASK_SLOT
    return {
        "title": prefix + task.title,
        "start": start,
        "end": end,
        "all_day": task.all_day,
    }


def event_payload(event: Event) -> dict:
    return {
        "title": event.title,
        "start": event.start,
        "end": event.end,
        "all_day": event.all_day,
    }


def fingerprint(payload: dict) -> str:
    def iso(value):
        return (
            value.astimezone(UTC).isoformat() if isinstance(value, datetime) else value
        )

    canonical = {k: iso(payload.get(k)) for k in ("title", "start", "end", "all_day")}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def task_qualifies(task: Task, user) -> bool:
    return (
        task.due_at is not None
        and task.status != "cancelled"
        and task.assignees.filter(pk=user.pk).exists()
    )


def event_qualifies(event: Event, user) -> bool:
    return (
        event.created_by_id == user.pk or event.participants.filter(pk=user.pk).exists()
    )


def candidates(user) -> list[tuple[str, object]]:
    """The objects to push, inside the sync window."""
    start, end = window()
    tasks = (
        Task.objects.filter(assignees=user, due_at__range=(start, end))
        .exclude(status="cancelled")
        .distinct()
    )
    events = (
        Event.objects.filter(Q(participants=user) | Q(created_by=user))
        .filter(start__lte=end, end__gte=start)
        .distinct()
    )
    return [("task", t) for t in tasks] + [("event", e) for e in events]


def payload_for(kind: str, obj) -> dict:
    return task_payload(obj) if kind == "task" else event_payload(obj)


def load_object(kind: str, object_id: int):
    model = Task if kind == "task" else Event
    return model.objects.filter(pk=object_id).first()


# --- Push -----------------------------------------------------------------------------
def push(user, calendar: ExternalCalendar, provider) -> dict:
    stats = {"created": 0, "updated": 0, "deleted": 0}
    mappings = {(m.object_type, m.object_id): m for m in calendar.mappings.all()}
    seen: set[tuple[str, int]] = set()
    now = timezone.now()

    for kind, obj in candidates(user):
        key = (kind, obj.pk)
        seen.add(key)
        payload = payload_for(kind, obj)
        digest = fingerprint(payload)
        mapping = mappings.get(key)
        if mapping is None:
            result = provider.insert(calendar.external_id, payload)
            SyncMapping.objects.create(
                calendar=calendar,
                object_type=kind,
                object_id=obj.pk,
                external_id=result["id"],
                etag=result.get("etag", ""),
                pushed_hash=digest,
                pushed_at=now,
                external_updated_at=result.get("updated"),
            )
            stats["created"] += 1
        elif mapping.state == MappingState.ACTIVE and mapping.pushed_hash != digest:
            result = provider.update(calendar.external_id, mapping.external_id, payload)
            mapping.etag = result.get("etag", "")
            mapping.pushed_hash = digest
            mapping.pushed_at = now
            mapping.external_updated_at = result.get("updated")
            mapping.save()
            stats["updated"] += 1

    # Mapped objects that no longer belong in the calendar: gone, cancelled,
    # unassigned, no longer a participant.
    for key, mapping in mappings.items():
        if key in seen:
            continue
        obj = load_object(*key)
        keep = obj is not None and (
            task_qualifies(obj, user)
            if key[0] == "task"
            else event_qualifies(obj, user)
        )
        if keep:
            continue  # out of the window: left alone
        if mapping.state == MappingState.ACTIVE:
            provider.delete(calendar.external_id, mapping.external_id)
            stats["deleted"] += 1
        mapping.delete()
    return stats


# --- Pull -----------------------------------------------------------------------------
def _may_change(user, kind: str, obj) -> str:
    """ "all" (editor), "dates" (assignee of the task), or ""."""
    access = effective_access(user, obj.project)
    if access.has(Role.EDITOR):
        return "all"
    if kind == "task" and obj.assignees.filter(pk=user.pk).exists():
        return "dates"
    return ""


def _apply(kind: str, obj, item: dict, scope: str) -> None:
    if kind == "task":
        if scope == "all":
            title = item["title"]
            for prefix in (TODO, DONE):
                if title.startswith(prefix):
                    title = title[len(prefix) :]
            obj.title = title.strip() or obj.title
        obj.all_day = item["all_day"]
        obj.due_at = item["start"] if item["all_day"] else item["end"]
        if not item["all_day"] and obj.start_at and obj.start_at > obj.due_at:
            obj.start_at = None
        obj.save()
    else:
        if scope == "all":
            obj.title = item["title"].strip() or obj.title
        obj.all_day = item["all_day"]
        obj.start, obj.end = item["start"], max(item["end"], item["start"])
        obj.save()


def apply_incoming(mapping: SyncMapping, item: dict, user) -> None:
    if item["deleted"]:
        if mapping.state != MappingState.DETACHED:
            mapping.state = MappingState.DETACHED
            mapping.save(update_fields=["state", "updated_at"])
        return
    if mapping.state == MappingState.DETACHED or item["start"] is None:
        return
    incoming = fingerprint(item)
    if incoming == mapping.pushed_hash:
        # Our own echo (or an untouched event): remember the etag, that's all.
        if item.get("etag") and item["etag"] != mapping.etag:
            mapping.etag = item["etag"]
            mapping.save(update_fields=["etag", "updated_at"])
        return
    obj = load_object(mapping.object_type, mapping.object_id)
    if obj is None:
        return
    scope = _may_change(user, mapping.object_type, obj)
    if not scope:
        # No right: the local values win at the next push.
        mapping.pushed_hash = ""
        mapping.save(update_fields=["pushed_hash", "updated_at"])
        return
    local_payload = payload_for(mapping.object_type, obj)
    pushed_at = mapping.pushed_at or datetime.min.replace(tzinfo=UTC)
    local_changed = obj.updated_at > pushed_at + timedelta(seconds=1)
    external_changed = bool(item.get("updated")) and item["updated"] > pushed_at
    if local_changed and external_changed:
        local_wins = obj.updated_at >= item["updated"]
        SyncConflict.objects.create(
            mapping=mapping,
            winner="local" if local_wins else "external",
            details={
                "local": {k: str(v) for k, v in local_payload.items()},
                "external": {
                    k: str(item[k]) for k in ("title", "start", "end", "all_day")
                },
            },
        )
        if local_wins:
            mapping.pushed_hash = ""  # forces a push of the local values
            mapping.save(update_fields=["pushed_hash", "updated_at"])
            return
    _apply(mapping.object_type, obj, item, scope)
    obj.refresh_from_db()
    local_digest = fingerprint(payload_for(mapping.object_type, obj))
    # Partly refused (a viewer's title change) or renormalised (a task slot):
    # an empty fingerprint makes the next push put the calendar back in line.
    mapping.pushed_hash = local_digest if local_digest == incoming else ""
    mapping.etag = item.get("etag", "")
    mapping.external_updated_at = item.get("updated")
    mapping.pushed_at = timezone.now()
    mapping.save()


def upsert_external_event(calendar: ExternalCalendar, item: dict) -> None:
    if item["deleted"] or item["start"] is None or item["end"] is None:
        ExternalEvent.objects.filter(calendar=calendar, external_id=item["id"]).delete()
        return
    ExternalEvent.objects.update_or_create(
        calendar=calendar,
        external_id=item["id"],
        defaults={
            "title": item["title"][:300],
            "start": item["start"],
            "end": item["end"],
            "all_day": item["all_day"],
            "location": item["location"][:300],
            "etag": item.get("etag", ""),
        },
    )


def pull(calendar: ExternalCalendar, provider) -> int:
    try:
        items, cursor = provider.changes(calendar)
    except CursorInvalid:
        # Full read again: the mirrored events are rebuilt from scratch.
        calendar.sync_cursor = ""
        calendar.events.all().delete()
        items, cursor = provider.changes(calendar)
    mappings = {m.external_id: m for m in calendar.mappings.all()}
    user = calendar.account.user
    for item in items:
        mapping = mappings.get(item["id"])
        if mapping is not None:
            apply_incoming(mapping, item, user)
        elif calendar.is_displayed:
            upsert_external_event(calendar, item)
    calendar.sync_cursor = cursor
    return len(items)


# --- Entry points ---------------------------------------------------------------------
def sync_account(account: OAuthAccount) -> dict:
    """One account: push to its target calendar, pull its displayed ones."""
    stats = {"pushed": {}, "pulled": 0, "errors": []}
    if not account.usable or not feature_enabled(account):
        return stats
    provider = provider_for(account)
    calendars = list(account.calendars.filter(Q(is_displayed=True) | Q(is_target=True)))
    for calendar in calendars:
        try:
            with transaction.atomic():
                # Pull first: what changed outside is absorbed, then the push
                # sends local changes and puts refused edits back in line.
                stats["pulled"] += pull(calendar, provider)
                if calendar.is_target:
                    stats["pushed"] = push(account.user, calendar, provider)
                calendar.last_synced_at = timezone.now()
                calendar.last_error = ""
                calendar.save(
                    update_fields=[
                        "sync_cursor",
                        "last_synced_at",
                        "last_error",
                        "updated_at",
                    ]
                )
        except ProviderError as exc:
            calendar.last_error = str(exc)[:300]
            calendar.save(update_fields=["last_error", "updated_at"])
            stats["errors"].append(str(exc))
            log.warning("Calendar %s: %s", calendar.pk, exc)
    return stats


def refresh_calendars(account: OAuthAccount) -> list[ExternalCalendar]:
    """Reload the list from the provider; calendars that vanished are kept
    with their settings only if they are still used (target / displayed)."""
    provider = provider_for(account)
    found = provider.list_calendars()
    keep_ids = set()
    for item in found:
        calendar, _ = ExternalCalendar.objects.update_or_create(
            account=account,
            external_id=item["id"],
            defaults={
                "name": item["name"][:200],
                "color": (item["color"] or "")[:7],
                "is_primary": item["primary"],
            },
        )
        keep_ids.add(calendar.pk)
    account.calendars.exclude(pk__in=keep_ids).filter(
        is_displayed=False, is_target=False
    ).delete()
    return list(account.calendars.all())


def set_target(calendar: ExternalCalendar) -> None:
    """One target per user, whatever the provider."""
    ExternalCalendar.objects.filter(account__user=calendar.account.user).exclude(
        pk=calendar.pk
    ).update(is_target=False)
    calendar.is_target = True
    calendar.save(update_fields=["is_target", "updated_at"])


def renew_watch(calendar: ExternalCalendar) -> None:
    """Google push channel: (re)create it when missing or expiring today."""
    provider = provider_for(calendar.account)
    if (
        calendar.watch_expires_at
        and calendar.watch_expires_at > timezone.now() + timedelta(days=1)
    ):
        return
    try:
        provider.stop_watch(calendar)
        result = provider.watch(calendar)
    except ProviderError as exc:
        log.warning("Watch for calendar %s not renewed: %s", calendar.pk, exc)
        return
    if result is None:
        return
    calendar.watch_channel_id = result["channel_id"]
    calendar.watch_resource_id = result["resource_id"]
    calendar.watch_token_hash = hashlib.sha256(result["token"].encode()).hexdigest()
    calendar.watch_expires_at = result["expires_at"]
    calendar.save()
