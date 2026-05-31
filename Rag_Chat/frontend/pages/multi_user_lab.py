"""Multi-User ACL Lab — N개 페르소나로 동시에 같은 질문을 던져 ACL 차이를 본다.

목적:
- public / internal / confidential / restricted access_level 별로
  동일 질문이 어떤 답·어떤 redacted_count 를 받는지 한 화면에 비교.
- 백엔드 변경 없음 — 각 페르소나마다 별도 `requests.Session()` 으로
  `/auth/login/` 한 뒤 `/chat/` 을 친다.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests
import streamlit as st

st.set_page_config(page_title="Multi-User ACL Lab", layout="wide")

import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from role_gate import require_admin  # noqa: E402
require_admin()

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"
LOGIN_URL = f"{API_BASE}/auth/login/"
CHAT_URL = f"{API_BASE}/chat/"

# Source of truth = backend/chat/management/commands/seed_test_users.py
PERSONAS: list[dict[str, str]] = [
    {"email": "user.public@triplechat.test",      "role": "USER",    "access_level": "public",       "label": "사원 (public)"},
    {"email": "user.internal@triplechat.test",    "role": "USER",    "access_level": "internal",     "label": "사원 (internal)"},
    {"email": "manager.sales@triplechat.test",    "role": "MANAGER", "access_level": "confidential", "label": "매니저 (영업)"},
    {"email": "manager.eng@triplechat.test",      "role": "MANAGER", "access_level": "confidential", "label": "매니저 (엔지니어링)"},
    {"email": "admin@triplechat.test",            "role": "ADMIN",   "access_level": "restricted",   "label": "관리자"},
    {"email": "moderation.admin@triplechat.test", "role": "ADMIN",   "access_level": "restricted",   "label": "모더레이션 관리자"},
]

SHARED_PASSWORD = "Triple!23"

LEVEL_COLOR = {
    "public":       "#5BB85B",
    "internal":     "#3C82E8",
    "confidential": "#E89B3C",
    "restricted":   "#D14A4A",
}
ROLE_COLOR = {"USER": "#777", "MANAGER": "#5C6BC0", "ADMIN": "#D14A4A"}


def _chip(text: str, color: str) -> str:
    return (
        f"<span style='background:{color};color:#fff;padding:2px 8px;"
        f"border-radius:10px;font-size:11px;font-family:Geist Mono,monospace;"
        f"font-variant-numeric:tabular-nums;'>{text}</span>"
    )


def run_persona(persona: dict, question: str) -> dict[str, Any]:
    sess = requests.Session()
    try:
        r = sess.post(
            LOGIN_URL,
            json={"email": persona["email"], "password": SHARED_PASSWORD},
            timeout=15,
        )
        if r.status_code != 200:
            return {"persona": persona, "error": f"login {r.status_code}: {r.text[:120]}"}

        # DRF SessionAuthentication enforces CSRF on non-safe methods.
        # Django sets `csrftoken` cookie on login; forward it as the header.
        csrf = sess.cookies.get("csrftoken", "")
        chat_headers = {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf,
            "Referer": API_BASE,
        }
        c = sess.post(CHAT_URL, json={"question": question}, headers=chat_headers, timeout=180)
        if c.status_code == 403:
            j = c.json() if c.headers.get("content-type", "").startswith("application/json") else {}
            return {
                "persona": persona,
                "blocked": True,
                "response": j.get("error", "blocked"),
                "blocked_words": j.get("blocked_words", []),
                "categories": j.get("categories", []),
                "next_steps": j.get("next_steps", []),
                "redacted_count": 0,
            }
        if c.status_code != 200:
            return {"persona": persona, "error": f"chat {c.status_code}: {c.text[:160]}"}

        j = c.json()
        return {
            "persona": persona,
            "response": j.get("response", ""),
            "redacted_count": j.get("redacted_count", 0),
            "chat_id": j.get("chat_id"),
        }
    except Exception as exc:
        return {"persona": persona, "error": repr(exc)}
    finally:
        try:
            sess.post(f"{API_BASE}/auth/logout/", timeout=5)
        except Exception:
            pass


st.title("🪪 Multi-User ACL Lab")
st.caption(
    "동일 질문을 N개 페르소나로 동시에 던져 access_level 별 응답·redacted_count 차이를 본다. "
    "백엔드는 그대로 — 페르소나마다 별도 세션 쿠키."
)

with st.sidebar:
    st.markdown("### 페르소나 선택")
    labels = [p["label"] for p in PERSONAS]
    default = [PERSONAS[0]["label"], PERSONAS[1]["label"], PERSONAS[4]["label"]]
    chosen_labels = st.multiselect("동시 호출할 사용자", labels, default=default)
    chosen = [p for p in PERSONAS if p["label"] in chosen_labels]

    st.markdown("---")
    st.markdown("### 설정")
    st.code(f"BACKEND={API_BASE}", language="bash")
    st.caption(f"공통 비밀번호: `{SHARED_PASSWORD}` (seed)")

st.markdown("### 질문")
question = st.text_area(
    "모든 페르소나가 동일하게 던질 질문",
    value="Galaxy S25 의 가격과 배터리 용량을 알려줘.",
    height=80,
)

go = st.button("▶ 동시 실행", type="primary", disabled=not chosen or not question.strip())

if go:
    with st.spinner(f"{len(chosen)} 페르소나 병렬 실행 중…"):
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(8, len(chosen))) as ex:
            futures = [ex.submit(run_persona, p, question.strip()) for p in chosen]
            for fut in as_completed(futures):
                results.append(fut.result())

    results.sort(key=lambda r: [p["email"] for p in chosen].index(r["persona"]["email"]))

    st.markdown("### 결과")
    cols = st.columns(len(results))
    for col, r in zip(cols, results):
        p = r["persona"]
        with col:
            st.markdown(
                f"**{p['label']}**  "
                f"{_chip(p['role'], ROLE_COLOR.get(p['role'], '#777'))} "
                f"{_chip(p['access_level'], LEVEL_COLOR.get(p['access_level'], '#777'))}",
                unsafe_allow_html=True,
            )
            st.caption(p["email"])

            if "error" in r:
                st.error(r["error"])
                continue

            if r.get("blocked"):
                st.warning("BLOCKED — moderation 차단")
                if r.get("blocked_words"):
                    st.markdown(
                        "**blocked_words:** "
                        + ", ".join(f"`{w}`" for w in r["blocked_words"])
                    )
                if r.get("next_steps"):
                    st.markdown("**next_steps:**")
                    for s in r["next_steps"]:
                        st.markdown(f"- {s}")
                continue

            redacted = r.get("redacted_count", 0)
            ribbon_color = "#E89B3C" if redacted > 0 else "#2A2D33"
            st.markdown(
                f"<div style='border-left:3px solid {ribbon_color};"
                f"padding:8px 12px;background:#0f1014;color:#e8e8ea;"
                f"border-radius:0 6px 6px 0;font-size:13px;line-height:1.55;"
                f"max-height:340px;overflow:auto;'>"
                f"{(r.get('response') or '').replace(chr(10), '<br>')}"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='margin-top:6px;font-family:Geist Mono,monospace;"
                f"font-size:11px;color:#888;font-variant-numeric:tabular-nums;'>"
                f"redacted_count = <b style='color:#E89B3C'>{redacted}</b> · "
                f"chat_id={str(r.get('chat_id') or '')[:8]}"
                f"</div>",
                unsafe_allow_html=True,
            )

    # Diff summary
    st.markdown("### 차이 요약")
    valid = [r for r in results if "error" not in r and not r.get("blocked")]
    if len(valid) >= 2:
        responses = {r["persona"]["email"]: r.get("response", "") for r in valid}
        redacts = {r["persona"]["email"]: r.get("redacted_count", 0) for r in valid}
        unique_resp = len({v.strip() for v in responses.values()})
        st.markdown(
            f"- 유효 응답: **{len(valid)}** · 고유 텍스트: **{unique_resp}**\n"
            f"- redacted_count 분포: `{redacts}`\n"
            f"- 모든 응답 동일? **{'예' if unique_resp == 1 else '아니오'}**"
        )
    else:
        st.caption("유효 응답이 2개 미만 — 차이 비교 생략.")
