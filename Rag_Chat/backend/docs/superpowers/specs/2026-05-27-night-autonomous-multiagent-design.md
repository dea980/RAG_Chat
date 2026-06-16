# 야간 자율 멀티에이전트 + Wrap-up 시스템 — 설계

> **한 줄**: 사용자가 자는 동안 여러 Claude CLI 터미널이 각자 임무를 자율 수행하고,
> 끝나면(또는 STOP 신호 시) 각자 *작업 리포트 HTML* + *초보 RAG 학습 문서 HTML* 을 생성한다.
> 깼을 때 병합 대시보드 한 장으로 전체를 본다.
>
> 작성일: 2026-05-27 · 접근법: C (하이브리드 — 루프는 md, 파이썬 렌더러가 HTML+병합)

---

## 1. 문제 / 동기

현재 멀티에이전트 병렬 작업(night-parallel 패턴)은 **전부 수동**이다:
- 임무 분배, 세션 docs 작성, HTML 리포트(`learning_journey.html` 등), 핸드오프 — 사람이 직접.
- 자는 동안 터미널이 일은 하지만, 깼을 때 "각 터미널이 뭘 했고 / 거기서 무슨 RAG 개념을 배워야 하나" 가 정리되어 있지 않음.

목표: 이 wrap-up 을 **반복 가능한 자동 워크플로**로 만든다. 사용자는 RAG 초보 → 학습 문서는 디테일하고 비유 중심이어야 함.

## 2. 핵심 결정 (확정)

| 항목 | 결정 |
|---|---|
| 트리거 | **자율 루프** — 각 터미널이 자기 페이스로 작업, 임무 완료 또는 STOP 시 스스로 wrap-up |
| 임무 분배 | **공유 임무 파일 하나** (`sessions/missions.md`) — 기존 night-parallel 패턴 동일 |
| 출력 | 여러 파일 OK, 디테일 우선 (사용자 학습 속도 배려) |
| 포장 방식 | 접근법 C — 루프는 markdown 작성, `build_night_report.py`(jinja2) 가 HTML 렌더 + 병합 |
| 스킬 사용 | 루프 명령 본문에 "알맞은 superpowers 스킬 탐색(TDD/debugging/도메인)" 명시 |
| 커밋 | 각 에이전트 **commit 금지** — uncommitted leave, 사용자가 깨서 통합 (격리 규칙) |

## 3. 파일 배치

```
Rag_Chat/
├── .claude/
│   ├── commands/
│   │   ├── nightwork.md       # /nightwork <Tn>  (루프 명령)
│   │   └── wrapup.md          # /wrapup [<Tn>]   (수동 마무리·HTML 재생성)
│   └── settings.local.json    # allow 규칙 추가 (무인 실행용)
├── backend/
│   ├── scripts/
│   │   └── build_night_report.py   # md → HTML 렌더 + 병합 대시보드
│   └── docs/
│       ├── sessions/
│       │   ├── missions.md         # 공유 임무판 (T1/T2/T3… 섹션)
│       │   └── night/              # 루프가 쓰는 md (source of truth)
│       │       ├── T1.work.md
│       │       ├── T1.learning.md
│       │       ├── T2.work.md
│       │       └── …
│       │       └── STOP            # (선택) 만들면 모든 루프 즉시 wrap-up
│       ├── reports/night/          # 렌더된 HTML (build output)
│       │   ├── T1.html
│       │   ├── T1-learning.html
│       │   ├── T2.html
│       │   └── index.html          # 병합 대시보드 (깼을 때 진입점)
│       └── _layouts/
│           ├── night_report.html   # jinja2 — 작업 리포트
│           ├── night_learning.html # jinja2 — 학습 문서 (learning_journey 톤)
│           └── night_index.html    # jinja2 — 대시보드
```

`scripts/build_concepts.py` 가 패턴의 형(兄). `build_night_report.py` 는 동일한 markdown + jinja2 + frontmatter 패턴을 따른다.

## 4. 컴포넌트별 명세

### 4.1 `sessions/missions.md` — 공유 임무판

- 헤더: 날짜, 격리 규칙 요약, 상태 범례.
- 섹션: 터미널마다 `## T1`, `## T2` … 각 섹션에:
  - **목표** (한 줄), **임무 항목** (체크리스트), **쓰기 권한 영역** (전용 파일 / 1줄 공유 / 절대 금지), **완료 정의**(done criteria).
- night-parallel.md 의 표 3.1 구조 재사용.

### 4.2 `.claude/commands/nightwork.md` — 루프 명령

입력: `/nightwork T2` (`$1` = 터미널 ID).

동작 순서:
1. `sessions/missions.md` 읽기 → `$1` 섹션만. 격리 영역 / 완료 정의 확인.
2. 알맞은 스킬 탐색·사용 — 구현이면 TDD, 버그면 debugging, 도메인 스킬. (명령 본문에 명시.)
3. 임무 항목을 하나씩 작업. 항목 완료마다 `night/$1.work.md` 에 *무엇을·왜·어떻게·바뀐 파일·테스트 결과* 추가(append).
4. 매 반복 시작 시 `night/STOP` 존재 확인 → 있으면 즉시 5로.
5. 임무 전부 완료 OR STOP → **wrap-up**:
   - `night/$1.learning.md` 작성 — 이번 작업이 건드린 RAG 개념을 초보용으로 (비유 + "왜" 섹션 + 연습문제).
   - `python backend/scripts/build_night_report.py --terminal $1` 호출 → HTML 생성.
6. 자기 영역만 수정. **commit 안 함.** 종료.

자기 페이스 지속을 위해 `/loop` self-pace 를 얹는다 — 일찍 멈추면 깨워 이어감.

### 4.3 `.claude/commands/wrapup.md` — 수동 마무리

- 인자 없으면 전체, `/wrapup T2` 면 해당 터미널만.
- 루프 밖에서 학습 md 생성 + 렌더러 호출. 디버그·재생성용.

### 4.4 `backend/scripts/build_night_report.py` — 렌더러

- 입력: `sessions/night/*.work.md`, `*.learning.md` (frontmatter + body).
- 템플릿: `_layouts/night_*.html` (jinja2).
- 출력: `reports/night/<Tn>.html`, `<Tn>-learning.html`, `index.html`.
- 플래그: `--terminal <Tn>` (해당 터미널만), 없으면 전부 + 대시보드 재빌드.
- frontmatter 필드: `terminal`, `title`, `status`, `mission`, `updated`.
- `build_concepts.py` 의 frontmatter 파싱 / jinja2 환경 / `:::block` 처리 재사용.

### 4.5 출력 3종 (터미널당 2 + 공유 1)

| 파일 | 내용 | 독자 |
|---|---|---|
| `reports/night/<Tn>.html` | 작업 리포트 — 한 일, 바뀐 파일, 결정 근거, 테스트 결과 | 검토 |
| `reports/night/<Tn>-learning.html` | 초보 RAG 학습 — 그 작업이 건드린 개념, 비유, "왜", 연습 | 학습 |
| `reports/night/index.html` | 병합 대시보드 — T1~Tn 한 줄 요약 + 상태 + 링크 | 핸드오프 진입점 |

학습 문서 톤은 기존 `reports/learning_journey.html` 과 동일(다크모드 CSS 포함).

### 4.6 `.claude/settings.local.json` — 권한 (무인 실행)

allow 추가:
```
Bash(python3:*)
Bash(pytest:*)
Bash(git status:*)
Bash(git diff:*)
Bash(git add:*)
```
**의도적으로 allow 안 함 (= 막힘):** `git commit`, `git push`, `rm -rf`, `git reset --hard`, `.env` 수정, 남의 터미널 영역. 격리 + 안전.

## 5. 데이터 흐름

```
missions.md ──(읽기)──> /nightwork Tn (루프)
                              │ 작업 + 스킬
                              ▼
                    night/Tn.work.md  (append)
        STOP 감지 / 임무 완료 ─┐
                              ▼
                    night/Tn.learning.md (작성)
                              │ build_night_report.py
                              ▼
        reports/night/{Tn.html, Tn-learning.html, index.html}
                              │
            (사용자 깸) ──> index.html 진입 ──> reality check ──> 통합 commit
```

## 6. 에러 / 엣지 케이스

- **루프가 중간에 막힘(blocked)**: `Tn.work.md` 에 `status: blocked` + 막힌 이유 기록 후 wrap-up. 대시보드에 빨간 상태.
- **md 없는데 렌더 호출**: 렌더러가 skip + 경고, 크래시 안 함.
- **STOP 파일 잔존**: wrap-up 후 STOP 삭제 안 함(다른 터미널도 봐야 함). 사용자가 새 세션 시작 전 수동 삭제. (missions.md 에 명시.)
- **권한 프롬프트로 새벽에 정지**: settings.local.json allow 로 예방. 빠진 명령 발견 시 추가.
- **두 터미널이 같은 공유 파일(requirements.txt) append**: 끝줄 append + 출처 주석, commit 금지로 충돌 최소화 (기존 night-parallel 3.2 규칙).
- **`.omc/state` 를 조율에 쓰지 말 것**: OMC 세션별 로컬 기계 상태(`subagent-tracking`/`idle-notif-cooldown` 등)이며 gitignored. 별도 터미널은 여기 안 잡히고, 여러 세션이 동시에 덮어쓰므로 신뢰 불가. 야간 조율은 오직 파일 규칙(`missions.md` + `night/` + `STOP`)으로 한다.

## 7. 테스트 전략

- `build_night_report.py` 단위 테스트: frontmatter 파싱, 빈 입력 skip, `--terminal` 필터, 대시보드 집계.
- 픽스처: 샘플 `work.md` / `learning.md` → 렌더 → HTML 에 기대 섹션 존재 확인.
- 수동 검증: `/wrapup T1` 로 1개 터미널 e2e 1회.

## 8. 범위 밖 (YAGNI)

- 자동 통합/머지 — 사용자가 깨서 함.
- 실시간 진행 대시보드 / 웹소켓 — 정적 HTML 로 충분.
- 터미널 간 메시지 패싱 — 수직 격리로 불필요.
- STOP 외 다른 신호 채널(슬랙 등).

## 9. 미해결 / 구현 시 확정

- `night_learning.html` 템플릿이 `learning_journey.html` CSS 를 공유 파일로 뽑을지, 인라인 복제할지 (구현 시 결정 — 공유 권장).
- `/loop` self-pace 와 `nightwork.md` 의 결합 형태 (명령이 loop 를 부르는지, 사용자가 `/loop /nightwork Tn` 로 감싸는지).
