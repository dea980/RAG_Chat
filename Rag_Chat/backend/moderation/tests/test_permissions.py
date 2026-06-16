"""B6 — RBAC custom permission classes.

`IsModerationAdmin` 은 role=ADMIN 만 통과시킨다 (운영자 검수 UI / rule CRUD).
`IsManager`       은 role MANAGER 또는 ADMIN 을 통과시킨다 (감사 로그 열람 등).

DRF BasePermission 계약:
- `has_permission(request, view)` 가 bool 을 반환
- 익명 사용자, 비활성 사용자, 권한 부족 사용자는 모두 False
"""
from __future__ import annotations

from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from chat.models import User


class _PermissionTestBase(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.view = MagicMock()

    def _req(self, user):
        req = self.factory.get("/dummy/")
        req.user = user
        return req

    def _user(self, role: str, is_active: bool = True, email: str | None = None) -> User:
        email = email or f"{role.lower()}@triplechat.test"
        return User.objects.create_user(
            email=email, password="Triple!23", role=role, is_active=is_active
        )


class IsModerationAdminTest(_PermissionTestBase):
    def test_anonymous_denied(self):
        from moderation.permissions import IsModerationAdmin
        req = self._req(AnonymousUser())
        self.assertFalse(IsModerationAdmin().has_permission(req, self.view))

    def test_user_role_denied(self):
        from moderation.permissions import IsModerationAdmin
        u = self._user(User.Role.USER)
        self.assertFalse(IsModerationAdmin().has_permission(self._req(u), self.view))

    def test_manager_role_denied(self):
        from moderation.permissions import IsModerationAdmin
        u = self._user(User.Role.MANAGER)
        self.assertFalse(IsModerationAdmin().has_permission(self._req(u), self.view))

    def test_admin_role_allowed(self):
        from moderation.permissions import IsModerationAdmin
        u = self._user(User.Role.ADMIN)
        self.assertTrue(IsModerationAdmin().has_permission(self._req(u), self.view))

    def test_inactive_admin_denied(self):
        from moderation.permissions import IsModerationAdmin
        u = self._user(User.Role.ADMIN, is_active=False)
        self.assertFalse(IsModerationAdmin().has_permission(self._req(u), self.view))


class IsManagerTest(_PermissionTestBase):
    def test_anonymous_denied(self):
        from moderation.permissions import IsManager
        req = self._req(AnonymousUser())
        self.assertFalse(IsManager().has_permission(req, self.view))

    def test_user_role_denied(self):
        from moderation.permissions import IsManager
        u = self._user(User.Role.USER)
        self.assertFalse(IsManager().has_permission(self._req(u), self.view))

    def test_manager_role_allowed(self):
        from moderation.permissions import IsManager
        u = self._user(User.Role.MANAGER)
        self.assertTrue(IsManager().has_permission(self._req(u), self.view))

    def test_admin_role_allowed_via_inheritance(self):
        """ADMIN implies MANAGER — admin can do anything a manager can."""
        from moderation.permissions import IsManager
        u = self._user(User.Role.ADMIN)
        self.assertTrue(IsManager().has_permission(self._req(u), self.view))

    def test_inactive_manager_denied(self):
        from moderation.permissions import IsManager
        u = self._user(User.Role.MANAGER, is_active=False)
        self.assertFalse(IsManager().has_permission(self._req(u), self.view))
