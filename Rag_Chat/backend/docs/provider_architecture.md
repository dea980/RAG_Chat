# Provider Architecture (LLM / Embedding / VectorStore)
Abstraction that lets us swap Embedding / Reasoning / Generation via config, not code. Built so the system can migrate from external LLMs (Gemini/Qwen) to a self-hosted backend (Ollama/vLLM) without touching the chat pipeline — critical for handling 대외비 data.

## 1) Why
- Reduce vendor lock-in (Gemini ↔ Qwen via OpenAI-compatible endpoint).
- Change models by env vars or a toggle API, reuse one manager across RAG utils, API views, and indexing.
- **Pave the path** to fully self-hosted inference (Ollama → vLLM) without rewriting `chat/views.py`.

## 2) Components
```
backend/chat/providers/
├─ base.py      # interfaces
├─ gemini.py    # Gemini impl
├─ qwen.py      # Qwen impl (experimental, OpenAI-compatible)
└─ manager.py   # selection + cache
```

### ProviderManager (`backend/chat/providers/manager.py`)
- Returns embedding model, reasoning model, generation model, vector-store factory (Chroma/FAISS).
- Selection: primarily environment variables; toggle API can override.
- Output of every Reasoning/Generation call is run through `moderation.filter` before/after it leaves the process — provider implementations stay agnostic to policy.

### Embedding
- Default: Gemini `models/text-embedding-004`.
- Extensible: add `_create_*_embeddings()`; Qwen embedding not implemented yet.
- Self-hosted future: `sentence-transformers` or `bge-large-ko` via local server.

### Chat Providers (Reasoning / Generation)
- Supports 2-step chain: Reasoning → Generation.
- Implementations:
  - Gemini: `ChatGoogleGenerativeAI` (LangChain)
  - Qwen: `ChatOpenAI` (requires OpenAI-compatible endpoint)
  - Ollama (future): same `ChatOpenAI` pattern pointed at `http://ollama:11434/v1`.

## 3) Where It's Used
| Location | Role |
| --- | --- |
| `chat/utils.py` | `RAGUtils.get_vector_store()`, `create_vector_store_from_documents()` |
| `chat/views.py` | Reasoning → Generation chain during Q&A, sandwiched between inbound/outbound moderation |
| `chat/build_vector_store.py`, `chat/management/commands/build_vectors.py` | Embedding / vector store creation for indexing |
| `chat/tests/evals/run_chunk_ab.py` | Chunk size sweep — uses BM25 so the harness runs without an external LLM call |

## 4) Runtime Flow (provider view)
1) ProviderManager reads current config (env/toggle).
2) **INBOUND moderation** masks/blocks before retrieve.
3) Vector store fetches similar docs.
4) (Optional) reasoning model produces rationale/summary.
5) Generation model produces final answer.
6) **OUTBOUND moderation** runs over the answer.
7) Chat/SearchLog/ModerationLog/AuditLog record question, search, answer, hits, request.

## 5) Config Examples
```env
# Gemini only
GOOGLE_API_KEY=your-gemini-key
EMBEDDING_PROVIDER=gemini
REASONING_PROVIDER=gemini
GENERATION_PROVIDER=gemini

# Hybrid (Reasoning: Qwen, Generation: Gemini)
GOOGLE_API_KEY=your-gemini-key
QWEN_API_KEY=your-qwen-key
QWEN_API_BASE=https://api-inference.yourdomain/v1
REASONING_PROVIDER=qwen
GENERATION_PROVIDER=gemini

# Future: fully self-hosted (Ollama)
OLLAMA_BASE=http://ollama:11434/v1
REASONING_PROVIDER=ollama
GENERATION_PROVIDER=ollama
```

## 6) Notes / Constraints
- Qwen needs an OpenAI-compatible endpoint + API key.
- Two calls (Reasoning → Generation) can add latency.
- `run_local_fixed.sh` forwards the same env vars to Streamlit.

## 7) Closed Gaps (이전 문서에 'Known Gaps'로 기록되어 있던 항목 중)
- ✅ Forbidden-term filter — `moderation` 앱으로 구현, INBOUND/OUTBOUND 양방향.
- ✅ Health checks — `/api/v1/triple/health/`, `/health/ready/` (DB + Redis + provider).
- ✅ Redis vs DB session/expiry alignment — `refresh_user_session()` 단일 윈도우.
- ✅ RBAC 데이터 모델 — `chat.User.role` (USER/MANAGER/ADMIN) + department FK.
- ⏳ JWT endpoint protection — 모델은 있음, 권한 데코레이터는 Phase 1.

## 8) Open Gaps
- 외부 LLM 의존 — Stage 2 Ollama PoC, Stage 3 vLLM 전환 계획.
- Provider 장애 fallback chain 미구현 — Gemini → Qwen → Ollama 순환 fallback 예정.
- Reranker 미구현 — bge-reranker / Cohere 플러그 포인트만 둠.

## 9) Related Docs
- `provider_refactor_overview.md` — background/changes
- `provider_release_notes.md` — change log
- `../../ArchitectReadme.md` — full system architecture
- `security.md` §4 — 로컬 LLM 전환 절차 (Ollama / vLLM)
- `chunk_experiment.md` — retrieval 정확도 검증
