"""PDF loader — page 단위 텍스트 추출."""
from __future__ import annotations

from typing import Iterable

from ...base import RawDoc
from ...registry import register


@register
class PdfLoader:
    """PDF 파일 → 페이지 단위 RawDoc."""

    extensions = (".pdf",)
    source_type = "pdf"

    def load(self, path: str) -> Iterable[RawDoc]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required to ingest PDF files") from exc

        reader = PdfReader(path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if not text:
                continue
            yield RawDoc(
                content=text,
                source_file=path,
                source_type=self.source_type,
                page=i + 1,
                metadata={"page_index": i},
            )
