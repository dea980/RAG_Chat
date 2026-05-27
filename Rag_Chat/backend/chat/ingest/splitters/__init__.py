"""Splitter 모듈 — 청킹 전략 + source_type 별 default dispatch.

- recursive : 길이 기반 (RecursiveCharacterTextSplitter)
- row       : 표 1행 = 1청크 (CSV/Excel)
- (Phase 4) heading / clause 예정

`default_splitter_for(source_type)` 가 한 군데에서 dispatch 를 담당해
build_vectors / Upload API / pipeline 이 동일한 선택 로직을 공유한다.
"""
from __future__ import annotations

from .recursive import RecursiveSplitter
from .row import RowSplitter

# source_type → splitter name 매핑. Phase 4 splitter 추가 시 여기만 갱신.
DEFAULT_BY_SOURCE: dict[str, str] = {
    "csv": "row",
    "excel": "row",
    "pdf": "recursive",
    "docx": "recursive",
    "html": "recursive",
    "txt": "recursive",
    "md": "recursive",
}

_BY_NAME = {
    "recursive": RecursiveSplitter,
    "row": RowSplitter,
}


def default_splitter_for(source_type: str):
    """source_type 에 권장되는 splitter 인스턴스. 없으면 recursive."""
    name = DEFAULT_BY_SOURCE.get(source_type, "recursive")
    return _BY_NAME[name]()


def splitter_by_name(name: str, *, chunk_size: int | None = None,
                     chunk_overlap: int | None = None):
    """이름으로 splitter 생성 — chunk_lab 같은 explicit 사용 경로용."""
    cls = _BY_NAME.get(name, RecursiveSplitter)
    if cls is RecursiveSplitter:
        return cls(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return cls()
