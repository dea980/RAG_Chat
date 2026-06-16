"""Unit tests for KnowledgeOrmSink (Phase 6)."""
from __future__ import annotations

import pytest

from chat.ingest.base import RawDoc
from chat.ingest.sinks.knowledge_orm import KnowledgeOrmSink
from knowledge.models import Department, Product


def _csv_doc(model: str, color: str, price: str, *, row: int = 0) -> RawDoc:
    return RawDoc(
        content=f"Model: {model}\nColor: {color}\nPrice: {price}",
        source_file="/tmp/test.csv",
        source_type="csv",
        section=f"row:{row}",
        metadata={"fields": {"Model": model, "Color": color, "Price": price}},
    )


@pytest.mark.django_db
def test_upserts_csv_rows_into_products():
    docs = [
        _csv_doc("Galaxy S25", "Black", "1199.99", row=0),
        _csv_doc("Galaxy S25 Plus", "Silver", "1399.99", row=1),
    ]
    sink = KnowledgeOrmSink()
    result = sink.write(docs)

    assert result.count == 2
    assert Product.objects.count() == 2
    assert all(i.startswith("product:") for i in result.ids)

    s25 = Product.objects.get(name="Galaxy S25")
    assert s25.specs == {"Color": "Black", "Price": "1199.99"}
    assert "Galaxy S25" in s25.description
    assert s25.department.name == "영업팀"
    assert s25.category == Product.Category.PRODUCT


@pytest.mark.django_db
def test_idempotent_on_repeat_write():
    docs = [_csv_doc("Galaxy S25 Ultra", "Titanium Gray", "1599.99")]
    sink = KnowledgeOrmSink()
    sink.write(docs)
    sink.write(docs)  # same input — no duplicate
    assert Product.objects.count() == 1


@pytest.mark.django_db
def test_skips_non_structured_doc_types():
    docs = [
        RawDoc(
            content="some PDF page text",
            source_file="/tmp/x.pdf",
            source_type="pdf",
            metadata={},
        ),
        RawDoc(
            content="some text",
            source_file="/tmp/x.txt",
            source_type="txt",
            metadata={},
        ),
    ]
    sink = KnowledgeOrmSink()
    result = sink.write(docs)
    assert result.count == 0
    assert Product.objects.count() == 0


@pytest.mark.django_db
def test_uses_default_department_creates_it_once():
    docs = [_csv_doc("A", "x", "1"), _csv_doc("B", "y", "2", row=1)]
    sink = KnowledgeOrmSink(default_department="제품기획팀")
    sink.write(docs)
    assert Department.objects.filter(name="제품기획팀").count() == 1
    assert all(p.department.name == "제품기획팀" for p in Product.objects.all())


@pytest.mark.django_db
def test_custom_name_column():
    docs = [
        RawDoc(
            content="serial: ABC123\nlabel: My Product",
            source_file="/tmp/inv.csv",
            source_type="csv",
            section="row:0",
            metadata={"fields": {"serial": "ABC123", "label": "My Product"}},
        ),
    ]
    sink = KnowledgeOrmSink(name_column="label")
    sink.write(docs)
    product = Product.objects.get(name="My Product")
    assert product.specs == {"serial": "ABC123"}


@pytest.mark.django_db
def test_delete_ids_removes_products():
    docs = [_csv_doc("Galaxy ToDelete", "Black", "100")]
    sink = KnowledgeOrmSink()
    result = sink.write(docs)
    deleted = sink.delete_ids(result.ids)
    assert deleted == 1
    assert Product.objects.count() == 0


@pytest.mark.django_db
def test_delete_ids_ignores_unknown_id_formats():
    sink = KnowledgeOrmSink()
    deleted = sink.delete_ids(["chroma:abc", "weird-id", ""])
    assert deleted == 0
