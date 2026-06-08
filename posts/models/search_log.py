from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SearchLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="search_logs",
        verbose_name=_("使用者"),
    )
    keyword = models.CharField(_("關鍵字"), max_length=255)
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)

    class Meta:
        db_table = "search_logs"
        ordering = ["-created_at"]
        verbose_name = _("搜尋紀錄")
        verbose_name_plural = _("搜尋紀錄")

    def __str__(self) -> str:
        return f"SearchLog({self.user.username}: {self.keyword})"
