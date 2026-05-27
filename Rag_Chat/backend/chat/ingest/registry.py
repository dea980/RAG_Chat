"""파일 확장자 → Loader 클래스 매핑 (플러그인 등록제).

새 포맷 추가는 loader 파일 1개 만들고 `@register` 데코레이터만
달면 끝 — pipeline 코드는 안 건드린다. 이게 "layer" 의 핵심 가치.
"""
from __future__ import annotations

import os
from typing import Type

from .base import BaseLoader

# 확장자 ".csv" → CsvLoader 같은 매핑.
# 모듈 import 시점에 @register 가 자동으로 채운다.
_REGISTRY: dict[str, Type[BaseLoader]] = {}


def register(loader_cls: Type[BaseLoader]) -> Type[BaseLoader]:
    """Loader 클래스를 확장자 기준으로 등록하는 데코레이터."""
    for ext in loader_cls.extensions:
        _REGISTRY[ext.lower()] = loader_cls
    return loader_cls


def loader_for(path: str) -> BaseLoader | None:
    """파일 경로의 확장자를 보고 해당 Loader 인스턴스를 반환. 없으면 None."""
    ext = os.path.splitext(path)[1].lower()
    cls = _REGISTRY.get(ext)
    return cls() if cls else None


def registered_extensions() -> tuple[str, ...]:
    """현재 등록된 확장자 목록 — 디버깅/Health 체크용."""
    return tuple(sorted(_REGISTRY.keys()))
