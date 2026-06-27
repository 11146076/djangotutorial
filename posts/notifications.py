from __future__ import annotations

from django.db import transaction

from .models import Follow, Notification, Post, PostComment


def _create_notification(
    *,
    recipient,
    actor,
    notification_type: str,
    post: Post | None = None,
    comment: PostComment | None = None,
):
    if not recipient or not actor or recipient.pk == actor.pk:
        return None
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        post=post,
        comment=comment,
    )


def notify_post_liked(like):
    post = like.post
    return _create_notification(
        recipient=post.author,
        actor=like.user,
        notification_type=Notification.TYPE_POST_LIKED,
        post=post,
    )


def notify_post_commented(comment: PostComment):
    notifications = []
    post = comment.post
    created = _create_notification(
        recipient=post.author,
        actor=comment.author,
        notification_type=Notification.TYPE_POST_COMMENTED,
        post=post,
        comment=comment,
    )
    if created:
        notifications.append(created)

    if comment.parent_id and comment.parent.author_id != post.author_id:
        parent = comment.parent
        created = _create_notification(
            recipient=parent.author,
            actor=comment.author,
            notification_type=Notification.TYPE_COMMENT_REPLIED,
            post=post,
            comment=comment,
        )
        if created:
            notifications.append(created)
    return notifications


def notify_followers_new_post(post: Post):
    if post.visibility != Post.VISIBILITY_PUBLIC:
        return 0

    follower_ids = (
        Follow.objects.filter(following_id=post.author_id)
        .exclude(follower_id=post.author_id)
        .values_list("follower_id", flat=True)
    )
    notifications = [
        Notification(
            recipient_id=follower_id,
            actor_id=post.author_id,
            notification_type=Notification.TYPE_FOLLOWING_POSTED,
            post=post,
        )
        for follower_id in follower_ids
    ]
    with transaction.atomic():
        Notification.objects.bulk_create(notifications, batch_size=500)
    return len(notifications)
