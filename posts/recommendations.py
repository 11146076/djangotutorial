from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext as _

from posts.models import Collection, Post, SearchLog, Tag

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_MAX_SUGGESTIONS = 3
_MAX_TERM_LEN = 40

RECOMMENDATION_COLLECTION_LIMIT = 40
RECOMMENDATION_SEARCH_LIMIT = 15
RECOMMENDATION_DEFAULT_LIMIT = 6
RECOMMENDATION_FEED_TOP_COUNT = 3
RECOMMENDATION_CANDIDATE_LIMIT = 80


@dataclass
class RecommendedPost:
    post: Post
    reason: str
    score: float
    source: str


def extract_bold_terms(text: str) -> list[str]:
    terms: list[str] = []
    for match in _BOLD_PATTERN.finditer(text or ""):
        term = match.group(1).strip()
        if not term or len(term) > _MAX_TERM_LEN:
            continue
        if term not in terms:
            terms.append(term)
    return terms


def _match_tag(term: str) -> Tag | None:
    tag = Tag.objects.filter(name__iexact=term).first()
    if tag:
        return tag
    return Tag.objects.filter(name__icontains=term).order_by("name").first()


def build_post_suggestions(reply: str) -> list[dict[str, str | int]]:
    """從 AI 助理回覆中的 **粗體** 詞彙產生標籤／搜尋捷徑（非個人化推薦）。"""
    suggestions: list[dict[str, str | int]] = []
    seen: set[str] = set()

    for term in extract_bold_terms(reply):
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)

        tag = _match_tag(term)
        if tag:
            suggestions.append({"type": "tag", "id": tag.id, "name": tag.name})
        else:
            suggestions.append({"type": "search", "query": term, "name": term})

        if len(suggestions) >= _MAX_SUGGESTIONS:
            break

    return suggestions


def _build_interest_profile(user) -> dict[str, Any]:
    """依收藏與搜尋紀錄建立興趣權重。"""
    tag_weights: dict[int, float] = defaultdict(float)
    tag_labels: dict[int, str] = {}
    category_weights: dict[int, float] = defaultdict(float)
    category_labels: dict[int, str] = {}
    keywords: list[str] = []

    collections = list(
        Collection.objects.filter(user=user)
        .select_related("post", "post__category")
        .prefetch_related("post__tags")
        .order_by("-created_at")[:RECOMMENDATION_COLLECTION_LIMIT]
    )
    total_coll = len(collections) or 1
    for index, coll in enumerate(collections):
        recency = 1.0 + (total_coll - index) / total_coll
        post = coll.post
        if post.category_id:
            category_weights[post.category_id] += 2.0 * recency
            if post.category_id not in category_labels and post.category:
                category_labels[post.category_id] = post.category.name
        for tag in post.tags.all():
            tag_weights[tag.id] += 3.0 * recency
            tag_labels.setdefault(tag.id, tag.name)

    seen_kw: set[str] = set()
    for row in SearchLog.objects.filter(user=user).order_by("-created_at")[:RECOMMENDATION_SEARCH_LIMIT]:
        keyword = (row.keyword or "").strip()
        if not keyword:
            continue
        key = keyword.casefold()
        if key in seen_kw:
            continue
        seen_kw.add(key)
        keywords.append(keyword)

    return {
        "tag_weights": dict(tag_weights),
        "tag_labels": tag_labels,
        "category_weights": dict(category_weights),
        "category_labels": category_labels,
        "keywords": keywords,
        "collection_count": len(collections),
        "search_count": len(keywords),
    }


def _score_post(
    post: Post,
    *,
    tag_weights: dict[int, float],
    tag_labels: dict[int, str],
    category_weights: dict[int, float],
    category_labels: dict[int, str],
    keywords: list[str],
) -> tuple[float, str, str]:
    score = 0.0
    best_reason = ""
    best_source = "popular"

    post_tag_ids = {tag.id for tag in post.tags.all()}
    for tag_id in post_tag_ids:
        weight = tag_weights.get(tag_id, 0)
        if weight > 0:
            contribution = weight * 1.2
            if contribution >= score:
                score = contribution
                best_source = "collection_tag"
                best_reason = _("與你收藏的標籤「%(name)s」相似") % {"name": tag_labels.get(tag_id, "")}

    if post.category_id and post.category_id in category_weights:
        contribution = category_weights[post.category_id] * 1.0
        if contribution > score:
            score = contribution
            best_source = "collection_category"
            best_reason = _("與你收藏過的「%(name)s」分類相似") % {
                "name": category_labels.get(post.category_id, "")
            }

    title_lower = (post.title or "").casefold()
    content_lower = (post.content or "").casefold()
    tag_names = [tag.name.casefold() for tag in post.tags.all()]

    for keyword in keywords:
        kw_lower = keyword.casefold()
        contribution = 0.0
        source = "search"
        reason = _("符合你曾搜尋的「%(keyword)s」") % {"keyword": keyword}
        if kw_lower and kw_lower in title_lower:
            contribution = 3.5
        elif any(kw_lower in name for name in tag_names):
            contribution = 3.0
        elif kw_lower and kw_lower in content_lower:
            contribution = 1.8
        if contribution > score:
            score = contribution
            best_source = source
            best_reason = reason

    score += post.like_count * 0.05
    if not best_reason:
        best_reason = _("依社群熱門程度推薦")
        best_source = "popular"
    return score, best_reason, best_source


def _popular_fallback(*, user, limit: int, exclude_post_ids: set[int]) -> list[RecommendedPost]:
    posts = (
        Post.objects.filter(visibility=Post.VISIBILITY_PUBLIC)
        .exclude(author_id=user.id)
        .select_related("author", "category")
        .prefetch_related("tags")
        .order_by("-like_count", "-created_at", "-id")
    )
    if exclude_post_ids:
        posts = posts.exclude(pk__in=exclude_post_ids)
    collected_ids = set(Collection.objects.filter(user=user).values_list("post_id", flat=True))
    if collected_ids:
        posts = posts.exclude(pk__in=collected_ids)

    items: list[RecommendedPost] = []
    for post in posts[:limit]:
        items.append(
            RecommendedPost(
                post=post,
                reason=_("依社群熱門貼文推薦"),
                score=float(post.like_count),
                source="popular",
            )
        )
    return items


def get_personalized_recommendations(
    user,
    *,
    limit: int = RECOMMENDATION_DEFAULT_LIMIT,
    exclude_post_ids: list[int] | set[int] | None = None,
) -> tuple[list[RecommendedPost], dict[str, Any]]:
    """
    個人化推薦：綜合收藏貼文的標籤／分類，以及搜尋紀錄關鍵字加權打分。
    資料不足時改推熱門公開貼文。
    """
    if not user or not getattr(user, "is_authenticated", False) or not user.is_authenticated:
        return [], {"strategy": "none", "collection_signals": 0, "search_signals": 0}

    exclude_ids = set(exclude_post_ids or [])
    profile = _build_interest_profile(user)
    tag_weights = profile["tag_weights"]
    category_weights = profile["category_weights"]
    keywords = profile["keywords"]

    has_signals = bool(tag_weights or category_weights or keywords)
    if not has_signals:
        items = _popular_fallback(user=user, limit=limit, exclude_post_ids=exclude_ids)
        return items, {
            "strategy": "popular",
            "collection_signals": 0,
            "search_signals": 0,
        }

    candidate_filter = Q()
    if tag_weights:
        candidate_filter |= Q(tags__id__in=tag_weights.keys())
    if category_weights:
        candidate_filter |= Q(category_id__in=category_weights.keys())
    for keyword in keywords:
        candidate_filter |= (
            Q(title__icontains=keyword)
            | Q(content__icontains=keyword)
            | Q(tags__name__icontains=keyword)
        )

    posts = (
        Post.objects.filter(visibility=Post.VISIBILITY_PUBLIC)
        .filter(candidate_filter)
        .exclude(author_id=user.id)
        .select_related("author", "author__profile", "category")
        .prefetch_related("tags")
        .distinct()
    )
    if exclude_ids:
        posts = posts.exclude(pk__in=exclude_ids)
    collected_ids = set(Collection.objects.filter(user=user).values_list("post_id", flat=True))
    if collected_ids:
        posts = posts.exclude(pk__in=collected_ids)

    scored: list[RecommendedPost] = []
    for post in posts[:RECOMMENDATION_CANDIDATE_LIMIT]:
        score, reason, source = _score_post(
            post,
            tag_weights=tag_weights,
            tag_labels=profile["tag_labels"],
            category_weights=category_weights,
            category_labels=profile["category_labels"],
            keywords=keywords,
        )
        if score <= 0:
            continue
        scored.append(RecommendedPost(post=post, reason=reason, score=score, source=source))

    scored.sort(key=lambda item: (-item.score, -item.post.created_at.timestamp(), -item.post.id))
    items = scored[:limit]
    if not items:
        items = _popular_fallback(user=user, limit=limit, exclude_post_ids=exclude_ids)
        strategy = "popular"
    else:
        strategy = "personalized"

    # 首頁動態牆已列出全部貼文時，排除後可能為空；改不排除再取一次
    if not items and exclude_ids:
        return get_personalized_recommendations(user, limit=limit, exclude_post_ids=None)

    return items, {
        "strategy": strategy,
        "collection_signals": profile["collection_count"],
        "search_signals": profile["search_count"],
    }
