"""Embedding intrinsic evaluation harness.

Pair-based (cosine vs gold) evaluation — complements the retrieval-based
A/B harness in ``chat/tests/evals/run_embedding_ab.py``.

Supported datasets (under ``Rag_Chat/backend/data/``):
- KorSTS dev/test (0~5 score)         → Pearson/Spearman correlation
- KorNLI dev/test (entail/neu/contra) → bucket separation
- curated YAML (positive/neg/hard)    → bucket separation (도메인 특화)

Backend models reuse ``embedding_views.EMBEDDING_REGISTRY``. New model =
one entry there; no change here.
"""
from __future__ import annotations

import csv
import logging
import math
import os
import random
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .embedding_views import (
    EMBEDDING_REGISTRY,
    _cosine,
    _load_gemini_embedder,
    _load_onnx_reranker,
    _load_st_model,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class EvalPair:
    text1: str
    text2: str
    label: float | str           # KorSTS = float, others = string bucket name
    bucket: str = ""             # canonical bucket: positive / negative / hard_negative / neutral
    category: str = ""
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dataset loaders
# ---------------------------------------------------------------------------


def load_korsts(path: Path, limit: int | None = None) -> list[EvalPair]:
    pairs: list[EvalPair] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break
            try:
                score = float(row["score"])
            except (KeyError, ValueError):
                continue
            if score >= 4.0:
                bucket = "positive"
            elif score <= 1.0:
                bucket = "negative"
            else:
                bucket = "neutral"
            pairs.append(EvalPair(
                text1=row["sentence1"].strip(),
                text2=row["sentence2"].strip(),
                label=score,
                bucket=bucket,
            ))
    return pairs


def load_kornli(path: Path, limit: int | None = None) -> list[EvalPair]:
    bucket_map = {
        "entailment": "positive",
        "contradiction": "hard_negative",
        "neutral": "neutral",
    }
    pairs: list[EvalPair] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break
            label = (row.get("gold_label") or "").strip()
            bucket = bucket_map.get(label, "neutral")
            pairs.append(EvalPair(
                text1=(row.get("sentence1") or "").strip(),
                text2=(row.get("sentence2") or "").strip(),
                label=label,
                bucket=bucket,
            ))
    return pairs


def load_curated(path: Path, limit: int | None = None) -> list[EvalPair]:
    import yaml
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    pairs: list[EvalPair] = []
    for bucket in ("positive", "negative", "hard_negative"):
        for entry in (data.get(bucket) or []):
            pairs.append(EvalPair(
                text1=entry.get("text1", "").strip(),
                text2=entry.get("text2", "").strip(),
                label=bucket,
                bucket=bucket,
                category=entry.get("category", ""),
                tags=list(entry.get("tags") or []),
            ))
            if limit is not None and len(pairs) >= limit:
                return pairs
    return pairs


DATASETS: dict[str, Callable[[int | None], list[EvalPair]]] = {
    "korsts-dev": lambda lim: load_korsts(DATA_DIR / "KorSTS" / "sts-dev.tsv", lim),
    "korsts-test": lambda lim: load_korsts(DATA_DIR / "KorSTS" / "sts-test.tsv", lim),
    "kornli-dev": lambda lim: load_kornli(DATA_DIR / "KorNLI" / "xnli.dev.ko.tsv", lim),
    "kornli-test": lambda lim: load_kornli(DATA_DIR / "KorNLI" / "xnli.test.ko.tsv", lim),
    "curated": lambda lim: load_curated(DATA_DIR / "embedding_eval" / "curated_pairs.yaml", lim),
}


_DATASET_META = {
    "korsts-dev": {"label": "KorSTS dev (~1500쌍, score 0-5)", "kind": "regression"},
    "korsts-test": {"label": "KorSTS test (~1378쌍, score 0-5)", "kind": "regression"},
    "kornli-dev": {"label": "KorNLI dev (~2490쌍, ent/neu/con 균형)", "kind": "classification"},
    "kornli-test": {"label": "KorNLI test (~5010쌍, ent/neu/con 균형)", "kind": "classification"},
    "curated": {"label": "자체 큐레이션 (~60쌍, 사규/HR/재무/IT)", "kind": "buckets"},
}


def list_datasets() -> list[dict[str, Any]]:
    return [
        {"id": key, **meta, "available": (DATA_DIR / key).parent.exists()}
        for key, meta in _DATASET_META.items()
    ]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0.0 or dy == 0.0:
        return 0.0
    return num / (dx * dy)


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(enumerate(values), key=lambda kv: kv[1])
        result = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and order[j + 1][1] == order[i][1]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                result[order[k][0]] = avg
            i = j + 1
        return result

    return pearson(ranks(xs), ranks(ys))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


# ---------------------------------------------------------------------------
# Scoring backends
# ---------------------------------------------------------------------------


def _score_st_pairs(model_id: str, pairs: list[EvalPair]) -> list[float]:
    model = _load_st_model(model_id)
    text1s = [p.text1 for p in pairs]
    text2s = [p.text2 for p in pairs]
    vec1 = model.encode(text1s, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
    vec2 = model.encode(text2s, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
    return [_cosine(a.tolist(), b.tolist()) for a, b in zip(vec1, vec2)]


def _score_gemini_pairs(_model_id: str, pairs: list[EvalPair]) -> list[float]:
    embedder = _load_gemini_embedder()
    scores: list[float] = []
    for p in pairs:
        v1 = embedder.embed_query(p.text1)
        v2 = embedder.embed_query(p.text2)
        scores.append(_cosine(v1, v2))
    return scores


def _score_cross_pairs(_model_id: str, pairs: list[EvalPair]) -> list[float]:
    rr = _load_onnx_reranker()
    raw: list[float] = []
    for p in pairs:
        s = rr.score(p.text1, [p.text2])
        raw.append(float(s[0]) if s else 0.0)
    return [_sigmoid(s) for s in raw]


def _score_for_model(model_key: str, pairs: list[EvalPair]) -> list[float]:
    spec = EMBEDDING_REGISTRY[model_key]
    handler_name = spec["handler"].__name__
    if spec["kind"] == "cross":
        return _score_cross_pairs(spec["model_id"], pairs)
    if handler_name == "_embed_st_pair":
        return _score_st_pairs(spec["model_id"], pairs)
    if handler_name == "_embed_gemini_pair":
        return _score_gemini_pairs(spec["model_id"], pairs)
    raise ValueError(f"unsupported handler for batch eval: {handler_name}")


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


_BUCKET_EXPECTED = {
    "positive": 1.0,
    "negative": 0.0,
    "hard_negative": 0.2,
    "neutral": 0.5,
}


def _scatter_subsample(pairs: list[EvalPair], scores: list[float], n: int = 500) -> list[dict[str, Any]]:
    items = list(zip(pairs, scores))
    if len(items) > n:
        rng = random.Random(42)
        items = rng.sample(items, n)
    out = []
    for p, s in items:
        out.append({
            "label": p.label if isinstance(p.label, str) else round(float(p.label), 2),
            "score": round(s, 4),
            "bucket": p.bucket,
        })
    return out


def _top_errors(pairs: list[EvalPair], scores: list[float], n: int = 10) -> list[dict[str, Any]]:
    rows = []
    for p, s in zip(pairs, scores):
        if isinstance(p.label, (int, float)):
            err = abs(float(p.label) / 5.0 - s)
        else:
            err = abs(_BUCKET_EXPECTED.get(p.bucket, 0.5) - s)
        rows.append((err, p, s))
    rows.sort(key=lambda x: -x[0])
    return [
        {
            "text1": p.text1[:100],
            "text2": p.text2[:100],
            "label": p.label if isinstance(p.label, str) else round(float(p.label), 2),
            "bucket": p.bucket,
            "score": round(s, 4),
            "err": round(err, 4),
        }
        for err, p, s in rows[:n]
    ]


def _compute_metrics(
    pairs: list[EvalPair],
    scores: list[float],
    spec: dict[str, Any],
) -> dict[str, Any]:
    by_bucket: dict[str, list[float]] = {}
    for p, s in zip(pairs, scores):
        by_bucket.setdefault(p.bucket, []).append(s)

    bucket_means = {
        b: round(statistics.fmean(v), 4) for b, v in by_bucket.items() if v
    }
    bucket_stdev = {
        b: round(statistics.stdev(v), 4) if len(v) > 1 else 0.0 for b, v in by_bucket.items()
    }
    bucket_counts = {b: len(v) for b, v in by_bucket.items()}

    metrics: dict[str, Any] = {
        "label": spec["label"],
        "kind": spec["kind"],
        "bucket_means": bucket_means,
        "bucket_stdev": bucket_stdev,
        "bucket_counts": bucket_counts,
    }

    if "positive" in bucket_means and "negative" in bucket_means:
        metrics["separation"] = round(bucket_means["positive"] - bucket_means["negative"], 4)
    if "positive" in bucket_means and "hard_negative" in bucket_means:
        metrics["separation_hard"] = round(
            bucket_means["positive"] - bucket_means["hard_negative"], 4
        )

    numeric_labels = [
        float(p.label) for p in pairs if isinstance(p.label, (int, float))
    ]
    if len(numeric_labels) == len(pairs) and len(pairs) >= 2:
        metrics["pearson"] = round(pearson(numeric_labels, scores), 4)
        metrics["spearman"] = round(spearman(numeric_labels, scores), 4)

    metrics["top_errors"] = _top_errors(pairs, scores)
    metrics["scatter"] = _scatter_subsample(pairs, scores)

    return metrics


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def evaluate(
    dataset_id: str,
    model_keys: list[str],
    limit: int | None = None,
) -> dict[str, Any]:
    if dataset_id not in DATASETS:
        raise ValueError(
            f"unknown dataset: {dataset_id}. choose from {list(DATASETS)}"
        )

    pairs = DATASETS[dataset_id](limit)
    if not pairs:
        return {"dataset": dataset_id, "pair_count": 0, "results": {}}

    results: dict[str, Any] = {}
    for key in model_keys:
        if key not in EMBEDDING_REGISTRY:
            results[key] = {"error": f"unknown model: {key}"}
            continue
        spec = EMBEDDING_REGISTRY[key]
        try:
            scores = _score_for_model(key, pairs)
            results[key] = _compute_metrics(pairs, scores, spec)
        except Exception as exc:
            logger.warning("embedding eval failed (%s): %s", key, exc)
            results[key] = {"error": str(exc), "label": spec.get("label", key)}

    return {
        "dataset": dataset_id,
        "dataset_meta": _DATASET_META.get(dataset_id, {}),
        "pair_count": len(pairs),
        "results": results,
    }
