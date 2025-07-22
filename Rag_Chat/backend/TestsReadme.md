# Triple Chat 테스트 가이드

## 테스트 구조
```
backend/
└── chat/
    └── tests/
        ├── test_redis.py     # Redis 연결 및 세션 테스트
        ├── test_api.py       # API 엔드포인트 테스트
        ├── test_models.py    # 데이터베이스 모델 테스트
        └── test_tasks.py     # Celery 태스크 테스트
```

## Redis 및 세션 테스트
### Redis 연결 테스트
```python
def test_redis_connection():
    """Redis 연결 및 재연결 테스트"""
    redis_manager = RedisMessageManager()
    assert redis_manager.redis_client.ping()

def test_redis_connection_failure():
    """Redis 연결 실패 처리 테스트"""
    with patch('redis.Redis.ping', side_effect=redis.ConnectionError):
        with pytest.raises(redis.ConnectionError):
            RedisMessageManager()
```

### 세션 관리 테스트
```python
def test_session_management():
    """세션 생성 및 만료 테스트"""
    redis_manager = RedisMessageManager()
    user_id = "test_user"
    
    # 세션 생성
    assert redis_manager.save_message(user_id, {"test": "data"})
    
    # 세션 조회
    messages = redis_manager.get_messages(user_id)
    assert len(messages) == 1
    
    # 세션 만료
    time.sleep(1)  # TTL 대기
    messages = redis_manager.get_messages(user_id)
    assert len(messages) == 0
```

## API 테스트
### 채팅 API 테스트
```python
@pytest.mark.django_db
def test_chat_api():
    """채팅 API 엔드포인트 테스트"""
    client = APIClient()
    response = client.post('/api/v1/triple/chat/', {
        'question': 'test question'
    }, format='json')
    
    assert response.status_code == 200
    assert 'response' in response.data
```

### 사용자 관리 테스트
```python
@pytest.mark.django_db
def test_user_session():
    """사용자 세션 관리 테스트"""
    client = APIClient()
    response = client.post('/api/v1/triple/chat-user/', {
        'username': 'testuser'
    }, format='json')
    
    assert response.status_code == 200
    assert 'user_id' in response.data
```

## 모델 테스트
### User 모델 테스트
```python
@pytest.mark.django_db
def test_user_model():
    """User 모델 CRUD 테스트"""
    user = User.objects.create(
        username="testuser",
        user_id="test123"
    )
    assert user.username == "testuser"
    assert user.is_active
```

### Chat 모델 테스트
```python
@pytest.mark.django_db
def test_chat_model():
    """Chat 모델 관계 테스트"""
    user = User.objects.create(username="testuser")
    chat = Chat.objects.create(
        user=user,
        question_text="test question"
    )
    assert chat.user.username == "testuser"
```

## Celery 태스크 테스트
### 메시지 처리 테스트
```python
def test_process_chat_message():
    """채팅 메시지 처리 태스크 테스트"""
    result = process_chat_message.delay("test_user", "test message")
    assert result.get()['status'] == 'success'
```

### 세션 정리 테스트
```python
def test_cleanup_expired_sessions():
    """만료된 세션 정리 태스크 테스트"""
    result = cleanup_expired_sessions.delay()
    assert result.successful()
```

## 테스트 실행 방법

### 1. 전체 테스트 실행

```bash
python manage.py test
```

### 특정 테스트 실행
```bash
python manage.py test chat.tests.test_redis
python manage.py test chat.tests.test_api
```

### 커버리지 리포트 생성
```bash
coverage run --source='.' manage.py test
coverage report
coverage html  # 상세 리포트 생성
```

## 테스트 환경 설정

### 테스트용 Redis 설정
```python
# settings/test.py
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 1  # 테스트용 별도 DB
```

### 테스트용 데이터베이스 설정
```python
# settings/test.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:'  # 인메모리 데이터베이스 사용
    }
}
```

## 모의 객체(Mock) 사용
### Redis 모의 객체
```python
@patch('redis.Redis')
def test_with_mock_redis(mock_redis):
    mock_redis.return_value.ping.return_value = True
    redis_manager = RedisMessageManager()
    assert redis_manager.redis_client.ping()
```

### API 모의 객체
```python
@patch('requests.post')
def test_with_mock_api(mock_post):
    mock_post.return_value.json.return_value = {'status': 'success'}
    response = send_chat_request('test message')
    assert response['status'] == 'success'
```

## 성능 테스트
### Redis 성능 테스트
```python
def test_redis_performance():
    """Redis 작업 성능 테스트"""
    start_time = time.time()
    for _ in range(1000):
        redis_manager.save_message("test_user", {"test": "data"})
    end_time = time.time()
    assert end_time - start_time < 5  # 5초 이내 실행
```

### API 성능 테스트
```python
def test_api_performance():
    """API 응답 시간 테스트"""
    start_time = time.time()
    response = client.post('/api/v1/triple/chat/')
    end_time = time.time()
    assert end_time - start_time < 1  # 1초 이내 응답
```

## 지속적 통합(CI) 설정
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python manage.py test