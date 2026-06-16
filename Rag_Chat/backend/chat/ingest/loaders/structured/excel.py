"""Excel loader — pandas 로 각 행을 RawDoc 으로 변환.

기존 build_vectors.py 의 XLSX 분기에서 그대로 이전. 시트 여러 개면 모두
순회한다. langchain UnstructuredExcelLoader 는 시트 구분이 약해서 pandas
직접 사용이 더 안정적.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from ...base import RawDoc
from ...registry import register


@register
class ExcelLoader:
    """XLSX 파일 → 행 단위 RawDoc (시트별 순회)."""

    extensions = (".xlsx", ".xls")
    source_type = "excel"

    def load(self, path: str) -> Iterable[RawDoc]:
        """모든 시트를 읽고 행 단위로 RawDoc yield."""
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
        for sheet_name, df in sheets.items():
            for i, row in df.iterrows():
                # "col: value" 줄로 직렬화 — CSVLoader 가 만드는 포맷과 동일하게 맞춤
                content = "\n".join(
                    f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col])
                )
                yield RawDoc(
                    content=content,
                    source_file=path,
                    source_type=self.source_type,
                    section=f"{sheet_name}:row:{i}",
                    metadata={
                        "sheet": sheet_name,
                        "row_index": int(i),
                        "fields": {
                            c: (None if pd.isna(row[c]) else str(row[c]))
                            for c in df.columns
                        },
                    },
                )
