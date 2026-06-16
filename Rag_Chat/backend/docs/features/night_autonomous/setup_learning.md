# 야간 자율 멀티에이전트 — 셋업 학습 노트

> **무엇**: 사용자가 자는 동안 여러 Claude Code 터미널이 독립 임무를 수행하고, 깨었을 때 통합 가능한 결과를 남기는 인프라를 구축한 작업의 *왜* + *어떻게* 정리.
> **언제**: 2026-05-28 야간 셋업.
> **이전 맥락**: [`../../sessions/2026-05-27-night-parallel.md`](../../sessions/2026-05-27-night-parallel.md) — 어젯밤 수동 4-agent 분배의 학습이 본 인프라의 동기.
> **참조 plan**: [`../../superpowers/plans/2026-05-27-night-autonomous-multiagent.md`](../../superpowers/plans/2026-05-27-night-autonomous-multiagent.md)
> **참조 spec**: [`../../superpowers/specs/2026-05-27-night-autonomous-multiagent-design.md`](../../superpowers/specs/2026-05-27-night-autonomous-multiagent-design.md)

본 문서는 *튜토리얼* 이 아니라 *결정의 일지*. 각 task 가 어떤 함정을 피하기 위해 어떤 모양을 택했는지를 다음 세션이 5분 안에 파악할 수 있게.

---

## 한눈에 — 셋업 결과

| 산출물 | 위치 | 역할 |
|---|---|---|
| 공유 임무판 | `backend/docs/sessions/missions.md` | 자기 전에 채우고, 각 터미널이 자기 섹션만 읽음 |
| 야간 작업 소스 | `backend/docs/sessions/night/<Tn>.work.md` · `<Tn>.learning.md` | 각 터미널이 작성 (commit 금지) |
| HTML 출력 | `backend/docs/reports/night/index.html` + `<Tn>.html` + `<Tn>-learning.html` | 깨었을 때 진입점 |
| 렌더러 | `backend/scripts/build_night_report.py` (+ test_*.py) | markdown → HTML, 단독 실행 (Django 미의존) |
| jinja2 템플릿 | `backend/docs/_layouts/night_{base,report,learning,index}.html` | learning_journey.html 의 스타일 재사용 |
| 슬래시 커맨드 | `.claude/commands/{nightwork,wrapup}.md` | `/nightwork T1` / `/wrapup` |
| 권한 화이트리스트 | `.claude/settings.local.json` | 빌드·테스트·git add 만 무프롬프트 |
| 스캐폴드 | `backend/docs/sessions/night/.gitkeep` | 빈 디렉토리를 git 에 보존 |

---

## Task 1 — missions.md (공유 임무판)

### 왜
- 4개 터미널이 *어디까지* 자기 영역인지 모르면 동일 파일을 동시 수정 → 머지 지옥.
- 자기 전에 *한 곳* 에 적어두면 각 터미널은 자기 섹션만 읽어도 충돌 회피 가능.
- 어젯밤 수동 분배(2026-05-27-night-parallel.md) 에서 *암묵적* 으로 한 일을 *명시적* 인 단일 파일로 승격.

### 어떻게
- 섹션 = 터미널 (## T1, ## T2, ## T3).
- 각 섹션 필수 4 항목: **목표** / **임무 항목 체크리스트** / **쓰기 권한 영역**(전용·공유·금지 3분류) / **완료 정의**.
- STOP 신호 = `backend/docs/sessions/night/STOP` 파일. 매 항목 시작 전 존재 체크 → 있으면 즉시 wrap-up. *파일 존재 여부* 만 보는 이유: race condition 없음, 도구 의존 없음(grep/touch 만).
- 오늘 missions: T1=Moderation Phase A · T2=chunk_lab splitter 옵션 · T3=문서 통합.

### 학습 포인트
> **공유 파일 = 인터페이스 명세**. 마이크로서비스의 OpenAPI 스펙처럼, missions.md 는 "에이전트 A 가 에이전트 B 에게 무엇을 약속하는가" 의 정적 문서.
- 체크리스트(`- [ ]`) 가 단순한 진행률 표시가 아니라, 실패 시 *어디까지 됐는지* 의 흔적이 됨.
- 권한 영역의 *금지* 항목이 *전용* 항목보다 중요 — "뭐는 만져도 된다" 보다 "뭐는 절대 안 된다" 가 사람의 두뇌 부하를 줄임.

---

## Task 2 — jinja2 night templates

### 왜
- 4개 페이지(base/report/learning/index)를 각자 풀 HTML 로 작성하면 헤더·CSS 가 4벌 → 한 곳만 고쳐도 다른 3곳이 어긋남.
- 이미 `learning_journey.html` 의 톤(💡/✅/⚠️ 박스, 다크모드, Pretendard)이 사용자 학습용으로 검증됨 → 새로 디자인하지 말고 재사용.

### 어떻게
- `night_base.html` 이 CSS + page chrome 보유. `{% block content %}` 가 자식의 진입점.
- `night_report.html`, `night_learning.html`, `night_index.html` 이 `{% extends "night_base.html" %}` 로 상속 → 본문만 다르고 나머지 동일.
- learning_journey.html 의 CSS (`:root` 변수, 다크모드, `.analogy`/`.tip`/`.warn`/`.exercise` 박스) 를 그대로 복사 + night 전용 추가:
  - `.status-pill` 4종 (done/active/blocked/planned) — 대시보드 카드 상태 시각화
  - `.card` — 대시보드의 터미널 한 칸
- 검증: `python3 -c "from jinja2 import Environment, FileSystemLoader; env=...; env.get_template(t)"` 로 4개 다 load 되는지 확인 (구조 검증).

### 학습 포인트
> **상속 1단(base ← 3 children) 이 평면 4파일보다 항상 낫다**. CSS 1줄 수정 → 4곳 자동 반영.
- jinja2 의 `{% block %}` 은 함수 시그니처와 같음: 자식이 *오버라이드 가능한 슬롯* 을 선언.
- 학습용 박스 클래스(`analogy`/`tip` 등) 를 `night_base.html` 에 같이 두면, learning.md 본문에서 raw HTML `<div class="analogy">` 를 쓸 수 있음 (markdown 통과).

---

## Task 3 — build_night_report.py (TDD)

### 왜
- 렌더러를 Django 명령어로 만들면 `manage.py` 의 환경 부팅(DB 연결, settings.py) 이 필요 → 사용자가 모델 마이그레이션 중이거나 DB 꺼져 있으면 빌드 실패.
- 야간 wrap-up 은 *DB-agnostic* 이어야 함. → 스탠드얼론 파이썬 스크립트. `python backend/scripts/build_night_report.py` 한 줄.
- TDD 를 적용한 이유: 출력이 *HTML 파일* 이라 눈으로만 보면 회귀를 놓치기 쉬움. 핵심 4가지(파일 존재 · 본문 포함 · 필터 동작 · 잘못된 입력 스킵) 를 자동화.

### 어떻게
- TDD 순서:
  1. `test_build_night_report.py` 3개 케이스 작성 → `pytest` 실행 → `ModuleNotFoundError` 로 fail (예상)
  2. `build_night_report.py` 구현 → 다시 `pytest` → 3 passed
- 3 케이스 설계:
  - **happy path** — work.md + learning.md → T1.html / T1-learning.html / index.html 모두 생성, 본문 키워드 포함
  - **filter 동작** — `--terminal T2` 호출 시 T1 페이지는 안 만들지만 *대시보드는 여전히 T1·T2 모두 요약* (Task 의도: 부분 빌드해도 인덱스는 전체 상태)
  - **frontmatter 누락 스킵** — `---` 없는 파일은 경고 후 skip, 빈 대시보드는 정상 생성
- 데이터 모델: `@dataclass NightDoc(terminal, title, status, mission, updated, body_md)` — frontmatter YAML → 객체화. `status` enum 은 `STATUS_CLASS` 매핑으로 CSS class 결정.
- 인덱스 항상 재빌드 이유: 부분 빌드(`--terminal T2`)에도 대시보드는 *모든 터미널 현재 상태* 를 반영해야 깨었을 때 "T1 은 아직 안 끝났구나" 가 보임.

### 학습 포인트
> **TDD = 회귀 방지 자동화**. 향후 템플릿 변수명을 바꾸거나 frontmatter 키를 추가할 때 3 케이스가 안전망.
- `tmp_path` (pytest fixture) 로 격리된 디렉토리에서 빌드 → 실제 `backend/docs/sessions/night/` 를 오염시키지 않음.
- `sys.path.insert(0, str(SCRIPTS))` 로 `scripts/` 를 import path 에 추가 — Django app 으로 만들지 않고도 모듈처럼 import 가능.
- `re.compile(r"^(?P<tn>T\d+)\.work\.md$")` 로 파일명 패턴 검증 — 임의 파일이 source dir 에 떨어져도 무시.

---

## Settings 보완 — `.claude/settings.local.json`

### 왜
- 야간 자율 루프 중 *권한 프롬프트* 가 뜨면 사용자가 자는 동안 멈춤. 빌드·테스트·읽기 명령은 사전 허용 필요.
- 반면 `git commit` 은 *의도적으로* 허용 안 함 — 4개 에이전트가 동시 commit 하면 HEAD 가 한쪽으로 이동하며 다른 에이전트가 본인 작업분을 untracked 로 인식 (어젯밤 학습).

### 어떻게
- 기존 settings.local.json 에 `Bash(git add:*)` 1줄 추가. (`commit` 은 제외 유지 — 격리 규칙 강제 수단)
- 허용 범위:
  - `python(3)? -m pytest:*` · `pytest:*` — 테스트
  - `python(3)? backend/scripts/build_night_report.py:*` — 렌더러
  - `git status:*` · `git diff:*` · `git add:*` — 상태 확인 + 스테이징(but no commit)
  - `python3 -c "import markdown..."` — 의존성 확인 1회
- JSON 유효성: `python3 -c "import json; json.load(open('...'))"` 로 검증.

### 학습 포인트
> **허용리스트 = 보안 + 자동화의 균형**. 모든 명령 허용은 위험, 모두 차단은 자율 진행 불가. *읽기·빌드는 허용, 기록은 사용자* 가 안전한 분할.
- `.claude/` 가 `.gitignore` 에 포함되어 있어 settings.local.json/nightwork.md/wrapup.md 는 commit 되지 않음. 이는 의도된 동작 — 각 개발자가 본인 환경에 맞게 튜닝.
- plan T6 의 commit 단계는 본 repo 에서 실패(`Rag_Chat/.claude` ignored) → plan 의 가정 오류로 기록. 다음 plan 작성 시 `.gitignore` 사전 확인 필요.

---

## Tasks 4·5 — `/nightwork`, `/wrapup` 슬래시 커맨드

### 왜
- 야간 자율 루프의 *입구* 는 단순해야 함. 사용자가 자기 전 터미널마다 `/nightwork T1` 한 번 치면 끝.
- 동일 prompt 를 4 터미널에 복붙하지 않고 슬래시 커맨드로 캡슐화.

### 어떻게
- `.claude/commands/nightwork.md` — frontmatter 의 `argument-hint: <Tn>` 로 자동완성에 힌트 표시. `allowed-tools: Read, Edit, Write, Bash, Grep, Glob, TodoWrite, Skill` 로 도구 범위 제한.
- 본문에 5 섹션 명시:
  1. 임무 파악 (missions.md 의 본인 섹션만)
  2. 스킬 탐색 필수 (1% 라도 맞으면 invoke — superpowers 정책)
  3. 작업 루프 (매 항목 시작 전 STOP 체크)
  4. Wrap-up (work.md status 갱신 + learning.md 작성 + HTML 빌드)
  5. 자기 페이스 (`/loop` 으로 self-pace 가능)
- `/wrapup` 은 *수동* 마무리 — 중간에 사용자가 깨거나 일부 터미널만 끝났을 때 학습 문서를 보강하고 HTML 만 다시 빌드.

### 학습 포인트
> **슬래시 커맨드 = 재현 가능한 prompt 의 함수화**. prompt 가 코드처럼 버전 관리 가능(.claude/ 가 ignored 라도 로컬 디스크에선 변경 추적 가능).
- `argument-hint` 가 사용자 입력 실수를 줄임 — `Tn` 형식 강제.
- learning.md 본문에 raw HTML 박스(`<div class="analogy">`) 를 쓰도록 명시 — markdown 이 통과시키기 때문에 jinja2 까지 그대로 흘러감.

---

## Task 7 — Scaffold + e2e smoke

### 왜
- 빈 디렉토리는 git 에 보존되지 않음 → `.gitkeep` 로 source dir(`backend/docs/sessions/night/`) 를 미리 만들어 두지 않으면, 다음 clone 시 렌더러가 `no source dir` 로 실패.
- 인프라가 *실제로 돌아가는지* 모든 부품(missions → 템플릿 → 렌더러 → HTML) 을 한 번 통째로 흐름 검증해야 함.

### 어떻게
- `mkdir -p backend/docs/sessions/night && touch .gitkeep` — 디렉토리 + 빈 마커.
- T0 스모크: 가짜 work.md + learning.md 생성 → 렌더러 실행 → 3 파일 출력 확인 → 본문에 `T0` 와 `스모크` 포함 확인.
- 검증 후 T0 정리, 빈 대시보드 재빌드 → 최종 상태는 *깨끗한 scaffold*.

### 학습 포인트
> **e2e smoke 1회 + 정리** 가 단위 테스트 100개보다 *통합 실패* 를 잘 잡음.
- `.gitkeep` 는 관용 — git 이 이해하는 특수 이름이 아니라, 단지 빈 디렉토리에 *아무 파일이라도* 있게 만드는 placeholder.
- 정리(`rm`) 까지 *셋업의 일부* — 실제 야간 작업이 시작될 때 source dir 이 비어있어야 첫 wrap-up 결과가 깨끗.

---

## 통합 학습 — 본 셋업이 가르치는 3가지

### 1. 자율 = 사전에 결정해 둔 규칙의 집합
> "자율" 은 무규칙 자유가 아니라, *판단할 필요 없는 결정* 을 미리 박아두는 일.
- missions.md 의 권한 영역 → 에이전트가 "이 파일 만져도 되나?" 고민할 필요 없음.
- settings.local.json 의 allowlist → "이 명령 실행해도 되나?" 프롬프트 없음.
- STOP 신호 파일 → "지금 멈춰야 하나?" 의 답이 단일 ls 호출.

### 2. 격리 = 신뢰의 비용
- 4 에이전트가 commit 안 함 → 통합 시점에 사람만이 *어느 결과 채택할지* 결정.
- `.claude/` 가 ignored → 각 개발자가 본인 환경 튜닝, 팀 합의는 별도 채널(plan/spec doc).
- TDD 가 렌더러를 격리 → 다른 부품(템플릿, missions 포맷) 이 흔들려도 렌더러 회귀는 즉시 탐지.

### 3. 깼을 때 5분 안에 상황 파악
> 모든 산출물이 *깨었을 때의 진입점* 으로 수렴해야 함.
- 진입점 = `backend/docs/reports/night/index.html` (브라우저로 더블클릭)
- 거기서 각 터미널 카드 → 작업 리포트 + 학습 문서로 분기
- 통합 commit 순서: doc → research → 코드 → index 갱신 (어젯밤 학습)

---

## 다음 단계 (오늘 밤 실행)

1. `Rag_Chat/backend/docs/sessions/missions.md` 의 T1/T2/T3 섹션 *내용 검토* — 이미 채워두었으나 시작 전 한 번 더 확인.
2. 3개 터미널 띄우고 각각:
   ```
   /nightwork T1
   /nightwork T2
   /nightwork T3
   ```
3. (선택) 각 터미널에서 `/loop /nightwork T1` 로 self-pace 가능.
4. 자다가 깨거나 멈추고 싶으면: `touch backend/docs/sessions/night/STOP`
5. 깨었을 때: `backend/docs/reports/night/index.html` 브라우저로 열기.
6. 통합 commit 은 사용자가 직접 — `Rag_Chat/backend/docs/sessions/commit_split_plan.md` 참고.

---

## 관련 문서

- [`../../sessions/missions.md`](../../sessions/missions.md) — 오늘 밤 임무
- [`../../sessions/2026-05-27-night-parallel.md`](../../sessions/2026-05-27-night-parallel.md) — 어젯밤 수동 4-agent 의 학습 (본 인프라의 동기)
- [`../../superpowers/plans/2026-05-27-night-autonomous-multiagent.md`](../../superpowers/plans/2026-05-27-night-autonomous-multiagent.md) — 본 인프라의 plan
- [`../../superpowers/specs/2026-05-27-night-autonomous-multiagent-design.md`](../../superpowers/specs/2026-05-27-night-autonomous-multiagent-design.md) — 본 인프라의 spec
- [`../../reports/learning_journey.html`](../../reports/learning_journey.html) — night 템플릿이 톤·CSS 를 상속한 원본
- [`../../superpowers/plans/2026-05-28-moderation-implementation.md`](../../superpowers/plans/2026-05-28-moderation-implementation.md) — 오늘 밤 T1 미션의 참조 plan
