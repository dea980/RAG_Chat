# Triple Chat Frontend (Streamlit) — EN/KR
Scope: what runs today.

## Role / 역할
- EN: Single-page chat UI, keeps session, lets you switch provider presets.  
- KR: 단일 챗 UI, 세션 유지(backend `chat-user` + Redis), Provider 프리셋 토글, 응답/이미지 표시.

## Layout / 구조
```
frontend/
├─ app.py   # Streamlit UI
├─ api.py   # Backend client
├─ Dockerfile
└─ requirements.txt
```

## Run / 실행
```bash
cd Rag_Chat/frontend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
BACKEND_URL=http://localhost:8000 REDIS_HOST=localhost REDIS_PORT=6379 \
streamlit run app.py    # port 8501
```
`../run_local_fixed.sh` 사용 시 동일 포트에서 자동 기동.

## Behavior / 동작 포인트
- `/api/v1/triple/chat/` : send question, show answer/images  
- `/api/v1/triple/user/` : create/fetch session ID, save to Redis with TTL  
- `/api/v1/triple/providers/` : apply preset in sidebar  
- Errors surface in UI; no streaming, simple retry only.

## Env / 환경 변수
- `BACKEND_URL` (default `http://localhost:8000`)  
- `REDIS_HOST`, `REDIS_PORT`  
- `GOOGLE_API_KEY`, `QWEN_API_KEY`, `QWEN_API_BASE` (forwarded when calling presets)

## Limits / 한계
- No auth/roles; assumes open access.  
- No streaming; minimal session-expiry notice.  
- Custom provider combos beyond presets require direct API call.
