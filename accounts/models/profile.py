from django.db import models
from django.utils.translation import gettext_lazy as _


class Profile(models.Model):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="profile",
        primary_key=True,
        verbose_name=_("使用者"),
    )
    avatar = models.ImageField(_("大頭貼"), upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(_("自我介紹"), blank=True)
    dietary_preference = models.CharField(_("飲食偏好"), max_length=255, blank=True)

    class Meta:
        db_table = "profiles"
        verbose_name = _("個人資料")
        verbose_name_plural = _("個人資料")

    def __str__(self) -> str:
        return f"Profile({self.user.username})"
