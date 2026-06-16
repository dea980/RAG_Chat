"""TXT loader — 평문 텍스트 파일.

인코딩은 UTF-8 우선, 실패 시 CP949 fallback (한국어 윈도우 파일 대응).
파일 전체를 RawDoc 하나로 반환하고, 청킹은 splitter 가 담당한다.
"""
from __future__ import annotations

from typing import Iterable

from ...base import RawDoc
from ...registry import register

_ENCODINGS = ("utf-8", "utf-8-sig", "cp949", "euc-kr")


def _read_with_fallback(path: str) -> str:
    """다중 인코딩 fallback. 마지막엔 errors='replace' 로 손실 허용."""
    for enc in _ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


@register
class TxtLoader:
    """TXT/MD 파일 → 단일 RawDoc (splitter 가 쪼갬)."""

    extensions = (".txt", ".md")
    source_type = "txt"

    def load(self, path: str) -> Iterable[RawDoc]:
        text = _read_with_fallback(path)
        yield RawDoc(
            content=text,
            source_file=path,
            source_type=self.source_type,
            metadata={"char_count": len(text)},
        )
