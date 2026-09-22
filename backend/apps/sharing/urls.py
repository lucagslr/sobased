from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("share-links", views.ShareLinkViewSet, basename="share-link")

# The public page: the secret token is the path, media URLs add a signature.
public = "public/share/<str:token>/"
urlpatterns = router.urls + [
    path(public, views.PublicShareView.as_view(), name="public-share"),
    path(
        public + "unlock/", views.PublicUnlockView.as_view(), name="public-share-unlock"
    ),
    path(
        public + "media/<int:version_id>/",
        views.PublicMediaView.as_view(),
        name="public-share-media",
    ),
    path(
        public + "download/<int:version_id>/",
        views.PublicDownloadView.as_view(),
        name="public-share-download",
    ),
    path(
        public + "peaks/<int:version_id>/",
        views.PublicPeaksView.as_view(),
        name="public-share-peaks",
    ),
    path(
        public + "thumb/<int:version_id>/",
        views.PublicThumbnailView.as_view(),
        name="public-share-thumb",
    ),
]
