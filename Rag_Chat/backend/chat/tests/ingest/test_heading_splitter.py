import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "triple_chat_pjt.settings")
django.setup()

from chat.ingest.base import RawDoc
from chat.ingest.splitters.heading import HeadingSplitter


def _doc(content: str, source_type: str = "md") -> RawDoc:
    return RawDoc(content=content, source_file="handbook.md", source_type=source_type)


def test_splits_markdown_by_headings():
    content = "# 개요\n첫 문단.\n\n## 사양\n사양 문단.\n\n## 시작하기\n시작 문단.\n"
    chunks = list(HeadingSplitter().split(_doc(content)))
    assert len(chunks) == 3
    assert chunks[0].section == "개요"
    assert chunks[1].section == "개요 > 사양"
    assert chunks[2].section == "개요 > 시작하기"


def test_body_does_not_bleed_across_headings():
    content = "## A\n에이 본문.\n\n## B\n비 본문.\n"
    chunks = list(HeadingSplitter().split(_doc(content)))
    a = next(c for c in chunks if c.section.endswith("A"))
    assert "에이 본문" in a.content
    assert "비 본문" not in a.content


def test_nested_heading_section_includes_parent_path():
    content = "# 매뉴얼\n\n## 2. 주요 사양\n\n### 2.1 디스플레이\n6.2인치 AMOLED.\n"
    chunks = list(HeadingSplitter().split(_doc(content)))
    assert len(chunks) == 1
    assert chunks[0].section == "매뉴얼 > 2. 주요 사양 > 2.1 디스플레이"
    assert "6.2인치 AMOLED" in chunks[0].content


def test_sibling_after_deeper_heading_pops_stack():
    content = "## A\n\n### A.1\n에이일 본문.\n\n## B\n비 본문.\n"
    chunks = list(HeadingSplitter().split(_doc(content)))
    b = next(c for c in chunks if "비 본문" in c.content)
    assert b.section == "B"


def test_preamble_before_first_heading():
    content = "문서 소개 문단.\n\n# 첫 섹션\n내용.\n"
    chunks = list(HeadingSplitter().split(_doc(content)))
    assert chunks[0].section is None
    assert "문서 소개" in chunks[0].content
    assert chunks[1].section == "첫 섹션"


def test_metadata_and_source_preserved():
    doc = RawDoc(content="# H\n본문.\n", source_file="x.md", source_type="md", page=2)
    chunks = list(HeadingSplitter().split(doc))
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[0].metadata["splitter"] == "heading"
    assert chunks[0].source_file == "x.md"
    assert chunks[0].page == 2


def test_no_heading_falls_back_to_single_chunk():
    content = "헤딩이 전혀 없는 평문.\n둘째 줄.\n"
    chunks = list(HeadingSplitter().split(_doc(content)))
    assert len(chunks) == 1
    assert chunks[0].section is None
    assert "평문" in chunks[0].content
