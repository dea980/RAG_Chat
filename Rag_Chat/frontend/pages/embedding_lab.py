"""Embedding Lab — Pair Compare (Mode A) + Benchmark Eval (Mode B).

Mode A: 두 텍스트의 모델별 유사도 한 줄 비교.
Mode B: 라벨된 데이터셋 (KorSTS / KorNLI / 자체 큐레이션) 으로 모델별 정량 평가
        — Pearson/Spearman, bucket separation, scatter, worst-pair drill-down.

저장·임베딩 부작용 없음 (in-memory only). 첫 호출 시 sentence-transformers
모델 ~2GB 다운로드가 발생할 수 있다.

backend:
  POST /api/v1/triple/embeddings/compare/   (Mode A)
  GET  /api/v1/triple/embeddings/eval/      (Mode B 메타)
  POST /api/v1/triple/embeddings/eval/      (Mode B 실행)
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Embedding Lab", layout="wide")

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from role_gate import require_manager  # noqa: E402
require_manager()

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"
COMPARE_URL = f"{API_BASE}/embeddings/compare/"
EVAL_URL = f"{API_BASE}/embeddings/eval/"

# 의미 쌍 sample — design.md §6 의 SEMANTIC_PAIRS 일부.
SEMANTIC_PAIRS: dict[str, tuple[str, str]] = {
    "유사1: 연차 휴가 vs 연차 사용": ("연차 휴가", "연차 사용"),
    "유사2: 가격 ko vs en": ("가격이 얼마인가요", "What is the price"),
    "반대1: 사과 먹다 vs 받다": ("사과를 먹다", "사과를 받다"),
    "반대2: 월급 인상 vs 임금 삭감": ("월급 인상", "임금 삭감"),
    "도메인: 3분기 매출 vs Q3 revenue": ("3분기 매출", "Q3 revenue"),
}


# ---------------------------------------------------------------------------
# Backend helpers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=600)
def fetch_registered_models() -> list[dict[str, Any]]:
    try:
        resp = requests.get(COMPARE_URL, timeout=10)
        resp.raise_for_status()
        return resp.json().get("models", [])
    except Exception:
        return [
            {"id": "gemini", "label": "Gemini text-embedding-004", "kind": "embedding"},
            {"id": "bge-m3", "label": "BAAI/bge-m3", "kind": "embedding"},
            {"id": "e5-large", "label": "intfloat/multilingual-e5-large", "kind": "embedding"},
            {"id": "reranker-bge", "label": "ONNX bge-reranker-v2-m3", "kind": "cross"},
        ]


@st.cache_data(ttl=600)
def fetch_eval_meta() -> dict[str, Any]:
    try:
        resp = requests.get(EVAL_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {"datasets": [], "models": [], "error": str(exc)}


def call_compare(text1: str, text2: str, models: list[str]) -> dict[str, Any]:
    resp = requests.post(
        COMPARE_URL,
        json={"text1": text1, "text2": text2, "models": models},
        headers={"Content-Type": "application/json"},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


def call_eval(dataset: str, models: list[str], limit: int | None) -> dict[str, Any]:
    body: dict[str, Any] = {"dataset": dataset, "models": models}
    if limit is not None:
        body["limit"] = limit
    resp = requests.post(
        EVAL_URL,
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🧬 Embedding Lab")
st.caption(
    "Mode A = 두 텍스트의 모델별 유사도. Mode B = 라벨된 벤치마크 (KorSTS / KorNLI / 자체) "
    "전체 평가. 강사 7강 \"임베딩 모델 바꿔서 39조 찾음\" 시나리오의 정량 버전."
)

registered = fetch_registered_models()
model_ids = [m["id"] for m in registered]
labels_by_id = {m["id"]: m["label"] for m in registered}

tab_pair, tab_eval = st.tabs(["🔍 Pair Compare (Mode A)", "📊 Benchmark Eval (Mode B)"])

# ---------------------------------------------------------------------------
# Mode A — Pair Compare
# ---------------------------------------------------------------------------

with tab_pair:
    col_input, col_models = st.columns([2, 1])
    with col_input:
        sample_key = st.selectbox(
            "샘플 쌍",
            ["(직접 입력)"] + list(SEMANTIC_PAIRS.keys()),
            key="pair_sample",
        )
        if sample_key != "(직접 입력)":
            default1, default2 = SEMANTIC_PAIRS[sample_key]
        else:
            default1, default2 = "", ""
        text1 = st.text_area("text1", value=default1, height=100, key="pair_text1")
        text2 = st.text_area("text2", value=default2, height=100, key="pair_text2")

    with col_models:
        default_selected = [m for m in ["gemini", "bge-m3", "e5-large"] if m in model_ids]
        selected_pair = st.multiselect(
            "비교할 모델",
            options=model_ids,
            default=default_selected,
            format_func=lambda mid: labels_by_id.get(mid, mid),
            key="pair_models",
        )
        run_pair = st.button(
            "유사도 비교", type="primary", use_container_width=True, key="pair_run"
        )
        st.caption(
            "⚠ sentence-transformers 모델 첫 호출 시 ~2GB 다운로드. "
            "폐쇄망은 `SENTENCE_TRANSFORMERS_HOME`."
        )

    if run_pair:
        if not text1.strip() or not text2.strip():
            st.warning("text1, text2 둘 다 필요합니다.")
            st.stop()
        if not selected_pair:
            st.warning("모델을 한 개 이상 선택하세요.")
            st.stop()
        with st.spinner(f"{len(selected_pair)}개 모델 임베딩 + 유사도 계산 중..."):
            try:
                payload = call_compare(text1.strip(), text2.strip(), selected_pair)
            except requests.HTTPError as exc:
                st.error(f"backend {exc.response.status_code}: {exc.response.text[:300]}")
                st.stop()
            except requests.RequestException as exc:
                st.error(f"요청 실패: {exc}")
                st.stop()

        results: dict[str, Any] = payload.get("results", {})
        if not results:
            st.warning("결과 없음.")
        else:
            rows = []
            for mid, r in results.items():
                rows.append({
                    "model": labels_by_id.get(mid, mid),
                    "kind": r.get("kind", "?"),
                    "score": r.get("score"),
                    "dim": r.get("dim"),
                    "error": r.get("error", ""),
                })
            df = pd.DataFrame(rows)
            st.subheader("모델별 유사도")
            st.dataframe(df, use_container_width=True, hide_index=True)

            embed_rows = df[df["kind"] == "cosine"].dropna(subset=["score"])
            if not embed_rows.empty:
                st.subheader("cosine 유사도 (embedding 모델만)")
                st.bar_chart(embed_rows, x="model", y="score", height=260)

            with st.expander("해석 가이드"):
                st.markdown(
                    "- **cosine**: −1 ~ 1. 유사 쌍 > 0.7, 무관 쌍 < 0.5 정상.\n"
                    "- **cross** (reranker): 단위 다름. 다른 쌍 끼리 상대 비교만.\n"
                    "- 모든 쌍이 0.6~0.8 에 몰리면 변별력 부족 모델.\n"
                    "- 한국어↔영어 쌍 점수가 단일언어 모델 대비 떨어지면 한국어 학습 약함."
                )

            with st.expander("raw JSON"):
                st.json(payload)
    else:
        st.info("text1/text2 입력 + 모델 선택 후 **유사도 비교** 를 누르세요.")

# ---------------------------------------------------------------------------
# Mode B — Benchmark Eval
# ---------------------------------------------------------------------------

with tab_eval:
    meta = fetch_eval_meta()
    datasets = meta.get("datasets", [])
    eval_models = [m["id"] for m in meta.get("models", registered)]
    eval_labels = {m["id"]: m["label"] for m in meta.get("models", registered)}

    if "error" in meta:
        st.warning(f"메타 로드 실패 (백엔드 미기동?): {meta['error']}")

    col_ctrl, col_help = st.columns([2, 1])

    with col_ctrl:
        dataset_options = [(d["id"], f"{d['id']} — {d['label']}") for d in datasets]
        if not dataset_options:
            dataset_options = [
                ("korsts-dev", "korsts-dev"),
                ("kornli-dev", "kornli-dev"),
                ("curated", "curated"),
            ]
        dataset_id = st.selectbox(
            "데이터셋",
            options=[d[0] for d in dataset_options],
            format_func=lambda did: dict(dataset_options).get(did, did),
            key="eval_dataset",
        )

        default_eval_models = [m for m in ["bge-m3", "gemini"] if m in eval_models]
        selected_eval = st.multiselect(
            "평가할 모델 (여러 개 선택)",
            options=eval_models or model_ids,
            default=default_eval_models,
            format_func=lambda mid: eval_labels.get(mid, mid),
            key="eval_models",
        )

        limit = st.select_slider(
            "평가 쌍 수 (속도/정확도 trade-off)",
            options=[50, 100, 300, 500, 1000, 1500, 3000, "전체"],
            value=300,
            key="eval_limit",
        )

        run_eval = st.button(
            "평가 실행", type="primary", use_container_width=True, key="eval_run"
        )

    with col_help:
        st.markdown(
            """
            **데이터셋**
            - **korsts-dev/test** — 점수 0~5. Pearson/Spearman 측정.
            - **kornli-dev/test** — entailment/neutral/contradiction. bucket 평균 비교.
            - **curated** — 자체 사규/HR/재무 도메인 쌍.

            **속도 가이드 (CPU)**
            | 모델 | 1500쌍 |
            |---|---|
            | bge-m3 | ~75초 |
            | gemini | ~50초 (API) |
            | reranker-bge | ~120초 |

            결과는 in-memory. DB 저장 X.
            """
        )

    if run_eval:
        if not selected_eval:
            st.warning("모델을 한 개 이상 선택하세요.")
            st.stop()
        limit_val = None if limit == "전체" else int(limit)
        with st.spinner(
            f"{dataset_id} × {len(selected_eval)}개 모델 평가 중 "
            f"(쌍 수: {'전체' if limit_val is None else limit_val})..."
        ):
            try:
                eval_payload = call_eval(dataset_id, selected_eval, limit_val)
            except requests.HTTPError as exc:
                st.error(f"backend {exc.response.status_code}: {exc.response.text[:300]}")
                st.stop()
            except requests.RequestException as exc:
                st.error(f"요청 실패: {exc}")
                st.stop()

        pair_count = eval_payload.get("pair_count", 0)
        results_by_model = eval_payload.get("results", {})

        if not results_by_model or pair_count == 0:
            st.warning("결과 없음.")
        else:
            st.success(f"평가 완료 — {pair_count} 쌍 × {len(results_by_model)} 모델")

            # 1) 지표 표
            metric_rows = []
            for mid, m in results_by_model.items():
                if "error" in m:
                    metric_rows.append({"model": eval_labels.get(mid, mid), "error": m["error"]})
                    continue
                row = {
                    "model": eval_labels.get(mid, mid),
                    "kind": m.get("kind", ""),
                    "pearson": m.get("pearson"),
                    "spearman": m.get("spearman"),
                    "separation": m.get("separation"),
                    "separation_hard": m.get("separation_hard"),
                }
                for bucket, val in (m.get("bucket_means") or {}).items():
                    row[f"mean[{bucket}]"] = val
                metric_rows.append(row)
            st.subheader("모델별 지표")
            st.dataframe(pd.DataFrame(metric_rows), use_container_width=True, hide_index=True)

            # 2) Scatter — only meaningful for regression (KorSTS)
            for mid, m in results_by_model.items():
                if "error" in m:
                    continue
                scatter = m.get("scatter") or []
                if not scatter:
                    continue
                # KorSTS scatter (numeric label vs score)
                numeric = [
                    row for row in scatter
                    if isinstance(row.get("label"), (int, float))
                ]
                if numeric:
                    st.markdown(f"#### scatter — `{mid}` (사람 score vs 모델 점수)")
                    df_sc = pd.DataFrame(numeric)
                    st.scatter_chart(
                        df_sc, x="label", y="score", color="bucket", height=260,
                    )
                    continue
                # KorNLI/curated bucket bar
                df_sc = pd.DataFrame(scatter)
                means = df_sc.groupby("bucket")["score"].mean().reset_index()
                st.markdown(f"#### bucket 평균 — `{mid}`")
                st.bar_chart(means, x="bucket", y="score", height=200)

            # 3) Worst pairs (drill-down)
            for mid, m in results_by_model.items():
                if "error" in m:
                    continue
                errors = m.get("top_errors") or []
                if not errors:
                    continue
                with st.expander(f"⚠ `{mid}` — 가장 헤맨 쌍 top {len(errors)}"):
                    err_df = pd.DataFrame(errors)
                    st.dataframe(err_df, use_container_width=True, hide_index=True)
                    st.caption(
                        "`err` 가 크다 = 모델이 사람 라벨에서 가장 멀리 떨어진 예측. "
                        "여기서 모델의 한계 (도메인 / 부정 / 동음이의) 가 드러난다."
                    )

            with st.expander("raw JSON (디버깅)"):
                st.json(eval_payload)
    else:
        st.info(
            "데이터셋·모델·쌍 수 선택 후 **평가 실행**. "
            "처음 호출 시 모델 다운로드로 첫 평가는 더 오래 걸린다."
        )
        with st.expander("📚 지표 해석"):
            st.markdown(
                """
                | 지표 | 의미 | 좋은 모델 |
                |---|---|---|
                | **pearson** | 모델 score 와 사람 score 의 선형 상관 | > 0.80 |
                | **spearman** | 순위 상관 (스케일 무관) | > 0.80 |
                | **separation** | positive 평균 − negative 평균 | > 0.35 |
                | **separation_hard** | positive 평균 − hard_negative 평균 | > 0.20 |
                | **mean[positive]** | 의미 유사 쌍 평균 점수 | > 0.70 |
                | **mean[hard_negative]** | negation/homonym 평균 | 낮을수록 좋음 |

                **cross-encoder (reranker)**: 점수에 sigmoid 적용해서 0~1 로
                정규화. embedding 과 절대 비교는 불가하지만 separation 비교는 유효.
                """
            )
