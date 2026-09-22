"""Share links: the editors' API (ProjectScopedViewSet) and the public page
endpoints (no account, token in the URL, session-bound media URLs).

Public answers, by design:
- 404: no such link (an unknown token looks like any other missing page);
- 410: expired, revoked or exhausted ("Ce lien n'est plus disponible");
- 403: media URL copied to another browser, or password not given;
- 409: a watermarked stream still being prepared (the page polls).
"""

from django.db.models import Prefetch
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.files import protected_file_response
from apps.files.models import AssetDerivative, Kind
from apps.projects.access import Role
from apps.projects.permissions import ProjectScopedViewSet

from . import services, watermark
from .filters import ShareLinkFilter
from .models import Event, ShareLink, ShareLinkItem
from .serializers import (
    AccessLogSerializer,
    PublicShareSerializer,
    ShareLinkSerializer,
    UnlockSerializer,
)

READY = AssetDerivative.DerivativeStatus.READY
FAILED = AssetDerivative.DerivativeStatus.FAILED


class ShareLinkViewSet(ProjectScopedViewSet, viewsets.ModelViewSet):
    """Links are an editor's business, reading included (SPEC §10)."""

    queryset = ShareLink.objects.select_related(
        "project", "asset", "version__asset", "created_by"
    ).prefetch_related(
        Prefetch("items", queryset=ShareLinkItem.objects.select_related("asset"))
    )
    serializer_class = ShareLinkSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ShareLinkFilter
    read_role = Role.EDITOR
    write_role = Role.EDITOR

    @extend_schema(
        parameters=[
            OpenApiParameter("project", int),
            OpenApiParameter("include_descendants", bool),
            OpenApiParameter("workspace", int),
            OpenApiParameter(
                "state", str, enum=["active", "expired", "exhausted", "revoked"]
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=None, responses={200: ShareLinkSerializer})
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        link = self.get_object()
        if link.revoked_at is None:
            link.revoked_at = timezone.now()
            link.save(update_fields=["revoked_at", "updated_at"])
        return Response(self.get_serializer(link).data)

    @extend_schema(responses=AccessLogSerializer(many=True))
    @action(detail=True, url_path="access-log")
    def access_log(self, request, pk=None):
        link = self.get_object()
        entries = link.access_log.select_related("version")[:200]
        return Response(AccessLogSerializer(entries, many=True).data)


# --- Public page --------------------------------------------------------------------
class _PublicShareView(APIView):
    """Common ground: no account, the link found by its token, 404 / 410."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "share_page"

    def get_link(self, token: str) -> ShareLink:
        link = services.find_by_token(token)
        if link is None:
            raise NotFound()
        return link

    @staticmethod
    def gone(state: str) -> Response:
        return Response(
            {"detail": "Ce lien n'est plus disponible.", "state": state},
            status=status.HTTP_410_GONE,
        )

    def public_payload(self, request, link: ShareLink, unlocked: bool) -> dict:
        items = []
        if unlocked:
            items = [
                self.item(request, link, v) for v in services.exposed_versions(link)
            ]
        return {
            "title": link.title,
            "requires_password": not unlocked,
            "target_type": link.target_type,
            "allow_download": link.allow_download,
            "watermark": link.watermark,
            "expires_at": link.expires_at,
            "items": items,
        }

    def item(self, request, link: ShareLink, version) -> dict:
        base = f"/api/public/share/{self._token}/"
        sign = services.media_token(request, link, version)
        kind = version.kind
        ready, error, media_url = True, "", f"{base}media/{version.pk}/?t={sign}"
        derivatives = {(d.kind, d.params_hash): d for d in version.derivatives.all()}
        if kind == Kind.AUDIO:
            if link.watermark:
                derivative = watermark.request_audio(version)
                if derivative.status != READY:
                    ready, media_url = False, None
                    error = derivative.error if derivative.status == FAILED else ""
            elif ("stream_mp3", "") not in derivatives and version.processed_at is None:
                ready, media_url = False, None
        peaks = derivatives.get(("peaks", ""))
        thumbnail = derivatives.get(("thumbnail", ""))
        return {
            "version_id": version.pk,
            "name": version.asset.name,
            "kind": kind,
            "label": version.label,
            "number": version.number,
            "mime_type": version.mime_type,
            "duration_ms": version.duration_ms,
            "width": version.width,
            "height": version.height,
            "page_count": version.page_count,
            "media_url": media_url,
            "download_url": (
                f"{base}download/{version.pk}/?t={sign}"
                if link.allow_download
                else None
            ),
            "peaks_url": (
                f"{base}peaks/{version.pk}/?t={sign}"
                if peaks is not None and peaks.status == READY
                else None
            ),
            "thumbnail_url": (
                f"{base}thumb/{version.pk}/?t={sign}"
                if thumbnail is not None and thumbnail.status == READY
                else None
            ),
            "ready": ready,
            "error": error,
        }


class PublicShareView(_PublicShareView):
    """The page's data: password gate, or the items with their media URLs."""

    @extend_schema(responses={200: PublicShareSerializer, 404: None, 410: None})
    def get(self, request, token):
        self._token = token
        link = self.get_link(token)
        blocking = services.blocking_state(request, link)
        if blocking:
            return self.gone(blocking)
        unlocked = services.is_unlocked(request, link)
        if unlocked and not services.count_view(request, link):
            return self.gone("exhausted")
        return Response(
            PublicShareSerializer(self.public_payload(request, link, unlocked)).data
        )


class PublicUnlockView(_PublicShareView):
    """Password check: 5 failures per 15 min per link and IP, then 429."""

    throttle_scope = "share_unlock"

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @extend_schema(
        request=UnlockSerializer, responses={200: PublicShareSerializer, 410: None}
    )
    def post(self, request, token):
        self._token = token
        link = self.get_link(token)
        blocking = services.blocking_state(request, link)
        if blocking:
            return self.gone(blocking)
        if services.unlock_blocked(request, link):
            return Response(
                {"detail": "Trop d'essais. Réessaie dans un quart d'heure."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer = UnlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not services.check_link_password(
            link, serializer.validated_data["password"]
        ):
            services.record_unlock_failure(request, link)
            return Response(
                {"detail": "Mot de passe incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        services.clear_unlock_failures(request, link)
        services.mark_unlocked(request, link)
        if not services.count_view(request, link):
            return self.gone("exhausted")
        return Response(
            PublicShareSerializer(self.public_payload(request, link, True)).data
        )


class _PublicMediaView(_PublicShareView):
    """A file of the link, reachable only with a URL signed for this session."""

    throttle_classes = []  # a video seek is dozens of Range requests a minute

    def resolve(self, request, token, version_id):
        link = self.get_link(token)
        if not services.read_media_token(
            request, request.GET.get("t", ""), link, version_id
        ):
            raise PermissionDenied("Ce lien média n'est pas valable ici.")
        if not services.is_unlocked(request, link):
            raise PermissionDenied("Mot de passe requis.")
        version = services.exposed_version(link, version_id)
        if version is None or not version.file:
            raise NotFound()
        return link, version

    @staticmethod
    def derivative(version, kind, params_hash=""):
        return version.derivatives.filter(
            kind=kind, params_hash=params_hash, status=READY
        ).first()


class PublicMediaView(_PublicMediaView):
    """Stream (audio, watermarked or not), watermarked image, video, PDF."""

    @extend_schema(responses={200: {"type": "string", "format": "binary"}})
    def get(self, request, token, version_id):
        link, version = self.resolve(request, token, version_id)
        kind = version.kind
        if kind in (Kind.AUDIO, Kind.VIDEO):
            # A play is counted when the start of the stream is asked for,
            # not on every Range chunk of the same listening.
            range_header = request.META.get("HTTP_RANGE", "")
            at_start = not range_header or range_header.startswith("bytes=0-")
            blocking = services.blocking_state(request, link, version)
            if blocking:
                return self.gone(blocking)
            if at_start and not services.count_play(request, link, version):
                return self.gone("exhausted")
        else:
            blocking = services.blocking_state(request, link)
            if blocking:
                return self.gone(blocking)

        if kind == Kind.AUDIO:
            if link.watermark:
                derivative = self.derivative(
                    version, watermark.WM_AUDIO_KIND, watermark.audio_params_hash()
                )
                if derivative is None:
                    return Response(
                        {"detail": "Préparation de l'écoute…"},
                        status=status.HTTP_409_CONFLICT,
                    )
                return protected_file_response(
                    derivative.file, content_type="audio/mpeg"
                )
            derivative = self.derivative(version, "stream_mp3")
            if derivative is not None:
                return protected_file_response(
                    derivative.file, content_type="audio/mpeg"
                )
            # No stream (ffmpeg missing, or still processing): the original
            # plays in every browser for MP3/WAV/M4A.
            return protected_file_response(
                version.file, content_type=version.mime_type or "audio/mpeg"
            )
        if kind == Kind.IMAGE and link.watermark:
            derivative = watermark.get_or_build_image(version, link.watermark_text)
            return protected_file_response(derivative.file, content_type="image/webp")
        return protected_file_response(
            version.file, content_type=version.mime_type or "application/octet-stream"
        )


class PublicDownloadView(_PublicMediaView):
    @extend_schema(responses={200: {"type": "string", "format": "binary"}})
    def get(self, request, token, version_id):
        link, version = self.resolve(request, token, version_id)
        if not link.allow_download:
            raise PermissionDenied("Le téléchargement n'est pas autorisé.")
        blocking = services.blocking_state(request, link)
        if blocking:
            return self.gone(blocking)
        services.log_event(request, link, Event.DOWNLOAD, version=version)
        return protected_file_response(
            version.file,
            content_type=version.mime_type or "application/octet-stream",
            filename=version.original_filename or None,
            inline=False,
        )


class PublicPeaksView(_PublicMediaView):
    @extend_schema(responses={200: {"type": "object"}})
    def get(self, request, token, version_id):
        _, version = self.resolve(request, token, version_id)
        derivative = self.derivative(version, "peaks")
        if derivative is None:
            raise NotFound()
        return protected_file_response(
            derivative.file,
            content_type="application/json",
            cache_control="private, max-age=3600",
        )


class PublicThumbnailView(_PublicMediaView):
    @extend_schema(responses={200: {"type": "string", "format": "binary"}})
    def get(self, request, token, version_id):
        _, version = self.resolve(request, token, version_id)
        derivative = self.derivative(version, "thumbnail")
        if derivative is None:
            raise NotFound()
        return protected_file_response(
            derivative.file,
            content_type="image/webp",
            cache_control="private, max-age=3600",
        )
