# Provider Architecture (EN/KR)
Gemini ↔ Qwen을 코드 수정 없이 조합·교체하기 위한 현행 추상화 계층입니다. 구현된 범위만 적습니다.

## Goals / 목표
- EN: Pick embedding/reasoning/generation via env vars and reuse one manager across RAG utilities, API views, indexing.  
- KR: 임베딩·추론·생성을 환경 변수로 선택하고, 동일 Manager를 RAG/뷰/인덱싱에서 재사용해 벤더 락인 최소화.

## Components / 구성
### ProviderManager (`chat/providers/manager.py`)
- Default: Gemini embedding + Gemini reasoning/generation  
- Env vars: `EMBEDDING_PROVIDER`, `REASONING_PROVIDER`, `GENERATION_PROVIDER` (gemini|qwen)  
  `GOOGLE_API_KEY`, `GOOGLE_EMBEDDING_MODEL`, `GOOGLE_CHAT_MODEL`  
  `QWEN_API_KEY`, `QWEN_API_BASE`, `QWEN_MODEL_NAME`, `QWEN_REASONING_MODEL`, `QWEN_GENERATION_MODEL`  
- Cache: per (provider, purpose) instance reuse.

### Embedding
- Supported: Gemini `models/text-embedding-004`  
- Qwen embedding: not implemented yet (extend `_create_*_embeddings` if needed).

### Chat / Reasoning
- `get_reasoning_model()`, `get_generation_model()` produce LangChain wrappers.  
  - Gemini → `ChatGoogleGenerativeAI`  
  - Qwen → `ChatOpenAI` via OpenAI-compatible endpoint

## Where used / 사용 위치
- `chat/utils.py`: `RAGUtils.get_vector_store()`, `create_vector_store_from_documents()`  
- `chat/views.py`: reasoning → generation chain  
- `chat/build_vector_store.py`, `chat/management/commands/build_vectors.py`: indexing embeddings

## Config examples / 설정 예시
```
# Gemini only
GOOGLE_API_KEY=your-gemini-key
EMBEDDING_PROVIDER=gemini
REASONING_PROVIDER=gemini
GENERATION_PROVIDER=gemini

# Gemini + Qwen (reasoning only Qwen)
GOOGLE_API_KEY=your-gemini-key
QWEN_API_KEY=your-qwen-key
QWEN_API_BASE=https://<openai-compatible-endpoint>
REASONING_PROVIDER=qwen
GENERATION_PROVIDER=gemini
```

## Limits / 한계·주의
- Qwen requires OpenAI-compatible REST endpoint + key.  
- Embedding is Gemini-only today.  
- Singleton manager: long-running processes may need cache reset/reload for model changes.
