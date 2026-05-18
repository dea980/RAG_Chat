# Triple Chat — Internal RAG Q&A System
Prototype that tackles a real bootcamp-team problem: non-engineering teams (sales, support) waste hours digging through product docs to answer routine spec/price questions. This is a Django + LangChain RAG chatbot we built end-to-end to make those lookups conversational, with traceable logs so the answers can be audited later.

## 1) Motivation
- **The pain point**: sales reps repeatedly ask "what's the camera spec on S25 Ultra 1TB?" — answers exist in product CSVs and PDFs but live in too many places.
- **What we built**: a chatbot that retrieves the right product chunks and answers in natural language, with every (question → retrieved context → answer) tuple logged for review.
- **Out of scope (deliberate)**: auth/RBAC, forbidden-term filtering — designed but left for the [internal-chat](Rag_Chat/internal-chat/) iteration.

## 2) Problem Focus
Most RAG demos chase model output quality; we focused on the parts that decide whether a chatbot is actually usable in a company:
- **Retrieval accuracy** — measured via a [chunk-size A/B harness](Rag_Chat/backend/docs/chunk_experiment.md) on a real eval set (영업팀 시나리오 12문항). chunk_size=150 lifted recall@5 from 0.789 → 0.833 vs the legacy 1000-char setting.
- **Traceability** — every answer writes a Chat + SearchLog row, so any response can be replayed.
- **Provider flexibility** — Gemini ↔ Qwen via env vars only, no code change.

## 3) Architecture (current)
- Frontend: Streamlit (Redis Pub/Sub aware)
- Backend: Django REST Framework
- Async: Celery worker + beat (vector build, session cleanup)
- Session/Cache: Redis (TTL aligned with DB `User.expired_datetime`)
- **Database**: PostgreSQL 16 (SQLite fallback for local dev)
- Vector Store: FAISS / Chroma
- LLM: Gemini (default), Qwen (OpenAI-compatible, experimental)
- CI: GitHub Actions — lint, Django tests against Postgres+Redis services, retrieval A/B harness, Docker image build

### High-level flow
1) User question in Streamlit → 2) Vector search → 3) LLM generation → 4) Log question/context/response (session state in Redis)

## 4) Data Model (summary)
- User(user_id, created_datetime, expired_datetime)
- Chat(question_id, user_id, question_text, response_text, created_datetime, data_id)
- SearchLog(search_log_id, question_id, data_id, searching_time)
- RagData(data_id, data_text, image_urls)
Traceability: who asked what, with which data, and when.

## 5) Key Design Choices
- Django: structured API/persistence; future-ready for auth/RBAC.
- Redis: session cache + Pub/Sub.
- Celery: keeps logging/vector tasks off the request path.
- Provider abstraction (`chat/providers/manager.py`): env-driven embedding/reasoning/generation; default Gemini, Qwen experimental.

## 6) Implemented
- Session-based RAG chat (Streamlit + Django)
- Vector search + context injection
- Chat/SearchLog persistence
- Env-based provider switching
- **PostgreSQL** as the primary DB (SQLite kept as dev fallback)
- **Healthcheck endpoints** `/api/v1/triple/health/` (liveness) and `/health/ready/` (DB+Redis+provider readiness)
- **Session expiry alignment** — Redis TTL and DB `User.expired_datetime` share a single `SESSION_TIMEOUT` window via `refresh_user_session()`
- **Retrieval A/B harness** + 12-question eval set under [Rag_Chat/backend/chat/tests/evals/](Rag_Chat/backend/chat/tests/evals/)
- **GitHub Actions CI** — lint, Postgres+Redis integration tests, chunk A/B report as workflow artifact, backend+frontend Docker build
- **Role-based User** (USER/MANAGER/ADMIN) + department FK on `chat.User`
- **Knowledge base** — `Department`/`Contact`/`Product` models + `/api/v1/knowledge/products/`, `/contacts/`, `/departments/` 검색 API + Django Admin CRUD
- **Forbidden-word moderation** — multi-stage filter (BLOCK / MASK / WARN) hooked into chat pipeline both inbound and outbound; Django Admin `/admin/moderation/` 검수 페이지로 운영자가 단어 등록·로그 검수
- **Audit logging** — `AuditLogMiddleware`가 모든 API 호출 기록 (action/path/status/user/ip)
- **Security posture** — DEBUG=0에서 default SECRET_KEY 거부, CORS allowlist env-driven
- Run scripts: `run_local_fixed.sh`, Docker Compose

## 7) Known Limits
- JWT는 의존성에 있지만 endpoint protection 미적용 (Phase 1 예정)
- Single node; no HA/auto-scale
- Minimal streaming/concurrency
- Production chunk_size still 1000; eval suggests 150 — pending controlled rollout
- 외부 LLM(Gemini/Qwen) 의존 — 대외비 등급 상향 시 로컬 LLM 전환 필요 ([security.md](Rag_Chat/backend/docs/security.md) §4 참조)

## 8) How to Run

### Docker (recommended — full stack: Postgres + Redis + Backend + Celery + Frontend)
```bash
cd Rag_Chat
cp .env.example .env   # fill in GOOGLE_API_KEY at minimum
docker-compose up --build
# UI:        http://localhost:8501
# API:       http://localhost:8000
# Liveness:  http://localhost:8000/api/v1/triple/health/
# Readiness: http://localhost:8000/api/v1/triple/health/ready/
```

### Local dev script
```bash
chmod +x Rag_Chat/run_local_fixed.sh
cd Rag_Chat && ./run_local_fixed.sh    # SQLite fallback
```

### Retrieval A/B (no API key needed — uses BM25)
```bash
cd Rag_Chat/backend
./venv/bin/python -m chat.tests.evals.run_chunk_ab \
    --sizes 80,150,250,500,1000 \
    --overlaps 0,30,80,150 \
    --k 5
```

## 8.1) Demo Scenarios (영업팀 use case)

영업팀이 "Galaxy S25 라인업의 카메라/가격/스토리지"를 물어본다고 가정한 12개 질문이 [`dataset.jsonl`](Rag_Chat/backend/chat/tests/evals/dataset.jsonl)에 있습니다. 데모 시연 흐름:

1. `docker-compose up` → 챗봇 UI 띄우기 (http://localhost:8501)
2. 다음 같은 질문을 차례로 입력:
   - "갤럭시 S25 기본형 팬텀 블랙 256GB 가격이 얼마인가요?" → 1199.99 답변 + 행 소스
   - "S25 Ultra 페리스코프 카메라 스펙은?" → 10MP Periscope + 200MP Main 컨텍스트
   - "16GB RAM 가지는 모델 모두 알려주세요" → 다행(多行) 검색
3. 응답마다 Django Admin (또는 `/api/v1/triple/search-logs/`)에서 SearchLog row 확인 — 어느 RagData가 답변 근거였는지 추적 가능

## 9) Logs & Governance
- Each question writes Chat + SearchLog; session in Redis; history in SQLite.
- Enables review of question → context → answer for audits.

## 10) Documentation Map
- [Rag_Chat/backend/docs/security.md](Rag_Chat/backend/docs/security.md) — 대외비 대응 위협 모델 + 다층 방어 + 로컬 LLM 전환 경로
- [Rag_Chat/backend/docs/chunk_experiment.md](Rag_Chat/backend/docs/chunk_experiment.md) — chunk_size/overlap A/B 실험 결과 (자소서 "chunk 실험" 근거)
- [Rag_Chat/backend/docs/provider_architecture.md](Rag_Chat/backend/docs/provider_architecture.md)
- [Rag_Chat/backend/docs/provider_refactor_overview.md](Rag_Chat/backend/docs/provider_refactor_overview.md)
- [Rag_Chat/backend/docs/provider_release_notes.md](Rag_Chat/backend/docs/provider_release_notes.md)
- [Rag_Chat/frontend/frontnedREADME.md](Rag_Chat/frontend/frontnedREADME.md)
- [Rag_Chat/run_local_script_fixes.md](Rag_Chat/run_local_script_fixes.md)
- [Rag_Chat/프로젝트현황.md](Rag_Chat/프로젝트현황.md)
- [.github/workflows/ci.yml](.github/workflows/ci.yml) — CI pipeline
- [Rag_Chat/.env.example](Rag_Chat/.env.example) — environment template

## 11) Design Philosophy
Prioritize deployability, traceability, and reliability over raw model scores or UI polish.
