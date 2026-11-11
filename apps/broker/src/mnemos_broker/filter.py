"""Output filter: block verbatim memory reproduction and simple encodings.

The contract with the model is stricter than the filter: the prompt asks it not
to reproduce more than 12 consecutive words. The filter is the enforcement
point and rejects any answer that still shares a 12-word contiguous run with a
memory item, including runs hidden inside base64 or hex blobs.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import contextlib
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

MIN_LEAK_WORDS = 12
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_B64_CANDIDATE_RE = re.compile(r"[A-Za-z0-9+/=_-]{40,}")
_HEX_CANDIDATE_RE = re.compile(r"[0-9a-fA-F]{40,}")
_PRINTABLE_RE = re.compile(r"[\x20-\x7e\n\r\t]")


@dataclass(frozen=True)
class FilterResult:
    leaked: bool
    reason: str | None = None
    matched_memory: int | None = None
    matched_words: tuple[int, int] | None = None
    checked_encoding: bool = False


def normalise_words(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return [word for word in _WORD_RE.findall(folded) if word]


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    return len(_PRINTABLE_RE.findall(text)) / len(text)


def _decoded_candidates(value: str) -> list[str]:
    candidates: list[str] = []
    stripped = value.strip()
    if _HEX_CANDIDATE_RE.fullmatch(stripped) and len(stripped) % 2 == 0:
        with contextlib.suppress(ValueError, UnicodeDecodeError):
            candidates.append(bytes.fromhex(stripped).decode("utf-8"))
    decoders: tuple[Callable[[str], bytes], ...] = (
        lambda item: base64.b64decode(item, validate=True),
        lambda item: base64.urlsafe_b64decode(item + "=" * (-len(item) % 4)),
    )
    for decoder in decoders:
        try:
            decoded = decoder(stripped)
        except (binascii.Error, ValueError):
            continue
        try:
            candidates.append(decoded.decode("utf-8"))
        except UnicodeDecodeError:
            continue
    with contextlib.suppress(ValueError, UnicodeDecodeError):
        candidates.append(codecs.decode(stripped, "rot_13"))
    return [text for text in candidates if len(text) >= 20 and _printable_ratio(text) >= 0.85]


def _verbatim_match(
    answer_words: list[str], memory_words: list[str], min_words: int
) -> tuple[int, int] | None:
    if len(answer_words) < min_words or len(memory_words) < min_words:
        return None
    memory_ngrams = {
        tuple(memory_words[index : index + min_words])
        for index in range(len(memory_words) - min_words + 1)
    }
    for index in range(len(answer_words) - min_words + 1):
        if tuple(answer_words[index : index + min_words]) in memory_ngrams:
            return (index, index + min_words)
    return None


def check_answer(answer: str, memories: list[str]) -> FilterResult:
    answer_words = normalise_words(answer)
    for index, memory in enumerate(memories):
        match = _verbatim_match(answer_words, normalise_words(memory), MIN_LEAK_WORDS)
        if match is not None:
            return FilterResult(
                leaked=True,
                reason="answer shares a 12-word contiguous run with memory",
                matched_memory=index,
                matched_words=match,
            )

    for token in _B64_CANDIDATE_RE.findall(answer):
        for decoded in _decoded_candidates(token):
            decoded_words = normalise_words(decoded)
            for index, memory in enumerate(memories):
                match = _verbatim_match(decoded_words, normalise_words(memory), MIN_LEAK_WORDS)
                if match is not None:
                    return FilterResult(
                        leaked=True,
                        reason="encoded answer contains a 12-word memory run",
                        matched_memory=index,
                        matched_words=match,
                        checked_encoding=True,
                    )
    return FilterResult(leaked=False)


def answer_preview(answer: str, limit: int = 160) -> str:
    collapsed = " ".join(answer.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "…"
