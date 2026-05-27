# Provider Release Notes

## 2026-05-18 — Production-readiness bundle

### Provider-adjacent changes
- Provider 호출 양옆에 **moderation filter (INBOUND/OUTBOUND)** 가 자동 적용됨. provider 구현은 정책 무관.
- `provider_manager.{embedding,reasoning,generation}_provider_name` 속성이 `/health/ready/`에 노출되어 운영자가 현재 구성 확인 가능.
- Settings 로드 시 `GOOGLE_API_KEY` 빈 값이어도 부팅은 가능 (CI 시나리오), 단 실제 호출에선 실패.

### 새로 도입된 의존성
- `psycopg2-binary>=2.9.9` (Postgres)
- `rank-bm25>=0.2.2` (retrieval A/B harness — provider 호출 없이 chunk 정책 검증)
- `django-cors-headers>=4.2.0` (CORS allowlist)

### 미해결
- Provider fallback chain 미구현 — Gemini 장애 시 Qwen 자동 전환 안 됨.
- Embedding은 Gemini만 — 자체 호스팅 embedding(sentence-transformers/bge) 미구현.

---

## 2026-02-03 — Initial provider abstraction
Version: 2026-02-03

### Summary
Provider stack updated to let Gemini/Qwen combos switch per session. Streamlit presets and the Django API share one endpoint.

### Changes
1. **ProviderManager**
   - Combines env + session override to pick reasoning/generation.
   - Cache key `(provider, purpose)` to reuse model instances.
2. **Session Provider API** `/api/v1/triple/providers/`
   - GET: current session selection
   - POST: presets (`gemini_only`, `qwen_reasoning_gemini_generation`, `qwen_only`) or custom combo
   - DELETE: remove override
3. **Streamlit UI**
   - Sidebar preset selector, shows applied JSON, updates session immediately.
4. **Vector store / indexing**
   - `RAGUtils`, `build_vector_store.py`, `management/commands/build_vectors.py` create embeddings through ProviderManager.
   - Paths based on `settings.BASE_DIR` to reduce cwd issues.
5. **Docs/env template**
   - `backend/.env` includes Gemini/Qwen keys; related docs refreshed.

### Considerations
- `GOOGLE_API_KEY` required; Qwen uses `QWEN_API_KEY`, `QWEN_API_BASE`.
- Overrides live in cache with TTL (`PROVIDER_OVERRIDE_TTL`, default 1800s); fall back afterward.
- Reasoning→Generation is sequential; consider caching/async/streaming for latency.
- Streamlit presets are simple; complex mixes need direct API calls.

### Next
1) Add reranker plugin option
2) Health checks with fallback to defaults
3) CI matrix for provider combos
4) Streamlit advanced panel for custom combos
