"""OCR loader — 이미지에서 텍스트 추출 (강의 4분류 중 분류 2).

스캔 PDF/이미지(JPG/PNG)는 텍스트가 임베드돼 있지 않아 OCR 로 글자를
인식해야 분류 1(텍스트 추출형) 경로와 합류할 수 있다.

라이브러리: pytesseract (Tesseract OCR 바인딩). 한국어+영어 동시 인식을
기본으로 잡아두는 게 사내 자료(영업팀 가격표, 한/영 혼용 매뉴얼) 가정에
맞다. 청킹은 splitter 가 담당하므로 여기서는 전체 텍스트를 단일 RawDoc
으로 반환한다.
"""
from __future__ import annotations

from typing import Iterable

from ...base import RawDoc
from ...registry import register

_OCR_LANG = "kor+eng"


@register
class OcrLoader:
    """이미지 파일 → pytesseract OCR → 단일 RawDoc."""

    extensions = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
    source_type = "ocr"

    def load(self, path: str) -> Iterable[RawDoc]:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "pytesseract and Pillow are required to ingest images via OCR"
            ) from exc

        with Image.open(path) as img:
            text = pytesseract.image_to_string(img, lang=_OCR_LANG)
        text = text.strip()
        if not text:
            return
        yield RawDoc(
            content=text,
            source_file=path,
            source_type=self.source_type,
            metadata={"ocr_lang": _OCR_LANG, "char_count": len(text)},
        )
