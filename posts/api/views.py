from __future__ import annotations

import logging

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AiChatMultipartSerializer,
    AiChatRequestSerializer,
    AiChatResponseSerializer,
    RecommendationItemSerializer,
    RecommendationsResponseSerializer,
)
from .services import run_ai_chat
from posts.recommendations import get_personalized_recommendations

logger = logging.getLogger(__name__)


@extend_schema(
    tags=["AI Chat"],
    summary="AI 美食助理對話",
    description=(
        "送出文字或圖片給 AI 美食助理，取得回覆與可選的站內推薦建議。\n\n"
        "支援兩種 Content-Type：\n"
        "- `application/json`：可附 `image_base64`（data URL 或純 base64）\n"
        "- `multipart/form-data`：可附 `image` 檔案欄位\n\n"
        "需先登入（SessionAuthentication）。"
    ),
    request={
        "application/json": AiChatRequestSerializer,
        "multipart/form-data": AiChatMultipartSerializer,
    },
    responses={200: AiChatResponseSerializer},
    examples=[
        OpenApiExample(
            "JSON 文字提問",
            value={
                "message": "今晚想吃清淡一點，有什麼推薦？",
                "history": [
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好！想吃什么类型的料理？"},
                ],
            },
            request_only=True,
            media_type="application/json",
        ),
        OpenApiExample(
            "成功回應",
            value={
                "reply": "可以試試 **蔬菜湯麵** 或清蒸魚，口味清爽。",
                "suggestions": [
                    {"type": "search", "name": "蔬菜湯麵", "query": "蔬菜湯麵"},
                ],
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class AiChatAPIView(APIView):
    """
    AI 美食助理 API（DRF）。

    - JSON：`{"message": "...", "history": [...], "image_base64": "data:image/..."}`
    - Multipart：`message`、`history`（JSON 字串）、`image`（檔案）
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        content_type = (request.content_type or "").lower()

        if "application/json" in content_type:
            serializer = AiChatRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            message = data["message"]
            history = data.get("history") or []
            image_tuple = data.get("image_tuple")
        else:
            serializer = AiChatMultipartSerializer(data=request.data, files=request.FILES)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            message = data["message"]
            history = data.get("history") or []
            image_tuple = data.get("image_tuple")

        result = run_ai_chat(
            user=request.user,
            message=message,
            image_tuple=image_tuple,
            history=history,
        )
        out = AiChatResponseSerializer(result)
        return Response(out.data, status=status.HTTP_200_OK)


class RecommendationsAPIView(APIView):
    """個人化貼文推薦（依收藏與搜尋紀錄）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = 10
        try:
            limit = max(1, min(20, int(request.GET.get("limit", "10"))))
        except (TypeError, ValueError):
            limit = 10

        items, meta = get_personalized_recommendations(request.user, limit=limit)
        payload = {
            "strategy": meta.get("strategy", "none"),
            "collection_signals": meta.get("collection_signals", 0),
            "search_signals": meta.get("search_signals", 0),
            "items": [
                {
                    "post_id": item.post.id,
                    "title": item.post.title or "",
                    "author": item.post.author.username,
                    "category": item.post.category.name if item.post.category else "",
                    "like_count": item.post.like_count,
                    "reason": item.reason,
                    "source": item.source,
                }
                for item in items
            ],
        }
        return Response(RecommendationsResponseSerializer(payload).data, status=status.HTTP_200_OK)
