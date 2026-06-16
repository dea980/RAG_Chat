"""Heading splitter — markdown heading 구조 단위 분리.

`#`~`######` heading 을 경계로 본문을 섹션 단위 청크로 쪼갠다. heading
계층(stack)을 추적해 section 에 전체 경로("매뉴얼 > 2. 주요 사양 > 2.1
디스플레이")를 기록 — retrieval 시 어느 섹션에서 왔는지 추적 가능하다.
DOCX/HTML 본문도 markdown 으로 정규화되면 이 splitter 로 처리한다.
"""
from __future__ import annotations

import re
from typing import Iterable

from ..base import RawDoc

# ATX heading — 줄 시작의 #~###### + 공백 + 제목 (닫는 # 허용).
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


class HeadingSplitter:
    """markdown heading 계층을 보존하며 RawDoc 을 섹션 단위로 쪼갠다."""

    def split(self, doc: RawDoc) -> Iterable[RawDoc]:
        text = doc.content
        matches = list(_HEADING.finditer(text))

        segments: list[tuple[str | None, str]] = []
        if not matches:
            body = text.strip()
            if body:
                segments.append((None, body))
        else:
            preamble = text[: matches[0].start()].strip()
            if preamble:
                segments.append((None, preamble))

            stack: list[tuple[int, str]] = []  # (level, title) 계층
            for i, m in enumerate(matches):
                level = len(m.group(1))
                title = m.group(2).strip()
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))

                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                body = text[m.end() : end].strip()
                if body:  # 하위 heading 만 있는 컨테이너 heading 은 건너뛴다
                    section = " > ".join(t for _, t in stack)
                    segments.append((section, text[m.start() : end].strip()))

        for idx, (section, content) in enumerate(segments):
            yield RawDoc(
                content=content,
                source_file=doc.source_file,
                source_type=doc.source_type,
                page=doc.page,
                section=section,
                metadata={**doc.metadata, "chunk_index": idx, "splitter": "heading"},
            )
