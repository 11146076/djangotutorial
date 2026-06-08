from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0009_alter_postcomment_options_post_visibility"),
    ]

    operations = [
        migrations.CreateModel(
            name="PostHealthInsight",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("calories", models.PositiveIntegerField(default=0, verbose_name="估算熱量(kcal)")),
                (
                    "health_rank",
                    models.CharField(
                        choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
                        default="D",
                        max_length=1,
                        verbose_name="健康等級",
                    ),
                ),
                ("reason", models.CharField(default="", max_length=200, verbose_name="健康短評")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "等待分析"), ("completed", "完成"), ("failed", "失敗")],
                        default="pending",
                        max_length=20,
                        verbose_name="分析狀態",
                    ),
                ),
                ("model_name", models.CharField(blank=True, default="", max_length=64, verbose_name="模型名稱")),
                (
                    "confidence",
                    models.DecimalField(blank=True, decimal_places=3, max_digits=4, null=True, verbose_name="信心值"),
                ),
                ("error_message", models.TextField(blank=True, default="", verbose_name="錯誤訊息")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="建立時間")),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="health_insights",
                        to="posts.post",
                        verbose_name="貼文",
                    ),
                ),
            ],
            options={
                "verbose_name": "貼文健康分析",
                "verbose_name_plural": "貼文健康分析",
                "db_table": "post_health_insights",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddField(
            model_name="post",
            name="latest_health_insight",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="posts.posthealthinsight",
                verbose_name="最新健康分析",
            ),
        ),
        migrations.AddIndex(
            model_name="posthealthinsight",
            index=models.Index(fields=["post", "-created_at"], name="idx_health_post_created"),
        ),
        migrations.AddIndex(
            model_name="posthealthinsight",
            index=models.Index(fields=["health_rank"], name="idx_health_rank"),
        ),
    ]
