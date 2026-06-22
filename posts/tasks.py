from __future__ import annotations

from django.core.files.storage import default_storage
from django.db import transaction

from .ai_chat import AIProviderError
from .health_ai import estimate_post_health
from .models import Post, PostHealthInsight

try:
    from celery import shared_task
except Exception:  # pragma: no cover - celery not installed yet
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


def _post_image_tuple(post: Post) -> tuple[str, bytes] | None:
    for field in (post.image, post.image2, post.image3):
        if not field:
            continue
        try:
            with default_storage.open(field.name, "rb") as f:
                raw = f.read()
            ext = (field.name.rsplit(".", 1)[-1] or "").lower()
            mime = "image/jpeg"
            if ext == "png":
                mime = "image/png"
            elif ext == "gif":
                mime = "image/gif"
            elif ext == "webp":
                mime = "image/webp"
            return (mime, raw)
        except Exception:
            continue
    return None


def _get_or_create_pending_insight(post: Post) -> PostHealthInsight:
    insight = (
        PostHealthInsight.objects.filter(post=post, status=PostHealthInsight.STATUS_PENDING)
        .order_by("-id")
        .first()
    )
    if insight:
        insight.reason = "分析中"
        insight.error_message = ""
        insight.save(update_fields=["reason", "error_message"])
        return insight
    return PostHealthInsight.objects.create(
        post=post,
        calories=0,
        health_rank=PostHealthInsight.RANK_D,
        reason="分析中",
        status=PostHealthInsight.STATUS_PENDING,
    )


@shared_task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=4,
)
def analyze_post_health_task(self, post_id: int):
    post = Post.objects.filter(pk=post_id).first()
    if not post:
        return

    insight = _get_or_create_pending_insight(post)
    try:
        payload, model_name = estimate_post_health(content=post.content or "", image=_post_image_tuple(post))
        with transaction.atomic():
            insight.calories = payload["calories"]
            insight.health_rank = payload["health_rank"]
            insight.reason = payload["reason"]
            insight.status = PostHealthInsight.STATUS_COMPLETED
            insight.model_name = model_name
            insight.save(
                update_fields=[
                    "calories",
                    "health_rank",
                    "reason",
                    "status",
                    "model_name",
                ]
            )
            post.latest_health_insight = insight
            post.save(update_fields=["latest_health_insight", "updated_at"])
    except AIProviderError as exc:
        if exc.transient and self.request.retries < self.max_retries:
            insight.reason = "分析中"
            insight.error_message = ""
            insight.save(update_fields=["reason", "error_message"])
            raise self.retry(exc=exc, countdown=min(60, 5 * (2 ** self.request.retries)))
        insight.status = PostHealthInsight.STATUS_FAILED
        insight.reason = "暫時無法分析"
        insight.error_message = str(exc.message)[:1000]
        insight.save(update_fields=["status", "reason", "error_message"])
        raise
    except Exception as exc:
        insight.status = PostHealthInsight.STATUS_FAILED
        insight.reason = "暫時無法分析"
        insight.error_message = str(exc)[:1000]
        insight.save(update_fields=["status", "reason", "error_message"])
        raise
