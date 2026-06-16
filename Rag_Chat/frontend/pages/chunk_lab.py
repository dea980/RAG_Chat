"""Chunk Lab — 청크 사이즈/오버랩/splitter 별 결과를 나란히 비교.

이 페이지는 임베딩·저장을 하지 않는다. backend `/api/v1/triple/ingest/preview`
엔드포인트가 splitter 결과만 JSON 으로 돌려주고, 여기서 시각화한다.

학습용 메모:
  - 청크 크기가 작으면: 청크 수 많음 + 맥락 끊김
  - 청크 크기가 크면: 청크 수 적음 + 관련 없는 내용 섞임 (노이즈)
  - 7강 강사가 39조 정답 못 찾다가 500자 → "조항 단위" 로 바꾸고 찾은 그 실험.

UI 스택:
  - streamlit-extras: style_metric_cards
  - st.subheader(divider="violet") — colored_header 대체 (1.45+ deprecated)
  - st-aggrid: 정렬·셀 색상 가능한 비교 테이블 / 청크 그리드
  - plotly: 청크 길이 분포 overlay 히스토그램
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from st_aggrid import AgGrid, ColumnsAutoSizeMode, GridOptionsBuilder
from st_aggrid.shared import JsCode
from streamlit_extras.metric_cards import style_metric_cards


def _section(label: str, description: str = "") -> None:
    """colored_header 대체 — st.subheader(divider) 사용."""
    st.subheader(label, divider="violet")
    if description:
        st.caption(description)

st.set_page_config(page_title="Chunk Lab", layout="wide")

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from role_gate import require_manager  # noqa: E402
require_manager()

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"
PREVIEW_URL = f"{API_BASE}/ingest/preview/"
INGEST_URL = f"{API_BASE}/ingest/upload/"


# --- API --------------------------------------------------------------------


def call_ingest(
    file: Any, *, collection: str = "policy", sensitivity: str = "internal",
) -> dict:
    """실제 적재 — backend /ingest/upload/ 호출. DB write 발생."""
    files = {"files": (file.name, file.getvalue())}
    data = {"collection": collection, "sensitivity": sensitivity}
    resp = requests.post(INGEST_URL, files=files, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


COLLECTION_CHOICES = {
    "training": "학습 자료",
    "policy":   "사규·정책",
    "sales":    "영업 데이터",
    "user":     "유저 추가",
}

SENSITIVITY_CHOICES = {
    "public":       "공개",
    "internal":     "사내 공유",
    "confidential": "대외비",
    "restricted":   "기밀 (인덱싱 차단)",
}


def call_preview(
    *,
    text: str | None,
    file: Any,
    chunk_size: int,
    chunk_overlap: int,
    splitter: str,
) -> dict:
    """backend preview 엔드포인트 호출. text 또는 file 둘 중 하나."""
    data = {
        "chunk_size": str(chunk_size),
        "chunk_overlap": str(chunk_overlap),
        "splitter": splitter,
    }
    if file is not None:
        files = {"file": (file.name, file.getvalue())}
        resp = requests.post(PREVIEW_URL, data=data, files=files, timeout=30)
    else:
        data["text"] = text or ""
        resp = requests.post(PREVIEW_URL, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


# --- Visualization ----------------------------------------------------------


_LENGTH_HEAT_JS = JsCode(
    """
    function(params) {
        const v = params.value || 0;
        const max = 1500;
        const ratio = Math.min(v / max, 1);
        const r = Math.round(255 * ratio);
        const g = Math.round(180 * (1 - ratio));
        return {
            'backgroundColor': `rgba(${r}, ${g}, 80, 0.18)`,
            'textAlign': 'right',
            'fontVariantNumeric': 'tabular-nums',
        };
    }
    """
)


def summary_grid(results: list[dict]) -> None:
    """전 컬럼 비교 요약 — 정렬 가능 + 길이 셀 색상."""
    rows = [
        {
            "config": f"size={r['chunk_size']} / ov={r['chunk_overlap']}",
            "num_chunks": r["num_chunks"],
            "min": r["min_length"],
            "avg": r["avg_length"],
            "max": r["max_length"],
            "total_chars": r["total_chars"],
        }
        for r in results
    ]
    df = pd.DataFrame(rows)
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(sortable=True, resizable=True, filter=True)
    gb.configure_column("config", pinned="left", width=220)
    for c in ("num_chunks", "total_chars"):
        gb.configure_column(
            c, type=["numericColumn"], width=120,
            cellStyle={"fontVariantNumeric": "tabular-nums", "textAlign": "right"},
        )
    for c in ("min", "avg", "max"):
        gb.configure_column(c, type=["numericColumn"], width=100, cellStyle=_LENGTH_HEAT_JS)
    AgGrid(
        df,
        gridOptions=gb.build(),
        allow_unsafe_jscode=True,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_ALL_COLUMNS_TO_VIEW,
        height=min(180 + 32 * len(rows), 420),
        theme="streamlit",
        key="summary_grid",
    )


def length_distribution_plot(results: list[dict]) -> None:
    """청크 길이 분포 overlay 히스토그램."""
    fig = go.Figure()
    for r in results:
        lengths = [c["length"] for c in r["chunks"]]
        if not lengths:
            continue
        fig.add_trace(
            go.Histogram(
                x=lengths,
                name=f"size={r['chunk_size']} / ov={r['chunk_overlap']}",
                opacity=0.55,
                nbinsx=30,
            )
        )
    fig.update_layout(
        barmode="overlay",
        xaxis_title="청크 길이 (글자)",
        yaxis_title="개수",
        height=320,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", y=-0.25),
    )
    st.plotly_chart(fig, use_container_width=True)


def chunk_preview_grid(chunks: list[dict], key: str) -> None:
    """청크 미리보기 — 정렬·필터·셀 클릭 확장. 익스팬더 스택 대체."""
    if not chunks:
        st.info("청크 없음")
        return
    df = pd.DataFrame(chunks).reindex(
        columns=["chunk_index", "length", "section", "content"]
    )
    df["section"] = df["section"].fillna("")

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        wrapText=True, autoHeight=True, resizable=True, sortable=True, filter=True,
    )
    gb.configure_column("chunk_index", header_name="#", width=70, pinned="left")
    gb.configure_column(
        "length", header_name="len", width=100, cellStyle=_LENGTH_HEAT_JS,
    )
    gb.configure_column("section", width=130)
    gb.configure_column(
        "content",
        flex=2,
        cellStyle={
            "whiteSpace": "pre-wrap",
            "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace",
            "fontSize": "12px",
            "lineHeight": "1.45",
        },
    )

    AgGrid(
        df,
        gridOptions=gb.build(),
        allow_unsafe_jscode=True,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        height=460,
        theme="streamlit",
        key=key,
    )


# --- Sidebar ----------------------------------------------------------------


_section(
    "🧪 Chunk Lab",
    "청크 사이즈·오버랩 별 결과를 나란히 비교. 저장·임베딩은 하지 않음.",
)

with st.sidebar:
    st.subheader("입력")
    src_mode = st.radio("소스", ["붙여넣기", "파일 업로드"], horizontal=True)
    pasted_text = ""
    uploaded_file = None
    if src_mode == "붙여넣기":
        pasted_text = st.text_area(
            "텍스트",
            height=200,
            placeholder="여기에 사규/문서/매뉴얼 일부를 붙여넣으세요...",
        )
    else:
        uploaded_file = st.file_uploader(
            "파일 (CSV/XLSX/TXT/MD)",
            type=["csv", "xlsx", "xls", "txt", "md"],
        )

    st.divider()
    st.subheader("Splitter")
    splitter_name = st.selectbox(
        "전략",
        ["recursive", "row", "heading", "clause"],
        help=(
            "recursive = 길이 기반 / row = 1행 1청크 (표 전용) / "
            "heading = markdown heading 계층 (구조화 md) / "
            "clause = 제N조·Article N 조항 단위 (사규·법규)"
        ),
    )

    st.divider()
    st.subheader("비교 컬럼")
    n_cols = st.slider("동시 비교 개수", 1, 4, 3)
    default_sizes = [200, 500, 1000, 1500][:n_cols]
    default_overlaps = [0, 50, 100, 150][:n_cols]

    configs = []
    for i in range(n_cols):
        c1, c2 = st.columns(2)
        with c1:
            cs = st.number_input(
                f"size #{i + 1}",
                min_value=50, max_value=5000,
                value=default_sizes[i], step=50, key=f"cs_{i}",
            )
        with c2:
            co = st.number_input(
                f"overlap #{i + 1}",
                min_value=0, max_value=1000,
                value=default_overlaps[i], step=10, key=f"co_{i}",
            )
        configs.append({"chunk_size": cs, "chunk_overlap": co})

    st.divider()
    run = st.button("청킹 실행", type="primary", use_container_width=True)

    st.divider()
    st.subheader("실제 적재")
    st.caption(
        "⚠️ DB·벡터 저장 발생. 좌측 splitter/size 설정은 **무시**됨 — "
        "`ingest_path()` 가 파일 타입별 자동 dispatch. 같은 파일명 재업로드는 "
        "SHA256 dedup."
    )
    ingest_collection = st.selectbox(
        "Collection (도메인 분류)",
        list(COLLECTION_CHOICES.keys()),
        format_func=lambda k: f"{k} — {COLLECTION_CHOICES[k]}",
        index=1,  # policy default
        help="청크에 박혀 검색 시 namespace 필터로 사용. enum 외 값 거부됨.",
    )
    ingest_sensitivity = st.selectbox(
        "Sensitivity (열람 등급)",
        list(SENSITIVITY_CHOICES.keys()),
        format_func=lambda k: f"{k} — {SENSITIVITY_CHOICES[k]}",
        index=1,  # internal default
        help="restricted = 벡터 스토어 진입 차단 (Layer 1).",
    )
    ingest_disabled = uploaded_file is None
    if ingest_disabled:
        st.caption("파일 업로드 모드일 때만 활성화 (text 는 source_uri 불안정).")
    ingest_run = st.button(
        "이 파일을 실제 적재",
        type="secondary",
        use_container_width=True,
        disabled=ingest_disabled,
    )


# --- Run --------------------------------------------------------------------


if run:
    has_input = bool(pasted_text.strip()) or uploaded_file is not None
    if not has_input:
        st.warning("텍스트 붙여넣기 또는 파일 업로드 둘 중 하나가 필요합니다.")
        st.stop()

    results: list[dict] = []
    with st.spinner("청킹 중..."):
        for cfg in configs:
            try:
                res = call_preview(
                    text=pasted_text,
                    file=uploaded_file,
                    chunk_size=cfg["chunk_size"],
                    chunk_overlap=cfg["chunk_overlap"],
                    splitter=splitter_name,
                )
            except requests.HTTPError as exc:
                st.error(
                    f"backend {exc.response.status_code}: {exc.response.text[:200]}"
                )
                continue
            except requests.RequestException as exc:
                st.error(f"요청 실패: {exc}")
                continue
            results.append(res)

    if not results:
        st.stop()

    _section("📊 비교 요약", "헤더 클릭으로 정렬 가능")
    summary_grid(results)

    _section("📈 길이 분포", "여러 config 를 한 차트에 overlay")
    length_distribution_plot(results)

    _section("🔢 컬럼별 지표")
    cols = st.columns(len(results))
    for col, r in zip(cols, results):
        with col:
            st.caption(f"size={r['chunk_size']} / ov={r['chunk_overlap']}")
            m1, m2 = st.columns(2)
            m1.metric("청크 수", r["num_chunks"])
            m2.metric("평균", r["avg_length"])
            m1.metric("min", r["min_length"])
            m2.metric("max", r["max_length"])
    style_metric_cards(border_left_color="#7c3aed", box_shadow=True)

    _section(
        "🧩 청크 미리보기",
        "탭으로 config 전환 · 셀 클릭으로 전체 보기 · 헤더로 정렬",
    )
    tabs = st.tabs(
        [f"size={r['chunk_size']} / ov={r['chunk_overlap']}" for r in results]
    )
    for tab, r in zip(tabs, results):
        with tab:
            chunk_preview_grid(
                r["chunks"], key=f"grid_{r['chunk_size']}_{r['chunk_overlap']}"
            )

if ingest_run and uploaded_file is not None:
    _section(
        "📥 실제 적재 결과",
        f"collection={ingest_collection} · sensitivity={ingest_sensitivity}",
    )
    with st.spinner(f"적재 중... ({uploaded_file.name})"):
        try:
            res = call_ingest(
                uploaded_file,
                collection=ingest_collection,
                sensitivity=ingest_sensitivity,
            )
        except requests.HTTPError as exc:
            st.error(f"backend {exc.response.status_code}: {exc.response.text[:200]}")
            res = None
        except requests.RequestException as exc:
            st.error(f"요청 실패: {exc}")
            res = None

    if res is not None:
        processed = res.get("processed", [])
        failed = res.get("failed", [])
        cols = st.columns(3)
        cols[0].metric("처리됨", len(processed))
        cols[1].metric(
            "신규 청크",
            sum(p.get("chunks", 0) for p in processed if p.get("status") == "ok"),
        )
        cols[2].metric("실패", len(failed))
        style_metric_cards(border_left_color="#7c3aed", box_shadow=True)
        if processed:
            st.success("적재 완료")
            st.json(processed)
        if failed:
            st.error("일부 실패")
            st.json(failed)
        if processed and all(p.get("status") == "skipped" for p in processed):
            st.info("모두 dedup skip — 동일 SHA256 manifest 존재.")

if not run and not ingest_run:
    st.info("좌측에서 텍스트/파일 입력 후 **청킹 실행** 을 눌러주세요.")
    with st.expander("이 페이지가 무엇을 보여주는가"):
        st.markdown(
            "- **chunk_size**: 한 청크가 담을 글자 수 한계. 작으면 청크↑·맥락↓, "
            "크면 청크↓·노이즈↑.\n"
            "- **chunk_overlap**: 인접 청크 간 겹침. 너무 크면 중복 검색·"
            "비용↑, 너무 작으면 경계에서 맥락 끊김.\n"
            "- **splitter**: `recursive` = 단락/문장/단어 우선순위로 자름. "
            "`row` = 표 1행 1청크. `heading` = markdown `#`~`######` 계층 "
            "단위로 자름(구조화된 md). `clause` = `제N조`/`Article N` 조항 "
            "단위(사규·법규 — 7강 강사가 39조 정답 못 찾다 조항 단위로 "
            "바꾸고 찾은 그 케이스)."
        )
