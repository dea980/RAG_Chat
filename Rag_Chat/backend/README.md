# Backend README (EN/KR, fact-only)
Backend = Django REST + Celery. What it does now, nothing more.

## Role / 역할
- EN: Receive questions, run vector search, call LLM, return answer, log all steps.  
- KR: 질문 수신 → 벡터 검색 → LLM 호출 → 응답 생성, 전 과정을 DB에 기록. Redis 세션, Celery 비동기 작업 수행.

## Components / 구성
- Django app `chat/` (models, serializers, views, vector pipeline)  
- Celery app `triple_chat_pjt/celery.py` (worker, beat)  
- Provider abstraction `chat/providers/manager.py` (env-driven; Gemini 기본, Qwen 실험)  
- Storage: SQLite 기본, Redis 세션/캐시, FAISS/Chroma 벡터 스토어

## Data Model / 데이터 모델
- User(user_id, created_datetime, expired_datetime, last_activity)  
- RagData(data_id, data_text, image_urls)  
- Chat(question_id, user, question_text, response_text, question_created_datetime, data)  
- SearchLog(search_log_id, question, data, searching_time)

## Run (backend only) / 실행
```bash
cd Rag_Chat/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
# new terminal
celery -A triple_chat_pjt worker --loglevel=info
```
Env: `GOOGLE_API_KEY` 필수, Qwen 사용 시 `QWEN_API_KEY`, `QWEN_API_BASE`.

## Endpoints (short) / 엔드포인트
- POST `/api/v1/triple/chat/` 질문→응답 (로그 포함)  
- POST `/api/v1/triple/user/` 세션/유저 생성  
- POST `/api/v1/triple/activity/` 활동 갱신  
Swagger/ReDoc: `/api/schema/…` (로컬 기동 시)

## Limits / 한계
- No auth/RBAC/forbidden-term filter  
- Redis TTL ↔ DB expired_datetime 정합성 개선 필요  
- Streaming 미지원, 단일 인스턴스 기준 동시성

## Shortcut / 단축 실행
`../run_local_fixed.sh` 로 Redis(도커) + Django + Celery + Streamlit 일괄 기동.
