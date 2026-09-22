from django.urls import path

from . import views

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("auth/session/", views.SessionView.as_view(), name="auth-session"),
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path(
        "auth/verify-email/", views.VerifyEmailView.as_view(), name="auth-verify-email"
    ),
    path(
        "auth/verify-email/resend/",
        views.ResendVerificationView.as_view(),
        name="auth-verify-email-resend",
    ),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path(
        "auth/password/reset/",
        views.PasswordResetRequestView.as_view(),
        name="auth-password-reset",
    ),
    path(
        "auth/password/reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path(
        "auth/password/change/",
        views.PasswordChangeView.as_view(),
        name="auth-password-change",
    ),
    path("me/", views.MeView.as_view(), name="me"),
    path("me/avatar/", views.MyAvatarView.as_view(), name="me-avatar"),
    path("me/exports/", views.MyExportsView.as_view(), name="me-exports"),
    path(
        "me/exports/<int:pk>/download/",
        views.MyExportDownloadView.as_view(),
        name="me-export-download",
    ),
    path("me/delete/", views.DeleteAccountView.as_view(), name="me-delete"),
    path("users/search/", views.UserSearchView.as_view(), name="user-search"),
    path(
        "users/<str:username>/avatar/",
        views.UserAvatarView.as_view(),
        name="user-avatar",
    ),
]
