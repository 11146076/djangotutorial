from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

from .ai_chat import (
    AIProviderError,
    _ai_settings,
    _build_gemini_contents,
    _build_nvidia_messages,
    _prepare_vision_image,
    call_gemini_generate,
    call_nvidia_chat_completions,
)

logger = logging.getLogger("posts.health_ai")

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


def _health_request_timeout() -> int:
    raw = int(getattr(settings, "AI_HEALTH_REQUEST_TIMEOUT_SECONDS", 0) or 0)
    if raw > 0:
        return max(30, raw)
    base = int(getattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 35) or 35)
    return max(60, base)


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


def _build_health_messages(*, user_message: str, vision_image: tuple[str, bytes] | None) -> list[dict[str, Any]]:
    message_for_model = f"{HEALTH_ESTIMATE_SYSTEM_PROMPT}\n\n使用者內容：{user_message}"
    msgs = _build_nvidia_messages([], message_for_model, vision_image)
    msgs[0]["content"] = HEALTH_ESTIMATE_SYSTEM_PROMPT
    return msgs


def _call_nvidia_health(
    *,
    api_key: str,
    model: str,
    invoke_url: str,
    user_message: str,
    vision_image: tuple[str, bytes] | None,
    timeout_seconds: int,
) -> tuple[dict[str, Any], str]:
    raw = call_nvidia_chat_completions(
        messages=_build_health_messages(user_message=user_message, vision_image=vision_image),
        api_key=api_key,
        model=model,
        invoke_url=invoke_url,
        temperature=0.2,
        max_tokens=120,
        timeout_seconds=timeout_seconds,
    )
    return _normalize_health_payload(_extract_json_dict(raw)), model


def _call_gemini_health(
    *,
    api_key: str,
    model: str,
    user_message: str,
    vision_image: tuple[str, bytes] | None,
    timeout_seconds: int,
) -> tuple[dict[str, Any], str]:
    message_for_model = f"{HEALTH_ESTIMATE_SYSTEM_PROMPT}\n\n使用者內容：{user_message}"
    contents = _build_gemini_contents([], message_for_model, vision_image)
    raw = call_gemini_generate(
        contents=contents,
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    return _normalize_health_payload(_extract_json_dict(raw)), model


def estimate_post_health(*, content: str, image: tuple[str, bytes] | None) -> tuple[dict[str, Any], str]:
    user_message = (content or "").strip()
    if not user_message:
        user_message = "請根據圖片估算這份餐點熱量與健康等級。"

    cfg = _ai_settings()
    vision_image = _prepare_vision_image(image)
    timeout_seconds = _health_request_timeout()
    errors: list[str] = []

    if cfg["nvidia_key"]:
        try:
            return _call_nvidia_health(
                api_key=cfg["nvidia_key"],
                model=cfg["nvidia_model"],
                invoke_url=cfg["nvidia_url"],
                user_message=user_message,
                vision_image=vision_image,
                timeout_seconds=timeout_seconds,
            )
        except AIProviderError as exc:
            logger.warning("health nvidia primary failed: %s", exc.message)
            if not exc.transient:
                raise
            errors.append(exc.message)

    if cfg["nvidia_backup_key"] and cfg["nvidia_backup_key"] != cfg["nvidia_key"]:
        try:
            return _call_nvidia_health(
                api_key=cfg["nvidia_backup_key"],
                model=cfg["nvidia_backup_model"],
                invoke_url=cfg["nvidia_url"],
                user_message=user_message,
                vision_image=vision_image,
                timeout_seconds=timeout_seconds,
            )
        except AIProviderError as exc:
            logger.warning("health nvidia backup failed: %s", exc.message)
            if not exc.transient:
                raise
            errors.append(exc.message)

    if cfg["gemini_key"]:
        try:
            return _call_gemini_health(
                api_key=cfg["gemini_key"],
                model=cfg["gemini_model"],
                user_message=user_message,
                vision_image=vision_image,
                timeout_seconds=timeout_seconds,
            )
        except AIProviderError as exc:
            logger.warning("health gemini failed: %s", exc.message)
            if not exc.transient:
                raise
            errors.append(exc.message)

    if errors:
        raise AIProviderError(errors[-1], transient=True)

    raise AIProviderError("尚未設定可用的 AI API Key。", transient=False)
