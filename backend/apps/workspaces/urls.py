from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("workspaces", views.WorkspaceViewSet, basename="workspace")
router.register("project-types", views.ProjectTypeViewSet, basename="project-type")
router.register("tags", views.TagViewSet, basename="tag")

urlpatterns = router.urls
