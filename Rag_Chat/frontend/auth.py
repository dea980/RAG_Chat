"""Frontend auth — session-based login against /api/v1/triple/auth/*.

Streamlit reruns the script on every interaction, so we keep the
`requests.Session` (which holds the Django sessionid cookie) in
`st.session_state` so it survives reruns.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests
import streamlit as st

logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"


def _ensure_session() -> requests.Session:
    """Get-or-create the shared `requests.Session` for this Streamlit user."""
    sess = st.session_state.get("auth_session")
    if sess is None:
        sess = requests.Session()
        st.session_state["auth_session"] = sess
    return sess


def get_session() -> requests.Session:
    return _ensure_session()


def is_authenticated() -> bool:
    return bool(st.session_state.get("auth_user"))


def current_user() -> Optional[dict]:
    return st.session_state.get("auth_user")


def login(email: str, password: str) -> tuple[bool, str]:
    """POST /auth/login/. Returns (ok, message)."""
    sess = _ensure_session()
    try:
        resp = sess.post(
            f"{API_BASE_URL}/auth/login/",
            json={"email": email, "password": password},
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.exception("login network error")
        return False, f"network error: {exc}"

    if resp.status_code == 200:
        user = resp.json()
        st.session_state["auth_user"] = user
        st.session_state["user_id"] = user["user_id"]
        return True, "ok"
    if resp.status_code == 401:
        return False, "invalid credentials"
    return False, f"login failed: HTTP {resp.status_code}"


def logout() -> None:
    sess = _ensure_session()
    try:
        sess.post(f"{API_BASE_URL}/auth/logout/", timeout=5)
    except requests.RequestException:
        logger.exception("logout request failed (forcing local clear)")
    for key in ("auth_user", "user_id", "messages"):
        st.session_state.pop(key, None)
    # Drop the session cookie too.
    st.session_state["auth_session"] = requests.Session()


def render_login_form() -> None:
    """Inline login form. Renders inside the current container."""
    st.subheader("Sign in")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", value="user.internal@triplechat.test")
        password = st.text_input("Password", type="password", value="Triple!23")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        ok, msg = login(email, password)
        if ok:
            st.success(f"Signed in as {email}")
            st.rerun()
        else:
            st.error(msg)


def render_user_chip(container=None) -> None:
    """Sidebar chip showing the logged-in user + role + access_level + logout."""
    target = container or st.sidebar
    user = current_user()
    if not user:
        target.warning("Not signed in")
        return
    target.markdown(
        f"**{user['email']}**\n\n"
        f"`role`: {user['role']} · `access`: {user['access_level']}"
    )
    if target.button("Sign out", key="auth_logout_btn"):
        logout()
        st.rerun()
