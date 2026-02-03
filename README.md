Triple Chat – Internal RAG Q&A (fact-based)
Palantir Deployment Strategist 제출용으로 정리한 메인 README입니다. 과장 없이, 실제 구현 범위만 기술합니다.

1. 목적
- 내부 질의응답을 세션 단위로 추적하고, 검색·응답 로그를 남기는 실험형 RAG 파이프라인 검증
- LLM 벤더 락인 완화를 위해 Provider 추상화로 Gemini·Qwen 교차 테스트
- 금지어/리뷰 등 거버넌스 확장을 염두에 둔 데이터 경로와 로그 구조 확보

2. 문제 정의
- “누가 무엇을 물었고 어떤 데이터로 답했는가”를 재현 가능하게 할 것
- 모델·임베딩 교체를 코드 수정 없이 시도할 수 있을 것
- PoC 단계이므로 인증·RBAC·필터링 미구현임을 명시

3. 아키텍처 (현재 동작 기준)
- 프런트엔드: Streamlit 단일 페이지 (Redis Pub/Sub 반영)
- 백엔드: Django REST Framework
- 비동기: Celery (로그·벡터 빌드 분리)
- 세션/캐시: Redis
- 벡터 스토어: FAISS/Chroma
- 모델: Gemini(기본), Qwen(OpenAI 호환 엔드포인트로 실험)

처리 흐름 요약
1) 사용자 질문 수신 → 2) 벡터 검색 → 3) LLM 생성 → 4) 질문·컨텍스트·응답 로그 적재

4. 데이터 모델 (요약)
- User(user_id, created_datetime, expired_datetime)
- Chat(question_id, user_id, question_text, response_text, created_datetime, data_id)
- SearchLog(search_log_id, question_id, data_id, searching_time)
- RagData(data_id, data_text, image_urls)

추적 가능성: 질문 → 사용된 컨텍스트 → 최종 응답 경로를 테이블로 재구성 가능.

5. 핵심 설계 선택
- Django: API 스키마와 로그 저장을 안정적으로 관리
- Redis: 세션 상태 + Pub/Sub 이벤트
- Celery: UI와 분리된 로깅·백그라운드 작업
- Provider 추상화: `chat/providers/manager.py`가 임베딩/추론/생성 모델을 환경 변수로 선택. 기본 Gemini, Qwen은 실험용.

6. 현재 구현된 기능
- 세션 기반 RAG 챗봇 (Streamlit UI + Django API)
- 벡터 검색(FAISS/Chroma) + 컨텍스트 주입
- 질문/검색결과/응답 로그 저장
- Gemini/Qwen 모델 조합 전환(환경 변수 기반)
- 로컬 올인원 실행 스크립트(`run_local_fixed.sh`)와 Docker Compose

7. 미구현·한계
- 금지어 필터, RBAC, 정식 인증 없음
- 단일 노드 구성(HA/오토스케일 미구현)
- UI 스트리밍·동시성 최소 수준
- 헬스체크·APM·모니터링 대시보드 없음

8. 실행 방법
스크립트 (로컬 올인원)
```
chmod +x Rag_Chat/run_local_fixed.sh
cd Rag_Chat && ./run_local_fixed.sh
```
Redis(도커), Django, Celery(worker/beat), Streamlit을 순차 기동. GOOGLE_API_KEY 없으면 LLM 호출이 제한됨.

Docker Compose
```
cd Rag_Chat && docker-compose up --build
```

수동 실행 요약
1) Redis 컨테이너 실행  
2) `backend`: `python manage.py migrate && python manage.py runserver`  
3) `frontend`: `streamlit run app.py`  
4) `celery -A triple_chat_pjt worker --loglevel=info`

9. 로그·거버넌스 포인트
- Chat, SearchLog 테이블로 질문-컨텍스트-응답 경로 기록
- 세션 상태는 Redis에 저장; DB 만료 시각과 정합성 개선이 향후 과제
- Provider 선택은 환경 변수 기반(세션별 토글 API는 실험 단계)

10. 문서 맵
- `Rag_Chat/backend/docs/provider_architecture.md` — Provider 추상화 구조
- `Rag_Chat/backend/docs/provider_refactor_overview.md` — 리팩터 기록
- `Rag_Chat/backend/docs/provider_release_notes.md` — 변경 이력
- `Rag_Chat/frontend/frontnedREADME.md` — Streamlit UI 요약
- `Rag_Chat/run_local_script_fixes.md` — 실행 스크립트 수정 내역
- `Rag_Chat/프로젝트현황.md` — 현재 이슈/다음 작업
