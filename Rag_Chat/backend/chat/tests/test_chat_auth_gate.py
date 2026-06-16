"""B4 — ChatAPIView must require auth and read user from session, not payload.

- Anonymous → 401
- Authenticated → request.user.access_level flows into ModuleContext
- Client-supplied user_id in payload is ignored (no privilege escalation)
"""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase


class ChatAuthGateTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="gate@triplechat.test", password="Triple!23",
            access_level="confidential", role="MANAGER",
        )

    def _login(self):
        self.client.post(
            "/api/v1/triple/auth/login/",
            {"email": "gate@triplechat.test", "password": "Triple!23"},
            content_type="application/json",
        )

    def test_anonymous_chat_call_rejected(self):
        resp = self.client.post(
            "/api/v1/triple/chat/",
            {"question": "hello"},
            content_type="application/json",
        )
        # DRF session auth returns 403 for unauthenticated requests
        # (401 requires a WWW-Authenticate header from a token-style auth).
        self.assertIn(resp.status_code, (401, 403))

    def test_authenticated_chat_uses_session_user_access_level(self):
        self._login()
        with patch("chat.views.PipelineRunner.run") as run_mock, \
             patch("chat.views.moderate_text") as mod:
            # mock pipeline returns a basic context
            def _fake_run(ctx):
                ctx.context_text = "ctx"
                ctx.response = "ok"
                ctx.extra["rag_metadata"] = {"redacted_count": 2, "image_paths": []}
                self._captured_access_level = ctx.user_access_level
                return ctx
            run_mock.side_effect = _fake_run

            mod.return_value = type("R", (), {"sanitized": "hello"})()
            resp = self.client.post(
                "/api/v1/triple/chat/",
                {"question": "hello"},
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self._captured_access_level, "confidential")
        self.assertEqual(resp.json()["redacted_count"], 2)

    def test_payload_user_id_cannot_escalate(self):
        """Even if client puts another user_id in payload, session wins."""
        self._login()
        with patch("chat.views.PipelineRunner.run") as run_mock, \
             patch("chat.views.moderate_text") as mod:
            def _fake_run(ctx):
                ctx.context_text = "ctx"
                ctx.response = "ok"
                ctx.extra["rag_metadata"] = {"redacted_count": 0, "image_paths": []}
                self._captured_user_id = ctx.user_id
                self._captured_access_level = ctx.user_access_level
                return ctx
            run_mock.side_effect = _fake_run

            mod.return_value = type("R", (), {"sanitized": "hi"})()
            resp = self.client.post(
                "/api/v1/triple/chat/",
                {"question": "hi", "user_id": "U99999999999"},  # forged
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        # Session user wins, payload is ignored
        self.assertEqual(self._captured_user_id, self.user.user_id)
        self.assertEqual(self._captured_access_level, "confidential")
