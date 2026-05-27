"""Loader 모듈 — 포맷별 파서. 각 하위 패키지가 강의 4분류에 대응.

- structured/ : CSV, Excel        (분류 3)
- text/       : PDF, DOCX, HTML   (분류 1, Phase 3 에서 추가)
- ocr/        : 스캔 PDF, 이미지  (분류 2, Phase 5)
- special/    : HWP, CAD          (분류 4, Phase 7)

이 패키지를 import 하기만 해도 모든 loader 가 registry 에 등록된다.
"""
# 등록을 트리거하기 위한 side-effect import.
from . import structured  # noqa: F401
from . import text  # noqa: F401
from .ocr import image as _ocr_image  # noqa: F401
