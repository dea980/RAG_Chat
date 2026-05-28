# Triple Chat — Project Memory

내부 RAG Q&A 시스템. 영업·지원팀이 제품 스펙을 자연어로 묻고, 출처와 함께 답변받는 사내 챗봇.

## Design System
**모든 시각적·UI 결정은 [DESIGN.md](./DESIGN.md)를 단일 출처로 한다.**
- 폰트(Pretendard + Geist Mono), 컬러 토큰(#0A0B0D 베이스 + #E89B3C 액센트), 간격(4px base), 모션 — 전부 거기에 정의됨.
- Streamlit / 포트폴리오 페이지 / 미래 Next.js 프론트 **세 표면 모두** 이 토큰을 따른다.
- 미승인 채로 design system을 벗어나지 말 것. QA 모드에서는 DESIGN.md와 일치하지 않는 코드를 플래그.
- 시그니쳐: assistant 메시지 아래 **citation chip horizontal ribbon** (amber `#E89B3C` 보더). 다른 챗 UI처럼 출처를 푸터에 숨기지 않는다.
- 거절·차단 시각 패턴은 빨강 배너 금지. `warning border + 사유 + 다음 단계`.

## Moderation (대외비·욕설 방어)
**관리자가 코드 없이 튜닝할 수 있어야 한다** — 이게 메인 요구사항. 하드코딩된 필터는 첫 분기에 죽는다.
- 4경계 방어 — **업로드** / **질문** / **검색결과** / **답변** 모두 차단·마스킹·경고 가능.
- 운영자 검수 UI(`/admin/moderation/`): 카테고리(욕설·대외비·PII·자체) · 패턴(키워드·regex·임베딩 유사도) · 적용 경계 체크박스 · severity(BLOCK→error, MASK→warning, WARN→info) · 트리거 카운트 · **실시간 테스트 패널**(샘플 입력 → 결과 즉시 표시).
- 4경계 동일 감사 스키마(누가·언제·무엇·규칙·결과) — incident 사후 추적 비용 절감.
- 무성 드롭 금지: retrieval에서 차단된 chunk는 citation에 `[수정됨·1건]`으로 가시화. 사용자가 결과 누락을 알아야 신뢰 유지.

## Architecture (요약)
- Frontend: Streamlit (`Rag_Chat/frontend/`) — 챗(`chat.py`), 페이지(`pages/chunk_lab.py`, `token_lab.py`)
- Backend: Django REST Framework (`Rag_Chat/backend/`)
- Async: Celery worker + beat (vector build, session cleanup)
- Session·Cache: Redis (TTL = User.expired_datetime 정렬)
- DB: PostgreSQL 16 (SQLite fallback)
- Vector: FAISS / Chroma
- Reranker: ONNX `BAAI/bge-reranker-v2-m3` (현재 브랜치: feature/onnx-reranker)
- 5 providers (Gemini · Qwen · OpenRouter · Ollama · HuggingFace) — env 기반 스왑, 코드 변경 없음

## Learning Docs (학습 문서)
**모든 작업 완료 시 `docs/learning/` 에 학습 문서를 함께 생성한다.**
- 위치: `Rag_Chat/backend/docs/learning/` (백엔드) 또는 `Rag_Chat/docs/learning/` (프론트/공통)
- 파일명: `YYYY-MM-DD-<slug>.md` (예: `2026-05-28-acl-filter-wiring.md`)
- 대상 독자: **이 코드를 처음 보는 주니어 개발자**. 전문 용어는 반드시 풀어 설명.
- 필수 섹션:
  1. **한 줄 요약** — 이 작업이 뭔지 한 문장
  2. **비유** — 일상 사물에 빗대어 핵심 개념 설명 (회사 문서고 출입증, 우편함 등)
  3. **왜 이게 필요한가** — 이전 방식의 한계 vs 새 방식의 이점 (표 권장)
  4. **핵심 코드** — 변경의 중심이 되는 코드 조각 (5줄 이내) + 한 줄씩 주석
  5. **데이터 흐름** — 요청이 어떤 파일을 거치는지 화살표 다이어그램 (텍스트 OK)
  6. **확인 방법** — 테스트 명령어 또는 수동 확인 절차
  7. **연습 문제** — 1~2개, 독자가 직접 코드를 고쳐보는 실습
- 기존 `backend/docs/sessions/night/T1.learning.md` 스타일 참고.
- 학습 문서 없이 작업 완료 선언 금지.

## Conventions
- 응답 언어: 한국어 우선(사용자 언어에 맞춤). 코드·커밋·변수명: 영어.
- 커밋: Conventional Commits (`feat:` / `fix:` / `refactor:` / `chore:` / `docs:` / `test:`)
- TypeScript: `any` 금지, 타입 명시.
- 데이터 출력에는 항상 tabular-nums(Geist Mono).
