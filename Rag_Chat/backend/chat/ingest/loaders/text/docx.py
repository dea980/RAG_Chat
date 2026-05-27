"""DOCX loader — 문서 텍스트 추출."""
from __future__ import annotations

from typing import Iterable

from ...base import RawDoc
from ...registry import register


@register
class DocxLoader:
    """DOCX 파일 → 단일 RawDoc."""

    extensions = (".docx",)
    source_type = "docx"

    def load(self, path: str) -> Iterable[RawDoc]:
        try:
            import docx2txt
        except ImportError as exc:
            raise RuntimeError("docx2txt is required to ingest DOCX files") from exc

        text = (docx2txt.process(path) or "").strip()
        if not text:
            return
        yield RawDoc(
            content=text,
            source_file=path,
            source_type=self.source_type,
            metadata={"char_count": len(text)},
        )
