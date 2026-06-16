"""Streamlit role gate — block pages by `auth_user.role`.

DESIGN.md 룰:
- 빨강 배너 금지. warning border (amber `#E89B3C`) + 사유 + 다음 단계.
- 미인증/권한미달 시 `st.stop()` 으로 페이지 본문 차단.

사용법 (각 page 최상단):
    from role_gate import require_role
    require_role(["MANAGER", "ADMIN"])   # 또는 require_admin() / require_manager()
"""
from __future__ import annotations

from typing import Iterable

import streamlit as st


ROLE_LABEL = {
    "USER":    "사원",
    "MANAGER": "부서장",
    "ADMIN":   "운영자",
}


def _current_role() -> str | None:
    user = st.session_state.get("auth_user")
    if not user:
        return None
    return user.get("role")


def _render_block(reason: str, next_steps: list[str]) -> None:
    steps_html = "".join(f"<li>{s}</li>" for s in next_steps)
    st.markdown(
        f"""
<div style="border-left:3px solid #E89B3C;background:#1a1208;
            padding:14px 18px;border-radius:0 8px 8px 0;color:#f0e6d2;
            font-family:Pretendard,system-ui,sans-serif;">
  <div style="font-size:13px;color:#E89B3C;font-weight:600;
              letter-spacing:0.04em;text-transform:uppercase;">접근 차단</div>
  <div style="margin-top:6px;font-size:14px;line-height:1.55;">{reason}</div>
  <div style="margin-top:10px;font-size:12px;color:#bfb295;">다음 단계</div>
  <ul style="margin:4px 0 0 18px;padding:0;font-size:13px;color:#e0d6bf;
             line-height:1.55;">{steps_html}</ul>
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar_chip() -> None:
    """Mirror app.py's render_user_chip — every gated page needs Sign out.

    Renders both the sidebar chip (collapsible) AND a top-bar Sign out so the
    affordance is visible even when the sidebar is hidden. Sub-pages and
    app.py never run together (each Streamlit page is a separate script),
    so duplicate widget keys can't collide across them.
    """
    try:
        import auth as _auth  # frontend/auth.py
        _auth.render_user_chip()
        _auth.render_topbar()
    except Exception:
        pass


def require_role(allowed: Iterable[str]) -> None:
    """Block render unless `auth_user.role in allowed`. `st.stop()` on deny.

    Also renders the auth chip (user + role + Sign out) in the sidebar so every
    sub-page has a logout affordance, not just app.py.
    """
    allowed_set = {r.upper() for r in allowed}
    role = _current_role()

    if role is None:
        _render_block(
            reason="로그인이 필요한 페이지입니다.",
            next_steps=[
                "메인 페이지(`app.py`)에서 사내 계정으로 로그인하세요.",
                "이미 로그인했는데 이 화면이 보이면 세션이 만료된 상태입니다 — 재로그인.",
            ],
        )
        st.stop()

    # Render Sign out chip in sidebar BEFORE gate-deny so denied users can still
    # log out and switch accounts without bouncing back to app.py.
    _render_sidebar_chip()

    if role not in allowed_set:
        allowed_labels = " / ".join(ROLE_LABEL.get(r, r) for r in sorted(allowed_set))
        _render_block(
            reason=(
                f"이 페이지는 **{allowed_labels}** 권한이 필요합니다. "
                f"현재 계정 권한: `{ROLE_LABEL.get(role, role)}` ({role})."
            ),
            next_steps=[
                "권한이 필요한 작업이면 운영자에게 요청하세요.",
                "다른 계정으로 전환하려면 사이드바의 `Sign out` 후 재로그인.",
            ],
        )
        st.stop()


def require_manager() -> None:
    """MANAGER + ADMIN 통과."""
    require_role(["MANAGER", "ADMIN"])


def require_admin() -> None:
    """ADMIN 만 통과."""
    require_role(["ADMIN"])
