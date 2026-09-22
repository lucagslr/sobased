from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("activity", views.ActivityViewSet, basename="activity")

urlpatterns = router.urls
