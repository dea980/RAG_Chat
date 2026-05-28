# Session — 2026-05-27 Night · 4 Agents in Parallel

> 사용자가 잠들기 전, **이 터미널 (Claude Code 문서화) + 새 Claude Code 2개 + 다른 Claude 1개 = 4개 에이전트** 를
> 동시에 띄워 작업을 분담. Codex 는 토큰 소진으로 제외. 이 문서는 그 분배의 **배경 + 학습 포인트 + 충돌 회피 원칙** 을
> 정리한다. 다음 세션이 결과를 통합할 때의 진입점.

---

## 1. 한 줄 요약

> 단일 사용자가 4개의 LLM 에이전트를 병렬로 돌려 한 코드베이스를 동시에 발전시키는 실험.
> 핵심은 **수직 격리 (vertical isolation)** — 각 에이전트가 자기 디렉토리만 만지고,
> 공유 파일은 단 한 줄만 추가.

---

## 2. 왜 4개로 나눴나 (배경)

### 2.1 단일 에이전트 한계

- 컨텍스트 윈도우 한정 → 4개 분야 (문서/UI/loader/리서치) 를 한 세션에 끌고 가면
  앞단의 결정 근거가 흐려짐.
- 사용자 학습 페이스 — 한 에이전트가 모든 결정을 내리면 사용자가 *보면서 따라가기* 가 어려움.
  여러 갈래로 나누면 한 갈래는 천천히 읽으며 다른 갈래는 빠르게 진행 가능.
- 사람의 검토 부담 분산 — 한 PR 에 다 묶이면 리뷰 단위가 너무 큼.

### 2.2 에이전트별 강점 매칭

| 에이전트 | 강점 | 이번 분배 |
|---|---|---|
| **이 터미널 (Claude Code)** | 멀티 파일 일관성, 문서 narrative, 코드↔doc 매핑 | **T1 · 문서화 / 메모리** |
| **새 Claude Code (UI)** | Streamlit / DRF 패턴 익숙, lazy-load pattern 재사용 | **T2 · Embedding Lab Mode A** |
| **새 Claude Code (Backend)** | 플러그인 등록 + 의존성 추가 + 테스트 | **T3 · Phase 5 OCR loader** |
| **다른 Claude (리서치)** | 라이브러리 비교, 외부 문서 종합 | **T4 · Phase 7-a HWP 리서치** |
| ~~Codex~~ | (단일 알고리즘 정밀 구현) | 토큰 소진 — 제외 |

---

## 3. 충돌 회피 원칙 (Vertical Isolation)

병렬로 코드 만지면 머지 충돌이 가장 무서움. 본 세션은 **파일 단위 수직 격리** 로 해결.

### 3.1 각 에이전트의 "쓰기 권한 영역"

| Agent | 신규 파일 (전용) | 1줄만 추가 (공유) | 절대 금지 |
|---|---|---|---|
| **T1** | `backend/docs/sessions/2026-05-27-night-parallel.md`<br>`backend/docs/sessions/handoff_night.md`<br>`backend/docs/features/embedding_lab/page.md` (skeleton)<br>`backend/docs/features/ingest/phase5_ocr.md` (skeleton)<br>`backend/docs/features/ingest/phase7a_hwp.md` (skeleton) | `backend/docs/_index.md` (line 추가)<br>`backend/docs/sessions/handoff.md`<br>`backend/docs/sessions/commit_split_plan.md`<br>`backend/docs/reports/learning_journey.html` (§8 추가) | 모든 코드 |
| **T2** | `backend/chat/embedding_views.py`<br>`frontend/pages/embedding_lab.py`<br>(테스트는 선택) | `backend/chat/urls.py` (라우트 1줄)<br>`backend/requirements.txt` (`sentence-transformers`) | 다른 모든 곳 |
| **T3** | `backend/chat/ingest/loaders/text/ocr.py`<br>`backend/chat/tests/ingest/test_ocr_loader.py` | `backend/chat/ingest/loaders/__init__.py` (import 1줄)<br>`backend/requirements.txt` (`pytesseract`) | 다른 모든 곳 |
| **T4** | `backend/docs/features/ingest/phase7a_hwp_research.md` (전용) | (없음) | 모든 코드 |

### 3.2 공유 파일 충돌 해소

세 곳이 부딪힐 수 있음:

```
backend/requirements.txt          ← T2, T3 둘 다 의존성 추가
backend/docs/_index.md             ← T1 만 갱신
backend/chat/urls.py               ← T2 만 1줄 추가
backend/chat/ingest/loaders/__init__.py  ← T3 만 1줄 추가
```

`requirements.txt` 만 진짜 공유. 안전 장치:

1. **둘 다 끝에 append** — 줄 추가 위치가 같으니 끝줄에 차례로 쌓음. 머지 충돌 = 단순한 append vs append.
2. **둘 다 commit 안 함** — 사용자가 깨어나 reality check 후 통합 commit.
3. **각 에이전트가 자기 줄에 주석으로 출처 표기**:
   ```
   pytesseract>=0.3.10   # T3: Phase 5 OCR loader
   sentence-transformers>=3.0  # T2: Embedding Lab local models
   ```

### 3.3 왜 *commit 금지* 가 핵심

여러 에이전트가 동시에 commit 하면:
- HEAD 가 한쪽 에이전트만의 시점으로 이동 → 다른 에이전트의 `git status` 가 *상대 작업분을 untracked* 로 인식
- pre-commit hook 이 동시에 돌면 lockfile 충돌
- 사용자가 reality check 할 시점이 없음

**규칙**: T1~T4 모두 *uncommitted leave*. 다음 세션이 통합.

---

## 4. 학습 포인트 — 멀티 에이전트 개발의 핵심

### 4.1 수직 격리 = "디렉토리가 인터페이스"

> 마이크로서비스에서 "Bounded Context" 가 서비스 경계인 것처럼, 멀티에이전트 개발에선
> **디렉토리/파일 경계가 에이전트 경계**.

각 에이전트가 자기 디렉토리만 만지면 머지가 trivial. 공유 파일은 *최소 표면적*
(import 1줄, route 1줄, deps 1줄) 로 줄여서 라인 충돌 가능성을 거의 0 으로.

### 4.2 사용자 = 통합 노드 (Integration Node)

병렬 에이전트는 commit 안 함 → 사용자만이 머지 시점을 결정. 이게 안전한 이유:

- **단일 책임의 결정자** — 어느 에이전트 결과를 채택할지 사람만 판단
- **순차 commit** — 4개 결과를 한 시점에 다 받아서 *순서대로* commit (충돌 시각화 쉬움)
- **취소가 free** — uncommitted 면 `git checkout -- <path>` 한 줄

### 4.3 리서치 에이전트의 가치

T4 는 코드 0줄 — 리서치만. 그런데 이게 다음 세션의 phase 7 구현 시
**가장 큰 시간 절약**:

- 라이브러리 후보 4~5개를 직접 비교한 표 + 권고가 doc 로 남음
- 다음 세션 구현 에이전트는 *결정* 부분을 건너뛰고 *적용* 으로 바로 진입

**리서치를 분리한 이유**: 코드 작성과 비교 분석은 사고 모드가 다름. 한 에이전트가
둘 다 하면 "조사하다 만 채로 코드 박는" 함정에 빠짐.

### 4.4 OPT-IN 으로 작은 단위 → 큰 단위

T2 는 design.md 의 phase A 만 (Pair Compare 1개 모드). B/C/D 는 다음 세션:

- design.md = 풀스펙 청사진 (3 모드)
- T2 작업 = phase A 만 (Mode A + 3 모델)
- 다음 세션 = Mode B / C 확장

> **교훈**: 큰 설계는 그대로 두고, 구현은 *항상 최소 슬라이스* 부터.
> Embedding Lab 의 모든 모드를 한 번에 만들면 4시간 후 통합 불가능. Mode A 만 1시간.

### 4.5 문서화 에이전트의 존재 의의

T1 (이 터미널) 은 코드 0줄. 그러나:

- **결정의 *근거* 가 사라지지 않게** — 왜 4개 에이전트, 왜 수직 격리, 왜 Mode A 만, 왜 리서치 분리 — 코드를 보면 *결과* 는 보이지만 *근거* 는 안 보임. doc 만이 그걸 보존.
- **다음 세션의 진입점** — `handoff_night.md` 가 깨어났을 때 "5분 안에 상황 파악" 을 가능하게 함.
- **`_index.md` 의 무결성** — 새 파일들이 인덱스에 등록 안 되면 *그림자 파일* 이 됨. 인덱스 갱신은 코드 작성 에이전트의 일이 아니라 문서화 에이전트의 일.

---

## 5. 각 터미널의 시작 prompt (재현 가능)

다른 환경에서 같은 구조를 재현하고 싶으면 그대로 복붙:

### T2 — Embedding Lab Mode A

```text
You are working in /Users/daeyeop/Desktop/AI/RAG_Chat/Rag_Chat.
Read backend/docs/features/embedding_lab/design.md first.
Implement ONLY Phase A (Pair Compare, mode A) per §3-4.
Models: gemini + bge-m3 + multilingual-e5 (3 only).
Use lazy-load + @lru_cache pattern from chat/token_utils.py:_encoding_for.
HF ids: bge-m3 → "BAAI/bge-m3", multilingual-e5 → "intfloat/multilingual-e5-large".
Frontend page must mirror token_lab.py shell (set_page_config layout=wide,
BACKEND_URL env fallback, "이 페이지가 무엇" expander).
Files you may touch:
  backend/chat/embedding_views.py (new)
  backend/chat/urls.py (one route line)
  frontend/pages/embedding_lab.py (new)
  backend/requirements.txt (sentence-transformers>=3.0)
Do NOT touch any other files. Do NOT commit.
```

### T3 — Phase 5 OCR Loader

```text
You are working in /Users/daeyeop/Desktop/AI/RAG_Chat/Rag_Chat.
Read backend/docs/architecture/ingest_layer.md (분류 2 OCR section) +
backend/chat/ingest/loaders/text/pdf.py for the loader pattern.
Implement OCR loader at backend/chat/ingest/loaders/text/ocr.py.
Library: pytesseract (assume tesseract binary present; no install).
Korean lang code: 'kor+eng'.
Register via @register decorator for extensions: ['.png', '.jpg', '.jpeg', '.tiff'].
Fixtures already exist: backend/chat/tests/ingest/fixtures/ocr/
  (generated by scripts/build_ocr_fixtures.py).
Files you may touch:
  backend/chat/ingest/loaders/text/ocr.py (new)
  backend/chat/ingest/loaders/__init__.py (one import line)
  backend/chat/tests/ingest/test_ocr_loader.py (new)
  backend/requirements.txt (pytesseract>=0.3.10).
Do NOT touch any other files. Do NOT commit.
```

### T4 — Phase 7-a HWP Research

```text
Research only — no code changes.
Goal: figure out the best Python library to extract text from HWP 5.x files.
Candidates: pyhwp, hwp5txt, olefile + custom, LibreOffice headless (soffice).
Real test file:
  Rag_Chat/backend/chat/tests/ingest/fixtures/special/standard_employment_rules_2026.hwp
  (277KB, 고용노동부 2026 표준 취업규칙).
Output: write findings to
  Rag_Chat/backend/docs/features/ingest/phase7a_hwp_research.md (new).
Compare: install difficulty, Korean accuracy, dependency weight, license,
maintenance status.
Recommend one. Do NOT write loader code.
```

---

## 6. 처리 시점 별 행동 ("깨어났을 때 무엇")

### 6.1 즉시 (sanity)

```bash
cd /Users/daeyeop/Desktop/AI/RAG_Chat
git status --short        # 4개 에이전트 결과 미커밋 파일 확인
git stash list            # stash@{0} 가 그대로 있는지 (GenerationModule + galaxy CSV)
```

기대 결과:
```
 M Rag_Chat/backend/chat/urls.py                              (T2)
 M Rag_Chat/backend/chat/ingest/loaders/__init__.py            (T3)
 M Rag_Chat/backend/requirements.txt                           (T2 + T3 둘 다 라인 추가)
?? Rag_Chat/backend/chat/embedding_views.py                    (T2)
?? Rag_Chat/backend/chat/ingest/loaders/text/ocr.py            (T3)
?? Rag_Chat/backend/chat/tests/ingest/test_ocr_loader.py       (T3)
?? Rag_Chat/frontend/pages/embedding_lab.py                    (T2)
?? Rag_Chat/backend/docs/features/ingest/phase7a_hwp_research.md (T4)
```

(`backend/docs/` 의 T1 작업분도 untracked 로 잡힘 — `sessions/2026-05-27-night-parallel.md`,
`sessions/handoff_night.md`, `features/embedding_lab/page.md`, `features/ingest/phase5_ocr.md`,
`features/ingest/phase7a_hwp.md`.)

### 6.2 통합 순서 (제안)

1. **T1 doc 들 먼저 commit** — narrative 가 남아야 코드 결정의 *맥락* 이 살아있음
2. **T4 리서치 commit** — 다음 코드 commit 의 결정 근거 확정
3. **T3 OCR commit** — Phase 5 완성
4. **T2 Embedding Lab Mode A commit** — feature commit
5. **`_index.md` 갱신 commit** — 마지막에 인덱스 sync

각 commit 직전 `git diff` 로 reality check. `--no-verify` 절대 사용 X.

### 6.3 안 합쳐도 되는 것

- **stash@{0}** — `GenerationModule Korean prompt + galaxy CSV` 는 사용자 본인 작업. 본인이 적절한 시점에 `git stash pop` 하거나 별도 처리.
- **본인 README.md** — IDE 에 열어둔 상태. 본 세션 작업 아님.

---

## 7. 알아둘 위험 (gotchas)

### 7.1 requirements.txt 머지 충돌

T2 와 T3 둘 다 마지막 줄에 append. `git status` 시:
```
both modified:   backend/requirements.txt
```

해결:
```bash
# T2 와 T3 의 추가분이 둘 다 살아남도록 양쪽 줄을 다 보존하면 됨
git diff backend/requirements.txt
# (보고 양쪽 라인 다 있는지 확인)
git add backend/requirements.txt
```

대부분 *둘 다 끝줄에 깔끔히 append* 라 자동 머지 가능.

### 7.2 pytesseract — 시스템 의존성

`pip install pytesseract` 만으로는 부족. **시스템 `tesseract` 바이너리** 가 있어야 함:

```bash
brew install tesseract tesseract-lang   # macOS, 한국어 데이터 포함
```

T3 가 이걸 install 하라고 하지 *말아야* 함 (사용자 권한). 코드는 `pytesseract.TesseractNotFoundError` 발생 시 명확한 안내 메시지를 출력해야.

### 7.3 sentence-transformers — 첫 로드 시 ~2GB 다운로드

T2 가 `bge-m3`, `multilingual-e5-large` 모델을 사용. lazy load 라 import 시점엔 안 받고
*첫 호출 시* `~/.cache/huggingface/` 로 다운로드. 사내 폐쇄망에선:

```bash
export SENTENCE_TRANSFORMERS_HOME=/path/to/pre-downloaded
```

T2 의 page.md 에 이 노트가 들어가야 함 (T1 이 통합 doc 작성 시 포함).

### 7.4 chunk_lab.py UI 1줄 누락

`splitter` 옵션에 `"heading"`, `"clause"` 가 아직 추가 안 됨 (`["recursive", "row"]` 만).
어느 T 도 안 맡음 → **다음 세션 첫 작업** 으로 처리.

---

## 8. 안 한 것 (의도적)

| 안 한 것 | 사유 |
|---|---|
| **5번째 에이전트로 frontend chunk_lab 1줄 패치** | 1줄짜리 작업에 에이전트 1개 띄우는 건 over. 다음 세션 첫 작업 |
| **HWP 코드까지 T4 에 시키기** | 리서치만 분리. 결과 보고 *사용자가* 라이브러리 결정 → 다음 세션이 구현 |
| **Embedding Lab Mode B/C** | 작업량 큼. Mode A 통합 후 별도 phase |
| **자동 머지 스크립트** | 4-way 머지를 자동화하면 사용자가 본인 코드 책임에서 멀어짐. *수동 reality check* 가 의도된 단계 |
| **`build_vectors --rebuild`** | API key 필요. 사용자가 직접 |
| **stash pop / drop** | 사용자 권한 |

---

## 9. 학습 메모 — 사용자에게

이 세션의 가장 중요한 학습 포인트 3가지:

### 9.1 "분배 = 인터페이스 설계"

코드 작성보다 **무엇을 누구한테 시킬지 정하는 단계** 가 더 어렵고 중요.
이 세션에서 사용자가 한 결정:

- Codex 빠진 빈 자리를 *그대로 두지 않고* HWP 리서치로 채움 (T4)
- Embedding Lab 을 *통째로* 시키지 않고 Mode A 만 (T2)
- 문서화 에이전트를 *생략하지 않음* — 코드 결정의 근거 보존 (T1)

→ 인터페이스 설계 = **누가 무엇을 *안 만지는가*** 까지 정하는 일.

### 9.2 "병렬은 가능, 무한 병렬은 불가능"

4개가 동시에 돌고 있어도:
- 공유 파일 (`requirements.txt`, `urls.py`) 의 머지 부담은 사용자 한 명에게 옴
- 8개 띄우면 머지가 사람 능력 초과

**한계**: 사람이 검토 가능한 *동시* 에이전트 수 ≒ 4. 그 이상은 *순차* 가 답.

### 9.3 "문서화는 코드 작성 *전후* 둘 다 필요"

- **전** — design.md (Embedding Lab) 가 있어야 T2 가 spec 따라 구현
- **후** — 본 night-parallel.md 가 있어야 다음 세션이 *왜* 이 분배인지 이해

문서 = *시간을 가로지르는 인터페이스*. T2 가 깨어났을 때 design.md 가 있고,
다음 세션이 깨어났을 때 본 doc 가 있다.

---

## 10. 관련 문서

- [`handoff_night.md`](handoff_night.md) — 깨어났을 때 1페이지 요약 (이 문서의 *결과만*)
- [`handoff.md`](handoff.md) — 일반 세션 핸드오프 (env/provider 상태)
- [`commit_split_plan.md`](commit_split_plan.md) — 미커밋 변경분 커밋 분할 (이번 세션 후 갱신됨)
- [`../features/embedding_lab/design.md`](../features/embedding_lab/design.md) — T2 가 따라 구현한 spec
- [`../features/embedding_lab/page.md`](../features/embedding_lab/page.md) — T2 결과를 받을 통합 doc (skeleton)
- [`../features/ingest/phase5_ocr.md`](../features/ingest/phase5_ocr.md) — T3 결과를 받을 통합 doc (skeleton)
- [`../features/ingest/phase7a_hwp.md`](../features/ingest/phase7a_hwp.md) — T4 결과를 받을 통합 doc (skeleton)
- [`../reports/learning_journey.html`](../reports/learning_journey.html) — §8 멀티에이전트 워크플로우 학습 섹션
