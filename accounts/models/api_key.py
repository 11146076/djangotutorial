import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.roles import ROLE_CHOICES, ROLE_MEMBER


class ApiKey(models.Model):
    """並存認證：API Key（與帳密 Session 登入並行）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        verbose_name=_("使用者"),
    )
    name = models.CharField(_("名稱"), max_length=100)
    key = models.CharField(_("金鑰"), max_length=64, unique=True, db_index=True)
    role = models.CharField(
        _("授權角色"),
        max_length=30,
        choices=ROLE_CHOICES,
        default=ROLE_MEMBER,
        help_text=_("此金鑰呼叫 API 時的有效角色（可高於或等於使用者本身）。"),
    )
    is_active = models.BooleanField(_("啟用"), default=True)
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)
    last_used_at = models.DateTimeField(_("最後使用"), blank=True, null=True)

    class Meta:
        db_table = "api_keys"
        verbose_name = _("API 金鑰")
        verbose_name_plural = _("API 金鑰")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ApiKey({self.name} → {self.user.username})"

    @classmethod
    def generate_key(cls) -> str:
        return secrets.token_urlsafe(32)

    def mark_used(self) -> None:
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])

    def effective_role(self) -> str:
        """金鑰角色與使用者角色取較高者。"""
        from accounts.roles import role_level

        user_role = getattr(self.user, "role", ROLE_MEMBER)
        if role_level(self.role) >= role_level(user_role):
            return self.role
        return user_role
