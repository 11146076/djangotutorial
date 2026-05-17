"""
AI chat provider helpers for the site.

Providers:
- NVIDIA Integrate (OpenAI-compatible /v1/chat/completions; supports vision models)
- Google Gemini (generateContent; supports optional inline image)
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 20
MAX_MESSAGE_CHARS = 4000
MAX_IMAGE_BYTES = 5 * 1024 * 1024
_TARGET_JPEG_BYTES = 120 * 1024

SYSTEM_PROMPT = """你是「等等吃啥」網站的 AI 美食助理。
規則：
- 一律用繁體中文回答。
- 針對美食、餐廳、聚餐、料理、營養與飲食建議提供具體可執行的回答。
- 如果使用者上傳食物照片：先描述你看到的內容，再估算大概熱量（若不確定要說明假設與不確定性）。
- 資訊不足時先問 1–3 個問題釐清。
- 回答請務必簡明扼要，除非使用者要求，否則請保持在 150 字以內。
- 不要提供與美食無關的資訊或建議。
"""

_ALLOWED_IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})

DEFAULT_NVIDIA_INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_NVIDIA_MODEL = "meta/llama-3.2-11b-vision-instruct"

GEMINI_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class AIProviderError(Exception):
    def __init__(self, message: str, *, transient: bool = False):
        super().__init__(message)
        self.message = message
        self.transient = transient


def _request_timeout() -> int:
    return max(10, int(getattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 60)))


def _http_post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    *,
    provider: str,
) -> dict[str, Any]:
    """POST JSON 並回傳解析後的 dict；記錄耗時與 payload 大小。"""
    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
    timeout = _request_timeout()
    logger.debug(
        "%s request url=%s bytes=%d timeout=%ds",
        provider,
        url.split("?")[0],
        len(body_bytes),
        timeout,
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        elapsed = time.monotonic() - started
        logger.info(
            "%s response ok elapsed=%.2fs response_bytes=%d",
            provider,
            elapsed,
            len(raw),
        )
        return json.loads(raw.decode("utf-8"))
    except TimeoutError:
        elapsed = time.monotonic() - started
        logger.warning("%s timeout after %.2fs", provider, elapsed)
        raise
    except urllib.error.HTTPError as exc:
        elapsed = time.monotonic() - started
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        logger.warning(
            "%s http_error code=%s elapsed=%.2fs body=%s",
            provider,
            exc.code,
            elapsed,
            err_body[:300],
        )
        raise


def _demo_reply(message: str, image: bool) -> str:
    if image:
        return _("尚未設定可用的 AI API Key（NVIDIA_API_KEY 或 GEMINI_API_KEY）。")
    if message:
        return _("（示範模式）你說：%(message)s\n\n請在 `.env` 設定 NVIDIA_API_KEY 或 GEMINI_API_KEY。") % {
            "message": message
        }
    return _("（示範模式）請輸入訊息。")


def _normalize_history(history: list[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(history, list):
        return out
    for item in history[-MAX_HISTORY_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        out.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    return out


def decode_client_image_base64(image_base64: str | None) -> tuple[str, bytes] | None:
    """
    將前端 `FileReader.readAsDataURL` 或純 Base64 字串還原成 (mime, 原始位元組)。
    """
    if image_base64 is None or not isinstance(image_base64, str):
        return None
    s = image_base64.strip()
    if not s:
        return None

    lowered = s.lower()
    if lowered.startswith("blob:") or lowered.startswith("http://") or lowered.startswith("https://"):
        raise ValueError(_("圖片必須以 Base64 傳送，請勿使用 blob 或網址路徑。"))

    mime = "image/jpeg"
    if s.startswith("data:"):
        try:
            header, b64_payload = s.split(",", 1)
        except ValueError as exc:
            raise ValueError(_("圖片 Data URL 格式無效。")) from exc
        if ";base64" not in header.lower():
            raise ValueError(_("圖片必須為 base64 的 Data URL（需含 ;base64,）。"))
        semi = header.find(";")
        if semi > 5:
            candidate = header[5:semi].strip().lower()
            if candidate:
                mime = candidate
        b64_str = "".join(b64_payload.split())
    else:
        b64_str = "".join(s.split())

    try:
        raw = base64.b64decode(b64_str, validate=True)
    except (binascii.Error, ValueError):
        pad = (-len(b64_str)) % 4
        try:
            raw = base64.b64decode(b64_str + ("=" * pad), validate=False)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(_("圖片 Base64 解碼失敗，請確認檔案是否完整。")) from exc

    if not raw:
        raise ValueError(_("解碼後的圖片內容為空。"))
    if mime not in _ALLOWED_IMAGE_MIMES:
        raise ValueError(_("不支援的圖片格式，請使用 JPG、PNG、GIF 或 WebP。"))
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(_("圖片請小於 5MB。"))
    return (mime, raw)


def _compress_image_bytes(raw: bytes, *, mime_hint: str | None = None) -> tuple[str, bytes]:
    """
    將圖片壓成較小的 JPEG 位元組，供 NVIDIA / Gemini 共用，避免重複壓縮與過大 JSON。
    """
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(raw))
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")

        max_side = 768
        w, h = im.size
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

        quality = 72
        data = b""
        for _ in range(7):
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) <= _TARGET_JPEG_BYTES:
                break
            quality = max(40, quality - 8)
            if quality <= 48:
                w2, h2 = im.size
                im = im.resize((max(1, int(w2 * 0.85)), max(1, int(h2 * 0.85))), Image.LANCZOS)

        if data:
            return ("image/jpeg", data)
    except Exception:
        logger.debug("image compress fallback to original bytes", exc_info=True)

    mime = (mime_hint or "image/jpeg").lower()
    if mime not in _ALLOWED_IMAGE_MIMES:
        mime = "image/jpeg"
    return (mime, raw)


def _prepare_vision_image(image: tuple[str, bytes] | None) -> tuple[str, bytes] | None:
    if not image:
        return None
    mime, raw = image
    out = _compress_image_bytes(raw, mime_hint=mime)
    logger.debug("vision image prepared mime=%s bytes=%d", out[0], len(out[1]))
    return out


def _nvidia_key_from_env() -> str:
    return (os.environ.get("NVIDIA_API_KEY") or os.environ.get("api_key") or "").strip()


def _ai_settings() -> dict[str, str]:
    """單次讀取設定，避免 get_assistant_reply 內重複 getattr。"""
    nvidia_model = getattr(settings, "NVIDIA_MODEL", DEFAULT_NVIDIA_MODEL)
    return {
        "nvidia_key": (getattr(settings, "NVIDIA_API_KEY", "") or "").strip() or _nvidia_key_from_env(),
        "nvidia_model": nvidia_model,
        "nvidia_backup_key": (getattr(settings, "NVIDIA_BACKUP_API_KEY", "") or "").strip(),
        "nvidia_backup_model": getattr(settings, "NVIDIA_BACKUP_MODEL", nvidia_model),
        "nvidia_url": getattr(settings, "NVIDIA_INVOKE_URL", DEFAULT_NVIDIA_INVOKE_URL),
        "gemini_key": (getattr(settings, "GEMINI_API_KEY", "") or "").strip(),
        "gemini_model": getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash"),
    }


def _build_nvidia_messages(
    history: list[dict[str, str]],
    message: str,
    image: tuple[str, bytes] | None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": h["role"], "content": h["content"]} for h in history)

    text = (message or "").strip()[:MAX_MESSAGE_CHARS]
    if image:
        mime, raw_bytes = image
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        prompt = text or _("請描述這張圖片，並估算大概熱量（若不確定請說明理由與假設）。")
        content: list[dict[str, Any]] = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": text})

    return messages


def call_nvidia_chat_completions(
    *,
    messages: list[dict[str, Any]],
    api_key: str,
    model: str,
    invoke_url: str = DEFAULT_NVIDIA_INVOKE_URL,
    temperature: float = 0.4,
    top_p: float = 0.95,
    max_tokens: int = 200,
) -> str:
    key = (api_key or "").strip()
    if not key:
        raise AIProviderError(
            _("缺少 NVIDIA API Key：請在 `.env` 設定 `NVIDIA_API_KEY`（或 `api_key`）。"),
            transient=False,
        )

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }

    def _parse_response(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise AIProviderError(_("NVIDIA API 沒有回傳 choices，請稍後再試。"), transient=True)
        msg = (choices[0].get("message") or {}).get("content") or ""
        msg = (msg or "").strip()
        if not msg:
            raise AIProviderError(_("NVIDIA API 回覆為空，請稍後再試。"), transient=True)
        return msg

    try:
        data = _http_post_json(invoke_url, payload, headers, provider="nvidia")
        return _parse_response(data)
    except TimeoutError:
        raise AIProviderError(_("NVIDIA API 讀取回覆逾時（timeout），請稍後再試。"), transient=True)
    except urllib.error.HTTPError as exc:
        if exc.code in (502, 503, 504):
            logger.info("nvidia transient %s, retry once", exc.code)
            time.sleep(0.8)
            try:
                data = _http_post_json(invoke_url, payload, headers, provider="nvidia-retry")
                return _parse_response(data)
            except Exception:
                logger.exception("nvidia retry failed")
            raise AIProviderError(
                _(
                    "NVIDIA API 上游暫時性錯誤（HTTP %(code)s）。\n"
                    "請稍後重試；若傳圖片，建議換較小或較清晰的圖片，或改用 Gemini。"
                )
                % {"code": exc.code},
                transient=True,
            )
        if exc.code in (401, 403):
            raise AIProviderError(
                _("NVIDIA API 權限不足：請確認 `NVIDIA_API_KEY` 正確且仍有效。"),
                transient=False,
            )
        if exc.code == 429:
            raise AIProviderError(_("NVIDIA API 請求太頻繁（429）：請稍後再試。"), transient=True)
        raise AIProviderError(
            _("NVIDIA API 錯誤（HTTP %(code)s）。") % {"code": exc.code},
            transient=True,
        )
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.exception("nvidia connection/parse error")
        raise AIProviderError(_("NVIDIA API 連線/解析失敗：%(err)s") % {"err": exc}, transient=True)


def _gemini_role(role: str) -> str | None:
    if role == "user":
        return "user"
    if role == "assistant":
        return "model"
    return None


def _build_gemini_contents(
    history: list[dict[str, str]],
    message: str,
    image: tuple[str, bytes] | None,
) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for h in history:
        gr = _gemini_role(h["role"])
        if not gr:
            continue
        contents.append({"role": gr, "parts": [{"text": h["content"]}]})

    if image:
        mime, raw = image
        b64 = base64.b64encode(raw).decode("ascii")
        text_part = (message or _("請描述這張圖片並給出飲食建議。")).strip()[:MAX_MESSAGE_CHARS]
        parts: list[dict[str, Any]] = [
            {"text": text_part},
            {"inlineData": {"mimeType": mime, "data": b64}},
        ]
    else:
        parts = [{"text": (message or _("你好")).strip()[:MAX_MESSAGE_CHARS]}]

    contents.append({"role": "user", "parts": parts})
    return contents


def call_gemini_generate(contents: list[dict[str, Any]], *, model: str, api_key: str) -> str:
    key = (api_key or "").strip()
    if not key:
        raise AIProviderError(_("缺少 Gemini API Key：請在 `.env` 設定 `GEMINI_API_KEY`。"), transient=False)

    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 200},
    }
    url = GEMINI_GENERATE_URL.format(model=model) + f"?key={quote(key, safe='')}"
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}

    try:
        data = _http_post_json(url, body, headers, provider="gemini")
        candidates = data.get("candidates") or []
        if not candidates:
            raise AIProviderError(_("Gemini 沒有回傳候選回覆，請稍後再試。"), transient=True)
        content = (candidates[0].get("content") or {})
        parts = content.get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        out = "\n".join(t for t in texts if t).strip()
        if not out:
            raise AIProviderError(_("Gemini 回覆為空，請稍後再試。"), transient=True)
        return out
    except TimeoutError:
        raise AIProviderError(_("Gemini API 讀取回覆逾時（timeout），請稍後再試。"), transient=True)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AIProviderError(
                _("Gemini API 權限不足：請確認 `GEMINI_API_KEY` 正確且已開啟 API。"),
                transient=False,
            )
        if exc.code == 429:
            raise AIProviderError(_("Gemini API 請求太頻繁（429）：請稍後再試。"), transient=True)
        raise AIProviderError(
            _("Gemini API 錯誤（HTTP %(code)s）。") % {"code": exc.code},
            transient=True,
        )
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.exception("gemini connection/parse error")
        raise AIProviderError(_("Gemini API 連線/解析失敗：%(err)s") % {"err": exc}, transient=True)


def get_assistant_reply(
    *,
    message: str,
    image: tuple[str, bytes] | None,
    history: list[Any],
) -> tuple[str, str]:
    """
    image: 已由 view 解出之 (mime_type, raw_bytes)；無圖則為 None。
    """
    started = time.monotonic()
    hist = _normalize_history(history)
    vision_image = _prepare_vision_image(image)
    cfg = _ai_settings()

    msgs = _build_nvidia_messages(hist, message, vision_image)
    nvidia_errors: list[str] = []

    if cfg["nvidia_key"]:
        try:
            reply = call_nvidia_chat_completions(
                messages=msgs,
                api_key=cfg["nvidia_key"],
                model=cfg["nvidia_model"],
                invoke_url=cfg["nvidia_url"],
            )
            logger.info(
                "ai_chat ok provider=nvidia model=%s has_image=%s elapsed=%.2fs",
                cfg["nvidia_model"],
                bool(vision_image),
                time.monotonic() - started,
            )
            return reply, cfg["nvidia_model"]
        except AIProviderError as exc:
            nvidia_errors.append(_("主模型失敗：%(msg)s") % {"msg": exc.message})
            logger.warning("nvidia primary failed: %s", exc.message)

    if cfg["nvidia_backup_key"] and cfg["nvidia_backup_key"] != cfg["nvidia_key"]:
        try:
            reply = call_nvidia_chat_completions(
                messages=msgs,
                api_key=cfg["nvidia_backup_key"],
                model=cfg["nvidia_backup_model"],
                invoke_url=cfg["nvidia_url"],
            )
            logger.info(
                "ai_chat ok provider=nvidia-backup model=%s elapsed=%.2fs",
                cfg["nvidia_backup_model"],
                time.monotonic() - started,
            )
            return reply, cfg["nvidia_backup_model"]
        except AIProviderError as exc:
            nvidia_errors.append(_("備援模型失敗：%(msg)s") % {"msg": exc.message})
            logger.warning("nvidia backup failed: %s", exc.message)

    if cfg["gemini_key"]:
        contents = _build_gemini_contents(hist, message, vision_image)
        try:
            reply = call_gemini_generate(contents, model=cfg["gemini_model"], api_key=cfg["gemini_key"])
            logger.info(
                "ai_chat ok provider=gemini model=%s elapsed=%.2fs",
                cfg["gemini_model"],
                time.monotonic() - started,
            )
            return reply, cfg["gemini_model"]
        except AIProviderError as exc:
            logger.warning("gemini failed: %s", exc.message)
            if nvidia_errors:
                combined = "; ".join(nvidia_errors)
                return (
                    _("%(nvidia)s；Gemini 也失敗：%(gemini)s") % {"nvidia": combined, "gemini": exc.message},
                    "fallback-error",
                )
            return exc.message, "gemini-error"

    if nvidia_errors:
        logger.warning("ai_chat all providers failed elapsed=%.2fs", time.monotonic() - started)
        return "; ".join(nvidia_errors), "nvidia-error"

    logger.info("ai_chat demo mode elapsed=%.2fs", time.monotonic() - started)
    return _demo_reply(message, bool(vision_image)), "demo"
