"""Share-link rules that the views share (SPECIFICATIONS §6).

- the secret token: generated, hashed for lookups, encrypted for display;
- the link session: which links a visitor unlocked, when they were counted;
- signed media URLs bound to the visitor's session;
- counting views and plays within a window, checking quotas;
- the access journal with truncated IPs;
- the password attempt counter (5 per 15 min per link and IP).
"""

from __future__ import annotations

import hashlib
import ipaddress
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.core.cache import cache
from django.db.models import F
from django.utils import timezone

from apps.core import crypto
from apps.files.models import AssetVersion

from .models import Event, ShareAccessLog, ShareLink, State, Target

MEDIA_SALT = "sharing.media"


# --- Tokens -----------------------------------------------------------------------
def new_token() -> str:
    return secrets.token_urlsafe(32)  # 32 random bytes, 43 URL-safe characters


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def public_url(link: ShareLink) -> str | None:
    """The full URL, re-read from the encrypted copy (None if the key changed)."""
    token = crypto.decrypt(link.token_encrypted)
    return f"{settings.SITE_URL}/s/{token}" if token else None


def find_by_token(token: str) -> ShareLink | None:
    if not token or len(token) > 128:
        return None
    return (
        ShareLink.objects.select_related("project", "asset", "version__asset")
        .filter(token_hash=token_hash(token))
        .first()
    )


def set_password(link: ShareLink, password: str | None) -> None:
    link.password_hash = make_password(password) if password else ""


def check_link_password(link: ShareLink, password: str) -> bool:
    return bool(link.password_hash) and check_password(password, link.password_hash)


# --- What a link exposes ----------------------------------------------------------
def exposed_versions(link: ShareLink) -> list[AssetVersion]:
    """The versions a visitor may reach, in playlist order. An asset target
    always means its latest version at opening time."""
    if link.target_type == Target.VERSION:
        return [link.version] if link.version_id else []
    if link.target_type == Target.ASSET:
        latest = link.asset.latest_version if link.asset_id else None
        return [latest] if latest else []
    versions = []
    for item in link.items.select_related("asset"):
        latest = item.asset.latest_version
        if latest:
            versions.append(latest)
    return versions


def exposed_version(link: ShareLink, version_id: int) -> AssetVersion | None:
    return next((v for v in exposed_versions(link) if v.pk == version_id), None)


# --- Visitor session ----------------------------------------------------------------
def _session_key(request) -> str:
    """The anonymous session's key, creating the session if needed: media
    tokens are bound to it, so it must exist before any URL is signed."""
    if request.session.session_key is None:
        request.session.create()
    return request.session.session_key


def session_fingerprint(request) -> str:
    return hashlib.sha256(_session_key(request).encode()).hexdigest()[:24]


def _unlocked_key(link: ShareLink) -> str:
    return f"share_unlocked_{link.pk}"


def is_unlocked(request, link: ShareLink) -> bool:
    return not link.has_password or bool(request.session.get(_unlocked_key(link)))


def mark_unlocked(request, link: ShareLink) -> None:
    request.session[_unlocked_key(link)] = True


def media_token(request, link: ShareLink, version: AssetVersion) -> str:
    """Signed, short-lived, bound to this session: copied elsewhere, it fails."""
    return signing.dumps(
        {"l": link.pk, "v": version.pk, "s": session_fingerprint(request)},
        salt=MEDIA_SALT,
        compress=True,
    )


def read_media_token(request, token: str, link: ShareLink, version_id: int) -> bool:
    try:
        data = signing.loads(
            token, salt=MEDIA_SALT, max_age=settings.SHARE_MEDIA_TOKEN_SECONDS
        )
    except (signing.BadSignature, signing.SignatureExpired):
        return False
    return (
        data.get("l") == link.pk
        and data.get("v") == version_id
        and data.get("s") == session_fingerprint(request)
    )


# --- Journal -----------------------------------------------------------------------
def client_ip(request) -> str:
    """The visitor's IP behind one trusted proxy (REST_FRAMEWORK NUM_PROXIES)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def truncate_ip(ip: str) -> str:
    """IPv4 to /24, IPv6 to /48 (nLPD/RGPD: enough to spot abuse, not a person)."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ""
    bits = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f"{address}/{bits}", strict=False).network_address)


def log_event(request, link: ShareLink, event: str, version=None) -> ShareAccessLog:
    return ShareAccessLog.objects.create(
        share_link=link,
        version=version,
        event=event,
        ip_truncated=truncate_ip(client_ip(request)),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
    )


# --- Counting ----------------------------------------------------------------------
def _recent(request, key: str) -> bool:
    """True if `key` was stamped in this session within the counting window."""
    stamp = request.session.get(key)
    return bool(stamp) and (
        timezone.now().timestamp() - stamp < settings.SHARE_COUNT_WINDOW_SECONDS
    )


def _stamp(request, key: str) -> None:
    request.session[key] = timezone.now().timestamp()


def has_recent_view(request, link: ShareLink) -> bool:
    return _recent(request, f"share_view_{link.pk}")


def has_recent_play(request, link: ShareLink, version: AssetVersion) -> bool:
    return _recent(request, f"share_play_{link.pk}_{version.pk}")


def blocking_state(request, link: ShareLink, version: AssetVersion | None = None):
    """The state that stops this visitor, or None. A quota reached does
    not cut off the session that consumed the last unit: it keeps its
    30 minutes (SPECIFICATIONS §6), a new session gets 410."""
    state = link.state
    if state == State.ACTIVE:
        return None
    if state == State.EXHAUSTED:
        if has_recent_view(request, link) and (
            version is None
            or has_recent_play(request, link, version)
            or link.max_plays is None
        ):
            return None
    return state


def count_view(request, link: ShareLink) -> bool:
    """One view per session and link per window. Returns False when the
    view quota forbids a NEW view (a session already counted keeps reading)."""
    key = f"share_view_{link.pk}"
    if _recent(request, key):
        return True
    if link.max_views is not None and link.view_count >= link.max_views:
        return False
    now = timezone.now()
    ShareLink.objects.filter(pk=link.pk).update(
        view_count=F("view_count") + 1,
        last_opened_at=now,
        first_opened_at=link.first_opened_at or now,
    )
    link.refresh_from_db(fields=["view_count", "first_opened_at", "last_opened_at"])
    _stamp(request, key)
    log_event(request, link, Event.VIEW)
    if link.first_opened_at == now:
        from apps.notifications import services as notifications

        notifications.share_link_opened(link)
    return True


def count_play(request, link: ShareLink, version: AssetVersion) -> bool:
    """One play per session and version per window, counted when the start
    of the stream is requested. False when the play quota is reached."""
    key = f"share_play_{link.pk}_{version.pk}"
    if _recent(request, key):
        return True
    if link.max_plays is not None and link.play_count >= link.max_plays:
        return False
    ShareLink.objects.filter(pk=link.pk).update(play_count=F("play_count") + 1)
    link.refresh_from_db(fields=["play_count"])
    _stamp(request, key)
    log_event(request, link, Event.PLAY, version=version)
    return True


# --- Password attempts -------------------------------------------------------------
def _failures_key(link: ShareLink, request) -> str:
    return f"share-unlock:{link.pk}:{client_ip(request)}"


def unlock_blocked(request, link: ShareLink) -> bool:
    return (
        cache.get(_failures_key(link, request), 0) >= settings.SHARE_UNLOCK_MAX_FAILURES
    )


def record_unlock_failure(request, link: ShareLink) -> None:
    key = _failures_key(link, request)
    # add() is a no-op if the key exists: the window starts at the first
    # failure and is not extended by the following ones (same as login).
    cache.add(key, 0, timeout=settings.SHARE_UNLOCK_WINDOW_SECONDS)
    cache.incr(key)
    log_event(request, link, Event.PASSWORD_FAILED)


def clear_unlock_failures(request, link: ShareLink) -> None:
    cache.delete(_failures_key(link, request))
