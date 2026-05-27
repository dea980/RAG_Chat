# Model Provider Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Ollama and Hugging Face chat provider switching while exposing embedding configuration separately.

**Architecture:** Extend the existing `ProviderManager` instead of introducing a new abstraction. Session-scoped chat provider overrides continue to flow through `/providers/`; embedding stays system-scoped and read-only because vector indexes must be rebuilt after embedding changes.

**Tech Stack:** Django REST Framework, LangChain `ChatOpenAI`, Streamlit, pytest/Django tests.

---

### Task 1: Provider Manager

**Files:**
- Modify: `Rag_Chat/backend/chat/providers/manager.py`
- Test: `Rag_Chat/backend/chat/tests/test_provider_manager.py`

- [ ] Add failing tests for Ollama chat model construction, Hugging Face chat model construction, and embedding config exposure.
- [ ] Run the targeted provider manager tests and confirm they fail because the methods/providers do not exist yet.
- [ ] Implement `_create_ollama_chat_model`, `_create_huggingface_chat_model`, provider routing, and `get_embedding_config`.
- [ ] Run the targeted provider manager tests and confirm they pass.

### Task 2: Provider API

**Files:**
- Modify: `Rag_Chat/backend/chat/views.py`
- Test: `Rag_Chat/backend/chat/tests/test_views.py`

- [ ] Add failing API tests showing `/providers/` accepts `ollama_only` and `huggingface_only`, rejects unknown providers, and returns embedding config.
- [ ] Run the targeted view tests and confirm they fail for missing provider support.
- [ ] Extend `COMBO_MAP`, `VALID_PROVIDERS`, and GET/POST responses.
- [ ] Run the targeted view tests and confirm they pass.

### Task 3: Frontend And Env Docs

**Files:**
- Modify: `Rag_Chat/frontend/app.py`
- Modify: `Rag_Chat/.env.example`
- Modify: `Rag_Chat/backend/README.md`

- [ ] Add Ollama/Hugging Face presets to the Streamlit sidebar.
- [ ] Show embedding configuration in a separate sidebar section.
- [ ] Document `OLLAMA_*`, `HUGGINGFACE_*`, and generic embedding env vars with a reindexing warning.
- [ ] Run backend tests touched by the provider change.
