from __future__ import annotations

import logging

from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AiChatMultipartSerializer, AiChatRequestSerializer, AiChatResponseSerializer
from .services import run_ai_chat

logger = logging.getLogger(__name__)


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
