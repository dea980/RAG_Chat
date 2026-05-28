"""Token counting helpers for model/language comparison.

OpenAI-compatible profiles use `tiktoken` encodings where available. Gemini,
Claude, and Qwen rows are intentionally labelled as estimates because their
production tokenizers differ from OpenAI's encodings.
"""
from __future__ import annotations

import os
from functools import lru_cache
from math import ceil
from typing import Any

try:
    import tiktoken
except ImportError:  # pragma: no cover - dependency should be installed
    tiktoken = None  # type: ignore


EXACT_PROFILES = [
    {
        "id": "openai_o200k",
        "label": "GPT-4o / o-series",
        "encoding": "o200k_base",
        "note": "OpenAI o200k_base tokenizer.",
    },
    {
        "id": "openai_cl100k",
        "label": "GPT-4 / GPT-3.5 / text-embedding-3",
        "encoding": "cl100k_base",
        "note": "OpenAI cl100k_base tokenizer.",
    },
    {
        "id": "openai_p50k",
        "label": "Legacy code models",
        "encoding": "p50k_base",
        "note": "OpenAI p50k_base tokenizer.",
    },
]


ESTIMATE_PROFILES = [
    {
        "id": "gemini_estimate",
        "label": "Gemini estimate",
        "basis": "openai_o200k",
        "multiplier": 1.05,
        "note": "Approximation based on OpenAI o200k token count.",
    },
    {
        "id": "claude_estimate",
        "label": "Claude estimate",
        "basis": "openai_cl100k",
        "multiplier": 1.00,
        "note": "Approximation based on OpenAI cl100k token count.",
    },
    {
        "id": "qwen_estimate",
        "label": "Qwen estimate",
        "basis": "openai_cl100k",
        "multiplier": 1.08,
        "note": "Approximation based on OpenAI cl100k token count.",
    },
    {
        "id": "gpt_oss_estimate",
        "label": "gpt-oss estimate",
        "basis": "openai_o200k",
        "multiplier": 1.00,
        "note": "gpt-oss uses o200k_harmony (same base vocab as o200k_base, "
                "+ harmony chat format). Estimate via o200k_base token count.",
    },
]


LANGUAGE_SAMPLES = [
    {
        "language": "Korean",
        "text": "갤럭시 S25 울트라의 카메라 사양과 가격을 요약해 주세요.",
    },
    {
        "language": "English",
        "text": "Summarize the camera specifications and price of the Galaxy S25 Ultra.",
    },
    {
        "language": "Japanese",
        "text": "Galaxy S25 Ultra のカメラ仕様と価格を要約してください。",
    },
    {
        "language": "Chinese",
        "text": "请总结 Galaxy S25 Ultra 的相机规格和价格。",
    },
    {
        "language": "Code",
        "text": "def price_with_tax(price: float) -> float:\n    return round(price * 1.1, 2)",
    },
    {
        "language": "Mixed",
        "text": "S25 Ultra 512GB 모델의 price와 camera specs를 비교해줘.",
    },
]


@lru_cache(maxsize=8)
def _encoding_for(name: str):
    if tiktoken is None:
        return None
    if os.getenv("TOKENLAB_ENABLE_TIKTOKEN", "0") != "1":
        return None
    try:
        return tiktoken.get_encoding(name)
    except Exception:
        # Some encodings (notably o200k_base) may not be cached locally and
        # tiktoken attempts a network fetch. Token Lab must remain offline-safe.
        return None


def _fallback_token_count(text: str) -> int:
    """Coarse fallback when tiktoken is unavailable."""
    if not text:
        return 0
    return max(1, ceil(len(text.encode("utf-8")) / 4))


def _exact_count(text: str, encoding_name: str) -> tuple[int, str]:
    encoding = _encoding_for(encoding_name)
    if encoding is None:
        return _fallback_token_count(text), "fallback"
    return len(encoding.encode(text)), "exact"


def _ratio(tokens: int, characters: int) -> float:
    if characters == 0:
        return 0.0
    return round(tokens / characters, 3)


def analyze_text(text: str) -> dict[str, Any]:
    """Return token counts across supported model profiles."""
    characters = len(text)
    byte_count = len(text.encode("utf-8"))

    profiles: list[dict[str, Any]] = []
    exact_counts: dict[str, int] = {}
    for profile in EXACT_PROFILES:
        tokens, method = _exact_count(text, profile["encoding"])
        exact_counts[profile["id"]] = tokens
        profiles.append({
            "id": profile["id"],
            "label": profile["label"],
            "method": method,
            "tokenizer": profile["encoding"],
            "tokens": tokens,
            "tokens_per_character": _ratio(tokens, characters),
            "note": profile["note"],
        })

    for profile in ESTIMATE_PROFILES:
        basis_count = exact_counts.get(profile["basis"], _fallback_token_count(text))
        tokens = int(round(basis_count * profile["multiplier"]))
        if text and tokens == 0:
            tokens = 1
        profiles.append({
            "id": profile["id"],
            "label": profile["label"],
            "method": "estimate",
            "tokenizer": profile["basis"],
            "tokens": tokens,
            "tokens_per_character": _ratio(tokens, characters),
            "note": profile["note"],
        })

    reference_tokens = exact_counts.get("openai_cl100k", _fallback_token_count(text))
    chunk_targets = [250, 500, 1000, 2000]
    chunk_recommendations = [
        {
            "target_tokens": target,
            "estimated_chunks": ceil(reference_tokens / target) if reference_tokens else 0,
        }
        for target in chunk_targets
    ]

    return {
        "text_preview": text[:160],
        "characters": characters,
        "bytes": byte_count,
        "profiles": profiles,
        "reference_profile": "openai_cl100k",
        "reference_tokens": reference_tokens,
        "chunk_recommendations": chunk_recommendations,
    }


def language_sample_comparison() -> list[dict[str, Any]]:
    """Return fixed language sample token comparisons."""
    rows = []
    for sample in LANGUAGE_SAMPLES:
        analysis = analyze_text(sample["text"])
        rows.append({
            "language": sample["language"],
            "text": sample["text"],
            "characters": analysis["characters"],
            "bytes": analysis["bytes"],
            "profiles": analysis["profiles"],
        })
    return rows
