from django.db import models
from django.utils.translation import gettext_lazy as _


class PostHealthInsight(models.Model):
    RANK_A = "A"
    RANK_B = "B"
    RANK_C = "C"
    RANK_D = "D"
    HEALTH_RANK_CHOICES = (
        (RANK_A, "A"),
        (RANK_B, "B"),
        (RANK_C, "C"),
        (RANK_D, "D"),
    )

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, _("等待分析")),
        (STATUS_COMPLETED, _("完成")),
        (STATUS_FAILED, _("失敗")),
    )

    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="health_insights",
        verbose_name=_("貼文"),
    )
    calories = models.PositiveIntegerField(_("估算熱量(kcal)"), default=0)
    health_rank = models.CharField(_("健康等級"), max_length=1, choices=HEALTH_RANK_CHOICES, default=RANK_D)
    reason = models.CharField(_("健康短評"), max_length=200, default="")
    status = models.CharField(_("分析狀態"), max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    model_name = models.CharField(_("模型名稱"), max_length=64, blank=True, default="")
    confidence = models.DecimalField(_("信心值"), max_digits=4, decimal_places=3, blank=True, null=True)
    error_message = models.TextField(_("錯誤訊息"), blank=True, default="")
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)

    class Meta:
        db_table = "post_health_insights"
        verbose_name = _("貼文健康分析")
        verbose_name_plural = _("貼文健康分析")
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["post", "-created_at"], name="idx_health_post_created"),
            models.Index(fields=["health_rank"], name="idx_health_rank"),
        ]

    def __str__(self) -> str:
        return f"PostHealthInsight(post_id={self.post_id}, rank={self.health_rank}, kcal={self.calories})"
