"""Unit tests for OnnxBgeReranker — model is mocked to avoid HF download.

The reranker is opt-in (`feature/onnx-reranker` branch) and torch/optimum/
transformers are heavy deps not installed in the default dev venv. Skip the
whole module cleanly when any of them is missing so `manage.py test` doesn't
treat it as an ERROR. (pytest.importorskip raises pytest's own Skipped,
which the Django/unittest loader does not recognise.)
"""
import importlib
import unittest
from unittest.mock import MagicMock, patch

for _mod in ("torch", "optimum.onnxruntime", "transformers"):
    try:
        importlib.import_module(_mod)
    except ImportError:
        raise unittest.SkipTest(f"{_mod} not installed — onnx reranker tests skipped")

import pytest  # noqa: E402  — re-imported so fixture-based tests can still run via pytest


@pytest.fixture
def mock_ort_model():
    """Patch ORTModelForSequenceClassification and AutoTokenizer."""
    with patch("chat.rerankers.onnx_bge.ORTModelForSequenceClassification") as m_model, \
         patch("chat.rerankers.onnx_bge.AutoTokenizer") as m_tok:
        m_model.from_pretrained.return_value = MagicMock()
        m_tok.from_pretrained.return_value = MagicMock()
        yield m_model, m_tok


def test_score_returns_one_float_per_passage(mock_ort_model):
    """score() must return one float per input passage in input order."""
    from chat.rerankers.onnx_bge import OnnxBgeReranker
    import torch

    reranker = OnnxBgeReranker(model_id="dummy")
    # Mock tokenizer call returns a dict-like with .to() chainable
    tok_out = MagicMock()
    tok_out.to.return_value = tok_out
    reranker._tokenizer.return_value = tok_out  # type: ignore[attr-defined]
    # Mock model call returns object with .logits tensor of shape (n, 1)
    model_out = MagicMock()
    model_out.logits = torch.tensor([[0.9], [0.1], [0.5]])
    reranker._model.return_value = model_out  # type: ignore[attr-defined]

    scores = reranker.score("질문", ["passage A", "passage B", "passage C"])

    assert len(scores) == 3
    assert all(isinstance(s, float) for s in scores)
    assert scores == pytest.approx([0.9, 0.1, 0.5])


def test_score_with_empty_passages_returns_empty_list(mock_ort_model):
    """score() with no passages must return [] without calling the model."""
    from chat.rerankers.onnx_bge import OnnxBgeReranker

    reranker = OnnxBgeReranker(model_id="dummy")
    assert reranker.score("질문", []) == []
    reranker._model.assert_not_called()  # type: ignore[attr-defined]
