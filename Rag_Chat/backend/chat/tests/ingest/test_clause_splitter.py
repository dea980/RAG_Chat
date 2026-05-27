import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "triple_chat_pjt.settings")
django.setup()

from chat.ingest.base import RawDoc
from chat.ingest.splitters.clause import ClauseSplitter


def _doc(content: str) -> RawDoc:
    return RawDoc(content=content, source_file="rules.txt", source_type="txt")


def test_splits_korean_clauses_into_separate_chunks():
    content = (
        "제1조 (목적)\n이 규정은 목적을 정한다.\n\n"
        "제2조 (적용범위)\n모든 임직원에게 적용된다.\n\n"
        "제3조 (정의)\n용어를 정의한다.\n"
    )
    chunks = list(ClauseSplitter().split(_doc(content)))
    assert [c.section for c in chunks] == ["제1조", "제2조", "제3조"]


def test_clause_chunk_keeps_body_and_does_not_bleed():
    content = "제1조 (목적)\n이 규정은 목적을 정한다.\n\n제2조 (적용범위)\n적용된다.\n"
    chunks = list(ClauseSplitter().split(_doc(content)))
    assert "목적을 정한다" in chunks[0].content
    assert "적용된다" in chunks[1].content
    assert "적용된다" not in chunks[0].content


def test_preamble_before_first_clause_is_its_own_chunk():
    content = "사내 정보보안 규정 (샘플)\n\n제1조 (목적)\n목적.\n"
    chunks = list(ClauseSplitter().split(_doc(content)))
    assert chunks[0].section is None
    assert "사내 정보보안 규정" in chunks[0].content
    assert chunks[1].section == "제1조"


def test_buchik_is_its_own_section():
    content = "제1조 (목적)\n목적.\n\n부칙\n이 규정은 2024년부터 시행한다.\n"
    chunks = list(ClauseSplitter().split(_doc(content)))
    sections = [c.section for c in chunks]
    assert "부칙" in sections
    buchik = next(c for c in chunks if c.section == "부칙")
    assert "2024년" in buchik.content


def test_english_articles():
    content = "Article 1 (Purpose)\nThis sets the purpose.\n\nArticle 2 (Scope)\nApplies to all.\n"
    chunks = list(ClauseSplitter().split(_doc(content)))
    assert [c.section for c in chunks] == ["Article 1", "Article 2"]


def test_spaced_clause_marker_is_normalized():
    content = "제 39 조 (연차휴가)\n연차는 15일이다.\n"
    chunks = list(ClauseSplitter().split(_doc(content)))
    assert chunks[0].section == "제39조"


def test_metadata_has_chunk_index_and_splitter_name():
    content = "제1조 (목적)\n목적.\n\n제2조 (적용)\n적용.\n"
    chunks = list(ClauseSplitter().split(_doc(content)))
    assert [c.metadata["chunk_index"] for c in chunks] == [0, 1]
    assert all(c.metadata["splitter"] == "clause" for c in chunks)


def test_source_fields_preserved():
    doc = RawDoc(
        content="제1조 (목적)\n목적.\n", source_file="x.pdf", source_type="pdf", page=3
    )
    chunks = list(ClauseSplitter().split(doc))
    assert chunks[0].source_file == "x.pdf"
    assert chunks[0].source_type == "pdf"
    assert chunks[0].page == 3


def test_no_clause_marker_falls_back_to_single_chunk():
    content = "조항 표시가 전혀 없는 일반 문단입니다.\n그냥 줄글.\n"
    chunks = list(ClauseSplitter().split(_doc(content)))
    assert len(chunks) == 1
    assert chunks[0].section is None
    assert "일반 문단" in chunks[0].content
