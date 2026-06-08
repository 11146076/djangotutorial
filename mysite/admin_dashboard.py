from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone

from posts.models import AiChatLog, Post, PostComment, PostHealthInsight, SearchLog


def get_dashboard_stats() -> dict:
    User = get_user_model()
    today = timezone.localdate()

    return {
        "users": User.objects.count(),
        "posts": Post.objects.count(),
        "posts_public": Post.objects.filter(visibility=Post.VISIBILITY_PUBLIC).count(),
        "posts_private": Post.objects.filter(visibility=Post.VISIBILITY_PRIVATE).count(),
        "comments": PostComment.objects.count(),
        "health_pending": PostHealthInsight.objects.filter(status=PostHealthInsight.STATUS_PENDING).count(),
        "health_failed": PostHealthInsight.objects.filter(status=PostHealthInsight.STATUS_FAILED).count(),
        "ai_chats_today": AiChatLog.objects.filter(created_at__date=today).count(),
        "searches_today": SearchLog.objects.filter(created_at__date=today).count(),
    }
