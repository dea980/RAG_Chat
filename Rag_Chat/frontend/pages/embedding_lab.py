"""Embedding Lab — Mode A (Pair Compare).

두 텍스트의 모델별 유사도를 한 줄로 비교. design.md §2 의 모드 A.
저장·임베딩 부작용 없음 (in-memory only). 첫 호출 시 sentence-transformers
모델 ~2GB 다운로드가 발생할 수 있다 — spinner 로 안내.

backend: POST /api/v1/triple/embeddings/compare
        GET  /api/v1/triple/embeddings/compare   (registered model 목록)
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Embedding Lab", layout="wide")

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"
COMPARE_URL = f"{API_BASE}/embeddings/compare/"

# 의미 쌍 sample — design.md §6 의 SEMANTIC_PAIRS 일부.
SEMANTIC_PAIRS: dict[str, tuple[str, str]] = {
    "유사1: 연차 휴가 vs 연차 사용": ("연차 휴가", "연차 사용"),
    "유사2: 가격 ko vs en": ("가격이 얼마인가요", "What is the price"),
    "반대1: 사과 먹다 vs 받다": ("사과를 먹다", "사과를 받다"),
    "반대2: 월급 인상 vs 임금 삭감": ("월급 인상", "임금 삭감"),
    "도메인: 3분기 매출 vs Q3 revenue": ("3분기 매출", "Q3 revenue"),
}


@st.cache_data(ttl=600)
def fetch_registered_models() -> list[dict[str, Any]]:
    try:
        resp = requests.get(COMPARE_URL, timeout=10)
        resp.raise_for_status()
        return resp.json().get("models", [])
    except Exception:
        # backend 미기동이어도 페이지가 죽지 않게 하드코딩 fallback.
        return [
            {"id": "gemini", "label": "Gemini text-embedding-004", "kind": "embedding"},
            {"id": "bge-m3", "label": "BAAI/bge-m3", "kind": "embedding"},
            {"id": "e5-large", "label": "intfloat/multilingual-e5-large", "kind": "embedding"},
            {"id": "reranker-bge", "label": "ONNX bge-reranker-v2-m3", "kind": "cross"},
        ]


def call_compare(text1: str, text2: str, models: list[str]) -> dict[str, Any]:
    resp = requests.post(
        COMPARE_URL,
        json={"text1": text1, "text2": text2, "models": models},
        headers={"Content-Type": "application/json"},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


st.title("🧬 Embedding Lab — Pair Compare")
st.caption(
    "두 텍스트 의 모델별 유사도 한 줄 비교. 강사 7강의 "
    "\"임베딩 모델 바꿔서 39조 찾음\" 시나리오 재현용."
)

registered = fetch_registered_models()
model_ids = [m["id"] for m in registered]
labels_by_id = {m["id"]: m["label"] for m in registered}

with st.sidebar:
    st.subheader("입력")
    sample_key = st.selectbox(
        "샘플 쌍",
        ["(직접 입력)"] + list(SEMANTIC_PAIRS.keys()),
    )
    if sample_key != "(직접 입력)":
        default1, default2 = SEMANTIC_PAIRS[sample_key]
    else:
        default1, default2 = "", ""

    text1 = st.text_area("text1", value=default1, height=100)
    text2 = st.text_area("text2", value=default2, height=100)

    st.divider()
    st.subheader("모델 선택")
    default_selected = [m for m in ["gemini", "bge-m3", "e5-large"] if m in model_ids]
    selected = st.multiselect(
        "비교할 모델",
        options=model_ids,
        default=default_selected,
        format_func=lambda mid: labels_by_id.get(mid, mid),
    )

    st.divider()
    run = st.button("유사도 비교", type="primary", use_container_width=True)

    st.divider()
    st.caption(
        "⚠ sentence-transformers 모델(bge-m3, e5-large)은 **첫 호출 시 ~2GB 다운로드**. "
        "이후는 캐시. 사내 폐쇄망은 `SENTENCE_TRANSFORMERS_HOME` 으로 미리 받은 캐시 경로 지정."
    )

if run:
    if not text1.strip() or not text2.strip():
        st.warning("text1, text2 둘 다 필요합니다.")
        st.stop()
    if not selected:
        st.warning("모델을 한 개 이상 선택하세요.")
        st.stop()

    with st.spinner(f"{len(selected)}개 모델 임베딩 + 유사도 계산 중..."):
        try:
            payload = call_compare(text1.strip(), text2.strip(), selected)
        except requests.HTTPError as exc:
            st.error(f"backend {exc.response.status_code}: {exc.response.text[:300]}")
            st.stop()
        except requests.RequestException as exc:
            st.error(f"요청 실패: {exc}")
            st.stop()

    results: dict[str, Any] = payload.get("results", {})
    if not results:
        st.warning("결과 없음.")
        st.stop()

    rows = []
    for mid, r in results.items():
        row = {
            "model": labels_by_id.get(mid, mid),
            "kind": r.get("kind", "?"),
            "score": r.get("score"),
            "dim": r.get("dim"),
            "error": r.get("error", ""),
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    st.subheader("모델별 유사도")
    st.dataframe(df, use_container_width=True, hide_index=True)

    embed_rows = df[df["kind"] == "cosine"].dropna(subset=["score"])
    if not embed_rows.empty:
        st.subheader("cosine 유사도 비교 (embedding 모델만)")
        st.bar_chart(embed_rows, x="model", y="score", height=260)

    with st.expander("해석 가이드"):
        st.markdown(
            "- **cosine** (embedding 모델): −1 ~ 1. 의미 유사 쌍은 일반적으로 > 0.7, "
            "의미 다른 쌍은 < 0.5 가 정상.\n"
            "- **cross** (reranker): 단위가 cosine 과 다르다. 같은 모델 안에서 "
            "다른 쌍 끼리 상대 비교에만 의미.\n"
            "- **한국어 약점 모델**: 유사 쌍·반대 쌍이 모두 0.6 ~ 0.8 에 몰리면 변별력 부족.\n"
            "- **다국어 매칭**: 한국어 ↔ 영어 쌍에서 점수가 영어 단일 모델 대비 떨어지면 "
            "한국어 학습이 약한 모델."
        )

    with st.expander("raw JSON"):
        st.json(payload)
else:
    st.info("좌측에서 text1/text2 입력 + 모델 선택 후 **유사도 비교** 를 누르세요.")
    with st.expander("이 페이지가 무엇을 보여주는가"):
        st.markdown(
            "- **목적**: 같은 두 텍스트를 임베딩 모델마다 다르게 임베딩 → cosine 유사도 비교.\n"
            "- **시나리오**: 7강 강사가 사규 39조 검색 실패 → 임베딩 모델 교체로 해결한 그 과정의 측정 도구.\n"
            "- **모델 set**:\n"
            "  - `gemini` (text-embedding-004) — 기존 default. 호출당 과금.\n"
            "  - `bge-m3` — 다국어 강함, 한국어 우수. 로컬, 첫 호출 시 ~2GB 다운로드.\n"
            "  - `e5-large` — Microsoft multilingual-e5-large. 로컬, ~2GB.\n"
            "  - `reranker-bge` — 기존 ONNX reranker 재사용. 임베딩 X, cross-encoder score 직접 출력 (단위 다름 주의).\n"
            "- **모델 추가**: backend `chat/embedding_views.py` 의 `EMBEDDING_REGISTRY` 딕셔너리에 한 줄 추가하면 끝. 코드 변경 후 backend 재기동만.\n"
            "- **다음 phase**: Mode B (n×n matrix + UMAP), Mode C (corpus retrieval top-k) — design.md §8."
        )
