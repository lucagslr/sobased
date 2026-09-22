"""Assets, versions and anchored comments (SPEC §9).

All three viewsets are ProjectScopedViewSet: reading needs the Viewer role,
writing the Editor role, commenting the Commenter role. Files are only ever
served by the `file`, `stream`, `peaks` and `thumbnail` actions, after that
check, through apps.core.files.protected_file_response().
"""

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from apps.core.files import protected_file_response
from apps.projects.access import Role, effective_access, get_access_map
from apps.projects.permissions import ProjectScopedViewSet

from . import services
from .filters import AssetFilter
from .models import Asset, AssetComment, AssetDerivative, AssetVersion
from .serializers import (
    AssetCommentSerializer,
    AssetSerializer,
    AssetVersionSerializer,
    ChangeStatusSerializer,
    StatusChangeSerializer,
)

READY = AssetDerivative.DerivativeStatus.READY


def _versions_queryset():
    # Meta.ordering is dropped by Django on GROUP BY queries: order here.
    return (
        AssetVersion.objects.select_related("author")
        .prefetch_related("derivatives")
        .order_by("-number")
        .annotate(
            comments_total=Count("comments", distinct=True),
            open_threads_total=Count(
                "comments",
                filter=Q(
                    comments__parent__isnull=True, comments__resolved_at__isnull=True
                ),
                distinct=True,
            ),
        )
    )


class _ReadOnGetMixin:
    """Custom GET actions (file, stream...) only need the reading role."""

    def required_role(self):
        if self.request.method in SAFE_METHODS:
            return self.read_role
        return super().required_role()


class AssetViewSet(_ReadOnGetMixin, ProjectScopedViewSet, viewsets.ModelViewSet):
    queryset = Asset.objects.select_related("project", "created_by").prefetch_related(
        "tags", "followers", Prefetch("versions", queryset=_versions_queryset())
    )
    serializer_class = AssetSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = AssetFilter
    ordering_fields = ["updated_at", "created_at", "name"]
    ordering = ["-updated_at", "-id"]
    action_roles = {"follow": Role.VIEWER, "versions": Role.VIEWER}

    @extend_schema(
        parameters=[
            OpenApiParameter("project", int),
            OpenApiParameter("include_descendants", bool),
            OpenApiParameter("workspace", int),
            OpenApiParameter(
                "kind", str, enum=["audio", "image", "video", "document", "other"]
            ),
            OpenApiParameter(
                "status", str, enum=["draft", "to_validate", "approved", "rejected"]
            ),
            OpenApiParameter("tag", int),
            OpenApiParameter("search", str),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        self.check_project_access(data["project"])
        upload = data.pop("file")
        label, note = data.pop("label", ""), data.pop("note", "")
        asset = serializer.save(created_by=self.request.user)
        try:
            services.add_version(
                asset, upload, self.request.user, label=label, note=note
            )
        except services.UploadTooLarge as exc:
            raise ValidationError({"file": [str(exc)]}) from exc

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return self._fresh(response, response.data["id"], status.HTTP_201_CREATED)

    def _fresh(self, response, pk, code=status.HTTP_200_OK):
        asset = self.get_queryset().get(pk=pk)
        return Response(self.get_serializer(asset).data, status=code)

    # --- Versions ------------------------------------------------------------------
    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                    "label": {"type": "string"},
                    "note": {"type": "string"},
                },
            }
        },
        responses={200: AssetVersionSerializer(many=True), 201: AssetVersionSerializer},
    )
    @action(
        detail=True,
        methods=["get", "post"],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def versions(self, request, pk=None):
        """GET: every version, newest first. POST: the next one (editors)."""
        asset = self.get_object()
        if request.method == "GET":
            queryset = _versions_queryset().filter(asset=asset)
            return Response(
                AssetVersionSerializer(
                    queryset, many=True, context=self.get_serializer_context()
                ).data
            )
        self.check_project_access(asset.project, Role.EDITOR)
        upload = request.FILES.get("file")
        drive_file_id = request.data.get("drive_file_id", "")
        if upload is None and not drive_file_id:
            raise ValidationError({"file": ["Aucun fichier reçu."]})
        try:
            if upload is not None:
                version = services.add_version(
                    asset,
                    upload,
                    request.user,
                    label=request.data.get("label", ""),
                    note=request.data.get("note", ""),
                )
            else:
                version = services.add_drive_version(
                    asset,
                    str(drive_file_id),
                    request.user,
                    label=request.data.get("label", ""),
                    note=request.data.get("note", ""),
                )
        except services.UploadTooLarge as exc:
            raise ValidationError({"file": [str(exc)]}) from exc
        except services.DriveProblem as exc:
            raise ValidationError({"drive_file_id": [str(exc)]}) from exc
        fresh = _versions_queryset().get(pk=version.pk)
        return Response(
            AssetVersionSerializer(fresh, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    # --- Status ----------------------------------------------------------------------
    @extend_schema(request=ChangeStatusSerializer, responses={200: AssetSerializer})
    @action(detail=True, methods=["post"], url_path="status")
    def change_status(self, request, pk=None):
        asset = self.get_object()  # editor: write_role
        serializer = ChangeStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_status(
            asset,
            serializer.validated_data["status"],
            request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return self._fresh(None, asset.pk)

    @extend_schema(responses=StatusChangeSerializer(many=True))
    @action(detail=True, url_path="status-history")
    def status_history(self, request, pk=None):
        asset = self.get_object()
        history = asset.status_changes.select_related("changed_by")
        return Response(StatusChangeSerializer(history, many=True).data)

    @extend_schema(request=None, responses={200: AssetSerializer})
    @action(detail=True, methods=["post", "delete"])
    def follow(self, request, pk=None):
        asset = self.get_object()
        if request.method == "POST":
            asset.followers.add(request.user)
        else:
            asset.followers.remove(request.user)
        return self._fresh(None, asset.pk)


class AssetVersionViewSet(
    _ReadOnGetMixin,
    ProjectScopedViewSet,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """One version: label and note may change, the file never does."""

    queryset = _versions_queryset().select_related("asset__project")
    serializer_class = AssetVersionSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    action_roles = {"comments": Role.VIEWER}

    def get_project(self, obj):
        return obj.asset.project

    def perform_destroy(self, instance):
        if instance.asset.versions.count() == 1:
            raise ValidationError(
                "La dernière version ne se supprime pas : supprime le fichier entier."
            )
        instance.delete()

    def _serve(
        self,
        field_file,
        content_type,
        filename=None,
        inline=True,
        cache_control="private, no-store",
    ):
        if not field_file:
            raise NotFound()
        return protected_file_response(
            field_file,
            content_type=content_type,
            filename=filename,
            inline=inline,
            cache_control=cache_control,
        )

    def _derivative(self, version, kind):
        found = version.derivatives.filter(kind=kind, status=READY).first()
        if found is None:
            raise NotFound()
        return found

    @extend_schema(responses={200: {"type": "string", "format": "binary"}})
    @action(detail=True)
    def file(self, request, pk=None):
        """The original, for members: Caddy streams it (Range included)."""
        version = self.get_object()
        return self._serve(
            version.file,
            version.mime_type or "application/octet-stream",
            filename=version.original_filename or None,
            inline=request.query_params.get("download") not in ("1", "true"),
        )

    @extend_schema(responses={200: {"type": "string", "format": "binary"}})
    @action(detail=True)
    def stream(self, request, pk=None):
        """MP3 128 kbps for in-app playback."""
        version = self.get_object()
        derivative = self._derivative(version, "stream_mp3")
        return self._serve(
            derivative.file, "audio/mpeg", cache_control="private, max-age=3600"
        )

    @extend_schema(responses={200: {"type": "object"}})
    @action(detail=True)
    def peaks(self, request, pk=None):
        """Pre-computed waveform (JSON) for wavesurfer."""
        version = self.get_object()
        derivative = self._derivative(version, "peaks")
        return self._serve(
            derivative.file, "application/json", cache_control="private, max-age=3600"
        )

    @extend_schema(responses={200: {"type": "string", "format": "binary"}})
    @action(detail=True)
    def thumbnail(self, request, pk=None):
        version = self.get_object()
        derivative = self._derivative(version, "thumbnail")
        return self._serve(
            derivative.file, "image/webp", cache_control="private, max-age=3600"
        )

    @extend_schema(request=None, responses={200: AssetVersionSerializer})
    @action(detail=True, methods=["post"], url_path="import-from-drive")
    def import_from_drive(self, request, pk=None):
        """Copy a Drive-referenced version into the internal storage
        (editors): needed to stream it or share it by link."""
        version = self.get_object()
        self.check_project_access(version.asset.project, Role.EDITOR)
        try:
            services.import_from_drive(version, request.user)
        except (services.UploadTooLarge, *services.DriveProblem, ValueError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        fresh = _versions_queryset().get(pk=version.pk)
        return Response(
            AssetVersionSerializer(fresh, context=self.get_serializer_context()).data
        )

    # --- Comments -----------------------------------------------------------------
    @extend_schema(
        request=AssetCommentSerializer,
        responses={200: AssetCommentSerializer(many=True), 201: AssetCommentSerializer},
    )
    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        """GET: every comment of the version (threads flattened, replies carry
        `parent`). POST: a new thread, or a reply with `parent` (commenters)."""
        version = self.get_object()
        context = {**self.get_serializer_context(), "version": version}
        if request.method == "GET":
            comments = version.comments.select_related("author", "resolved_by")
            return Response(
                AssetCommentSerializer(comments, many=True, context=context).data
            )
        self.check_project_access(version.asset.project, Role.COMMENTER)
        serializer = AssetCommentSerializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(version=version, author=request.user)
        version.asset.followers.add(request.user)
        return Response(
            AssetCommentSerializer(comment, context=context).data,
            status=status.HTTP_201_CREATED,
        )


class AssetCommentViewSet(
    ProjectScopedViewSet,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Edit (author), delete (author or admin), resolve / reopen a thread
    (its author or an editor)."""

    queryset = AssetComment.objects.select_related(
        "version__asset__project", "author", "resolved_by"
    )
    serializer_class = AssetCommentSerializer
    http_method_names = ["patch", "delete", "post", "head", "options"]
    write_role = Role.COMMENTER
    action_roles = {"resolve": Role.COMMENTER, "reopen": Role.COMMENTER}

    def get_project(self, obj):
        return obj.version.asset.project

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "access_map": get_access_map(self.request),
        }

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        mine = obj.author_id == request.user.pk
        is_admin = effective_access(request, obj.version.asset.project).has(Role.ADMIN)
        is_editor = effective_access(request, obj.version.asset.project).has(
            Role.EDITOR
        )
        if self.action == "partial_update" and not mine:
            raise PermissionDenied("Seul l'auteur peut modifier ce commentaire.")
        if self.action == "destroy" and not (mine or is_admin):
            raise PermissionDenied(
                "Seul l'auteur ou un admin peut supprimer ce commentaire."
            )
        if self.action in ("resolve", "reopen"):
            root = obj if obj.parent_id is None else obj.parent
            if not (root.author_id == request.user.pk or is_editor):
                raise PermissionDenied(
                    "Seul l'auteur du fil ou un éditeur peut le résoudre."
                )

    def perform_update(self, serializer):
        serializer.save(edited_at=timezone.now())

    def _thread(self, comment):
        return comment if comment.parent_id is None else comment.parent

    @extend_schema(request=None, responses={200: AssetCommentSerializer})
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        root = self._thread(self.get_object())
        root.resolved_at = timezone.now()
        root.resolved_by = request.user
        root.save(update_fields=["resolved_at", "resolved_by", "updated_at"])
        return Response(self.get_serializer(root).data)

    @extend_schema(request=None, responses={200: AssetCommentSerializer})
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        root = self._thread(self.get_object())
        root.resolved_at = None
        root.resolved_by = None
        root.save(update_fields=["resolved_at", "resolved_by", "updated_at"])
        return Response(self.get_serializer(root).data)
