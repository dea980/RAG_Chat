# Provider Refactor Overview
Summary of structure changes around the provider abstraction, and how it now fits in with the new moderation / knowledge / audit layers.

## Changes (cumulative)
- **ProviderManager**: select embedding/reasoning/generation via env; default Gemini, Qwen combo experimental.
- **Vector store cleanup**: `RAGUtils`, `build_vector_store.py`, `management/commands/build_vectors.py` create embeddings through ProviderManager.
- **Reasoning → Generation chain**: `chat/views.py` feeds reasoning output into the generation prompt.
- **Env alignment**: `Rag_Chat/.env.example` (root) is now the single template — propagated to backend container via docker-compose.
- **Session provider toggle**: `/api/v1/triple/providers/` GET/POST applies presets (gemini_only, qwen_reasoning_gemini_generation, qwen_only); Streamlit sidebar calls it.
- **Moderation wrap (new)**: every reasoning/generation call is sandwiched between INBOUND and OUTBOUND `moderation.filter` calls so providers stay agnostic to policy. Sanitized text is what actually leaves the process.
- **Audit (new)**: provider responses are recorded indirectly via `Chat.response_text` (post-moderation) and `AuditLog`.

## Considerations
- `GOOGLE_API_KEY` required; Qwen needs `QWEN_API_KEY`, `QWEN_API_BASE`.
- Sequential reasoning→generation can add latency; consider caching/async/streaming.
- Qwen local serving needs GPU; otherwise stay Gemini-only.
- Singleton cache may need reset in long-running processes.
- **Provider 호출은 모더레이션 layer 뒤에 있다** — 새 provider를 추가해도 policy 적용은 자동.

## Next Steps
1) Reranker plugin path (Cohere, bge-reranker, etc.) — chunk experiment 결과(150-sweet-spot) 검증 후
2) Provider health check with fallback chain: Gemini → Qwen → Ollama
3) CI matrix for provider-combo smoke tests
4) Streamlit advanced panel for custom combos
5) **Local LLM provider 추가** (Ollama) — `chat/providers/ollama.py`, env: `OLLAMA_BASE`, `OLLAMA_MODEL`. 마이그레이션 절차는 [security.md §4](security.md#4-로컬-llm-전환-경로) 참조.

See `provider_architecture.md` for structure details, `provider_release_notes.md` for change log.
