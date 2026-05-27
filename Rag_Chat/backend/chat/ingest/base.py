"""Ingest layer 의 표준 인터페이스.

세 종류의 Protocol 만 정의한다:
- Loader  : 파일 → RawDoc[]            (포맷별 파싱)
- Splitter: RawDoc → RawDoc[]          (청킹)
- Sink    : RawDoc[] → 저장소(Chroma/ORM), WriteResult 반환
이 셋을 pipeline.py 가 조립한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol, runtime_checkable


@dataclass
class RawDoc:
    """포맷에 의존하지 않는 공통 문서 표현.

    CSV 행 한 줄, PDF 한 페이지, HWP 한 조항이 모두 동일한 RawDoc 으로
    표준화되어야 그 다음 splitter/sink 가 포맷에 무관해진다.
    """
    content: str                       # 검색 대상 텍스트 본문
    source_file: str                   # 원본 파일 경로(또는 S3 URI)
    source_type: str                   # "csv" | "pdf" | "hwp" | ...
    page: int | None = None            # PDF/PPT 페이지 (해당될 때만)
    section: str | None = None         # heading 또는 "제39조" 같은 조항 식별자
    metadata: dict = field(default_factory=dict)  # 자유 확장 (예: CSV 컬럼)


@dataclass
class WriteResult:
    """Sink 의 쓰기 결과. pipeline 이 manifest 에 ids 를 기록한다."""
    count: int           # 기록된 청크 개수
    ids: list[str]       # 각 청크의 저장소 id (삭제·재인덱싱용)


@runtime_checkable
class BaseLoader(Protocol):
    """파일 경로를 받아 RawDoc 들을 생성.

    구현체는 `extensions` 튜플과 `load(path)` 메서드만 충족하면 된다.
    registry 에서 확장자로 자동 매핑된다.
    """
    extensions: tuple[str, ...]        # 예: (".csv",) — 등록 키
    source_type: str                   # manifest 의 loader 필드에 들어감

    def load(self, path: str) -> Iterable[RawDoc]:
        """파일을 읽어 RawDoc iterable 반환."""
        ...


@runtime_checkable
class BaseSplitter(Protocol):
    """RawDoc 한 개를 청크 단위 RawDoc 여러 개로 쪼갠다.

    예: 1000자 PDF 문단 → 500자 청크 2개 (overlap 포함).
    splitter 는 source_type 별로 다른 전략을 쓸 수 있다 (Phase 4).
    """

    def split(self, doc: RawDoc) -> Iterable[RawDoc]:
        """RawDoc → 청크 단위 RawDoc iterable."""
        ...


@runtime_checkable
class BaseSink(Protocol):
    """청크들을 저장소에 기록. 기록한 청크 개수와 저장 id 들을 반환."""

    def write(self, docs: Iterable[RawDoc]) -> WriteResult:
        """저장소에 기록 후 (count, ids) 반환."""
        ...

    def delete_ids(self, ids: list[str]) -> int:
        """이전 버전의 청크 id 들을 저장소에서 제거. 삭제된 수 반환."""
        ...
