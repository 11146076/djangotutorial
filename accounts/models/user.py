from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    email = models.EmailField(_("電子郵件"), unique=True)
    role = models.CharField(_("角色"), max_length=30, default="member")
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        verbose_name = _("使用者")
        verbose_name_plural = _("使用者")

    def __str__(self) -> str:
        return self.username
