from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("events", views.EventViewSet, basename="event")

urlpatterns = router.urls
