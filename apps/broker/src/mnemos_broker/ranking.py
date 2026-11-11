"""Lexical relevance plus recency, capped to a context token budget.

This is deliberately simple and deterministic: the product needs a defensible
selection rule, not a second model. The score favours items that share query
terms, breaks ties by recency, and never crosses the scope boundary because the
caller only passes items already filtered by owner and scope.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, datetime

from .prompts import MemoryItem

DEFAULT_CONTEXT_TOKENS = 2048
MAX_CONTEXT_TOKENS = 4000

_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "you",
        "your",
    }
)


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4)) + 12


def context_budget(max_answer_tokens: int) -> int:
    return max(512, min(MAX_CONTEXT_TOKENS, max_answer_tokens * 8))


def _terms(text: str) -> list[str]:
    from .filter import normalise_words

    return [word for word in normalise_words(text) if word not in _STOPWORDS]


def score_item(question_terms: set[str], item: MemoryItem, now: datetime) -> float:
    item_terms = _terms(item.text)
    if not item_terms:
        return 0.0
    counts: dict[str, int] = {}
    for term in item_terms:
        counts[term] = counts.get(term, 0) + 1
    overlap = sum(counts.get(term, 0) for term in question_terms)
    lexical = overlap / math.sqrt(len(item_terms) + 1)
    age_days = max(0.0, (now - item.created_at.astimezone(UTC)).total_seconds() / 86_400)
    recency = 0.25 * math.exp(-age_days / 30.0)
    return lexical + recency


def rank_items(
    question: str,
    items: list[MemoryItem],
    *,
    max_answer_tokens: int,
    now: datetime | None = None,
) -> tuple[list[MemoryItem], int]:
    """Return selected items and the number of candidates considered."""
    if not items:
        return [], 0
    moment = now or datetime.now(UTC)
    question_terms = set(_terms(question))
    scored = [replace(item, score=score_item(question_terms, item, moment)) for item in items]
    scored.sort(key=lambda item: (-item.score, -item.created_at.timestamp(), item.item_id))

    budget = min(MAX_CONTEXT_TOKENS, context_budget(max_answer_tokens))
    selected: list[MemoryItem] = []
    used = 0
    for item in scored:
        cost = estimate_tokens(item.text)
        if selected and used + cost > budget:
            continue
        if not selected and cost > budget:
            max_chars = max(64, budget * 4)
            truncated = item.text[:max_chars].rsplit(" ", 1)[0]
            item = replace(item, text=truncated)
            cost = estimate_tokens(item.text)
        selected.append(item)
        used += cost
        if used >= budget:
            break
    return selected, len(scored)
