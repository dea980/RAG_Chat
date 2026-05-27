# Backend Docs — Index

> 모든 backend/프로젝트 문서를 그룹 + 상태 테이블로 정리한 인덱스.
> 여러 agent (Claude Code / Codex / 다른 Claude 세션) 가 같은 프로젝트에서
> 작업할 때 맥락이 흩어지지 않도록.
>
> 🗺 **한 페이지 시각 요약**: [reports/project_journey.html](reports/project_journey.html)
> 👉 **다음 세션 진입점**: [sessions/handoff.md](sessions/handoff.md) — env/provider 현재 상태 + 즉시 처리할 것
> 🔧 **커밋 분할 핸드오프**: [sessions/commit_split_plan.md](sessions/commit_split_plan.md)

상태 범례 — ✅ done · 🟢 active · ⏳ planned · ⏸ paused · 📝 reference

---

## 1. 진행 phase 한눈에

| Phase | 상태 | 주제 |
|---|---|---|
| 0 | ✅ | Django + DRF + Celery + Streamlit + Chroma 기본 스택 |
| 0+ | ✅ | 챗 RAG 파이프라인, 세션, search log, knowledge ORM, moderation |
| 1 | ✅ | Ingest layer skeleton — `chat/ingest/` 패키지, loader/splitter/sink 추상 |
| 2 | ✅ | Manifest + SHA256 dedup — 중복 적재 차단, 멱등 ingest |
| 2+ | ✅ | Chunk Lab + Token Lab 페이지 |
| 3 | ✅ | 텍스트 loader (PDF/DOCX/HTML/TXT) + splitter dispatch 통합 |
| 4 | ✅ | Clause/heading splitter (opt-in only) |
| 5 | ⏳ | OCR loader (분류 2) |
| 6 | ⏳ | ORM sink (knowledge_product 로 분류 3 이전) |
| 7 | ⏳ | HWP / CAD (분류 4) — 변환 단계 별도 |
| 8 | ⏸ | Upload API + Celery 비동기 (트리거 발생 시) |

---

## 2. 아키텍처 — [`architecture/`](architecture/)

| 문서 | 상태 | 역할 |
|---|---|---|
| [core_concepts.md](architecture/core_concepts.md) | 📝 | 강의 6/7강 + 시스템 개념 + 다음 8강 미리보기 + 우선순위 |
| [ingest_layer.md](architecture/ingest_layer.md) | ✅ | Ingest 전체 설계 — 4분류, 인터페이스, 단계 계획 |
| [security.md](architecture/security.md) | 📝 | 사내 기밀 위협 모델 + 로컬 LLM 전환 경로 |
| [architect_readme.md](architecture/architect_readme.md) | 📝 | 외부 아키텍트 인계용 readme |
| [architect_readme.html](architecture/architect_readme.html) | 📝 | architect_readme의 HTML 렌더 |

---

## 3. 기능별 — [`features/`](features/)

### 3.1 Ingest — [`features/ingest/`](features/ingest/)

| 문서 | 상태 | 역할 |
|---|---|---|
| [admin_upload_plan.md](features/ingest/admin_upload_plan.md) | ✅ | Admin upload UI + ingest endpoint 계획 (구현됨, `bc73020`) |
| [phase1_skeleton.md](features/ingest/phase1_skeleton.md) | ✅ | Phase 1 작업 기록 |
| [phase2_manifest.md](features/ingest/phase2_manifest.md) | ✅ | Phase 2 manifest/dedup |
| [phase3_text_loaders.md](features/ingest/phase3_text_loaders.md) | ✅ | PDF/DOCX/HTML loader 통합 |
| [phase3_integration.md](features/ingest/phase3_integration.md) | ✅ | splitter dispatch + Upload manifest 통합 PR |
| [phase4_splitters.md](features/ingest/phase4_splitters.md) | ✅ | Clause/Heading splitter (opt-in) |
| [upload_api.md](features/ingest/upload_api.md) | 📝 | Upload API 통합 기록 (이슈는 phase3_integration 참고) |
| [async_plan.md](features/ingest/async_plan.md) | ⏸ | Celery + Redis 비동기 인제스천 — Phase 8 보류 |
| [async_tradeoff.html](features/ingest/async_tradeoff.html) | ⏸ | 인제스천 부하 분리 vs LLM 컨텍스트 캐시 비교 (결론 = "지금 불필요") |

### 3.2 Chunking — [`features/chunking/`](features/chunking/)

| 문서 | 상태 | 페이지/도구 |
|---|---|---|
| [lab_page.md](features/chunking/lab_page.md) | ✅ | `frontend/pages/chunk_lab.py` — splitter 결과 비교 UI (§8 streamlit-extras+aggrid+plotly 리팩토링, §9 Docker 디버깅 메모 2026-05-27) |
| [testing_page.md](features/chunking/testing_page.md) | 📝 | chunk_lab 의 설계/요구 문서 |
| [experiment.md](features/chunking/experiment.md) | 📝 | 청크 사이즈 A/B 회귀 측정 (`chat/tests/evals/run_chunk_ab.py`) |

### 3.3 Providers / 임베딩 / LLM — [`features/providers/`](features/providers/)

| 문서 | 상태 | 역할 |
|---|---|---|
| [architecture.md](features/providers/architecture.md) | 📝 | Gemini/Qwen/OpenRouter/Ollama/HF provider 추상 |
| [refactor_overview.md](features/providers/refactor_overview.md) | 📝 | provider manager 리팩토링 배경 |
| [switching_result.md](features/providers/switching_result.md) | 🟢 | 5-provider switching 결과 (`feature/onnx-reranker` 미커밋) |
| [openrouter_evaluation.md](features/providers/openrouter_evaluation.md) | 📝 | OpenRouter 도입 평가 |
| [release_notes.md](features/providers/release_notes.md) | 📝 | provider 변경 이력 |

### 3.4 Token Lab — [`features/token_lab/`](features/token_lab/)

| 문서 | 상태 | 페이지 |
|---|---|---|
| [page.md](features/token_lab/page.md) | 🟢 | `frontend/pages/token_lab.py` — 모델/언어별 토큰화 비교 (미커밋) |

---

## 4. 세션 / 핸드오프 — [`sessions/`](sessions/)

| 문서 | 상태 | 역할 |
|---|---|---|
| [handoff.md](sessions/handoff.md) | 🟢 | 다음 세션 진입점 — env/provider 현재 상태 + 즉시 처리 |
| [commit_split_plan.md](sessions/commit_split_plan.md) | 🟢 | `feature/onnx-reranker` 잔여 변경분 커밋 분할 계획 |
| [2026-05-27.md](sessions/2026-05-27.md) | 📝 | 2026-05-27 작업 로그 |

---

## 5. 가이드 — [`guides/`](guides/)

| 문서 | 상태 | 역할 |
|---|---|---|
| [run_local_script_fixes.md](guides/run_local_script_fixes.md) | 📝 | `run_local.sh` 수정 가이드 |
| [test_fixtures.md](guides/test_fixtures.md) | 📝 | 테스트 fixture 작성/관리 가이드 |
| [python_file_guide.html](guides/python_file_guide.html) | 📝 | 주요 Python 파일 가이드 |
| [workflow.html](guides/workflow.html) | 📝 | 개발 워크플로우 안내 |
| [ab_testing_guide.html](guides/ab_testing_guide.html) | 📝 | A/B 테스트 가이드 |

---

## 6. 리포트 — [`reports/`](reports/)

| 문서 | 상태 | 역할 |
|---|---|---|
| [project_journey.html](reports/project_journey.html) | 📝 | Phase 1~3 통합까지 시각 요약 |
| [project_status.html](reports/project_status.html) | 📝 | 프로젝트 상태 스냅샷 |
| [prd.html](reports/prd.html) | 📝 | PRD |
| [work_distribution.md](reports/work_distribution.md) | 📝 | Claude Code / Codex / 다른 Claude 분담 매트릭스 |
| [work_distribution.html](reports/work_distribution.html) | 📝 | work_distribution 의 HTML 렌더 |
| [architect.md](reports/architect.md) | 📝 | 아키텍트 메모 |

---

## 7. 코드와 문서의 매핑

```
backend/chat/
├── ingest/                            ← features/ingest/*, architecture/ingest_layer.md
│   ├── base.py, registry.py
│   ├── pipeline.py                    ← ingest_path() 진입
│   ├── manifest.py                    ← Phase 2 dedup
│   ├── loaders/structured/{csv,excel}.py
│   ├── loaders/text/{txt,pdf,docx,html}.py
│   ├── splitters/{recursive,row}.py
│   └── sinks/chroma.py
├── ingest_views.py                    ← features/ingest/upload_api.md, features/chunking/lab_page.md
├── token_views.py, token_utils.py     ← features/token_lab/page.md
├── providers/                         ← features/providers/*.md
├── models.py                          ← IngestManifest
└── tests/evals/run_chunk_ab.py        ← features/chunking/experiment.md

frontend/pages/
├── chunk_lab.py                       ← features/chunking/lab_page.md
└── token_lab.py                       ← features/token_lab/page.md
```

---

## 8. 새 문서 작성 가이드

여러 agent (Claude Code / Codex / 다른 Claude) 가 병렬로 일한다. Claude Code 의 역할 = **문서화와 맥락 일관성 유지**.

새 코드/모듈이 들어왔을 때:

1. 적절한 그룹 디렉토리(`architecture/`, `features/<topic>/`, `guides/`, `reports/`, `sessions/`) 에 새 파일 추가
2. 본 인덱스 표에 한 줄 추가 — 제목, 상태, 역할
3. 학습 메모 + "안 한 것 + 사유" 는 본문 내 별도 섹션
4. naming / response shape / env 처리 등 다른 모듈과 어긋난 부분은 **불일치 노트** 로 본문에 명시

---

## 9. 외부 문서

루트(`Rag_Chat/`):
- [README.md](../../README.md) — 프로젝트 외부 소개
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — 상위 아키텍처
- [프로젝트현황.md](../../프로젝트현황.md) — 진행 상황 한국어 정리

기타:
- `Rag_Chat/docs/` — 정적 사이트 빌드 골격 (`_layouts/`, `concepts/hybrid-search.md`)
- `docs/superpowers/` — superpowers plans/specs (`2026-05-19-onnx-reranker`, `2026-05-27-model-provider-switching`)
- `Rag_Chat/backend/TestsReadme.md`, `Rag_Chat/frontend/README.md`, `Rag_Chat/triple_chat_pjt/testReadme.md` — 모듈별 readme (이동하지 않음)
