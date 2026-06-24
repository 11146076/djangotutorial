from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q
from django.utils.html import strip_tags

from posts.models import Collection, Follow, Like, Post, SearchLog, Tag

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_MAX_SUGGESTIONS = 3
_MAX_TERM_LEN = 40

MAX_SIGNAL_POSTS = 50
MAX_SEARCH_TERMS = 8
MAX_CANDIDATES = 160


@dataclass(frozen=True)
class MealRecommendation:
    post: Post
    reason: str
    badges: tuple[str, ...]
    score: float


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


def _candidate_filter(profile) -> Q:
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


def _post_text(post: Post) -> str:
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


def _score_post(post: Post, profile) -> tuple[float, list[str]]:
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

    text = _post_text(post)
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

    candidate_query = _candidate_filter(profile)
    candidates: list[Post] = []
    if candidate_query:
        candidates.extend(
            base_qs.filter(candidate_query).distinct().order_by("-created_at", "-id")[:MAX_CANDIDATES]
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
        score, reasons = _score_post(post, profile)
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
    picked = recommendations[:limit]

    if len(picked) < limit:
        already_ids = {rec.post.id for rec in picked}
        filler_posts = (
            Post.objects.filter(visibility=Post.VISIBILITY_PUBLIC)
            .exclude(id__in=already_ids)
            .select_related("author", "author__profile", "category", "latest_health_insight")
            .prefetch_related("tags")
            .annotate(
                comment_count=Count("post_comments", distinct=True),
                collection_count=Count("collections", distinct=True),
            )
            .order_by("-like_count", "-created_at", "-id")[: limit - len(picked)]
        )
        for post in filler_posts:
            score, reasons = _score_post(post, profile)
            badges = []
            if post.category:
                badges.append(post.category.name)
            badges.extend(f"#{tag.name}" for tag in post.tags.all()[:2])
            picked.append(
                MealRecommendation(
                    post=post,
                    reason="；".join(reasons[:2]) if reasons else "熱門公開貼文推薦",
                    badges=tuple(badges[:3]),
                    score=score,
                )
            )

    return picked[:limit]
