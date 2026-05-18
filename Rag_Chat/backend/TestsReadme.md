# Triple Chat 테스트 가이드

테스트는 두 가지 축으로 운영됩니다:
1. **단위/통합 테스트** — pytest + Django test runner (Postgres + Redis 서비스 의존)
2. **검색 정확도 회귀** — `chat/tests/evals/run_chunk_ab.py` (BM25, LLM 호출 0)

## 디렉토리 구조

```
backend/
├── chat/
│   └── tests/
│       ├── test_utils.py        # RAGUtils 등 유틸 테스트
│       ├── test_views.py        # ChatAPIView / ChatUserAPIView 통합 테스트
│       └── evals/
│           ├── dataset.jsonl    # 영업팀 시나리오 12문항
│           └── run_chunk_ab.py  # chunk_size × overlap A/B 하니스
├── knowledge/                   # (테스트 미작성 — Phase 1)
├── moderation/                  # (테스트 미작성 — Phase 1)
└── audit/                       # (테스트 미작성 — Phase 1)
```

> **솔직히 짚어두는 점**: 새로 추가된 knowledge / moderation / audit 앱에는 unit test가 아직 없습니다.
> 이는 의도된 trade-off — 영업팀 베타 일정에 맞추기 위함. Phase 1에서 다음 우선순위로 보강:
> 1. `moderation.filter.apply` — BLOCK/MASK/WARN 각 경로
> 2. `knowledge.views.ProductSearchView` — Q 파라미터 + category 필터
> 3. `audit.middleware.AuditLogMiddleware` — 예외 시 응답 비차단

## 실행

### 로컬 (SQLite, 빠른 dev 실행)
```bash
cd backend
./venv/bin/pytest                # 모든 테스트
./venv/bin/pytest chat/tests/test_views.py -k chat_api
```

### Postgres + Redis 환경 (CI와 동일)
```bash
docker-compose up -d postgres redis
DATABASE_URL=postgres://postgres:postgres@localhost:5432/triple_chat \
REDIS_URL=redis://localhost:6379/0 \
./venv/bin/pytest
```

### 검색 정확도 A/B
```bash
./venv/bin/python -m chat.tests.evals.run_chunk_ab \
  --sizes 80,150,250,500,1000 \
  --overlaps 0,30,80,150 \
  --k 5
```
결과 표 + JSON. CI에서도 동일하게 실행되어 artifact로 보관됨.

## Smoke / 수동 검증

### Health
```bash
curl -s http://localhost:8000/api/v1/triple/health/
curl -s http://localhost:8000/api/v1/triple/health/ready/ | jq
```

### Knowledge API
```bash
curl -s 'http://localhost:8000/api/v1/knowledge/products/?q=galaxy' | jq
curl -s 'http://localhost:8000/api/v1/knowledge/contacts/?department=영업' | jq
```

### Moderation 동작 확인 (Django shell)
```python
from moderation.models import ForbiddenWord, ModerationLog
from moderation.filter import apply

ForbiddenWord.objects.create(word="기밀", category="기밀", severity="MASK")
result = apply("이건 기밀입니다", source=ModerationLog.Source.INBOUND)
assert result.sanitized == "이건 [REDACTED]입니다"
```

### Audit
모든 mutating call이 자동 기록 — `/admin/audit/auditlog/`에서 확인.

## CI 통합

`.github/workflows/ci.yml`의 4개 job:
1. **lint** — flake8 (pragmatic ruleset)
2. **django-tests** — Postgres + Redis 서비스 컨테이너 + pytest
3. **retrieval-eval** — chunk A/B harness, 결과를 GitHub Step Summary + artifact로 노출
4. **docker-build** — backend / frontend 이미지 빌드 검증

## 향후 (Phase 1)

| 추가할 테스트 | 이유 |
|---------------|------|
| `moderation.filter` 각 분기 | BLOCK이 정말 LLM 호출 0인지 보장 |
| `knowledge` 검색 ranking | "갤럭시" → 정확히 제품 행 매칭 |
| `audit` 미들웨어 panic-safety | 감사 실패가 응답에 영향 없는지 |
| `chat.refresh_user_session` | Redis TTL ↔ DB expiry 정합성 회귀 |
| API 시리얼라이저 validation | bad input 거부 |
