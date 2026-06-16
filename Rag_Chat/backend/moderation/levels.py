"""Sensitivity ladder + ACL helpers (Phase A — label-based moderation).

이 모듈은 ORM 의존이 없는 순수 헬퍼만 둔다. Document/User 모델은
sensitivity 라벨 값(`public`/`internal`/`confidential`/`restricted`) 만
참조하므로, 같은 ladder 를 4 boundary 모두가 공유한다.

핵심 규칙:
- `restricted` 문서는 벡터 인덱싱에서 제외한다 (`should_index`).
- 사용자는 자기 `access_level` 이상 sensitivity 의 chunk 만 retrieve 한다
  (`can_access`).
- chunk metadata 에 `sensitivity` 키가 없는 옛 데이터는 안전 측 default
  로 `internal` 로 간주한다 (`DEFAULT_LEVEL`).
"""
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

SENSITIVITY_LEVEL: dict[str, int] = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}

DEFAULT_LEVEL = "internal"


def can_access(user_level: str, content_level: str) -> bool:
    """True if a user can retrieve content with the given sensitivity."""
    return SENSITIVITY_LEVEL[user_level] >= SENSITIVITY_LEVEL[content_level]


def should_index(content_level: str) -> bool:
    """Layer 1 — `restricted` documents are not added to the vector store."""
    return content_level != "restricted"


def apply_acl_filter(
    hits: Sequence,
    user_level: str,
) -> Tuple[List, int]:
    """Filter retrieval hits by user access level.

    Each hit must expose a `.metadata` dict; the sensitivity is read from
    `metadata["sensitivity"]` and defaults to `internal` when absent.

    Returns: (kept_hits, redacted_count).
    """
    kept: List = []
    redacted = 0
    for hit in hits:
        meta = getattr(hit, "metadata", {}) or {}
        sens = meta.get("sensitivity", DEFAULT_LEVEL)
        if sens not in SENSITIVITY_LEVEL:
            sens = DEFAULT_LEVEL
        if can_access(user_level, sens):
            kept.append(hit)
        else:
            redacted += 1
    return kept, redacted
