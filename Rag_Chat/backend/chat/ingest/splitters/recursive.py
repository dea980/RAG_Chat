"""길이 기반 splitter — langchain RecursiveCharacterTextSplitter 래핑.

청크 크기는 환경변수로 외부에서 주입 (chunk_experiment.md 의 A/B 결과 활용
가능하게). PDF/긴 텍스트 문서의 기본 splitter.
"""
from __future__ import annotations

import os
from typing import Iterable

from langchain.text_splitter import RecursiveCharacterTextSplitter

from ..base import RawDoc


class RecursiveSplitter:
    """긴 텍스트를 chunk_size 단위로 (overlap 포함) 쪼개는 splitter."""

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None):
        # 환경변수가 없으면 현재 빌더 기본값(1000/200) 유지 — 기존 동작 보존.
        self.chunk_size = chunk_size or int(os.getenv("INGEST_CHUNK_SIZE", "1000"))
        self.chunk_overlap = chunk_overlap or int(os.getenv("INGEST_CHUNK_OVERLAP", "200"))
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            keep_separator=True,
        )

    def split(self, doc: RawDoc) -> Iterable[RawDoc]:
        """RawDoc.content 를 길이 기준으로 쪼개 새 RawDoc 들을 yield."""
        for i, chunk_text in enumerate(self._splitter.split_text(doc.content)):
            yield RawDoc(
                content=chunk_text,
                source_file=doc.source_file,
                source_type=doc.source_type,
                page=doc.page,
                section=doc.section,
                metadata={
                    **doc.metadata,
                    "chunk_index": i,
                    "splitter": "recursive",
                },
            )
