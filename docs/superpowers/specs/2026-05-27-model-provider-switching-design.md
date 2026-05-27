# Model Provider Switching Design

## Goal

Add first-class model switching for chat LLM providers while keeping embedding configuration separate because embedding changes require vector reindexing.

## Architecture

The existing `ProviderManager` remains the central factory. Chat selection stays session-scoped through `/providers/` and Redis/cache overrides. Embedding selection is exposed as system configuration only; it is not changed per session because Chroma indexes are tied to the embedding model and dimensions.

## Chat Providers

Supported chat providers become `gemini`, `qwen`, `openrouter`, `ollama`, and `huggingface`.

Ollama uses LangChain's OpenAI-compatible `ChatOpenAI` client with `OLLAMA_BASE_URL` defaulting to `http://localhost:11434/v1` and placeholder API key `ollama`.

Hugging Face uses an OpenAI-compatible endpoint through `ChatOpenAI`. Operators provide `HUGGINGFACE_BASE_URL`, `HUGGINGFACE_API_KEY`, and model variables. This supports Hugging Face Inference Endpoints or TGI deployments that expose an OpenAI-compatible API.

## Embedding Configuration

Embedding provider/model is resolved separately from chat providers. `/providers/` includes an `embedding` object showing provider, model, and whether reindexing is required when changed. The first implementation only exposes this state and environment variables; runtime mutation is intentionally avoided.

## UI

The Streamlit sidebar keeps chat provider presets and adds Ollama/Hugging Face presets. It also shows the active embedding configuration in a separate section with a reindexing note.

## Testing

Add tests around `ProviderManager` model construction and `/providers/` validation/response behavior. Tests mock LangChain clients, so no external model service is required.
