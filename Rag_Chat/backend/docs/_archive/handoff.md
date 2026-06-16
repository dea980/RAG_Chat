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

## 12. 2026-05-27 (저녁 마감) — Phase 6 ORM Sink + Phase 5 OCR loader

이번 세션 (저녁) 추가 작업:

- **Phase 6 — ORM Sink + CSV fields 보존** ✅
  - `chat/ingest/sinks/knowledge_orm.py` 신설 — `KnowledgeOrmSink` (CSV/Excel → `Product.update_or_create`,
    `name_column` 기본 `Model`, 비정형 source_type 은 silently skip).
  - `chat/ingest/sinks/composite.py` 신설 — `CompositeSink` (여러 sink fan-out, prefix 기반 delete 라우팅).
  - `chat/ingest/loaders/structured/csv.py` 수정 — LangChain CSVLoader 래핑 제거,
    `csv.DictReader` 직접 사용. `metadata['fields']` 에 실제 컬럼 값 dict 가 들어가
    ORM 매핑 가능 (이전엔 LangChain source/row 만 있어 매핑 불가).
  - `chat/build_vector_store.py` 에 `DeprecationWarning` 추가. Ingest layer 가 대체.
  - 단위 테스트 7개 (`test_knowledge_orm_sink.py`) — pytest 실행은 *기존 postgres
    인증 문제* 로 막힘 (`health/ready/` 가 `database ok=false`). 코드 import / dry-run 통과.
  - 자세히: [phase6_orm_sink.md](../features/ingest/phase6_orm_sink.md).
- **Phase 5 — OCR image loader** (sub-agent 디스패치)
  - `chat/ingest/loaders/ocr/image.py` + `__init__.py` 신설. `OcrImageLoader`,
    `extensions = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp")`, `source_type = "ocr"`,
    pytesseract `lang="kor+eng"`.
  - `chat/ingest/loaders/__init__.py` 에 `from .ocr import image as _ocr_image` 한 줄.
  - `chat/tests/ingest/test_ocr_loader.py` — 2 pass, 3 skip (tesseract 미설치 환경 가드).
- **app 8000 정리** — DY-ADAS uvicorn (PID 53406) 종료, `docker-compose.yml` backend
  포트 `8002:8000` → `8000:8000`, `chunk_lab.py` 기본 포트 8001 → 8000 통일.

### ⚠️ 정리할 잔재

- **OCR loader 중복 파일** — `chat/ingest/loaders/text/ocr.py` (다른 agent 가 미리
  만든 것) 와 `chat/ingest/loaders/ocr/image.py` (이 세션 sub-agent 가 만든
  설계상 올바른 위치) 가 *둘 다* `@register` 한다.
  `loader_for(".png")` 가 어느 클래스를 반환할지 결정적이지 않을 위험.
  다음 세션에서 `text/ocr.py` 삭제 + `text/__init__.py` import 정리 필요.

### 이번 세션 신규/변경 파일 (저녁분)

```
backend/chat/build_vector_store.py                   # M (deprecation)
backend/chat/ingest/loaders/structured/csv.py        # M (DictReader 전환, fields 보존)
backend/chat/ingest/sinks/__init__.py                # M (3개 sink export)
backend/chat/ingest/sinks/knowledge_orm.py           # 신규
backend/chat/ingest/sinks/composite.py               # 신규
backend/chat/tests/test_knowledge_orm_sink.py        # 신규
backend/chat/ingest/loaders/ocr/__init__.py          # 신규 (sub-agent)
backend/chat/ingest/loaders/ocr/image.py             # 신규 (sub-agent)
backend/chat/ingest/loaders/__init__.py              # M (sub-agent 한 줄 import)
backend/chat/tests/ingest/test_ocr_loader.py         # 신규 (sub-agent)
backend/docs/features/ingest/phase6_orm_sink.md      # 신규
backend/docs/_index.md                               # M (Phase 6 row 🟢, doc entry 추가)
backend/docs/sessions/handoff.md                     # 이 섹션
docker-compose.yml                                   # M (8002:8000 → 8000:8000)
frontend/pages/chunk_lab.py                          # M (기본 포트 8001 → 8000)
```

### 다음 세션 우선순위

1. **postgres 인증 fix** — `health/ready/` 가 `ok=true` 로 회복되도록 volume
   재설정 또는 .env 일치. Phase 6 통합 테스트 + 전체 chat 기능에 영향.
2. **OCR 중복 파일 정리** — `text/ocr.py` 삭제 + `text/__init__.py` 정리.
3. **seed_demo 갱신** — `KnowledgeOrmSink` 로 CSV 한 줄로 대체 (Phase 6.5).
4. **galaxy_lineup.csv 실적재 검증** — `ingest_path` + `CompositeSink` 로 종합 동작 확인.

---

## 13. 2026-05-28 (야간 4-agent 통합) — Moderation Phase A + chunk_lab UI + 통합 docs

오늘 야간에 또 한 번의 4-agent 병렬 세션. yesterday (2026-05-27 night) 와 *다른 구성*:

| 터미널 | 목표 | 결과 위치 |
|---|---|---|
| **T1** | Moderation Phase A — sensitivity label + access_level + retrieval ACL | `backend/moderation/levels.py`, `tests/`, knowledge/chat models migrations, retrieval `redacted_count` |
| **T2** | `frontend/pages/chunk_lab.py` splitter selectbox 에 `heading`, `clause` 노출 | `frontend/pages/chunk_lab.py` (M) + `night/T2.work.md`·`T2.learning.md` |
| **T3** | 어젯밤 4-agent 결과 통합 문서화 — `_index` sync · cross-link · commit_split_plan 재작성 | `_index.md` (M, §3.6/§3.7/§9.2 확장), `sessions/commit_split_plan.md` (rewritten), 본 handoff §13 |

T3 = 이 섹션을 쓴 터미널. T1·T2 는 코드 작업, T3 는 doc 작업.

### 13.1 즉시 처리할 것 (다음 세션 첫 5분)

1. **T1·T2·T3 결과를 [commit_split_plan.md](commit_split_plan.md) 의 8묶음 순서대로 커밋**
   - 1번 chore 정리 (OCR 중복 제거 + 루트 DownSub HTML 삭제) 부터 시작
   - 6번 moderation Phase A 는 *별도 PR* 권장 (코드+마이그레이션+테스트 규모)
2. **`git diff` reality check** — embedding_lab 의 backend 코드가 status 에 안 보임. yesterday T2 가 Mode A 구현까지 갔는지 재확인. 안 갔으면 commit_split_plan §4 = doc only commit.
3. **`build_night_report.py` 산출 HTML** (`backend/docs/reports/night/index.html`) 확인 — T1·T2·T3 work/learning 가 dashboard 에 정상 표시되는지.
4. **moderation Phase A Exit Criteria** ([plans/2026-05-28-moderation-implementation.md](../superpowers/plans/2026-05-28-moderation-implementation.md) §A.6) 체크 — `python -m pytest moderation/tests/test_acl.py -v` 전수 pass, `Document.objects.first().sensitivity == 'internal'`, retrieval response 에 `redacted_count` 포함.

### 13.2 야간 작업 산출물 위치

```
backend/docs/sessions/missions.md                       # 야간 임무판 (T1/T2/T3 섹션)
backend/docs/sessions/night/T2.work.md  T2.learning.md  # T2 야간 로그·학습
backend/docs/sessions/night/T3.work.md  T3.learning.md  # T3 야간 로그·학습 (T3 = 본 섹션 작성자)
backend/docs/reports/night/index.html                   # build_night_report.py 산출 dashboard
backend/docs/reports/night/T*.html  T*-learning.html    # 각 T 의 work/learning HTML
```

T1 도 work.md/learning.md 가 있어야 dashboard 에 등장. T1 이 wrap-up 없이 빠진 상태라면 dashboard 의 T1 row 가 missing — 다음 세션이 T1 결과 보고 수동 작성하거나, T1 다시 깨워서 wrap-up.

### 13.3 OCR 중복 잔재 정리 (§12 의 카운트다운)

`chat/ingest/loaders/ocr/{__init__,image}.py` 가 **삭제됨** (status 의 `D` 행) → 카운트다운 ✅. `chat/ingest/loaders/text/ocr.py` 만 남음. `loaders/__init__.py` 와 `loaders/text/__init__.py` 의 import 도 정리됨 (M 행). 커밋 시점에 한 번 더 `loader_for(".png")` 가 단일 클래스를 반환하는지 sanity 체크.

### 13.4 design system 등장

- 루트에 `CLAUDE.md` + `DESIGN.md` 신설 (untracked). DESIGN.md = 모든 UI·시각 결정의 단일 출처 (Pretendard + Geist Mono + `#E89B3C` accent + citation ribbon).
- `Rag_Chat/docs/_layouts/{concept,index}.html` 가 새 토큰 반영하도록 수정됨 (M).
- `Rag_Chat/docs/design/` (untracked) — preview 페이지 + tokens.css.
- 이 묶음은 [commit_split_plan.md](commit_split_plan.md) §7 으로.

### 13.5 다음 phase 진입 순서 제안

1. Moderation **Phase A** commit 완료 → **Phase B** spec 검토 (boundary expansion, ModerationRule 모델)
2. Phase 7-a HWP loader *구현* (T4 리서치 권고 = pyhwp, six 동반 설치 필요)
3. Embedding Lab Mode B (n×n matrix) — yesterday T2 의 Mode A 가 실제로 구현됐는지 확인 후
4. `chunk_lab` heading/clause 옵션 → 실 backend 로 dry-run 검증

---

## 관련 문서
- [project_status.html](../reports/project_status.html) — provider/env 시각화
- [project_journey.html](../reports/project_journey.html) — Ingest Phase 1~3+ 시각 요약
- [reports/night/index.html](../reports/night/index.html) — **야간 4-agent dashboard** (오늘 야간 결과)
- [2026-05-27.md](2026-05-27.md) — yesterday 작업 상세 로그
- [2026-05-27-night-parallel.md](2026-05-27-night-parallel.md) — yesterday 4-agent narrative
- [missions.md](missions.md) — 오늘 야간 임무판
- [commit_split_plan.md](commit_split_plan.md) — `feature/onnx-reranker` 잔여 변경분 커밋 분할 계획 (2026-05-28 02:10 재작성)
- [_index.md](../_index.md) — 전체 문서/Phase 인덱스
- [프로젝트현황.md](../../../프로젝트현황.md) — 한국어 진행 현황
