from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
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


def csrf_failure(request, reason=""):
    """JSON instead of Django's HTML page: the only client is the SPA."""
    return JsonResponse(
        {"detail": "Session expirée ou jeton CSRF invalide. Recharge la page."},
        status=403,
    )
