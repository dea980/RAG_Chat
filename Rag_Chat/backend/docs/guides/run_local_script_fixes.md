# run_local_fixed.sh Notes
Local-run helper for the SQLite-fallback dev mode. For the full Postgres + RBAC + moderation + audit stack, prefer `docker-compose up --build` — env 변수 템플릿은 [backend/README.md](backend/README.md#environment-variables-single-source-rag_chatenv) 에 inline 으로 들어 있습니다.

## Issues found (in the original script)
- Single root venv assumption mixing backend/frontend deps
- `DATABASE_URL` path mismatch, missing `backend/db` dir
- Merge markers left in `backend/requirements.txt` → pip fail
- Docker/Redis not checked before use
- No cleanup on interrupt; weak port handling

## Fixes (current script)
- Separate venv per backend/frontend; run with each interpreter
- Create `backend/db`, align `DATABASE_URL` default
- Strip conflict markers before installing requirements
- Check Docker running; create Redis container if absent, ping before proceed
- Kill processes on ports 8000/8501 if occupied
- Trap Ctrl+C and clean Django/Streamlit/Celery (worker/beat)
- Load `.env` with `set -a`; warn when `GOOGLE_API_KEY` missing

## Usage
```bash
chmod +x run_local_fixed.sh
cd Rag_Chat && ./run_local_fixed.sh
```
Optional: `PYTHON_BIN=/path/to/python ./run_local_fixed.sh`

## When to use docker-compose instead
- Demo / 영업팀 베타 / 대외비 모드 → **docker-compose**:
  ```bash
  cd Rag_Chat
  # Rag_Chat/.env 를 backend/README.md 의 "Environment variables" 섹션 템플릿대로 작성
  docker-compose up --build
  docker-compose exec backend python manage.py createsuperuser
  ```
- Postgres 16 + Redis 7 + backend(gunicorn) + Celery worker + beat + Streamlit 일괄 기동.
- `run_local_fixed.sh`는 SQLite fallback dev 모드 — Postgres 마이그레이션·새 앱(knowledge/moderation/audit)도 동작하지만 운영 정합성은 docker-compose 쪽이 높음.

## Caveats
- Without `GOOGLE_API_KEY`, LLM calls are limited (헬스체크는 그래도 동작).
- Force-killing port holders may affect other local services.
- 단일 노드 dev 셋업 — Celery beat이 있어 세션 만료 cleanup은 자동.

## Related
- [backend/README.md](backend/README.md#environment-variables-single-source-rag_chatenv) — 환경변수 템플릿 (inline)
- [docker-compose.yml](docker-compose.yml) — 전체 스택 정의
- [backend/README.md](backend/README.md) — backend 실행 옵션
