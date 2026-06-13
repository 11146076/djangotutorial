from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from posts.models import Category, Post, Tag

User = get_user_model()


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")
        read_only_fields = fields


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name")


class PostListSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    like_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = (
            "id",
            "title",
            "author",
            "category",
            "tags",
            "visibility",
            "like_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PostDetailSerializer(PostListSerializer):
    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ("content",)


class PostWriteSerializer(serializers.ModelSerializer):
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        required=False,
        source="tags",
    )

    class Meta:
        model = Post
        fields = ("title", "content", "category", "tag_ids", "visibility")

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if instance.author_id != self.context["request"].user.id:
            raise serializers.ValidationError("只能編輯自己的貼文。")
        return super().update(instance, validated_data)
