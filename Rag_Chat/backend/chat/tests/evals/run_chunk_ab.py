"""Chunk size × overlap A/B harness for the RAG retrieval pipeline.

Why this exists
---------------
The chatbot's accuracy depends heavily on whether the retriever returns chunks
that contain the full spec a sales person is asking about. ``chunk_size`` and
``chunk_overlap`` are the two knobs that control how the source CSV is sliced
before embedding. This script sweeps a grid and reports recall@k, so we can
justify the values currently hard-coded in ``build_vector_store.py`` instead
of picking them by feel.

Backend choice
--------------
BM25 (rank-bm25) is used as the retriever so the harness runs offline without
a Gemini API key — useful for CI and quick local iteration. The chunking
strategy itself (the thing under test) is identical to production
(``RecursiveCharacterTextSplitter``), so conclusions about chunk_size/overlap
transfer to the embedding-backed retriever; only the absolute scores shift.

Usage
-----
::

    cd backend
    python -m chat.tests.evals.run_chunk_ab \
        --csv galaxy_s25_data.csv \
        --dataset chat/tests/evals/dataset.jsonl \
        --sizes 200,400,800,1200 \
        --overlaps 0,80,160 \
        --k 5
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Sequence

from rank_bm25 import BM25Okapi
from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class EvalQuestion:
    id: str
    question: str
    expected_keywords: List[str]
    scenario: str = ""


@dataclass
class GridResult:
    chunk_size: int
    chunk_overlap: int
    num_chunks: int
    avg_recall_at_k: float
    per_question_recall: List[float]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_questions(path: Path) -> List[EvalQuestion]:
    qs: List[EvalQuestion] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            qs.append(EvalQuestion(
                id=data["id"],
                question=data["question"],
                expected_keywords=data["expected_keywords"],
                scenario=data.get("scenario", ""),
            ))
    return qs


def load_csv_documents(csv_path: Path):
    loader = CSVLoader(file_path=str(csv_path), encoding="utf-8")
    return loader.load()


# ---------------------------------------------------------------------------
# Tokenization (cheap, language-agnostic enough for this dataset)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")


def tokenize(text: str) -> List[str]:
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def recall_for_question(question: EvalQuestion, retrieved_text: str) -> float:
    """Fraction of expected keywords present in the concatenated retrieved chunks."""
    hits = sum(1 for kw in question.expected_keywords if kw.lower() in retrieved_text.lower())
    return hits / len(question.expected_keywords) if question.expected_keywords else 0.0


def evaluate_grid_point(
    docs,
    questions: Sequence[EvalQuestion],
    chunk_size: int,
    chunk_overlap: int,
    k: int,
) -> GridResult:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    splits = splitter.split_documents(docs)
    corpus = [tokenize(c.page_content) for c in splits]
    bm25 = BM25Okapi(corpus)

    per_q: List[float] = []
    for q in questions:
        scores = bm25.get_scores(tokenize(q.question))
        # top-k chunk indices
        top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        joined = "\n".join(splits[i].page_content for i in top_idx)
        per_q.append(recall_for_question(q, joined))

    return GridResult(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        num_chunks=len(splits),
        avg_recall_at_k=round(sum(per_q) / len(per_q), 4) if per_q else 0.0,
        per_question_recall=[round(r, 3) for r in per_q],
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def render_markdown(results: List[GridResult], k: int) -> str:
    sizes = sorted({r.chunk_size for r in results})
    overlaps = sorted({r.chunk_overlap for r in results})
    lookup = {(r.chunk_size, r.chunk_overlap): r for r in results}

    lines = [
        f"### Recall@{k} grid (rows = chunk_size, cols = chunk_overlap)",
        "",
        "| chunk_size \\ overlap | " + " | ".join(str(o) for o in overlaps) + " |",
        "|---" * (len(overlaps) + 1) + "|",
    ]
    for size in sizes:
        cells = []
        for ov in overlaps:
            r = lookup.get((size, ov))
            cells.append(f"{r.avg_recall_at_k:.3f} (n={r.num_chunks})" if r else "—")
        lines.append(f"| **{size}** | " + " | ".join(cells) + " |")

    best = max(results, key=lambda r: r.avg_recall_at_k)
    lines.append("")
    lines.append(
        f"**Best:** chunk_size={best.chunk_size}, overlap={best.chunk_overlap} "
        f"→ recall@{k}={best.avg_recall_at_k:.3f} ({best.num_chunks} chunks)"
    )
    return "\n".join(lines)


def parse_int_list(raw: str) -> List[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chunk size/overlap A/B harness")
    parser.add_argument("--csv", default="galaxy_s25_data.csv",
                        help="Path to the source CSV (relative to backend/)")
    parser.add_argument("--dataset", default="chat/tests/evals/dataset.jsonl",
                        help="Path to JSONL of eval questions")
    parser.add_argument("--sizes", default="200,500,1000,1500",
                        help="Comma-separated chunk sizes to sweep")
    parser.add_argument("--overlaps", default="0,100,200,300",
                        help="Comma-separated chunk overlaps to sweep")
    parser.add_argument("--k", type=int, default=5, help="top-k for recall@k")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--markdown", help="Optional markdown report path")
    args = parser.parse_args(list(argv) if argv is not None else None)

    base = Path(__file__).resolve().parents[3]  # backend/
    csv_path = (base / args.csv).resolve()
    dataset_path = (base / args.dataset).resolve()

    if not csv_path.exists():
        parser.error(f"CSV not found: {csv_path}")
    if not dataset_path.exists():
        parser.error(f"Dataset not found: {dataset_path}")

    docs = load_csv_documents(csv_path)
    questions = load_questions(dataset_path)

    sizes = parse_int_list(args.sizes)
    overlaps = parse_int_list(args.overlaps)

    results: List[GridResult] = []
    for size in sizes:
        for ov in overlaps:
            if ov >= size:
                # Skip nonsense combinations (overlap must be < size for the splitter)
                continue
            results.append(evaluate_grid_point(docs, questions, size, ov, args.k))

    md = render_markdown(results, args.k)
    print(md)

    if args.output:
        Path(args.output).write_text(
            json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if args.markdown:
        Path(args.markdown).write_text(md + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
