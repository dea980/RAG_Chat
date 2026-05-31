"""Unit tests for chat.embedding_eval (loaders + metrics).

No actual model calls — those require ~2GB downloads and live API keys.
The eval harness has two surfaces: data loaders + pure math. Both are
covered here. Live-model regression is left for a separate manual run
via ``python manage.py embedding_eval --limit 50``.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from chat.embedding_eval import (
    DATASETS,
    DATA_DIR,
    EvalPair,
    _compute_metrics,
    _scatter_subsample,
    _top_errors,
    load_curated,
    load_kornli,
    load_korsts,
    pearson,
    spearman,
)


# ---------------------------------------------------------------------------
# Dataset loaders
# ---------------------------------------------------------------------------


def test_data_dir_resolves():
    assert DATA_DIR.exists(), f"data dir missing: {DATA_DIR}"


def test_load_korsts_dev_first_10():
    path = DATA_DIR / "KorSTS" / "sts-dev.tsv"
    if not path.exists():
        pytest.skip("KorSTS dev tsv missing")
    pairs = load_korsts(path, limit=10)
    assert len(pairs) == 10
    assert all(isinstance(p.label, float) for p in pairs)
    assert all(p.bucket in {"positive", "negative", "neutral"} for p in pairs)
    assert all(p.text1 and p.text2 for p in pairs)


def test_load_kornli_dev_first_10():
    path = DATA_DIR / "KorNLI" / "xnli.dev.ko.tsv"
    if not path.exists():
        pytest.skip("KorNLI dev tsv missing")
    pairs = load_kornli(path, limit=10)
    assert len(pairs) == 10
    valid = {"entailment", "contradiction", "neutral"}
    assert all(p.label in valid for p in pairs)
    bucket_set = {p.bucket for p in pairs}
    assert bucket_set <= {"positive", "hard_negative", "neutral"}


def test_load_curated():
    path = DATA_DIR / "embedding_eval" / "curated_pairs.yaml"
    if not path.exists():
        pytest.skip("curated yaml missing")
    pairs = load_curated(path)
    assert len(pairs) > 0
    buckets = {p.bucket for p in pairs}
    assert "positive" in buckets
    assert "negative" in buckets
    assert "hard_negative" in buckets


def test_dataset_registry_keys():
    expected = {"korsts-dev", "korsts-test", "kornli-dev", "kornli-test", "curated"}
    assert expected <= set(DATASETS.keys())


# ---------------------------------------------------------------------------
# Correlation metrics
# ---------------------------------------------------------------------------


def test_pearson_perfect_positive():
    assert math.isclose(pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]), 1.0, abs_tol=1e-9)


def test_pearson_perfect_negative():
    assert math.isclose(pearson([1.0, 2.0, 3.0], [3.0, 2.0, 1.0]), -1.0, abs_tol=1e-9)


def test_pearson_zero_for_constant():
    # constant y → undefined; harness returns 0.0
    assert pearson([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) == 0.0


def test_spearman_monotonic_nonlinear():
    # y is monotonic but not linear — Pearson < 1, Spearman == 1
    xs = [1.0, 2.0, 3.0, 4.0]
    ys = [1.0, 4.0, 9.0, 16.0]
    assert math.isclose(spearman(xs, ys), 1.0, abs_tol=1e-9)
    assert pearson(xs, ys) < 1.0


def test_spearman_handles_ties():
    # ties should be averaged
    val = spearman([1.0, 1.0, 2.0], [1.0, 1.0, 2.0])
    assert math.isclose(val, 1.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _spec(kind: str = "embedding") -> dict:
    return {"label": "test-model", "kind": kind}


def test_compute_metrics_korsts_like():
    pairs = [
        EvalPair("a", "b", label=5.0, bucket="positive"),
        EvalPair("c", "d", label=4.5, bucket="positive"),
        EvalPair("e", "f", label=0.0, bucket="negative"),
        EvalPair("g", "h", label=0.5, bucket="negative"),
    ]
    scores = [0.9, 0.85, 0.10, 0.15]
    m = _compute_metrics(pairs, scores, _spec())
    assert "pearson" in m
    assert m["pearson"] > 0.9
    assert "spearman" in m
    assert "separation" in m
    assert m["separation"] == round(((0.9 + 0.85) / 2) - ((0.10 + 0.15) / 2), 4)
    assert m["bucket_counts"]["positive"] == 2
    assert m["bucket_counts"]["negative"] == 2


def test_compute_metrics_kornli_like_no_pearson():
    pairs = [
        EvalPair("a", "b", label="entailment", bucket="positive"),
        EvalPair("c", "d", label="contradiction", bucket="hard_negative"),
        EvalPair("e", "f", label="neutral", bucket="neutral"),
    ]
    scores = [0.8, 0.2, 0.5]
    m = _compute_metrics(pairs, scores, _spec())
    assert "pearson" not in m   # labels are strings
    assert "spearman" not in m
    assert m["bucket_means"]["positive"] == 0.8
    assert m["bucket_means"]["hard_negative"] == 0.2
    assert "separation_hard" in m
    assert m["separation_hard"] == 0.6


def test_top_errors_returns_worst_first():
    pairs = [
        EvalPair("a", "b", label=5.0, bucket="positive"),    # expect ~1.0
        EvalPair("c", "d", label=0.0, bucket="negative"),    # expect ~0.0
    ]
    # both wildly wrong
    scores = [0.0, 1.0]
    errs = _top_errors(pairs, scores, n=2)
    assert len(errs) == 2
    assert errs[0]["err"] >= errs[1]["err"]


def test_scatter_subsamples_large_input():
    pairs = [EvalPair(f"a{i}", f"b{i}", label=float(i % 5), bucket="neutral") for i in range(2000)]
    scores = [0.5] * 2000
    out = _scatter_subsample(pairs, scores, n=500)
    assert len(out) == 500


def test_scatter_keeps_small_input_intact():
    pairs = [EvalPair("a", "b", label=1.0, bucket="positive")]
    scores = [0.7]
    out = _scatter_subsample(pairs, scores, n=500)
    assert len(out) == 1
    assert out[0]["score"] == 0.7
