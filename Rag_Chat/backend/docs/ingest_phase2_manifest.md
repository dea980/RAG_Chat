# Ingest Layer — Phase 2 Manifest (작업 기록)

> 동기 CLI 기반 ingest 에 멱등성/dedup 을 부여한 Phase 2.
> Celery 는 도입하지 않았다 (`async_ingest_plan.md` 의 결론대로 Phase 8 보류).

---

## 1. 해결한 문제

- 같은 파일을 두 번 `build_vectors` 돌리면 Chroma 에 청크가 또 적재됨
  → 누적된 결과로 7행 CSV 가 **88 청크**가 되어 있었던 hidden bug.
- 파일 내용이 바뀌었을 때 옛 청크가 제거되지 않아 stale chunks 누적.
- 실패한 ingest 시도가 추적되지 않아 재시도 여부 판단 불가.

## 2. 추가된 파일

```
chat/models.py                            # IngestManifest 모델 추가
chat/migrations/0006_ingestmanifest.py    # 마이그레이션
chat/ingest/manifest.py                   # SHA256 helper + DB 조회/기록
```

## 3. 수정된 파일

```
chat/ingest/base.py                       # WriteResult dataclass + BaseSink.delete_ids 추가
chat/ingest/sinks/chroma.py               # 결정론적 ID, add_documents(ids=...), delete_ids, reset
chat/ingest/pipeline.py                   # manifest 통합 (skip / supersede / record_success/failure)
chat/management/commands/build_vectors.py # --rebuild, --force 플래그
```

## 4. IngestManifest 스키마

| 필드 | 타입 | 설명 |
|---|---|---|
| `source_uri` | CharField(512) | `file:///abs/path` 또는 `s3://...` |
| `doc_sha256` | CharField(64) | 파일 내용 hex digest |
| `loader` | CharField(32) | `csv` / `pdf` / `txt` ... |
| `splitter` | CharField(32) | `row` / `recursive` ... |
| `chunk_count` | IntegerField | 저장된 청크 개수 |
| `chroma_ids` | JSONField | 결정론적 chroma id 목록 (삭제용) |
| `status` | TextChoices | `OK` / `FAILED` / `SUPERSEDED` |
| `error` | TextField | 실패 시 traceback (8000자 절단) |
| `ingested_at` | DateTimeField | auto_now_add |

`unique_together = (source_uri, doc_sha256)` — 같은 파일·같은 내용 두 번 안 들어감.

## 5. Pipeline 동작 (Phase 2)

```
1. loader_for(path) — 확장자로 loader 결정 (Phase 1과 동일)
2. file_sha256(path) — 내용 hash 계산
3. already_ingested(source_uri, sha256, status=OK) → 있으면 skip 후 반환
4. previous_versions(source_uri, exclude=sha256) → 있으면:
       - 각 manifest 의 chroma_ids 합집합을 sink.delete_ids() 로 제거
       - 그 manifest 들을 SUPERSEDED 표시
5. loader.load() → splitter.split() → sink.write() → WriteResult(count, ids)
6. record_success / record_failure 로 manifest 갱신 (update_or_create)
```

## 6. 결정론적 청크 ID

`ChromaSink._chunk_id(chunk)` 가 다음을 SHA256 으로 묶어 id 생성:
- `chunk.source_file`
- `chunk.section` (CSV 행 번호, PDF 페이지 등)
- `chunk.metadata["chunk_index"]`
- `chunk.content`

결과:
- 같은 파일·같은 청킹 결과 → 같은 id → Chroma `add_documents` 가 자동 upsert
- 파일 내용이 바뀌어 청크가 달라지면 id 도 달라짐 → 옛 id 는 manifest 의
  `chroma_ids` 에 남아 삭제 추적 가능

## 7. 새 CLI 플래그

```bash
# 평소 사용 — manifest 가 dedup 자동 처리
python manage.py build_vectors

# 같은 hash 라도 재적재 (디버깅용 — manifest 는 update_or_create)
python manage.py build_vectors --force

# Chroma 컬렉션과 manifest 전부 비우고 처음부터 (88청크 정리용)
python manage.py build_vectors --rebuild
```

## 8. 검증 결과

```
1st (fresh)        chunks=7  manifest=1
2nd (same hash)    chunks=0  manifest=1   ← skip
3rd (force=True)   chunks=7  manifest=1   ← update_or_create
unknown ext        ValueError ✓
file_sha256 stable ✓
```

## 9. 안 한 것 (의도적)

- **Celery shared_task / Redis 락** — Phase 8 보류. 동기 CLI 라 트리거 없음.
- **자동 디렉토리 스캔** — 동일. Phase 8 와 함께.
- **manifest list 명령어** — Django admin 에서 보면 됨. 별도 CLI 불필요.
- **chroma_ids 와 실제 Chroma 컬렉션 정합성 감사 명령** — orphan 청크가
  manifest 없이 누적된 경우만 필요. `--rebuild` 가 더 단순.

## 10. 학습 메모

- **`update_or_create` 가 `create` 보다 안전한 이유**: `force=True` 또는
  이전에 FAILED 한 시도가 있을 때 unique 제약 충돌을 피한다. 코드 분기
  없이 한 함수로 흡수.
- **Protocol 에 `delete_ids` 추가**: BaseSink 가 read-only 가 아닌 invariant
  를 갖게 됨. ORM sink (Phase 6) 도 같은 메서드 구현 필요.
- **`get_vector_store()` vs `from_documents()`**: Phase 1 까지는 후자였는데
  ids 제어가 안 되어 결정론적 id 를 못 썼다. `get_vector_store().add_documents(docs, ids=...)`
  로 바꾼 게 dedup 의 핵심.
- **`already_ingested` 가 OK 만 본다**: FAILED 레코드가 있어도 같은 hash
  로 재시도 가능. update_or_create 가 FAILED → OK 로 갱신.
