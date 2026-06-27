from django.db.models import Count

from posts.models import Notification, Tag


def wheel_tags(request):
    """標籤轉盤：僅含至少一篇貼文使用到的標籤，依使用次數與名稱排序，最多 16 格。"""
    items = list(
        Tag.objects.annotate(_post_count=Count("posts", distinct=True))
        .filter(_post_count__gt=0)
        .order_by("-_post_count", "name")[:16]
        .values("id", "name")
    )
    return {"wheel_tag_items": items}


def unread_notifications(request):
    if not request.user.is_authenticated:
        return {"unread_notifications_count": 0}
    return {
        "unread_notifications_count": Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()
    }
