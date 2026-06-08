from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AiChatLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_chat_logs",
        verbose_name=_("使用者"),
    )
    message = models.TextField(_("提問文字"), blank=True, default="")
    image = models.ImageField(
        _("提問圖片"),
        upload_to="ai_chat/",
        blank=True,
        null=True,
    )
    assistant_reply = models.TextField(_("AI 回覆"), blank=True, default="")
    model_name = models.CharField(_("模型"), max_length=120, blank=True, default="")
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)

    class Meta:
        db_table = "ai_chat_logs"
        ordering = ["-created_at", "-id"]
        verbose_name = _("AI 對話紀錄")
        verbose_name_plural = _("AI 對話紀錄")

    def __str__(self) -> str:
        preview = (self.message or "（僅圖片）")[:20]
        return f"AiChatLog({self.user.username}: {preview})"
