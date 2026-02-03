# Provider Architecture (현행)
Gemini와 Qwen을 코드 수정 없이 교체·조합하기 위한 추상화 계층을 설명합니다. 구현된 범위만 기술합니다.

## 목표
- 임베딩/추론/생성 모델을 환경 변수로 선택
- 동일한 ProviderManager를 RAG 유틸리티, API 뷰, 벡터 빌드에 재사용
- 벤더 락인 최소화, 실험 반복 비용 절감

## 주요 구성
### ProviderManager (`chat/providers/manager.py`)
- 기본값: Gemini 임베딩 + Gemini 추론/생성
- 환경 변수
  - `EMBEDDING_PROVIDER` (default: gemini)
  - `REASONING_PROVIDER`, `GENERATION_PROVIDER` (`gemini` | `qwen`)
  - `GOOGLE_API_KEY`, `GOOGLE_EMBEDDING_MODEL`, `GOOGLE_CHAT_MODEL`
  - `QWEN_API_KEY`, `QWEN_API_BASE`, `QWEN_MODEL_NAME`, `QWEN_REASONING_MODEL`, `QWEN_GENERATION_MODEL`
- 캐시: 목적별(provider, purpose)로 모델 인스턴스를 1회 생성 후 재사용

### 임베딩
- 지원: Gemini `models/text-embedding-004`
- Qwen 임베딩은 미구현 (필요 시 `_create_*_embeddings` 확장)

### Chat / Reasoning
- `get_reasoning_model()`, `get_generation_model()`이 LangChain 래퍼를 생성
  - Gemini: `ChatGoogleGenerativeAI`
  - Qwen: OpenAI 호환 엔드포인트를 통한 `ChatOpenAI`

## 사용 위치
- `chat/utils.py`: `RAGUtils.get_vector_store()`, `create_vector_store_from_documents()`
- `chat/views.py`: Reasoning → Generation 체인 구성
- `chat/build_vector_store.py`, `chat/management/commands/build_vectors.py`: 인덱싱 시 임베딩 생성

## 설정 예시
```
# Gemini only
GOOGLE_API_KEY=your-gemini-key
EMBEDDING_PROVIDER=gemini
REASONING_PROVIDER=gemini
GENERATION_PROVIDER=gemini

# Gemini + Qwen (reasoning만 Qwen)
GOOGLE_API_KEY=your-gemini-key
QWEN_API_KEY=your-qwen-key
QWEN_API_BASE=https://<openai-compatible-endpoint>
REASONING_PROVIDER=qwen
GENERATION_PROVIDER=gemini
```

## 한계·주의
- Qwen 사용 시 OpenAI 호환 REST 엔드포인트와 API 키가 필요함.
- 임베딩은 현재 Gemini만 제공.
- ProviderManager는 싱글톤이므로 장시간 실행 후 모델 재초기화가 필요하면 모듈을 리로드하거나 캐시 무효화 로직을 추가해야 함.
