"""SPEC §6: "Aucun endpoint ne filtre les droits à la main."

Every API view must either be built on a scoped mixin (rights handled
centrally), or be listed below WITH the reason it is safe. Adding an endpoint
without thinking about access rights therefore breaks the build.
"""

from django.urls import URLPattern, URLResolver, get_resolver

from apps.projects.permissions import ProjectScopedViewSet, WorkspaceScopedViewSet

ALLOWED = {
    # Public or about the signed-in user only: no project data involved.
    "SessionView": "session probe",
    "CsrfView": "sets a cookie",
    "RegisterView": "public sign-up",
    "VerifyEmailView": "public, signed token",
    "ResendVerificationView": "acts on request.user only",
    "LoginView": "public",
    "LogoutView": "acts on the session only",
    "PasswordResetRequestView": "public",
    "PasswordResetConfirmView": "public, one-time token",
    "PasswordChangeView": "acts on request.user only",
    "MeView": "acts on request.user only",
    "MyAvatarView": "acts on request.user only",
    "UserAvatarView": "any signed-in user may see an avatar",
    "UserSearchView": "public user fields only",
    "HealthView": "no data",
    "SpectacularAPIView": "schema, signed-in users",
    # Rights on a scope that is a workspace OR a project: they call
    # effective_access() / workspace_access() through views._require().
    "MembershipViewSet": "uses _require() on the membership's scope",
    "InvitationViewSet": "uses _require() on the invitation's scope",
    "InvitationLookupView": "public, unguessable token, minimal data",
}


def _api_view_classes():
    def walk(patterns, prefix=""):
        for entry in patterns:
            route = prefix + str(entry.pattern)
            if isinstance(entry, URLResolver):
                yield from walk(entry.url_patterns, route)
            elif isinstance(entry, URLPattern) and route.startswith("api/"):
                view_class = getattr(entry.callback, "cls", None) or getattr(
                    entry.callback, "view_class", None
                )
                yield route, view_class

    return list(walk(get_resolver().url_patterns))


def test_every_api_view_handles_access_rights_centrally():
    offenders = []
    for route, view_class in _api_view_classes():
        assert view_class is not None, f"function-based view on {route}"
        if issubclass(view_class, (ProjectScopedViewSet, WorkspaceScopedViewSet)):
            continue
        if view_class.__name__ not in ALLOWED:
            offenders.append(f"{route} -> {view_class.__name__}")

    assert not offenders, (
        "These views neither use a scoped mixin nor appear in ALLOWED "
        "(apps/projects/tests/test_route_audit.py):\n" + "\n".join(offenders)
    )


def test_allow_list_has_no_stale_entries():
    names = {view_class.__name__ for _, view_class in _api_view_classes()}

    assert set(ALLOWED) <= names, f"remove: {sorted(set(ALLOWED) - names)}"
