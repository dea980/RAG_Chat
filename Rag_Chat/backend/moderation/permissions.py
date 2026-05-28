"""DRF permission classes for the moderation surface (Phase B — RBAC).

운영자 검수 UI (`/admin/moderation/`) 와 미래의 rule CRUD endpoint 는
인증 (IsAuthenticated) 만으로는 부족하다. 사내 사용자도 인증은 받지만
욕설 필터·대외비 패턴을 수정할 권한은 없다. role 컬럼 (`chat.User.role`)
을 게이트로 두어 코드 변경 없이 운영자만 통과시킨다.

계층:
- ADMIN  : 전사 운영자 (C-level / 보안 책임자) — rule CRUD, 감사 로그 검수
- MANAGER: 부서장 (감사 로그 열람 · 권한 위임 권장은 가능, rule 자체는 ADMIN)
- USER   : 일반 사원

`IsModerationAdmin` 은 ADMIN 만 통과시키고,
`IsManager` 는 ADMIN 과 MANAGER 둘 다 통과시킨다 (admin implies manager).
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from chat.models import User


def _has_role(request, allowed: set[str]) -> bool:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_active:
        return False
    return getattr(user, "role", None) in allowed


class IsModerationAdmin(BasePermission):
    """Allow only authenticated, active users with role=ADMIN."""

    message = "운영자 권한 (ADMIN) 이 필요합니다."

    def has_permission(self, request, view) -> bool:
        return _has_role(request, {User.Role.ADMIN})


class IsManager(BasePermission):
    """Allow authenticated, active users with role ADMIN or MANAGER.

    ADMIN > MANAGER 위계 — ADMIN 은 MANAGER 가 할 수 있는 모든 작업도 가능.
    """

    message = "부서장 (MANAGER) 이상 권한이 필요합니다."

    def has_permission(self, request, view) -> bool:
        return _has_role(request, {User.Role.ADMIN, User.Role.MANAGER})
