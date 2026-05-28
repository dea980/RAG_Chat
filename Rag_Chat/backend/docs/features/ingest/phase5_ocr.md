# Phase 5 — OCR Loader (yesterday T3 결과 통합 자리)

> **5분 진입 (다음 세션)** — yesterday T3 가 `text/ocr.py` 구현 + `ocr/` 디렉토리 중복 발생 → 오늘 야간 정리 commit 으로 `ocr/__init__.py`·`image.py` 삭제, `text/ocr.py` 단독 생존. 현재 `git status` 에 `D Rag_Chat/backend/chat/ingest/loaders/ocr/__init__.py` 두 줄 = 정리 완료 흔적. 다음 commit 직전 `python -c "from chat.ingest.registry import loader_for; print(loader_for('.png'))"` 로 OCRLoader 단일 반환 확인.
>
> **상태**: 🔧 SKELETON — yesterday T3 에이전트가 `backend/chat/ingest/loaders/text/ocr.py` 를 구현. 본 doc 는 *결과를 받아* 통합 내용으로 채워질 자리.
>
> 채워질 시점: T3 가 다음 파일들을 작성하고 사용자가 reality check 한 직후.
>
> ```
> backend/chat/ingest/loaders/text/ocr.py                  (신규)
> backend/chat/ingest/loaders/__init__.py                  (import 1줄)
> backend/chat/tests/ingest/test_ocr_loader.py             (신규)
> backend/requirements.txt                                  (pytesseract 1줄)
> ```

---

## 1. 구현 범위 (작성 예정)

T3 결과 채워넣을 항목 — 초안:

- [ ] **라이브러리**: `pytesseract` (Tesseract OCR Python 바인딩)
- [ ] **대상 확장자**: `.png`, `.jpg`, `.jpeg`, `.tiff`
- [ ] **언어 코드**: `kor+eng` (한·영 동시 인식)
- [ ] **시스템 의존성**: `tesseract` 바이너리 + `tesseract-data-kor` (사용자가 직접 설치)
- [ ] **에러 처리**: `pytesseract.TesseractNotFoundError` 시 명확한 안내 메시지
- [ ] **테스트 fixtures**: `backend/chat/tests/ingest/fixtures/ocr/` (기존, `scripts/build_ocr_fixtures.py` 로 생성)

---

## 2. 검증된 호출 경로 (작성 예정)

예상 패턴 — `pdf.py` loader 를 따라:

```python
# backend/chat/ingest/loaders/text/ocr.py
from chat.ingest.base import BaseLoader, RawDoc
from chat.ingest.registry import register

@register(extensions=(".png", ".jpg", ".jpeg", ".tiff"), source_type="ocr")
class OCRLoader(BaseLoader):
    source_type = "ocr"

    def load(self, path: str) -> list[RawDoc]:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(path), lang="kor+eng")
        return [RawDoc(
            content=text,
            source_file=path,
            source_type="ocr",
            metadata={"ocr_lang": "kor+eng"},
        )]
```

`source_type="ocr"` → `default_splitter_for("ocr")` 매핑 필요. T3 가 추가 안 했으면 다음 세션이 `splitters/__init__.py:DEFAULT_BY_SOURCE` 에 `"ocr": "recursive"` 1줄 추가.

---

## 3. 학습 메모 — 분류 2 OCR 의 위치 (작성 예정)

강의 7강 4분류 중 *분류 2* (스캔 PDF, 이미지). 본 phase 의 핵심 학습:

1. **OCR 은 lossy** — 90~95% 정확도. 한국어 손글씨/저해상도는 더 떨어짐. 결과는 *그대로* 임베딩하지 말고 후처리(개행 정리, OCR artifact 제거) 권장.
2. **언어 모델별 정확도 차이** — Tesseract 4 (LSTM-based) 가 Tesseract 3 (legacy) 보다 한국어 훨씬 좋음. 시스템에 받는 버전 체크 필요.
3. **PaddleOCR vs Tesseract** — PaddleOCR 가 정확도 더 높지만 의존성 무거움 (PyTorch + paddlepaddle). 사내 폐쇄망에선 Tesseract 가 현실적.
4. **이미지 전처리 영향** — DPI 300+ / 흑백 변환 / 노이즈 제거 거치면 정확도 +5~10%. 본 phase 는 *raw 이미지 그대로* 입력. 전처리는 별도 후속 작업.
5. **`ingest_path` 자동 라우팅** — 사용자는 `.png` 던지기만 하면 OCR loader 자동 dispatch. Plugin registry 의 힘.

---

## 4. ingest layer 일관성 (작성 예정)

T3 가 다른 loader 패턴 따랐는지 체크:

- [ ] `@register` 데코레이터로 확장자 등록
- [ ] `BaseLoader` Protocol 준수 (`source_type`, `load(path)`)
- [ ] `RawDoc` 반환 (content + source_file + source_type + metadata)
- [ ] `metadata` 에 OCR 특유 정보 (`ocr_lang`, `image_dpi` 등) 포함
- [ ] `chat/ingest/loaders/__init__.py` 에 side-effect import 추가
- [ ] 테스트: fixture 1~2개로 `load(path)` 호출 + RawDoc 검증

---

## 5. 안 된 것 (의도적, 별도 phase) (작성 예정)

- **PaddleOCR 모드** — 정확도 더 높지만 의존성 무거움. 별도 옵션
- **PDF 내 임베드 이미지 OCR** — 현재 `pdf.py` 는 text 만 추출. 이미지 페이지만 따로 OCR 라우팅은 후속 작업
- **OCR 결과 검수 UI** — Chunk Lab 처럼 *미리보기* 페이지 후속
- **수기 보정 룰** — `ㅇ` → `0` 같은 OCR 흔한 오인식 보정. 도메인별 룰 후속

---

## 6. 다음 세션 즉시 처리할 것 (작성 예정)

- [ ] `tesseract` + `tesseract-data-kor` 시스템 설치 확인 (`brew install tesseract tesseract-lang`)
- [ ] `default_splitter_for("ocr")` 매핑 (`splitters/__init__.py` 1줄)
- [ ] `data/samples/` 에 실제 스캔 한국어 문서 fixture 추가 (현재는 PIL 로 합성한 이미지만)
- [ ] OCR 결과 후처리 정책 결정 (raw 그대로 vs 정리 후 청킹)

---

## 관련 문서

- [`../../architecture/ingest_layer.md`](../../architecture/ingest_layer.md) — 분류 2 OCR 설계
- [`../../sessions/2026-05-27-night-parallel.md`](../../sessions/2026-05-27-night-parallel.md) — T3 가 어떤 분배 하에서 만들어졌는지
- [`phase3_text_loaders.md`](phase3_text_loaders.md) — pdf/docx/html loader 패턴 reference
- [`phase4_splitters.md`](phase4_splitters.md) — splitter dispatch 갱신 사례
- [`../../guides/test_fixtures.md`](../../guides/test_fixtures.md) — fixture 구조
