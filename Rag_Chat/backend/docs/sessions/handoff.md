# Session Handoff — 2026-05-27

> 다음 세션(또는 다른 agent)이 이어받기 위한 상태 스냅샷.
> Provider 스위칭 정리 + `.env` 통합 작업 기준.

---

## 1. 한 줄 요약

Chat LLM 과 임베딩을 분리하고 5개 provider(gemini/qwen/openrouter/ollama/huggingface)를
선택 가능하게 만든 뒤, 환경 설정을 **단일 `.env`** 로 통합했다. 현재 운영 provider 는
`openrouter`, Ollama 는 로컬 모델 확인 완료 상태로 즉시 전환 가능.

---

## 2. 이번 세션에 한 것

- **`.env` 통합** — `.env.example` 에만 있던 키(`RERANKER_*`, `OLLAMA_*`, `HUGGINGFACE_*`)를
  겹치지 않게 `.env` 로 병합. `.env.example` 삭제, `.gitignore` 에 `.env.example` 추가.
  → 커밋 `ae308c9` (`feature/onnx-reranker` 브랜치)
- **Ollama 로컬 모델 확인** — `qwen3.6`(23GB), `gemma4`(9.6GB) 설치됨. `llama3.1` 은 미설치.
  `.env` 에 `OLLAMA_MODEL=qwen3.6` 설정.
- **상태 HTML 생성** — `Rag_Chat/project_status.html` (provider/ingest/env 스냅샷).

> 참고: provider 스위칭 코드(`ProviderManager`, 프론트 preset)는 다른 agent 작업분으로
> 이미 working tree 에 있었음. 이번 세션은 그 위에 env 정리 + 문서화를 얹은 것.

---

## 3. 현재 `.env` provider 상태

| 키 | 값 | 비고 |
|---|---|---|
| `EMBEDDING_PROVIDER` | `gemini` | `GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001` |
| `REASONING_PROVIDER` | `openrouter` | `openai/gpt-oss-20b:free` |
| `GENERATION_PROVIDER` | `openrouter` | `openai/gpt-oss-20b:free` |
| `OLLAMA_MODEL` | `qwen3.6` | 로컬 설치됨, provider 만 바꾸면 사용 가능 |
| `RERANKER_ENABLED` | `0` | optional, 무거운 의존성 → 기본 비활성 |

`.env` 는 gitignored → repo 에 없음. 로컬 파일이 source of truth.

---

## 4. 다음 세션 적용 방법

**Ollama 로 전환하려면** (`.env` 만 수정, 코드 변경 불필요):
```env
REASONING_PROVIDER=ollama
GENERATION_PROVIDER=ollama
# OLLAMA_MODEL=qwen3.6  (이미 설정됨)
```
그 뒤 `ollama serve` 만 실행하면 됨 (모델은 이미 로컬에 있음).

**프론트엔드** — Streamlit 사이드바 *Provider Preset* 에서 `Ollama Only` 선택 시 세션 단위 전환.

---

## 5. 주의사항 (gotchas)

- **임베딩 변경 = 재인덱싱 필수.** `EMBEDDING_PROVIDER`/모델을 바꾸면 기존 Chroma 벡터 DB 를
  다시 만들어야 검색 품질이 유효함 (`get_embedding_config()` 가 `requires_reindex: true` 노출).
- **`EMBEDDING_MODEL` 키는 일부러 `.env` 에 안 넣음.** 넣으면 표시값이
  실제 사용값(`GOOGLE_EMBEDDING_MODEL`)과 어긋남. provider별 모델 키만 사용.
- **Hugging Face 는 단순 모델명 불가.** OpenAI 호환 엔드포인트(Inference Endpoint/TGI)가
  `HUGGINGFACE_BASE_URL` 에 있어야 함. 미설정 시 `RuntimeError`.
- **`llama3.1` 미설치.** `.env`/문서의 과거 예시가 llama3.1 이었으나 로컬엔 없음 → qwen3.6 사용.

---

## 6. 안 한 것 / 보류

- **Hugging Face 엔드포인트** — 담당자가 추후 직접 준비 (`HUGGINGFACE_*` 는 빈 placeholder).
- **push** — `ae308c9` 는 로컬 커밋만. 푸시 미실행.
- **다른 working tree 변경** — ingest Phase 3 / Upload API 통합 등 미커밋 변경은 손대지 않음
  (다른 agent 작업분). 통합 이슈는 [_index.md](../_index.md) Phase 표 참고.

---

## 7. Ingest Layer 상태 (Claude Code 측 작업 요약)

오늘 Claude Code 가 한 작업 (env 와는 별개 트랙):

- **Phase 1 skeleton** — `chat/ingest/` 패키지, loader/splitter/sink 추상 ([phase1_skeleton.md](../features/ingest/phase1_skeleton.md))
- **Phase 2 manifest** — `IngestManifest` 모델 + SHA256 dedup + 결정론적 청크 id ([phase2_manifest.md](../features/ingest/phase2_manifest.md))
- **Chunk Lab + TXT loader** — `/api/v1/triple/ingest/preview/` + Streamlit `pages/chunk_lab.py` ([lab_page.md](../features/chunking/lab_page.md))
- **Phase 3 통합** — 다른 agent 가 추가한 PDF/DOCX/HTML loader + Upload API 가 `pipeline.ingest_path` 를 단일 진입점으로 공유하도록 정리 ([phase3_integration.md](../features/ingest/phase3_integration.md))
- **사건사고**: 세션 후반 `pipeline.py` 가 IDE undo 로 부분 revert 됨 → `git checkout HEAD -- pipeline.py` 로 복원. 8 시나리오 재검증 통과.

검증된 호출 경로 (모두 `ingest_path` 경유):

```python
# CLI
ingest_path(path, sink=sink, force=options["force"])
# Upload API
ingest_path(tmp, source_uri_override=f"upload://{name}")
```

splitter 미지정 시 `default_splitter_for(loader.source_type)` 자동 (csv→row, pdf/docx/html/txt→recursive).

---

## 8. 다음 세션 즉시 처리할 것

### 8.1 Phase 4 — 완료 (오늘 통합됨) ✅

Codex 가 추가한 clause/heading splitter 가 `splitters/__init__.py` 의
`_BY_NAME` 에 등록됨. **opt-in only 정책** — `DEFAULT_BY_SOURCE` 매핑에는
넣지 않아 자동 dispatch 안 됨. `splitter_by_name("clause"|"heading")` 으로 명시 선택.

상세: [phase4_splitters.md](../features/ingest/phase4_splitters.md)

### 8.2 chunk_lab UI 에 새 splitter 노출 (다음 작업 후보)

`frontend/pages/chunk_lab.py` 의 splitter 옵션이 `["recursive", "row"]` 만.
backend `_resolve_splitter` 는 이미 `splitter_by_name` 경유라 한 줄만 추가:

```python
splitter_name = st.selectbox("전략", ["recursive", "row", "heading", "clause"], ...)
```

### 8.3 나머지 untracked 검토 대상

```
chat/tests/evals/dataset_legal.jsonl          # eval 확장
chat/tests/evals/dataset_galaxy_full.jsonl
chat/tests/test_provider_manager.py           # provider 테스트
chat/tests/test_token_utils.py
chat/tests/test_token_views.py
backend/scripts/                              # 미확인 디렉토리
backend/data/                                 # 미확인 디렉토리
Rag_Chat/project_status.html                  # 다른 agent 가 생성한 상태 HTML
backend/docs/model_provider_switching_result.md
backend/docs/python_file_guide.html
```

각각 통합 검토 후 doc 작성 또는 무시 결정.

전체 untracked: `git status --short | grep '^??'`

---

## 9. Sanity 명령 — 새 세션 시작 시

```bash
cd Rag_Chat/backend
./venv/bin/python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'triple_chat_pjt.settings')
django.setup()
from chat.ingest import pipeline, loaders
from chat.ingest.registry import registered_extensions
from chat.ingest.splitters import default_splitter_for
import inspect
sig = inspect.signature(pipeline.ingest_path)
print('extensions:', registered_extensions())
print('ingest_path params:', list(sig.parameters.keys()))
print('default for pdf:', type(default_splitter_for('pdf')).__name__)
print('default for csv:', type(default_splitter_for('csv')).__name__)
"
```

기대 출력 (Phase 3 통합 상태):
```
extensions: ('.csv', '.docx', '.html', '.htm', '.md', '.pdf', '.txt', '.xls', '.xlsx')
ingest_path params: ['path', 'splitter', 'sink', 'force', 'source_uri_override']
default for pdf: RecursiveSplitter
default for csv: RowSplitter
```

`source_uri_override` 가 빠져있거나 `ingest_path` 가 splitter required 면 → pipeline.py 가 다시 revert 된 것. `git checkout HEAD -- chat/ingest/pipeline.py` 로 복원.

---

## 10. 2026-05-27 (오후 추가) — Test data + UI 리팩토링 + Doc 정리

오후에 추가로 한 것:

- **Test data 인벤토리 신설** — `chat/tests/ingest/fixtures/` (text/structured/special/ocr)
  + `data/samples/` + eval dataset 두 개. 자세히: [test_fixtures.md](../guides/test_fixtures.md).
- **HWP 실제 파일 확보** — `fixtures/special/standard_employment_rules_2026.hwp`
  (고용노동부 2026년 표준 취업규칙 HWP 5.x, 277KB). Phase 7-a HWP loader (Codex)
  진짜 검증 데이터로 즉시 사용 가능.
- **Galaxy 라인업 실제 데이터** — gsmarena.com / en.wikipedia.org 에서 S25/S25+/S25 Ultra
  풀스펙 추출. 초안의 합성 값 (RAM/카메라 화소 등 부정확) 전부 교체.
- **OCR fixture 자동 생성** — `backend/scripts/build_ocr_fixtures.py` (PIL only).
- **Chunk Lab UI 리팩토링** — `streamlit-extras` + `st-aggrid` + `plotly` 교체.
  상세: [lab_page.md](../features/chunking/lab_page.md) §8.
- **frontend `BACKEND_URL` env 통일** — `chunk_lab.py` 가 다른 페이지와 다른 env 키
  (`API_BASE_URL`) 쓰던 불일치 제거. 첫 Connection refused 원인 + 해결:
  [lab_page.md](../features/chunking/lab_page.md) §9.
- **app.py 사이드바 정리** — Current Providers / Embedding Configuration 두 개의
  raw `st.json` 을 compact 마크다운 + collapsed Raw JSON expander 로.

§8.3 untracked 목록은 이제 대부분 확인됨:
- `dataset_legal.jsonl`, `dataset_galaxy_full.jsonl` — 신규 eval dataset (합성/실제)
- `backend/scripts/build_ocr_fixtures.py` — OCR 이미지 생성기 (PIL only)
- `backend/data/samples/` — end-to-end 샘플 (Galaxy 실제 + 사규 합성)
- `model_provider_switching_result.md` — `features/providers/switching_result.md` 로 이전됨

다음 세션 우선순위 (변동 없음):
1. **Phase 5 — OCR loader** (다른 Claude 리서치 후)
2. **Phase 6 — ORM sink** (Claude Code, knowledge_product 이전)
3. **Phase 7-a — HWP loader** (Codex, 실제 fixture ready)

---

## 11. 2026-05-27 (저녁 추가) — Admin upload 통합 + docs 재구조화

Claude Code 세션 추가 작업:

- **Admin upload UI + ingest endpoint 커밋** — `bc73020 feat: admin upload endpoint and ingest pipeline`
  (사이드바 파일 업로더 + `POST /api/v1/triple/ingest/upload/` + `IngestManifest` 모델 + 마이그레이션 + fixture).
  지원 확장자: xlsx, xls, csv, txt, md, pdf, docx, html. HWP 는 선택지만 열어두고 처리 미구현.
- **`backend/docs/` 재구조화** — 평평한 ~30개 파일을 6개 그룹(`architecture/`, `features/{ingest,chunking,providers,token_lab}/`,
  `guides/`, `reports/`, `sessions/`) 으로 이동. 루트(`Rag_Chat/`) 의 `ArchitectReadme.{md,html}`,
  `architect.md`, `prd.html`, `project_status.html`, `workflow.html`, `ab_testing_guide.html`,
  `run_local_script_fixes.md` 도 `backend/docs/` 로 이주.
- **typo fix** — `frontend/frontnedREADME.md` → `frontend/README.md`.
- **`_index.md` 재작성** — 상태 범례(✅ done · 🟢 active · ⏳ planned · ⏸ paused · 📝 reference) +
  그룹별 링크 테이블 + Phase 진행표.
- **링크 정정** — 본 handoff 내 구 경로 11개 새 경로로 갱신 (`_index.md`,
  `ingest_phase*` → `features/ingest/phase*`, `chunk_*` → `features/chunking/*`, `project_status` → `reports/`,
  `프로젝트현황.md` → `../../../프로젝트현황.md`).

git 영향 — 추적된 파일 24개가 D(이동) + 새 디렉토리 6개가 untracked. 다음 세션 시작 시 단일 docs 커밋으로 묶을 예정.

---

## 관련 문서
- [project_status.html](../reports/project_status.html) — provider/env 시각화
- [project_journey.html](../reports/project_journey.html) — Ingest Phase 1~3+ 시각 요약
- [2026-05-27.md](2026-05-27.md) — 오늘 작업 상세 로그
- [commit_split_plan.md](commit_split_plan.md) — `feature/onnx-reranker` 잔여 변경분 커밋 분할 계획
- [_index.md](../_index.md) — 전체 문서/Phase 인덱스
- [프로젝트현황.md](../../../프로젝트현황.md) — 한국어 진행 현황
