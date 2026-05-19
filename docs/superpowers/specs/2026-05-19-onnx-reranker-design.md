# ONNX Reranker Pipeline Module — Design

- Date: 2026-05-19
- Author: Daeyeop Kim
- Status: Approved

## Goal

Improve RAG retrieval precision by adding an ONNX-based cross-encoder reranker
between the existing `retrieve` and `reasoning` pipeline steps. The reranker
operates on a wider candidate pool (top-N=20) returned by vector search and
narrows it to top-K=3 documents that are passed downstream.

This is intentionally **not** an LLM agent — it is a deterministic pipeline
module that always reranks. The "Agent" framing was discussed and discarded
in favor of a simpler, testable module.

## Non-Goals

- LLM-based decision making (no ReAct, no tool calling)
- Conditional / gated reranking (always on, controllable only via env toggle)
- Replacing the embedding model (Gemini/OpenRouter remain as-is)
- Multi-stage rerank pipelines

## Architecture

```
[ retrieve k=20 ]  ->  [ rerank -> top-3 ]  ->  [ reasoning ]  ->  [ generation ]
   raw Documents          ONNX cross-encoder         (unchanged)         (unchanged)
```

The change is additive: existing modules are not removed, only `RetrieveModule`
is widened to surface raw `Document` objects, and a new `RerankModule` is
inserted before `ReasoningModule`.

## Components

### 1. `chat/rerankers/onnx_bge.py` (new)

Thin wrapper around `optimum.onnxruntime.ORTModelForSequenceClassification`
loading `BAAI/bge-reranker-v2-m3` (ONNX variant).

- `OnnxBgeReranker.score(query: str, passages: list[str]) -> list[float]`
- Loaded lazily on first call; model and tokenizer cached on the instance.
- CPU execution provider by default; `RERANKER_DEVICE` env can switch to CUDA.

### 2. `chat/providers/__init__.py` — `provider_manager.get_reranker()`

- Returns a process-wide singleton instance of the reranker (lazy init).
- Honors `RERANKER_ENABLED=0` by returning `None`; callers must handle.
- Mirrors the existing `get_reasoning_model` / `get_generation_model` pattern.

### 3. `chat/utils.py` — `RAGUtils.get_rag_context`

- Default `k` raised from 3 to `RERANKER_TOP_N` (default 20).
- Return shape extended:
  ```python
  {
    "context": str,         # merged top-N text (legacy)
    "image_paths": list,    # legacy
    "docs": list[Document], # NEW — raw docs for downstream rerank
  }
  ```
- Backward compatibility: callers reading only `context`/`image_paths` are
  unaffected.

### 4. `chat/pipeline/modules.py`

- `RetrieveModule.run()`: write raw docs to `context.extra["retrieved_docs"]`.
- **New** `RerankModule`:
  - Reads `context.extra["retrieved_docs"]`.
  - Calls `provider_manager.get_reranker()`. If `None`, no-op (passthrough).
  - Scores `(question, doc.page_content)` pairs.
  - Selects top-K (default 3 via `RERANKER_TOP_K`).
  - Rewrites `context.context_text` and `context.images` to reflect the new
    ordering.
  - On scoring failure, logs and falls back to the original ordering — never
    breaks the request.

### 5. `chat/pipeline/runner.py`

- `DEFAULT_REGISTRY["rerank"] = RerankModule`.
- Default pipeline becomes `["retrieve", "rerank", "reasoning", "generation"]`.

### 6. Configuration

| Env var | Default | Purpose |
|---|---|---|
| `RERANKER_ENABLED` | `1` | Master toggle. `0` disables module entirely. |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | HF model id (must have ONNX variant). |
| `RERANKER_TOP_N` | `20` | How many candidates `retrieve` fetches. |
| `RERANKER_TOP_K` | `3` | How many survivors `rerank` keeps. |
| `RERANKER_DEVICE` | `cpu` | `cpu` or `cuda`. |

### 7. Dependencies

Add to `requirements.txt`:

- `optimum[onnxruntime]>=1.20`
- `onnxruntime>=1.17`  (or `onnxruntime-gpu` if `RERANKER_DEVICE=cuda`)

The model itself is **not** vendored. It downloads on first run via
`huggingface_hub` and is cached at `~/.cache/huggingface/`. In Docker this
directory must be mounted to a persistent volume or pre-baked into the image.

## Data Flow

1. User question arrives at the pipeline.
2. `RetrieveModule` performs `vector_store.similarity_search(question, k=20)`.
3. Raw `Document` list is stashed in `ModuleContext.extra["retrieved_docs"]`.
4. `RerankModule` loads the singleton reranker, scores all 20 pairs, sorts
   descending, takes top 3.
5. `context.context_text` is rebuilt from top-3 (`\n\n` separated).
6. `context.images` filtered to images present in the surviving docs.
7. `ReasoningModule` and `GenerationModule` proceed unchanged.

## Error Handling

- **Reranker init failure** (model download, ONNX load): logged, singleton
  set to `None`, all subsequent requests bypass rerank.
- **Per-request scoring failure**: logged, original retrieve ordering preserved
  (effectively a no-op rerank).
- **No retrieved docs**: module is a passthrough.

The pipeline must never 500 because of a reranker problem.

## Testing

- `chat/tests/test_rerank.py`:
  - Unit test with a stub reranker returning controlled scores; assert order.
  - Test passthrough when `retrieved_docs` is empty.
  - Test passthrough when `get_reranker()` returns `None`.
  - Test failure fallback when `reranker.score` raises.
- Update existing pipeline integration test to include `rerank` step.

## Trade-offs

| Aspect | Impact |
|---|---|
| Latency | +50–200 ms (CPU, top-20 → top-3) |
| Memory | +~700 MB resident for the loaded model |
| Cold start | One-time ~30 s download on first run; cached after |
| Quality | Better precision on paraphrased / synonym-heavy queries, esp. Korean |

## Rollout

1. Land code with `RERANKER_ENABLED=1` as default.
2. Verify in staging that latency budget holds (~p95 +200ms acceptable).
3. If production latency regresses unacceptably, flip `RERANKER_ENABLED=0`
   via env without redeploy.

## Out of Scope (Future Work)

- Conditional / score-gap-aware reranking (skip rerank when top-1 dominates).
- LLM-as-judge rerank for the final top-K.
- A/B test harness comparing rerank-on vs rerank-off (the existing
  Mann-Whitney A/B infra could be reused later).
