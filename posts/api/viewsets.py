from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Profile
from posts.models import Category, Collection, CommentLike, Follow, Like, Notification, Post, PostComment, Tag
from posts.notifications import notify_followers_new_post, notify_post_commented, notify_post_liked
from posts.tasks import analyze_post_health_task

from .pagination import ProfileResultsSetPagination, StandardResultsSetPagination
from .permissions import IsAuthorOrReadOnly, IsNotificationRecipient, IsStaffOrReadOnly
from .querysets import annotate_post_list, apply_post_filters, filter_visible_posts, parse_positive_id_list
from .serializers_domain import (
    CategorySerializer,
    CollectionSerializer,
    CommentCreateSerializer,
    CommentSerializer,
    NotificationSerializer,
    PostSerializer,
    PostWriteSerializer,
    ProfileSerializer,
    TagSerializer,
    ToggleResponseSerializer,
    UserProfileSerializer,
)

User = get_user_model()


@extend_schema_view(
    list=extend_schema(summary="貼文列表", tags=["Posts"]),
    retrieve=extend_schema(summary="貼文詳情", tags=["Posts"]),
    create=extend_schema(summary="建立貼文", tags=["Posts"]),
    update=extend_schema(summary="更新貼文", tags=["Posts"]),
    partial_update=extend_schema(summary="部分更新貼文", tags=["Posts"]),
    destroy=extend_schema(summary="刪除貼文", tags=["Posts"]),
)
class PostViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthorOrReadOnly]
    pagination_class = StandardResultsSetPagination
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = annotate_post_list(Post.objects.all(), self.request.user)
        qs = filter_visible_posts(qs, self.request.user)
        q = (self.request.query_params.get("q") or "").strip()[:100]
        category_ids = parse_positive_id_list(self.request.query_params.getlist("category"))
        tag_ids = parse_positive_id_list(self.request.query_params.getlist("tag"))
        author = (self.request.query_params.get("author") or "").strip()
        if author:
            qs = qs.filter(author__username__iexact=author)
        return apply_post_filters(qs, q=q, category_ids=category_ids, tag_ids=tag_ids)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PostWriteSerializer
        return PostSerializer

    def perform_create(self, serializer):
        post = serializer.save()
        notify_followers_new_post(post)
        try:
            analyze_post_health_task.delay(post.id)
        except AttributeError:
            analyze_post_health_task(post.id)

    @extend_schema(summary="按讚／取消按讚", tags=["Posts"], responses=ToggleResponseSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        post = self.get_object()
        like = post.likes.filter(user=request.user).first()
        if like:
            like.delete()
            liked = False
        else:
            like, created = Like.objects.get_or_create(user=request.user, post=post)
            if created:
                notify_post_liked(like)
            liked = True
        post.refresh_from_db(fields=["like_count"])
        return Response({"is_liked": liked, "like_count": post.like_count})

    @extend_schema(summary="收藏／取消收藏", tags=["Posts"], responses=ToggleResponseSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def collect(self, request, pk=None):
        post = self.get_object()
        collection = post.collections.filter(user=request.user).first()
        if collection:
            collection.delete()
            collected = False
        else:
            Collection.objects.get_or_create(user=request.user, post=post)
            collected = True
        return Response(
            {
                "is_collected": collected,
                "collection_count": post.collections.count(),
            }
        )


@extend_schema_view(
    list=extend_schema(
        summary="留言列表",
        tags=["Comments"],
        parameters=[
            OpenApiParameter(name="post", description="依貼文 ID 篩選", required=False, type=int),
        ],
    ),
    retrieve=extend_schema(summary="留言詳情", tags=["Comments"]),
    create=extend_schema(summary="建立留言", tags=["Comments"]),
    update=extend_schema(summary="更新留言", tags=["Comments"]),
    partial_update=extend_schema(summary="部分更新留言", tags=["Comments"]),
    destroy=extend_schema(summary="刪除留言", tags=["Comments"]),
)
class CommentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthorOrReadOnly]
    pagination_class = StandardResultsSetPagination
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = PostComment.objects.select_related("author", "author__profile", "post").order_by("created_at", "id")
        post_id = self.request.query_params.get("post")
        if post_id:
            qs = qs.filter(post_id=post_id)
        user = self.request.user
        if user.is_authenticated:
            qs = qs.annotate(
                user_has_liked=Exists(
                    CommentLike.objects.filter(comment_id=OuterRef("pk"), user_id=user.id)
                )
            )
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return CommentCreateSerializer
        return CommentSerializer

    def create(self, request, *args, **kwargs):
        serializer = CommentCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        post_id = serializer.validated_data["post_id"]
        post = Post.objects.filter(pk=post_id).first()
        if not post:
            return Response({"error": "找不到貼文。"}, status=status.HTTP_404_NOT_FOUND)
        if post.visibility == Post.VISIBILITY_PRIVATE and post.author_id != request.user.id:
            return Response({"error": "無權限在此貼文留言。"}, status=status.HTTP_403_FORBIDDEN)
        comment = serializer.save()
        notify_post_commented(comment)
        return Response(CommentSerializer(comment, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="留言按讚／取消按讚", tags=["Comments"], responses=ToggleResponseSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        comment = self.get_object()
        existing = CommentLike.objects.filter(user=request.user, comment=comment).first()
        if existing:
            existing.delete()
            liked = False
        else:
            CommentLike.objects.get_or_create(user=request.user, comment=comment)
            liked = True
        comment.refresh_from_db(fields=["like_count"])
        return Response({"is_liked": liked, "like_count": comment.like_count})


@extend_schema_view(
    list=extend_schema(summary="通知列表", tags=["Notifications"]),
    retrieve=extend_schema(summary="通知詳情", tags=["Notifications"]),
)
class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsNotificationRecipient]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related("actor", "actor__profile")
        unread = self.request.query_params.get("unread")
        if unread in ("1", "true", "yes"):
            qs = qs.filter(is_read=False)
        return qs

    @extend_schema(summary="標記單則通知為已讀", tags=["Notifications"])
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_read()
        return Response(NotificationSerializer(notification, context={"request": request}).data)

    @extend_schema(summary="全部標記為已讀", tags=["Notifications"])
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        from django.utils import timezone

        updated = Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return Response({"updated": updated})


@extend_schema_view(
    list=extend_schema(summary="我的收藏列表", tags=["Collections"]),
    destroy=extend_schema(summary="取消收藏", tags=["Collections"]),
)
class CollectionViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = CollectionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        qs = (
            Collection.objects.filter(user=user)
            .select_related("post", "post__author", "post__author__profile", "post__category")
            .prefetch_related("post__tags")
            .annotate(
                comment_count=Count("post__post_comments", distinct=True),
                collection_count=Count("post__collections", distinct=True),
            )
            .order_by("-created_at", "-id")
        )
        return qs.filter(
            Q(post__visibility=Post.VISIBILITY_PUBLIC) | Q(post__author_id=user.id)
        )


@extend_schema_view(
    list=extend_schema(summary="分類列表", tags=["Taxonomy"]),
    create=extend_schema(summary="建立分類（管理員）", tags=["Taxonomy"]),
    destroy=extend_schema(summary="刪除分類（管理員）", tags=["Taxonomy"]),
)
class CategoryViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Category.objects.order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [IsStaffOrReadOnly]


@extend_schema_view(
    list=extend_schema(summary="標籤列表", tags=["Taxonomy"]),
    create=extend_schema(summary="建立標籤（管理員）", tags=["Taxonomy"]),
    destroy=extend_schema(summary="刪除標籤（管理員）", tags=["Taxonomy"]),
)
class TagViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Tag.objects.order_by("name")
    serializer_class = TagSerializer
    permission_classes = [IsStaffOrReadOnly]


def _build_user_profile_payload(request, user: User) -> dict:
    profile, _ = Profile.objects.get_or_create(user=user)
    avatar_url = None
    if profile.avatar:
        avatar_url = request.build_absolute_uri(profile.avatar.url)
    is_following = False
    if request.user.is_authenticated and request.user.id != user.id:
        is_following = Follow.objects.filter(follower=request.user, following=user).exists()
    return {
        "id": user.id,
        "username": user.username,
        "bio": profile.bio or "",
        "dietary_preference": profile.dietary_preference or "",
        "avatar_url": avatar_url,
        "follower_count": Follow.objects.filter(following=user).count(),
        "following_count": Follow.objects.filter(follower=user).count(),
        "is_following": is_following,
    }


@extend_schema_view(
    retrieve=extend_schema(summary="使用者公開檔案", tags=["Users"]),
)
class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    lookup_field = "username"
    lookup_value_regex = r"[^/]+"

    def retrieve(self, request, username=None):
        user = self.get_object()
        data = _build_user_profile_payload(request, user)
        return Response(UserProfileSerializer(data).data)

    @extend_schema(
        summary="目前登入者檔案",
        tags=["Users"],
        request=None,
        responses=UserProfileSerializer,
        methods=["GET"],
    )
    @extend_schema(
        summary="更新目前登入者檔案",
        tags=["Users"],
        request=ProfileSerializer,
        responses=UserProfileSerializer,
        methods=["PATCH"],
    )
    @action(detail=False, methods=["get", "patch"], permission_classes=[IsAuthenticated], url_path="me")
    def me(self, request):
        if request.method == "PATCH":
            profile, _ = Profile.objects.get_or_create(user=request.user)
            serializer = ProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        data = _build_user_profile_payload(request, request.user)
        return Response(UserProfileSerializer(data).data)

    @extend_schema(summary="追蹤／取消追蹤", tags=["Users"], responses=ToggleResponseSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def follow(self, request, username=None):
        target = self.get_object()
        if target.id == request.user.id:
            return Response({"error": "不能追蹤自己。"}, status=status.HTTP_400_BAD_REQUEST)
        relation = Follow.objects.filter(follower=request.user, following=target).first()
        if relation:
            relation.delete()
            is_following = False
        else:
            Follow.objects.get_or_create(follower=request.user, following=target)
            is_following = True
        return Response(
            {
                "is_following": is_following,
                "follower_count": Follow.objects.filter(following=target).count(),
            }
        )

    @extend_schema(summary="使用者貼文列表", tags=["Users"])
    @action(detail=True, methods=["get"])
    def posts(self, request, username=None):
        user = self.get_object()
        qs = annotate_post_list(Post.objects.filter(author=user), request.user)
        if request.user.id != user.id:
            qs = qs.filter(visibility=Post.VISIBILITY_PUBLIC)
        paginator = ProfileResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = PostSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(summary="使用者留言列表", tags=["Users"])
    @action(detail=True, methods=["get"])
    def comments(self, request, username=None):
        user = self.get_object()
        qs = PostComment.objects.filter(author=user).select_related("author", "author__profile", "post").order_by(
            "-created_at", "-id"
        )
        paginator = ProfileResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = CommentSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)
