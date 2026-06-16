"""Clause splitter — 조항 단위 분리 (사규/법규).

"제N조" / "Article N" / "부칙" 을 경계로 본문을 조항 단위 청크로 쪼갠다.
길이 기반(recursive)과 달리 의미 단위(조항)를 보존해 "연차 며칠?" 같은
질문에 해당 조항 청크가 통째로 회수되도록 한다. section 필드에 정규화된
조항 식별자("제39조")를 넣어 retrieval 시 출처 추적이 가능하다.
"""
from __future__ import annotations

import re
from typing import Iterable

from ..base import RawDoc

# 조항 머리말 — 줄 시작에서만 인식 (본문 중간의 "제3조" 언급은 무시).
_KO = r"제\s*\d+\s*조"
_EN = r"Article\s+\d+"
_SUPPLEMENT = r"부칙"
_MARKER = re.compile(rf"^[ \t]*({_KO}|{_EN}|{_SUPPLEMENT})", re.MULTILINE)


def _normalize(label: str) -> str:
    """머리말을 표준 section 식별자로 정규화 ("제 39 조" → "제39조")."""
    label = label.strip()
    m = re.match(rf"{_KO}", label)
    if m:
        digits = re.search(r"\d+", label).group()
        return f"제{digits}조"
    m = re.match(rf"{_EN}", label)
    if m:
        digits = re.search(r"\d+", label).group()
        return f"Article {digits}"
    return label  # 부칙 등


class ClauseSplitter:
    """조항("제N조"/"Article N"/"부칙") 경계로 RawDoc 을 쪼개는 splitter."""

    def split(self, doc: RawDoc) -> Iterable[RawDoc]:
        text = doc.content
        matches = list(_MARKER.finditer(text))

        segments: list[tuple[str | None, str]] = []
        if not matches:
            body = text.strip()
            if body:
                segments.append((None, body))
        else:
            preamble = text[: matches[0].start()].strip()
            if preamble:
                segments.append((None, preamble))
            for i, m in enumerate(matches):
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                body = text[m.start() : end].strip()
                if body:
                    segments.append((_normalize(m.group(1)), body))

        for idx, (section, content) in enumerate(segments):
            yield RawDoc(
                content=content,
                source_file=doc.source_file,
                source_type=doc.source_type,
                page=doc.page,
                section=section,
                metadata={**doc.metadata, "chunk_index": idx, "splitter": "clause"},
            )
