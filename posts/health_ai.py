from __future__ import annotations

import json
from typing import Any

from django.conf import settings

from .ai_chat import (
    AIProviderError,
    _build_gemini_contents,
    _build_nvidia_messages,
    _prepare_vision_image,
    call_gemini_generate,
    call_nvidia_chat_completions,
)

HEALTH_ESTIMATE_SYSTEM_PROMPT = """你是美食健康估算助手。
請根據使用者提供的食物描述與圖片內容，估算熱量與健康分級。
你只能輸出 JSON，且必須符合以下格式：
{"calories": integer, "health_rank": "A|B|C|D", "reason": "string"}

規則：
1. calories 必須是整數（單位 kcal）。
2. health_rank 只能是 A、B、C、D 其中之一。
3. reason 需為繁體中文一句話，18 字內。
4. 不能輸出任何 JSON 以外文字。
"""


def _extract_json_dict(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("AI 回覆不是有效 JSON")


def _normalize_health_payload(payload: dict[str, Any]) -> dict[str, Any]:
    calories = int(payload.get("calories", 0))
    calories = max(0, min(5000, calories))
    rank = str(payload.get("health_rank", "D")).strip().upper()
    if rank not in {"A", "B", "C", "D"}:
        rank = "D"
    reason = str(payload.get("reason", "")).strip()[:200]
    if not reason:
        reason = "整體偏高熱量，建議均衡搭配。"
    return {
        "calories": calories,
        "health_rank": rank,
        "reason": reason,
    }


def estimate_post_health(*, content: str, image: tuple[str, bytes] | None) -> tuple[dict[str, Any], str]:
    user_message = (content or "").strip()
    if not user_message:
        user_message = "請根據圖片估算這份餐點熱量與健康等級。"

    nvidia_key = (getattr(settings, "NVIDIA_API_KEY", "") or "").strip()
    nvidia_model = getattr(settings, "NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct")
    nvidia_url = getattr(settings, "NVIDIA_INVOKE_URL", "").strip() or "https://integrate.api.nvidia.com/v1/chat/completions"
    gemini_key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    gemini_model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")

    message_for_model = f"{HEALTH_ESTIMATE_SYSTEM_PROMPT}\n\n使用者內容：{user_message}"
    vision_image = _prepare_vision_image(image)

    if nvidia_key:
        msgs = _build_nvidia_messages([], message_for_model, vision_image)
        msgs[0]["content"] = HEALTH_ESTIMATE_SYSTEM_PROMPT
        raw = call_nvidia_chat_completions(
            messages=msgs,
            api_key=nvidia_key,
            model=nvidia_model,
            invoke_url=nvidia_url,
            temperature=0.2,
            max_tokens=120,
        )
        return _normalize_health_payload(_extract_json_dict(raw)), nvidia_model

    if gemini_key:
        contents = _build_gemini_contents([], message_for_model, vision_image)
        raw = call_gemini_generate(contents=contents, model=gemini_model, api_key=gemini_key)
        return _normalize_health_payload(_extract_json_dict(raw)), gemini_model

    raise AIProviderError("尚未設定可用的 AI API Key。", transient=False)
