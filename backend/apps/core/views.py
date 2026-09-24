from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Used by monitoring and by the deploy script: are Postgres and Redis up?"""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: None})
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        cache.set("health", "ok", 5)
        return Response({"status": "ok"})


class SiteInfoSerializer(serializers.Serializer):
    name = serializers.CharField()
    hosting_location = serializers.ChoiceField(choices=[("ch", "Suisse"), ("eu", "UE")])
    hosting_provider = serializers.CharField()
    contact_email = serializers.CharField()


class SiteView(APIView):
    """Public constants the privacy page displays (SPEC §16): where the data
    is hosted and whom to write to. Nothing about any user."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=SiteInfoSerializer)
    def get(self, request):
        return Response(
            {
                "name": "Faiblegraine",
                "hosting_location": settings.HOSTING_LOCATION,
                "hosting_provider": settings.HOSTING_PROVIDER,
                "contact_email": settings.PRIVACY_CONTACT_EMAIL,
            }
        )


def csrf_failure(request, reason=""):
    """JSON instead of Django's HTML page: the only client is the SPA."""
    return JsonResponse(
        {"detail": "Session expirée ou jeton CSRF invalide. Recharge la page."},
        status=403,
    )
