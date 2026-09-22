from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("contacts", views.ContactViewSet, basename="contact")
router.register(
    "project-contacts", views.ProjectContactViewSet, basename="project-contact"
)

urlpatterns = router.urls
