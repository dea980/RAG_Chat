"""Token Lab — model/language token comparison page."""
from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

st.set_page_config(page_title="Token Lab", layout="wide")

API_BASE = os.getenv("API_BASE_URL") or (
    os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"
)
TOKEN_URL = f"{API_BASE}/tokens/estimate/"


DEFAULT_TEXT = """갤럭시 S25 Ultra 512GB 모델의 카메라 사양, 가격, 색상을
영업팀 고객 안내용으로 한국어와 영어를 섞어서 요약해 주세요."""


def call_token_estimate(text: str, include_samples: bool) -> dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        json={"text": text, "include_samples": include_samples},
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def profile_rows(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for profile in analysis.get("profiles", []):
        rows.append({
            "profile": profile["label"],
            "tokens": profile["tokens"],
            "tokens / char": profile["tokens_per_character"],
            "method": profile["method"],
            "tokenizer": profile["tokenizer"],
            "note": profile["note"],
        })
    return rows


def language_rows(samples: list[dict[str, Any]], profile_id: str) -> list[dict[str, Any]]:
    rows = []
    for sample in samples:
        selected = next(
            (p for p in sample["profiles"] if p["id"] == profile_id),
            sample["profiles"][0],
        )
        rows.append({
            "language": sample["language"],
            "characters": sample["characters"],
            "bytes": sample["bytes"],
            "tokens": selected["tokens"],
            "tokens / char": selected["tokens_per_character"],
            "sample": sample["text"],
        })
    return rows


st.title("Token Lab")

with st.sidebar:
    st.header("Input")
    include_samples = st.checkbox("언어 샘플 비교", value=True)
    chart_profile = st.selectbox(
        "언어 비교 기준",
        [
            ("openai_o200k", "GPT-4o / o-series"),
            ("openai_cl100k", "GPT-4 / GPT-3.5 / embeddings"),
            ("gemini_estimate", "Gemini estimate"),
            ("claude_estimate", "Claude estimate"),
            ("qwen_estimate", "Qwen estimate"),
        ],
        format_func=lambda item: item[1],
    )[0]
    run = st.button("계산", type="primary", use_container_width=True)

text = st.text_area(
    "텍스트",
    value=DEFAULT_TEXT,
    height=220,
    placeholder="토큰 수를 비교할 프롬프트, RAG chunk, 코드, 문서를 입력하세요.",
)

if run:
    if not text.strip():
        st.warning("텍스트가 필요합니다.")
        st.stop()

    try:
        payload = call_token_estimate(text, include_samples)
    except requests.HTTPError as exc:
        st.error(f"backend 오류: {exc.response.status_code} {exc.response.text[:300]}")
        st.stop()
    except requests.RequestException as exc:
        st.error(f"요청 실패: {exc}")
        st.stop()

    analysis = payload["analysis"]

    top = st.columns(4)
    top[0].metric("문자", analysis["characters"])
    top[1].metric("Bytes", analysis["bytes"])
    top[2].metric("기준 토큰", analysis["reference_tokens"])
    top[3].metric("기준 모델", analysis["reference_profile"])

    st.subheader("모델별 토큰")
    rows = profile_rows(analysis)
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.bar_chart(rows, x="profile", y="tokens", height=260)

    st.subheader("RAG chunk 기준")
    st.dataframe(
        analysis["chunk_recommendations"],
        use_container_width=True,
        hide_index=True,
    )

    samples = payload.get("language_samples") or []
    if samples:
        st.subheader("언어별 샘플 비교")
        lang = language_rows(samples, chart_profile)
        st.dataframe(lang, use_container_width=True, hide_index=True)
        st.bar_chart(lang, x="language", y="tokens", height=260)

    with st.expander("계산 방식"):
        st.markdown(
            "- 기본 동작은 네트워크 없는 byte 기반 fallback 계산이다.\n"
            "- 서버에서 `TOKENLAB_ENABLE_TIKTOKEN=1` 을 켜고 encoding cache 가 준비되어 있으면 OpenAI 계열은 `tiktoken` exact 계산을 사용한다.\n"
            "- Gemini, Claude, Qwen 은 실제 tokenizer 가 달라 estimate 로 표시한다.\n"
            "- RAG chunk 추천은 `openai_cl100k` 기준 토큰 수를 250/500/1000/2000으로 나눈 값이다."
        )
else:
    st.info("텍스트를 입력하고 계산을 누르세요.")
