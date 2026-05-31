"""Embedding model A/B test harness using FAISS.

Compares retrieval quality across multiple embedding models on the same
chunked documents and evaluation questions. Production uses pgvector +
Gemini; this harness lets you test alternatives offline before committing.

Usage
-----
::

    cd backend
    python -m chat.tests.evals.run_embedding_ab \\
        --csv galaxy_s25_data.csv \\
        --dataset chat/tests/evals/dataset.jsonl \\
        --models bge-m3,e5-large,minilm \\
        --k 3 \\
        --html results/embedding_ab.html

Add ``--models gemini`` to include the production model (requires GOOGLE_API_KEY).
Add ``--rerank`` to measure ONNX reranker effect on top of each model.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[4] / ".env")
except ImportError:
    pass

import faiss
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import CSVLoader

from .eval_core import (
    EvalQuestion,
    ModelResult,
    RetrievalResult,
    Timer,
    keyword_recall,
    load_questions,
    mrr_score,
    render_html,
)

# ---------------------------------------------------------------------------
# Embedding model registry
# ---------------------------------------------------------------------------

MODEL_REGISTRY: Dict[str, Dict] = {
    "bge-m3": {
        "hf_name": "BAAI/bge-m3",
        "dimensions": 1024,
        "type": "sentence-transformers",
    },
    "e5-large": {
        "hf_name": "intfloat/multilingual-e5-large",
        "dimensions": 1024,
        "type": "sentence-transformers",
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
    "minilm": {
        "hf_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dimensions": 384,
        "type": "sentence-transformers",
    },
    "gemini": {
        "dimensions": 3072,
        "type": "gemini",
    },
}


# ---------------------------------------------------------------------------
# Embedder abstraction
# ---------------------------------------------------------------------------

class Embedder:
    """Uniform interface for embedding text via different backends."""

    def __init__(self, model_key: str):
        self.key = model_key
        self.config = MODEL_REGISTRY[model_key]
        self.dimensions = self.config["dimensions"]
        self._model = None

    def _load(self):
        if self._model is not None:
            return

        if self.config["type"] == "sentence-transformers":
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.config["hf_name"])

        elif self.config["type"] == "gemini":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise RuntimeError("GOOGLE_API_KEY required for gemini embeddings")
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            self._model = GoogleGenerativeAIEmbeddings(
                model=os.getenv("GOOGLE_EMBEDDING_MODEL", "models/text-embedding-004"),
                google_api_key=api_key,
            )

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        self._load()

        if self.config["type"] == "sentence-transformers":
            prefix = self.config.get("passage_prefix", "")
            if prefix:
                texts = [prefix + t for t in texts]
            vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.array(vecs, dtype=np.float32)

        elif self.config["type"] == "gemini":
            vecs = self._model.embed_documents(texts)
            arr = np.array(vecs, dtype=np.float32)
            faiss.normalize_L2(arr)
            return arr

    def embed_query(self, text: str) -> np.ndarray:
        self._load()

        if self.config["type"] == "sentence-transformers":
            prefix = self.config.get("query_prefix", "")
            vec = self._model.encode([prefix + text], normalize_embeddings=True, show_progress_bar=False)
            return np.array(vec, dtype=np.float32)

        elif self.config["type"] == "gemini":
            vec = self._model.embed_query(text)
            arr = np.array([vec], dtype=np.float32)
            faiss.normalize_L2(arr)
            return arr


# ---------------------------------------------------------------------------
# FAISS index builder
# ---------------------------------------------------------------------------

def build_faiss_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """Build a flat inner-product index (cosine sim on L2-normalized vectors)."""
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_model(
    model_key: str,
    chunk_texts: List[str],
    questions: List[EvalQuestion],
    k: int,
    reranker=None,
) -> ModelResult:
    """Run full eval pipeline for one embedding model."""
    embedder = Embedder(model_key)
    print(f"  [{model_key}] Embedding {len(chunk_texts)} chunks ({embedder.dimensions}d)...")

    doc_embeddings = embedder.embed_documents(chunk_texts)
    index = build_faiss_index(doc_embeddings)

    index_bytes = index.ntotal * doc_embeddings.shape[1] * 4  # float32
    index_size_mb = index_bytes / (1024 * 1024)

    timer = Timer()
    per_question: List[RetrievalResult] = []

    # Fetch more if reranking
    search_k = k * 5 if reranker else k

    for q in questions:
        with timer:
            query_vec = embedder.embed_query(q.question)
            scores, indices = index.search(query_vec, search_k)

        top_indices = indices[0].tolist()
        top_texts = [chunk_texts[i] for i in top_indices if i >= 0]

        # Optional reranking
        if reranker and top_texts:
            try:
                rerank_scores = reranker.score(q.question, top_texts)
                ranked = sorted(zip(top_texts, rerank_scores), key=lambda x: x[1], reverse=True)
                top_texts = [t for t, _ in ranked[:k]]
            except Exception:
                top_texts = top_texts[:k]
        else:
            top_texts = top_texts[:k]

        joined = "\n".join(top_texts)
        recall = keyword_recall(q, joined)
        mrr = mrr_score(q, top_texts)

        per_question.append(RetrievalResult(
            question_id=q.id,
            recall=round(recall, 3),
            mrr=round(mrr, 3),
            top_k_texts=top_texts,
        ))

    avg_recall = sum(r.recall for r in per_question) / len(per_question) if per_question else 0
    avg_mrr = sum(r.mrr for r in per_question) / len(per_question) if per_question else 0

    suffix = " +rerank" if reranker else ""
    return ModelResult(
        model_name=f"{model_key}{suffix}",
        dimensions=embedder.dimensions,
        avg_recall=round(avg_recall, 4),
        avg_mrr=round(avg_mrr, 4),
        latency_ms=round(timer.avg_ms, 2),
        index_size_mb=round(index_size_mb, 3),
        per_question=per_question,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Embedding model A/B harness (FAISS)")
    parser.add_argument("--csv", default="galaxy_s25_data.csv")
    parser.add_argument("--dataset", default="chat/tests/evals/dataset.jsonl")
    parser.add_argument("--models", default="bge-m3,minilm",
                        help="Comma-separated model keys from registry")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--rerank", action="store_true",
                        help="Also test with ONNX reranker on top")
    parser.add_argument("--output", help="JSON output path")
    parser.add_argument("--html", help="HTML report path")
    args = parser.parse_args(list(argv) if argv is not None else None)

    base = Path(__file__).resolve().parents[3]  # backend/
    csv_path = (base / args.csv).resolve()
    dataset_path = (base / args.dataset).resolve()

    if not csv_path.exists():
        parser.error(f"CSV not found: {csv_path}")
    if not dataset_path.exists():
        parser.error(f"Dataset not found: {dataset_path}")

    # Load & chunk
    docs = CSVLoader(file_path=str(csv_path), encoding="utf-8").load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap,
    )
    splits = splitter.split_documents(docs)
    chunk_texts = [s.page_content for s in splits]
    print(f"Loaded {len(docs)} docs → {len(chunk_texts)} chunks "
          f"(size={args.chunk_size}, overlap={args.chunk_overlap})")

    questions = load_questions(dataset_path)
    print(f"Eval questions: {len(questions)}")

    model_keys = [m.strip() for m in args.models.split(",") if m.strip()]

    # Validate model keys
    for mk in model_keys:
        if mk not in MODEL_REGISTRY:
            available = ", ".join(MODEL_REGISTRY.keys())
            parser.error(f"Unknown model '{mk}'. Available: {available}")

    # Optional reranker
    reranker = None
    if args.rerank:
        try:
            # Add backend to path for provider import
            backend_dir = str(base)
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "triple_chat_pjt.settings")
            import django; django.setup()
            from chat.providers import provider_manager
            reranker = provider_manager.get_reranker()
            if reranker:
                print("Reranker: ONNX BGE-reranker-v2-m3 loaded")
            else:
                print("Reranker: not available (RERANKER_ENABLED not set)")
        except Exception as exc:
            print(f"Reranker load failed: {exc}")

    # Run evaluations
    all_results: List[ModelResult] = []
    for mk in model_keys:
        try:
            result = evaluate_model(mk, chunk_texts, questions, args.k)
            all_results.append(result)
            print(f"  → recall@{args.k}={result.avg_recall:.3f}  "
                  f"MRR={result.avg_mrr:.3f}  "
                  f"latency={result.latency_ms:.1f}ms")

            # With reranker if requested
            if reranker:
                result_rr = evaluate_model(mk, chunk_texts, questions, args.k, reranker=reranker)
                all_results.append(result_rr)
                print(f"  → +rerank recall@{args.k}={result_rr.avg_recall:.3f}  "
                      f"MRR={result_rr.avg_mrr:.3f}")

        except Exception as exc:
            print(f"  [{mk}] FAILED: {exc}")

    if not all_results:
        print("No results — nothing to report.")
        return 1

    # Reports
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps([asdict(r) for r in all_results], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"JSON → {out}")

    if args.html:
        out = Path(args.html)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(all_results, args.k), encoding="utf-8")
        print(f"HTML → {out}")

    # Console summary
    print(f"\n{'Model':<25} {'Recall@'+str(args.k):>10} {'MRR':>8} {'ms':>8} {'MB':>8}")
    print("-" * 63)
    for r in sorted(all_results, key=lambda x: x.avg_recall, reverse=True):
        print(f"{r.model_name:<25} {r.avg_recall:>10.3f} {r.avg_mrr:>8.3f} "
              f"{r.latency_ms:>8.1f} {r.index_size_mb:>8.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
