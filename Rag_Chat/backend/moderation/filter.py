"""Multi-stage forbidden-word filter.

Used by the chat pipeline to enforce the three-action policy:

    BLOCK   → raise BlockedError, never reach the LLM, log
    WARNING → pass through, but log for human review
    MASK    → replace match with mask_replacement before sending, log

The same hook is used for outbound text (LLM responses) so leaked secrets
still get caught.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple

from django.utils import timezone

from .models import ForbiddenWord, ModerationLog


class BlockedByModerationError(Exception):
    """Raised when an INBOUND message hits a BLOCK rule."""

    def __init__(self, words: List[str], message: str = "요청에 차단된 단어가 포함되어 있습니다."):
        super().__init__(message)
        self.words = words
        self.message = message


@dataclass
class ModerationResult:
    sanitized: str
    blocked: bool = False
    masked_words: List[str] = field(default_factory=list)
    warned_words: List[str] = field(default_factory=list)
    blocked_words: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)

    @property
    def any_hit(self) -> bool:
        return bool(self.masked_words or self.warned_words or self.blocked_words)


_SOURCE_TO_DIRECTIONS: dict[str, Tuple[str, ...]] = {
    "INBOUND":   ("BOTH", "INBOUND"),
    "UPLOAD":    ("BOTH", "INBOUND"),
    "OUTBOUND":  ("BOTH", "OUTBOUND"),
    "RETRIEVAL": ("BOTH", "OUTBOUND"),
}


def _directions_for(source: str) -> Tuple[str, ...]:
    return _SOURCE_TO_DIRECTIONS.get(source, ("BOTH", "OUTBOUND"))


def _active_rules(direction_keys: Iterable[str]):
    return ForbiddenWord.objects.filter(is_active=True, direction__in=list(direction_keys))


def _find_matches(text: str, words: Iterable[str]) -> List[Tuple[str, int, int]]:
    hits: List[Tuple[str, int, int]] = []
    lowered = text.lower()
    for w in words:
        if not w:
            continue
        needle = w.lower()
        start = 0
        while True:
            idx = lowered.find(needle, start)
            if idx == -1:
                break
            hits.append((w, idx, idx + len(needle)))
            start = idx + len(needle)
    return hits


def apply(text: str, *, source: str, user=None, chat=None) -> ModerationResult:
    """Run the forbidden-word policy on ``text``.

    source must be one of ``ModerationLog.Source`` values.
    """
    if not text:
        return ModerationResult(sanitized=text)

    direction_filter = _directions_for(source)
    rules = list(_active_rules(direction_filter))
    if not rules:
        return ModerationResult(sanitized=text)

    by_severity: dict = {sev: [] for sev in ForbiddenWord.Severity.values}
    mask_lookup: dict = {}
    cat_lookup: dict = {}
    for r in rules:
        by_severity[r.severity].append(r.word)
        mask_lookup[r.word.lower()] = r.mask_replacement
        cat_lookup[r.word.lower()] = r.category

    # 1) BLOCK first — short-circuit before any masking.
    blocked_hits = _find_matches(text, by_severity[ForbiddenWord.Severity.BLOCK])
    if blocked_hits:
        words = sorted({w for w, _, _ in blocked_hits})
        categories = sorted({cat_lookup.get(w.lower(), "") for w in words if cat_lookup.get(w.lower())})
        ModerationLog.objects.create(
            user=user,
            chat=chat,
            detected_words=words,
            matched_categories=categories,
            action=ModerationLog.Action.BLOCKED,
            source=source,
            original_excerpt=text[:500],
            sanitized_excerpt="",
            created_at=timezone.now(),
        )
        raise BlockedByModerationError(words=words)

    # 2) MASK — collect intervals and substitute in one pass (right-to-left).
    sanitized = text
    mask_hits = _find_matches(text, by_severity[ForbiddenWord.Severity.MASK])
    masked_words: List[str] = []
    if mask_hits:
        # right-to-left to preserve earlier indices
        for word, start, end in sorted(mask_hits, key=lambda h: h[1], reverse=True):
            replacement = mask_lookup.get(word.lower(), "[REDACTED]")
            sanitized = sanitized[:start] + replacement + sanitized[end:]
            masked_words.append(word)
        masked_words = sorted(set(masked_words))

    # 3) WARN — informational, no text change.
    warn_hits = _find_matches(text, by_severity[ForbiddenWord.Severity.WARNING])
    warned_words = sorted({w for w, _, _ in warn_hits})

    categories: List[str] = []
    for w in masked_words + warned_words:
        cat = cat_lookup.get(w.lower())
        if cat and cat not in categories:
            categories.append(cat)

    if masked_words:
        ModerationLog.objects.create(
            user=user,
            chat=chat,
            detected_words=masked_words,
            matched_categories=[cat_lookup.get(w.lower(), "") for w in masked_words],
            action=ModerationLog.Action.MASKED,
            source=source,
            original_excerpt=text[:500],
            sanitized_excerpt=sanitized[:500],
        )
    if warned_words:
        ModerationLog.objects.create(
            user=user,
            chat=chat,
            detected_words=warned_words,
            matched_categories=[cat_lookup.get(w.lower(), "") for w in warned_words],
            action=ModerationLog.Action.WARNED,
            source=source,
            original_excerpt=text[:500],
            sanitized_excerpt=sanitized[:500],
        )

    return ModerationResult(
        sanitized=sanitized,
        masked_words=masked_words,
        warned_words=warned_words,
        categories=categories,
    )
