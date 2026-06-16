# 커밋 분할 계획 (2026-05-28 야간 통합 시점 핸드오프)

`feature/onnx-reranker` 브랜치에 누적된 미커밋 변경분을 정리하기 위한 문서. 다음 세션에서 이 문서대로 작은 단위 커밋으로 쪼개 진행한다.

> **재작성 이력**
> - 2026-05-27 초안: provider switching / token_lab / chunk_lab / chore / docs 5묶음 기준.
> - 2026-05-27 저녁: phase 5 OCR + phase 6 ORM sink 추가.
> - **2026-05-28 02:10 (T3 야간)**: 어젯밤 4-agent 결과 + 오늘 야간 4-agent 결과를 흡수해 전면 재작성. 아래 분류는 *현재 `git status` 스냅샷* 과 직접 매칭.
>
> 작성 시점 `git status --short` 가 본 문서의 진실. 다른 agent 가 새 파일을 만들면 본 문서가 그만큼 stale 해진다. *진행 직전 다시 sync*.

---

## 0. 현재 `git status` 스냅샷 (2026-05-28 02:10)

```
M  .gitignore
M  README.md
M  Rag_Chat/backend/chat/ingest/loaders/__init__.py
D  Rag_Chat/backend/chat/ingest/loaders/ocr/__init__.py
D  Rag_Chat/backend/chat/ingest/loaders/ocr/image.py
M  Rag_Chat/backend/chat/ingest/loaders/text/__init__.py
M  Rag_Chat/backend/docs/_index.md
M  Rag_Chat/backend/docs/architecture/security.md
M  Rag_Chat/backend/docs/reports/learning_journey.html
M  Rag_Chat/backend/docs/superpowers/specs/2026-05-27-night-autonomous-multiagent-design.md
M  Rag_Chat/backend/requirements.txt
M  Rag_Chat/docs/_layouts/concept.html
M  Rag_Chat/docs/_layouts/index.html
M  Rag_Chat/frontend/pages/chunk_lab.py
?? CLAUDE.md
?? DESIGN.md
?? Rag_Chat/backend/chat/ingest/loaders/text/ocr.py
?? Rag_Chat/backend/docs/features/embedding_lab/page.md
?? Rag_Chat/backend/docs/features/ingest/phase5_ocr.md
?? Rag_Chat/backend/docs/features/ingest/phase7a_hwp.md
?? Rag_Chat/backend/docs/features/ingest/phase7a_hwp_research.md
?? Rag_Chat/backend/docs/features/moderation/
?? Rag_Chat/backend/docs/reports/night/
?? Rag_Chat/backend/docs/sessions/2026-05-27-night-parallel.md
?? Rag_Chat/backend/docs/sessions/night/T2.learning.md
?? Rag_Chat/backend/docs/sessions/night/T2.work.md
?? Rag_Chat/backend/docs/sessions/night/T3.work.md
?? Rag_Chat/backend/docs/superpowers/plans/2026-05-28-moderation-implementation.md
?? Rag_Chat/backend/docs/superpowers/specs/2026-05-28-moderation-architecture.md
?? Rag_Chat/backend/moderation/levels.py
?? Rag_Chat/backend/moderation/tests/
?? Rag_Chat/docs/design/
?? "파수 대외비 문서 관리 및 보안 _ Fasoo 기밀 문서 암호화 및 추적.html"
```

(T1·T3 작업이 진행 중이면 추가 untracked 가 더 생긴다. 진행 직전 `git status --short` 재확인.)

---

## 1. chore: 정리 — 루트 잡파일 + OCR 중복 제거

가장 먼저, 신호잡음 줄이려 *정리만 하는 커밋* 부터.

- **`D  Rag_Chat/backend/chat/ingest/loaders/ocr/__init__.py`** — OCR loader 위치 정리 (yesterday night handoff §12 "정리할 잔재")
- **`D  Rag_Chat/backend/chat/ingest/loaders/ocr/image.py`** — 같이 삭제. `text/ocr.py` 가 올바른 위치
- **`M  Rag_Chat/backend/chat/ingest/loaders/__init__.py`** — `ocr/` 패키지 import 제거 (해당이라면)
- **`M  Rag_Chat/backend/chat/ingest/loaders/text/__init__.py`** — `text/ocr.py` 사이드이펙트 import 정리
- **`M  .gitignore`** — DownSub txt 패턴 추가했다면 함께
- **루트 DownSub HTML 삭제**: `파수 대외비 문서 관리 및 보안 _ Fasoo ...html` — 저장소에 들어가면 안 됨. 본 commit 직전 `rm` 또는 `.gitignore`

→ 단일 commit. 메시지: `chore: dedupe OCR loader location and clean root junk`

---

## 2. feat: phase 5 OCR loader 통합

- **`?? Rag_Chat/backend/chat/ingest/loaders/text/ocr.py`** — OCR loader (text/ 하위 정상 위치)
- (1번에서 처리되지 않았다면) `text/__init__.py` 의 OCR import 한 줄
- **`M  Rag_Chat/backend/requirements.txt`** — `pytesseract` 라인만 cherry-pick (sentence-transformers 라인은 따로)
- **`?? Rag_Chat/backend/docs/features/ingest/phase5_ocr.md`** — yesterday T1 이 만든 통합 노트 (skeleton 상태. 본 commit 직전 5분 실측으로 채워두면 좋음)

부분 stage 필요 (`requirements.txt` 의 pytesseract 줄만). 메시지: `feat(ingest): phase 5 OCR loader (pytesseract)`

---

## 3. feat: phase 7-a HWP research (코드 0줄, 리서치 doc 만)

- **`?? Rag_Chat/backend/docs/features/ingest/phase7a_hwp_research.md`** — T4 가 어젯밤 작성한 실측 리서치 (pyhwp 권고 + libhwp 패닉 / hwp-extract 부적합 등)
- **`?? Rag_Chat/backend/docs/features/ingest/phase7a_hwp.md`** — 부모 phase 통합 노트 skeleton (구현은 다음 세션)

메시지: `docs(ingest): phase 7-a HWP loader research and skeleton`

---

## 4. feat: embedding lab Mode A

- **`?? Rag_Chat/backend/docs/features/embedding_lab/page.md`** — T2 통합 노트 skeleton (yesterday)
- T2 가 어젯밤 만든 backend/frontend 변경분이 *현 status 에 안 보임* — embedding_views.py / urls.py / embedding_lab.py 모두 흔적 없음. 어제 yesterday T2 가 *Mode A 구현* 까지 가지 않고 doc skeleton 만 남긴 상태로 보인다. 다음 세션이 진행하거나 status 재점검.

메시지: `docs(embedding-lab): Phase A skeleton doc` 또는 코드 추가 후 `feat`.

---

## 5. feat(chunk-lab): heading/clause splitter 옵션 노출 (T2 야간 ✅)

- **`M  Rag_Chat/frontend/pages/chunk_lab.py`** — T2 가 오늘 야간에 splitter selectbox 에 `heading`, `clause` 추가
- **`?? Rag_Chat/backend/docs/sessions/night/T2.work.md` / `T2.learning.md`** — T2 야간 작업 로그·학습

메시지: `feat(chunk-lab): expose heading and clause splitter options`

---

## 6. feat(moderation): Phase A — sensitivity label + ACL retrieval filter (T1 야간 진행 중)

- **`?? Rag_Chat/backend/moderation/levels.py`** — `SENSITIVITY_LEVEL` ladder + `can_access()` (T1)
- **`?? Rag_Chat/backend/moderation/tests/`** — `test_acl.py` 등
- *(상태에 안 보이지만 T1 mission 이 요구)* — `knowledge/models.py` Document.sensitivity, `chat/models.py` User.access_level, migrations 2종, retrieval ACL 필터, redacted_count 응답 추가. status 에 안 잡혀 있다면 T1 미완료 가능 — 진행 직전 확인.
- **`M  Rag_Chat/backend/docs/architecture/security.md`** — 4경계 방어 텍스트 갱신
- **`?? Rag_Chat/backend/docs/superpowers/plans/2026-05-28-moderation-implementation.md`** — Phase A→B→C 실행 plan
- **`?? Rag_Chat/backend/docs/superpowers/specs/2026-05-28-moderation-architecture.md`** — 3-layer 아키텍처 spec
- **`?? Rag_Chat/backend/docs/features/moderation/`** — `learn.md`, `references.md`, `refs/`

메시지: `feat(moderation): phase A label-based access filter`

---

## 7. docs(design-system): DESIGN.md 단일 출처 + 정적 사이트 레이아웃 동기화

- **`?? DESIGN.md`** (루트) — design system 단일 출처
- **`?? Rag_Chat/docs/design/`** — preview 페이지 + tokens.css 등
- **`M  Rag_Chat/docs/_layouts/concept.html`** — design system 토큰 반영
- **`M  Rag_Chat/docs/_layouts/index.html`** — 동일
- **`M  README.md`** — design system link 추가했다면 함께

메시지: `docs(design): introduce DESIGN.md as single source of truth`

---

## 8. docs(meta): CLAUDE.md + _index.md 갱신

- **`?? CLAUDE.md`** (루트) — 프로젝트 메모리 (Triple Chat / Moderation / DESIGN.md)
- **`M  Rag_Chat/backend/docs/_index.md`** — T3 야간이 §3.6/3.7 모더레이션·night_autonomous 추가, §9.2 superpowers 표 확장
- **`?? Rag_Chat/backend/docs/sessions/2026-05-27-night-parallel.md`** — yesterday 4-agent narrative
- **`?? Rag_Chat/backend/docs/sessions/night/T3.work.md`** + T3.learning.md — 본 세션 작업 로그
- **`?? Rag_Chat/backend/docs/reports/night/`** — `build_night_report.py` 산출 HTML
- **`M  Rag_Chat/backend/docs/reports/learning_journey.html`** — §8 멀티에이전트 워크플로우 학습 섹션 추가분
- **`M  Rag_Chat/backend/docs/superpowers/specs/2026-05-27-night-autonomous-multiagent-design.md`** — 야간 spec 갱신

메시지: `docs: refresh _index + night session narrative + CLAUDE.md`

---

## 커밋하지 말 것 (정리)

- `"파수 대외비 문서 관리 및 보안 _ Fasoo 기밀 문서 암호화 및 추적.html"` — DownSub HTML, 1번 commit 전에 `rm` 또는 gitignore.

---

## 작업 순서 제안

> 충돌 표면을 줄이려고 *정리 → 구현 → 통합 doc* 순. 각 commit 직전 `git diff` reality check.

1. **정리 (1번)** — OCR 중복 제거 + 루트 잡파일. 신호잡음 down.
2. **OCR loader (2번)** — `text/ocr.py` 가 단독으로 살아남게.
3. **HWP research (3번)** — 다음 세션 구현 결정 근거 확정.
4. **chunk_lab UI (5번)** — T2 1줄짜리 quick win.
5. **moderation Phase A (6번)** — T1 결과 통합. 가장 큰 commit, *별도* PR 권장 (코드 + 마이그레이션 + 테스트).
6. **embedding lab (4번)** — T2 yesterday skeleton (코드 결과는 status 에 안 보임 — 확인 후).
7. **design system (7번)** — 시각 자산 + tokens.
8. **meta docs (8번)** — `_index` / `CLAUDE.md` / night narrative. 마지막에 인덱스 sync.

각 commit 전 `--no-verify` 절대 X. pre-commit 실패 시 *수정* 후 *새 commit* (amend 금지 — 본 프로젝트 규약).

---

## 관련 문서

- [handoff.md](handoff.md) — env/provider 현재 상태 + 다음 세션 진입점
- [2026-05-27-night-parallel.md](2026-05-27-night-parallel.md) — 어젯밤 4-agent narrative
- [missions.md](missions.md) — 오늘 야간 4-agent 임무판
- [../_index.md](../_index.md) — 전체 문서 인덱스
