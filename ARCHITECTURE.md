# Triple Chat — Architecture

> Engineer-facing system map. Recruiters: see [README.md](./README.md).
> Concept deep-dives: [Rag_Chat/docs/concepts/](./Rag_Chat/docs/concepts/).
> 학습 narrative · 진행 노트: [Rag_Chat/backend/docs/_index.md](./Rag_Chat/backend/docs/_index.md).

---

## 1. System Map

```
┌────────────────────────────────────────────────────────────────────────┐
│  Streamlit (frontend/app.py + pages/{chunk_lab,token_lab,embedding_lab})│
│  – chat with citation chip ribbon                                       │
│  – /admin/moderation 운영자 튜닝 UI                                      │
└────────────────────────────┬───────────────────────────────────────────┘
                             │  REST + session cookie
                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Django + DRF (backend/)                                                │
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────────────────────────┐│
│  │ Auth + Persona ACL   │  │ Retrieval Pipeline                       ││
│  │ chat/persona.py      │  │ chat/pipeline/{base,modules,runner}.py   ││
│  │ chat/models.py:User  │  │   ① dense vector search (pgvector)       ││
│  │ (USER/MANAGER/ADMIN  │  │   ② ONNX cross-encoder rerank            ││
│  │  + department FK     │  │      chat/rerankers/onnx_bge.py          ││
│  │  + persona)          │  │   ③ persona ACL filter (drop / mask)     ││
│  └──────────────────────┘  └──────────────────────────────────────────┘│
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────────────────────────┐│
│  │ Moderation           │  │ Ingest                                   ││
│  │ moderation/          │  │ chat/ingest/{loaders,splitters,sinks,    ││
│  │  – 4 boundaries      │  │   manifest}.py                           ││
│  │  – BLOCK/MASK/WARN   │  │   – plugin registry (@register)          ││
│  │  – KW + regex label  │  │   – SHA256 dedup → IngestManifest        ││
│  └──────────────────────┘  └──────────────────────────────────────────┘│
│                                                                         │
│  ┌──────────────────────┐  ┌──────────────────────────────────────────┐│
│  │ Audit                │  │ Provider Manager (env-swap)              ││
│  │ audit/middleware.py  │  │ chat/providers/manager.py                ││
│  │  – every API row     │  │   Gemini · Qwen · OpenRouter · Ollama ·  ││
│  └──────────────────────┘  │   HuggingFace                            ││
│                            └──────────────────────────────────────────┘│
└────────────────┬────────────────┬───────────────────────┬───────────────┘
                 ▼                ▼                       ▼
        Postgres 16          Redis 7              Celery worker + beat
        (+ pgvector)         (session, broker)    (vector build, cleanup)
```

Data flows top → bottom. ACL · moderation · audit each see every request.

---

## 2. Layers

| Layer | Path | Responsibility |
|---|---|---|
| **Ingest** | `backend/chat/ingest/` | file → `RawDoc` → splitter → sink. Plugin registry, SHA256 dedup, deterministic chunk id. 4 분류 (text · OCR · structured · 전용) |
| **Retrieval** | `backend/chat/pipeline/`, `chat/rerankers/onnx_bge.py` | dense top-N → cross-encoder rerank → top-K. `RERANKER_ENABLED=0` 으로 끔 |
| **Persona ACL** | `backend/chat/persona.py` + `chat/models.py:User.persona` | namespace × role × confidentiality label. retrieval 후 chunk drop/mask, citation 에 `[수정됨·N건]` 가시화 |
| **Moderation** | `backend/moderation/` | 4 경계 (업로드·질문·검색·답변) 라벨 기반 필터. KW + regex pattern type. severity BLOCK/MASK/WARN. 운영자 Admin UI |
| **Audit** | `backend/audit/middleware.py` | 모든 API 호출 (user · path · status · ip) 한 줄 |
| **Providers** | `backend/chat/providers/manager.py` | embedding · reasoning · generation 역할별 env 분리. 5 vendor |
| **Async** | Celery worker + beat | 세션 정리, vector build. RPC 동기 path 는 멱등 유지 |

---

## 3. Key Decisions

| Decision | Why | Tradeoff | Considered |
|---|---|---|---|
| Postgres + pgvector (vs FAISS / dedicated VDB) | single store · txn · SQL-side ACL | < dedicated VDB throughput @ 10M+ vectors | FAISS (legacy), Chroma, Pinecone |
| ONNX `bge-reranker-v2-m3` (local) | API cost 0, sub-100ms, offline 가능 | first-run 568MB 캐시, +50ms latency | Cohere Rerank API, none |
| Label-based moderation (vs regex-only) | 운영자 코드 없이 튜닝, audit 가능, KW+RE 둘 다 | hard match 필요한 경우 regex 패턴 직접 작성 | Pure regex, 외부 SaaS (Fasoo) |
| 4 경계 (업로드·질문·검색·답변) 동일 스키마 | incident 사후 추적 비용 ↓, 무성 드롭 금지 | 운영자 학습 곡선 | 단일 진입점 필터 |
| 5-provider env-swap | dev · 비용 · 대외비 등급별 유연성 | provider abstraction tax (`role` × `vendor` matrix) | vendor lock-in |
| Streamlit (vs Next.js) | 1-dev velocity, design tokens 공유, 백엔드 가까움 | streaming UX · mobile · 디자인 자유도 | Next.js 14 (Phase later) |
| Conversation thread (vs flat Chat) | sales 시나리오 후속 질문, persona 별 history | 모델 마이그레이션 비용 | flat Chat (legacy) |
| Labeled eval dataset (vs anecdotal) | Recall@K · MRR 로 모델·청크 결정 근거 | 정답 라벨링 비용 (영업 12 문항 → 확장 필요) | 5쌍 SEMANTIC_PAIRS (legacy) |

---

## 4. Data Model

```
User ── persona ──┐
│                 ▼
│         Conversation ── ConversationMessage
│
├── Chat ── SearchLog ── RagData
│
├── ModerationRule ── ForbiddenWord ── ModerationLog
│
├── AuditLog (middleware)
│
└── IngestManifest (SHA256 → chunk ids)
```

핵심 :

- `User` — `role` ∈ {USER, MANAGER, ADMIN}, `department` FK, `persona` (영업 / 지원 / 기획)
- `Chat`, `SearchLog`, `RagData` — Q→context→A 재현 가능 (traceability)
- `Conversation` + `ConversationMessage` — thread 단위, persona 컨텍스트 유지
- `ModerationRule` (category × pattern_type ∈ {KW, RE} × scope ⊆ 4경계 × severity) + `ForbiddenWord` (legacy) + `ModerationLog`
- `IngestManifest` — file SHA256, status, chunk count. 같은 파일 재실행 시 자동 skip / 옛 청크 제거

상세 ER: `backend/chat/models.py`, `backend/moderation/models.py`, `backend/knowledge/models.py`.

---

## 5. Request Lifecycle (chat send)

```
1. POST /api/v1/triple/chat/        Session cookie
2. IsAuthenticated                  401 if anonymous
3. AuditLogMiddleware:in            audit row (path·user·ts)
4. Moderation:INBOUND               question 검사 → BLOCK | MASK | pass
5. Persona context build            persona + role + dept → ACL filter
6. Retrieval                        ① pgvector dense top-N
                                    ② ONNX rerank → top-K
                                    ③ ACL drop/mask (citation [수정됨·N건])
7. Moderation:SEARCH                retrieved chunk 검사
8. Provider call                    embeddings + generation (env-resolved)
9. Moderation:OUTBOUND              LLM 응답 검사
10. Persist                         Chat · SearchLog · ConversationMessage
11. AuditLogMiddleware:out          status·latency
12. Response                        answer + citation ribbon + redacted hint
```

step 4, 7, 9 모두 동일 `ModerationLog` 스키마 (who · when · what · rule · result). 모더레이션 무성 드롭 금지 — citation 에 `[수정됨·N건]` 표기.

---

## 6. Concept Pointers

| Concept | Doc |
|---|---|
| Hybrid Search (BM25 + 벡터, RRF) | [docs/concepts/hybrid-search.md](./Rag_Chat/docs/concepts/hybrid-search.md) |
| Reranker (cross-encoder, ONNX) | [docs/concepts/reranker.md](./Rag_Chat/docs/concepts/reranker.md) |
| Persona ACL (namespace × role) | [docs/concepts/persona-acl.md](./Rag_Chat/docs/concepts/persona-acl.md) |
| 4-boundary Moderation | [docs/concepts/moderation-4boundary.md](./Rag_Chat/docs/concepts/moderation-4boundary.md) |
| Embedding Eval Harness | [docs/concepts/embedding-eval.md](./Rag_Chat/docs/concepts/embedding-eval.md) |
| IR Metrics (Recall@K · MRR · nDCG) | [docs/concepts/ir-metrics.md](./Rag_Chat/docs/concepts/ir-metrics.md) |

운영 narrative · phase 진행 · 세션 핸드오프 → [backend/docs/_index.md](./Rag_Chat/backend/docs/_index.md).
보안 위협 모델 · 로컬 LLM 전환 경로 → [backend/docs/architecture/security.md](./Rag_Chat/backend/docs/architecture/security.md).
시각·UI 단일 출처 → [DESIGN.md](./DESIGN.md).

---

## 7. Known Limits

- JWT 의존성만 추가, endpoint protection 은 세션 cookie 기반 (Phase 1 작업)
- Single node — HA / auto-scale 없음
- 외부 LLM 의존 (대외비 등급 ↑ 시 Ollama / vLLM 전환 필요 — `security.md` §4)
- Production chunk_size 1000, eval 은 150 권장 → controlled rollout 대기
- Streaming response 미지원
