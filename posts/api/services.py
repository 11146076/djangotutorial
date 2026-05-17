from __future__ import annotations

import logging
import uuid
from typing import Any

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from posts.ai_chat import get_assistant_reply
from posts.models import AiChatLog

logger = logging.getLogger(__name__)
User = get_user_model()


def run_ai_chat(
    *,
    user: User,
    message: str,
    history: list[Any],
    image_tuple: tuple[str, bytes] | None,
) -> dict[str, str]:
    logger.info(
        "ai_chat request user_id=%s has_image=%s message_len=%d history_len=%d",
        user.pk,
        bool(image_tuple),
        len(message),
        len(history) if isinstance(history, list) else 0,
    )

    reply, model_name = get_assistant_reply(message=message, image=image_tuple, history=history)

    log = AiChatLog(user=user, message=message, assistant_reply=reply, model_name=model_name)
    if image_tuple:
        mime, raw = image_tuple
        ext = "jpg"
        if mime == "image/png":
            ext = "png"
        elif mime == "image/gif":
            ext = "gif"
        elif mime == "image/webp":
            ext = "webp"
        filename = f"{uuid.uuid4().hex}.{ext}"
        log.image.save(filename, ContentFile(raw), save=False)
    log.save()

    return {"reply": reply}
