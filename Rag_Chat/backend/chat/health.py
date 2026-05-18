"""
Health & readiness endpoints.

- /api/v1/triple/health/         lightweight liveness probe (no deps touched)
- /api/v1/triple/health/ready/   readiness probe (DB + Redis + provider config)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict

from django.db import connections
from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .redis_manager import RedisConnectionManager

logger = logging.getLogger(__name__)


def _check_database() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        connections["default"].cursor().execute("SELECT 1")
        return {
            "ok": True,
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "engine": connections["default"].settings_dict.get("ENGINE", ""),
        }
    except OperationalError as exc:
        return {"ok": False, "error": str(exc)}


def _check_redis() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        client = RedisConnectionManager.get_instance().get_connection()
        client.ping()
        return {
            "ok": True,
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_provider() -> Dict[str, Any]:
    try:
        from .providers import provider_manager
        return {
            "ok": True,
            "embedding": getattr(provider_manager, "embedding_provider_name", "unknown"),
            "reasoning": getattr(provider_manager, "reasoning_provider_name", "unknown"),
            "generation": getattr(provider_manager, "generation_provider_name", "unknown"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


class LivenessView(APIView):
    """Cheap probe — true if Django is serving."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class ReadinessView(APIView):
    """
    Full dependency probe.
    Returns 503 if DB or Redis is unreachable; provider config issues only warn.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        db = _check_database()
        redis_info = _check_redis()
        provider = _check_provider()

        critical_ok = db["ok"] and redis_info["ok"]
        payload = {
            "status": "ready" if critical_ok else "degraded",
            "checks": {
                "database": db,
                "redis": redis_info,
                "provider": provider,
            },
        }
        http_status = status.HTTP_200_OK if critical_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        if not critical_ok:
            logger.warning("Readiness check failed: %s", payload["checks"])
        return Response(payload, status=http_status)
