"""B6 — wire IsModerationAdmin into a real DRF endpoint.

`/api/v1/triple/moderation/rules/` 는 ForbiddenWord CRUD endpoint.
관리자만 GET/POST 가능. MANAGER 와 USER 는 403, 익명은 403 (DRF session auth).
"""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from chat.models import User
from moderation.models import ForbiddenWord


class ModerationRuleEndpointTest(TestCase):
    RULE_URL = "/api/v1/triple/moderation/rules/"

    def setUp(self) -> None:
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin.b6@triplechat.test", password="Triple!23", role=User.Role.ADMIN
        )
        self.manager = User.objects.create_user(
            email="manager.b6@triplechat.test", password="Triple!23", role=User.Role.MANAGER
        )
        self.user = User.objects.create_user(
            email="user.b6@triplechat.test", password="Triple!23", role=User.Role.USER
        )

    def _login(self, email: str) -> None:
        ok = self.client.login(username=email, password="Triple!23")
        self.assertTrue(ok, f"login failed for {email}")

    def test_anonymous_blocked(self):
        resp = self.client.get(self.RULE_URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_regular_user_blocked(self):
        self._login("user.b6@triplechat.test")
        resp = self.client.get(self.RULE_URL)
        self.assertEqual(resp.status_code, 403)

    def test_manager_blocked_from_rules(self):
        """MANAGER 도 rule 자체는 수정 못함 — 로그 열람만 허용."""
        self._login("manager.b6@triplechat.test")
        resp = self.client.get(self.RULE_URL)
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_list(self):
        ForbiddenWord.objects.create(word="시크릿", category="기밀")
        self._login("admin.b6@triplechat.test")
        resp = self.client.get(self.RULE_URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        items = body["results"] if isinstance(body, dict) else body
        self.assertIn("시크릿", [item["word"] for item in items])

    def test_admin_can_create(self):
        self._login("admin.b6@triplechat.test")
        resp = self.client.post(
            self.RULE_URL,
            {"word": "대외비", "category": "기밀", "severity": "BLOCK"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(ForbiddenWord.objects.filter(word="대외비").exists())


class ModerationLogEndpointTest(TestCase):
    """`/moderation/logs/` 는 MANAGER 이상 열람. 쓰기는 막힌다 (read-only)."""

    LOG_URL = "/api/v1/triple/moderation/logs/"

    def setUp(self) -> None:
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin.b6log@triplechat.test", password="Triple!23", role=User.Role.ADMIN
        )
        self.manager = User.objects.create_user(
            email="manager.b6log@triplechat.test", password="Triple!23", role=User.Role.MANAGER
        )
        self.user = User.objects.create_user(
            email="user.b6log@triplechat.test", password="Triple!23", role=User.Role.USER
        )

    def _login(self, email: str) -> None:
        self.assertTrue(self.client.login(username=email, password="Triple!23"))

    def test_user_blocked(self):
        self._login("user.b6log@triplechat.test")
        resp = self.client.get(self.LOG_URL)
        self.assertEqual(resp.status_code, 403)

    def test_manager_can_read(self):
        self._login("manager.b6log@triplechat.test")
        resp = self.client.get(self.LOG_URL)
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_read(self):
        self._login("admin.b6log@triplechat.test")
        resp = self.client.get(self.LOG_URL)
        self.assertEqual(resp.status_code, 200)

    def test_manager_cannot_write(self):
        self._login("manager.b6log@triplechat.test")
        resp = self.client.post(
            self.LOG_URL, {"action": "BLOCKED", "source": "INBOUND"},
            content_type="application/json",
        )
        # ViewSet that exposes only list/retrieve → 405 Method Not Allowed
        self.assertIn(resp.status_code, (403, 405))
