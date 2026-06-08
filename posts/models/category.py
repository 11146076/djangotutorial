from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    name = models.CharField(_("名稱"), max_length=100)

    class Meta:
        db_table = "categories"
        ordering = ["name"]
        verbose_name = _("分類")
        verbose_name_plural = _("分類")

    def __str__(self) -> str:
        return self.name
