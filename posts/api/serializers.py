from __future__ import annotations

import json

from rest_framework import serializers

from posts.ai_chat import MAX_IMAGE_BYTES, decode_client_image_base64


class ChatHistoryItemSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=("user", "assistant"))
    content = serializers.CharField(max_length=4000, allow_blank=False, trim_whitespace=True)


class AiChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, max_length=4000, default="")
    history = ChatHistoryItemSerializer(many=True, required=False, default=list)
    image_base64 = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        message = (attrs.get("message") or "").strip()
        image_b64 = attrs.get("image_base64")
        image_tuple = None
        if image_b64:
            try:
                image_tuple = decode_client_image_base64(image_b64)
            except ValueError as exc:
                raise serializers.ValidationError({"image_base64": str(exc)}) from exc
        if not message and not image_tuple:
            raise serializers.ValidationError(
                {"non_field_errors": [serializers.ErrorDetail("請輸入文字或上傳圖片。", code="required")]}
            )
        attrs["message"] = message
        attrs["image_tuple"] = image_tuple
        return attrs


class AiChatMultipartSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, max_length=4000, default="")
    history = serializers.CharField(required=False, allow_blank=True, default="[]")
    image = serializers.ImageField(required=False, allow_null=True)

    def validate_history(self, value):
        if value in (None, ""):
            return []
        if isinstance(value, list):
            raw = value
        else:
            try:
                raw = json.loads(value)
            except (json.JSONDecodeError, TypeError) as exc:
                raise serializers.ValidationError("history 必須為 JSON 陣列。") from exc
        if not isinstance(raw, list):
            raise serializers.ValidationError("history 必須為陣列。")
        nested = ChatHistoryItemSerializer(data=raw, many=True)
        nested.is_valid(raise_exception=True)
        return nested.validated_data

    def validate_image(self, image):
        if not image:
            return None
        if image.size > MAX_IMAGE_BYTES:
            raise serializers.ValidationError("圖片請小於 5MB。")
        ct = (getattr(image, "content_type", "") or "").lower()
        if ct and ct not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            raise serializers.ValidationError("請上傳 JPG、PNG、GIF 或 WebP 圖片。")
        raw = image.read()
        if len(raw) > MAX_IMAGE_BYTES:
            raise serializers.ValidationError("圖片請小於 5MB。")
        return (ct or "image/jpeg", raw)

    def validate(self, attrs):
        message = (attrs.get("message") or "").strip()
        image_tuple = attrs.get("image")
        if not message and not image_tuple:
            raise serializers.ValidationError(
                {"non_field_errors": [serializers.ErrorDetail("請輸入文字或上傳圖片。", code="required")]}
            )
        attrs["message"] = message
        attrs["image_tuple"] = image_tuple
        return attrs


class AiChatResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
    suggestions = serializers.ListField(
        child=serializers.DictField(),
        required=False,
    )


class RecommendationItemSerializer(serializers.Serializer):
    post_id = serializers.IntegerField()
    title = serializers.CharField()
    author = serializers.CharField()
    category = serializers.CharField()
    like_count = serializers.IntegerField()
    reason = serializers.CharField()
    source = serializers.CharField()


class RecommendationsResponseSerializer(serializers.Serializer):
    strategy = serializers.CharField()
    collection_signals = serializers.IntegerField()
    search_signals = serializers.IntegerField()
    items = RecommendationItemSerializer(many=True)
