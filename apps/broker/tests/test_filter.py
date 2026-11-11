from __future__ import annotations

import base64

from mnemos_broker.filter import MIN_LEAK_WORDS, answer_preview, check_answer

MEMORY = (
    "The quick brown fox jumps over the lazy dog every single morning "
    "before breakfast in the garden."
)


def test_verbatim_run_is_blocked() -> None:
    answer = "Sure: The quick brown fox jumps over the lazy dog every single morning"
    result = check_answer(answer, [MEMORY])
    assert result.leaked is True
    assert result.matched_memory == 0
    assert result.reason is not None


def test_summary_is_allowed() -> None:
    answer = "Your morning routine involves a fox in the garden, before breakfast."
    result = check_answer(answer, [MEMORY])
    assert result.leaked is False
    assert result.reason is None


def test_short_memory_cannot_trip_the_twelve_word_rule() -> None:
    memory = "The launch code is blue."
    result = check_answer("The launch code is blue.", [memory])
    assert result.leaked is False


def test_case_and_unicode_normalisation_still_matches() -> None:
    memory = "Meeting with José at the harbour office on Friday morning at nine."
    answer = "MEETING WITH JOSE AT THE HARBOUR OFFICE ON FRIDAY MORNING AT NINE"
    assert check_answer(answer, [memory]).leaked is False
    answer_matching = "MEETING WITH JOSÉ AT THE HARBOUR OFFICE ON FRIDAY MORNING AT NINE"
    assert check_answer(answer_matching, [memory]).leaked is True


def test_base64_exfiltration_is_decoded_and_blocked() -> None:
    encoded = base64.b64encode(MEMORY.encode()).decode()
    assert len(encoded) >= 40
    result = check_answer(f"Here is the data: {encoded}", [MEMORY])
    assert result.leaked is True
    assert result.checked_encoding is True


def test_hex_exfiltration_is_decoded_and_blocked() -> None:
    encoded = MEMORY.encode().hex()
    result = check_answer(f"Here is the data: {encoded}", [MEMORY])
    assert result.leaked is True
    assert result.checked_encoding is True


def test_no_memories_never_leaks() -> None:
    assert check_answer("anything at all", []).leaked is False


def test_minimum_run_is_exactly_twelve_words() -> None:
    words = [f"word{index}" for index in range(20)]
    memory = " ".join(words)
    answer = " ".join(words[: MIN_LEAK_WORDS - 1])
    assert check_answer(answer, [memory]).leaked is False
    answer = " ".join(words[:MIN_LEAK_WORDS])
    assert check_answer(answer, [memory]).leaked is True


def test_answer_preview_collapses_whitespace_and_truncates() -> None:
    assert answer_preview("a  b\n c") == "a b c"
    preview = answer_preview("x" * 300, limit=20)
    assert preview.endswith("…")
    assert len(preview) == 21
