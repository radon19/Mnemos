from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mnemos_broker.prompts import MemoryItem
from mnemos_broker.ranking import (
    MAX_CONTEXT_TOKENS,
    context_budget,
    estimate_tokens,
    rank_items,
)

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def item(text: str, *, days_ago: int = 0, item_id: str = "id") -> MemoryItem:
    return MemoryItem(
        item_id=item_id,
        scope="health",
        created_at=NOW - timedelta(days=days_ago),
        text=text,
    )


def test_lexical_overlap_outranks_unrelated() -> None:
    items = [
        item("The garden has tomatoes and basil.", item_id="garden"),
        item("My flight to Lisbon departs at nine.", item_id="flight"),
    ]
    selected, considered = rank_items("When is my flight?", items, max_answer_tokens=256)
    assert considered == 2
    assert [entry.item_id for entry in selected] == ["flight", "garden"]


def test_recency_breaks_a_tie() -> None:
    items = [
        item("dentist appointment", days_ago=30, item_id="old"),
        item("dentist appointment", days_ago=1, item_id="new"),
    ]
    selected, _ = rank_items("dentist appointment", items, max_answer_tokens=256)
    assert [entry.item_id for entry in selected][:2] == ["new", "old"]


def test_empty_input_is_safe() -> None:
    selected, considered = rank_items("anything", [], max_answer_tokens=256)
    assert selected == []
    assert considered == 0


def test_context_budget_is_bounded() -> None:
    assert context_budget(16) >= 512
    assert context_budget(8192) == MAX_CONTEXT_TOKENS
    assert estimate_tokens("abc") == 13


def test_oversized_first_item_is_truncated_to_budget() -> None:
    huge = "word " * 2000
    selected, _ = rank_items("word", [item(huge)], max_answer_tokens=16)
    assert len(selected) == 1
    assert len(selected[0].text) < len(huge)
    assert estimate_tokens(selected[0].text) <= MAX_CONTEXT_TOKENS


def test_budget_stops_adding_more_items() -> None:
    filled = "token " * 500
    extra = "tail " * 500
    selected, _ = rank_items(
        "token tail", [item(filled, item_id="a"), item(extra, item_id="b")], max_answer_tokens=64
    )
    assert len(selected) == 1


def test_scores_are_recorded() -> None:
    selected, _ = rank_items("flight", [item("flight at nine")], max_answer_tokens=128)
    assert selected[0].score > 0
