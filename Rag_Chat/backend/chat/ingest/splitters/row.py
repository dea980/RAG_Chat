"""Row splitter — 표(CSV/Excel) 1행 = 1청크.

표 데이터는 행이 의미의 최소 단위라 더 이상 쪼개면 맥락이 깨진다.
즉 splitter 가 사실상 pass-through 이지만, splitter 자리에 무언가
들어가야 pipeline 인터페이스가 일관되므로 이 클래스를 둔다.
"""
from __future__ import annotations

from typing import Iterable

from ..base import RawDoc


class RowSplitter:
    """표 데이터 전용 — 입력 RawDoc 을 그대로 yield (분할하지 않음)."""

    def split(self, doc: RawDoc) -> Iterable[RawDoc]:
        """입력 RawDoc 을 그대로 반환, chunk_index=0 만 표시."""
        yield RawDoc(
            content=doc.content,
            source_file=doc.source_file,
            source_type=doc.source_type,
            page=doc.page,
            section=doc.section,
            metadata={**doc.metadata, "chunk_index": 0, "splitter": "row"},
        )
