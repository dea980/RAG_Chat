# Triple Chat 프론트엔드

## 소개
Triple Chat의 프론트엔드는 Streamlit을 사용하여 구현되었으며, 사용자 친화적인 채팅 인터페이스를 제공합니다. Redis를 통한 세션 관리와 실시간 상태 업데이트를 지원하며, 안정적인 연결 관리 시스템을 갖추고 있습니다.

## 기술 스택 상세
- Streamlit
- Redis (Pub/Sub, Session Management)
- Python Requests
- Docker

## 프로젝트 구조
```
frontend/
├── app.py              # 메인 Streamlit 애플리케이션
├── api.py             # 백엔드 API 클라이언트
├── Dockerfile         # Docker 설정
└── requirements.txt   # 의존성 목록
```

## 주요 기능

### 개선된 세션 관리
- Redis 연결 풀링 및 자동 재연결
- 세션 상태 실시간 확인
- 안정적인 Pub/Sub 이벤트 처리
- 세션 만료 자동 감지 및 처리
- 사용자 활동 추적 개선

### 채팅 인터페이스
- 실시간 메시지 전송
- 채팅 기록 표시
- 사용자 입력 처리
- 에러 처리 및 피드백
- 참조 문서 표시
- 이미지 미리보기

### 백엔드 통신
- REST API 통신
- 비동기 요청 처리
- 향상된 에러 핸들링
- 자동 재시도 메커니즘

## Redis 연결 관리
```python
def get_redis_client():
    """안정적인 Redis 클라이언트 생성"""
    try:
        client = redis.StrictRedis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_timeout=5
        )
        client.ping()
        return client
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return None

def check_session_active():
    """세션 활성 상태 확인"""
    if not st.session_state.user_id:
        return False
    try:
        return bool(redis_client.get(f"user_session:{st.session_state.user_id}"))
    except redis.RedisError as e:
        logger.error(f"Failed to check session: {e}")
        return False
```

## 로컬 개발 환경 설정

1. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. 의존성 설치
```bash
pip install -r requirements.txt
pip install watchdog  # 성능 향상을 위한 파일 모니터링
```

3. 환경 변수 설정
```bash
export BACKEND_URL=http://localhost:8000
export REDIS_HOST=localhost
export REDIS_PORT=6379
```

3. 개발 서버 실행:
   ```bash
   streamlit run app.py
   ```

## 환경 변수
| 변수명 | 설명 | 기본값 |
|--------|------|---------|
| BACKEND_URL | 백엔드 API 주소 | http://localhost:8000 |
| REDIS_HOST | Redis 호스트 | localhost |
| REDIS_PORT | Redis 포트 | 6379 |
| REDIS_DB | Redis DB 번호 | 0 |
| SESSION_EXPIRY | 세션 만료 시간(초) | 3600 |
| LOG_LEVEL | 로깅 레벨 | INFO |

## 에러 처리 개선사항

### Redis 연결 오류 처리
```python
try:
    redis_client = get_redis_client()
    if not redis_client:
        st.error("세션 서버 연결에 실패했습니다.")
        st.stop()
except Exception as e:
    logger.error(f"Redis initialization error: {e}")
    st.error("서비스 초기화에 실패했습니다.")
    st.stop()
```

### 세션 상태 모니터링
```python
def listen_to_redis():
    """향상된 Redis pub/sub 리스너"""
    while True:
        try:
            pubsub = redis_client.pubsub()
            pubsub.subscribe("session_expired")
            for message in pubsub.listen():
                if message["type"] == "message":
                    st.session_state["session_expired"] = True
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
            time.sleep(5)  # 재시도 전 대기
```

## 성능 최적화
1. Redis 연결 풀링
   - 연결 재사용
   - 자동 재연결 메커니즘
   - 타임아웃 설정

2. 세션 관리 개선
   - 세션 상태 캐싱
   - 효율적인 상태 갱신
   - 불필요한 Redis 조회 감소

3. UI/UX 최적화
   - 불필요한 리렌더링 방지
   - 컴포넌트 캐싱
   - 지연 로딩 구현

4. 모니터링 및 로깅
   - 상세한 에러 로깅
   - 성능 메트릭 수집
   - 상태 모니터링

## 모니터링 시스템

### Redis 모니터링
- 연결 상태 추적
- 세션 활성화 상태
- Pub/Sub 이벤트 처리
- 에러 발생 빈도

### 성능 메트릭
- API 응답 시간
- Redis 작업 지연시간
- UI 렌더링 성능
- 메모리 사용량

### 에러 추적
- Redis 연결 오류
- API 통신 실패
- 세션 관리 문제
- 데이터 처리 오류

### 상태 대시보드
- 실시간 세션 수
- 활성 사용자 수
- 에러 발생률
- 시스템 건강도

## 문제 해결 가이드

### Redis 연결 문제
1. Redis 서버 상태 확인
2. 환경 변수 설정 확인
3. 네트워크 연결 확인
4. 로그 분석

### 세션 관리 문제
1. Redis 키 존재 여부 확인
2. 세션 타임아웃 설정 확인
3. Pub/Sub 이벤트 확인
4. 사용자 상태 검증

### API 통신 문제
1. 백엔드 서버 상태 확인
2. 네트워크 연결 확인
3. 요청/응답 로그 분석
4. 재시도 메커니즘 확인