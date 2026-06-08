from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class CommentLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_likes",
        verbose_name=_("使用者"),
    )
    comment = models.ForeignKey(
        "posts.PostComment",
        on_delete=models.CASCADE,
        related_name="comment_likes",
        verbose_name=_("留言"),
    )
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)

    class Meta:
        db_table = "post_comment_likes"
        verbose_name = _("留言讚")
        verbose_name_plural = _("留言讚")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "comment"],
                name="unique_comment_like_per_user_comment",
            )
        ]

    def __str__(self) -> str:
        return f"CommentLike({self.user_id} -> comment {self.comment_id})"
