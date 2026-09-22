"""The two calendar providers behind one small interface (SPEC §12).

Both speak in the same normalised shapes:

- a calendar: {"id", "name", "color", "primary"}
- an incoming event: {"id", "deleted", "title", "start", "end", "all_day",
  "updated", "etag", "location"} with aware datetimes; an all-day event
  keeps SOBASED's convention (midnight UTC, inclusive end for events);
- an outgoing payload: {"title", "start", "end", "all_day"}.

Google Calendar API v3 with syncToken (and push channels when the site is
reachable in HTTPS); Microsoft Graph with calendarView/delta on a window.
`CursorInvalid` tells sync.py to start again from a full read.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from . import google, microsoft
from .google import DriveClient, GoogleError
from .microsoft import GraphClient, MicrosoftError
from .models import ExternalCalendar, OAuthAccount, Provider

WINDOW_PAST_DAYS = 30
WINDOW_FUTURE_DAYS = 180
GOOGLE_CAL = "https://www.googleapis.com/calendar/v3"
GOOGLE_EVENT_FIELDS = "id,status,summary,start,end,updated,etag,location"


class CursorInvalid(Exception):
    """The sync token / delta link is no longer accepted: full read again."""


class ProviderError(Exception):
    pass


def window() -> tuple[datetime, datetime]:
    now = timezone.now()
    return now - timedelta(days=WINDOW_PAST_DAYS), now + timedelta(
        days=WINDOW_FUTURE_DAYS
    )


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


# --- Google ---------------------------------------------------------------------------
class GoogleCalendarProvider:
    def __init__(self, account: OAuthAccount):
        self.client = DriveClient(account)  # same bearer handling, other URLs

    def _call(self, method, url, **kwargs):
        try:
            return self.client.request(method, url, **kwargs)
        except GoogleError as exc:
            if exc.status == 410:
                raise CursorInvalid() from exc
            raise ProviderError(str(exc)) from exc

    def list_calendars(self) -> list[dict]:
        data = self._call("GET", f"{GOOGLE_CAL}/users/me/calendarList").json()
        return [
            {
                "id": item["id"],
                "name": item.get("summaryOverride") or item.get("summary", ""),
                "color": item.get("backgroundColor", ""),
                "primary": bool(item.get("primary")),
            }
            for item in data.get("items", [])
            if item.get("accessRole") in ("owner", "writer", "reader")
        ]

    @staticmethod
    def _body(payload: dict) -> dict:
        if payload["all_day"]:
            start = payload["start"].date()
            end = payload["end"].date() + timedelta(days=1)  # Google: exclusive
            return {
                "summary": payload["title"],
                "start": {"date": start.isoformat()},
                "end": {"date": end.isoformat()},
            }
        return {
            "summary": payload["title"],
            "start": {"dateTime": payload["start"].isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": payload["end"].isoformat(), "timeZone": "UTC"},
        }

    def insert(self, calendar_id: str, payload: dict) -> dict:
        data = self._call(
            "POST",
            f"{GOOGLE_CAL}/calendars/{calendar_id}/events",
            params={"fields": GOOGLE_EVENT_FIELDS},
            json=self._body(payload),
        ).json()
        return self._normalise(data)

    def update(self, calendar_id: str, external_id: str, payload: dict) -> dict:
        data = self._call(
            "PATCH",
            f"{GOOGLE_CAL}/calendars/{calendar_id}/events/{external_id}",
            params={"fields": GOOGLE_EVENT_FIELDS},
            json=self._body(payload),
        ).json()
        return self._normalise(data)

    def delete(self, calendar_id: str, external_id: str) -> None:
        try:
            self._call(
                "DELETE", f"{GOOGLE_CAL}/calendars/{calendar_id}/events/{external_id}"
            )
        except ProviderError as exc:
            if "404" not in str(exc) and "410" not in str(exc):
                raise

    def changes(self, calendar: ExternalCalendar) -> tuple[list[dict], str]:
        """Incremental with the syncToken; without one, the whole window."""
        items: list[dict] = []
        params: dict = {
            "fields": f"items({GOOGLE_EVENT_FIELDS}),nextPageToken,nextSyncToken"
        }
        if calendar.sync_cursor:
            params["syncToken"] = calendar.sync_cursor
        else:
            start, end = window()
            params.update(
                {
                    "timeMin": start.isoformat(),
                    "timeMax": end.isoformat(),
                    "singleEvents": "true",
                    "showDeleted": "true",
                }
            )
        cursor = ""
        url = f"{GOOGLE_CAL}/calendars/{calendar.external_id}/events"
        while True:
            data = self._call("GET", url, params=params).json()
            items += [self._normalise(item) for item in data.get("items", [])]
            if data.get("nextPageToken"):
                params = {**params, "pageToken": data["nextPageToken"]}
                continue
            cursor = data.get("nextSyncToken", "")
            break
        return items, cursor

    @staticmethod
    def _normalise(item: dict) -> dict:
        start_raw, end_raw = item.get("start") or {}, item.get("end") or {}
        all_day = "date" in start_raw
        if all_day:
            start = _midnight(parse_date(start_raw["date"]))
            # Google's end is exclusive: back to SOBASED's inclusive end.
            end = _midnight(
                parse_date(end_raw.get("date", start_raw["date"]))
            ) - timedelta(days=1)
            end = max(end, start)
        else:
            start = parse_datetime(start_raw.get("dateTime", "")) if start_raw else None
            end = parse_datetime(end_raw.get("dateTime", "")) if end_raw else None
        updated = parse_datetime(item["updated"]) if item.get("updated") else None
        return {
            "id": item.get("id", ""),
            "deleted": item.get("status") == "cancelled",
            "title": item.get("summary", "") or "",
            "start": start,
            "end": end,
            "all_day": all_day,
            "updated": updated,
            "etag": item.get("etag", ""),
            "location": item.get("location", "") or "",
        }

    # --- Push channels (only with a public HTTPS address) -------------------
    def watch(self, calendar: ExternalCalendar) -> dict | None:
        if not settings.SITE_IS_HTTPS:
            return None
        channel_id = uuid.uuid4().hex
        token = uuid.uuid4().hex
        data = self._call(
            "POST",
            f"{GOOGLE_CAL}/calendars/{calendar.external_id}/events/watch",
            json={
                "id": channel_id,
                "type": "web_hook",
                "address": settings.SITE_URL
                + "/api/integrations/google/calendar/webhook/",
                "token": token,
            },
        ).json()
        return {
            "channel_id": channel_id,
            "token": token,
            "resource_id": data.get("resourceId", ""),
            "expires_at": (
                datetime.fromtimestamp(int(data["expiration"]) / 1000, tz=UTC)
                if data.get("expiration")
                else timezone.now() + timedelta(days=7)
            ),
        }

    def stop_watch(self, calendar: ExternalCalendar) -> None:
        if not calendar.watch_channel_id:
            return
        try:
            self._call(
                "POST",
                f"{GOOGLE_CAL}/channels/stop",
                json={
                    "id": calendar.watch_channel_id,
                    "resourceId": calendar.watch_resource_id,
                },
            )
        except ProviderError:
            pass


# --- Microsoft ------------------------------------------------------------------------
class MicrosoftCalendarProvider:
    def __init__(self, account: OAuthAccount):
        self.client = GraphClient(account)

    def _call(self, method, url, **kwargs):
        try:
            return self.client.request(method, url, **kwargs)
        except MicrosoftError as exc:
            if exc.status == 410:
                raise CursorInvalid() from exc
            raise ProviderError(str(exc)) from exc

    def list_calendars(self) -> list[dict]:
        data = self._call("GET", f"{microsoft.GRAPH_URL}/me/calendars").json()
        return [
            {
                "id": item["id"],
                "name": item.get("name", ""),
                "color": item.get("hexColor", "") or "",
                "primary": bool(item.get("isDefaultCalendar")),
            }
            for item in data.get("value", [])
        ]

    @staticmethod
    def _body(payload: dict) -> dict:
        if payload["all_day"]:
            start = payload["start"].date()
            end = payload["end"].date() + timedelta(days=1)  # Graph: exclusive too
            return {
                "subject": payload["title"],
                "isAllDay": True,
                "start": {
                    "dateTime": f"{start.isoformat()}T00:00:00",
                    "timeZone": "UTC",
                },
                "end": {"dateTime": f"{end.isoformat()}T00:00:00", "timeZone": "UTC"},
            }
        fmt = "%Y-%m-%dT%H:%M:%S"
        return {
            "subject": payload["title"],
            "isAllDay": False,
            "start": {
                "dateTime": payload["start"].astimezone(UTC).strftime(fmt),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": payload["end"].astimezone(UTC).strftime(fmt),
                "timeZone": "UTC",
            },
        }

    def insert(self, calendar_id: str, payload: dict) -> dict:
        data = self._call(
            "POST",
            f"{microsoft.GRAPH_URL}/me/calendars/{calendar_id}/events",
            json=self._body(payload),
        ).json()
        return self._normalise(data)

    def update(self, calendar_id: str, external_id: str, payload: dict) -> dict:
        data = self._call(
            "PATCH",
            f"{microsoft.GRAPH_URL}/me/events/{external_id}",
            json=self._body(payload),
        ).json()
        return self._normalise(data)

    def delete(self, calendar_id: str, external_id: str) -> None:
        try:
            self._call("DELETE", f"{microsoft.GRAPH_URL}/me/events/{external_id}")
        except ProviderError as exc:
            if "404" not in str(exc):
                raise

    def changes(self, calendar: ExternalCalendar) -> tuple[list[dict], str]:
        """calendarView/delta over the window; the deltaLink is the cursor."""
        items: list[dict] = []
        if calendar.sync_cursor:
            url, params = calendar.sync_cursor, None
        else:
            start, end = window()
            url = (
                f"{microsoft.GRAPH_URL}/me/calendars/{calendar.external_id}"
                "/calendarView/delta"
            )
            params = {
                "startDateTime": start.isoformat(),
                "endDateTime": end.isoformat(),
            }
        headers = {"Prefer": 'outlook.timezone="UTC"'}
        cursor = ""
        while True:
            data = self._call("GET", url, params=params, headers=headers).json()
            items += [self._normalise(item) for item in data.get("value", [])]
            if data.get("@odata.nextLink"):
                url, params = data["@odata.nextLink"], None
                continue
            cursor = data.get("@odata.deltaLink", "")
            break
        return items, cursor

    @staticmethod
    def _parse(value: dict | None) -> datetime | None:
        if not value or not value.get("dateTime"):
            return None
        text = value["dateTime"][:26]
        parsed = parse_datetime(text)
        return (
            parsed.replace(tzinfo=UTC) if parsed and parsed.tzinfo is None else parsed
        )

    def _normalise(self, item: dict) -> dict:
        deleted = "@removed" in item
        all_day = bool(item.get("isAllDay"))
        start, end = self._parse(item.get("start")), self._parse(item.get("end"))
        if all_day and start and end:
            start = _midnight(start.date())
            end = max(_midnight(end.date()) - timedelta(days=1), start)
        updated = (
            parse_datetime(item["lastModifiedDateTime"])
            if item.get("lastModifiedDateTime")
            else None
        )
        return {
            "id": item.get("id", ""),
            "deleted": deleted,
            "title": item.get("subject", "") or "",
            "start": start,
            "end": end,
            "all_day": all_day,
            "updated": updated,
            "etag": item.get("@odata.etag", ""),
            "location": ((item.get("location") or {}).get("displayName") or ""),
        }

    def watch(self, calendar: ExternalCalendar) -> dict | None:
        return None  # polling only (SPECIFICATIONS §8)

    def stop_watch(self, calendar: ExternalCalendar) -> None:
        return None


def provider_for(account: OAuthAccount):
    if account.provider == Provider.GOOGLE:
        return GoogleCalendarProvider(account)
    return MicrosoftCalendarProvider(account)


def feature_enabled(account: OAuthAccount) -> bool:
    """Google needs the Calendar scope; Microsoft always asks Calendars.ReadWrite."""
    if account.provider == Provider.GOOGLE:
        return google.enabled() and account.has_feature("calendar")
    return microsoft.enabled() and "Calendars.ReadWrite" in (account.scopes or [])
