from django.db import models
from django.utils.translation import gettext_lazy as _


class Tag(models.Model):
    name = models.CharField(_("名稱"), max_length=100, unique=True)

    class Meta:
        db_table = "tags"
        ordering = ["name"]
        verbose_name = _("標籤")
        verbose_name_plural = _("標籤")

    def __str__(self) -> str:
        return self.name
