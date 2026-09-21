from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("tasks", views.TaskViewSet, basename="task")
router.register(
    "checklist-items", views.ChecklistItemViewSet, basename="checklist-item"
)
router.register("task-comments", views.TaskCommentViewSet, basename="task-comment")

urlpatterns = router.urls
