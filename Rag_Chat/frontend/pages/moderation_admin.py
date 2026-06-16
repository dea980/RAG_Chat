"""Moderation operator page — rule CRUD + real-time test panel + recent logs.

Auth gate: only ADMIN role can open this page. The B6 backend permission
(IsModerationAdmin) is the authoritative gate; the frontend gate is for UX
("you don't have access") rather than security.

DESIGN.md tokens used:
- Mono small-caps section labels (Geist Mono 11px uppercase)
- Severity chip colors: BLOCK=#C24A4A · MASK=#D9A441 · WARN=#6B8AB8
- Accent amber #E89B3C for active states
- tabular-nums via Geist Mono on all data
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any

import requests
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auth as auth_mod  # noqa: E402

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"

SEVERITY_COLORS = {
    "BLOCK": "#C24A4A",
    "MASK": "#D9A441",
    "WARNING": "#6B8AB8",
}
ACTION_COLORS = {
    "BLOCKED": "#C24A4A",
    "MASKED": "#D9A441",
    "WARNED": "#6B8AB8",
    "PASS": "#4F9D7A",
}
SOURCE_LABELS = {
    "INBOUND": "사용자 입력 (질문)",
    "OUTBOUND": "LLM 응답",
    "UPLOAD": "문서 업로드",
    "RETRIEVAL": "벡터 검색 결과",
}

st.set_page_config(page_title="Moderation Admin · Triple Chat", layout="wide")

from role_gate import require_admin  # noqa: E402
require_admin()


def _inject_design_tokens() -> None:
    st.markdown(
        """
        <style>
          /* Geist Mono for all data; Pretendard for body — DESIGN.md tokens */
          .label-mono {
            font-family: 'Geist Mono', ui-monospace, monospace;
            font-size: 11px;
            letter-spacing: 0.09em;
            text-transform: uppercase;
            color: #8B8B93;
          }
          .chip {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: 'Geist Mono', monospace;
            font-size: 11px;
            font-feature-settings: 'tnum' 1;
            border: 1px solid rgba(255,255,255,0.08);
          }
          .data-cell {
            font-family: 'Geist Mono', monospace;
            font-feature-settings: 'tnum' 1;
            font-size: 13px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _chip(text: str, color: str) -> str:
    return (
        f'<span class="chip" style="color:{color};'
        f'background:{color}14;border-color:{color}55;">{text}</span>'
    )


def _section_label(text: str) -> None:
    st.markdown(f'<div class="label-mono">{text}</div>', unsafe_allow_html=True)


def _require_admin() -> dict[str, Any]:
    if not auth_mod.is_authenticated():
        st.warning("Sign in required.")
        auth_mod.render_login_form()
        st.stop()
    user = auth_mod.current_user() or {}
    if user.get("role") != "ADMIN":
        st.error("운영자(ADMIN) 권한이 필요합니다.")
        st.write(f"current role: `{user.get('role', '-')}` — contact admin to request access.")
        st.stop()
    return user


def _sess() -> requests.Session:
    return auth_mod.get_session()


def _fetch_rules() -> list[dict]:
    resp = _sess().get(f"{API_BASE}/moderation/rules/")
    resp.raise_for_status()
    body = resp.json()
    return body["results"] if isinstance(body, dict) else body


def _fetch_logs(limit: int = 20) -> list[dict]:
    resp = _sess().get(f"{API_BASE}/moderation/logs/")
    if resp.status_code != 200:
        return []
    body = resp.json()
    items = body["results"] if isinstance(body, dict) else body
    return items[:limit]


def _create_rule(payload: dict) -> tuple[bool, str]:
    resp = _sess().post(f"{API_BASE}/moderation/rules/", json=payload)
    if resp.status_code == 201:
        return True, "추가됨"
    try:
        return False, str(resp.json())
    except ValueError:
        return False, resp.text


def _delete_rule(rule_id: int) -> bool:
    resp = _sess().delete(f"{API_BASE}/moderation/rules/{rule_id}/")
    return resp.status_code == 204


def _test_text(text: str, source: str) -> dict:
    resp = _sess().post(
        f"{API_BASE}/moderation/test/", json={"text": text, "source": source}
    )
    resp.raise_for_status()
    return resp.json()


def _render_rules_section() -> None:
    _section_label("RULES")
    st.caption("ForbiddenWord — 4경계 (질문·응답·업로드·검색) 에 자동 적용")

    rules = _fetch_rules()

    if rules:
        for r in rules:
            cols = st.columns([3, 1, 2, 1, 1, 1, 1])
            cols[0].markdown(
                f'<span class="data-cell">{r["word"]}</span>'
                f' &nbsp;<span class="label-mono">{r["category"]}</span>',
                unsafe_allow_html=True,
            )
            ptype = r.get("pattern_type", "KW")
            ptype_color = "#E89B3C" if ptype == "RE" else "#8B8B93"
            cols[1].markdown(_chip(ptype, ptype_color), unsafe_allow_html=True)
            cols[2].markdown(
                _chip(r["severity"], SEVERITY_COLORS.get(r["severity"], "#8B8B93")),
                unsafe_allow_html=True,
            )
            cols[3].markdown(
                f'<span class="data-cell">{r["direction"]}</span>',
                unsafe_allow_html=True,
            )
            cols[4].markdown(
                "✓" if r["is_active"] else "—",
                unsafe_allow_html=True,
            )
            cols[5].markdown(
                f'<span class="data-cell" style="color:#5C5D63;font-size:11px;">'
                f'{r["updated_at"][:10]}</span>',
                unsafe_allow_html=True,
            )
            if cols[6].button("삭제", key=f"del_{r['id']}"):
                if _delete_rule(r["id"]):
                    st.rerun()
                else:
                    st.error("삭제 실패")
    else:
        st.caption("아직 등록된 규칙이 없습니다.")

    with st.expander("규칙 추가", expanded=False):
        with st.form("new_rule", clear_on_submit=True):
            word = st.text_input("단어 / 패턴 *")
            category = st.text_input("카테고리 *", placeholder="예: 기밀, PII, 욕설, 경쟁사")
            pattern_type = st.radio(
                "패턴 종류",
                ["KW", "RE"],
                format_func=lambda p: {
                    "KW": "키워드 — 대소문자 무시 부분 일치 (예: '대외비')",
                    "RE": r"정규식 — re.search (예: \d{6}-\d{7} 주민번호)",
                }[p],
                horizontal=True,
            )
            col1, col2, col3 = st.columns(3)
            severity = col1.selectbox(
                "Severity *",
                ["BLOCK", "MASK", "WARNING"],
                format_func=lambda s: {
                    "BLOCK": "BLOCK · 즉시 차단",
                    "MASK": "MASK · 마스킹",
                    "WARNING": "WARNING · 경고 후 통과",
                }[s],
            )
            direction = col2.selectbox(
                "방향 *",
                ["BOTH", "INBOUND", "OUTBOUND"],
                format_func=lambda d: {
                    "BOTH": "BOTH · 양방향",
                    "INBOUND": "INBOUND · 질문·업로드",
                    "OUTBOUND": "OUTBOUND · 응답·검색",
                }[d],
            )
            mask_repl = col3.text_input(
                "마스킹 치환문자", value="[REDACTED]",
                help="severity=MASK 일 때만 사용",
            )
            note = st.text_input("메모 (선택)", placeholder="이 규칙을 추가한 이유")
            if st.form_submit_button("추가", use_container_width=True):
                if not word.strip() or not category.strip():
                    st.error("단어와 카테고리는 필수입니다.")
                else:
                    ok, msg = _create_rule({
                        "word": word.strip(),
                        "category": category.strip(),
                        "pattern_type": pattern_type,
                        "severity": severity,
                        "direction": direction,
                        "mask_replacement": mask_repl,
                        "note": note,
                        "is_active": True,
                    })
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


def _render_test_panel() -> None:
    _section_label("TEST PANEL")
    st.caption("샘플 텍스트로 규칙 작동을 즉시 확인 — 감사 로그는 기록되지 않음")

    col1, col2 = st.columns([3, 1])
    text = col1.text_area(
        "테스트 텍스트",
        height=120,
        placeholder="예) 이건 대외비 문서입니다",
        label_visibility="collapsed",
    )
    source = col2.selectbox(
        "경계",
        list(SOURCE_LABELS.keys()),
        format_func=lambda s: SOURCE_LABELS[s],
    )
    run = col2.button("실행", type="primary", use_container_width=True)

    if run and text.strip():
        try:
            result = _test_text(text, source)
        except requests.HTTPError as exc:
            st.error(f"테스트 실패: {exc}")
            return
        action = result.get("action", "PASS")
        st.markdown(
            f'**Action:** {_chip(action, ACTION_COLORS.get(action, "#8B8B93"))}',
            unsafe_allow_html=True,
        )
        if result.get("blocked_words"):
            st.markdown(f"**Blocked:** `{', '.join(result['blocked_words'])}`")
        if result.get("masked_words"):
            st.markdown(f"**Masked:** `{', '.join(result['masked_words'])}`")
        if result.get("warned_words"):
            st.markdown(f"**Warned:** `{', '.join(result['warned_words'])}`")
        if result.get("categories"):
            st.markdown(f"**Categories:** {', '.join(result['categories'])}")
        if action == "MASKED" and result.get("sanitized"):
            st.markdown("**Sanitized output:**")
            st.code(result["sanitized"])
        elif action == "PASS":
            st.markdown(
                '<span class="data-cell" style="color:#4F9D7A;">'
                '통과 — 해당 경계에서 일치하는 활성 규칙이 없습니다.</span>',
                unsafe_allow_html=True,
            )


def _render_logs_section() -> None:
    _section_label("RECENT LOGS (LAST 20)")
    logs = _fetch_logs(limit=20)
    if not logs:
        st.caption("기록된 감사 이벤트가 없습니다.")
        return
    for ev in logs:
        cols = st.columns([2, 1, 1, 4, 2])
        try:
            ts = datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00"))
            ts_str = ts.strftime("%m-%d %H:%M:%S")
        except (KeyError, ValueError):
            ts_str = ev.get("created_at", "")[:19]
        cols[0].markdown(
            f'<span class="data-cell" style="color:#5C5D63;">{ts_str}</span>',
            unsafe_allow_html=True,
        )
        cols[1].markdown(
            _chip(ev["action"], ACTION_COLORS.get(ev["action"], "#8B8B93")),
            unsafe_allow_html=True,
        )
        cols[2].markdown(
            f'<span class="data-cell">{ev["source"]}</span>',
            unsafe_allow_html=True,
        )
        words = ", ".join(ev.get("detected_words", [])) or "—"
        cols[3].markdown(
            f'<span class="data-cell">{words}</span>',
            unsafe_allow_html=True,
        )
        cols[4].markdown(
            f'<span class="data-cell" style="color:#8B8B93;">'
            f'{ev.get("user_email") or "system"}</span>',
            unsafe_allow_html=True,
        )


def main() -> None:
    _inject_design_tokens()
    user = _require_admin()

    st.title("Moderation Admin")
    st.caption(
        f"signed in as **{user.get('email', '?')}** · role=`{user.get('role', '?')}` · "
        f"access=`{user.get('access_level', '?')}`"
    )

    tab_rules, tab_test, tab_logs = st.tabs(["Rules", "Test panel", "Audit logs"])
    with tab_rules:
        _render_rules_section()
    with tab_test:
        _render_test_panel()
    with tab_logs:
        _render_logs_section()


main()
