"""Chat Compare — 같은 프롬프트를 N개 모델에 동시 호출하고 응답을 나란히 비교.

`/api/v1/triple/chat/compare/` 가 RAG/moderation/DB 없이 모델만 부르고 결과를
리턴한다. 모델 spec 형식: `provider:model` (예: `ollama:gpt-oss`) 또는 `provider`
(env 의 default 모델 사용).
"""
from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

st.set_page_config(page_title="Chat Compare", layout="wide")

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"
COMPARE_URL = f"{API_BASE}/chat/compare/"

PROVIDER_OPTIONS = [
    "ollama",
    "gemini",
    "openrouter",
    "qwen",
    "huggingface",
]

# Provider 별 자주 쓰는 모델 후보 — 사용자가 자유 입력도 가능.
KNOWN_MODELS: dict[str, list[str]] = {
    "ollama": ["qwen3.6", "gpt-oss", "llama3.1", "(env default)"],
    "gemini": ["(env default)", "gemini-1.5-pro", "gemini-1.5-flash"],
    "openrouter": ["(env default)"],
    "qwen": ["(env default)"],
    "huggingface": ["(env default)"],
}


def call_compare(prompt: str, specs: list[str]) -> dict[str, Any]:
    resp = requests.post(
        COMPARE_URL,
        json={"prompt": prompt, "models": specs},
        headers={"Content-Type": "application/json"},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()


def spec_from_choice(provider: str, model: str) -> str:
    if not model or model == "(env default)":
        return provider
    return f"{provider}:{model}"


st.title("🆚 Chat Compare")
st.caption(
    "같은 프롬프트를 여러 모델에 동시에 보내고 응답을 나란히 본다. "
    "RAG/moderation/DB 저장 없음 — 순수 모델 응답만."
)

with st.sidebar:
    st.subheader("프롬프트")
    prompt = st.text_area(
        "텍스트",
        height=180,
        placeholder="비교할 질문/프롬프트를 입력하세요...",
    )

    st.divider()
    st.subheader("비교 모델")
    n_cols = st.slider("컬럼 수", 1, 4, 2)

    defaults = [
        ("ollama", "qwen3.6"),
        ("ollama", "gpt-oss"),
        ("gemini", "(env default)"),
        ("openrouter", "(env default)"),
    ]

    specs: list[str] = []
    labels: list[str] = []
    for i in range(n_cols):
        default_provider, default_model = defaults[i]
        st.markdown(f"**컬럼 #{i + 1}**")
        provider = st.selectbox(
            f"provider #{i + 1}",
            PROVIDER_OPTIONS,
            index=PROVIDER_OPTIONS.index(default_provider),
            key=f"prov_{i}",
            label_visibility="collapsed",
        )
        model_choices = KNOWN_MODELS.get(provider, ["(env default)"])
        default_index = (
            model_choices.index(default_model)
            if default_model in model_choices else 0
        )
        model_choice = st.selectbox(
            f"model #{i + 1}",
            model_choices,
            index=default_index,
            key=f"model_choice_{i}",
            label_visibility="collapsed",
        )
        custom = st.text_input(
            f"custom model #{i + 1} (옵션)",
            value="",
            key=f"model_custom_{i}",
            placeholder="비워두면 위 선택값 사용",
            label_visibility="collapsed",
        )
        final_model = custom.strip() or model_choice
        spec = spec_from_choice(provider, final_model)
        specs.append(spec)
        labels.append(spec)

    st.divider()
    run = st.button("비교 실행", type="primary", use_container_width=True)

if run:
    if not prompt.strip():
        st.warning("프롬프트가 필요합니다.")
        st.stop()

    with st.spinner(f"{len(specs)}개 모델 호출 중... (오래 걸릴 수 있음)"):
        try:
            payload = call_compare(prompt.strip(), specs)
        except requests.HTTPError as exc:
            st.error(
                f"backend {exc.response.status_code}: {exc.response.text[:300]}"
            )
            st.stop()
        except requests.RequestException as exc:
            st.error(f"요청 실패: {exc}")
            st.stop()

    results = payload.get("results", [])
    if not results:
        st.warning("결과 없음.")
        st.stop()

    cols = st.columns(len(results))
    for col, r in zip(cols, results):
        with col:
            spec = r.get("spec", "?")
            elapsed = r.get("elapsed_ms")
            st.subheader(spec)
            if elapsed is not None:
                st.caption(f"⏱ {elapsed} ms")
            if "error" in r:
                st.error(f"오류: {r['error']}")
            else:
                st.markdown(r.get("response", ""))

    with st.expander("raw JSON"):
        st.json(payload)
else:
    st.info("좌측에서 프롬프트 입력 + 컬럼 설정 후 **비교 실행** 을 누르세요.")
    with st.expander("이 페이지가 무엇을 보여주는가"):
        st.markdown(
            "- **목적**: 같은 질문에 모델마다 응답이 어떻게 다른지 시각 비교.\n"
            "- **RAG 없음**: 백엔드 검색·context 주입을 거치지 않는다. "
            "순수 모델 응답만. 같은 prompt 라도 RAG 통과 시는 결과가 달라질 수 있다.\n"
            "- **moderation 없음**: 차단 단어 필터도 없으니 사내 도메인 표현 시험에 적합.\n"
            "- **DB 저장 없음**: chat 기록이 남지 않는다 — lab 페이지 본분.\n"
            "- **모델 spec**: `provider:model` 형식. model 비워두면 backend `.env` 의 default 모델 사용.\n"
            "- **Ollama 모델 추가**: `ollama pull <model>` 후 custom 칸에 모델명 입력하면 즉시 사용 가능."
        )
