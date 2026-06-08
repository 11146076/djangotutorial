from django.core.management.base import BaseCommand

from posts.models import Category, Tag


DEFAULT_CATEGORIES = [
    "早餐",
    "正餐",
    "宵夜",
    "甜點 / 零食",
    "飲料 / 手搖",
    "輕食 / 沙拉",
]

DEFAULT_TAGS = [
    "酸",
    "甜",
    "苦",
    "辣",
    "小資平價",
    "約會聚餐",
    "異國料理",
    "健康低卡",
    "素食友善",
    "踩雷勿近",
    "氣氛佳",
]


class Command(BaseCommand):
    help = "清空並重建預設類別(Category)與標籤(Tag)資料"

    def handle(self, *args, **options):
        Category.objects.all().delete()
        Tag.objects.all().delete()

        n_cat = 0
        for name in DEFAULT_CATEGORIES:
            Category.objects.create(name=name)
            n_cat += 1

        n_tag = 0
        for name in DEFAULT_TAGS:
            Tag.objects.create(name=name)
            n_tag += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"完成！已清空舊資料並建立 {n_cat} 筆類別、{n_tag} 筆標籤。"
            )
        )
