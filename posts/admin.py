import csv

from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponse
from django.utils.html import format_html
from import_export import resources
from import_export.admin import ExportMixin

from mysite.admin_site import eatwhat_admin
from posts.tasks import analyze_post_health_task

from .models import (
    AiChatLog,
    Category,
    Collection,
    CommentLike,
    Follow,
    Like,
    Notification,
    Post,
    PostComment,
    PostHealthInsight,
    SearchLog,
    Tag,
)


class PostResource(resources.ModelResource):
    class Meta:
        model = Post
        fields = (
            "id",
            "title",
            "author__username",
            "category__name",
            "visibility",
            "like_count",
            "created_at",
            "updated_at",
        )


class CommentInline(admin.TabularInline):
    model = PostComment
    fields = ("author", "content", "like_count", "created_at")
    readonly_fields = ("created_at", "like_count")
    extra = 0
    autocomplete_fields = ("author",)
    show_change_link = True
    ordering = ("-created_at",)


class PostHealthInsightInline(admin.TabularInline):
    model = PostHealthInsight
    fields = ("status", "health_rank", "calories", "reason", "model_name", "created_at")
    readonly_fields = fields
    extra = 0
    ordering = ("-created_at",)
    max_num = 5
    can_delete = False


@admin.action(description="重算選取貼文的 like_count")
def recalc_like_count(modeladmin, request, queryset):
    post_ids = list(queryset.values_list("id", flat=True))
    counts = dict(
        Like.objects.filter(post_id__in=post_ids)
        .values("post_id")
        .annotate(c=Count("id"))
        .values_list("post_id", "c")
    )
    updated = 0
    for post_id in post_ids:
        updated += Post.objects.filter(id=post_id).update(like_count=counts.get(post_id, 0))
    modeladmin.message_user(request, f"已重算 {updated} 篇貼文的讚數。")


@admin.action(description="重新排程健康分析")
def queue_health_analysis(modeladmin, request, queryset):
    queued = 0
    for post in queryset:
        try:
            analyze_post_health_task.delay(post.id)
        except Exception:
            analyze_post_health_task(post.id)
        queued += 1
    modeladmin.message_user(request, f"已排程 {queued} 篇貼文的健康分析。")


@admin.action(description="匯出選取貼文為 CSV")
def export_posts_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="posts.csv"'
    writer = csv.writer(response)
    writer.writerow(["id", "title", "author", "category", "visibility", "like_count", "created_at"])
    for post in queryset.select_related("author", "category").order_by("-created_at"):
        writer.writerow(
            [
                post.id,
                post.title,
                post.author.username,
                post.category.name if post.category else "",
                post.get_visibility_display(),
                post.like_count,
                post.created_at.isoformat(),
            ]
        )
    return response


class PostAdmin(ExportMixin, admin.ModelAdmin):
    resource_classes = [PostResource]
    inlines = [CommentInline, PostHealthInsightInline]

    date_hierarchy = None
    list_display = (
        "id",
        "title_short",
        "author",
        "category",
        "visibility_badge",
        "like_count",
        "comment_count",
        "health_summary",
        "created_at",
    )
    list_filter = ("visibility", "category", "created_at", "updated_at")
    search_fields = ("title", "content", "author__username", "author__email", "tags__name")
    ordering = ("-created_at",)
    list_per_page = 25
    list_select_related = ("author", "category", "latest_health_insight")
    show_full_result_count = False

    autocomplete_fields = ("author", "category", "tags", "latest_health_insight")
    filter_horizontal = ("tags",)
    readonly_fields = ("like_count", "created_at", "updated_at", "content_preview")
    actions = (recalc_like_count, queue_health_analysis, export_posts_csv)

    fieldsets = (
        (None, {"fields": ("author", "title", "content", "content_preview")}),
        ("分類與標籤", {"fields": ("category", "tags", "visibility")}),
        ("圖片", {"fields": ("image", "image2", "image3"), "classes": ("collapse",)}),
        ("統計", {"fields": ("like_count", "latest_health_insight", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_comment_count=Count("post_comments", distinct=True))

    @admin.display(description="標題", ordering="title")
    def title_short(self, obj):
        title = (obj.title or obj.content or "").replace("\n", " ").strip()
        if len(title) > 40:
            return f"{title[:40]}…"
        return title or "—"

    @admin.display(description="可見性", ordering="visibility")
    def visibility_badge(self, obj):
        if obj.visibility == Post.VISIBILITY_PRIVATE:
            return format_html('<span style="color:#b45309;">私密</span>')
        return format_html('<span style="color:#047857;">公開</span>')

    @admin.display(description="留言", ordering="_comment_count")
    def comment_count(self, obj):
        return obj._comment_count

    @admin.display(description="健康分析")
    def health_summary(self, obj):
        insight = obj.latest_health_insight
        if not insight:
            return "—"
        if insight.status == PostHealthInsight.STATUS_PENDING:
            return "待分析"
        if insight.status == PostHealthInsight.STATUS_FAILED:
            return format_html('<span style="color:#b91c1c;">失敗</span>')
        return f"{insight.health_rank} · {insight.calories} kcal"

    @admin.display(description="內容預覽")
    def content_preview(self, obj):
        text = (obj.content or "").replace("\n", " ").strip()
        if len(text) > 200:
            text = f"{text[:200]}…"
        return text or "—"


class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "post_count")
    search_fields = ("name",)
    ordering = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_post_count=Count("posts", distinct=True))

    @admin.display(description="貼文數", ordering="_post_count")
    def post_count(self, obj):
        return obj._post_count


class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "post_count")
    search_fields = ("name",)
    ordering = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_post_count=Count("posts", distinct=True))

    @admin.display(description="貼文數", ordering="_post_count")
    def post_count(self, obj):
        return obj._post_count


class CommentLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "comment", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "comment__content")
    autocomplete_fields = ("user", "comment")
    ordering = ("-created_at",)
    list_select_related = ("user", "comment", "comment__post")
    show_full_result_count = False


class PostCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "content_short", "like_count", "created_at")
    list_filter = ("created_at", "is_pinned", "is_locked")
    search_fields = ("content", "author__username", "author__email", "post__title")
    autocomplete_fields = ("post", "author", "parent", "root")
    ordering = ("-created_at",)
    list_select_related = ("post", "author")
    readonly_fields = ("created_at", "updated_at")
    show_full_result_count = False

    @admin.display(description="內容")
    def content_short(self, obj):
        text = (obj.content or "").strip()
        if len(text) > 50:
            return f"{text[:50]}…"
        return text


class LikeAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "user__email", "post__title")
    autocomplete_fields = ("post", "user")
    ordering = ("-created_at",)
    list_select_related = ("post", "user")
    show_full_result_count = False


class FollowAdmin(admin.ModelAdmin):
    list_display = ("id", "follower", "following", "created_at")
    list_filter = ("created_at",)
    search_fields = ("follower__username", "following__username")
    autocomplete_fields = ("follower", "following")
    ordering = ("-created_at",)
    list_select_related = ("follower", "following")
    show_full_result_count = False


class CollectionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "user__email", "post__title")
    autocomplete_fields = ("user", "post")
    ordering = ("-created_at",)
    list_select_related = ("user", "post")
    show_full_result_count = False


class SearchLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "keyword", "created_at")
    list_filter = ("created_at",)
    search_fields = ("keyword", "user__username", "user__email")
    autocomplete_fields = ("user",)
    ordering = ("-created_at",)
    list_select_related = ("user",)
    readonly_fields = ("user", "keyword", "created_at")
    show_full_result_count = False


class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "actor", "notification_type", "post", "is_read", "created_at")
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("recipient__username", "recipient__email", "actor__username", "actor__email", "post__title")
    autocomplete_fields = ("recipient", "actor", "post", "comment")
    ordering = ("-created_at",)
    list_select_related = ("recipient", "actor", "post", "comment")
    readonly_fields = ("created_at", "read_at")
    show_full_result_count = False


class AiChatLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "model_name",
        "message_preview",
        "reply_preview",
        "has_image",
        "created_at",
    )
    list_filter = ("model_name", "created_at")
    search_fields = ("message", "assistant_reply", "model_name", "user__username", "user__email")
    autocomplete_fields = ("user",)
    ordering = ("-created_at",)
    list_select_related = ("user",)
    readonly_fields = (
        "user",
        "message",
        "assistant_reply",
        "image",
        "image_preview",
        "model_name",
        "created_at",
    )
    show_full_result_count = False

    fieldsets = (
        (None, {"fields": ("user", "model_name", "created_at")}),
        ("提問", {"fields": ("message", "image", "image_preview")}),
        ("回覆", {"fields": ("assistant_reply",)}),
    )

    @admin.display(description="提問")
    def message_preview(self, obj):
        text = (obj.message or "（僅圖片）").strip()
        if len(text) > 40:
            return f"{text[:40]}…"
        return text

    @admin.display(description="回覆")
    def reply_preview(self, obj):
        text = (obj.assistant_reply or "").strip()
        if len(text) > 40:
            return f"{text[:40]}…"
        return text or "—"

    @admin.display(description="有圖片", boolean=True)
    def has_image(self, obj):
        return bool(obj.image)

    @admin.display(description="圖片預覽")
    def image_preview(self, obj):
        if not obj.image:
            return "—"
        return format_html('<img src="{}" style="max-height:120px;border-radius:8px;" alt="">', obj.image.url)


@admin.action(description="重新排程健康分析")
def queue_insight_reanalysis(modeladmin, request, queryset):
    post_ids = list(queryset.values_list("post_id", flat=True).distinct())
    queued = 0
    for post_id in post_ids:
        try:
            analyze_post_health_task.delay(post_id)
        except Exception:
            analyze_post_health_task(post_id)
        queued += 1
    modeladmin.message_user(request, f"已為 {queued} 篇貼文重新排程健康分析。")


class PostHealthInsightAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "health_rank", "calories", "status", "model_name", "created_at")
    list_filter = ("health_rank", "status", "created_at")
    search_fields = ("post__title", "post__author__username", "reason", "model_name", "error_message")
    autocomplete_fields = ("post",)
    ordering = ("-created_at",)
    list_select_related = ("post", "post__author")
    readonly_fields = (
        "post",
        "calories",
        "health_rank",
        "reason",
        "status",
        "model_name",
        "confidence",
        "error_message",
        "created_at",
    )
    actions = (queue_insight_reanalysis,)
    show_full_result_count = False

    fieldsets = (
        (None, {"fields": ("post", "status", "created_at")}),
        ("分析結果", {"fields": ("health_rank", "calories", "reason", "confidence", "model_name")}),
        ("錯誤", {"fields": ("error_message",), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        return False


eatwhat_admin.register(Post, PostAdmin)
eatwhat_admin.register(Category, CategoryAdmin)
eatwhat_admin.register(Tag, TagAdmin)
eatwhat_admin.register(CommentLike, CommentLikeAdmin)
eatwhat_admin.register(PostComment, PostCommentAdmin)
eatwhat_admin.register(Like, LikeAdmin)
eatwhat_admin.register(Follow, FollowAdmin)
eatwhat_admin.register(Collection, CollectionAdmin)
eatwhat_admin.register(SearchLog, SearchLogAdmin)
eatwhat_admin.register(Notification, NotificationAdmin)
eatwhat_admin.register(AiChatLog, AiChatLogAdmin)
eatwhat_admin.register(PostHealthInsight, PostHealthInsightAdmin)
