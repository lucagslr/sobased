import zoneinfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .emails import send_verification_email
from .models import DataExport, username_validator

User = get_user_model()


def avatar_url(user) -> str | None:
    """API URL of the avatar, or None (the front then shows initials).

    The file name is random, so it doubles as a cache-busting version.
    """
    if not user.avatar:
        return None
    version = user.avatar.name.rsplit("/", 1)[-1].split(".")[0]
    return f"/api/users/{user.username}/avatar/?v={version}"


def _check_password_strength(password, user=None):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc


class PublicUserSerializer(serializers.ModelSerializer):
    """The ONLY shape in which a user is exposed to other users (SPEC §4).

    Never add e-mail, phone or id here: the search endpoint is open to every
    signed-in user.
    """

    display_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["username", "display_name", "avatar_url"]

    def get_avatar_url(self, user) -> str | None:
        return avatar_url(user)


class MeSerializer(serializers.ModelSerializer):
    """The signed-in user's own profile and preferences."""

    display_name = serializers.CharField(read_only=True)
    email_verified = serializers.BooleanField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    # Server limits the front needs before sending anything (upload size).
    max_upload_mb = serializers.SerializerMethodField()
    # Only required when the e-mail changes (see validate()).
    current_password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "email_verified",
            "first_name",
            "last_name",
            "display_name",
            "avatar_url",
            "phone",
            "timezone",
            "theme",
            "daily_digest_enabled",
            "daily_digest_time",
            "email_on_mention",
            "email_on_assignment",
            "max_upload_mb",
            "current_password",
        ]
        # The username is immutable: "@username" mentions are stored as text.
        read_only_fields = ["id", "username"]

    def get_avatar_url(self, user) -> str | None:
        return avatar_url(user)

    def get_max_upload_mb(self, user) -> int:
        return settings.MAX_UPLOAD_MB

    def validate_timezone(self, value):
        if value not in zoneinfo.available_timezones():
            raise serializers.ValidationError("Fuseau horaire inconnu.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        others = User.objects.exclude(pk=self.instance.pk)
        if others.filter(email=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet e-mail.")
        return value

    def validate(self, attrs):
        password = attrs.pop("current_password", None)
        new_email = attrs.get("email")
        if new_email and new_email != self.instance.email:
            # The e-mail is the password-recovery channel: changing it with a
            # stolen session must not be enough to take the account over.
            if not password or not self.instance.check_password(password):
                raise serializers.ValidationError(
                    {"current_password": "Mot de passe requis pour changer d'e-mail."}
                )
        return attrs

    def update(self, instance, validated_data):
        email_changed = (
            "email" in validated_data and validated_data["email"] != instance.email
        )
        if email_changed:
            instance.email_verified_at = None
        user = super().update(instance, validated_data)
        if email_changed:
            send_verification_email(user)
        return user


class SessionSerializer(serializers.Serializer):
    """Shape of GET /api/auth/session/: the profile, or null when signed out."""

    user = MeSerializer(allow_null=True)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(validators=[username_validator])
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    accept_privacy = serializers.BooleanField()
    # Token of the invitation link the visitor came from, if any.
    invitation = serializers.CharField(required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet e-mail.")
        return value

    def validate_accept_privacy(self, value):
        if not value:
            raise serializers.ValidationError(
                "Tu dois accepter la politique de confidentialité."
            )
        return value

    def validate(self, attrs):
        # Validated here (not in validate_password) so the similarity check can
        # compare the password with the username and e-mail.
        candidate = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return value

    def validate_new_password(self, value):
        _check_password_strength(value, self.context["request"].user)
        return value


class DataExportSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=DataExport.Status.choices, read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = DataExport
        fields = [
            "id",
            "status",
            "size_bytes",
            "error",
            "expires_at",
            "created_at",
            "is_available",
        ]
        read_only_fields = fields


class DeleteAccountSerializer(serializers.Serializer):
    """The password is asked again: a stolen session must not be enough."""

    password = serializers.CharField(write_only=True)
