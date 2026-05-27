# 커밋 분할 계획 (다음 세션 핸드오프)

`feature/onnx-reranker` 브랜치에 admin upload 커밋(`bc73020`) 이후 남은 변경분을 정리하기 위한 문서입니다. 다음 세션에서 이 문서대로 작은 단위 커밋으로 쪼개 진행합니다.

> **주의 — 이 문서 작성 후 두 가지가 더 일어났음**
> 1. 다른 agent 가 `ae308c9`(env 통합) / `b74e28e`(docs 인덱스) / `e333fa4`(test fix) / `f328f1d`(Phase 4 splitter) 4개 추가 커밋. 일부 변경분은 이미 흡수됐을 수 있으니 진행 전 `git diff` 로 재확인.
> 2. `backend/docs/` 가 그룹별 디렉토리로 재구조화됨. 본문에 적힌 평평한 경로(예: `backend/docs/model_provider_switching_result.md`) 는 이제 `backend/docs/features/providers/switching_result.md` 등으로 이동. 현재 위치는 [_index.md](../_index.md) 참고.

## 1. feat: model provider switching (openrouter / ollama / huggingface)

핵심 — `ProviderConfigAPIView`, `ProviderManager`에 3개 provider 조합 추가.

- `Rag_Chat/backend/chat/views.py` — `PROVIDER_PRESETS` 확장, `VALID_PROVIDERS` 갱신
- `Rag_Chat/backend/chat/providers/manager.py` — `get_embedding_config()` 추가
- `Rag_Chat/backend/chat/tests/test_views.py` — 신규 조합 테스트가 포함되면 같이
- `Rag_Chat/backend/chat/tests/test_provider_manager.py` (untracked)
- `Rag_Chat/.env.example` — 새 env 키
- `Rag_Chat/backend/requirements.txt` — 새 의존성
- `Rag_Chat/backend/docs/model_provider_switching_result.md`
- `docs/superpowers/plans/2026-05-27-model-provider-switching.md`
- `docs/superpowers/specs/2026-05-27-model-provider-switching-design.md`

## 2. feat: Token Lab (token counting API + page)

- `Rag_Chat/backend/chat/token_utils.py` (untracked)
- `Rag_Chat/backend/chat/token_views.py` (untracked)
- `Rag_Chat/backend/chat/tests/test_token_utils.py` (untracked)
- `Rag_Chat/backend/chat/tests/test_token_views.py` (untracked)
- `Rag_Chat/backend/chat/tests/test_utils.py` — token 관련 변경이면 함께, 아니면 4번
- `Rag_Chat/frontend/pages/token_lab.py` (untracked)
- `Rag_Chat/backend/docs/token_lab_page.md`

참고 — `urls.py` 의 `tokens/estimate/` 라우트는 이미 admin upload 커밋에 포함됨.

## 3. feat: Chunk Lab page

- `Rag_Chat/frontend/pages/chunk_lab.py` (untracked)
- `Rag_Chat/backend/docs/chunk_lab_page.md` (untracked)
- `Rag_Chat/backend/docs/chunk_testing_page.md` (untracked)

참고 — `ingest/preview/` 백엔드 API는 admin upload 커밋에 포함됨.

## 4. chore: reranker / build_vectors tweaks + eval datasets

- `Rag_Chat/backend/chat/rerankers/onnx_bge.py`
- `Rag_Chat/backend/chat/tests/test_rerank.py`
- `Rag_Chat/backend/chat/management/commands/build_vectors.py`
- `Rag_Chat/backend/chat/tests/evals/dataset_galaxy_full.jsonl` (untracked)
- `Rag_Chat/backend/chat/tests/evals/dataset_legal.jsonl` (untracked)
- `Rag_Chat/backend/scripts/build_ocr_fixtures.py` (untracked) — fixture 빌드 스크립트면 여기

## 5. docs: project status / architecture / concepts

- `README.md`
- `Rag_Chat/ARCHITECTURE.md`
- `Rag_Chat/backend/README.md`
- `Rag_Chat/프로젝트현황.md`
- `Rag_Chat/backend/docs/_index.md` (untracked)
- `Rag_Chat/backend/docs/core_concepts.md` (untracked)
- `Rag_Chat/backend/docs/async_ingest_plan.md` (untracked)
- `Rag_Chat/backend/docs/async_ingest_tradeoff.html` (untracked)
- `Rag_Chat/backend/docs/ingest_phase3_integration.md` (untracked) — 1번 커밋에 함께 묻혀야 했지만 누락. 여기 또는 별도 docs 커밋
- `Rag_Chat/backend/docs/project_journey.html` (untracked)
- `Rag_Chat/backend/docs/python_file_guide.html` (untracked)
- `Rag_Chat/docs/` (untracked, `_layouts/`, `build/`, `concepts/`)
- `Rag_Chat/project_status.html` (untracked)
- `Rag_Chat/scripts/build_concepts.py` (untracked) — concepts 빌드 스크립트
- `Rag_Chat/backend/data/samples/` (untracked) — 내용 확인 필요

## 커밋하지 말 것 (정리)

루트에 떨어진 DownSub 자막 다운로드 — 저장소에 들어가면 안 됨.

- `[Korean (auto-generated)-Korean (auto-generated)] Code  )  GPT,        & AX   [DownSub.com].txt`
- `[Korean (auto-generated)]    4  RAG       , AX   [DownSub.com].txt`

처리 옵션:
- 그냥 삭제 (`rm '[Korean...].txt'`)
- 혹은 루트 `.gitignore` 에 `*[DownSub.com]*.txt` 추가

## 작업 순서 제안

1. DownSub txt 정리 (삭제 or gitignore)
2. 각 그룹 stage → diff 확인 → commit
3. provider switching → Token Lab → Chunk Lab → chore → docs 순 권장 (아키텍처 영향도 → UI → docs)
4. 마지막에 `git status` 가 깨끗한지 확인
