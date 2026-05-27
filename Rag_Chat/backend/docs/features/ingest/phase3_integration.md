# Phase 3 Integration — Splitter Dispatch + Upload Manifest 통합

> [ingest_phase3_text_loaders.md](ingest_phase3_text_loaders.md) 와
> [ingest_upload_api.md](ingest_upload_api.md) 에서 짚었던 두 일관성 이슈를
> 한 번에 해결한 통합 작업 기록.

---

## 1. 해결한 두 이슈

### Issue A — Splitter dispatch 가 두 군데에서 다름
- `build_vectors.py` 가 `RowSplitter()` 하드코딩 → PDF/DOCX/HTML 청킹 안 됨
- `IngestUploadAPIView._splitter_for_source_type` 가 별도 로직 — 중복

### Issue B — Upload API 가 Phase 2 manifest 우회
- `_ingest_uploaded_file` 가 `ChromaSink().write()` 직접 호출 → 중복 적재 가능
- 임시 파일 경로 매번 달라 `source_uri` 가 안정 키 안 됨

---

## 2. 적용된 변경

### 2.1 `chat/ingest/splitters/__init__.py` — Dispatch 진입점 신설

```python
DEFAULT_BY_SOURCE = {
    "csv": "row", "excel": "row",
    "pdf": "recursive", "docx": "recursive", "html": "recursive",
    "txt": "recursive", "md": "recursive",
}

def default_splitter_for(source_type: str): ...
def splitter_by_name(name: str, *, chunk_size=None, chunk_overlap=None): ...
```

Phase 4 splitter (clause/heading) 들어오면 이 dict 한 줄 갱신.

### 2.2 `chat/ingest/pipeline.py` — splitter/sink optional + source_uri_override

```python
def ingest_path(
    path,
    splitter: BaseSplitter | None = None,
    sink: BaseSink | None = None,
    *,
    force: bool = False,
    source_uri_override: str | None = None,
) -> int:
    ...
    if splitter is None:
        splitter = default_splitter_for(loader.source_type)
    if sink is None:
        sink = ChromaSink()
    source_uri = source_uri_override or manifest_helpers.source_uri_for(path)
    ...
```

세 가지 효과:
- splitter 인자 안 주면 source_type 보고 알아서 선택
- sink 인자 안 주면 ChromaSink 기본
- 임시 파일 경로로 호출하더라도 `source_uri_override` 로 안정 키 주입 가능

### 2.3 `chat/management/commands/build_vectors.py` — RowSplitter 제거

```python
# 이전: splitter = RowSplitter()  ← 하드코딩
# 이후: ingest_path(path, sink=sink, force=options["force"])
#       (splitter 미지정 → source_type 기반 자동)
```

이제 PDF/DOCX/HTML 가 `DEFAULT_SOURCES` 에 추가돼도 자동으로
RecursiveSplitter 가 적용됨.

### 2.4 `chat/ingest_views.py` — Upload 가 pipeline 경유

```python
def _ingest_uploaded_file(tmp_path: str, *, original_name: str) -> int:
    """Load + split + persist via the unified pipeline."""
    source_uri = f"upload://{original_name}"
    return ingest_path(tmp_path, source_uri_override=source_uri)
```

핵심: `upload://<filename>` 안정 키.
- 같은 파일 두 번 업로드 → SHA256 같음 → skip
- 같은 이름·다른 내용 업로드 → 옛 청크 삭제 + manifest SUPERSEDED 표시
- 다른 이름·같은 내용 업로드 → 별도 source_uri 로 기록 (의도된 동작)

응답 변경:
```python
"status": "ok" if chunk_count > 0 else "skipped"  # 0 청크면 skip 명시
```

기존 `_splitter_for_source_type` 헬퍼는 제거 — `default_splitter_for` 로 통합.

---

## 3. 검증

```
1. default_splitter_for: OK (csv→row, pdf/txt/unknown→recursive)
2. splitter_by_name: OK (recursive 에만 chunk_size/overlap kwarg)
4. CSV via pipeline: chunks=7 splitter=row              ← 자동 선택
5. TXT with override: chunks=3 splitter=recursive       ← 자동 + 안정 키
   uri='upload://mydoc.txt'
6. Same upload re-attempt: chunks=0                     ← manifest skip
7. Content changed: chunks=4, OK=1, SUPERSEDED=1        ← 옛 버전 SUPERSEDED
8. build_vectors path (csv): chunks=7 splitter=row      ← CLI 도 동일 dispatch
```

8개 시나리오 모두 통과.

## 4. 영향 받는 entry point — 모두 같은 dispatch 공유

| 호출 위치 | 호출 형태 |
|---|---|
| `build_vectors` CLI | `ingest_path(path, sink=sink, force=...)` |
| `IngestUploadAPIView` | `ingest_path(tmp, source_uri_override=f"upload://{name}")` |
| 향후 Celery task | `ingest_path(path, source_uri_override=...)` |
| 향후 디렉토리 스캔 | `ingest_paths(paths)` |

전부 `pipeline.ingest_path` 한 곳을 거치므로:
- manifest dedup ✓
- splitter 자동 선택 ✓
- 결정론적 청크 id ✓
- 옛 버전 supersede ✓
- 실패 기록 ✓

## 5. 안 한 것 (의도적)

- **`IngestUploadAPIView.permission_classes`** — 별도 결정 필요 (보안 정책).
  Upload 가 영구 저장이므로 `IsAuthenticated` + Role(`MANAGER+`) 권장.
  보안 검토 후 별도 PR.
- **PDF `metadata.page_index` 정리** — `page` 와 redundant 하지만 동작에
  영향 없음. 향후 정리 시.
- **Chunk Lab 의 `_resolve_splitter`** — 사용자가 명시적으로 splitter 와
  파라미터를 고르는 explicit 경로라 자동 dispatch 대상 아님. `splitter_by_name`
  을 사용하도록 정리만.
- **Phase 4 (clause/heading splitter)** — Codex 담당. 이번 PR 범위 밖.
- **디렉토리 자동 스캔** — Phase 8 (Upload API 자동 인입 트리거) 와 함께.

## 6. 다음 자연스러운 작업

| 작업 | 담당 | 비고 |
|---|---|---|
| Upload API 권한 추가 | Claude Code | 보안 정책 확정 후 |
| Phase 4 splitter (clause/heading) | Codex | DOCX/HTML 구조 보존 |
| Upload UI (Streamlit `pages/upload_lab.py`) | 다른 Claude | API 가 준비됐으니 자연스러움 |
| 디렉토리 자동 스캔 (`build_vectors --dir`) | Claude Code | 운영 편의 |

## 7. 학습 메모

- **Dispatch 패턴**: source_type → splitter 매핑이 한 dict 에 모임. 새 포맷
  추가가 (1) loader 등록 (2) `DEFAULT_BY_SOURCE` 한 줄 — 두 곳만 건드림.
- **안정 키 (`upload://...`)**: 임시 파일은 매번 경로가 다르지만 의미적으로
  같은 파일임을 표현하기 위한 URI scheme. file:// 외에 도메인별 scheme 을
  도입할 수 있는 여지 (예: `s3://`, `gdrive://`).
- **optional 인자가 default 를 가지면 사용처가 단순해진다**: `ingest_path(path)`
  만 호출해도 동작. 명시적 인자가 필요할 때만 주면 됨.
- **테스트가 진짜 검증한 것**: dispatch 로직, manifest 통합, supersede 흐름
  — 세 가지가 한 번에 검증됨. `FakeSink` 로 API key 없이 가능.

---

## 관련 문서

- [ingest_layer.md](ingest_layer.md) — 전체 설계
- [ingest_phase2_manifest.md](ingest_phase2_manifest.md) — manifest 가 막는 사고
- [ingest_phase3_text_loaders.md](ingest_phase3_text_loaders.md) — 이슈 정의 (Issue A)
- [ingest_upload_api.md](ingest_upload_api.md) — 이슈 정의 (Issue B)
- [core_concepts.md](core_concepts.md) — Dispatch/멱등성 등 시스템 개념
