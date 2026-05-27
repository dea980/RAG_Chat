"""OCR loader 테스트 — 분류 2 (스캔/이미지) 경로 검증.

tesseract 바이너리 또는 pytesseract 미설치 환경에서는 OCR 실행 테스트는
skip 하고 registry 등록만 검증한다. 픽스처는 backend/scripts/build_ocr_fixtures.py
가 생성한 PNG (한국어/영어/혼합).
"""
import os
import shutil

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "triple_chat_pjt.settings")
django.setup()

from chat.ingest import loaders  # noqa: F401 — registry side-effect
from chat.ingest.registry import loader_for, registered_extensions

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "ocr")

try:
    import pytesseract  # noqa: F401

    _HAS_PYTESSERACT = True
except ImportError:
    _HAS_PYTESSERACT = False

_HAS_TESSERACT_BIN = shutil.which("tesseract") is not None

requires_ocr = pytest.mark.skipif(
    not (_HAS_PYTESSERACT and _HAS_TESSERACT_BIN),
    reason="OCR run requires pytesseract package + tesseract binary",
)


def test_image_extensions_registered():
    extensions = registered_extensions()
    for ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        assert ext in extensions


def test_loader_for_png_returns_ocr_loader():
    loader = loader_for(os.path.join(FIXTURES, "sample_en.png"))
    assert loader is not None
    assert loader.source_type == "ocr"


@requires_ocr
def test_loads_english_image():
    path = os.path.join(FIXTURES, "sample_en.png")
    docs = list(loader_for(path).load(path))
    assert len(docs) == 1
    doc = docs[0]
    text = doc.content.lower()
    assert "galaxy" in text
    assert "2025" in text
    assert doc.source_type == "ocr"
    assert doc.source_file == path
    assert doc.metadata["ocr_lang"] == "kor+eng"


@requires_ocr
def test_loads_korean_image():
    path = os.path.join(FIXTURES, "sample_ko.png")
    docs = list(loader_for(path).load(path))
    assert len(docs) == 1
    content = docs[0].content
    assert "갤럭시" in content or "2025" in content


@requires_ocr
def test_loads_mixed_image():
    path = os.path.join(FIXTURES, "sample_mixed.png")
    docs = list(loader_for(path).load(path))
    assert len(docs) == 1
    content = docs[0].content
    assert "Galaxy" in content
    assert "Ultra" in content
    assert "mAh" in content
    assert "45W" in content
