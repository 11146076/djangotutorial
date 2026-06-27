from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AiChatAPIView, RecommendationsAPIView
from .viewsets import (
    CategoryViewSet,
    CollectionViewSet,
    CommentViewSet,
    NotificationViewSet,
    PostViewSet,
    TagViewSet,
    UserViewSet,
)

app_name = "posts_api"

router = DefaultRouter()
router.register("posts", PostViewSet, basename="post")
router.register("comments", CommentViewSet, basename="comment")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("collections", CollectionViewSet, basename="collection")
router.register("categories", CategoryViewSet, basename="category")
router.register("tags", TagViewSet, basename="tag")
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("ai-chat/", AiChatAPIView.as_view(), name="ai_chat"),
    path("recommendations/", RecommendationsAPIView.as_view(), name="recommendations"),
    path("", include(router.urls)),
]
