# Provider 리팩터 릴리스 노트

## 버전: 2026-02-03

### 개요
Gemini/Qwen 조합을 세션 단위로 전환할 수 있도록 Provider 체계를 정비했습니다. Streamlit 사이드바 프리셋과 Django API가 동일한 엔드포인트를 사용합니다.

### 주요 변경사항
1. ProviderManager 확장  
   - 환경 변수 + 세션 override를 조합해 reasoning/generation 모델을 선택.  
   - 캐시 키를 `(provider, purpose)`로 분리해 모델 인스턴스 재사용.

2. 세션별 Provider API (`/api/v1/triple/providers/`)  
   - GET: 현재 세션의 선택 상태 반환  
   - POST: 프리셋(`gemini_only`, `qwen_reasoning_gemini_generation`, `qwen_only`) 또는 커스텀 조합 적용  
   - DELETE: override 제거 후 기본값 복구

3. Streamlit UI  
   - 사이드바에 Provider Preset 셀렉터 추가, 적용 결과를 JSON으로 표시.  
   - 백엔드 API를 호출해 세션별 설정을 즉시 반영.

4. 벡터 스토어/인덱싱  
   - `RAGUtils`, `build_vector_store.py`, `management/commands/build_vectors.py`가 ProviderManager 경유로 임베딩 생성.  
   - `settings.BASE_DIR` 기준 경로 사용해 실행 위치 의존성 감소.

5. 문서/환경 템플릿  
   - `backend/.env`에 Gemini/Qwen 키 필드 추가.  
   - 관련 문서(`provider_architecture.md`, `provider_refactor_overview.md`) 업데이트.

### 고려사항
- `GOOGLE_API_KEY` 필수. Qwen 사용 시 `QWEN_API_KEY`, `QWEN_API_BASE` 필요.  
- override는 캐시에 저장되며 TTL(`PROVIDER_OVERRIDE_TTL`, 기본 1800초) 후 기본값으로 복귀.  
- Reasoning → Generation 순차 호출로 응답 지연 가능. 캐싱/비동기/스트리밍 검토.  
- Streamlit 프리셋은 단순 조합 위주. 세밀한 설정은 API 직접 호출 필요.

### 다음 단계 제안
1) 리랭커 플러그인 추가  
2) Provider 헬스 체크 및 장애 시 기본값 fallback  
3) 조합별 스모크 테스트 CI 매트릭스화  
4) Streamlit 고급 패널로 커스텀 조합 입력 지원
