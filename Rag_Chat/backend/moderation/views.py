"""Moderation REST endpoints (Phase B6 — operator surface).

`ForbiddenWordViewSet` 은 ADMIN 만 통과 (rule CRUD).
`ModerationLogViewSet` 은 MANAGER 이상 통과, read-only.

Why two viewsets? CLAUDE.md 의 4경계 보안 요구사항 중 "관리자가 코드 없이
튜닝" 을 만족시키려면 rule 수정 (write) 과 감사 (read) 의 권한이 분리되어야
한다. 부서장은 사고가 났을 때 자기 부서 사용자의 로그를 조회해야 하지만,
필터 자체를 바꿀 권한은 운영자에게만 둔다.
"""
from __future__ import annotations

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import ForbiddenWord, ModerationLog
from .permissions import IsManager, IsModerationAdmin
from .serializers import ForbiddenWordSerializer, ModerationLogSerializer


class ForbiddenWordViewSet(viewsets.ModelViewSet):
    queryset = ForbiddenWord.objects.all().order_by("-updated_at")
    serializer_class = ForbiddenWordSerializer
    permission_classes = [IsAuthenticated, IsModerationAdmin]


class ModerationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ModerationLog.objects.all().order_by("-created_at")
    serializer_class = ModerationLogSerializer
    permission_classes = [IsAuthenticated, IsManager]
