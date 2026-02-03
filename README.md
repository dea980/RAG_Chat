Triple Chat – Internal RAG Q&A 

1) Purpose / 목적  
- EN: Track Q&A per session, log retrieved context and responses, and try vendor-flexible RAG.  
- KR: 세션 단위 질문·검색·응답을 남기고, LLM 공급자를 갈아끼우며 RAG 파이프라인을 검증.

2) Problem Statement / 문제 정의  
- EN: Reproducibility of “who asked what and with which data,” and quick model/embedding swap without code changes.  
- KR: “누가 무엇을 어떤 데이터로 답했는가”를 재현 가능하게 하고, 코드 수정 없이 모델/임베딩을 교체할 수 있어야 함. (현재 인증·RBAC·필터는 미구현)

3) Architecture (today) / 아키텍처  
- Frontend: Streamlit (Redis Pub/Sub)  
- Backend: Django REST Framework  
- Async: Celery (logging, vector build)  
- Session/Cache: Redis  
- Vector Store: FAISS/Chroma  
- Models: Gemini (default), Qwen (OpenAI-compatible endpoint; experimental)

Flow / 처리 흐름  
1. Ask in Streamlit → 2. Vector search → 3. LLM generation → 4. Log question/context/answer.

4) Data Model (summary)  
User(user_id, created_datetime, expired_datetime)  
Chat(question_id, user_id, question_text, response_text, created_datetime, data_id)  
SearchLog(search_log_id, question_id, data_id, searching_time)  
RagData(data_id, data_text, image_urls)  
추적: 질문 → 사용된 컨텍스트 → 응답을 테이블로 재구성 가능.

5) Key Choices / 설계 근거  
- Django: API 스키마·로그 일관 관리.  
- Redis: 세션·Pub/Sub.  
- Celery: UI와 분리된 로깅/벡터 작업.  
- Provider abstraction: `chat/providers/manager.py` selects embedding/reasoning/generation via env vars; Gemini 기본, Qwen 실험.

6) Implemented / 구현됨  
- Session-based RAG chat (Streamlit + Django)  
- Vector search (FAISS/Chroma) + context injection  
- Chat/SearchLog persistence  
- Gemini↔Qwen combos via env  
- Local one-shot run script (`run_local_fixed.sh`) and Docker Compose

7) Not Yet / 미구현·한계  
- No auth/RBAC/forbidden-terms  
- Single-node; no HA/auto-scale  
- Minimal streaming/concurrency  
- No health checks/APM/dashboard

8) How to Run / 실행  
Script:  
```
chmod +x Rag_Chat/run_local_fixed.sh
cd Rag_Chat && ./run_local_fixed.sh
```
Docker Compose: `cd Rag_Chat && docker-compose up --build`  
Manual: Redis → `backend` migrate/runserver → `frontend` streamlit → `celery -A triple_chat_pjt worker`
Note: GOOGLE_API_KEY 없으면 LLM 호출 제한.

9) Logs & Governance / 로그·거버넌스  
- Chat, SearchLog capture question → context → answer chain.  
- Session state in Redis; DB expired_datetime 정합성은 개선 필요.  
- Provider 선택: env 기반(세션별 토글은 실험 단계).

10) Doc Map  
- `Rag_Chat/backend/docs/provider_architecture.md` (구조)  
- `Rag_Chat/backend/docs/provider_refactor_overview.md` (리팩터 기록)  
- `Rag_Chat/backend/docs/provider_release_notes.md` (변경 이력)  
- `Rag_Chat/frontend/frontnedREADME.md` (프런트 요약)  
- `Rag_Chat/run_local_script_fixes.md` (실행 스크립트 수정)  
- `Rag_Chat/프로젝트현황.md` (상태/다음 액션)
