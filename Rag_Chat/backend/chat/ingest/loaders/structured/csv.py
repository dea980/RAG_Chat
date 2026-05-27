"""CSV loader — langchain CSVLoader 를 RawDoc 으로 감싼다.

CSVLoader 는 행마다 `col: value\\ncol: value\\n...` 형태로 page_content 를
만든다. 우리는 그것을 RawDoc.content 로 그대로 사용하고, 컬럼 원본 값은
metadata['fields'] 에 보존한다 (정확 조회용 — Phase 6 ORM sink 가 활용).
"""
from __future__ import annotations

from typing import Iterable

from langchain_community.document_loaders import CSVLoader

from ...base import RawDoc
from ...registry import register


@register
class CsvLoader:
    """CSV 파일 → 행 단위 RawDoc."""

    extensions = (".csv",)
    source_type = "csv"

    def load(self, path: str) -> Iterable[RawDoc]:
        """파일을 읽고 각 행을 RawDoc 으로 yield."""
        for i, doc in enumerate(CSVLoader(file_path=path).load()):
            yield RawDoc(
                content=doc.page_content,
                source_file=path,
                source_type=self.source_type,
                section=f"row:{i}",
                metadata={
                    "row_index": i,
                    # CSVLoader 가 채운 metadata (source 등) 를 보존
                    "fields": dict(doc.metadata),
                },
            )
