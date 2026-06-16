# Ingest Layer — Phase 1 Skeleton (작업 기록)

> `ingest_layer.md` 설계를 기반으로 Phase 1 (Skeleton) 을 작성하면서 보여준
> 코드 미리보기 + 실제 적용된 diff. 학습용 레퍼런스로 보존.

---

## 추가된 파일 (13개)

```
backend/chat/ingest/
  __init__.py                          # 레이어 진입점 패키지
  base.py                              # RawDoc + 3개 Protocol
  registry.py                          # 확장자 → loader 매핑
  pipeline.py                          # 오케스트레이션 (ingest_path / ingest_paths)
  loaders/
    __init__.py                        # 모든 loader side-effect import
    structured/
      __init__.py
      csv.py                           # langchain CSVLoader 래핑
      excel.py                         # pandas + 시트별 순회
  splitters/
    __init__.py
    recursive.py                       # 길이 기반 (RecursiveCharacterTextSplitter)
    row.py                             # 표 1행 = 1청크 (pass-through)
  sinks/
    __init__.py
    chroma.py                          # provider_manager 위임 + 메타데이터 평탄화
```

## 수정된 파일 (1개)

`backend/chat/management/commands/build_vectors.py`
- 70+ 줄 → 약 35줄
- CSV/XLSX if/else 분기 제거
- `ingest.pipeline.ingest_path()` 호출만 남김

---

## 핵심 인터페이스

```python
# base.py
@dataclass
class RawDoc:
    content: str
    source_file: str
    source_type: str
    page: int | None = None
    section: str | None = None
    metadata: dict = field(default_factory=dict)

class BaseLoader(Protocol):
    extensions: tuple[str, ...]
    def load(self, path: str) -> Iterable[RawDoc]: ...

class BaseSplitter(Protocol):
    def split(self, doc: RawDoc) -> Iterable[RawDoc]: ...

class BaseSink(Protocol):
    def write(self, docs: Iterable[RawDoc]) -> int: ...
```

## 등록 패턴 (새 포맷 추가 시)

새 loader 만들 때:

```python
# chat/ingest/loaders/text/pdf.py  (예시 — Phase 3 에서 추가 예정)
from langchain_community.document_loaders import PyPDFLoader
from ...base import RawDoc
from ...registry import register

@register
class PdfLoader:
    extensions = (".pdf",)
    source_type = "pdf"

    def load(self, path: str):
        for i, page in enumerate(PyPDFLoader(path).load()):
            yield RawDoc(
                content=page.page_content,
                source_file=path,
                source_type=self.source_type,
                page=i,
            )
```

그리고 `loaders/__init__.py` 에 한 줄:

```python
from . import text  # noqa: F401
```

끝. `build_vectors.py` 는 안 건드린다.

---

## 검증 결과

```
$ python -c "from chat.ingest import base, registry, pipeline; ..."
imports OK
registered extensions: ('.csv', '.xls', '.xlsx')
RawDoc fields: ['content', 'source_file', 'source_type', 'page', 'section', 'metadata']

$ python -c "loader.load('galaxy_s25_data.csv')"
CSV → 7 RawDocs → 7 chunks
first chunk content: Model: Galaxy S25 | Color: Phantom Black | Storage: 256GB | ...
source_type: csv | section: row:0
```

기존 동작과 동일 — 7행 CSV → 7청크 (이전 빌더의 `chunk_size=1000` 기준에서도
행이 짧아 1청크였음). 단, 이제 metadata 가 표준 키(`source_file`,
`source_type`, `section`, `chunk_index`) 로 통일.

---

## Phase 1 이 의도적으로 안 한 것

| 항목 | 이유 / 후속 단계 |
|---|---|
| Manifest / dedup | Phase 2 — `IngestManifest` 모델 + SHA256 기반 |
| PDF / DOCX / HTML loader | Phase 3 — 새 loader 파일 하나씩 |
| Clause / heading splitter | Phase 4 — 사규/법규 조항 단위 청킹 |
| OCR loader | Phase 5 — pytesseract / PaddleOCR |
| ORM sink (knowledge_product) | Phase 6 — 분류 3 정확 조회용 |
| HWP / CAD | Phase 7 — 변환 단계 별도 |
| Upload API + Admin 위젯 | Phase 8 — HTTP 업로드가 생길 때 Celery 비동기 적용 (`async_ingest_plan.md`, `async_ingest_tradeoff.html` 참고) |
| `chat/build_vector_store.py` 제거 | 별도 PR — 중복 빌더 정리 |

---

## 학습 메모

- **Protocol vs ABC**: Python 3.8+ `typing.Protocol` 사용. ABC 보다 결합도 낮음
  — loader 가 protocol 을 명시적으로 상속하지 않아도 duck typing 으로 통한다.
  `@runtime_checkable` 로 isinstance() 검사도 가능.
- **side-effect import**: `loaders/__init__.py` 가 하위 모듈을 import 하는
  순간 `@register` 데코레이터가 실행되어 registry 가 채워진다. Django app
  등록과 유사한 패턴.
- **메타데이터 평탄화**: Chroma 는 metadata 에 nested dict/list 못 받음
  (scalar 만). `_to_lc_document()` 에서 nested 는 폐기 — 그 데이터가 필요하면
  ORM sink 가 별도로 보관.
- **Celery 보류**: Phase 1/2 의 병목은 비동기 실행이 아니라 중복 적재다.
  Upload API/외부 트리거가 생기기 전까지는 동기 CLI + manifest 가 더 단순하다.
- **CsvLoader 가 yield 쓰는 이유**: 큰 CSV 들어왔을 때 메모리 폭주 방지.
  pipeline 도 `list()` 대신 generator 로 흘릴 수 있게 설계 가능 (지금은 단순화
  위해 `list()` 로 받지만, Phase 5 OCR 처럼 무거워지면 streaming 전환).
