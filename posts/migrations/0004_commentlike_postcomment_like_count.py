# Generated manually for comment likes

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0003_alter_post_options"),
        ("posts", "0002_post_comment_threading"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="postcomment",
            name="like_count",
            field=models.PositiveIntegerField(default=0, verbose_name="讚數"),
        ),
        migrations.CreateModel(
            name="CommentLike",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="建立時間")),
                (
                    "comment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comment_likes",
                        to="posts.postcomment",
                        verbose_name="留言",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comment_likes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="使用者",
                    ),
                ),
            ],
            options={
                "verbose_name": "留言讚",
                "verbose_name_plural": "留言讚",
                "db_table": "post_comment_likes",
            },
        ),
        migrations.AddConstraint(
            model_name="commentlike",
            constraint=models.UniqueConstraint(
                fields=("user", "comment"),
                name="unique_comment_like_per_user_comment",
            ),
        ),
    ]
