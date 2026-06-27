from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    TYPE_POST_LIKED = "post_liked"
    TYPE_POST_COMMENTED = "post_commented"
    TYPE_COMMENT_REPLIED = "comment_replied"
    TYPE_FOLLOWING_POSTED = "following_posted"

    TYPE_CHOICES = (
        (TYPE_POST_LIKED, _("貼文被按讚")),
        (TYPE_POST_COMMENTED, _("貼文有新留言")),
        (TYPE_COMMENT_REPLIED, _("留言有新回覆")),
        (TYPE_FOLLOWING_POSTED, _("追蹤者發布新貼文")),
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("收件者"),
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_notifications",
        verbose_name=_("觸發者"),
    )
    notification_type = models.CharField(_("通知類型"), max_length=40, choices=TYPE_CHOICES)
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
        verbose_name=_("貼文"),
    )
    comment = models.ForeignKey(
        "posts.PostComment",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
        verbose_name=_("留言"),
    )
    is_read = models.BooleanField(_("已讀"), default=False)
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)
    read_at = models.DateTimeField(_("讀取時間"), blank=True, null=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at", "-id"]
        verbose_name = _("通知")
        verbose_name_plural = _("通知")
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"], name="idx_notify_recipient_read"),
            models.Index(fields=["recipient", "-created_at"], name="idx_notify_recipient_created"),
        ]

    def __str__(self) -> str:
        return f"Notification({self.recipient_id}, {self.notification_type}, read={self.is_read})"

    def mark_read(self):
        if self.is_read:
            return
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])

    def target_url(self) -> str:
        if self.post_id:
            return reverse("posts:post_detail", kwargs={"pk": self.post_id})
        return reverse("posts:notifications_list")

    def message(self) -> str:
        actor_name = self.actor.username
        if self.notification_type == self.TYPE_POST_LIKED:
            return f"{actor_name} 按讚了你的貼文。"
        if self.notification_type == self.TYPE_POST_COMMENTED:
            return f"{actor_name} 在你的貼文留下留言。"
        if self.notification_type == self.TYPE_COMMENT_REPLIED:
            return f"{actor_name} 回覆了你的留言。"
        if self.notification_type == self.TYPE_FOLLOWING_POSTED:
            return f"你追蹤的 {actor_name} 發布了新貼文。"
        return "你有一則新通知。"
