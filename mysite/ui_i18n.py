"""前台 UI 字串（依目前語系翻譯，供模板與 JavaScript 共用）。"""

from django.utils.translation import gettext as _


def ui_i18n(request):
    return {
        "ui_i18n": {
            # 互動計數
            "likes": _("讚"),
            "comments": _("留言"),
            "collections": _("收藏"),
            # 互動按鈕
            "like": _("按讚"),
            "unlike": _("取消按讚"),
            "collect": _("收藏"),
            "uncollect": _("取消收藏"),
            "liked": _("已按讚"),
            "unliked": _("已取消按讚"),
            "collected": _("已收藏"),
            "uncollected": _("已取消收藏"),
            "action_failed": _("操作失敗，請稍後再試"),
            # 搜尋與篩選
            "search": _("搜尋"),
            "clear": _("清除"),
            "category": _("分類"),
            "tags": _("標籤"),
            "search_placeholder": _("搜尋貼文內容或發文者"),
            "filtering_categories": _("搜尋中分類"),
            "filtering_tags": _("搜尋中標籤"),
            "filter_hint": _("可複選：按住 Ctrl 再點選多項；不選表示不限。"),
            # 發文
            "compose_post": _("發表貼文"),
            "compose_expand": _("點一下展開表單"),
            "publish": _("發布"),
            "title": _("標題"),
            "new_category": _("新增分類"),
            "new_tags": _("新增標籤"),
            "tags_multi": _("標籤（多選）"),
            "visibility_label": _("誰可以看到"),
            "content_label": _("發布貼文"),
            "gallery_label": _("貼文附圖（可選，最多 3 張）"),
            # 留言
            "comment_placeholder": _("留言..."),
            "no_comments": _("尚無留言"),
            "hide_comments": _("收起留言"),
            "view_all_comments": _("查看全部 {n} 則留言"),
            # 回到頂部
            "back_to_top": _("回到最上方"),
            "new_posts_back_to_top": _("有新貼文，回到上方查看"),
            # 其他
            "health_expert": _("健康達人"),
            "ago": _("前"),
            "private_only": _("僅自己可見"),
            "prev_page": _("上一頁"),
            "next_page": _("下一頁"),
            "posts_found": _("關鍵字「{q}」共找到 {n} 篇貼文"),
        }
    }
