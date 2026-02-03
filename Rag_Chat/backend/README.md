# Backend README (fact-based)
Triple Chat 백엔드(Django REST + Celery)의 현재 상태와 실행 방법을 정리했습니다. 실제로 동작하는 범위만 기술합니다.

## 역할
- 질문 수신, 벡터 검색, LLM 호출, 응답 생성
- 질문·검색 컨텍스트·응답을 DB에 기록
- Redis 세션 관리 및 Celery 비동기 작업 수행

## 주요 구성
- Django 앱: `chat/` (모델, 시리얼라이저, 뷰, 벡터 파이프라인)
- Celery: `triple_chat_pjt/celery.py` 설정, 워커·비트로 로그/벡터 작업 분리
- Provider 추상화: `chat/providers/manager.py`가 임베딩/추론/생성 모델을 환경 변수로 선택 (기본 Gemini, Qwen 실험 지원)
- 데이터 저장: SQLite 기본, Redis 세션/캐시, FAISS/Chroma 벡터 스토어

## 데이터 모델 핵심
- `User(user_id, created_datetime, expired_datetime, last_activity)`
- `RagData(data_id, data_text, image_urls)`
- `Chat(question_id, user, question_text, response_text, question_created_datetime, data)`
- `SearchLog(search_log_id, question, data, searching_time)`

## 실행 방법 (백엔드만 수동 기동)
```bash
cd Rag_Chat/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
# 별도 터미널에서
celery -A triple_chat_pjt worker --loglevel=info
```
필수 환경 변수: `GOOGLE_API_KEY` (Gemini). Qwen 사용 시 `QWEN_API_KEY`, `QWEN_API_BASE` 추가.

## 엔드포인트 (요약)
- `POST /api/v1/triple/chat/` : 질문 → 응답 생성 (세션/로그 포함)
- `POST /api/v1/triple/user/` : 사용자/세션 생성
- `POST /api/v1/triple/activity/` : 세션 활동 갱신
Swagger/ReDoc 스키마는 로컬 기동 시 `/api/schema/` 하위에서 확인 가능.

## 한계·주의
- 인증·RBAC·금지어 필터 미구현
- DB 트랜잭션/세션 만료 정합성 개선 필요 (Redis TTL ↔ DB expired_datetime)
- 스트리밍 응답 미지원, 동시성은 단일 인스턴스 기준

## 실행 단축 스크립트
`../run_local_fixed.sh`를 사용하면 Redis(도커) + Django + Celery + Streamlit이 일괄 기동됩니다.
