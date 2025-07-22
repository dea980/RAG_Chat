# Triple Chat 프로젝트

Django, Streamlit, LangChain을 활용한 현대적인 채팅 애플리케이션으로, 실시간 통신 기능과 AI 기반 상호작용을 제공합니다.

## 기술 스택
- **백엔드**
  - Django
  - Django REST Framework
  - LangChain
  - Celery
  - SQLite
  - Redis
  - Vector Store (FAISS)

- **프론트엔드**
  - Streamlit
  - Python Requests
  - Redis Pub/Sub

## 주요 기능
1. AI 채팅 인터페이스
2. 세션 기반 사용자 관리
3. 비동기 작업 처리
4. 채팅 기록 저장
5. RAG (Retrieval Augmented Generation) 데이터 관리
6. 벡터 기반 문서 검색
7. 실시간 세션 모니터링

## 설치 및 실행 방법

### 사전 요구사항
- Docker
- Docker Compose
- Python 3.8+
- OpenAI API 키
- Redis

### 환경 설정
1. 프로젝트 클론
```bash
git clone [repository-url]
cd triple_chat_pjt
```

2. 가상환경 설정
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 의존성 설치
```bash
pip install -r requirements.txt
pip install watchdog  # 향상된 성능을 위한 파일 모니터링
```

### 실행 방법

#### 자동 실행 스크립트 사용
모든 서비스를 한 번에 실행하려면:
```bash
chmod +x run_local_fixed.sh
./run_local_fixed.sh
```
이 스크립트는 다음을 자동으로 실행합니다:
- Redis 서버
- Django 백엔드
- Streamlit 프론트엔드
- Celery 워커

#### Docker로 실행하기
```bash
docker-compose up --build
```

#### 수동으로 실행하기
1. Redis 서버 실행
```bash
docker start redis || docker run -d -p 6379:6379 --name redis redis:7
```

2. 백엔드 실행
```bash
cd backend
python manage.py migrate
python manage.py runserver
```

3. Celery 워커 실행
```bash
cd backend
celery -A triple_chat_pjt worker --loglevel=info
```

4. 프론트엔드 실행
```bash
cd frontend
streamlit run app.py
```

## 서비스 접속
- 프론트엔드: http://localhost:8501
- 백엔드 API: http://localhost:8000

## 프로젝트 구조
```
triple_chat_pjt/
├── backend/
│   ├── chat/                 # 메인 앱 디렉토리
│   │   ├── models.py        # 데이터베이스 모델
│   │   ├── serializers.py   # API 시리얼라이저
│   │   ├── views.py         # API 뷰
│   │   ├── tasks.py        # Celery 태스크
│   │   ├── redis_manager.py # Redis 관리
│   │   ├── tests.py        # 테스트 코드
│   │   └── vector_store/   # FAISS 벡터 저장소
│   ├── triple_chat_pjt/     # 프로젝트 설정
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── app.py              # Streamlit 앱
│   ├── api.py             # 백엔드 API 클라이언트
│   └── requirements.txt
├── run_local_fixed.sh           # 로컬 실행 스크립트
└── docker-compose.yml
```

## 최근 업데이트
- 세션 관리 개선
  - Redis 연결 안정성 강화
  - 세션 상태 확인 로직 개선
  - 자동 재연결 메커니즘 추가
- 실행 스크립트 추가
  - 모든 서비스 자동 실행
  - 상태 모니터링 추가
  - 오류 처리 개선
- 성능 최적화
  - Watchdog 추가
  - Redis 연결 풀링
  - 프로세스 관리 개선

## 문제 해결
1. Redis 연결 오류
   - Redis 서버가 실행 중인지 확인
   - 환경 변수 REDIS_HOST와 REDIS_PORT 확인
   - Redis 컨테이너 상태 확인

2. 데이터베이스 마이그레이션 오류
   - `python manage.py makemigrations` 실행
   - `python manage.py migrate` 실행
   - SQLite 파일 권한 확인

3. 세션 관리 문제
   - Redis 연결 상태 확인
   - 세션 타임아웃 설정 확인
   - 로그에서 오류 메시지 확인

4. OpenAI API 오류
   - API 키가 올바르게 설정되었는지 확인
   - 환경 변수 OPENAI_API_KEY 확인

## 기여 방법
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 라이선스
이 프로젝트는 MIT 라이선스를 따릅니다.