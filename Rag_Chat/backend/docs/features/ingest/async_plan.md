# Async Ingest — Celery + Redis 활용안

> ## ⚠️ 결론 (2026-05-27 갱신)
>
> **현재 단계에서는 Celery 가 필요 없다. Phase 8 (Upload API) 로 미룬다.**
>
> 이전 버전 결론("A 인제스천 비동기를 먼저") 은 과한 권고였다. 트리거가
> 없다 — 현재 ingest 는 CLI 단일 호출이고 HTTP request-path 압력·동시성·
> 외부 트리거 어느 것도 없다. Phase 2 manifest (Django 모델 + SHA256) 만으로
> 중복 적재·재실행 안전성 90% 가 해결된다.
>
> Celery 가 필요해지는 시점:
> 1. Upload API 가 생겨 ingest 가 HTTP request-path 에 들어올 때
> 2. Slack/Webhook 외부 자동 트리거가 생길 때
> 3. 다수 운영자가 동시에 파일 올릴 때
>
> 이 셋 중 하나라도 발생하면 그때 아래 설계를 참고. 그전에는 동기 CLI 유지.
>
> ---
>
> 질문: "맥락의 경량화를 위해 Redis 와 Celery beat 를 활용하는 방식으로
> 하는 것은? 가능한가?"
> 답: **가능하지만 지금은 필요 없다.** 인프라(Celery+Redis)가 떠 있어 언제든
> 붙일 수는 있다. "맥락 경량화" 가 (1) 인제스천 부하 분리인지 (2) LLM 컨텍스트
> 절약인지에 따라 갈리는데, (1) 은 트리거 부재로 보류, (2) 는 트래픽 누적
> 후 검토.

---

## 1. 인제스천 부하 분리 (미래 적용 설계)

### 지금은 아직 문제가 아니다

- 현재 ingest 진입점은 `python manage.py build_vectors` 동기 CLI 이다.
  HTTP 요청이 아니므로 timeout/UX 압력이 없다.
- 영업팀 Admin 파일 드롭, Upload API, Slack/Webhook 자동 인입은 아직 없다.
- 같은 파일 반복 실행으로 생기는 중복 적재는 Celery 락보다
  **Phase 2 manifest (Django 모델 + SHA256)** 로 먼저 해결해야 한다.

아래 설계는 Phase 8 에서 Upload API 또는 외부 트리거가 생겼을 때 적용한다.

### 미래 해결 — Celery shared_task

```python
# chat/tasks.py 에 추가 (스케치)
from celery import shared_task
from .ingest.pipeline import ingest_path
from .ingest.splitters.row import RowSplitter
from .ingest.sinks.chroma import ChromaSink

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def ingest_file_task(self, path: str, splitter_name: str = "row") -> int:
    """파일 1개를 비동기로 ingest. Celery worker 가 실행."""
    splitter = _make_splitter(splitter_name)  # 환경변수로 chunk_size 받음
    sink = ChromaSink()
    try:
        return ingest_path(path, splitter, sink)
    except Exception as exc:
        # 일시적 임베딩 API 오류는 재시도, 파일 자체 문제면 retry 불가능 분기
        raise self.retry(exc=exc)
```

호출 측 (Admin 파일 드롭 등):

```python
ingest_file_task.delay("/uploads/사규_v3.pdf")
# → 즉시 task_id 반환, 응답 즉시 끊김
```

### Redis 의 역할 — 큐 + 락 + 진행 상태

1. **메시지 브로커 (이미 사용 중)** — Celery 의 기본 queue. 추가 작업 없음.

2. **In-progress 락** — 같은 파일 double-submit 방지:
   ```python
   from django.core.cache import cache  # 이미 redis 백엔드
   lock_key = f"ingest:lock:{sha256(path)}"
   if cache.add(lock_key, "1", timeout=600):   # NX 시맨틱
       ingest_file_task.delay(path)
   else:
       return "already in progress"
   ```
   manifest 가 영구 dedup 을 담당하고, Redis 락은 동시 업로드 중복 실행만 막는다.

3. **진행 상태 캐시** — UI 가 진행률 보여줄 수 있도록:
   ```python
   cache.set(f"ingest:progress:{task_id}", {"stage": "loading", "pct": 0.2}, 3600)
   ```
   사용자는 Streamlit/Admin 에서 진행률 폴링.

### Celery beat 의 역할 — 정기 스캔

```python
# triple_chat_pjt/settings.py 또는 celery beat schedule
CELERY_BEAT_SCHEDULE = {
    "scan-knowledge-sources": {
        "task": "chat.tasks.scan_and_ingest",
        "schedule": crontab(minute="*/10"),   # 10분마다
    },
}
```

```python
@shared_task
def scan_and_ingest() -> dict:
    """지정 디렉토리(예: backend/knowledge_sources/) 를 훑어
    manifest 에 없는 신규 파일만 ingest_file_task 로 enqueue."""
    new = _diff_against_manifest(settings.KNOWLEDGE_SOURCES_DIR)
    for path in new:
        ingest_file_task.delay(path)
    return {"queued": len(new)}
```

→ 영업팀이 NAS / S3 에 파일만 떨궈도 자동 색인.

### Phase 8 적용 시 효과

- 동기 CLI 인 `build_vectors` 는 개발/복구용으로 유지하고,
  실 운영 업로드는 Celery 경로로 전환.
- HTTP 요청·UI 응답이 빨라짐 — "맥락 경량화" 의 한 축 충족.

---

## 2. LLM 컨텍스트 윈도우 절약 (Redis 단독)

만약 "맥락 경량화" 가 **LLM 호출 시 컨텍스트가 너무 무거워서** 라는 뜻이면
방향이 다르다. 이쪽은 ingest layer 가 아니라 **retrieval 측** 문제다.

### 가능한 캐시 패턴

1. **Retrieval 결과 캐시** — 같은 질문이 자주 들어오면 Chroma 검색 결과를
   Redis 에 캐싱 (TTL 5~30분):
   ```python
   key = f"retrieval:{sha256(question)}:k={k}"
   docs = cache.get(key) or _do_retrieval()
   ```
   LLM 호출은 캐시 못 함 (응답이 다양해야 하니), 그 앞단 검색만 캐싱.

2. **임베딩 캐시** — 짧은 질문이 반복되면 embedding API 호출 자체를 캐싱:
   ```python
   key = f"emb:{model}:{sha256(text)}"
   vec = cache.get(key) or embed(text)
   ```
   비용 절감 효과가 크다 — Gemini/OpenAI 임베딩은 호출당 과금.

3. **대화 요약 캐시** — 멀티턴 대화의 이전 turn 요약을 Redis 에 저장해
   LLM 으로 보낼 컨텍스트 자체를 줄임. 7강에서 강사가 짚은 "히스토리 관리가
   실무 핵심 과제" 가 이 영역.

이 셋은 ingest layer 작업과 독립이므로 별도 PR.

---

## 3. 권장 적용 순서 (갱신)

| 단계 | 의존 | 비고 |
|---|---|---|
| (a) Manifest 모델 + SHA256 dedup | Phase 1 layer | 지금 다음 작업. Celery 없이 동기 CLI 에 먼저 적용 |
| (b) `build_vectors --reset/--force` | (a) | 같은 source 재인덱싱과 Chroma cleanup 경로 |
| (c) Text/OCR/HWP loader 확장 | (a) | 새 loader 를 실제로 돌려도 중복 오염 방지 |
| (d) 임베딩 캐시 | 독립 | 비용 압력이 보이면 model 키 포함해 Redis 캐시 |
| (e) Upload API + 진행률 캐시 | (a) | HTTP request-path 가 생길 때 |
| (f) `ingest_file_task` shared_task + Redis 락 | (e) | Phase 8. 동시 업로드/외부 트리거 대응 |
| (g) Celery beat 디렉토리 스캔 | (f) | 자동 색인이 실제 요구사항이 될 때 |

---

## 4. 주의 — Celery 도입의 비용

- **로컬 dev 마찰**: `docker-compose up` 으로 worker+beat+broker 떠야 함.
  CLI 만으로 빠른 반복 작업 하려면 `build_vectors` 동기 경로를 유지해야 함.
- **로그/관측성**: task 실패 추적이 시각적이지 않음 — Flower 도입 또는
  Sentry / structlog 로 task_id 별 추적 필요.
- **테스트**: `CELERY_TASK_ALWAYS_EAGER=True` 로 동기 실행 모드 두고
  unit test 작성.
- **재시도 폭주**: 임베딩 provider 가 다운되면 모든 task 가 retry → 큐 폭주.
  exponential backoff + dead letter queue 고려.

---

## 5. 결론 (갱신)

"가능한가?" → **가능. 하지만 지금 필요 없다.**

- **현재 단계 (~Phase 7)**: 동기 `build_vectors` CLI 가 충분. Phase 2 manifest
  로 중복 적재만 막으면 운영 안정성 확보.
- **Phase 8 (Upload API) 들어갈 때**: 위 (e)~(g) 를 한 PR 로 같이.
- **트래픽이 의미 있어진 후**: 임베딩 캐시 (B-2) 만 따로 도입.

이 문서는 **그 시점이 왔을 때 참고할 설계** 로 보존. 지금 구현 X.
