# Night Missions — 2026-05-28

> 야간 병렬 세션의 공유 임무판. 각 터미널은 시작 시 `/nightwork <Tn>` 로 자기 섹션만 읽는다.
> 핵심 규칙: **수직 격리** — 자기 전용 파일만 만들고, 공유 파일은 끝줄에 1줄 append + 출처 주석.
> 아무도 commit 하지 않는다. 사용자가 깨서 통합한다.

상태 범례 — ✅ done · 🟢 active · ⛔ blocked · ⏳ planned

## STOP 신호
`backend/docs/sessions/night/STOP` 파일을 만들면 모든 터미널이 다음 항목 시작 전 감지하여
즉시 wrap-up 한다. 새 세션 시작 전 사용자가 이 파일을 지운다.

---

## T1
- **목표**: Moderation Phase A — sensitivity label + access_level + retrieval filter 구현
- **임무 항목**:
  - [ ] `knowledge/models.py` 에 `Sensitivity` enum + `Document.sensitivity` / `sensitivity_set_by` / `sensitivity_set_at` 추가
  - [ ] `chat/models.py` 의 `User` 에 `access_level` 필드 추가 (default=INTERNAL)
  - [ ] `moderation/levels.py` 신규 — `SENSITIVITY_LEVEL` ladder + `can_access()` helper
  - [ ] `python manage.py makemigrations knowledge chat` 후 `migrate`
  - [ ] `chat/build_vector_store.py` (또는 ingest 파이프라인) 에 `should_index()` 추가 — restricted skip + chunk meta에 sensitivity 복사
  - [ ] retrieval 함수에 ACL 필터 적용 — response 에 `redacted_count` 키 포함
  - [ ] `moderation/tests/test_acl.py` 신규 — `AclLevelTest` + `RetrievalAclTest` 통과
  - [ ] Phase A Exit Criteria (plan §A.6) 전부 체크
- **쓰기 권한 영역**:
  - 전용(자유 생성/수정):
    `Rag_Chat/backend/moderation/levels.py`
    `Rag_Chat/backend/moderation/tests/test_acl.py`
    `Rag_Chat/backend/knowledge/migrations/0NNN_document_sensitivity.py` (auto)
    `Rag_Chat/backend/chat/migrations/0NNN_user_access_level.py` (auto)
  - 수정 가능 (자기 책임 하):
    `Rag_Chat/backend/knowledge/models.py`
    `Rag_Chat/backend/chat/models.py`
    `Rag_Chat/backend/chat/build_vector_store.py` (또는 retrieval 모듈)
    `Rag_Chat/backend/chat/views.py` (retrieval 호출처)
  - 공유(끝줄 1줄 append + `# T1:` 출처 주석): 없음 (Phase A 는 requirements 추가 없음)
  - 금지: `Rag_Chat/frontend/**`, `Rag_Chat/backend/docs/**`, T2/T3 영역 전부
- **완료 정의**:
  - `python -m pytest moderation/tests/test_acl.py -v` 모두 통과
  - migration 적용 후 `Document.objects.first().sensitivity` 가 'internal'
  - retrieval response 에 `redacted_count` 포함되는 integration 테스트 통과
  - work.md + learning.md + HTML 빌드 완료
- **참조**:
  - plan: `Rag_Chat/backend/docs/superpowers/plans/2026-05-28-moderation-implementation.md` §Phase A
  - spec: `Rag_Chat/backend/docs/superpowers/specs/2026-05-28-moderation-architecture.md`
  - 학습 노트: `Rag_Chat/backend/docs/features/moderation/learn.md`

---

## T2
- **목표**: `frontend/pages/chunk_lab.py` 의 splitter selectbox 에 `"heading"`, `"clause"` 옵션 추가 — Phase 3/4 splitter UI 노출
- **임무 항목**:
  - [ ] `Rag_Chat/frontend/pages/chunk_lab.py` 의 splitter `selectbox` 옵션 리스트 확인
  - [ ] 현재 `["recursive", "row"]` → `["recursive", "row", "heading", "clause"]` 로 확장
  - [ ] 백엔드 호출 시 `splitter` 파라미터가 그대로 전달되는지 확인 (이미 동작하는지 dry-run)
  - [ ] 새 옵션 선택 시 정상 응답 받는지 페이지에서 수동 시뮬 (백엔드 splitter 매핑 파일 확인)
  - [ ] Streamlit 페이지 한 번 새로고침해 정상 작동 시각 확인 (백엔드 미기동 시 mock 응답 또는 graceful 에러 메시지 확인)
- **쓰기 권한 영역**:
  - 전용(자유 수정): `Rag_Chat/frontend/pages/chunk_lab.py`
  - 공유: 없음 (1줄 패치)
  - 금지: backend 코드 전체, docs 전체, T1/T3 영역
- **완료 정의**:
  - chunk_lab.py 의 splitter 옵션에 `heading`/`clause` 가 노출됨
  - Streamlit 시작 시 import error 없음 (`streamlit run` 까지는 안 해도 됨 — `python -c "import ast; ast.parse(open('Rag_Chat/frontend/pages/chunk_lab.py').read())"` 통과)
  - work.md + learning.md + HTML 빌드 완료
- **참조**:
  - 현재 splitter 등록 위치는 `Rag_Chat/backend/chat/ingest/loaders/text/__init__.py` 또는 `chat/chunkers/` (grep으로 확인)
  - 작업 분리 사유: `backend/docs/sessions/2026-05-27-night-parallel.md` §7.4

---

## T3
- **목표**: 어젯밤 4-agent 결과 통합 문서화 — `_index.md` sync + 새 doc 들 cross-link + commit-split-plan 갱신
- **임무 항목**:
  - [ ] `Rag_Chat/backend/docs/_index.md` 에 신규 doc 5개 등록 라인 추가:
    - `features/embedding_lab/page.md`
    - `features/ingest/phase5_ocr.md`
    - `features/ingest/phase7a_hwp.md`
    - `features/ingest/phase7a_hwp_research.md`
    - `features/moderation/learn.md` (디렉토리 존재 시)
  - [ ] `Rag_Chat/backend/docs/sessions/commit_split_plan.md` 를 현재 `git status` 와 동기화 — 어떤 untracked 파일이 어느 commit 묶음에 들어갈지 정리
  - [ ] `Rag_Chat/backend/docs/sessions/handoff.md` 의 "다음 세션 진입점" 섹션을 오늘 야간 결과 + Phase A 진행 상태로 업데이트
  - [ ] 신규 skeleton doc (`features/embedding_lab/page.md`, `features/ingest/phase5_ocr.md`, `features/ingest/phase7a_hwp.md`) 가 비어있으면 *플레이스홀더 채워두기* — 다음 세션 작성자가 5분 안에 맥락 잡도록
  - [ ] Cross-link 검증: 새 doc 들이 서로/`_index.md`/`night-parallel.md` 로 모두 양방향 연결
- **쓰기 권한 영역**:
  - 전용/수정:
    `Rag_Chat/backend/docs/_index.md`
    `Rag_Chat/backend/docs/sessions/commit_split_plan.md`
    `Rag_Chat/backend/docs/sessions/handoff.md`
    `Rag_Chat/backend/docs/features/embedding_lab/page.md`
    `Rag_Chat/backend/docs/features/ingest/phase5_ocr.md`
    `Rag_Chat/backend/docs/features/ingest/phase7a_hwp.md`
  - 공유: 없음 (doc 작업 단독)
  - 금지: 모든 코드 (`*.py`, `*.html` 템플릿, frontend), T1/T2 영역
- **완료 정의**:
  - `_index.md` 가 `find Rag_Chat/backend/docs -name "*.md" | wc -l` 와 같은 개수 (cross-link 무결성)
  - commit_split_plan.md 가 현재 `git status` 와 일치 (수동 확인)
  - work.md + learning.md + HTML 빌드 완료
- **참조**:
  - 어젯밤 컨텍스트: `Rag_Chat/backend/docs/sessions/2026-05-27-night-parallel.md`
  - 통합 doc 정책: 동 문서 §4.5 (`_index.md` 의 무결성)
