"""Session-scoped provider override store."""

from __future__ import annotations

import os
from typing import Dict, Optional

from django.core.cache import cache


def _key(session_id: str) -> str:
    return f"provider_override:{session_id}"


def _ttl() -> int:
    return int(os.getenv("PROVIDER_OVERRIDE_TTL", "1800"))


def set_override(session_id: str, *, reasoning: Optional[str] = None, generation: Optional[str] = None) -> Dict[str, Optional[str]]:
    data = {
        "reasoning_provider": reasoning,
        "generation_provider": generation,
    }
    cache.set(_key(session_id), data, timeout=_ttl())
    return data


def get_override(session_id: str) -> Dict[str, Optional[str]]:
    return cache.get(_key(session_id), {})


def clear_override(session_id: str) -> None:
    cache.delete(_key(session_id))
