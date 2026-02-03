# run_local_fixed.sh Notes (EN/KR)
Summary of what was broken and what the fixed script does.

## Issues found / 발견된 문제
- Single root venv assumption → backend/frontend deps mixed  
- `DATABASE_URL` path mismatch, missing `backend/db` dir  
- Merge markers left in `backend/requirements.txt` → pip fail  
- Docker/Redis not checked before use  
- No cleanup on interrupt; weak port handling

## Fixes / 수정 사항
- Separate venv per backend/frontend; run with each interpreter  
- Create `backend/db`, align `DATABASE_URL` default  
- Strip conflict markers before installing requirements  
- Check Docker running; create Redis container if absent, ping before proceed  
- Kill processes on ports 8000/8501 if occupied  
- Trap Ctrl+C and clean Django/Streamlit/Celery (worker/beat)  
- Load `.env` with `set -a`; warn when `GOOGLE_API_KEY` missing

## Usage / 사용법
```bash
chmod +x run_local_fixed.sh
cd Rag_Chat && ./run_local_fixed.sh
```
Optional: `PYTHON_BIN=/path/to/python ./run_local_fixed.sh`

## Caveats / 남은 주의사항
- Without `GOOGLE_API_KEY`, LLM calls are limited.  
- Force-killing port holders may affect other local services.  
- No health checks/APM; rely on console logs.
