"""Splitter 모듈 — 청킹 전략 + source_type 별 default dispatch.

- recursive : 길이 기반 (RecursiveCharacterTextSplitter)
- row       : 표 1행 = 1청크 (CSV/Excel)
- heading   : markdown heading 계층 단위 (Phase 4, opt-in)
- clause    : "제N조"/"Article N" 조항 단위 (Phase 4, 사규/법규, opt-in)

`default_splitter_for(source_type)` 가 한 군데에서 dispatch 를 담당해
build_vectors / Upload API / pipeline 이 동일한 선택 로직을 공유한다.
"""
from __future__ import annotations

from .clause import ClauseSplitter
from .heading import HeadingSplitter
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

# heading/clause 는 DEFAULT_BY_SOURCE 에 넣지 않는다 — 확장자만으론 자동 선택이
# 위험하다(clause=조항 문서, heading=구조화된 md). flat 마크다운/일반 PDF 에
# 자동으로 걸면 청킹이 오히려 깨지므로 splitter_by_name 으로 명시 선택(opt-in)만 허용.
_BY_NAME = {
    "recursive": RecursiveSplitter,
    "row": RowSplitter,
    "heading": HeadingSplitter,
    "clause": ClauseSplitter,
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
