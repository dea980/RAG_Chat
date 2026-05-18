# 백엔드 스모크 테스트 가이드 (legacy)

> **현재 권장 경로**: 자동화된 테스트는 [`backend/TestsReadme.md`](../backend/TestsReadme.md)와 GitHub Actions(`.github/workflows/ci.yml`)를 사용합니다. 본 문서는 빠른 손-테스트 절차 정도로 유지됩니다.

## 사전 준비

### Docker 권장 (전 스택)
```bash
cd Rag_Chat
cp .env.example .env   # GOOGLE_API_KEY 채우기
docker-compose up --build
```
- Postgres 5432, Redis 6379, Django 8000, Streamlit 8501 일괄 기동.

### 로컬 dev (SQLite fallback)
```bash
cd Rag_Chat
./run_local_fixed.sh
```

## 빠른 수동 검증

### 1) 헬스
```bash
curl -s http://localhost:8000/api/v1/triple/health/
curl -s http://localhost:8000/api/v1/triple/health/ready/ | jq
```

### 2) 루트 리다이렉트
```bash
curl -sI http://localhost:8000/ | head -5
# → 302 Found, Location: /api/v1/triple/chat/
```

### 3) 사용자/세션
```bash
curl -s -X POST http://localhost:8000/api/v1/triple/chat-user/ -H 'Content-Type: application/json' -d '{}' | jq
```

### 4) 채팅 (LLM 호출)
```bash
curl -s -X POST http://localhost:8000/api/v1/triple/chat/ \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"U0001000100001","question":"갤럭시 S25 256GB 가격이 얼마인가요?"}' | jq
```

### 5) Knowledge (LLM 호출 없음, 결정적 검색)
```bash
curl -s 'http://localhost:8000/api/v1/knowledge/products/?q=galaxy' | jq
```

### 6) Moderation BLOCK 시나리오 (관리자 사전 등록 필요)
```bash
# /admin/moderation/forbiddenword/ 에 word="블락테스트", severity=BLOCK 등록 후
curl -s -X POST http://localhost:8000/api/v1/triple/chat/ \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"U0001000100001","question":"블락테스트 확인"}'
# → 403 + blocked_words
```

## 테스트 결과 해석
- ✅ : 응답 200 / 200-with-expected fields
- ❌ : 5xx 또는 expected field 누락 — 상세 로그 확인

## 문제 해결
1. **연결 오류** — backend 컨테이너가 떠 있는지: `docker-compose ps`
2. **DB 오류** — `docker-compose exec backend python manage.py migrate`
3. **헬스 readiness 실패** — `/health/ready/` 응답에서 어느 컴포넌트가 down인지 확인 (db/redis/provider)

## 자동화된 테스트
정식 테스트는 [`backend/TestsReadme.md`](../backend/TestsReadme.md) 참조 — pytest, chunk A/B harness, GitHub Actions CI 통합 모두 거기에.
