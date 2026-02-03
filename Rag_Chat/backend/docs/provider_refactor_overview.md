# Provider 리팩터 개요 (요약)
최근 Provider 추상화 작업으로 발생한 구조 변화와 영향 범위를 정리했습니다.

## 변경 사항
- ProviderManager 도입: 임베딩/추론/생성 모델을 환경 변수로 선택. 기본은 Gemini, Qwen 조합은 실험 지원.
- 벡터 스토어 경로 정리: `RAGUtils`, `build_vector_store.py`, `management/commands/build_vectors.py`가 ProviderManager를 통해 임베딩을 생성.
- Reasoning → Generation 체인: `chat/views.py`에서 두 단계 호출 구조를 사용(선택한 reasoning 모델 출력 → 생성 모델 프롬프트에 포함).
- 환경 변수 정리: `backend/.env` 템플릿에 Gemini/Qwen 키 포함. `run_local_fixed.sh`가 동일 변수를 프런트엔드에도 전달.
- 세션별 Provider 토글: `/api/v1/triple/providers/` GET/POST로 프리셋(예: gemini_only, qwen_reasoning_gemini_generation, qwen_only) 적용. Streamlit 사이드바가 이 엔드포인트를 호출.

## 고려 사항
- `GOOGLE_API_KEY` 필수. Qwen 사용 시 `QWEN_API_KEY`, `QWEN_API_BASE` 필요.
- 두 모델 순차 호출 구조라 응답 지연 가능성이 있음; 캐싱/비동기/스트리밍 검토 필요.
- Qwen 로컬 서빙 시 GPU 리소스 요구. 준비되지 않으면 Gemini-only 유지.
- ProviderManager는 싱글톤 캐시를 사용하므로 장시간 실행 후 재초기화가 필요할 수 있음.

## 다음 단계 
1) 리랭커 플러그인 구조 추가 (Cohere, bge-reranker 등 선택적)  
2) Provider 헬스 체크 + 장애 시 기본값(fallback) 적용  
3) Provider 조합별 스모크 테스트를 CI 매트릭스로 추가  
4) Streamlit에서 커스텀 조합 입력을 지원하는 고급 패널 검토  

상세 구조는 `provider_architecture.md` 참고.
