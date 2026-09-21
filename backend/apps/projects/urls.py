from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("projects", views.ProjectViewSet, basename="project")
router.register("memberships", views.MembershipViewSet, basename="membership")
router.register("invitations", views.InvitationViewSet, basename="invitation")

urlpatterns = [
    path(
        "invitations/lookup/<str:token>/",
        views.InvitationLookupView.as_view(),
        name="invitation-lookup",
    ),
    *router.urls,
]
