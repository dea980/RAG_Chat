"""Provider factory utilities for embeddings, reasoning models, and generation models.

This module exposes a singleton ``provider_manager`` that returns the configured
providers based on environment variables. The goal is to make model swaps (e.g.,
Gemini ↔ Qwen) a matter of configuration rather than code edits.
"""

from .manager import ProviderManager

provider_manager = ProviderManager()

__all__ = ["provider_manager", "ProviderManager"]
