from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ForbiddenWordViewSet, ModerationLogViewSet, ModerationTestAPIView

router = DefaultRouter()
router.register(r"rules", ForbiddenWordViewSet, basename="moderation-rule")
router.register(r"logs", ModerationLogViewSet, basename="moderation-log")

urlpatterns = router.urls + [
    path("test/", ModerationTestAPIView.as_view(), name="moderation-test"),
]
