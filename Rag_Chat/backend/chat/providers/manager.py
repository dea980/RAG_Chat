from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Dict, Optional, Tuple

from django.conf import settings

try:
    from langchain_google_genai import (
        ChatGoogleGenerativeAI,
        GoogleGenerativeAIEmbeddings,
    )
except ImportError:  # pragma: no cover - optional dependency handled at runtime
    ChatGoogleGenerativeAI = None  # type: ignore
    GoogleGenerativeAIEmbeddings = None  # type: ignore

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError:  # pragma: no cover
    ChatOpenAI = None  # type: ignore
    OpenAIEmbeddings = None  # type: ignore

from langchain_community.vectorstores import Chroma

from ..provider_overrides import get_override

logger = logging.getLogger(__name__)


class ProviderManager:
    """Central point for resolving embedding and chat providers.

    Environment variables control which providers are used:

    - ``EMBEDDING_PROVIDER``: ``gemini`` (default)
    - ``REASONING_PROVIDER``: ``gemini`` (default) or ``qwen``
    - ``GENERATION_PROVIDER``: ``gemini`` (default) or ``qwen``

    Additional variables:

    - ``GOOGLE_API_KEY``
    - ``GOOGLE_EMBEDDING_MODEL`` (default ``models/text-embedding-004``)
    - ``GOOGLE_CHAT_MODEL`` (default ``gemini-1.5-pro``)
    - ``QWEN_API_KEY`` / ``QWEN_API_BASE`` / ``QWEN_MODEL_NAME``
    - ``QWEN_REASONING_MODEL`` (optional override for reasoning)
    - ``QWEN_GENERATION_MODEL`` (optional override for generation)
    """

    def __init__(self) -> None:
        """Initialise provider defaults from environment variables."""
        self.embedding_provider_name = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()
        self.reasoning_provider_name = os.getenv("REASONING_PROVIDER", "gemini").lower()
        self.generation_provider_name = os.getenv("GENERATION_PROVIDER", "gemini").lower()

        self._embedding_model = None
        self._vector_store_cache = None
        self._chat_model_cache: Dict[Tuple[str, str], object] = {}
        self._reranker = None
        self._reranker_init_attempted = False

    def get_reranker(self):
        """Return a singleton ONNX reranker, or None if disabled / unavailable.

        Honors:
        - RERANKER_ENABLED (default "0"): set to "1" to enable.
        - RERANKER_MODEL (default "BAAI/bge-reranker-v2-m3").
        - RERANKER_DEVICE (default "cpu").
        """
        if os.getenv("RERANKER_ENABLED", "0") != "1":
            return None
        if self._reranker is not None:
            return self._reranker
        if self._reranker_init_attempted:
            return None  # prior init failed; do not retry on every request
        self._reranker_init_attempted = True
        try:
            from ..rerankers import OnnxBgeReranker  # local import to avoid heavy load at startup
            self._reranker = OnnxBgeReranker(
                model_id=os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
                device=os.getenv("RERANKER_DEVICE", "cpu"),
            )
            return self._reranker
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error("Failed to initialise reranker: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Embeddings / Vector store
    # ------------------------------------------------------------------
    def get_embedding_model(self):
        """Return a LangChain embedding model instance."""

        if self._embedding_model is None:
            if self.embedding_provider_name == "gemini":
                self._embedding_model = self._create_gemini_embeddings()
            elif self.embedding_provider_name == "openrouter":
                self._embedding_model = self._create_openrouter_embeddings()
            else:
                raise ValueError(
                    f"Unsupported embedding provider: {self.embedding_provider_name}"
                )
        return self._embedding_model

    def get_embedding_config(self) -> Dict[str, object]:
        """Return system-scoped embedding config for UI/API display."""
        provider = self.embedding_provider_name
        model = os.getenv("EMBEDDING_MODEL")
        if not model:
            if provider == "gemini":
                model = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/text-embedding-004")
            elif provider == "openrouter":
                model = os.getenv(
                    "OPENROUTER_EMBEDDING_MODEL",
                    "nvidia/llama-nemotron-embed-v1-1b-v2:free",
                )
            else:
                model = os.getenv(f"{provider.upper()}_EMBEDDING_MODEL", "")
        return {
            "provider": provider,
            "model": model,
            "scope": "system",
            "requires_reindex": True,
        }

    def get_vector_store(self):
        """Construct a Chroma vector store hooked to the embedding model."""

        embeddings = self.get_embedding_model()
        return Chroma(
            persist_directory=settings.VECTOR_STORE_PATH,
            embedding_function=embeddings,
        )

    def create_vector_store_from_documents(self, documents):
        embeddings = self.get_embedding_model()
        return Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=settings.VECTOR_STORE_PATH,
        )

    def _create_gemini_embeddings(self):
        if GoogleGenerativeAIEmbeddings is None:
            raise ImportError(
                "langchain-google-genai must be installed to use Gemini embeddings"
            )

        api_key = self._resolve_google_api_key()
        model = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/text-embedding-004")
        return GoogleGenerativeAIEmbeddings(
            model=model,
            google_api_key=api_key,
        )

    # ------------------------------------------------------------------
    # Reasoning / generation models
    # ------------------------------------------------------------------
    def get_reasoning_model(self, session_id: Optional[str] = None):
        """Return the reasoning chat model for the given session."""
        selection = self._resolve_provider_selection(session_id)
        return self._get_cached_chat_model(selection["reasoning_provider"], "REASONING")

    def get_generation_model(self, session_id: Optional[str] = None):
        """Return the generation chat model for the given session."""
        selection = self._resolve_provider_selection(session_id)
        return self._get_cached_chat_model(selection["generation_provider"], "GENERATION")

    def get_active_selection(self, session_id: Optional[str] = None) -> Dict[str, str]:
        """Expose the resolved provider choice for external consumers."""
        return self._resolve_provider_selection(session_id)

    def _get_cached_chat_model(self, provider: str, purpose: str):
        """Return a cached chat model or build it if not available."""
        key = (provider, purpose)
        if key not in self._chat_model_cache:
            self._chat_model_cache[key] = self._create_chat_model(provider, purpose)
        return self._chat_model_cache[key]

    def _resolve_provider_selection(self, session_id: Optional[str]) -> Dict[str, str]:
        """Resolve defaults merged with any session override."""
        reasoning = self.reasoning_provider_name
        generation = self.generation_provider_name
        if session_id:
            override = get_override(session_id)
            reasoning = override.get("reasoning_provider") or reasoning
            generation = override.get("generation_provider") or generation
        return {
            "reasoning_provider": reasoning,
            "generation_provider": generation,
        }

    def _create_chat_model(self, provider: str, purpose: str):
        provider = provider.lower()
        if provider == "gemini":
            return self._create_gemini_chat_model(purpose)
        if provider == "qwen":
            return self._create_qwen_chat_model(purpose)
        if provider == "openrouter":
            return self._create_openrouter_chat_model(purpose)
        if provider == "ollama":
            return self._create_ollama_chat_model(purpose)
        if provider == "huggingface":
            return self._create_huggingface_chat_model(purpose)
        raise ValueError(f"Unsupported chat provider: {provider}")

    def build_chat_model_explicit(
        self, provider: str, model: Optional[str] = None,
        purpose: str = "GENERATION",
    ):
        """Build a chat model with an optional explicit model name.

        Used by the side-by-side chat-compare lab endpoint where the caller
        specifies provider + model at runtime (e.g., ``ollama:gpt-oss`` vs
        ``ollama:qwen3.6``). Not cached — comparison runs need fresh
        instances since (provider, model) is the key not (provider, purpose).
        Falls back to the env-based factory when ``model`` is None.
        """
        provider = provider.lower()
        if model is None:
            return self._create_chat_model(provider, purpose)

        temperature = float(os.getenv(f"{purpose}_TEMPERATURE", "0.7"))

        if provider == "ollama":
            if ChatOpenAI is None:
                raise ImportError("langchain-openai required for Ollama")
            return ChatOpenAI(
                api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                model=model,
                temperature=temperature,
            )
        if provider == "qwen":
            if ChatOpenAI is None:
                raise ImportError("langchain-openai required for Qwen")
            api_key = os.getenv("QWEN_API_KEY")
            base_url = os.getenv("QWEN_API_BASE")
            if not api_key or not base_url:
                raise RuntimeError("QWEN_API_KEY and QWEN_API_BASE required")
            return ChatOpenAI(
                api_key=api_key, base_url=base_url,
                model=model, temperature=temperature,
            )
        if provider == "openrouter":
            if ChatOpenAI is None:
                raise ImportError("langchain-openai required for OpenRouter")
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY required")
            return ChatOpenAI(
                api_key=api_key,
                base_url=self._openrouter_base_url(),
                model=model,
                temperature=temperature,
                default_headers=self._openrouter_headers() or None,
            )
        if provider == "huggingface":
            if ChatOpenAI is None:
                raise ImportError("langchain-openai required for HuggingFace")
            api_key = os.getenv("HUGGINGFACE_API_KEY")
            base_url = os.getenv("HUGGINGFACE_BASE_URL")
            if not api_key or not base_url:
                raise RuntimeError("HUGGINGFACE_API_KEY and HUGGINGFACE_BASE_URL required")
            return ChatOpenAI(
                api_key=api_key, base_url=base_url,
                model=model, temperature=temperature,
            )
        if provider == "gemini":
            if ChatGoogleGenerativeAI is None:
                raise ImportError("langchain-google-genai required for Gemini")
            api_key = self._resolve_google_api_key()
            max_tokens = int(os.getenv(f"{purpose}_MAX_OUTPUT_TOKENS", "2048"))
            return ChatGoogleGenerativeAI(
                model=model, google_api_key=api_key,
                temperature=temperature, max_output_tokens=max_tokens,
            )
        raise ValueError(f"Unsupported chat provider: {provider}")

    def _create_gemini_chat_model(self, purpose: str):
        if ChatGoogleGenerativeAI is None:
            raise ImportError(
                "langchain-google-genai must be installed to use Gemini chat models"
            )

        api_key = self._resolve_google_api_key()
        model_name = os.getenv("GOOGLE_CHAT_MODEL", "gemini-1.5-pro")
        temperature = float(os.getenv(f"{purpose}_TEMPERATURE", "0.7"))
        max_tokens = int(os.getenv(f"{purpose}_MAX_OUTPUT_TOKENS", "2048"))
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    def _create_qwen_chat_model(self, purpose: str):
        if ChatOpenAI is None:
            raise ImportError(
                "langchain-openai must be installed to use OpenAI-compatible providers"
            )

        api_key = os.getenv("QWEN_API_KEY")
        base_url = os.getenv("QWEN_API_BASE")
        if not api_key or not base_url:
            raise RuntimeError(
                "QWEN_API_KEY and QWEN_API_BASE must be set to use the Qwen provider"
            )
        default_model = os.getenv("QWEN_MODEL_NAME", "qwen2.5-72b-instruct")
        model_override = os.getenv(f"QWEN_{purpose}_MODEL")
        model_name = model_override or default_model
        temperature = float(os.getenv(f"{purpose}_TEMPERATURE", "0.7"))

        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
        )

    def _create_ollama_chat_model(self, purpose: str):
        if ChatOpenAI is None:
            raise ImportError(
                "langchain-openai must be installed to use Ollama chat models"
            )

        default_model = os.getenv("OLLAMA_MODEL", "llama3.1")
        model_override = os.getenv(f"OLLAMA_{purpose}_MODEL")
        model_name = model_override or default_model
        temperature = float(os.getenv(f"{purpose}_TEMPERATURE", "0.7"))
        return ChatOpenAI(
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            model=model_name,
            temperature=temperature,
        )

    def _create_huggingface_chat_model(self, purpose: str):
        if ChatOpenAI is None:
            raise ImportError(
                "langchain-openai must be installed to use Hugging Face chat models"
            )

        api_key = os.getenv("HUGGINGFACE_API_KEY")
        base_url = os.getenv("HUGGINGFACE_BASE_URL")
        if not api_key or not base_url:
            raise RuntimeError(
                "HUGGINGFACE_API_KEY and HUGGINGFACE_BASE_URL must be set to use the Hugging Face provider"
            )
        default_model = os.getenv("HUGGINGFACE_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
        model_override = os.getenv(f"HUGGINGFACE_{purpose}_MODEL")
        model_name = model_override or default_model
        temperature = float(os.getenv(f"{purpose}_TEMPERATURE", "0.7"))
        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
        )

    # ------------------------------------------------------------------
    # OpenRouter (OpenAI-compatible) — single API key gives access to
    # Gemini / Llama / Qwen / DeepSeek / etc. Free-tier models keep LLM
    # cost at zero for the sales-team beta.
    # ------------------------------------------------------------------
    def _openrouter_base_url(self) -> str:
        return os.getenv("OPENROUTER_BASE", "https://openrouter.ai/api/v1")

    def _openrouter_headers(self) -> Dict[str, str]:
        # Optional headers OpenRouter recommends for leaderboard / referer.
        headers: Dict[str, str] = {}
        referer = os.getenv("OPENROUTER_HTTP_REFERER")
        title = os.getenv("OPENROUTER_X_TITLE")
        if referer:
            headers["HTTP-Referer"] = referer
        if title:
            headers["X-Title"] = title
        return headers

    def _create_openrouter_embeddings(self):
        if OpenAIEmbeddings is None:
            raise ImportError(
                "langchain-openai must be installed to use OpenRouter embeddings"
            )
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY must be set to use OpenRouter embeddings")
        model = os.getenv(
            "OPENROUTER_EMBEDDING_MODEL",
            "nvidia/llama-nemotron-embed-v1-1b-v2:free",
        )
        return OpenAIEmbeddings(
            api_key=api_key,
            base_url=self._openrouter_base_url(),
            model=model,
            default_headers=self._openrouter_headers() or None,
        )

    def _create_openrouter_chat_model(self, purpose: str):
        if ChatOpenAI is None:
            raise ImportError(
                "langchain-openai must be installed to use OpenRouter chat models"
            )
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY must be set to use the OpenRouter provider")
        default_model = os.getenv(
            "OPENROUTER_MODEL_NAME",
            "meta-llama/llama-3.3-70b-instruct:free",
        )
        model_override = os.getenv(f"OPENROUTER_{purpose}_MODEL")
        model_name = model_override or default_model
        temperature = float(os.getenv(f"{purpose}_TEMPERATURE", "0.7"))
        return ChatOpenAI(
            api_key=api_key,
            base_url=self._openrouter_base_url(),
            model=model_name,
            temperature=temperature,
            default_headers=self._openrouter_headers() or None,
        )

    # ------------------------------------------------------------------
    def _resolve_google_api_key(self) -> str:
        api_key = os.getenv("GOOGLE_API_KEY") or getattr(settings, "GOOGLE_API_KEY", None)
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not configured. Set it via environment or settings."
            )
        return api_key
