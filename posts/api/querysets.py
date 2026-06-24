from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Q, QuerySet

from posts.models import Collection, Like, Post


def parse_positive_id_list(values) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
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


def annotate_post_list(qs: QuerySet, user) -> QuerySet:
    qs = qs.select_related("author", "author__profile", "category", "latest_health_insight").prefetch_related(
        "tags"
    ).annotate(
        comment_count=Count("post_comments", distinct=True),
        collection_count=Count("collections", distinct=True),
    )
    if user and user.is_authenticated:
        qs = qs.annotate(
            user_has_liked=Exists(Like.objects.filter(post_id=OuterRef("pk"), user_id=user.id)),
            user_has_collected=Exists(
                Collection.objects.filter(post_id=OuterRef("pk"), user_id=user.id)
            ),
        )
    return qs.order_by("-created_at", "-id")


def filter_visible_posts(qs: QuerySet, user) -> QuerySet:
    if user and user.is_authenticated:
        return qs.filter(Q(visibility=Post.VISIBILITY_PUBLIC) | Q(author_id=user.id))
    return qs.filter(visibility=Post.VISIBILITY_PUBLIC)


def apply_post_filters(qs: QuerySet, *, q: str = "", category_ids: list[int] | None = None, tag_ids: list[int] | None = None) -> QuerySet:
    if q:
        qs = qs.filter(
            Q(content__icontains=q)
            | Q(title__icontains=q)
            | Q(author__username__icontains=q)
            | Q(tags__name__icontains=q)
        ).distinct()
    if category_ids:
        qs = qs.filter(category_id__in=category_ids)
    if tag_ids:
        qs = qs.filter(tags__id__in=tag_ids).distinct()
    return qs
