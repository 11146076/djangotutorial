from __future__ import annotations

import bleach
from django.conf import settings
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import Profile
from posts.forms import PostEditForm
from posts.models import Category, Collection, Notification, Post, PostComment, Tag

User = get_user_model()


class UserBriefSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "avatar_url")

    def get_avatar_url(self, obj) -> str | None:
        profile = getattr(obj, "profile", None)
        if profile and profile.avatar:
            request = self.context.get("request")
            url = profile.avatar.url
            return request.build_absolute_uri(url) if request else url
        return None


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Profile
        fields = ("username", "bio", "dietary_preference", "avatar")
        read_only_fields = ("username",)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name")


class PostHealthInsightBriefSerializer(serializers.Serializer):
    calories = serializers.IntegerField(allow_null=True)
    health_rank = serializers.CharField(allow_null=True)
    reason = serializers.CharField(allow_null=True)
    status = serializers.CharField()


class PostSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comment_count = serializers.IntegerField(read_only=True, required=False)
    collection_count = serializers.IntegerField(read_only=True, required=False)
    is_liked = serializers.SerializerMethodField()
    is_collected = serializers.SerializerMethodField()
    image_urls = serializers.SerializerMethodField()
    health_insight = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "title",
            "content",
            "visibility",
            "like_count",
            "author",
            "category",
            "tags",
            "comment_count",
            "collection_count",
            "is_liked",
            "is_collected",
            "image_urls",
            "health_insight",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "like_count",
            "author",
            "created_at",
            "updated_at",
        )

    def get_is_liked(self, obj) -> bool:
        if hasattr(obj, "user_has_liked"):
            return bool(obj.user_has_liked)
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return obj.likes.filter(user_id=user.id).exists()

    def get_is_collected(self, obj) -> bool:
        if hasattr(obj, "user_has_collected"):
            return bool(obj.user_has_collected)
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return obj.collections.filter(user_id=user.id).exists()

    def get_image_urls(self, obj) -> list[str]:
        request = self.context.get("request")
        urls = []
        for image in obj.gallery_images():
            url = image.url
            urls.append(request.build_absolute_uri(url) if request else url)
        return urls

    @extend_schema_field(PostHealthInsightBriefSerializer(allow_null=True))
    def get_health_insight(self, obj):
        insight = obj.latest_health_insight
        if not insight:
            return None
        return PostHealthInsightBriefSerializer(insight).data


class PostWriteSerializer(serializers.ModelSerializer):
    new_category = serializers.CharField(required=False, allow_blank=True, write_only=True)
    new_tags = serializers.CharField(required=False, allow_blank=True, write_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False, write_only=True, source="tags"
    )
    gallery = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        write_only=True,
        allow_empty=True,
    )
    image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    image2 = serializers.ImageField(required=False, allow_null=True, write_only=True)
    image3 = serializers.ImageField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Post
        fields = (
            "title",
            "content",
            "visibility",
            "category",
            "tag_ids",
            "new_category",
            "new_tags",
            "gallery",
            "image",
            "image2",
            "image3",
        )

    def validate_content(self, value):
        from django.utils.html import strip_tags

        text_only = strip_tags(value or "").replace("\xa0", " ").strip()
        if not text_only:
            raise serializers.ValidationError("請輸入貼文內容。")
        return bleach.clean(
            value,
            tags=getattr(settings, "BLEACH_ALLOWED_TAGS", None),
            attributes=getattr(settings, "BLEACH_ALLOWED_ATTRIBUTES", None),
            protocols=getattr(settings, "BLEACH_ALLOWED_PROTOCOLS", None),
            strip=True,
        )

    def _apply_gallery(self, post: Post, files: list) -> None:
        if not files:
            return
        if len(files) > 3:
            raise serializers.ValidationError({"gallery": "最多只能上傳 3 張圖片。"})
        post.image = files[0]
        post.image2 = files[1] if len(files) > 1 else None
        post.image3 = files[2] if len(files) > 2 else None

    def create(self, validated_data):
        gallery = validated_data.pop("gallery", [])
        image = validated_data.pop("image", None)
        image2 = validated_data.pop("image2", None)
        image3 = validated_data.pop("image3", None)
        new_category = validated_data.pop("new_category", "")
        new_tags = validated_data.pop("new_tags", "")
        tags = validated_data.pop("tags", None)

        post = Post(**validated_data)
        post.author = self.context["request"].user
        files = list(gallery)
        for extra in (image, image2, image3):
            if extra:
                files.append(extra)
        self._apply_gallery(post, files)

        if new_category:
            category_obj, _ = Category.objects.get_or_create(name=new_category.strip())
            post.category = category_obj

        post.save()
        if tags is not None:
            post.tags.set(tags)
        if new_tags:
            form = PostEditForm()
            for name in form._parse_new_tags(new_tags):
                tag_obj, _ = Tag.objects.get_or_create(name=name)
                post.tags.add(tag_obj)
        return post

    def update(self, instance, validated_data):
        gallery = validated_data.pop("gallery", None)
        image = validated_data.pop("image", None)
        image2 = validated_data.pop("image2", None)
        image3 = validated_data.pop("image3", None)
        new_category = validated_data.pop("new_category", "")
        new_tags = validated_data.pop("new_tags", "")
        tags = validated_data.pop("tags", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if new_category:
            category_obj, _ = Category.objects.get_or_create(name=new_category.strip())
            instance.category = category_obj

        files = []
        if gallery is not None:
            files.extend(gallery)
        for extra in (image, image2, image3):
            if extra:
                files.append(extra)
        if files:
            self._apply_gallery(instance, files)

        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        if new_tags:
            form = PostEditForm()
            for name in form._parse_new_tags(new_tags):
                tag_obj, _ = Tag.objects.get_or_create(name=name)
                instance.tags.add(tag_obj)
        return instance


class CommentSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)
    post_id = serializers.IntegerField(source="post.id", read_only=True)
    parent_id = serializers.IntegerField(read_only=True, allow_null=True)
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = PostComment
        fields = (
            "id",
            "post_id",
            "parent_id",
            "content",
            "author",
            "like_count",
            "is_liked",
            "is_locked",
            "is_pinned",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "author", "like_count", "is_locked", "is_pinned", "created_at", "updated_at")

    def get_is_liked(self, obj) -> bool:
        if hasattr(obj, "user_has_liked"):
            return bool(obj.user_has_liked)
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return obj.comment_likes.filter(user_id=user.id).exists()


class CommentCreateSerializer(serializers.ModelSerializer):
    post_id = serializers.IntegerField(write_only=True)
    parent_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = PostComment
        fields = ("post_id", "content", "parent_id")

    def validate_content(self, value):
        content = (value or "").strip()
        if not content:
            raise serializers.ValidationError("留言內容不可為空。")
        if len(content) > 2000:
            return content[:2000]
        return content

    def validate_parent_id(self, value):
        if value is None:
            return None
        post_id = self.initial_data.get("post_id")
        parent = PostComment.objects.filter(pk=value, post_id=post_id).first()
        if not parent:
            raise serializers.ValidationError("找不到父留言。")
        if parent.is_locked:
            raise serializers.ValidationError("此留言已鎖定，無法回覆。")
        return parent

    def create(self, validated_data):
        post_id = validated_data.pop("post_id")
        parent = validated_data.pop("parent_id", None)
        post = Post.objects.get(pk=post_id)
        comment = PostComment.objects.create(
            post=post,
            author=self.context["request"].user,
            content=validated_data["content"],
            parent=parent,
        )
        if parent:
            comment.root_id = parent.root_id or parent.id
        else:
            comment.root_id = comment.id
        comment.save(update_fields=["root"])
        return comment


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserBriefSerializer(read_only=True)
    message = serializers.SerializerMethodField()
    target_url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "notification_type",
            "message",
            "target_url",
            "actor",
            "post_id",
            "comment_id",
            "is_read",
            "created_at",
            "read_at",
        )
        read_only_fields = fields

    def get_message(self, obj) -> str:
        return obj.message()

    def get_target_url(self, obj) -> str:
        return obj.target_url()


class CollectionSerializer(serializers.ModelSerializer):
    post = PostSerializer(read_only=True)

    class Meta:
        model = Collection
        fields = ("id", "post", "created_at")
        read_only_fields = fields


class ToggleResponseSerializer(serializers.Serializer):
    is_liked = serializers.BooleanField(required=False)
    is_collected = serializers.BooleanField(required=False)
    like_count = serializers.IntegerField(required=False)
    collection_count = serializers.IntegerField(required=False)
    is_following = serializers.BooleanField(required=False)
    follower_count = serializers.IntegerField(required=False)


class UserProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    bio = serializers.CharField(allow_blank=True)
    dietary_preference = serializers.CharField(allow_blank=True)
    avatar_url = serializers.CharField(allow_null=True)
    follower_count = serializers.IntegerField()
    following_count = serializers.IntegerField()
    is_following = serializers.BooleanField(required=False)
