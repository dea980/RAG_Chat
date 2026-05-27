import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "triple_chat_pjt.settings")
django.setup()

from chat.ingest.splitters import default_splitter_for, splitter_by_name
from chat.ingest.splitters.clause import ClauseSplitter
from chat.ingest.splitters.heading import HeadingSplitter
from chat.ingest.splitters.recursive import RecursiveSplitter
from chat.ingest.splitters.row import RowSplitter


def test_splitter_by_name_returns_clause():
    assert isinstance(splitter_by_name("clause"), ClauseSplitter)


def test_splitter_by_name_returns_heading():
    assert isinstance(splitter_by_name("heading"), HeadingSplitter)


def test_existing_names_still_resolve():
    assert isinstance(splitter_by_name("recursive"), RecursiveSplitter)
    assert isinstance(splitter_by_name("row"), RowSplitter)


def test_md_auto_default_stays_recursive_no_regression():
    # heading 없는 flat 마크다운이 단일 청크로 무너지지 않도록
    # 자동 디폴트는 recursive 유지 (heading 은 opt-in).
    assert isinstance(default_splitter_for("md"), RecursiveSplitter)


def test_clause_is_not_an_auto_default_for_any_source():
    # clause 는 내용 의존적(조항 문서) → 확장자 자동매핑 대상이 아님.
    for source_type in ("pdf", "docx", "html", "txt", "md", "csv", "excel"):
        assert not isinstance(default_splitter_for(source_type), ClauseSplitter)


def test_unknown_source_falls_back_to_recursive():
    assert isinstance(default_splitter_for("zzz"), RecursiveSplitter)
