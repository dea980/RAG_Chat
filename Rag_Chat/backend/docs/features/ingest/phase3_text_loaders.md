# Ingest Phase 3 — Text 분류 1 Loaders (다른 agent 작업 통합 기록)

> 다른 agent (Codex / 다른 Claude 세션) 가 PDF/DOCX/HTML loader 를 추가.
> 분류 1 (텍스트 추출형) 의 핵심 포맷이 한 번에 들어왔다.
> 구현은 깔끔하지만 **splitter dispatch 가 통합되지 않은 채로 두 군데에서
> 따로 처리**되고 있어 정리가 필요하다.

---

## 1. 추가된 파일

```
backend/chat/ingest/loaders/text/
  __init__.py                # txt + pdf + docx + html side-effect import
  txt.py                     # Phase 2 단계에 Claude Code 가 추가, 기존
  pdf.py                     # 신규 — pypdf 페이지 단위
  docx.py                    # 신규 — docx2txt 전체 텍스트
  html.py                    # 신규 — BeautifulSoup 본문 추출
```

요구사항 (`backend/requirements.txt` 확인):
- `pypdf>=4.0.0` ✓
- `docx2txt>=0.8` ✓
- `beautifulsoup4>=4.12.0` ✓

## 2. 각 loader 구조 요약

| Loader | source_type | RawDoc 단위 | 메타데이터 | 의존성 |
|---|---|---|---|---|
| `PdfLoader` | `pdf` | **페이지마다 1개** (1-indexed) | `page` 필드 + `metadata.page_index` (0-indexed, 약간 redundant) | `pypdf` |
| `DocxLoader` | `docx` | **문서 전체 1개** | `char_count` | `docx2txt` |
| `HtmlLoader` | `html` | **문서 전체 1개** | `char_count` | `beautifulsoup4` |

공통: lazy import (의존성 부재 시 `RuntimeError` 친절히 발생), 빈 텍스트면
yield 안 함 (skip).

## 3. ⚠️ 통합 이슈 — Splitter Dispatch 가 두 군데에서 다름

**중요도: 높음**. 같은 RAG 파이프라인인데 진입 경로에 따라 splitter 선택
로직이 따로 있다.

### 현재 상황

**`build_vectors.py` (CLI)** — RowSplitter 하드코딩:
```python
splitter = RowSplitter()
...
ingested += ingest_path(path, splitter, sink, force=options["force"])
```

→ PDF/DOCX/HTML 을 만나도 RowSplitter 가 적용된다. RowSplitter 는
pass-through (1개 RawDoc → 1청크) 라:
- **PDF**: 페이지마다 1청크. 5000자 페이지 → 5000자 청크. 청킹 효과 0.
- **DOCX/HTML**: 문서 전체가 단일 RawDoc → **단일 청크**. 즉 청킹이 사실상
  안 됨. 100KB DOCX → 1 chunk.

이건 retrieval 정확도에 치명적. 7강 강사가 짚은 청킹 효과가 사라진다.

**`ingest_views.IngestUploadAPIView` (Upload API)** — source_type 별 분기:
```python
def _splitter_for_source_type(source_type: str):
    if source_type in {"csv", "excel"}:
        return RowSplitter()
    return RecursiveSplitter()
```

→ CSV/XLSX 는 RowSplitter, 그 외는 RecursiveSplitter (default chunk_size).
이쪽은 합리적이지만 **build_vectors 와 같은 로직이 두 군데에 따로 존재**.

### 권장 통합 — Splitter Registry 또는 Pipeline 자동 선택

#### 옵션 A — `pipeline.ingest_path` 가 splitter 자동 선택 (권장)

`pipeline.ingest_path` 시그니처에서 splitter 를 optional 로:

```python
def ingest_path(
    path,
    splitter: BaseSplitter | None = None,
    sink: BaseSink | None = None,
    *,
    force: bool = False,
):
    loader = loader_for(path)
    if splitter is None:
        splitter = default_splitter_for(loader.source_type)
    if sink is None:
        sink = ChromaSink()
    ...
```

그리고 `chat/ingest/splitters/__init__.py` 에:

```python
DEFAULT_BY_SOURCE = {
    "csv": "row",
    "excel": "row",
    "pdf": "recursive",
    "docx": "recursive",
    "html": "recursive",
    "txt": "recursive",
}

def default_splitter_for(source_type: str) -> BaseSplitter:
    name = DEFAULT_BY_SOURCE.get(source_type, "recursive")
    return {"row": RowSplitter, "recursive": RecursiveSplitter}[name]()
```

이렇게 하면:
- `build_vectors` 는 splitter 인자 제거 → registry 가 처리
- `IngestUploadAPIView._splitter_for_source_type` 도 제거 → 같은 로직
- Phase 4 에서 `clause` / `heading` splitter 가 들어와도 `DEFAULT_BY_SOURCE`
  한 줄만 갱신

#### 옵션 B — Splitter Registry 데코레이터 (Phase 4 와 함께)

Loader 가 자기 splitter 선호도를 선언:

```python
@register
class PdfLoader:
    extensions = (".pdf",)
    source_type = "pdf"
    default_splitter = "recursive"
```

`pipeline.ingest_path` 가 `loader.default_splitter` 를 보고 dispatch.
조항 단위 splitter 가 추가될 때 사규 PDF 는 `default_splitter = "clause"`
로 override 가능.

옵션 B 가 더 확장성 좋다. 단 Phase 4 splitter 도입 시 같이 가야 자연스러움.

### 단기 fix (옵션 A 가 너무 큰 변경이면)

`build_vectors.py` 에 `_splitter_for_source_type` 를 같이 두기:

```python
# build_vectors.py
from ...ingest_views import _splitter_for_source_type
# 또는 splitters/__init__.py 로 옮긴 헬퍼

# DEFAULT_SOURCES 순회 시
for fname in self.DEFAULT_SOURCES:
    ...
    loader = loader_for(path)
    splitter = _splitter_for_source_type(loader.source_type)
    ingested += ingest_path(path, splitter, sink, force=options["force"])
```

여전히 두 곳에서 같은 함수를 import — 통합은 아니지만 중복 로직은 제거.

## 4. 다른 일관성 노트

### 4.1 PDF 의 `page` vs `metadata.page_index`

```python
yield RawDoc(
    content=text,
    source_file=path,
    source_type=self.source_type,
    page=i + 1,                      # 1-indexed
    metadata={"page_index": i},      # 0-indexed
)
```

`RawDoc.page` 표준 필드(`base.py`) 와 `metadata.page_index` 가 같은 정보를
다르게 저장. 약간 redundant. 둘 다 두는 게 위험은 아닌데 다음 페이지 기반
loader 들이 어느 쪽을 따라야 할지 헷갈릴 수 있음. **권장: `page` 만 유지,
0-indexed 가 필요하면 코드에서 `page - 1`**.

### 4.2 DOCX/HTML 이 단일 RawDoc 인 점

현재는 splitter 가 청킹 부담을 다 짊어진다. 단점:
- heading 정보 손실 — DOCX 의 styles, HTML 의 `<h1>~<h6>` 가 사라짐.
- section 메타데이터 없음 — "이 청크가 § 3.2 에서 왔다" 추적 불가.

이건 Phase 4 (heading/clause splitter) 가 해결할 영역. Loader 단에서
heading 을 markdown 으로 변환하거나, 별도 메타데이터로 보존해두면
Phase 4 splitter 가 활용 가능. **권장: 일단 그대로 두고, Phase 4 와
함께 재방문**.

### 4.3 RawDoc 메타데이터 표준화

분류 1 loader 들이 `char_count` 만 metadata 에 넣음. Phase 2 가 자동으로
주입하는 `doc_sha256` 외에는 추가 정보 없음. PDF 는 페이지 수, DOCX 는
작성자/작성일 등의 풍부한 메타데이터를 가질 수 있다 — 추후 retrieval 시
필터링에 쓰일 잠재력. 지금 강제는 안 함.

## 5. 통합 후 가능한 시연 시나리오

Phase 3 + 통합이 끝나면 다음이 가능:

1. **사규 PDF 검색** — `사규_v3.pdf` 를 `knowledge_sources/` 에 두고
   `build_vectors` → "연차 며칠 쓸 수 있나요?" 질문에 39조 청크 회수.
   (7강 강사의 그 시연을 우리 코드로 재현.)
2. **DOCX 매뉴얼** — 제품 매뉴얼 docx → chunk_lab 으로 적정 chunk_size
   탐색 → build_vectors 로 적재.
3. **사내 위키 HTML 덤프** — 정적 HTML export → 본문만 추출되어 색인.

다 가능하려면 §3 통합이 선행돼야 함 (RowSplitter 로는 청킹 안 됨).

## 6. 영향도 정리 — 후속 작업

| 항목 | 우선순위 | 담당 후보 | 비고 |
|---|---|---|---|
| `pipeline.ingest_path` 가 splitter 자동 dispatch (옵션 A) | **높음** | Claude Code (integration) | 두 진입경로 일관화 |
| build_vectors 의 RowSplitter 하드코딩 제거 | 높음 | Claude Code (위와 동일 PR) | PDF 청킹이 실제로 동작하게 |
| `_splitter_for_source_type` 를 `splitters/__init__.py` 로 이동 | 중 | Claude Code | DRY |
| PDF `metadata.page_index` 제거 (page 만) | 낮 | 추가한 agent | 작은 정리 |
| Phase 4 heading/clause splitter | 다음 단계 | Codex | DOCX/HTML 의 구조 보존 |
| Upload API 의 manifest 통합 ([ingest_upload_api.md](ingest_upload_api.md)) | 높음 | Claude Code | 별도 doc |
| 새 포맷용 Chunk Lab 시연 (PDF 한 권 청킹 비교) | 낮 | 다른 Claude | PDF 들어오면 자연스러움 |

## 7. 안 한 것 (의도적 — 문서화 단계)

- **코드 수정 X** — Claude Code 역할은 통합 문서/일관성. 위 권고는 정리 PR
  담당이 받아 가서 결정.
- **테스트 추가 X** — loader 테스트 (PDF fixture 등) 는 추가한 agent 의 영역.
- **Phase 4 splitter 제안 코드 X** — work_distribution 대로 Codex 담당.

---

## 관련 문서

- [ingest_layer.md](ingest_layer.md) — 4분류 설계 (Phase 3 = 분류 1)
- [ingest_phase2_manifest.md](ingest_phase2_manifest.md) — manifest 가 새 loader 에도 자동 적용됨 (sha256 변경 없음)
- [ingest_upload_api.md](ingest_upload_api.md) — Upload API 의 manifest 우회 이슈 (별도 트랙)
- [chunk_testing_page.md](chunk_testing_page.md) / [chunk_lab_page.md](chunk_lab_page.md) — 새 loader 들을 chunk_lab 에서 즉시 비교 가능
- [work_distribution.md](work_distribution.md) — Phase 4 splitter 가 Codex 담당
