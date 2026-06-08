from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name=_("使用者"),
    )
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name=_("貼文"),
    )
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)

    class Meta:
        db_table = "likes"
        verbose_name = _("按讚")
        verbose_name_plural = _("按讚")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_like_per_user_post",
            )
        ]

    def __str__(self) -> str:
        return f"Like({self.user.username} -> {self.post_id})"
