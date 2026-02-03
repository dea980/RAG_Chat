# Provider Refactor Overview (EN/KR)
최근 Provider 추상화 이후 구조 변화와 영향 범위를 모았습니다.

## Changes / 변경 사항
- ProviderManager: env로 embedding/reasoning/generation 선택. 기본 Gemini, Qwen 조합은 실험.  
- Vector store path cleanup: `RAGUtils`, `build_vector_store.py`, `management/commands/build_vectors.py` 모두 ProviderManager 통해 임베딩 생성.  
- Reasoning → Generation chain: `chat/views.py`에서 reasoning 출력 후 생성 프롬프트에 포함.  
- Env alignment: `backend/.env`에 Gemini/Qwen 키 포함, `run_local_fixed.sh`가 동일 변수 프런트엔드에 전달.  
- Session provider toggle: `/api/v1/triple/providers/` GET/POST로 프리셋 적용 (gemini_only, qwen_reasoning_gemini_generation, qwen_only). Streamlit 사이드바에서 호출.

## Considerations / 고려 사항
- `GOOGLE_API_KEY` 필수, Qwen은 `QWEN_API_KEY`, `QWEN_API_BASE` 필요.  
- 두 모델 순차 호출로 지연 증가 가능 → 캐싱/비동기/스트리밍 검토.  
- Qwen 로컬 서빙 시 GPU 요구; 준비 안 됐으면 Gemini-only 유지.  
- 싱글톤 캐시라 장기 실행 후 재초기화가 필요할 수 있음.

## Next Steps / 다음 단계
1) 리랭커 플러그인 구조 (Cohere, bge-reranker 등)  
2) Provider 헬스 체크 + 장애 시 기본값 fallback  
3) 조합별 스모크 테스트를 CI 매트릭스로 추가  
4) Streamlit에서 커스텀 조합 입력 지원 고급 패널 검토  

자세한 구조는 `provider_architecture.md` 참고.
