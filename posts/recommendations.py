from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q
from django.utils.html import strip_tags
from django.utils.translation import gettext as _

from posts.models import Collection, Follow, Like, Post, SearchLog, Tag

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_MAX_SUGGESTIONS = 3
_MAX_TERM_LEN = 40

RECOMMENDATION_COLLECTION_LIMIT = 40
RECOMMENDATION_SEARCH_LIMIT = 15
RECOMMENDATION_DEFAULT_LIMIT = 6
RECOMMENDATION_FEED_TOP_COUNT = 3
RECOMMENDATION_CANDIDATE_LIMIT = 80

MAX_SIGNAL_POSTS = 50
MAX_SEARCH_TERMS = 8
MAX_MEAL_CANDIDATES = 160


@dataclass(frozen=True)
class MealRecommendation:
    post: Post
    reason: str
    badges: tuple[str, ...]
    score: float


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


def _normalized_terms(*values: str) -> list[str]:
    seen = set()
    terms: list[str] = []
    for value in values:
        raw = (value or "").strip()
        if not raw:
            continue
        parts = [raw]
        parts.extend(p for p in re.split(r"[\s,，、/／;；|]+", raw) if p)
        for part in parts:
            term = part.strip().lower()
            if len(term) < 2 or term in seen:
                continue
            seen.add(term)
            terms.append(term)
            if len(terms) >= MAX_SEARCH_TERMS:
                return terms
    return terms


def _collect_post_preferences(posts, *, weight: int, category_weights: Counter, tag_weights: Counter) -> None:
    for post in posts:
        if post.category_id:
            category_weights[post.category_id] += weight
        for tag in post.tags.all():
            tag_weights[tag.id] += weight


def _build_preference_profile(user):
    category_weights: Counter[int] = Counter()
    tag_weights: Counter[int] = Counter()

    collected_posts = [
        item.post
        for item in Collection.objects.filter(user=user)
        .select_related("post", "post__category")
        .prefetch_related("post__tags")
        .order_by("-created_at")[:MAX_SIGNAL_POSTS]
    ]
    liked_posts = [
        item.post
        for item in Like.objects.filter(user=user)
        .select_related("post", "post__category")
        .prefetch_related("post__tags")
        .order_by("-created_at")[:MAX_SIGNAL_POSTS]
    ]
    own_posts = list(
        Post.objects.filter(author=user)
        .select_related("category")
        .prefetch_related("tags")
        .order_by("-created_at")[:MAX_SIGNAL_POSTS]
    )

    _collect_post_preferences(collected_posts, weight=5, category_weights=category_weights, tag_weights=tag_weights)
    _collect_post_preferences(liked_posts, weight=4, category_weights=category_weights, tag_weights=tag_weights)
    _collect_post_preferences(own_posts, weight=2, category_weights=category_weights, tag_weights=tag_weights)

    search_terms = _normalized_terms(
        *SearchLog.objects.filter(user=user).order_by("-created_at").values_list("keyword", flat=True)[:MAX_SEARCH_TERMS]
    )
    try:
        dietary_preference = user.profile.dietary_preference
    except ObjectDoesNotExist:
        dietary_preference = ""
    dietary_terms = _normalized_terms(dietary_preference)
    followed_user_ids = set(Follow.objects.filter(follower=user).values_list("following_id", flat=True))

    return {
        "category_weights": category_weights,
        "tag_weights": tag_weights,
        "search_terms": search_terms,
        "dietary_terms": dietary_terms,
        "followed_user_ids": followed_user_ids,
    }


def _meal_candidate_filter(profile) -> Q:
    query = Q()
    if profile["category_weights"]:
        query |= Q(category_id__in=profile["category_weights"].keys())
    if profile["tag_weights"]:
        query |= Q(tags__id__in=profile["tag_weights"].keys())
    if profile["followed_user_ids"]:
        query |= Q(author_id__in=profile["followed_user_ids"])
    for term in [*profile["search_terms"], *profile["dietary_terms"]]:
        query |= (
            Q(title__icontains=term)
            | Q(content__icontains=term)
            | Q(category__name__icontains=term)
            | Q(tags__name__icontains=term)
            | Q(author__username__icontains=term)
        )
    return query


def _meal_post_text(post: Post) -> str:
    tag_text = " ".join(tag.name for tag in post.tags.all())
    category_text = post.category.name if post.category else ""
    return " ".join(
        [
            post.title or "",
            strip_tags(post.content or ""),
            category_text,
            tag_text,
            post.author.username,
        ]
    ).lower()


def _score_meal_post(post: Post, profile) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    category_weights = profile["category_weights"]
    tag_weights = profile["tag_weights"]

    if post.category_id and post.category_id in category_weights:
        score += category_weights[post.category_id]
        reasons.append(f"符合你常互動的「{post.category.name}」分類")

    matched_tags = [tag.name for tag in post.tags.all() if tag.id in tag_weights]
    if matched_tags:
        score += min(10, sum(tag_weights[tag.id] for tag in post.tags.all() if tag.id in tag_weights))
        reasons.append(f"含有你喜歡的 #{matched_tags[0]} 標籤")

    if post.author_id in profile["followed_user_ids"]:
        score += 5
        reasons.append(f"來自你追蹤的 {post.author.username}")

    text = _meal_post_text(post)
    for term in profile["search_terms"]:
        if term in text:
            score += 4
            reasons.append(f"和你最近搜尋「{term}」有關")
            break

    for term in profile["dietary_terms"]:
        if term in text:
            score += 3
            reasons.append(f"貼近你的飲食偏好「{term}」")
            break

    insight = post.latest_health_insight
    if insight and insight.status == "completed":
        if insight.health_rank == "A":
            score += 2.5
            reasons.append("健康等級 A，適合今天清爽一點")
        elif insight.health_rank == "B":
            score += 1.5
            reasons.append("健康等級 B，均衡度不錯")

    popularity = (post.like_count * 0.35) + (getattr(post, "comment_count", 0) * 0.25) + (
        getattr(post, "collection_count", 0) * 0.45
    )
    if popularity:
        score += min(6, popularity)
        if not reasons:
            reasons.append("近期互動熱度不錯")

    if not reasons:
        reasons.append("近期新鮮靈感，適合當作今天候選")

    return score, reasons


def get_today_meal_recommendations(user, *, limit: int = 3) -> list[MealRecommendation]:
    """首頁「今天吃什麼？」卡片：綜合收藏、按讚、搜尋、追蹤與飲食偏好。"""
    if not getattr(user, "is_authenticated", False):
        return []

    profile = _build_preference_profile(user)
    base_qs = (
        Post.objects.filter(visibility=Post.VISIBILITY_PUBLIC)
        .exclude(author=user)
        .select_related("author", "author__profile", "category", "latest_health_insight")
        .prefetch_related("tags")
        .annotate(
            comment_count=Count("post_comments", distinct=True),
            collection_count=Count("collections", distinct=True),
        )
    )

    candidate_query = _meal_candidate_filter(profile)
    candidates: list[Post] = []
    if candidate_query:
        candidates.extend(
            base_qs.filter(candidate_query).distinct().order_by("-created_at", "-id")[:MAX_MEAL_CANDIDATES]
        )

    seen_ids = {post.id for post in candidates}
    fallback_count = max(limit * 8, 12)
    fallback_qs = base_qs.exclude(id__in=seen_ids) if seen_ids else base_qs
    candidates.extend(fallback_qs.distinct().order_by("-like_count", "-created_at", "-id")[:fallback_count])

    recommendations: list[MealRecommendation] = []
    seen_ids.clear()
    for post in candidates:
        if post.id in seen_ids:
            continue
        seen_ids.add(post.id)
        score, reasons = _score_meal_post(post, profile)
        badges = []
        if post.category:
            badges.append(post.category.name)
        badges.extend(f"#{tag.name}" for tag in post.tags.all()[:2])
        recommendations.append(
            MealRecommendation(
                post=post,
                reason="；".join(reasons[:2]),
                badges=tuple(badges[:3]),
                score=score,
            )
        )

    recommendations.sort(key=lambda rec: (rec.score, rec.post.created_at, rec.post.id), reverse=True)
    return recommendations[:limit]
