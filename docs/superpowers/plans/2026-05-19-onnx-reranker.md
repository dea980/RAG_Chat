# ONNX Reranker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic ONNX cross-encoder rerank step (bge-reranker-v2-m3) between `retrieve` and `reasoning` in the RAG pipeline so the top-K context passed to the LLM is precision-ranked rather than relying solely on dense-embedding similarity.

**Architecture:** A new `RerankModule` is inserted into the pipeline. `RetrieveModule` is widened to surface raw `Document` objects via `ModuleContext.extra["retrieved_docs"]`. A new singleton `OnnxBgeReranker` (lazy-loaded via `provider_manager.get_reranker()`) scores `(question, passage)` pairs with `optimum.onnxruntime`. Reranker failures degrade to passthrough — the pipeline never 500s because of rerank.

**Tech Stack:** Python 3.11+, Django, LangChain, `optimum[onnxruntime]`, `onnxruntime`, pytest.

**Spec:** [`docs/superpowers/specs/2026-05-19-onnx-reranker-design.md`](../specs/2026-05-19-onnx-reranker-design.md)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `Rag_Chat/backend/requirements.txt` | Modify | Add `optimum[onnxruntime]`, `onnxruntime` |
| `Rag_Chat/backend/chat/rerankers/__init__.py` | Create | Package marker, re-exports `OnnxBgeReranker` |
| `Rag_Chat/backend/chat/rerankers/onnx_bge.py` | Create | ONNX cross-encoder wrapper with `.score()` |
| `Rag_Chat/backend/chat/providers/manager.py` | Modify | Add `get_reranker()` singleton accessor |
| `Rag_Chat/backend/chat/utils.py` | Modify | `RAGUtils.get_rag_context` returns raw docs; default `k` from env |
| `Rag_Chat/backend/chat/pipeline/modules.py` | Modify | `RetrieveModule` stashes raw docs; **new** `RerankModule` |
| `Rag_Chat/backend/chat/pipeline/runner.py` | Modify | Register `rerank` in `DEFAULT_REGISTRY`; default sequence |
| `Rag_Chat/backend/chat/tests/test_rerank.py` | Create | Unit tests for `RerankModule` |
| `Rag_Chat/backend/chat/tests/test_onnx_bge.py` | Create | Unit tests for `OnnxBgeReranker` (mocked) |
| `Rag_Chat/.env.example` | Modify | Document `RERANKER_*` env vars |
| `README.md` | Modify | Brief note on the rerank step + cold-start download |

---

## Task 1: Add dependencies

**Files:**
- Modify: `Rag_Chat/backend/requirements.txt`

- [ ] **Step 1: Append reranker deps**

Open `Rag_Chat/backend/requirements.txt` and append at the bottom:

```text

# Reranker (ONNX cross-encoder)
optimum[onnxruntime]>=1.20.0
onnxruntime>=1.17.0
```

- [ ] **Step 2: Install locally to confirm resolution**

Run from repo root:
```bash
pip install -r Rag_Chat/backend/requirements.txt
```
Expected: install completes without conflict (existing `numpy<2.0` pin is compatible with onnxruntime).

- [ ] **Step 3: Commit**

```bash
git add Rag_Chat/backend/requirements.txt
git commit -m "chore: add optimum + onnxruntime for reranker"
```

---

## Task 2: `OnnxBgeReranker` — failing test first

**Files:**
- Create: `Rag_Chat/backend/chat/rerankers/__init__.py`
- Create: `Rag_Chat/backend/chat/tests/test_onnx_bge.py`

- [ ] **Step 1: Create empty package init**

Create `Rag_Chat/backend/chat/rerankers/__init__.py`:

```python
"""Reranker implementations for the RAG pipeline."""

from .onnx_bge import OnnxBgeReranker

__all__ = ["OnnxBgeReranker"]
```

- [ ] **Step 2: Write the failing test**

Create `Rag_Chat/backend/chat/tests/test_onnx_bge.py`:

```python
"""Unit tests for OnnxBgeReranker — model is mocked to avoid HF download."""
from unittest.mock import MagicMock, patch

import pytest


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
    assert scores == [0.9, 0.1, 0.5]


def test_score_with_empty_passages_returns_empty_list(mock_ort_model):
    """score() with no passages must return [] without calling the model."""
    from chat.rerankers.onnx_bge import OnnxBgeReranker

    reranker = OnnxBgeReranker(model_id="dummy")
    assert reranker.score("질문", []) == []
    reranker._model.assert_not_called()  # type: ignore[attr-defined]
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd Rag_Chat/backend && pytest chat/tests/test_onnx_bge.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'chat.rerankers.onnx_bge'`.

---

## Task 3: `OnnxBgeReranker` — minimal implementation

**Files:**
- Create: `Rag_Chat/backend/chat/rerankers/onnx_bge.py`

- [ ] **Step 1: Implement the reranker**

Create `Rag_Chat/backend/chat/rerankers/onnx_bge.py`:

```python
"""ONNX-backed BGE cross-encoder reranker."""
from __future__ import annotations

import logging
import os
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
        return logits.view(-1).cpu().tolist()
```

- [ ] **Step 2: Run the tests**

```bash
cd Rag_Chat/backend && pytest chat/tests/test_onnx_bge.py -v
```
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add Rag_Chat/backend/chat/rerankers/ Rag_Chat/backend/chat/tests/test_onnx_bge.py
git commit -m "feat: add OnnxBgeReranker (ONNX cross-encoder for RAG rerank)"
```

---

## Task 4: `provider_manager.get_reranker()` singleton

**Files:**
- Modify: `Rag_Chat/backend/chat/providers/manager.py`

- [ ] **Step 1: Add the accessor**

In `Rag_Chat/backend/chat/providers/manager.py`, in `__init__` add a new cache attribute and a new method. Insert after the existing `_chat_model_cache` line:

```python
        self._reranker = None
        self._reranker_init_attempted = False
```

Then add this method anywhere in the `ProviderManager` class (e.g. just before the embeddings section):

```python
    def get_reranker(self):
        """Return a singleton ONNX reranker, or None if disabled / unavailable.

        Honors:
        - RERANKER_ENABLED (default "1"): set to "0" to disable.
        - RERANKER_MODEL (default "BAAI/bge-reranker-v2-m3").
        - RERANKER_DEVICE (default "cpu").
        """
        if os.getenv("RERANKER_ENABLED", "1") != "1":
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
```

- [ ] **Step 2: Smoke-check the import path**

```bash
cd Rag_Chat/backend && python -c "from chat.providers import provider_manager; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add Rag_Chat/backend/chat/providers/manager.py
git commit -m "feat: provider_manager.get_reranker() singleton accessor"
```

---

## Task 5: Extend `RAGUtils.get_rag_context` to surface raw docs

**Files:**
- Modify: `Rag_Chat/backend/chat/utils.py:155-184`

- [ ] **Step 1: Update `process_search_results`**

Replace the existing `process_search_results` (around lines 155-168) with:

```python
    @staticmethod
    def process_search_results(search_results):
        """Process search results into legacy fields plus raw docs."""
        context = "\n".join([doc.page_content for doc in search_results])
        image_paths = [
            doc.metadata["image_path"]
            for doc in search_results
            if "image_path" in doc.metadata
        ]
        return {
            "context": context,
            "image_paths": image_paths,
            "docs": list(search_results),
        }
```

- [ ] **Step 2: Update `get_rag_context` default k**

Replace the existing `get_rag_context` signature (around line 171) with a wider default derived from env:

```python
    @staticmethod
    def get_rag_context(question: str, k: int | None = None) -> Dict[str, Any]:
        """Retrieve RAG context (top-k raw docs + merged text)."""
        if k is None:
            k = int(os.getenv("RERANKER_TOP_N", "20"))
        try:
            vector_store = RAGUtils.get_vector_store()
            search_results = vector_store.similarity_search(question, k=k)
            return RAGUtils.process_search_results(search_results)
        except Exception as e:
            logger.error(f"Error in get_rag_context: {str(e)}")
            return {"context": "", "image_paths": [], "docs": []}
```

- [ ] **Step 3: Run existing tests to confirm no regression**

```bash
cd Rag_Chat/backend && pytest chat/tests/ -v -x
```
Expected: existing tests continue to pass.

- [ ] **Step 4: Commit**

```bash
git add Rag_Chat/backend/chat/utils.py
git commit -m "feat: get_rag_context returns raw docs and reads top-N from env"
```

---

## Task 6: `RetrieveModule` exposes raw docs

**Files:**
- Modify: `Rag_Chat/backend/chat/pipeline/modules.py:16-40`

- [ ] **Step 1: Surface raw docs in context.extra**

Replace `RetrieveModule.run` body (lines 21-40) with:

```python
    def run(self, context: ModuleContext) -> ModuleContext:
        try:
            rag_context = RAGUtils.get_rag_context(context.question)
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ModuleError(f"Failed to retrieve context: {exc}") from exc

        context.context_text = rag_context.get("context", "")
        raw_images = rag_context.get("image_paths", [])
        images: List[str] = []
        for image in raw_images:
            if not image:
                continue
            if isinstance(image, str):
                images.extend([item.strip() for item in image.split("\n") if item.strip()])
            else:
                images.append(str(image))

        context.images = images
        context.extra["rag_metadata"] = rag_context
        context.extra["retrieved_docs"] = rag_context.get("docs", [])
        return context
```

- [ ] **Step 2: Smoke-check the change**

```bash
cd Rag_Chat/backend && python -c "from chat.pipeline.modules import RetrieveModule; print(RetrieveModule.name)"
```
Expected: `retrieve`.

- [ ] **Step 3: Commit**

```bash
git add Rag_Chat/backend/chat/pipeline/modules.py
git commit -m "feat: RetrieveModule surfaces raw docs in context.extra"
```

---

## Task 7: `RerankModule` — failing test first

**Files:**
- Create: `Rag_Chat/backend/chat/tests/test_rerank.py`

- [ ] **Step 1: Write the failing tests**

Create `Rag_Chat/backend/chat/tests/test_rerank.py`:

```python
"""Unit tests for RerankModule."""
from unittest.mock import MagicMock, patch

import pytest
from langchain.schema import Document

from chat.pipeline.base import ModuleContext


def _ctx(docs):
    c = ModuleContext(question="q", session_id="s", user_id="u")
    c.extra["retrieved_docs"] = docs
    c.context_text = "\n".join(d.page_content for d in docs)
    c.images = [d.metadata["image_path"] for d in docs if "image_path" in d.metadata]
    return c


def _docs():
    return [
        Document(page_content="A", metadata={"image_path": "a.png"}),
        Document(page_content="B", metadata={}),
        Document(page_content="C", metadata={"image_path": "c.png"}),
        Document(page_content="D", metadata={}),
    ]


@patch("chat.pipeline.modules.provider_manager")
def test_rerank_keeps_top_k_in_score_order(mock_pm):
    from chat.pipeline.modules import RerankModule

    reranker = MagicMock()
    reranker.score.return_value = [0.1, 0.9, 0.2, 0.8]  # B and D are top
    mock_pm.get_reranker.return_value = reranker

    module = RerankModule(top_k=2)
    out = module.run(_ctx(_docs()))

    assert out.context_text == "B\n\nD"
    assert out.images == []  # B and D have no image_path


@patch("chat.pipeline.modules.provider_manager")
def test_rerank_passthrough_when_reranker_is_none(mock_pm):
    from chat.pipeline.modules import RerankModule

    mock_pm.get_reranker.return_value = None
    module = RerankModule(top_k=2)
    ctx = _ctx(_docs())
    original_text = ctx.context_text

    out = module.run(ctx)

    assert out.context_text == original_text


@patch("chat.pipeline.modules.provider_manager")
def test_rerank_passthrough_when_no_retrieved_docs(mock_pm):
    from chat.pipeline.modules import RerankModule

    reranker = MagicMock()
    mock_pm.get_reranker.return_value = reranker
    module = RerankModule(top_k=2)

    ctx = ModuleContext(question="q", session_id="s", user_id="u")
    ctx.context_text = "preset"
    out = module.run(ctx)

    assert out.context_text == "preset"
    reranker.score.assert_not_called()


@patch("chat.pipeline.modules.provider_manager")
def test_rerank_falls_back_on_scoring_failure(mock_pm):
    from chat.pipeline.modules import RerankModule

    reranker = MagicMock()
    reranker.score.side_effect = RuntimeError("boom")
    mock_pm.get_reranker.return_value = reranker

    module = RerankModule(top_k=2)
    ctx = _ctx(_docs())
    original_text = ctx.context_text

    out = module.run(ctx)

    assert out.context_text == original_text
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd Rag_Chat/backend && pytest chat/tests/test_rerank.py -v
```
Expected: 4 FAILED with `ImportError: cannot import name 'RerankModule'`.

---

## Task 8: `RerankModule` — implementation

**Files:**
- Modify: `Rag_Chat/backend/chat/pipeline/modules.py`

- [ ] **Step 1: Add imports at top**

At the top of `Rag_Chat/backend/chat/pipeline/modules.py`, ensure these imports exist (add only what is missing):

```python
import logging
import os

from ..providers import provider_manager

logger = logging.getLogger(__name__)
```

- [ ] **Step 2: Append the RerankModule class**

Append at the bottom of the same file:

```python
class RerankModule(PipelineModule):
    """ONNX cross-encoder rerank of retrieved documents."""

    name = "rerank"

    def __init__(self, top_k: int | None = None) -> None:
        self.top_k = top_k if top_k is not None else int(os.getenv("RERANKER_TOP_K", "3"))

    def run(self, context: ModuleContext) -> ModuleContext:
        docs = context.extra.get("retrieved_docs") or []
        if not docs:
            return context

        reranker = provider_manager.get_reranker()
        if reranker is None:
            return context

        try:
            scores = reranker.score(context.question, [d.page_content for d in docs])
        except Exception as exc:
            logger.warning("Reranker scoring failed, keeping original order: %s", exc)
            return context

        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)[: self.top_k]
        top_docs = [d for d, _ in ranked]

        context.context_text = "\n\n".join(d.page_content for d in top_docs)
        context.images = [
            d.metadata["image_path"] for d in top_docs if "image_path" in d.metadata
        ]
        context.extra["retrieved_docs"] = top_docs
        return context
```

- [ ] **Step 3: Run the rerank tests**

```bash
cd Rag_Chat/backend && pytest chat/tests/test_rerank.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add Rag_Chat/backend/chat/pipeline/modules.py Rag_Chat/backend/chat/tests/test_rerank.py
git commit -m "feat: RerankModule (ONNX cross-encoder rerank step)"
```

---

## Task 9: Register `rerank` in the pipeline runner

**Files:**
- Modify: `Rag_Chat/backend/chat/pipeline/runner.py:8-18`

- [ ] **Step 1: Add to the registry**

Replace the existing import + `DEFAULT_REGISTRY` block (lines 8-18) with:

```python
from .base import ModuleContext, PipelineModule, ModuleError
from .modules import GenerationModule, ReasoningModule, RerankModule, RetrieveModule


ModuleConfig = Union[PipelineModule, Dict[str, object]]


DEFAULT_REGISTRY = {
    "retrieve": RetrieveModule,
    "rerank": RerankModule,
    "reasoning": ReasoningModule,
    "generation": GenerationModule,
}
```

- [ ] **Step 2: Find callers that build the default sequence**

```bash
grep -rn "retrieve.*reasoning.*generation\|PipelineRunner(" Rag_Chat/backend/chat/
```
For each call site that builds a pipeline from the default sequence, update the step list to `["retrieve", "rerank", "reasoning", "generation"]`. If callers pass explicit step lists, leave them alone.

- [ ] **Step 3: Run the full chat test suite**

```bash
cd Rag_Chat/backend && pytest chat/tests/ -v
```
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add Rag_Chat/backend/chat/pipeline/runner.py
git commit -m "feat: register rerank step in pipeline runner default sequence"
```

---

## Task 10: Env documentation + README note

**Files:**
- Modify: `Rag_Chat/.env.example` (create if missing)
- Modify: `README.md`

- [ ] **Step 1: Document env vars**

Find or create `Rag_Chat/.env.example` and append:

```dotenv
# --- Reranker (ONNX cross-encoder) ---
RERANKER_ENABLED=1
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_N=20
RERANKER_TOP_K=3
RERANKER_DEVICE=cpu
```

- [ ] **Step 2: Add README section**

In `README.md`, add a short section after the existing pipeline description:

```markdown
### Reranker

After dense vector retrieval, an ONNX cross-encoder (`BAAI/bge-reranker-v2-m3`)
rescore the top-N candidates and selects the top-K for the LLM. The model
downloads on first run to `~/.cache/huggingface/` (~568 MB). To disable,
set `RERANKER_ENABLED=0`.
```

- [ ] **Step 3: Commit**

```bash
git add Rag_Chat/.env.example README.md
git commit -m "docs: document RERANKER_* env vars and rerank step"
```

---

## Task 11: End-to-end smoke test (manual)

**Files:** none (manual)

- [ ] **Step 1: Start the stack**

```bash
docker compose -f Rag_Chat/docker-compose.yml up -d
```
Expected: services come up; first request triggers ~30 s reranker download (visible in logs).

- [ ] **Step 2: Issue a sample query**

Submit a Korean Galaxy-S25 question through the frontend (e.g., "갤럭시 S25 울트라 카메라 스펙 알려줘"). In the backend logs, confirm a line like `Loading reranker BAAI/bge-reranker-v2-m3 on cpu` appears once.

- [ ] **Step 3: Toggle off and re-verify**

Set `RERANKER_ENABLED=0`, restart the backend, re-issue the same question. Confirm no reranker log line; response still succeeds.

- [ ] **Step 4: Final commit (only if anything was tweaked)**

If smoke testing surfaced fixes, commit them with a focused message. Otherwise skip.

---

## Done When

- All 4 unit tests in `test_rerank.py` pass.
- Both unit tests in `test_onnx_bge.py` pass.
- Existing `chat/tests/` suite still passes.
- A live Korean query through the running app shows the reranker initialising on first call and responding correctly with `RERANKER_ENABLED=1`.
- `RERANKER_ENABLED=0` falls back to vector-search-only behavior without errors.
