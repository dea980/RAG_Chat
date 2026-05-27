"""Token comparison API for the Token Lab page."""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .token_utils import analyze_text, language_sample_comparison

logger = logging.getLogger(__name__)


class TokenEstimateAPIView(APIView):
    """Compare token usage across model profiles."""

    permission_classes = [AllowAny]

    def post(self, request):
        text = (request.data.get("text") or "").strip()
        include_samples = request.data.get("include_samples", True)

        if not text:
            return Response(
                {"error": "text 값이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = {"analysis": analyze_text(text)}
            if include_samples:
                payload["language_samples"] = language_sample_comparison()
            return Response(payload, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.error("TokenEstimateAPIView failed: %r", exc, exc_info=True)
            return Response(
                {"error": "토큰 계산 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
