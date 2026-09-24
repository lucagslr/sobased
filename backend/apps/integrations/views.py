"""Integrations API (SPEC §11): the signed-in user's external accounts,
the Google OAuth round trip, the Picker configuration, Drive links, and the
Drive actions of a project (folder, upload).

Account endpoints act on request.user only. Drive links and project actions
go through the project rights (ProjectScopedViewSet / check_project_access).
"""

import hashlib

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.projects.access import Role
from apps.projects.models import Project
from apps.projects.permissions import ProjectScopedViewSet
from apps.projects.serializers import ProjectSerializer

from . import drive, google, microsoft, sync
from .calendars import ProviderError, feature_enabled
from .google import GoogleError
from .microsoft import MicrosoftError
from .models import (
    FEATURE_SCOPES,
    DriveLink,
    ExternalCalendar,
    ExternalEvent,
    OAuthAccount,
    Provider,
    SyncConflict,
)
from .serializers import (
    ConnectUrlSerializer,
    DriveLinkSerializer,
    ExternalCalendarSerializer,
    ExternalEventSerializer,
    IntegrationsStateSerializer,
    PickerConfigSerializer,
    SyncConflictSerializer,
)
from .tasks import sync_calendar_account

SETTINGS_URL = "/parametres/integrations"


def _drive_error(exc: Exception) -> ValidationError:
    return ValidationError({"detail": str(exc)})


class IntegrationsStateView(APIView):
    @extend_schema(responses=IntegrationsStateSerializer)
    def get(self, request):
        return Response(
            IntegrationsStateSerializer(drive.integration_state(request.user)).data
        )


class GoogleConnectView(APIView):
    """The authorization URL for the requested features (drive, calendar)."""

    @extend_schema(
        parameters=[OpenApiParameter("features", str, description="drive,calendar")],
        responses=ConnectUrlSerializer,
    )
    def get(self, request):
        if not google.enabled():
            raise ValidationError(
                {"detail": "L'intégration Google n'est pas configurée."}
            )
        wanted = [f for f in request.GET.get("features", "drive").split(",") if f]
        scopes = [FEATURE_SCOPES[f] for f in wanted if f in FEATURE_SCOPES]
        if not scopes:
            raise ValidationError({"features": "drive ou calendar."})
        return Response({"url": google.authorization_url(request.user, scopes)})


class GoogleCallbackView(APIView):
    """Google sends the browser back here; the user must be the one who
    started (signed state), then the tokens are stored encrypted."""

    @extend_schema(responses={302: None})
    def get(self, request):
        state = google.read_state(request.GET.get("state", ""))
        code = request.GET.get("code")
        if not state or state.get("u") != request.user.pk or not code:
            return HttpResponseRedirect(f"{SETTINGS_URL}?google=refus")
        if request.GET.get("error"):
            return HttpResponseRedirect(f"{SETTINGS_URL}?google=refus")
        try:
            data = google.exchange_code(code)
            info = google.userinfo(data["access_token"])
        except (GoogleError, KeyError):
            return HttpResponseRedirect(f"{SETTINGS_URL}?google=erreur")
        with transaction.atomic():
            account, _ = OAuthAccount.objects.get_or_create(
                user=request.user, provider=Provider.GOOGLE
            )
            account.account_email = info.get("email", "")[:254]
            google.store_tokens(account, data)
        return HttpResponseRedirect(f"{SETTINGS_URL}?google=ok")


class GoogleDisconnectView(APIView):
    """Revoke at Google, forget the tokens. Folders owned by this account
    keep their links; creation and upload are disabled (drive_account
    becomes null)."""

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @extend_schema(responses={204: None})
    def delete(self, request):
        account = drive.google_account(request.user)
        if account is not None:
            google.revoke(account)
            account.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PickerConfigView(APIView):
    """What the Picker needs, with a short-lived access token of the user."""

    @extend_schema(responses=PickerConfigSerializer)
    def get(self, request):
        account = drive.drive_account(request.user)
        if not google.enabled() or account is None:
            raise ValidationError({"detail": "Connecte Google Drive d'abord."})
        try:
            token = google.valid_access_token(account)
        except GoogleError as exc:
            raise _drive_error(exc) from exc
        return Response(
            {
                "api_key": settings.GOOGLE_API_KEY,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "app_id": settings.GOOGLE_APP_ID,
                "access_token": token,
            }
        )


class DriveLinkViewSet(
    ProjectScopedViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Drive files attached to a project or a task (Picker)."""

    queryset = DriveLink.objects.select_related("project", "task", "added_by")
    serializer_class = DriveLinkSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["project", "task"]
    pagination_class = None

    def perform_create(self, serializer):
        data = serializer.validated_data
        self.check_project_access(data["project"])
        try:
            link = drive.attach_picked_file(
                data["project"],
                data["drive_file_id"],
                self.request.user,
                data.get("task"),
            )
        except (drive.DriveUnavailable, GoogleError) as exc:
            raise _drive_error(exc) from exc
        serializer.instance = link


class ProjectDriveViewSet(ProjectScopedViewSet, viewsets.GenericViewSet):
    """`/api/projects/{id}/drive/…`: the folder and uploads (editors)."""

    queryset = Project.objects.select_related("parent", "drive_account")
    serializer_class = ProjectSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_project(self, obj):
        return obj

    def get_serializer_context(self):
        from apps.projects.access import get_access_map

        return {
            **super().get_serializer_context(),
            "access_map": get_access_map(self.request),
        }

    @extend_schema(request=None, responses={200: ProjectSerializer})
    @action(detail=True, methods=["post"], url_path="drive/create-folder")
    def create_folder(self, request, pk=None):
        project = self.get_object()
        try:
            drive.create_folder(project, drive.drive_account(request.user))
        except (drive.DriveUnavailable, GoogleError) as exc:
            raise _drive_error(exc) from exc
        project.refresh_from_db()
        return Response(self.get_serializer(project).data)

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
            }
        },
        responses={201: DriveLinkSerializer},
    )
    @action(detail=True, methods=["post"], url_path="drive/upload")
    def upload(self, request, pk=None):
        project = self.get_object()
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["Aucun fichier reçu."]})
        try:
            link = drive.upload_to_project(project, upload, request.user)
        except (drive.DriveUnavailable, GoogleError) as exc:
            raise _drive_error(exc) from exc
        return Response(DriveLinkSerializer(link).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: ProjectSerializer})
    @action(detail=True, methods=["post"], url_path="drive/share")
    def share(self, request, pk=None):
        """Re-apply the sharing with members (after new members joined)."""
        project = self.get_object()
        try:
            shared = drive.share_with_members(project)
        except (drive.DriveUnavailable, GoogleError) as exc:
            raise _drive_error(exc) from exc
        data = self.get_serializer(project).data
        data["shared_with"] = shared
        return Response(data)

    def required_role(self):
        return Role.EDITOR


# --- Microsoft (SPEC §12) -------------------------------------------------------------
class MicrosoftConnectView(APIView):
    @extend_schema(responses=ConnectUrlSerializer)
    def get(self, request):
        if not microsoft.enabled():
            raise ValidationError(
                {"detail": "L'intégration Microsoft n'est pas configurée."}
            )
        return Response({"url": microsoft.authorization_url(request.user)})


class MicrosoftCallbackView(APIView):
    @extend_schema(responses={302: None})
    def get(self, request):
        state = microsoft.read_state(request.GET.get("state", ""))
        code = request.GET.get("code")
        refused = not state or state.get("u") != request.user.pk or not code
        if refused or request.GET.get("error"):
            return HttpResponseRedirect(f"{SETTINGS_URL}?microsoft=refus")
        try:
            data = microsoft.exchange_code(code)
            info = microsoft.userinfo(data["access_token"])
        except (MicrosoftError, KeyError):
            return HttpResponseRedirect(f"{SETTINGS_URL}?microsoft=erreur")
        with transaction.atomic():
            account, _ = OAuthAccount.objects.get_or_create(
                user=request.user, provider=Provider.MICROSOFT
            )
            email = info.get("mail") or info.get("userPrincipalName") or ""
            account.account_email = email[:254]
            microsoft.store_tokens(account, data)
        return HttpResponseRedirect(f"{SETTINGS_URL}?microsoft=ok")


class MicrosoftDisconnectView(APIView):
    """No revocation endpoint at Microsoft for this flow: forgetting the
    tokens is the disconnection (the user may also revoke in their account)."""

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @extend_schema(responses={204: None})
    def delete(self, request):
        OAuthAccount.objects.filter(
            user=request.user, provider=Provider.MICROSOFT
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Calendars ------------------------------------------------------------------------
class ExternalCalendarViewSet(
    mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """My external calendars: which ones to display, which one receives my
    Faiblegraine objects (one target per user)."""

    queryset = ExternalCalendar.objects.none()  # for the schema; see get_queryset
    serializer_class = ExternalCalendarSerializer
    http_method_names = ["get", "patch", "post", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        return ExternalCalendar.objects.filter(
            account__user=self.request.user
        ).select_related("account")

    def perform_update(self, serializer):
        wants_target = serializer.validated_data.get("is_target")
        calendar = serializer.save()
        if wants_target:
            sync.set_target(calendar)

    @extend_schema(request=None, responses=ExternalCalendarSerializer(many=True))
    @action(detail=False, methods=["post"])
    def refresh(self, request):
        """Reload the lists from Google and Microsoft."""
        errors = []
        for account in OAuthAccount.objects.filter(user=request.user):
            if not account.usable or not feature_enabled(account):
                continue
            try:
                sync.refresh_calendars(account)
            except (ProviderError, GoogleError, MicrosoftError) as exc:
                errors.append(str(exc))
        data = self.get_serializer(self.get_queryset(), many=True).data
        if errors:
            return Response({"detail": " ".join(errors), "calendars": data}, status=400)
        return Response(data)


class SyncNowView(APIView):
    """Queue a sync of my accounts (the beat does it every 5 minutes)."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "sync_now"

    @extend_schema(request=None, responses={202: None})
    def post(self, request):
        for account in OAuthAccount.objects.filter(user=request.user):
            if account.usable and feature_enabled(account):
                sync_calendar_account.delay(account.pk)
        return Response(status=status.HTTP_202_ACCEPTED)


class SyncConflictsView(APIView):
    @extend_schema(responses=SyncConflictSerializer(many=True))
    def get(self, request):
        conflicts = SyncConflict.objects.filter(
            mapping__calendar__account__user=request.user
        ).select_related("mapping__calendar")[:50]
        return Response(SyncConflictSerializer(conflicts, many=True).data)


class ExternalEventsView(APIView):
    """Events of my displayed calendars crossing [start, end[: read-only."""

    @extend_schema(
        parameters=[OpenApiParameter("start", str), OpenApiParameter("end", str)],
        responses=ExternalEventSerializer(many=True),
    )
    def get(self, request):
        start = parse_datetime(request.GET.get("start", "") or "")
        end = parse_datetime(request.GET.get("end", "") or "")
        if start is None or end is None:
            raise ValidationError({"start": "start et end (ISO) sont requis."})
        events = (
            ExternalEvent.objects.filter(
                calendar__account__user=request.user,
                calendar__is_displayed=True,
                start__lt=end,
                end__gte=start,
            )
            .select_related("calendar__account")
            .order_by("start")[:2000]
        )
        return Response(ExternalEventSerializer(events, many=True).data)


class GoogleCalendarWebhookView(APIView):
    """Google push notification: the channel token must match the calendar's
    stored hash; then a sync is queued. Always 200 (Google retries otherwise)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        channel_id = request.headers.get("X-Goog-Channel-ID", "")
        token = request.headers.get("X-Goog-Channel-Token", "")
        if channel_id and token:
            digest = hashlib.sha256(token.encode()).hexdigest()
            calendar = ExternalCalendar.objects.filter(
                watch_channel_id=channel_id, watch_token_hash=digest
            ).first()
            if calendar is not None:
                sync_calendar_account.delay(calendar.account_id)
        return Response(status=status.HTTP_200_OK)
