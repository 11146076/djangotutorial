from django.db.models import F
from django.db.models.functions import Greatest
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .comment_like import CommentLike
from .like import Like
from .post import Post
from .post_comment import PostComment


@receiver(post_save, sender=Like)
def increment_like_count(sender, instance, created, **kwargs):
    if created:
        Post.objects.filter(pk=instance.post_id).update(like_count=F("like_count") + 1)


@receiver(post_delete, sender=Like)
def decrement_like_count(sender, instance, **kwargs):
    Post.objects.filter(pk=instance.post_id).update(like_count=Greatest(F("like_count") - 1, 0))


@receiver(post_save, sender=CommentLike)
def increment_comment_like_count(sender, instance, created, **kwargs):
    if created:
        PostComment.objects.filter(pk=instance.comment_id).update(like_count=F("like_count") + 1)


@receiver(post_delete, sender=CommentLike)
def decrement_comment_like_count(sender, instance, **kwargs):
    PostComment.objects.filter(pk=instance.comment_id).update(like_count=Greatest(F("like_count") - 1, 0))
