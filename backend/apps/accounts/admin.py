from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class SobasedUserAdmin(UserAdmin):
    """Support tool only; everyday account management happens in the app."""

    list_display = ["username", "email", "email_verified_at", "is_active", "is_staff"]
    fieldsets = UserAdmin.fieldsets + (
        (
            "SOBASED",
            {
                "fields": [
                    "email_verified_at",
                    "avatar",
                    "phone",
                    "timezone",
                    "theme",
                    "daily_digest_enabled",
                    "daily_digest_time",
                    "email_on_mention",
                    "email_on_assignment",
                    "privacy_accepted_at",
                    "anonymized_at",
                ]
            },
        ),
    )
