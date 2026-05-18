"""Single middleware that records every API call to AuditLog.

Excludes the healthcheck and Django admin assets to keep noise low.
The user_id is taken from the request body / query string — we don't have
full JWT yet so we attribute by the same session token the chat API uses.
"""
from __future__ import annotations

import logging
from typing import Optional

from .models import AuditLog

logger = logging.getLogger(__name__)

_EXCLUDED_PREFIXES = (
    "/static/",
    "/admin/jsi18n/",
    "/api/v1/triple/health",
)
_AUDITED_PREFIXES = (
    "/api/v1/triple/",
    "/api/v1/knowledge/",
    "/admin/",
)


def _extract_user_id(request) -> Optional[str]:
    # Forms / JSON / query string — same convention the chat views use.
    if hasattr(request, "data") and isinstance(getattr(request, "data", None), dict):
        uid = request.data.get("user_id")
        if uid:
            return str(uid)
    uid = request.POST.get("user_id") or request.GET.get("user_id")
    return str(uid) if uid else None


def _resolve_user(user_id: Optional[str]):
    if not user_id:
        return None
    try:
        from chat.models import User
        return User.objects.filter(user_id=user_id).first()
    except Exception:  # pragma: no cover - defensive
        return None


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if path.startswith(_EXCLUDED_PREFIXES):
            return response
        if not any(path.startswith(p) for p in _AUDITED_PREFIXES):
            return response
        try:
            AuditLog.objects.create(
                user=_resolve_user(_extract_user_id(request)),
                action=f"http.{request.method.lower()}",
                method=request.method,
                path=path[:255],
                status_code=response.status_code,
                ip_address=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            )
        except Exception as exc:  # never break the request because of audit
            logger.warning("AuditLog write failed: %s", exc)
        return response


def _client_ip(request) -> Optional[str]:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
