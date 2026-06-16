# Ingest Upload API — 다른 agent 작업 통합 기록 (⚠️ 일관성 이슈 포함)

> 다른 agent (Codex / 다른 Claude 세션) 가 `IngestUploadAPIView` 를 추가.
> 파일을 실제로 RAG 저장소(Chroma) 에 적재하는 HTTP 엔드포인트.
> Phase 8 (Upload API) 트리거가 일부 발생한 상태이며, 현재 구현이 **Phase 2
> manifest 를 우회**하고 있어 통합 시 짚어야 할 일관성 이슈가 있다.

---

## 1. 추가된 항목

```
backend/chat/ingest_views.py     (modified)
  + _splitter_for_source_type()
  + _ingest_uploaded_file()
  + class IngestUploadAPIView

backend/chat/urls.py             (modified)
  + path("ingest/upload/", IngestUploadAPIView.as_view(), name='ingest-upload')
```

**프론트엔드 페이지는 아직 없음** (`frontend/pages/` 에 upload UI 미존재).

## 2. 동작 흐름

`POST /api/v1/triple/ingest/upload/` — multipart, `files` 필드 (배열).

```
1. files 받음
2. 각 file 마다:
   a. 확장자 검사 — registered_extensions() 안에 있는지
   b. 임시 파일에 쓰기
   c. loader_for(tmp).load() → RawDoc[]
   d. source_type 별 default splitter (csv/excel → row, 그 외 → recursive)
   e. ChromaSink().write(chunks)  ← 여기가 문제. pipeline.ingest_path 우회
   f. 임시 파일 unlink
3. {processed: [...], failed: [...]} 반환
```

## 3. ⚠️ 일관성 이슈 — Phase 2 manifest 우회

**중요도: 높음**. Phase 2 가 막으려고 만든 그 중복 적재 사고 (8행 CSV → 88
청크) 가 Upload 경로에서 다시 발생할 수 있다.

### 현재 코드 (`_ingest_uploaded_file`)

```python
def _ingest_uploaded_file(tmp_path: str) -> int:
    loader = loader_for(tmp_path)
    chunks = []
    for raw_doc in loader.load(tmp_path):
        splitter = _splitter_for_source_type(raw_doc.source_type)
        chunks.extend(splitter.split(raw_doc))
    result = ChromaSink().write(chunks)   # 🚨 manifest 안 거침
    return result.count
```

### 무엇이 빠졌나

`pipeline.ingest_path()` 가 하는 일 중 안 한 것:

| 단계 | `pipeline.ingest_path` | `_ingest_uploaded_file` |
|---|---|---|
| SHA256 계산 | ✅ `file_sha256()` | ❌ |
| 같은 hash 면 skip | ✅ `already_ingested()` | ❌ |
| 같은 source 의 옛 hash 청크 제거 | ✅ `previous_versions` + `delete_ids` | ❌ |
| manifest 기록 | ✅ `record_success` / `record_failure` | ❌ |
| 결정론적 id 적용 | ✅ (ChromaSink 자체 기능) | ✅ (sink 가 동일) |

`ChromaSink.write()` 의 결정론적 id 덕에 *같은 청크 내용* 이면 Chroma 가
upsert 처리. 단:
- 같은 파일이 다른 이름으로 올라오면 `source_file` 이 달라 id 가 달라짐 →
  **새 청크로 추가됨** (중복 적재).
- 파일 내용이 바뀌었을 때 옛 청크가 자동 제거되지 않음 → **stale chunks
  누적**.
- 운영자가 "이 파일이 들어왔는가" 를 확인할 수단이 없음 (manifest 없음).

### 권장 수정 (다른 agent / 다음 PR)

`_ingest_uploaded_file` 가 `pipeline.ingest_path` 를 호출하도록 변경.

```python
# (제안) ingest_views.py
from .ingest.pipeline import ingest_path
from .ingest.splitters.row import RowSplitter
from .ingest.splitters.recursive import RecursiveSplitter

def _ingest_uploaded_file(tmp_path: str, *, original_name: str) -> int:
    # 임시 경로가 아닌 원본 파일명을 source_uri 에 반영 — 같은 이름 재업로드 시 dedup
    # 옵션 1: tmp_path 그대로 쓰되 _to_source_uri 가 안정 키 생성
    # 옵션 2: ingest_path 가 source_uri override 인자를 받게 확장
    loader = loader_for(tmp_path)
    splitter = _splitter_for_source_type(loader.source_type)
    sink = ChromaSink()
    return ingest_path(tmp_path, splitter, sink)
```

단, 현재 `ingest_path` 는 `source_uri = file:// + abspath(path)` 로 만든다.
업로드 임시 파일은 `/tmp/<random>.csv` 처럼 매번 경로가 달라 manifest 가
같은 파일을 인식 못 한다. **두 가지 옵션**:

#### 옵션 A — `pipeline.ingest_path` 에 `source_uri_override` 추가
```python
def ingest_path(path, splitter, sink, *, force=False, source_uri_override: str | None = None):
    ...
    source_uri = source_uri_override or manifest_helpers.source_uri_for(path)
    ...
```
업로드 측에서 `f"upload://{original_name}"` 같은 안정 키 주입.

#### 옵션 B — `_ingest_uploaded_file` 가 manifest 직접 호출
```python
from .ingest import manifest as manifest_helpers
source_uri = f"upload://{original_name}"  # 또는 filename + sha256 prefix
doc_sha = manifest_helpers.file_sha256(tmp_path)
existing = manifest_helpers.already_ingested(source_uri, doc_sha)
if existing:
    return 0
...
```

옵션 A 가 더 좋다 — pipeline 한 곳에 dedup 로직 집중. Upload / CLI / 향후
Celery task 모두 같은 함수 호출 → 일관성.

## 4. 부가 일관성 노트

### 4.1 `permission_classes` 없음

`IngestPreviewAPIView` 도 명시 없음, `IngestUploadAPIView` 도 명시 없음.
Preview 는 저장 안 해서 anonymous OK 지만 **Upload 는 영구 저장 → 권한
필요**. 적어도 Manager+ 만 허용해야 함.

```python
# (제안)
from rest_framework.permissions import IsAuthenticated
class IngestUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]
```

추후 Role 기반 permission 도입 시 ADMIN/MANAGER 만 허용.

### 4.2 응답 shape 가 chunk_lab / token_lab 과 다름

| 페이지 | 응답 top-level |
|---|---|
| chunk_lab preview | `{source, num_chunks, chunks: [...], ...}` |
| token_lab | `{analysis: {...}, language_samples: [...]}` |
| **upload** | `{processed: [...], failed: [...]}` |

배치 처리라 list 두 개 반환은 합리적. 단 각 항목의 키 명명:
- `processed[i]`: `{filename, status, chunks}` — status 가 redundant ("ok" 만)
- `failed[i]`: `{filename, error}` — chunks 키 없음

향후 통일 시 `result: [{filename, status, chunks?, error?}]` 단일 배열도
고려.

### 4.3 동시 업로드 / 비동기 가능성

현재 동기 처리. 큰 PDF 가 들어오면 HTTP timeout 위험.

이게 [`async_ingest_plan.md`](async_ingest_plan.md) 가 정의한 **Phase 8
트리거 1번 — "Upload API 가 생겨 ingest 가 HTTP request-path 에 들어올 때"**
다. 보류했던 비동기 도입 논의를 다시 시작할 때가 된 셈.

다만 PDF/HWP loader (Phase 3/7) 가 아직 없으니 *지금은 작은 CSV/TXT 만
가능*. 무거운 포맷이 합류하기 전에 manifest 통합 + 비동기 결정 둘 다 해야
함.

## 5. 영향도 정리 — 누가 무엇을 봐야 하나

| 항목 | 우선순위 | 담당 후보 | 비고 |
|---|---|---|---|
| `_ingest_uploaded_file` 이 `pipeline.ingest_path` 통과하도록 수정 | **높음** | Claude Code (integration) | 중복 적재 차단 |
| `pipeline.ingest_path(source_uri_override)` 옵션 추가 | 높음 | Claude Code | 위 작업 의존 |
| `IngestUploadAPIView.permission_classes` | 중 | Claude Code 또는 추가한 agent | 영구 저장은 권한 필요 |
| Upload 결과에 manifest 정보 노출 (`manifest_id`) | 중 | 추가한 agent | UI 가 추적 가능하게 |
| Streamlit upload 페이지 | 낮 | 다른 Claude | UI 가 없으면 운영자가 못 씀 |
| 큰 파일 비동기 처리 | **Phase 8 검토 재시작** | 회의 후 결정 | `async_ingest_plan.md` 재방문 |

## 6. 안 한 것 (의도적 — 문서화 단계)

- **코드 수정 X** — Claude Code 의 역할은 문서화/일관성. 위 권고는 통합
  담당이 작업할 때 참고.
- **manifest 호출 강제 X** — 단순 monkey-patch 가 아니라 `ingest_path`
  인터페이스 결정 후 정리해야 함 (옵션 A vs B 결정 필요).
- **테스트 추가 X** — Upload 경로의 dedup 테스트는 manifest 통합 이후.

---

## 관련 문서

- [ingest_phase2_manifest.md](ingest_phase2_manifest.md) — manifest 가 막는 사고의 정의
- [ingest_layer.md](ingest_layer.md) — pipeline 흐름 전체
- [async_ingest_plan.md](async_ingest_plan.md) — Phase 8 트리거 정의 — 이 Upload API 가 그 트리거 1번
- [work_distribution.md](work_distribution.md) — agent 분담 매트릭스
