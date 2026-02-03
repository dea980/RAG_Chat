# Provider Release Notes (EN/KR)
Version: 2026-02-03

## Summary / 개요
Provider 체계를 정비해 Gemini/Qwen 조합을 세션 단위로 전환 가능하게 했습니다. Streamlit 프리셋과 Django API가 동일 엔드포인트를 사용합니다.

## Changes / 주요 변경사항
1. ProviderManager  
   - Env + session override로 reasoning/generation 선택.  
   - Cache key `(provider, purpose)`로 인스턴스 재사용.
2. Session Provider API `/api/v1/triple/providers/`  
   - GET: 세션 선택 상태  
   - POST: 프리셋(gemini_only, qwen_reasoning_gemini_generation, qwen_only) 또는 커스텀 적용  
   - DELETE: override 제거
3. Streamlit UI  
   - 사이드바 프리셋 셀렉터, 적용 결과 JSON 표시, 즉시 반영.
4. Vector store / indexing  
   - `RAGUtils`, `build_vector_store.py`, `management/commands/build_vectors.py`가 Manager 경유로 임베딩 생성.  
   - `settings.BASE_DIR` 기준 경로 사용.
5. Docs & env template  
   - `backend/.env`에 Gemini/Qwen 필드 추가, 관련 문서 업데이트.

## Considerations / 고려사항
- `GOOGLE_API_KEY` 필수, Qwen은 `QWEN_API_KEY`, `QWEN_API_BASE` 필요.  
- Override는 TTL(`PROVIDER_OVERRIDE_TTL`, 기본 1800초) 후 기본값으로 복귀.  
- Reasoning→Generation 순차 호출로 지연 가능; 캐싱/비동기/스트리밍 검토.  
- Streamlit 프리셋은 단순 조합; 세밀한 설정은 API 직접 호출.

## Next / 다음 단계
1) 리랭커 플러그인 추가  
2) Provider 헬스 체크 + 장애 시 기본값 fallback  
3) 조합별 스모크 테스트 CI 매트릭스화  
4) Streamlit 고급 패널로 커스텀 조합 입력 지원
