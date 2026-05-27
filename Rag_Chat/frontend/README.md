# Triple Chat Frontend (Streamlit)
Scope: what runs today + integration points exposed by the new backend apps.

## Role
- Single-page chat UI, keeps session state, allows provider presets, shows responses/images.
- Surfaces moderation results inline (BLOCK / MASK warnings come back from the chat API).
- Can call the deterministic knowledge endpoints for "who owns this product" 등 LLM 우회 조회.

## Layout
```
frontend/
├─ app.py   # Streamlit UI
├─ api.py   # Backend client
├─ Dockerfile
└─ requirements.txt
```

## Run
```bash
cd Rag_Chat/frontend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
BACKEND_URL=http://localhost:8000 REDIS_HOST=localhost REDIS_PORT=6379 \
streamlit run app.py    # port 8501
```
`../run_local_fixed.sh` launches it automatically on the same port.

## Backend endpoints used
- `/api/v1/triple/chat/` — send question, show answer/images (inbound+outbound moderation applied server-side)
- `/api/v1/triple/chat-user/` — create/fetch session id, save to Redis with TTL
- `/api/v1/triple/update-activity/` — extend session
- `/api/v1/triple/providers/` — apply provider preset from sidebar
- `/api/v1/triple/health/` — backend liveness
- `/api/v1/knowledge/products|contacts|departments/` — deterministic search (no LLM)
- Errors surface in UI; HTTP 403 on a blocked-word violation is displayed to the user as a clear "차단된 단어" notice.

## Env
- `BACKEND_URL` (default `http://localhost:8000`)
- `REDIS_HOST`, `REDIS_PORT`
- `GOOGLE_API_KEY`, `QWEN_API_KEY`, `QWEN_API_BASE` (forwarded on preset calls)

## Limits
- No auth/roles in the UI yet (backend supports Role; UI integration is Phase 1)
- No streaming; minimal session-expiry notice
- Custom provider combos beyond presets require direct API call
- Knowledge search UI page not yet built — accessible via API or Django Admin
