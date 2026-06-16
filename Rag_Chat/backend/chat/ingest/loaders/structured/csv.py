"""CSV loader — csv.DictReader 로 행 단위 RawDoc 생성.

각 행은 'column: value\\n...' 형태로 content 가 직렬화되고, 컬럼 원본 값은
metadata['fields'] 에 dict 로 보존된다. Phase 6 의 ORM sink 가 이 fields 를
정확 조회용으로 활용한다 (Chroma 는 벡터·근사 검색, ORM 은 SQL·정확 조회).

기존엔 LangChain CSVLoader 를 래핑했으나 fields 가 LangChain 의 메타데이터
(source/row) 만 들어가서 ORM 매핑이 불가능했다 — 직접 DictReader 로 전환.
"""
from __future__ import annotations

import csv
from typing import Iterable

from ...base import RawDoc
from ...registry import register


@register
class CsvLoader:
    """CSV 파일 → 행 단위 RawDoc."""

    extensions = (".csv",)
    source_type = "csv"

    def load(self, path: str) -> Iterable[RawDoc]:
        """파일을 읽고 각 행을 RawDoc 으로 yield.

        content 는 '컬럼: 값' 줄들의 join — Excel loader 와 동일한 직렬화로
        Chroma 벡터 표현이 포맷 간 일관적이게 한다.
        """
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                content = "\n".join(
                    f"{col}: {val}" for col, val in row.items() if val not in (None, "")
                )
                yield RawDoc(
                    content=content,
                    source_file=path,
                    source_type=self.source_type,
                    section=f"row:{i}",
                    metadata={
                        "row_index": i,
                        "fields": dict(row),
                    },
                )
