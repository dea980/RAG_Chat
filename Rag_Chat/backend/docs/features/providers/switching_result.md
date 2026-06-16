# Model Provider Switching Result

Date: 2026-05-27

## Summary

RAG Chat now separates chat LLM provider switching from embedding configuration.

Chat LLM providers can be changed by session through the existing `/providers/` API and Streamlit sidebar. Embedding configuration is exposed separately as system-scoped metadata because changing embedding models requires rebuilding the Chroma vector index.

## Added Chat Providers

The chat provider layer now supports:

- `gemini`
- `qwen`
- `openrouter`
- `ollama`
- `huggingface`

## Ollama Support

Ollama is wired through LangChain's OpenAI-compatible `ChatOpenAI` client.

Environment variables:

```env
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1
# OLLAMA_REASONING_MODEL=llama3.1
# OLLAMA_GENERATION_MODEL=qwen2.5:7b
```

Use `ollama serve` before selecting the Ollama provider.

## Hugging Face Support

Hugging Face support expects an OpenAI-compatible endpoint, such as a Hugging Face Inference Endpoint or TGI deployment.

Environment variables:

```env
HUGGINGFACE_API_KEY=
HUGGINGFACE_BASE_URL=
HUGGINGFACE_MODEL=meta-llama/Llama-3.1-8B-Instruct
# HUGGINGFACE_REASONING_MODEL=
# HUGGINGFACE_GENERATION_MODEL=
```

This intentionally does not assume that a plain Hugging Face model ID is enough to run chat generation.

## Embedding Configuration

Embedding configuration is kept separate from chat LLM provider selection.

Environment variables:

```env
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=models/text-embedding-004
GOOGLE_EMBEDDING_MODEL=models/text-embedding-004
OPENROUTER_EMBEDDING_MODEL=nvidia/llama-nemotron-embed-v1-1b-v2:free
```

Embedding changes are system-scoped. They are not session overrides.

Changing the embedding provider or model requires rebuilding the Chroma vector index because vector dimensions and embedding spaces may differ.

## API Changes

`GET /api/v1/triple/providers/` now returns chat provider selection plus embedding configuration.

Example shape:

```json
{
  "session_id": "session-1",
  "selection": {
    "reasoning_provider": "ollama",
    "generation_provider": "ollama"
  },
  "override": {},
  "embedding": {
    "provider": "gemini",
    "model": "models/text-embedding-004",
    "scope": "system",
    "requires_reindex": true
  }
}
```

Supported preset values now include:

- `gemini_only`
- `qwen_reasoning_gemini_generation`
- `qwen_only`
- `openrouter_only`
- `ollama_only`
- `huggingface_only`

## UI Changes

The Streamlit sidebar now includes provider presets for:

- OpenRouter Only
- Ollama Only
- Hugging Face Only

The sidebar also displays the current embedding configuration separately and notes that embedding changes require rebuilding the vector index.

## Files Changed

- `Rag_Chat/backend/chat/providers/manager.py`
- `Rag_Chat/backend/chat/views.py`
- `Rag_Chat/backend/chat/tests/test_provider_manager.py`
- `Rag_Chat/backend/chat/tests/test_views.py`
- `Rag_Chat/frontend/app.py`
- `Rag_Chat/.env.example`
- `Rag_Chat/backend/README.md`

## Verification

The following checks passed:

```bash
python3 manage.py test chat.tests.test_provider_manager chat.tests.test_views.ProviderConfigAPIViewTestCase -v 2
```

Result: 7 tests passed.

```bash
python3 -m py_compile frontend/app.py frontend/api.py
```

Result: passed.

```bash
python3 -m py_compile backend/chat/providers/manager.py backend/chat/views.py
```

Result: passed.

