from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class PostComment(models.Model):
    content = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_comments",
    )
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="post_comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    root = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="descendants",
    )
    is_locked = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    like_count = models.PositiveIntegerField(_("讚數"), default=0)

    class Meta:
        db_table = "post_comment"
        ordering = ["created_at"]
        verbose_name = _("貼文留言")
        verbose_name_plural = _("貼文留言")
        indexes = [
            models.Index(fields=["post", "created_at"], name="post_comment_post_created"),
            models.Index(fields=["root", "created_at"], name="post_comment_root_created"),
            models.Index(fields=["parent", "created_at"], name="post_comment_parent_created"),
        ]

    def __str__(self) -> str:
        return f"PostComment({self.author_id} -> {self.post_id})"
