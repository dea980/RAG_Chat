"""HTTP client for the new conversation/message endpoints.

Wraps:
  GET    /conversations/                 list_conversations()
  POST   /conversations/                 create_conversation(title)
  GET    /conversations/<id>/            get_conversation(conv_id)
  DELETE /conversations/<id>/            delete_conversation(conv_id)
  POST   /messages/                      send_message(text, conv_id, files, ingest)

All calls reuse `auth.get_session()` so the Django session cookie + CSRF token
are shared with the rest of the app.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

import auth as auth_mod

logger = logging.getLogger(__name__)

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/triple"
CONV_URL = f"{API_BASE}/conversations/"
MSG_URL = f"{API_BASE}/messages/"


def _csrf_headers() -> dict[str, str]:
    sess = auth_mod.get_session()
    token = sess.cookies.get("csrftoken", "")
    return {"X-CSRFToken": token, "Referer": API_BASE}


def list_conversations(limit: int = 50) -> list[dict[str, Any]]:
    sess = auth_mod.get_session()
    try:
        r = sess.get(f"{CONV_URL}?limit={limit}", timeout=10)
        r.raise_for_status()
        return r.json().get("items", [])
    except requests.RequestException as exc:
        logger.error(f"list_conversations failed: {exc!r}")
        return []


def create_conversation(title: str = "") -> dict[str, Any] | None:
    sess = auth_mod.get_session()
    try:
        r = sess.post(
            CONV_URL,
            json={"title": title},
            headers={**_csrf_headers(), "Content-Type": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        logger.error(f"create_conversation failed: {exc!r}")
        return None


def get_conversation(conv_id: str) -> dict[str, Any] | None:
    sess = auth_mod.get_session()
    try:
        r = sess.get(f"{CONV_URL}{conv_id}/", timeout=10)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        logger.error(f"get_conversation failed: {exc!r}")
        return None


def delete_conversation(conv_id: str) -> bool:
    sess = auth_mod.get_session()
    try:
        r = sess.delete(
            f"{CONV_URL}{conv_id}/",
            headers=_csrf_headers(),
            timeout=10,
        )
        return r.status_code in (204, 200)
    except requests.RequestException as exc:
        logger.error(f"delete_conversation failed: {exc!r}")
        return False


def send_message(
    text: str,
    conversation_id: str | None = None,
    files: list | None = None,
    ingest: bool = False,
    top_k: int = 5,
    use_reasoning: bool = False,
    history_turns: int = 5,
    timeout: int = 240,
) -> dict[str, Any] | None:
    """Multipart POST to /messages/. files = list of streamlit UploadedFile.

    Tunable knobs are forwarded to the backend as form fields:
        top_k          how many chunks to retrieve (1-20)
        use_reasoning  add the reasoning LLM call (slower, sometimes higher quality)
        history_turns  how many past user+assistant turn pairs to include as prefix
    """
    sess = auth_mod.get_session()
    data = {
        "text": text,
        "ingest": "1" if ingest else "0",
        "top_k": str(top_k),
        "use_reasoning": "1" if use_reasoning else "0",
        "history_turns": str(history_turns),
    }
    if conversation_id:
        data["conversation_id"] = conversation_id
    multipart_files = [
        ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
        for f in (files or [])
    ]
    try:
        r = sess.post(
            MSG_URL,
            data=data,
            files=multipart_files or None,
            headers=_csrf_headers(),
            timeout=timeout,
        )
        if r.status_code == 403:
            j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if "blocked_words" in j or "categories" in j:
                j["blocked"] = True
                return j
            logger.error(f"messages 403 (non-mod): {j}")
            return None
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        logger.error(f"send_message failed: {exc!r}")
        return None
