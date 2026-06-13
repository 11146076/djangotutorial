from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AiChatAPIView
from .viewsets import CategoryViewSet, PostViewSet, TagViewSet

app_name = "posts_api"

router = DefaultRouter()
router.register("posts", PostViewSet, basename="post")
router.register("categories", CategoryViewSet, basename="category")
router.register("tags", TagViewSet, basename="tag")

urlpatterns = [
    path("ai-chat/", AiChatAPIView.as_view(), name="ai_chat"),
    path("", include(router.urls)),
]
