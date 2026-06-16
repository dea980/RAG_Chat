"""C1.1 — filter.apply must support UPLOAD + RETRIEVAL sources.

ForbiddenWord.direction values stay INBOUND/OUTBOUND/BOTH. The Source enum
gains UPLOAD/RETRIEVAL so audit logs can distinguish which boundary tripped
the rule. filter.apply maps:
  INBOUND, UPLOAD       → match INBOUND + BOTH rules
  OUTBOUND, RETRIEVAL   → match OUTBOUND + BOTH rules
"""
from __future__ import annotations

from django.test import TestCase

from moderation.filter import apply as moderate_text, BlockedByModerationError
from moderation.models import ForbiddenWord, ModerationLog


class SourceEnumTest(TestCase):
    def test_upload_source_exists(self):
        self.assertEqual(ModerationLog.Source.UPLOAD, "UPLOAD")

    def test_retrieval_source_exists(self):
        self.assertEqual(ModerationLog.Source.RETRIEVAL, "RETRIEVAL")


class UploadSourceDirectionTest(TestCase):
    def setUp(self):
        ForbiddenWord.objects.create(
            word="시크릿", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.INBOUND,
        )

    def test_upload_blocks_via_inbound_rule(self):
        with self.assertRaises(BlockedByModerationError):
            moderate_text("시크릿 문서", source=ModerationLog.Source.UPLOAD)

    def test_upload_ignores_outbound_only_rule(self):
        ForbiddenWord.objects.create(
            word="대외비", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.OUTBOUND,
        )
        result = moderate_text("대외비 문서", source=ModerationLog.Source.UPLOAD)
        self.assertFalse(result.blocked_words)


class RetrievalSourceDirectionTest(TestCase):
    def setUp(self):
        ForbiddenWord.objects.create(
            word="leak", category="기밀",
            severity=ForbiddenWord.Severity.MASK,
            direction=ForbiddenWord.Direction.OUTBOUND,
            mask_replacement="[REDACTED]",
        )

    def test_retrieval_masks_via_outbound_rule(self):
        result = moderate_text("the leak surfaced", source=ModerationLog.Source.RETRIEVAL)
        self.assertEqual(result.sanitized, "the [REDACTED] surfaced")
        self.assertEqual(result.masked_words, ["leak"])

    def test_retrieval_ignores_inbound_only_rule(self):
        ForbiddenWord.objects.create(
            word="질문", category="입력만",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.INBOUND,
        )
        result = moderate_text("질문 결과", source=ModerationLog.Source.RETRIEVAL)
        self.assertFalse(result.blocked_words)


class BothDirectionAppliesEverywhereTest(TestCase):
    def test_both_rule_hits_all_sources(self):
        ForbiddenWord.objects.create(
            word="모든곳", category="all",
            severity=ForbiddenWord.Severity.WARNING,
            direction=ForbiddenWord.Direction.BOTH,
        )
        for source in [
            ModerationLog.Source.INBOUND,
            ModerationLog.Source.OUTBOUND,
            ModerationLog.Source.UPLOAD,
            ModerationLog.Source.RETRIEVAL,
        ]:
            result = moderate_text("모든곳 텍스트", source=source)
            self.assertEqual(result.warned_words, ["모든곳"], f"source={source} missed BOTH rule")
