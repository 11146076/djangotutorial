from __future__ import annotations

import logging

from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from posts.models import Category, Post, Tag

from .post_serializers import (
    CategorySerializer,
    PostDetailSerializer,
    PostListSerializer,
    PostWriteSerializer,
    TagSerializer,
)

logger = logging.getLogger(__name__)


def _visible_posts_queryset(user):
    qs = Post.objects.select_related("author", "category").prefetch_related("tags")
    if user.is_authenticated:
        return qs.filter(Q(visibility=Post.VISIBILITY_PUBLIC) | Q(author=user))
    return qs.filter(visibility=Post.VISIBILITY_PUBLIC)


class PostViewSet(viewsets.ModelViewSet):
    """貼文 REST API：列表、詳情、建立、更新、刪除。"""

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return _visible_posts_queryset(self.request.user).order_by("-created_at", "-id")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PostWriteSerializer
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostListSerializer

    def perform_create(self, serializer):
        post = serializer.save()
        logger.info("API created post id=%s user=%s", post.id, self.request.user.username)

    def perform_update(self, serializer):
        post = serializer.save()
        logger.info("API updated post id=%s user=%s", post.id, self.request.user.username)

    def perform_destroy(self, instance):
        if instance.author_id != self.request.user.id and not self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("只能刪除自己的貼文。")
        logger.info("API deleted post id=%s user=%s", instance.id, self.request.user.username)
        instance.delete()

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        """目前使用者的貼文（含私密）。"""
        if not request.user.is_authenticated:
            return Response({"error": "請先登入。"}, status=status.HTTP_401_UNAUTHORIZED)
        qs = (
            Post.objects.filter(author=request.user)
            .select_related("author", "category")
            .prefetch_related("tags")
            .order_by("-created_at", "-id")
        )
        page = self.paginate_queryset(qs)
        serializer = PostListSerializer(page or qs, many=True, context={"request": request})
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class CategoryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class TagViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
