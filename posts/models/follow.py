from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils.translation import gettext_lazy as _


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following_relationships",
        verbose_name=_("追蹤者"),
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follower_relationships",
        verbose_name=_("被追蹤者"),
    )
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)

    class Meta:
        db_table = "follows"
        verbose_name = _("追蹤關係")
        verbose_name_plural = _("追蹤關係")
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="unique_follow_pair",
            ),
            models.CheckConstraint(
                condition=~models.Q(follower=F("following")),
                name="prevent_self_follow",
            ),
        ]

    def __str__(self) -> str:
        return f"Follow({self.follower.username} -> {self.following.username})"
