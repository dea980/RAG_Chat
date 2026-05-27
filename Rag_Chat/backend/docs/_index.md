# Backend Docs — Index

> `backend/docs/` 의 모든 문서를 프로젝트 narrative 에 매핑한 인덱스.
> 여러 agent (Claude Code / Codex / 별도 Claude) 가 같은 프로젝트에서
> 작업할 때 맥락이 흩어지지 않도록 정리.
>
> **🗺 한 페이지 요약: [project_journey.html](project_journey.html)** —
> Phase 1 ~ Phase 3 통합까지의 전체 흐름을 시각적으로.
>
> **최근 갱신: 2026-05-27** · Phase 3 Text Loaders + Dispatch 통합 완료 · `.env` 통합.
>
> 👉 **다음 세션 진입점: [session_handoff.md](session_handoff.md)** — provider/env 현재 상태와 적용 방법.

---

## 1. 프로젝트 narrative — 어디까지 왔나

| Phase | 상태 | 주제 |
|---|---|---|
| 0 | ✅ 기존 | Django + DRF + Celery + Streamlit + Chroma 기본 스택 |
| 0+ | ✅ 기존 | 챗 RAG 파이프라인, 세션, search log, knowledge ORM, moderation |
| 1 | ✅ 완료 | Ingest layer skeleton — `chat/ingest/` 패키지, loader/splitter/sink 추상 |
| 2 | ✅ 완료 | Manifest + SHA256 dedup — 중복 적재 차단, 멱등 ingest |
| 2+ | ✅ 완료 | Chunk Lab 페이지 — splitter 결과 비교 |
| 2+ | ✅ 완료 | Token Lab 페이지 — 모델/언어별 토큰화 비교 |
| 2+ | ✅ 통합 완료 | Upload API — `pipeline.ingest_path` 경유로 manifest dedup 적용 ([ingest_upload_api.md](ingest_upload_api.md), [ingest_phase3_integration.md](ingest_phase3_integration.md)) |
| 3 | ✅ 완료 | 텍스트 loader (PDF/DOCX/HTML/TXT) + splitter dispatch 통합 ([ingest_phase3_text_loaders.md](ingest_phase3_text_loaders.md), [ingest_phase3_integration.md](ingest_phase3_integration.md)) |
| 4 | ⏳ | Clause/heading splitter (사규/법규 조항 단위) — Codex 분담 |
| 5 | ⏳ | OCR loader (분류 2) — 다른 Claude 리서치 후 |
| 6 | ⏳ | ORM sink (knowledge_product 로 분류 3 이전) — Claude Code |
| 7 | ⏳ | HWP / CAD (분류 4) — 변환 단계 별도 |
| 8 | ⏸️ 보류 | Upload API + Celery 비동기 (트리거 발생 시) |

---

## 2. 카테고리별 문서 지도

### 2.1 Ingest Layer (분류 1~4 데이터 수집·정규화)

| 문서 | 역할 | 상태 |
|---|---|---|
| [ingest_layer.md](ingest_layer.md) | 전체 설계 — 4분류, 인터페이스, 단계 계획 | Phase 1/2 반영 완료 |
| [ingest_phase1_skeleton.md](ingest_phase1_skeleton.md) | Phase 1 (skeleton) 작업 기록 + 학습 메모 | 완료 기록 |
| [ingest_phase2_manifest.md](ingest_phase2_manifest.md) | Phase 2 (manifest/dedup) 작업 기록 | 완료 기록 |
| [ingest_upload_api.md](ingest_upload_api.md) | Upload API 통합 기록 (이슈는 [phase3_integration](ingest_phase3_integration.md) 에서 해결) | 참고 |
| [ingest_phase3_text_loaders.md](ingest_phase3_text_loaders.md) | PDF/DOCX/HTML loader 통합 기록 (이슈는 [phase3_integration](ingest_phase3_integration.md) 에서 해결) | 참고 |
| [ingest_phase3_integration.md](ingest_phase3_integration.md) | **splitter dispatch + Upload manifest 통합 PR 기록** | 완료 |
| [work_distribution.md](work_distribution.md) | Claude Code / Codex / 다른 Claude 분담 매트릭스 | Phase 3+ 진행 기준 |

### 2.2 Lab 페이지 (학습·실험 도구)

| 문서 | 역할 | 페이지 위치 |
|---|---|---|
| [chunk_testing_page.md](chunk_testing_page.md) | chunking 테스트 페이지 **설계** | (설계 단계) |
| [chunk_lab_page.md](chunk_lab_page.md) | chunking 테스트 페이지 **구현 기록** | `frontend/pages/chunk_lab.py` |
| [token_lab_page.md](token_lab_page.md) | 토큰 비교 페이지 **구현 기록** + 일관성 노트 | `frontend/pages/token_lab.py` |
| [chunk_experiment.md](chunk_experiment.md) | 청크 사이즈 A/B 회귀 측정 (CLI 도구) | `chat/tests/evals/run_chunk_ab.py` |

### 2.2+ 학습 지도

| 문서 | 역할 |
|---|---|
| [core_concepts.md](core_concepts.md) | 이 프로젝트로 익혀야 할 개념 — 강의 6강/7강 + 시스템 개념 + 다음 8강 미리보기 + 우선순위 |

### 2.3 Provider / 임베딩 / LLM

| 문서 | 역할 |
|---|---|
| [provider_architecture.md](provider_architecture.md) | Gemini/Qwen/OpenRouter provider 추상 |
| [provider_refactor_overview.md](provider_refactor_overview.md) | provider manager 리팩토링 배경 |
| [provider_release_notes.md](provider_release_notes.md) | provider 변경 이력 |
| [openrouter_evaluation.md](openrouter_evaluation.md) | OpenRouter 도입 평가 |

### 2.4 비동기·성능·캐시 (보류된 설계)

| 문서 | 역할 | 상태 |
|---|---|---|
| [async_ingest_plan.md](async_ingest_plan.md) | Celery + Redis 인제스천 비동기 설계 | **Phase 8 보류** |
| [async_ingest_tradeoff.html](async_ingest_tradeoff.html) | 인제스천 부하 분리 vs LLM 컨텍스트 캐시 장단점 | 결론 = "지금 둘 다 불필요" |

### 2.5 보안·운영

| 문서 | 역할 |
|---|---|
| [security.md](security.md) | 사내 기밀 위협 모델 + 로컬 LLM 전환 경로 |

---

## 3. 코드와 문서의 매핑

```
backend/chat/
├── ingest/                            ← ingest_layer.md, ingest_phase1/2_*.md
│   ├── base.py                        ← Protocol 정의
│   ├── registry.py                    ← @register 패턴
│   ├── pipeline.py                    ← ingest_path() 진입
│   ├── manifest.py                    ← Phase 2 dedup
│   ├── loaders/structured/{csv,excel}.py
│   ├── loaders/text/{txt}.py          ← Phase 3 시작점
│   ├── splitters/{recursive,row}.py
│   └── sinks/chroma.py                ← 결정론적 chunk id
├── ingest_views.py                    ← chunk_lab_page.md (preview API)
├── token_views.py                     ← token_lab_page.md
├── token_utils.py                     ← token_lab_page.md
├── providers/                         ← provider_*.md
├── models.py                          ← IngestManifest 등
└── tests/evals/run_chunk_ab.py        ← chunk_experiment.md
```

```
frontend/pages/
├── chunk_lab.py                       ← chunk_lab_page.md
└── token_lab.py                       ← token_lab_page.md
```

---

## 4. 새 문서 작성 가이드 (Claude Code 역할)

이 프로젝트는 **여러 agent (Claude Code, Codex, 다른 Claude 세션)** 가
병렬로 작업한다. Claude Code 의 역할은 **문서화와 맥락 일관성 유지**.

새 코드/모듈이 들어왔을 때 만들 문서:

1. **`<feature>_page.md` 또는 `<feature>_module.md`** — 무엇이 추가됐고
   기존 narrative 의 어느 자리에 들어가는가
2. **불일치 노트** — naming / response shape / env var 처리 등에서
   다른 모듈과 어긋난 부분 (수정 강요는 아님, 다음 PR 에서 참고)
3. **학습 메모** — 이 기능을 만들면서 알게 된 것 (강의·이슈 reference 포함)
4. **안 한 것** — 의도적으로 보류한 것 + 보류 사유

그리고 이 인덱스(`_index.md`) 의 카테고리 표에 줄 하나 추가.

---

## 5. 관련 외부 문서

루트 레벨 (`Rag_Chat/`):
- [README.md](../../README.md) — 프로젝트 외부 소개
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — 상위 아키텍처
- [프로젝트현황.md](../../프로젝트현황.md) — 진행 상황 한국어 정리

`docs/superpowers/` — gstack/superpowers 관련 도구 docs (이 인덱스 범위 밖)
