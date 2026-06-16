"""Retrieval Lab — 임베딩 모델별 검색 품질 비교 (FAISS in-memory).

모델 선택 → 동일 문서 임베딩 → 평가 질문으로 recall@k / MRR 측정.
backend API 불필요 — FAISS가 Streamlit 프로세스에서 직접 실행.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List

import faiss
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import CSVLoader

st.set_page_config(page_title="Retrieval Lab", layout="wide")

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from role_gate import require_manager  # noqa: E402
require_manager()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
DEFAULT_CSV = BACKEND_DIR / "galaxy_s25_data.csv"
DEFAULT_DATASET = BACKEND_DIR / "chat" / "tests" / "evals" / "dataset.jsonl"

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------
MODEL_REGISTRY = {
    "minilm": {
        "label": "MiniLM-v2 (384d)",
        "hf_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "dimensions": 384,
    },
    "bge-m3": {
        "label": "BGE-M3 (1024d)",
        "hf_name": "BAAI/bge-m3",
        "dimensions": 1024,
    },
    "e5-large": {
        "label": "E5-Large (1024d)",
        "hf_name": "intfloat/multilingual-e5-large",
        "dimensions": 1024,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
}


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
@st.cache_resource
def load_model(model_key: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_REGISTRY[model_key]["hf_name"])


def embed_texts(model_key: str, texts: List[str]) -> np.ndarray:
    model = load_model(model_key)
    cfg = MODEL_REGISTRY[model_key]
    prefix = cfg.get("passage_prefix", "")
    if prefix:
        texts = [prefix + t for t in texts]
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)


def embed_query(model_key: str, query: str) -> np.ndarray:
    model = load_model(model_key)
    cfg = MODEL_REGISTRY[model_key]
    prefix = cfg.get("query_prefix", "")
    vec = model.encode([prefix + query], normalize_embeddings=True, show_progress_bar=False)
    return vec.astype(np.float32)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_and_chunk(csv_path: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    docs = CSVLoader(file_path=csv_path, encoding="utf-8").load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
    )
    splits = splitter.split_documents(docs)
    return [s.page_content for s in splits]


def load_questions(path: Path) -> List[dict]:
    qs = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            qs.append(json.loads(line))
    return qs


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def evaluate(
    model_key: str,
    chunk_texts: List[str],
    questions: List[dict],
    k: int,
) -> dict:
    t0 = time.perf_counter()
    doc_embs = embed_texts(model_key, chunk_texts)
    embed_time = time.perf_counter() - t0

    index = faiss.IndexFlatIP(doc_embs.shape[1])
    index.add(doc_embs)

    per_q = []
    query_times = []

    for q in questions:
        t1 = time.perf_counter()
        q_vec = embed_query(model_key, q["question"])
        scores, indices = index.search(q_vec, k)
        query_times.append((time.perf_counter() - t1) * 1000)

        top_texts = [chunk_texts[i] for i in indices[0] if i >= 0]
        joined = " ".join(top_texts)

        kws = q["expected_keywords"]
        hits = sum(1 for kw in kws if kw.lower() in joined.lower())
        recall = hits / len(kws) if kws else 0

        # MRR
        mrr = 0.0
        for rank, text in enumerate(top_texts, 1):
            if any(kw.lower() in text.lower() for kw in kws):
                mrr = 1.0 / rank
                break

        per_q.append({
            "id": q["id"],
            "question": q["question"][:40],
            "scenario": q.get("scenario", ""),
            "recall": round(recall, 3),
            "mrr": round(mrr, 3),
            "hits": hits,
            "total_kw": len(kws),
        })

    avg_recall = sum(r["recall"] for r in per_q) / len(per_q) if per_q else 0
    avg_mrr = sum(r["mrr"] for r in per_q) / len(per_q) if per_q else 0

    return {
        "model": model_key,
        "label": MODEL_REGISTRY[model_key]["label"],
        "dimensions": MODEL_REGISTRY[model_key]["dimensions"],
        "avg_recall": round(avg_recall, 4),
        "avg_mrr": round(avg_mrr, 4),
        "avg_query_ms": round(sum(query_times) / len(query_times), 1) if query_times else 0,
        "embed_time_s": round(embed_time, 2),
        "index_size_kb": round(index.ntotal * doc_embs.shape[1] * 4 / 1024, 1),
        "per_question": per_q,
    }


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🔬 Retrieval Lab")
st.caption("FAISS in-memory — 임베딩 모델별 검색 품질 비교")

with st.sidebar:
    st.subheader("설정")

    chunk_size = st.slider("Chunk size", 200, 2000, 1000, 100)
    chunk_overlap = st.slider("Chunk overlap", 0, 500, 200, 50)
    k = st.slider("Top-k", 1, 10, 3)

    st.divider()
    st.subheader("모델 선택")
    selected_models = []
    for key, cfg in MODEL_REGISTRY.items():
        if st.checkbox(cfg["label"], value=(key == "minilm")):
            selected_models.append(key)

    st.divider()
    st.subheader("데이터 소스")
    uploaded_csv = st.file_uploader(
        "CSV 업로드 (선택)",
        type=["csv"],
        help="미업로드 시 backend/galaxy_s25_data.csv 사용.",
    )

    csv_path = ""
    if uploaded_csv is not None:
        import tempfile
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".csv", mode="wb",
        ) as tmp:
            tmp.write(uploaded_csv.getvalue())
            csv_path = tmp.name
        st.caption(f"업로드: {uploaded_csv.name} ({len(uploaded_csv.getvalue())} bytes)")
    elif DEFAULT_CSV.exists():
        csv_path = str(DEFAULT_CSV)
        st.caption(f"기본: {DEFAULT_CSV.name}")
    else:
        st.warning(f"기본 CSV 없음: {DEFAULT_CSV}")

    dataset_path = DEFAULT_DATASET

    run = st.button("평가 실행", type="primary", use_container_width=True)

    st.divider()
    st.caption(
        "sentence-transformers 모델은 **첫 실행 시 다운로드** (~2GB). "
        "이후 캐시."
    )

if not run:
    st.info("좌측에서 모델 선택 후 **평가 실행**을 누르세요.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 이 페이지가 하는 것")
        st.markdown(
            "- 같은 문서를 **여러 임베딩 모델**로 인코딩\n"
            "- **FAISS**로 in-memory 인덱스 생성\n"
            "- 평가 질문셋으로 **recall@k** / **MRR** 측정\n"
            "- 모델 간 성능 비교 차트 + per-question 히트맵"
        )
    with col2:
        st.markdown("### 왜 FAISS인가")
        st.markdown(
            "- **인터랙티브 실험**: 설정 바꾸고 즉시 결과 확인\n"
            "- pgvector는 re-index에 수분 → FAISS는 수초\n"
            "- 프로덕션은 **pgvector**, 실험은 **FAISS**\n"
            "- 결론 나면 pgvector에 반영"
        )
    st.stop()

if not selected_models:
    st.warning("모델을 1개 이상 선택하세요.")
    st.stop()

if not csv_path or not Path(csv_path).exists():
    st.error(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
    st.stop()

# Load data
chunk_texts = load_and_chunk(csv_path, chunk_size, chunk_overlap)
questions = load_questions(dataset_path) if dataset_path.exists() else []

if not questions:
    st.error("평가 질문셋을 찾을 수 없습니다.")
    st.stop()

st.write(f"**{len(chunk_texts)}** chunks (size={chunk_size}, overlap={chunk_overlap}) × **{len(questions)}** questions × **{len(selected_models)}** models")

# Run evaluation
results = []
progress = st.progress(0, text="평가 중...")
for i, mk in enumerate(selected_models):
    progress.progress((i) / len(selected_models), text=f"{MODEL_REGISTRY[mk]['label']} 임베딩 중...")
    results.append(evaluate(mk, chunk_texts, questions, k))
progress.progress(1.0, text="완료!")

# --- Summary table ---
st.subheader(f"모델별 비교 (recall@{k})")

summary_df = pd.DataFrame([{
    "Model": r["label"],
    "Dim": r["dimensions"],
    f"Recall@{k}": r["avg_recall"],
    "MRR": r["avg_mrr"],
    "Query(ms)": r["avg_query_ms"],
    "Index(KB)": r["index_size_kb"],
} for r in results]).sort_values(f"Recall@{k}", ascending=False)

st.dataframe(summary_df, use_container_width=True, hide_index=True)

# --- Bar chart ---
fig = go.Figure()
for r in results:
    fig.add_trace(go.Bar(
        name=r["label"],
        x=[f"Recall@{k}", "MRR"],
        y=[r["avg_recall"], r["avg_mrr"]],
    ))
fig.update_layout(
    barmode="group",
    height=300,
    margin=dict(t=30, b=30),
    paper_bgcolor="#0A0B0D",
    plot_bgcolor="#141519",
    font=dict(color="#e0e0e0"),
)
st.plotly_chart(fig, use_container_width=True)

# --- Per-question heatmap ---
st.subheader("Per-Question Recall Heatmap")

heatmap_data = {}
q_ids = [q["id"] for q in results[0]["per_question"]]
for r in results:
    heatmap_data[r["label"]] = [pq["recall"] for pq in r["per_question"]]

heatmap_df = pd.DataFrame(heatmap_data, index=q_ids)

fig2 = go.Figure(data=go.Heatmap(
    z=heatmap_df.values,
    x=heatmap_df.columns.tolist(),
    y=heatmap_df.index.tolist(),
    colorscale=[
        [0.0, "#450a0a"],
        [0.5, "#422006"],
        [1.0, "#064e3b"],
    ],
    text=np.round(heatmap_df.values, 2),
    texttemplate="%{text}",
    textfont=dict(size=12),
    hoverongaps=False,
))
fig2.update_layout(
    height=max(300, len(q_ids) * 35),
    margin=dict(t=20, b=20),
    paper_bgcolor="#0A0B0D",
    plot_bgcolor="#141519",
    font=dict(color="#e0e0e0"),
    yaxis=dict(autorange="reversed"),
)
st.plotly_chart(fig2, use_container_width=True)

# --- Per-question detail ---
with st.expander("질문별 상세"):
    for r in results:
        st.markdown(f"**{r['label']}** — recall@{k}={r['avg_recall']:.3f}")
        detail_df = pd.DataFrame(r["per_question"])
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

# --- Winner ---
best = max(results, key=lambda r: r["avg_recall"])
st.success(
    f"**추천: {best['label']}** — recall@{k}={best['avg_recall']:.3f}, "
    f"MRR={best['avg_mrr']:.3f}, {best['avg_query_ms']}ms/query, "
    f"{best['dimensions']}d, 무료 로컬 실행"
)
