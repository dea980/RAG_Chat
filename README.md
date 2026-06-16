# Triple Chat — Internal RAG Q&A

> 영업·지원팀이 제품 스펙·정책·매뉴얼을 자연어로 묻고, **출처와 함께** 답변받는 사내 RAG 챗봇.

Django + DRF · Streamlit · Postgres+pgvector · Redis · Celery · ONNX `bge-reranker-v2-m3` · 5 LLM providers (env-swap)

[**Architecture**](./ARCHITECTURE.md) · [**Concept docs**](./Rag_Chat/docs/concepts/) · [**Design system**](./DESIGN.md) · [**Backend docs index**](./Rag_Chat/backend/docs/_index.md)

---

## What makes it different

1. **출처가 본문이다** — 답변 바로 아래 amber `#E89B3C` **citation chip ribbon**. 푸터·툴팁에 숨기지 않는다. 답을 의심하는 순간 한 클릭으로 원 chunk 까지 추적.
2. **운영자가 코드 없이 튜닝하는 4경계 모더레이션** — **업로드 · 질문 · 검색 · 답변** 동일 스키마 필터. `/admin/moderation/` UI 에서 카테고리 · regex/keyword · severity · 적용 경계 체크박스 + **실시간 테스트 패널**. 무성 드롭 금지 — 차단된 chunk 는 `[수정됨·1건]` 으로 가시화.
3. **검색 품질을 숫자로 입증** — 영업팀 시나리오 12 문항 + labeled embedding eval dataset → **Recall@K · MRR · nDCG** harness. chunk_size 결정 ("1000 → 150 으로 recall@5 0.789 → 0.833"), reranker 도입, persona ACL 결정 모두 anecdote 아니라 metric.

추가 결정 근거 · tradeoff 표 → [ARCHITECTURE.md §3](./ARCHITECTURE.md#3-key-decisions).

---

## Quick Start

```bash
# 1) clone
git clone <repo>; cd RAG_Chat

# 2) .env (Rag_Chat/.env, gitignored)
#    GOOGLE_API_KEY 또는 OPENROUTER_API_KEY 1개 이상 필요
cat > Rag_Chat/.env <<'EOF'
PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
EOF

# 3) full stack (Postgres + Redis + Backend + Celery + Streamlit)
cd Rag_Chat && docker-compose up --build

# 4) open
# UI         http://localhost:8501
# API        http://localhost:8000
# Readiness  http://localhost:8000/api/v1/triple/health/ready/
# Admin      http://localhost:8000/admin/   (moderation 운영자 UI 포함)
```

로컬 SQLite fallback (LLM 만 필요):
```bash
cd Rag_Chat && ./run_local_fixed.sh
```

평가 (no API key, BM25 backend):
```bash
cd Rag_Chat/backend
./venv/bin/python -m chat.tests.evals.run_chunk_ab \
    --sizes 80,150,250,500,1000 --overlaps 0,30,80,150 --k 5
```

---

## Architecture (1-line)

```
Streamlit ─→ Django REST ─→ {Auth, Persona ACL, Retrieval (dense → rerank → ACL), Moderation×4, Audit}
                                                          │
                                       Postgres(pgvector) · Redis · Celery
                                                          │
                                              5 LLM providers (env-swap)
```

전체 system map · layers · decisions · request lifecycle → [**ARCHITECTURE.md**](./ARCHITECTURE.md).

---

## Tech deep-dive

학습 가능한 개념 카드 (정의 + 비유 + 우리 시스템 적용 + 측정 방법 + FAQ):

| Concept | What |
|---|---|
| [Hybrid Search](./Rag_Chat/docs/concepts/hybrid-search.md) | Dense + BM25 RRF — 고유명사·동의어 둘 다 잡기 |
| [Reranker](./Rag_Chat/docs/concepts/reranker.md) | Cross-encoder 로 top-N 재정렬. 왜 ONNX `bge-reranker-v2-m3` |
| [Persona ACL](./Rag_Chat/docs/concepts/persona-acl.md) | namespace × role × confidentiality label. retrieval-side filter |
| [4-boundary Moderation](./Rag_Chat/docs/concepts/moderation-4boundary.md) | 업로드·질문·검색·답변 동일 스키마 + 운영자 튜닝 |
| [Embedding Eval Harness](./Rag_Chat/docs/concepts/embedding-eval.md) | Labeled YAML dataset → metric 으로 모델 결정 |
| [IR Metrics](./Rag_Chat/docs/concepts/ir-metrics.md) | Recall@K · MRR · nDCG · p95 latency 정의·해석 |

운영 narrative · phase 진행 · 학습 노트 → [backend/docs/_index.md](./Rag_Chat/backend/docs/_index.md).

---

## Status

**Implemented**
- Session-based RAG chat (Streamlit + Django) with **citation chip ribbon**
- **Conversation thread** model (persona 별 history)
- **Persona ACL** — namespace × role × confidentiality, retrieval-side drop/mask, `[수정됨·N건]` 가시화
- **ONNX reranker** (`BAAI/bge-reranker-v2-m3`, `RERANKER_ENABLED=0` 으로 끔)
- **4-boundary Moderation** — KW + regex pattern type, severity BLOCK/MASK/WARN, 운영자 Admin + 실시간 테스트 패널
- **Embedding eval harness** — labeled YAML dataset → Recall@K · MRR
- **5-provider env-swap** (Gemini · Qwen · OpenRouter · Ollama · HuggingFace)
- **pgvector** 마이그레이션 (FAISS legacy fallback 유지)
- **Postgres 16** primary (SQLite dev fallback)
- **Audit middleware** — 모든 API 호출 row
- **GitHub Actions CI** — lint · Postgres+Redis 통합 테스트 · chunk A/B artifact · Docker build
- **Ingest plugin layer** — `@register` 1줄로 새 포맷, SHA256 dedup
- **Lab pages** — Chunk Lab · Token Lab · Embedding Lab

**Known limits** → [ARCHITECTURE.md §7](./ARCHITECTURE.md#7-known-limits)

---

## Design philosophy

Deployability · traceability · reliability **>** raw model score · UI polish.

UI 결정의 단일 출처는 [DESIGN.md](./DESIGN.md) — Quiet Utilitarian, Pretendard + Geist Mono, 액센트 amber `#E89B3C`. citation ribbon · `[수정됨·N건]` · warning border 가 시그니쳐.
