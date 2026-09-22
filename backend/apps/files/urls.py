from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("assets", views.AssetViewSet, basename="asset")
router.register("asset-versions", views.AssetVersionViewSet, basename="asset-version")
router.register("asset-comments", views.AssetCommentViewSet, basename="asset-comment")

urlpatterns = router.urls
