"""Embedding Lab — Pair Compare endpoint.

`POST /api/v1/triple/embeddings/compare` 가 두 텍스트와 모델 리스트를 받아
모델별 유사도를 돌려준다. design.md Mode A. 사이드바이사이드 비교용이라
저장·캐시 결과 누적 없음 (in-process lru_cache 만).

모델 등록은 ``EMBEDDING_REGISTRY`` dict — 새 모델은 여기 한 줄 추가.
"""
from __future__ import annotations

import logging
import math
import os
from functools import lru_cache
from typing import Any, Callable

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .providers.manager import ProviderManager

logger = logging.getLogger(__name__)


class EmbeddingLabRateThrottle(UserRateThrottle):
    rate = "30/minute"


# ---------------------------------------------------------------------------
# Model registry — extend this dict to add new models. Each entry declares
# its "kind":
#   - "embedding"   : returns a vector per text → cosine similarity
#   - "cross"       : returns a relevance score for (text1, text2) directly
# Loaders are wrapped with @lru_cache so subsequent calls reuse the loaded
# model. First-call download cost is on the user (sentence-transformers
# pulls ~2GB from Hugging Face Hub).
# ---------------------------------------------------------------------------


@lru_cache(maxsize=8)
def _load_st_model(model_id: str):
    """Lazy-load a sentence-transformers model. Heavy first call (~2GB DL)."""
    from sentence_transformers import SentenceTransformer
    home = os.getenv("SENTENCE_TRANSFORMERS_HOME")
    if home:
        return SentenceTransformer(model_id, cache_folder=home)
    return SentenceTransformer(model_id)


@lru_cache(maxsize=1)
def _load_gemini_embedder():
    """Reuse provider manager's Gemini embedding."""
    manager = ProviderManager()
    # Force-resolve gemini regardless of EMBEDDING_PROVIDER env.
    return manager._create_gemini_embeddings()  # noqa: SLF001


@lru_cache(maxsize=1)
def _load_onnx_reranker():
    """Reuse the ONNX BGE reranker as a cross-encoder for pair similarity."""
    from .rerankers import OnnxBgeReranker
    return OnnxBgeReranker(
        model_id=os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
        device=os.getenv("RERANKER_DEVICE", "cpu"),
    )


def _embed_st_pair(model_id: str, text1: str, text2: str) -> dict[str, Any]:
    model = _load_st_model(model_id)
    vec1, vec2 = model.encode([text1, text2], convert_to_numpy=True)
    return {
        "kind": "cosine",
        "score": _cosine(vec1.tolist(), vec2.tolist()),
        "dim": len(vec1),
    }


def _embed_gemini_pair(_: str, text1: str, text2: str) -> dict[str, Any]:
    embedder = _load_gemini_embedder()
    vec1 = embedder.embed_query(text1)
    vec2 = embedder.embed_query(text2)
    return {"kind": "cosine", "score": _cosine(vec1, vec2), "dim": len(vec1)}


def _score_reranker_pair(_: str, text1: str, text2: str) -> dict[str, Any]:
    reranker = _load_onnx_reranker()
    scores = reranker.score(text1, [text2])
    return {"kind": "cross", "score": float(scores[0]) if scores else 0.0}


EMBEDDING_REGISTRY: dict[str, dict[str, Any]] = {
    "bge-m3": {
        "label": "BAAI/bge-m3 (다국어, 한국어 강함)",
        "kind": "embedding",
        "model_id": "BAAI/bge-m3",
        "handler": _embed_st_pair,
        "note": "sentence-transformers · 첫 호출 시 ~2GB 다운로드.",
    },
    "e5-large": {
        "label": "intfloat/multilingual-e5-large",
        "kind": "embedding",
        "model_id": "intfloat/multilingual-e5-large",
        "handler": _embed_st_pair,
        "note": "sentence-transformers · 첫 호출 시 ~2GB 다운로드.",
    },
    "gemini": {
        "label": "Gemini text-embedding-004 (현재 default)",
        "kind": "embedding",
        "model_id": "models/text-embedding-004",
        "handler": _embed_gemini_pair,
        "note": "기존 provider 재사용 · GOOGLE_API_KEY 필요.",
    },
    "reranker-bge": {
        "label": "ONNX bge-reranker-v2-m3 (cross-encoder)",
        "kind": "cross",
        "model_id": "BAAI/bge-reranker-v2-m3",
        "handler": _score_reranker_pair,
        "note": "벡터 X · (text1, text2) 직접 score. 다른 cosine 값과 단위 다름.",
    },
}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return round(dot / (na * nb), 4)


def list_registered_models() -> list[dict[str, Any]]:
    return [
        {"id": key, "label": spec["label"], "kind": spec["kind"], "note": spec["note"]}
        for key, spec in EMBEDDING_REGISTRY.items()
    ]


class EmbeddingCompareAPIView(APIView):
    """Pair compare — two texts, N models, returns cosine/cross score per model."""

    permission_classes = [AllowAny]
    throttle_classes = [EmbeddingLabRateThrottle]

    def get(self, request):
        """List registered embedding models (frontend dropdown 용)."""
        return Response({"models": list_registered_models()})

    def post(self, request):
        text1 = (request.data.get("text1") or "").strip()
        text2 = (request.data.get("text2") or "").strip()
        models = request.data.get("models") or []
        if not text1 or not text2:
            return Response(
                {"error": "text1, text2 둘 다 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(models, list) or not models:
            return Response(
                {"error": "models 리스트가 필요합니다 (예: ['gemini', 'bge-m3'])."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results: dict[str, Any] = {}
        for key in models:
            spec = EMBEDDING_REGISTRY.get(key)
            if spec is None:
                results[key] = {"error": f"unknown model: {key}"}
                continue
            handler: Callable[[str, str, str], dict[str, Any]] = spec["handler"]
            try:
                results[key] = {
                    **handler(spec["model_id"], text1, text2),
                    "label": spec["label"],
                }
            except Exception as exc:
                logger.warning("embedding compare failed (%s): %s", key, exc)
                results[key] = {"error": str(exc), "label": spec["label"]}
        return Response({"text1": text1, "text2": text2, "results": results})
