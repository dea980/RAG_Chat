"""OCR image loader — pytesseract 로 이미지에서 텍스트 추출."""
from __future__ import annotations

from typing import Iterable

from ...base import RawDoc
from ...registry import register


@register
class OcrImageLoader:
    """이미지 파일 → OCR 텍스트 → 단일 RawDoc."""

    extensions = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp")
    source_type = "ocr"

    def load(self, path: str) -> Iterable[RawDoc]:
        import pytesseract
        from PIL import Image

        text = pytesseract.image_to_string(Image.open(path), lang="kor+eng")
        yield RawDoc(
            content=text,
            source_file=path,
            source_type=self.source_type,
            metadata={"ocr_lang": "kor+eng"},
        )
