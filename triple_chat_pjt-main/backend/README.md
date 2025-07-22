# Triple Chat 프로젝트

## 개요
Triple Chat 프로젝트는 AI 채팅 애플리케이션을 단계적으로 구축하는 혁신적인 저장소입니다. 이 프로젝트는 Streamlit을 활용한 프론트엔드와 Django REST Framework를 이용한 백엔드를 통해 기본적인 구현에서부터 더 정교한 AI 기반 대화형 인터페이스까지 채팅 애플리케이션의 발전 과정을 보여줍니다.

## 최근 업데이트: 세션 관리 시스템 개선
- User 모델에 `last_activity` 필드 추가: 사용자 활동 시간 자동 추적
- 세션 만료 로직 개선: 실제 비활성 사용자만 만료 처리됨
- 30일 이상 지난 만료 사용자 자동 정리 기능 추가
- 사용자 활동 추적 기능 강화
- 세션-사용자 연결 검증 강화

## 주요 기능
- 다중 채팅 애플리케이션
  - 기본 채팅: 간단한 텍스트 기반 메시징 시스템
  - AI 강화 채팅: 스마트 응답을 위한 AI 모델 통합
  - 고급 채팅: 다양한 AI 기능이 포함된 기능이 풍부한 채팅 애플리케이션

- 핵심 기술
  - 프론트엔드: Streamlit (Python 기반 웹 애플리케이션 프레임워크)
  - 백엔드: Django REST Framework (RESTful API 구현)
  - AI 통합: 다중 AI 모델 구현
  - 실시간 통신: WebSocket 통합
  - 세션 관리: Redis를 활용한 안정적인 세션 관리

## 프로젝트 구조
```
triple_chat_pjt/
├── frontend/        # Streamlit 프론트엔드
│   ├── pages/      # 스트림릿 페이지
│   └── components/ # 재사용 가능한 컴포넌트
│
├── backend/         # Django 백엔드
│   ├── api/        # REST API 엔드포인트
│   ├── chat/       # 채팅 관련 로직
│   └── models/     # 데이터베이스 모델
│
└── ai_models/      # AI 모델 통합
    ├── basic/      # 기본 AI 처리
    └── advanced/   # 고급 AI 기능
```

## 모델 구조

### User
```python
- user_id: CharField (PK)
- uuid: UUIDField
- created_datetime: DateTimeField
- expired_datetime: DateTimeField
- last_activity: DateTimeField  # 새로 추가됨
```

### RagData
```python
- data_id: AutoField (PK)
- data_text: TextField
- image_urls: JSONField
```

### Chat
```python
- question_id: AutoField (PK)
- user: ForeignKey(User)
- question_text: TextField
- question_created_datetime: DateTimeField
- response_text: TextField
- data: ForeignKey(RagData)
```

### SearchLog
```python
- search_log_id: AutoField (PK)
- question: ForeignKey(Chat)
- data: ForeignKey(RagData)
- searching_time: DateTimeField
```

## Redis 세션 관리
`redis_manager.py`는 다음과 같은 주요 세션 관리 기능을 제공합니다:

- 사용자 세션 생성 및 갱신
- 세션 만료 처리 
- 활성 세션 목록 조회
- 세션 데이터 저장 및 검색
- 연결 풀링을 통한 성능 최적화
- 자동 재연결 메커니즘

## 사전 요구사항
- Python (v3.8 이상)
- pip (최신 버전)
- Git
- Redis

## 설치 방법
1. 저장소 복제:
```bash
git clone https://gitlab.com/kdea989/triple_chat_pjt.git
cd triple_chat_pjt
```

2. 가상환경 생성 및 활성화:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
.\venv\Scripts\activate  # Windows
```

3. 의존성 설치:
```bash
# 백엔드 의존성
pip install -r backend/requirements.txt

# 프론트엔드 의존성
pip install -r frontend/requirements.txt
```

## 개발
프론트엔드와 백엔드를 각각 실행해야 합니다:

1. 백엔드 실행:
```bash
cd backend
python manage.py migrate
python manage.py runserver
```

2. 프론트엔드 실행:
```bash
cd frontend
streamlit run app.py
```

## 학습 경로
이 저장소는 점진적인 학습 경험을 제공하도록 구성되어 있습니다:

1. **기본 채팅 구현**
   - Streamlit을 사용한 기본 UI 구현
   - Django REST Framework로 API 엔드포인트 구축
   - 기본적인 채팅 기능 구현

2. **AI 채팅 강화**
   - AI 모델 통합
   - 실시간 응답 처리
   - 고급 채팅 기능 추가

3. **고급 기능**
   - 다중 AI 모델 통합
   - 실시간 업데이트 및 알림
   - 성능 최적화

## API 문서
백엔드 API 문서는 다음 URL에서 확인할 수 있습니다:
- Swagger UI: `http://localhost:8000/api/schema/swagger-ui/`
- ReDoc: `http://localhost:8000/api/schema/redoc/`
- postman : `http://localhost:8000/api/schema/postman/`

