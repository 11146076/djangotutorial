from __future__ import annotations

from django.utils.translation import gettext as _
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """讓前端維持讀取 `error` 欄位（與舊 JsonResponse 相容）。"""
    response = exception_handler(exc, context)
    if response is None:
        return None

    if response.status_code == 401:
        response.data = {"error": _("請先登入。")}
        return response

    data = response.data
    if isinstance(data, dict) and "error" in data:
        return response

    if isinstance(data, dict) and "detail" in data and len(data) == 1:
        response.data = {"error": str(data["detail"])}
        return response

    if isinstance(data, dict):
        parts: list[str] = []
        for key, value in data.items():
            if key == "non_field_errors":
                if isinstance(value, list):
                    parts.extend(str(v) for v in value)
                else:
                    parts.append(str(value))
            elif isinstance(value, list):
                parts.extend(str(v) for v in value)
            else:
                parts.append(str(value))
        response.data = {"error": " ".join(parts) if parts else _("請求格式錯誤。")}
        return response

    response.data = {"error": str(data)}
    return response
