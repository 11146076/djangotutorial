from django.core.management.base import BaseCommand

from posts.models import Post, PostHealthInsight
from posts.tasks import analyze_post_health_task


class Command(BaseCommand):
    help = "為舊貼文回填健康分析：已有分析則補 latest，無分析則送出 AI 任務"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync",
            action="store_true",
            help="同步執行分析（預設為丟到 Celery 非同步處理）",
        )

    def handle(self, *args, **options):
        run_sync = bool(options.get("sync"))
        queued = 0
        relinked = 0
        skipped = 0

        for post in Post.objects.all().order_by("id").iterator():
            latest_completed = (
                PostHealthInsight.objects.filter(
                    post_id=post.id,
                    status=PostHealthInsight.STATUS_COMPLETED,
                )
                .order_by("-created_at", "-id")
                .first()
            )

            if latest_completed:
                if post.latest_health_insight_id != latest_completed.id:
                    post.latest_health_insight = latest_completed
                    post.save(update_fields=["latest_health_insight", "updated_at"])
                    relinked += 1
                else:
                    skipped += 1
                continue

            if run_sync:
                analyze_post_health_task(post.id)
            else:
                analyze_post_health_task.delay(post.id)
            queued += 1

        mode_text = "同步" if run_sync else "非同步"
        self.stdout.write(
            self.style.SUCCESS(
                f"回填完成（{mode_text}）：排入分析 {queued} 篇、補上 latest {relinked} 篇、略過 {skipped} 篇。"
            )
        )
