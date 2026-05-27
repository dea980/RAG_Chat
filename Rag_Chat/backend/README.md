# Backend README (English)
Backend = Django REST + Celery. Production-readiness pass — RBAC data model, multi-stage forbidden-word moderation, knowledge base, audit logging, Postgres, healthchecks.

## Role
- Receive questions, run vector search, call LLM, return answers, log every step.
- Run forbidden-word moderation **before and after** every LLM call.
- Manage Redis sessions and async tasks via Celery.
- Serve a deterministic search API for product/contact/department lookups.

## Components
- Django app `chat/` — RAG models, pipeline, views; LangChain providers, healthcheck.
- Django app `knowledge/` — `Department`, `Contact`, `Product` + search API + Admin.
- Django app `moderation/` — `ForbiddenWord`, `ModerationLog`, BLOCK/MASK/WARN filter + Admin (검수 페이지).
- Django app `audit/` — `AuditLog` + middleware that records every API call.
- Celery app `triple_chat_pjt/celery.py` (worker, beat).
- Provider abstraction `chat/providers/manager.py` (env-driven; default Gemini, Qwen experimental).
- Storage: **PostgreSQL 16** (SQLite kept as dev fallback), Redis sessions/cache, FAISS/Chroma vector store.

## Data Model (summary)
- `chat.User(user_id, uuid, email, role[USER|MANAGER|ADMIN], department→knowledge.Department, expired_datetime, last_activity)`
- `chat.Chat`, `chat.SearchLog`, `chat.RagData` (질문/검색/응답 trace)
- `knowledge.Department`, `knowledge.Contact`, `knowledge.Product`
- `moderation.ForbiddenWord(severity[BLOCK|MASK|WARNING], direction[INBOUND|OUTBOUND|BOTH])`, `moderation.ModerationLog`
- `audit.AuditLog(action, method, path, status_code, user, ip_address, ...)`

## Environment variables (single source: `Rag_Chat/.env`)

예전에 흩어져 있던 `backend/.env`, `internal-chat/.env`, root `.env` 템플릿 파일은 모두 폐기됐습니다. 환경변수 정의는 **이 inline 템플릿이 유일한 출처**입니다. 새 환경에서는 아래를 그대로 복사해 `Rag_Chat/.env` 로 저장하고 키를 채우세요. (`Rag_Chat/.env` 는 gitignored)

```ini
# ---- Django ----
DJANGO_SECRET_KEY=change-me-in-production
DEBUG=0
ALLOWED_HOSTS=localhost,127.0.0.1,backend
CORS_ALLOWED_ORIGINS=http://localhost:8501,http://localhost:3000

# ---- PostgreSQL ----
POSTGRES_DB=triple_chat
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# ---- Session (Redis TTL ↔ DB expired_datetime 단일 윈도우, 초) ----
SESSION_TIMEOUT=300

# ---- Provider 선택 ----
# Chat LLM provider는 역할별로 바꿀 수 있다.
# 지원: gemini, qwen, openrouter, ollama, huggingface
#
# Embedding provider/model은 별도 축이다. 변경하면 기존 Chroma index와
# embedding 차원이 달라질 수 있으므로 벡터 재생성이 필요하다.
EMBEDDING_PROVIDER=openrouter
EMBEDDING_MODEL=nvidia/llama-nemotron-embed-v1-1b-v2:free
REASONING_PROVIDER=openrouter
GENERATION_PROVIDER=openrouter

# ---- OpenRouter (권장: 단일 키, free-tier) ----
# 발급: https://openrouter.ai/settings/keys
OPENROUTER_API_KEY=
OPENROUTER_BASE=https://openrouter.ai/api/v1
OPENROUTER_EMBEDDING_MODEL=nvidia/llama-nemotron-embed-v1-1b-v2:free
OPENROUTER_MODEL_NAME=qwen/qwen3-235b-a22b:free
OPENROUTER_REASONING_MODEL=qwen/qwen3-235b-a22b:free
OPENROUTER_GENERATION_MODEL=nvidia/nemotron-nano-9b-v2:free

# ---- Ollama 로컬 endpoint ----
# ollama serve 후 provider=ollama 로 선택
# OLLAMA_BASE_URL=http://localhost:11434/v1
# OLLAMA_MODEL=llama3.1
# OLLAMA_REASONING_MODEL=llama3.1
# OLLAMA_GENERATION_MODEL=qwen2.5:7b

# ---- Hugging Face OpenAI-compatible endpoint ----
# Hugging Face Inference Endpoint 또는 TGI OpenAI-compatible endpoint 필요
# HUGGINGFACE_API_KEY=
# HUGGINGFACE_BASE_URL=
# HUGGINGFACE_MODEL=meta-llama/Llama-3.1-8B-Instruct
# HUGGINGFACE_REASONING_MODEL=
# HUGGINGFACE_GENERATION_MODEL=

# ---- Gemini (provider=gemini 일 때만; 백업) ----
# GOOGLE_API_KEY=
# GOOGLE_EMBEDDING_MODEL=models/text-embedding-004
# GOOGLE_CHAT_MODEL=gemini-1.5-flash

# ---- Qwen 직접 endpoint (OpenRouter 안 쓸 때만; 백업) ----
# QWEN_API_KEY=
# QWEN_API_BASE=
# QWEN_MODEL_NAME=qwen-plus
```

`settings.py` 가 부팅 시 `Rag_Chat/.env` 를 python-dotenv 로 자동 로드합니다. docker-compose 도 같은 파일을 자동 로드.

## Run

### Docker Compose (recommended — full stack)
```bash
cd Rag_Chat
# Rag_Chat/.env 를 위 템플릿대로 만든 뒤
docker-compose up --build
docker-compose exec backend python manage.py createsuperuser
```

### Local (backend only, SQLite fallback)
```bash
cd Rag_Chat/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
# new terminal
celery -A triple_chat_pjt worker --loglevel=info
```
Env: `GOOGLE_API_KEY` required; for Qwen also set `QWEN_API_KEY`, `QWEN_API_BASE`.

## Endpoints

### Chat (RAG)
- POST `/api/v1/triple/chat/` — question → answer (logged + moderated)
- POST `/api/v1/triple/chat-user/` — create / refresh session
- POST `/api/v1/triple/update-activity/` — extend session

### Knowledge (deterministic, no LLM)
- GET `/api/v1/knowledge/products/?q=&category=`
- GET `/api/v1/knowledge/contacts/?q=&department=`
- GET `/api/v1/knowledge/departments/`

### Health
- GET `/api/v1/triple/health/` — liveness
- GET `/api/v1/triple/health/ready/` — DB + Redis + provider readiness

### Admin (검수 페이지)
- `/admin/moderation/forbiddenword/` — 금지어 등록·정책 설정
- `/admin/moderation/moderationlog/` — 탐지 이력 검수 (`reviewed` 체크박스)
- `/admin/knowledge/` — Department / Contact / Product CRUD
- `/admin/audit/auditlog/` — API 감사 로그 (read-only)

## Retrieval evaluation
A/B harness in `chat/tests/evals/`:
```bash
./venv/bin/python -m chat.tests.evals.run_chunk_ab \
    --sizes 80,150,250,500,1000 --overlaps 0,30,80,150 --k 5
```
Eval set in `chat/tests/evals/dataset.jsonl` (영업팀 시나리오 12문항).

## Limits (current)
- JWT는 dependencies에 있지만 endpoint protection 미적용 (Phase 1 예정)
- Forbidden-word 매칭은 substring (단어 경계 정규식은 Phase 2)
- 외부 LLM(Gemini/Qwen) 의존 — 대외비 등급 상향 시 Ollama/vLLM 전환 ([docs/security.md §4](docs/security.md))
- Single-instance concurrency, no streaming, no HA

## Shortcut
`../run_local_fixed.sh` brings up Redis (docker) + Django + Celery + Streamlit together (SQLite dev mode).

## Related docs
- [docs/security.md](docs/security.md) — 위협 모델 + 다층 방어 + 로컬 LLM 경로
- [docs/chunk_experiment.md](docs/chunk_experiment.md) — chunk_size A/B 결과
- [docs/provider_architecture.md](docs/provider_architecture.md) — LLM provider 추상화
- [../prd.html](../prd.html) — 시스템 전체 PRD
