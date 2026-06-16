"""ONNX-backed BGE cross-encoder reranker."""
from __future__ import annotations

import logging
from typing import List

import torch
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

logger = logging.getLogger(__name__)


class OnnxBgeReranker:
    """Score (query, passage) pairs with a BGE cross-encoder via ONNX Runtime."""

    def __init__(self, model_id: str, device: str = "cpu", max_length: int = 512) -> None:
        self.model_id = model_id
        self.device = device
        self.max_length = max_length
        logger.info("Loading reranker %s on %s", model_id, device)
        self._model = ORTModelForSequenceClassification.from_pretrained(
            model_id, file_name="onnx/model.onnx"
        )
        self._tokenizer = AutoTokenizer.from_pretrained(model_id)

    def score(self, query: str, passages: List[str]) -> List[float]:
        if not passages:
            return []
        pairs = [(query, p) for p in passages]
        inputs = self._tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        ).to(self.device)
        with torch.no_grad():
            logits = self._model(**inputs).logits
        return [float(x) for x in logits.view(-1).cpu().tolist()]
