# Triple Chat 프런트엔드 (Streamlit)
현 시점에 동작하는 범위만 요약합니다.

## 역할
- 단일 페이지 챗 UI
- 사용자 세션 표시 및 유지(backend `chat-user` API + Redis 키)
- Provider 프리셋 토글(Gemini only / Qwen reasoning + Gemini generation / Qwen only)
- 백엔드 RAG API 호출 후 응답·이미지 표시

## 구조
```
frontend/
├─ app.py   # Streamlit UI
├─ api.py   # 백엔드 호출 래퍼
├─ Dockerfile
└─ requirements.txt
```

## 실행
```bash
cd Rag_Chat/frontend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
BACKEND_URL=http://localhost:8000 REDIS_HOST=localhost REDIS_PORT=6379 \
streamlit run app.py   # 기본 포트 8501
```
`../run_local_fixed.sh`를 사용하면 동일 포트에서 자동 기동됩니다.

## 동작 포인트
- `/api/v1/triple/chat/` : 질문 전달 → 응답·이미지 표시
- `/api/v1/triple/user/` : 세션/유저 ID 생성 후 Redis에 TTL로 저장
- `/api/v1/triple/providers/` : 사이드바 프리셋 적용
- 오류는 화면에 표시하고 단순 재시도만 제공 (스트리밍 미지원)

## 환경 변수 (주요)
- `BACKEND_URL` (기본 `http://localhost:8000`)
- `REDIS_HOST`, `REDIS_PORT`
- `GOOGLE_API_KEY`, `QWEN_API_KEY`, `QWEN_API_BASE` (프리셋 API 호출 시 전달)

## 한계
- 인증/권한 없음, 공개 엔드포인트 전제
- 스트리밍·세밀한 세션 만료 알림 미구현
- 프리셋 외 커스텀 Provider 조합은 API 직접 호출 필요
