from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Post(models.Model):
    VISIBILITY_PUBLIC = "public"
    VISIBILITY_PRIVATE = "private"
    VISIBILITY_CHOICES = (
        (VISIBILITY_PUBLIC, _("所有人")),
        (VISIBILITY_PRIVATE, _("只有自己")),
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
        db_column="user_id",
        verbose_name=_("作者"),
    )
    category = models.ForeignKey(
        "posts.Category",
        on_delete=models.SET_NULL,
        related_name="posts",
        blank=True,
        null=True,
        verbose_name=_("分類"),
    )
    title = models.CharField(_("標題"), max_length=255, blank=True)
    content = RichTextUploadingField(_("內容"))
    image = models.ImageField(
        _("圖片 1"),
        upload_to="posts/",
        db_column="image_url",
        blank=True,
        null=True,
    )
    image2 = models.ImageField(
        _("圖片 2"),
        upload_to="posts/",
        blank=True,
        null=True,
    )
    image3 = models.ImageField(
        _("圖片 3"),
        upload_to="posts/",
        blank=True,
        null=True,
    )
    tags = models.ManyToManyField("posts.Tag", related_name="posts", blank=True, verbose_name=_("標籤"))
    visibility = models.CharField(
        _("可見性"),
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_PUBLIC,
    )
    like_count = models.PositiveIntegerField(_("讚數"), default=0)
    latest_health_insight = models.ForeignKey(
        "posts.PostHealthInsight",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
        verbose_name=_("最新健康分析"),
    )
    created_at = models.DateTimeField(_("建立時間"), auto_now_add=True)
    updated_at = models.DateTimeField(_("更新時間"), auto_now=True)

    class Meta:
        db_table = "posts"
        ordering = ["-created_at", "-id"]
        verbose_name = _("貼文")
        verbose_name_plural = _("貼文")

    def __str__(self) -> str:
        headline = self.title or self.content[:20]
        return f"Post({self.author.username}: {headline})"

    def gallery_images(self):
        """依序回傳已上傳的貼文附圖（最多三張，不含內文編輯器裡的圖）。"""
        out = []
        for f in (self.image, self.image2, self.image3):
            if f:
                out.append(f)
        return out
