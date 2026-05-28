"""Chat Compare lab — side-by-side LLM response comparison.

`POST /api/v1/triple/chat/compare/` accepts a prompt and a list of model
specs (`provider:model` or `provider`) and invokes each model directly via
``ProviderManager.build_chat_model_explicit``. RAG / moderation / DB write
are all bypassed because this endpoint exists to compare raw model behavior,
not to serve production chat.

Request:
    {
      "prompt": "...",
      "models": ["ollama:qwen3.6", "ollama:gpt-oss", "gemini", "openrouter"]
    }

Response:
    {"results": [{"spec": "...", "response": "...", "elapsed_ms": int}, ...]}
"""
from __future__ import annotations

import logging
import time

from langchain_core.messages import HumanMessage
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .providers.manager import ProviderManager

logger = logging.getLogger(__name__)


class CompareRateThrottle(UserRateThrottle):
    rate = "30/minute"


def _parse_spec(spec: str) -> tuple[str, str | None]:
    """`"ollama:gpt-oss"` -> `("ollama", "gpt-oss")`. `"gemini"` -> `("gemini", None)`."""
    provider, sep, model = spec.partition(":")
    return provider.strip().lower(), (model.strip() or None)


class ChatCompareAPIView(APIView):
    """Run the same prompt against N models and return their responses side by side."""

    permission_classes = [AllowAny]
    throttle_classes = [CompareRateThrottle]

    def post(self, request):
        prompt = (request.data.get("prompt") or "").strip()
        specs = request.data.get("models") or []
        if not prompt:
            return Response(
                {"error": "prompt 가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(specs, list) or not specs:
            return Response(
                {"error": "models 리스트가 필요합니다 (예: ['ollama:gpt-oss'])."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        manager = ProviderManager()
        results = []
        for spec in specs:
            if not isinstance(spec, str) or not spec.strip():
                results.append({"spec": str(spec), "error": "invalid spec"})
                continue
            provider, model = _parse_spec(spec)
            t0 = time.time()
            try:
                chat_model = manager.build_chat_model_explicit(provider, model)
                result = chat_model.invoke([HumanMessage(content=prompt)])
                content = getattr(result, "content", str(result))
                results.append({
                    "spec": spec,
                    "provider": provider,
                    "model": model,
                    "response": content,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                })
            except Exception as exc:
                logger.warning("chat-compare invoke failed for %s: %s", spec, exc)
                results.append({
                    "spec": spec,
                    "provider": provider,
                    "model": model,
                    "error": str(exc),
                    "elapsed_ms": int((time.time() - t0) * 1000),
                })
        return Response({"prompt": prompt, "results": results}, status=status.HTTP_200_OK)
