"""C2.1 — POST /api/v1/triple/moderation/test/ — dry-run filter against text.

Operator-only endpoint that drives the "real-time test panel" in the
Streamlit admin UI. Same filter.apply pipeline, but the result is returned
to the operator instead of being applied to user traffic. No ModerationLog
is written (test runs should not pollute the audit log).
"""
from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from chat.models import User
from moderation.models import ForbiddenWord, ModerationLog


class ModerationTestEndpointTest(TestCase):
    URL = "/api/v1/triple/moderation/test/"

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin.test@triplechat.test", password="Triple!23", role=User.Role.ADMIN
        )
        self.user = User.objects.create_user(
            email="user.test@triplechat.test", password="Triple!23", role=User.Role.USER
        )
        ForbiddenWord.objects.create(
            word="대외비", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.BOTH,
        )
        ForbiddenWord.objects.create(
            word="secret", category="비밀",
            severity=ForbiddenWord.Severity.MASK,
            direction=ForbiddenWord.Direction.BOTH,
            mask_replacement="[REDACTED]",
        )

    def _login(self, email):
        self.assertTrue(self.client.login(username=email, password="Triple!23"))

    def test_anonymous_blocked(self):
        resp = self.client.post(self.URL, {"text": "hi", "source": "INBOUND"}, format="json")
        self.assertIn(resp.status_code, (401, 403))

    def test_regular_user_blocked(self):
        self._login("user.test@triplechat.test")
        resp = self.client.post(self.URL, {"text": "hi", "source": "INBOUND"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_admin_block_response(self):
        self._login("admin.test@triplechat.test")
        resp = self.client.post(self.URL, {"text": "대외비 자료", "source": "INBOUND"}, format="json")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["action"], "BLOCKED")
        self.assertIn("대외비", body["blocked_words"])
        self.assertEqual(body["sanitized"], "")

    def test_admin_mask_response(self):
        self._login("admin.test@triplechat.test")
        resp = self.client.post(self.URL, {"text": "the secret is out", "source": "OUTBOUND"}, format="json")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["action"], "MASKED")
        self.assertEqual(body["sanitized"], "the [REDACTED] is out")
        self.assertIn("secret", body["masked_words"])

    def test_admin_clean_response(self):
        self._login("admin.test@triplechat.test")
        resp = self.client.post(self.URL, {"text": "nothing bad here", "source": "INBOUND"}, format="json")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["action"], "PASS")
        self.assertEqual(body["sanitized"], "nothing bad here")
        self.assertEqual(body["blocked_words"], [])

    def test_no_audit_log_written(self):
        self._login("admin.test@triplechat.test")
        before = ModerationLog.objects.count()
        self.client.post(self.URL, {"text": "대외비 자료", "source": "INBOUND"}, format="json")
        self.assertEqual(ModerationLog.objects.count(), before)

    def test_invalid_source_400(self):
        self._login("admin.test@triplechat.test")
        resp = self.client.post(self.URL, {"text": "hi", "source": "BANANA"}, format="json")
        self.assertEqual(resp.status_code, 400)
