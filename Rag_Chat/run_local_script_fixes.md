# run_local_fixed.sh 정리
원본 `run_local.sh`에서 확인된 문제와 수정 결과를 요약합니다.

## 발견된 문제
- 루트 단일 venv 가정 → 백엔드/프런트엔드 의존성 혼합
- `DATABASE_URL` 경로 불일치, `backend/db` 디렉터리 미생성
- `backend/requirements.txt`에 남은 충돌 마커로 pip 실패
- Docker/Redis 실행 여부 미검증
- 중단 시 프로세스 정리 부재, 포트 점유 처리 미흡

## run_local_fixed.sh 수정 사항
- 백엔드/프런트엔드 별도 venv 생성 후 각 해석기로 실행
- `backend/db` 생성, `DATABASE_URL` 기본값을 일관되게 설정
- requirements에 충돌 마커가 있으면 제거 후 설치
- Docker 동작 여부 확인, Redis 컨테이너 없으면 생성 후 ping 체크
- 포트 8000/8501 사용 중이면 선점 프로세스 종료(kill -9)
- Ctrl+C 시 Django/Streamlit/Celery(worker/beat) 정리
- `.env`를 `set -a`로 로드, `GOOGLE_API_KEY` 미설정 시 경고 출력

## 사용법
```bash
chmod +x run_local_fixed.sh
cd Rag_Chat && ./run_local_fixed.sh
```
필요 시 `PYTHON_BIN=/path/to/python ./run_local_fixed.sh`로 해석기 지정.

## 남은 주의사항
- GOOGLE_API_KEY가 없으면 LLM 호출이 제한됨
- 포트 강제 종료 동작이 로컬 다른 서비스에 영향을 줄 수 있음
- 헬스체크/APM은 미구현, 콘솔 로그 위주로 상태 확인
