"""C7 — block response must include next_steps per CLAUDE.md refusal pattern.

CLAUDE.md says:
  "거절·차단 시각 패턴은 빨강 배너 금지. warning border + 사유 + 다음 단계."

The backend has to supply the "다음 단계" array. Each blocked category maps
to a concrete action the user can take. Without this, the chat just says
"blocked" and the user has no path forward — the rule becomes a dead end.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from chat.models import User
from moderation.models import ForbiddenWord


class NextStepsHelperTest(TestCase):
    def test_confidential_category_maps_to_access_request(self):
        from moderation.messages import next_steps_for
        steps = next_steps_for(["대외비"])
        self.assertTrue(
            any("권한" in s or "공개 신청" in s for s in steps),
            f"expected access-request step, got {steps}",
        )

    def test_pii_category_maps_to_redact_advice(self):
        from moderation.messages import next_steps_for
        steps = next_steps_for(["PII"])
        self.assertTrue(any("개인정보" in s for s in steps), steps)

    def test_profanity_category_maps_to_rephrase(self):
        from moderation.messages import next_steps_for
        steps = next_steps_for(["욕설"])
        self.assertTrue(any("표현" in s or "다시" in s for s in steps), steps)

    def test_competitor_category_maps_to_sales_followup(self):
        from moderation.messages import next_steps_for
        steps = next_steps_for(["경쟁사"])
        self.assertTrue(any("영업" in s for s in steps), steps)

    def test_unknown_category_falls_back_to_admin(self):
        from moderation.messages import next_steps_for
        steps = next_steps_for(["완전모르는카테고리"])
        self.assertTrue(any("관리자" in s or "운영자" in s for s in steps), steps)

    def test_multiple_categories_returns_all(self):
        from moderation.messages import next_steps_for
        steps = next_steps_for(["대외비", "PII"])
        self.assertGreaterEqual(len(steps), 2)


class BlockedExceptionCarriesCategoriesTest(TestCase):
    """filter.apply must pass categories along with words on BLOCK."""

    def test_block_exception_has_categories(self):
        from moderation.filter import apply as moderate_text, BlockedByModerationError
        from moderation.models import ModerationLog
        ForbiddenWord.objects.create(
            word="기밀", category="대외비",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.BOTH,
        )
        with self.assertRaises(BlockedByModerationError) as ctx:
            moderate_text("기밀자료입니다", source=ModerationLog.Source.INBOUND)
        self.assertEqual(ctx.exception.categories, ["대외비"])


class ChatBlockResponseShapeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ns@triplechat.test", password="Triple!23",
            role=User.Role.USER, access_level="internal",
        )
        ForbiddenWord.objects.create(
            word="대외비", category="대외비",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.BOTH,
        )
        self.client.post(
            "/api/v1/triple/auth/login/",
            {"email": "ns@triplechat.test", "password": "Triple!23"},
            content_type="application/json",
        )

    def test_block_response_includes_next_steps(self):
        resp = self.client.post(
            "/api/v1/triple/chat/",
            {"question": "대외비 문서 알려줘"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertIn("next_steps", body)
        self.assertIsInstance(body["next_steps"], list)
        self.assertTrue(len(body["next_steps"]) >= 1)
        self.assertIn("categories", body)
        self.assertEqual(body["categories"], ["대외비"])
