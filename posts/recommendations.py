from __future__ import annotations

import re

from posts.models import Tag

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_MAX_SUGGESTIONS = 3
_MAX_TERM_LEN = 40


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
