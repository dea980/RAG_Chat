"""Shared evaluation primitives for retrieval harnesses.

Provides question loading, metric computation, and report rendering
used by both ``run_chunk_ab.py`` (BM25) and ``run_embedding_ab.py`` (FAISS).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence


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
class RetrievalResult:
    """Single question evaluation result."""
    question_id: str
    recall: float          # fraction of expected keywords found
    mrr: float             # 1/rank of first hit (0 if no hit)
    top_k_texts: List[str] = field(default_factory=list)


@dataclass
class ModelResult:
    """Aggregate result for one model configuration."""
    model_name: str
    dimensions: int
    avg_recall: float
    avg_mrr: float
    latency_ms: float      # average query latency
    index_size_mb: float
    per_question: List[RetrievalResult] = field(default_factory=list)


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


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def keyword_recall(question: EvalQuestion, retrieved_text: str) -> float:
    """Fraction of expected keywords present in retrieved text."""
    if not question.expected_keywords:
        return 0.0
    hits = sum(
        1 for kw in question.expected_keywords
        if kw.lower() in retrieved_text.lower()
    )
    return hits / len(question.expected_keywords)


def mrr_score(question: EvalQuestion, ranked_texts: List[str]) -> float:
    """Mean Reciprocal Rank — 1/rank of first chunk containing ANY keyword."""
    for rank, text in enumerate(ranked_texts, 1):
        lower = text.lower()
        if any(kw.lower() in lower for kw in question.expected_keywords):
            return 1.0 / rank
    return 0.0


# ---------------------------------------------------------------------------
# Timer
# ---------------------------------------------------------------------------

class Timer:
    def __init__(self):
        self._times: List[float] = []

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self._times.append((time.perf_counter() - self._start) * 1000)

    @property
    def avg_ms(self) -> float:
        return sum(self._times) / len(self._times) if self._times else 0.0


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def render_html(results: List[ModelResult], k: int) -> str:
    """Generate a self-contained HTML comparison report."""
    rows = ""
    for r in sorted(results, key=lambda x: x.avg_recall, reverse=True):
        rows += f"""<tr>
            <td><strong>{r.model_name}</strong></td>
            <td class="metric">{r.dimensions}</td>
            <td class="metric">{r.avg_recall:.3f}</td>
            <td class="metric">{r.avg_mrr:.3f}</td>
            <td class="metric">{r.latency_ms:.1f}</td>
            <td class="metric">{r.index_size_mb:.2f}</td>
        </tr>"""

    # Per-question heatmap
    heatmap_header = "".join(f"<th>{r.model_name}</th>" for r in results)
    heatmap_rows = ""
    if results and results[0].per_question:
        for i, pq in enumerate(results[0].per_question):
            cells = ""
            for r in results:
                val = r.per_question[i].recall if i < len(r.per_question) else 0
                color = f"rgba(74,222,128,{val})" if val > 0 else "rgba(248,113,113,0.3)"
                cells += f'<td style="background:{color};text-align:center">{val:.2f}</td>'
            heatmap_rows += f"<tr><td>{pq.question_id}</td>{cells}</tr>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Embedding A/B Report — recall@{k}</title>
<style>
  :root {{ --bg:#0A0B0D; --surface:#141519; --border:#2a2b30; --text:#e0e0e0;
           --accent:#E89B3C; --mono:'Geist Mono','SF Mono',monospace; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--text); font:15px/1.6 'Pretendard',sans-serif;
          padding:2rem; max-width:960px; margin:0 auto; }}
  h1 {{ color:var(--accent); font-size:1.4rem; margin-bottom:.3rem; }}
  h2 {{ color:var(--accent); font-size:1.1rem; margin:1.5rem 0 .5rem;
        border-bottom:1px solid var(--border); padding-bottom:.2rem; }}
  .subtitle {{ color:#888; font-size:.85rem; margin-bottom:1.5rem; }}
  table {{ width:100%; border-collapse:collapse; margin:.8rem 0; font-size:.85rem; }}
  th,td {{ padding:.5rem .6rem; border:1px solid var(--border); }}
  th {{ background:var(--surface); color:var(--accent); font-weight:600; }}
  td {{ background:var(--bg); }}
  .metric {{ font-family:var(--mono); text-align:right; }}
  .verdict {{ background:var(--surface); border-left:4px solid var(--accent);
              padding:.8rem 1rem; margin:1rem 0; border-radius:0 6px 6px 0; }}
</style>
</head>
<body>
<h1>Embedding Model A/B — recall@{k}</h1>
<p class="subtitle">FAISS IndexFlatIP / keyword recall + MRR</p>

<h2>Summary</h2>
<table>
<tr><th>Model</th><th>Dim</th><th>Recall@{k}</th><th>MRR</th><th>Latency(ms)</th><th>Index(MB)</th></tr>
{rows}
</table>

<h2>Per-Question Recall Heatmap</h2>
<table>
<tr><th>Q</th>{heatmap_header}</tr>
{heatmap_rows}
</table>

<div class="verdict">
  상단 모델이 recall@{k} 기준 최고 성능. MRR과 latency를 함께 고려하여 결정.
</div>
</body>
</html>"""
