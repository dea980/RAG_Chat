"""HTML loader — 본문 텍스트 추출."""
from __future__ import annotations

from typing import Iterable

from ...base import RawDoc
from ...registry import register
from .txt import _read_with_fallback


@register
class HtmlLoader:
    """HTML/HTM 파일 → 단일 RawDoc."""

    extensions = (".html", ".htm")
    source_type = "html"

    def load(self, path: str) -> Iterable[RawDoc]:
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise RuntimeError("beautifulsoup4 is required to ingest HTML files") from exc

        html = _read_with_fallback(path)
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        if not text:
            return
        yield RawDoc(
            content=text,
            source_file=path,
            source_type=self.source_type,
            metadata={"char_count": len(text)},
        )
