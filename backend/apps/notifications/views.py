"""The bell: my notifications, the unread counter, marking read.
Everything is rows of request.user only."""

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import Notification
from .serializers import NotificationSerializer, UnreadCountSerializer


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Notification.objects.none()  # for the schema; see get_queryset
    serializer_class = NotificationSerializer

    def get_queryset(self):
        queryset = Notification.objects.filter(
            recipient=self.request.user
        ).select_related("actor")
        if self.request.query_params.get("unread") in ("true", "1"):
            queryset = queryset.filter(read_at__isnull=True)
        return queryset

    @extend_schema(parameters=[OpenApiParameter("unread", bool)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(responses=UnreadCountSerializer)
    @action(detail=False, url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread": services.unread_count(request.user)})

    @extend_schema(request=None, responses={200: NotificationSerializer})
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at", "updated_at"])
        return Response(self.get_serializer(notification).data)

    @extend_schema(request=None, responses={204: None})
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        Notification.objects.filter(
            recipient=request.user, read_at__isnull=True
        ).update(read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)
