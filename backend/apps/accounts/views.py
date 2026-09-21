"""Authentication, profile and user search endpoints.

Session authentication only (no JWT). Anonymous POST endpoints are wrapped in
csrf_protect explicitly, because DRF's SessionAuthentication only enforces
CSRF once a user is authenticated.
"""

from django.conf import settings
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.module_loading import import_string
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.files import protected_file_response

from .avatars import InvalidImage, build_avatar
from .emails import send_password_reset_email, send_verification_email
from .serializers import (
    EmailSerializer,
    LoginSerializer,
    MeSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    SessionSerializer,
    TokenSerializer,
    _check_password_strength,
)
from .signals import email_verified
from .tokens import read_email_token

User = get_user_model()

OK = {"detail": "ok"}


class PublicAPIView(APIView):
    """Base for endpoints reachable without a session: CSRF + scoped throttle."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class CsrfView(APIView):
    """First call made by the front: sets the csrftoken cookie."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response(OK)


class SessionView(APIView):
    """Who am I? Always 200, so that a signed-out visitor does not produce a
    401 error in the browser console. Also sets the CSRF cookie: it is the
    first call the front makes."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: SessionSerializer})
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        return Response({"user": MeSerializer(user).data if user else None})


class RegisterView(PublicAPIView):
    throttle_scope = "register"

    @extend_schema(request=RegisterSerializer, responses={201: MeSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # An invitation link proves the visitor owns the invited address: if
        # they sign up with it, the e-mail is verified at once, and sign-up is
        # allowed even when registration is closed.
        resolve = import_string(settings.INVITATION_EMAIL_RESOLVER)
        invited = resolve(data.get("invitation", "")) == data["email"]
        if not settings.REGISTRATION_OPEN and not invited:
            return Response(
                {
                    "detail": "Les inscriptions se font uniquement sur invitation, "
                    "avec l'adresse e-mail qui a reçu l'invitation."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        user = User.objects.create_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            privacy_accepted_at=timezone.now(),
            email_verified_at=timezone.now() if invited else None,
        )
        if invited:
            email_verified.send(sender=User, user=user)  # applies the invitation
        else:
            send_verification_email(user)
        # An unverified account can sign in; it just cannot invite or be
        # invited by e-mail yet (SPECIFICATIONS §1.4).
        login(request, user)
        return Response(MeSerializer(user).data, status=status.HTTP_201_CREATED)


class VerifyEmailView(PublicAPIView):
    throttle_scope = None  # the signed token is not guessable

    @extend_schema(request=TokenSerializer, responses={200: None})
    def post(self, request):
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = read_email_token(serializer.validated_data["token"])
        user = (
            payload
            and User.objects.filter(
                pk=payload["uid"], email=payload["email"], is_active=True
            ).first()
        )
        if not user:
            return Response(
                {"detail": "Lien invalide ou expiré."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.email_verified_at:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
            email_verified.send(sender=User, user=user)
        return Response(OK)


class ResendVerificationView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "verify_email"

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        if not request.user.email_verified:
            send_verification_email(request.user)
        return Response(OK)


def _login_failures_key(username: str) -> str:
    return f"login-failures:{username.strip().lower()}"


class LoginView(PublicAPIView):
    """Username + password login with two rate limits.

    - per IP: DRF scoped throttle "login" (5/min);
    - per username: only FAILED attempts are counted (10/hour), so an attacker
      cannot lock a victim out just by spamming the endpoint with successes,
      and a legitimate user is never blocked by their own logins.
    """

    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: MeSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        key = _login_failures_key(username)

        if cache.get(key, 0) >= settings.LOGIN_MAX_FAILURES_PER_HOUR:
            return Response(
                {"detail": "Trop de tentatives. Réessaie dans une heure."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = authenticate(
            request, username=username, password=serializer.validated_data["password"]
        )
        if user is None:
            # add() is a no-op if the key exists: the 1 h window starts at the
            # first failure and is not extended by the following ones.
            cache.add(key, 0, timeout=3600)
            cache.incr(key)
            return Response(
                {"detail": "Nom d'utilisateur ou mot de passe incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache.delete(key)
        login(request, user)  # also rotates the session key
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        logout(request)
        return Response(OK)


class PasswordResetRequestView(PublicAPIView):
    throttle_scope = "password_reset"

    @extend_schema(request=EmailSerializer, responses={200: None})
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user and user.has_usable_password():
            send_password_reset_email(user)
        # Same answer whether the account exists or not (no e-mail enumeration).
        return Response(OK)


class PasswordResetConfirmView(PublicAPIView):
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: None})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = User.objects.get(
                pk=force_str(urlsafe_base64_decode(data["uid"])), is_active=True
            )
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if not user or not default_token_generator.check_token(user, data["token"]):
            return Response(
                {"detail": "Lien invalide ou expiré."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            _check_password_strength(data["new_password"], user)
        except ValidationError as exc:
            return Response(
                {"new_password": exc.detail}, status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(data["new_password"])
        # Receiving the link proves ownership of the mailbox.
        newly_verified = not user.email_verified_at
        if newly_verified:
            user.email_verified_at = timezone.now()
        user.save()
        if newly_verified:
            email_verified.send(sender=User, user=user)
        cache.delete(_login_failures_key(user.username))
        return Response(OK)


class PasswordChangeView(APIView):
    @extend_schema(request=PasswordChangeSerializer, responses={200: None})
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        # Changing the password invalidates every session; keep this one alive.
        update_session_auth_hash(request, request.user)
        return Response(OK)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class MyAvatarView(APIView):
    parser_classes = [MultiPartParser]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"avatar": {"type": "string", "format": "binary"}},
            }
        },
        responses={200: MeSerializer},
    )
    def put(self, request):
        upload = request.FILES.get("avatar")
        if upload is None:
            return Response(
                {"avatar": ["Aucun fichier reçu."]}, status=status.HTTP_400_BAD_REQUEST
            )
        if upload.size > settings.AVATAR_MAX_MB * 1024 * 1024:
            return Response(
                {"avatar": [f"Image trop lourde ({settings.AVATAR_MAX_MB} Mo max)."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            content = build_avatar(upload)
        except InvalidImage:
            return Response(
                {"avatar": ["Ce fichier n'est pas une image lisible."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
        user.avatar.save(f"{user.pk}-{content.name}", content, save=True)
        return Response(MeSerializer(user).data)

    @extend_schema(responses={200: MeSerializer})
    def delete(self, request):
        if request.user.avatar:
            request.user.avatar.delete(save=True)
        return Response(MeSerializer(request.user).data)


class UserAvatarView(APIView):
    """Avatar image of any user, for signed-in users only."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={(200, "image/webp"): bytes})
    def get(self, request, username):
        user = get_object_or_404(User, username__iexact=username, is_active=True)
        if not user.avatar:
            return Response(status=status.HTTP_404_NOT_FOUND)
        # The URL carries a version (?v=), so the browser may cache for long.
        return protected_file_response(
            user.avatar,
            content_type="image/webp",
            cache_control="private, max-age=604800, immutable",
        )


class UserSearchView(generics.ListAPIView):
    """Username autocompletion used to invite people.

    Returns username, display name and avatar only, never e-mail or id.
    """

    serializer_class = PublicUserSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "user_search"
    pagination_class = None

    def get_queryset(self):
        query = self.request.query_params.get("q", "").strip().lstrip("@")
        if len(query) < 2:
            return User.objects.none()
        return (
            User.objects.filter(is_active=True, anonymized_at__isnull=True)
            .filter(
                Q(username__istartswith=query)
                | Q(first_name__istartswith=query)
                | Q(last_name__istartswith=query)
            )
            .exclude(pk=self.request.user.pk)
            .order_by("username")[:10]
        )
