import json
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

from accounts.permissions import check_role
from accounts.roles import ROLE_EDITOR

from .forms import CategoryForm, PostEditForm, PostForm, TagForm
from .models import (
    Category,
    Collection,
    CommentLike,
    Follow,
    Like,
    Notification,
    Post,
    PostComment,
    SearchLog,
    Tag,
)
from .notifications import notify_followers_new_post, notify_post_commented, notify_post_liked
from .tasks import analyze_post_health_task
from .recommendations import get_today_meal_recommendations


def _wants_json(request):
    """前端用 fetch 並帶 Accept: application/json（或 X-Requested-With）時，視為要 JSON 而非整頁導向。"""
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("accept", "").lower()
    )


def _parse_positive_id_list(values):
    """從 GET 多值參數整理出不重複的正整數 id 列表（保順序）。"""
    seen = set()
    out = []
    for raw in values:
        s = str(raw).strip()
        if not s.isdigit():
            continue
        pk = int(s)
        if pk <= 0 or pk in seen:
            continue
        seen.add(pk)
        out.append(pk)
    return out


def _annotate_subtree_reply_counts(nodes):
    """
    為樹狀留言的每個 node 設定 subtree_reply_count：
    從該則留言往下整串分支的「回覆總則數」（不含自己，含所有層級的子回覆）。
    """

    def count_under(node):
        total = 0
        for child in node.replies:
            total += 1 + count_under(child)
        node.subtree_reply_count = total
        return total

    for node in nodes:
        count_under(node)


def _attach_comment_roots(posts):
    """為每篇貼文組出留言樹狀結構（root -> replies）。"""
    for p in posts:
        comments = list(p.post_comments.all().order_by("created_at"))
        by_id = {c.id: c for c in comments}
        for c in by_id.values():
            c.replies = []
        roots = []
        for c in comments:
            if c.parent_id and c.parent_id in by_id:
                by_id[c.parent_id].replies.append(c)
            else:
                roots.append(c)
        _annotate_subtree_reply_counts(roots)
        p.comment_roots = roots


def _annotate_posts_for_user(posts_qs, user):
    if user.is_authenticated:
        return posts_qs.annotate(
            user_has_liked=Exists(Like.objects.filter(post_id=OuterRef("pk"), user_id=user.id)),
            user_has_collected=Exists(
                Collection.objects.filter(post_id=OuterRef("pk"), user_id=user.id)
            ),
        )
    return posts_qs


def feed(request):
    search_query = (request.GET.get("q") or "").strip()
    category_ids = _parse_positive_id_list(request.GET.getlist("category"))
    tag_ids = _parse_positive_id_list(request.GET.getlist("tag"))
    page_number = (request.GET.get("page") or "").strip()
    following_only = (request.GET.get("following") or "").strip().lower() in ("1", "true", "on", "yes")

    if len(search_query) > 100:
        search_query = search_query[:100]
        messages.info(request, "搜尋字數過長，已自動截斷。")

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?{urlencode({'next': request.get_full_path()})}")

        # Use the edit form for creation too, so users can add new category/tags inline.
        form = PostEditForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.instance = post
            form.save_m2m()
            notify_followers_new_post(post)
            try:
                analyze_post_health_task.delay(post.id)
            except AttributeError:
                # Celery 未啟用時，直接同步執行，避免功能失效
                analyze_post_health_task(post.id)
            messages.success(request, "已發布貼文。")
            return redirect("posts:feed")
    else:
        form = PostEditForm()

    posts = (
        Post.objects.select_related("author", "author__profile", "category", "latest_health_insight")
        .prefetch_related("likes", "post_comments", "tags")
        .annotate(
            comment_count=Count("post_comments", distinct=True),
            collection_count=Count("collections", distinct=True),
        )
    )
    if request.user.is_authenticated:
        if following_only:
            posts = posts.filter(visibility=Post.VISIBILITY_PUBLIC)
        else:
            posts = posts.filter(
                Q(visibility=Post.VISIBILITY_PUBLIC) | Q(author_id=request.user.id)
            )
    else:
        posts = posts.filter(visibility=Post.VISIBILITY_PUBLIC)
    if search_query:
        posts = posts.filter(
            Q(content__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(author__username__icontains=search_query)
            | Q(tags__name__icontains=search_query)
        ).distinct()
        if request.user.is_authenticated:
            last = (
                SearchLog.objects.filter(user=request.user, keyword=search_query)
                .order_by("-created_at")
                .first()
            )
            if last is None or last.created_at < timezone.now() - timedelta(seconds=30):
                SearchLog.objects.create(user=request.user, keyword=search_query)

    if category_ids:
        valid_cats = list(Category.objects.filter(id__in=category_ids).values_list("id", flat=True))
        if valid_cats:
            posts = posts.filter(category_id__in=valid_cats)
    if tag_ids:
        valid_tags = list(Tag.objects.filter(id__in=tag_ids).values_list("id", flat=True))
        if valid_tags:
            posts = posts.filter(tags__id__in=valid_tags).distinct()

    if following_only:
        if not request.user.is_authenticated:
            following_only = False
        else:
            following_ids = list(
                Follow.objects.filter(follower=request.user).values_list("following_id", flat=True)
            )
            following_ids = [uid for uid in following_ids if uid != request.user.id]
            if following_ids:
                posts = posts.filter(author_id__in=following_ids).exclude(author_id=request.user.id)
            else:
                posts = posts.none()

    # annotate / distinct 會讓預設 Meta.ordering 失效，須明確指定：最新貼文在上
    posts = posts.order_by("-created_at", "-id")

    show_recommendations = (
        request.user.is_authenticated
        and not search_query
        and not category_ids
        and not tag_ids
        and not following_only
        and (not page_number or page_number == "1")
    )

    today_meal_recommendations = (
        get_today_meal_recommendations(request.user, limit=3) if show_recommendations else []
    )

    posts = _annotate_posts_for_user(posts, request.user)

    paginator = Paginator(posts, 20)
    page_obj = paginator.get_page(page_number or 1)

    feed_posts = list(page_obj.object_list)

    liked_comment_ids = []
    if request.user.is_authenticated:
        comment_ids_on_page = []
        for p in feed_posts:
            for c in p.post_comments.all():
                comment_ids_on_page.append(c.id)
        if comment_ids_on_page:
            liked_comment_ids = list(
                CommentLike.objects.filter(user=request.user, comment_id__in=comment_ids_on_page).values_list(
                    "comment_id", flat=True
                )
            )

    _attach_comment_roots(feed_posts)

    return render(
        request,
        "posts/feed.html",
        {
            "posts": feed_posts,
            "page_obj": page_obj,
            "paginator": paginator,
            "form": form,
            "search_query": search_query,
            "results_count": paginator.count,
            "categories": Category.objects.all(),
            "tags": Tag.objects.all(),
            "selected_category_ids": category_ids,
            "selected_tag_ids": tag_ids,
            "following_only": following_only,
            "liked_comment_ids": liked_comment_ids,
            "today_meal_recommendations": today_meal_recommendations,
            "show_recommendations": show_recommendations,
        },
    )


@login_required(login_url=settings.LOGIN_URL)
def like_toggle(request, pk):
    """
    貼文按讚 / 取消按讚。
    - 一般表單送出：處理完後導向上一頁或動態牆（會帶 Django message）。
    - AJAX（fetch + Accept: application/json）：只回 JSON，不重新整理頁面。
    """
    # 依照網址上的主鍵找出貼文；找不到就回 404
    post = get_object_or_404(Post, pk=pk)

    # 這個 view 只接受 POST（按鈕送出）；GET 就送回動態牆，避免誤觸網址改到資料
    if request.method != "POST":
        return redirect("posts:feed")

    wants_json = _wants_json(request)

    # 查目前使用者是否已經對這篇貼文按過讚（Like 是中介資料表）
    like = post.likes.filter(user=request.user).first()
    # liked 表示「這次操作完成後，使用者是否處於已按讚狀態」
    liked = False

    if like:
        # 已按讚 → 刪除那筆 Like，變成未按讚
        like.delete()
        liked = False
        if not wants_json:
            messages.info(request, "已取消按讚。")
    else:
        # 未按讚 → 建立 Like（get_or_create 避免重複鍵錯誤）
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if created:
            notify_post_liked(like)
        liked = True
        if not wants_json:
            messages.success(request, "已按讚。")

    # like_count 存在 Post 上，由 signal 維護；這裡從資料庫再讀一次確保數字最新
    post.refresh_from_db(fields=["like_count"])

    if wants_json:
        # 非同步模式：只回兩個欄位，給前端 Alpine / fetch 更新畫面用
        return JsonResponse(
            {
                "is_liked": liked,  # 現在是否為「已按讚」
                "like_count": post.like_count,  # 目前的讚數（整數）
            }
        )

    # 一般表單模式：導回表單裡 hidden「next」指定的安全網址，否則回動態牆
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("posts:feed")


@login_required(login_url=settings.LOGIN_URL)
def collect_toggle(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method != "POST":
        return redirect("posts:feed")

    wants_json = _wants_json(request)
    collection = post.collections.filter(user=request.user).first()
    collected = False
    if collection:
        collection.delete()
        collected = False
        if not wants_json:
            messages.info(request, "已取消收藏。")
    else:
        Collection.objects.get_or_create(user=request.user, post=post)
        collected = True
        if not wants_json:
            messages.success(request, "已收藏貼文。")

    if wants_json:
        return JsonResponse(
            {
                "is_collected": collected,
                "collection_count": post.collections.count(),
            }
        )

    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("posts:feed")


@login_required(login_url=settings.LOGIN_URL)
def comment_like_toggle(request, pk, comment_pk):
    post = get_object_or_404(Post, pk=pk)
    comment = get_object_or_404(PostComment, pk=comment_pk, post_id=post.id)
    if request.method != "POST":
        return redirect("posts:post_detail", pk=pk)

    wants_json = _wants_json(request)
    existing = CommentLike.objects.filter(user=request.user, comment=comment).first()
    if existing:
        existing.delete()
        liked = False
        if not wants_json:
            messages.info(request, "已取消留言按讚。")
    else:
        CommentLike.objects.get_or_create(user=request.user, comment=comment)
        liked = True
        if not wants_json:
            messages.success(request, "已對留言按讚。")
    comment.refresh_from_db(fields=["like_count"])

    if wants_json:
        return JsonResponse({"is_liked": liked, "like_count": comment.like_count})

    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("posts:post_detail", pk=pk)


@login_required(login_url=settings.LOGIN_URL)
def comment_create(request, pk):
    post = get_object_or_404(Post, pk=pk)
    wants_json = _wants_json(request)

    if request.method != "POST":
        if wants_json:
            return JsonResponse({"ok": False, "error": "不支援的請求方式。"}, status=405)
        return redirect("posts:feed")

    content = (request.POST.get("content") or "").strip()
    parent_id_raw = (request.POST.get("parent_id") or "").strip()

    if len(content) > 2000:
        content = content[:2000]

    parent = None
    if parent_id_raw.isdigit():
        parent = get_object_or_404(PostComment, pk=int(parent_id_raw), post_id=post.id)
        if parent.is_locked:
            msg = "此留言已鎖定，無法回覆。"
            if wants_json:
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
            next_url = (request.POST.get("next") or "").strip()
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect("posts:feed")

    if not content:
        if wants_json:
            return JsonResponse({"ok": False, "error": "留言內容不可為空。"}, status=400)
        messages.error(request, "留言內容不可為空。")
        next_url = (request.POST.get("next") or "").strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("posts:feed")

    comment = PostComment.objects.create(
        post=post,
        author=request.user,
        content=content,
        parent=parent,
    )
    if parent:
        comment.root_id = parent.root_id or parent.id
    else:
        comment.root_id = comment.id
    comment.save(update_fields=["root"])
    notify_post_commented(comment)

    if wants_json:
        comment = PostComment.objects.select_related("author", "author__profile").get(pk=comment.pk)
        comment.replies = []
        _annotate_subtree_reply_counts([comment])
        liked_comment_ids = list(
            CommentLike.objects.filter(user=request.user, comment__post_id=post.id).values_list(
                "comment_id", flat=True
            )
        )
        html = render_to_string(
            "posts/_comment_node.html",
            {"node": comment, "post": post, "liked_comment_ids": liked_comment_ids},
            request=request,
        )
        comment_count = PostComment.objects.filter(post_id=post.id).count()
        return JsonResponse(
            {
                "ok": True,
                "html": html,
                "comment_count": comment_count,
                "parent_id": parent.id if parent else None,
            }
        )

    messages.success(request, "留言已送出。")
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("posts:feed")


@login_required(login_url=settings.LOGIN_URL)
def comment_edit(request, pk, comment_pk):
    post = get_object_or_404(Post, pk=pk)
    comment = get_object_or_404(PostComment, pk=comment_pk, post_id=post.id)
    if comment.author_id != request.user.id:
        messages.error(request, "只能編輯自己的留言。")
        return redirect("posts:post_detail", pk=post.id)
    if request.method != "POST":
        return redirect("posts:post_detail", pk=post.id)

    content = (request.POST.get("content") or "").strip()
    if len(content) > 2000:
        content = content[:2000]
    if not content:
        messages.error(request, "留言內容不可為空。")
    else:
        comment.content = content
        comment.save(update_fields=["content", "updated_at"])
        messages.success(request, "留言已更新。")

    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("posts:post_detail", pk=post.id)


@login_required(login_url=settings.LOGIN_URL)
def comment_delete(request, pk, comment_pk):
    post = get_object_or_404(Post, pk=pk)
    comment = get_object_or_404(PostComment, pk=comment_pk, post_id=post.id)
    if comment.author_id != request.user.id:
        messages.error(request, "只能刪除自己的留言。")
        return redirect("posts:post_detail", pk=post.id)
    if request.method == "POST":
        comment.delete()
        messages.success(request, "留言已刪除。")

    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("posts:post_detail", pk=post.id)


def post_detail(request, pk):
    post = get_object_or_404(
        Post.objects.select_related("author", "author__profile", "category", "latest_health_insight")
        .prefetch_related("tags", "post_comments", "likes")
        .annotate(collection_count=Count("collections", distinct=True)),
        pk=pk,
    )
    if post.visibility == Post.VISIBILITY_PRIVATE and post.author_id != getattr(request.user, "id", None):
        messages.error(request, "此貼文僅作者可查看。")
        return redirect("posts:feed")
    is_liked = False
    is_collected = False
    if request.user.is_authenticated:
        is_liked = post.likes.filter(user=request.user).exists()
        is_collected = post.collections.filter(user=request.user).exists()
    comments = (
        PostComment.objects.filter(post_id=post.id)
        .select_related("author", "author__profile", "parent", "root")
        .order_by("created_at")
    )
    by_id = {c.id: c for c in comments}
    for c in by_id.values():
        c.replies = []
    roots = []
    for c in comments:
        if c.parent_id and c.parent_id in by_id:
            by_id[c.parent_id].replies.append(c)
        else:
            roots.append(c)

    _annotate_subtree_reply_counts(roots)

    liked_comment_ids = []
    if request.user.is_authenticated:
        liked_comment_ids = list(
            CommentLike.objects.filter(user=request.user, comment__post_id=post.id).values_list(
                "comment_id", flat=True
            )
        )

    return render(
        request,
        "posts/post_detail.html",
        {
            "post": post,
            "is_liked": is_liked,
            "is_collected": is_collected,
            "comment_roots": roots,
            "liked_comment_ids": liked_comment_ids,
        },
    )


@login_required(login_url=settings.LOGIN_URL)
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk, author=request.user)
    if request.method == "POST":
        form = PostEditForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "貼文已更新。")
            return redirect("posts:post_detail", pk=post.pk)
    else:
        form = PostEditForm(instance=post)
    return render(request, "posts/post_edit.html", {"form": form, "post": post})


@login_required(login_url=settings.LOGIN_URL)
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk, author=request.user)
    if request.method == "POST":
        post.delete()
        messages.success(request, "貼文已刪除。")
        return redirect("posts:feed")
    return render(request, "posts/post_confirm_delete.html", {"post": post})


def _staff_required(request):
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if not check_role(request.user, ROLE_EDITOR):
        messages.error(request, "需要編輯以上權限才能操作。")
        return redirect("posts:feed")
    return None


def category_manage(request):
    blocked = _staff_required(request)
    if blocked is not None:
        return blocked

    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "已新增分類。")
            return redirect("posts:category_manage")
    else:
        form = CategoryForm()
    categories = Category.objects.order_by("name")
    return render(request, "posts/category_manage.html", {"form": form, "categories": categories})


def category_delete(request, pk):
    blocked = _staff_required(request)
    if blocked is not None:
        return blocked
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
        messages.success(request, "已刪除分類。")
    return redirect("posts:category_manage")


def tag_manage(request):
    blocked = _staff_required(request)
    if blocked is not None:
        return blocked

    if request.method == "POST":
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "已新增標籤。")
            return redirect("posts:tag_manage")
    else:
        form = TagForm()
    tags = Tag.objects.order_by("name")
    return render(request, "posts/tag_manage.html", {"form": form, "tags": tags})


def tag_delete(request, pk):
    blocked = _staff_required(request)
    if blocked is not None:
        return blocked
    tag = get_object_or_404(Tag, pk=pk)
    if request.method == "POST":
        tag.delete()
        messages.success(request, "已刪除標籤。")
    return redirect("posts:tag_manage")


@login_required(login_url=settings.LOGIN_URL)
def collections_list(request):
    visibility_filter = Q(post__visibility=Post.VISIBILITY_PUBLIC) | Q(
        post__author_id=request.user.id
    )
    base_collections = Collection.objects.filter(user=request.user).filter(
        visibility_filter
    )

    category_raw = (request.GET.get("category") or "").strip()
    selected_category_id = None
    if category_raw.isdigit():
        cid = int(category_raw)
        if base_collections.filter(post__category_id=cid).exists():
            selected_category_id = cid

    collections = base_collections
    if selected_category_id:
        collections = collections.filter(post__category_id=selected_category_id)

    collections = (
        collections.select_related(
            "post", "post__author", "post__author__profile", "post__category"
        )
        .prefetch_related("post__tags")
        .order_by("-created_at")
    )
    posts = [c.post for c in collections]
    paginator = Paginator(posts, 20)
    page_obj = paginator.get_page((request.GET.get("page") or "").strip() or 1)

    filter_categories = (
        Category.objects.filter(
            posts__collections__user=request.user,
        )
        .filter(
            Q(posts__visibility=Post.VISIBILITY_PUBLIC)
            | Q(posts__author_id=request.user.id)
        )
        .annotate(
            collected_count=Count(
                "posts__collections",
                filter=Q(posts__collections__user=request.user)
                & (
                    Q(posts__visibility=Post.VISIBILITY_PUBLIC)
                    | Q(posts__author_id=request.user.id)
                ),
                distinct=True,
            )
        )
        .order_by("name")
        .distinct()
    )

    return render(
        request,
        "posts/collections.html",
        {
            "posts": page_obj.object_list,
            "collections_count": paginator.count,
            "page_obj": page_obj,
            "paginator": paginator,
            "filter_categories": filter_categories,
            "selected_category_id": selected_category_id,
        },
    )


@login_required(login_url=settings.LOGIN_URL)
def notifications_list(request):
    notifications = (
        Notification.objects.filter(recipient=request.user)
        .select_related("actor", "post", "comment")
        .order_by("-created_at", "-id")
    )
    paginator = Paginator(notifications, 20)
    page_obj = paginator.get_page((request.GET.get("page") or "").strip() or 1)
    return render(
        request,
        "posts/notifications.html",
        {
            "notifications": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
        },
    )


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_read()
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(notification.target_url())


@login_required(login_url=settings.LOGIN_URL)
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("posts:notifications_list")

