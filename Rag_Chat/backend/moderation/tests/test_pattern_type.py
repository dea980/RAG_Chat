"""C5 — ForbiddenWord supports two pattern types: KW (literal) and RE (regex).

KW preserves existing behavior — case-insensitive substring match.
RE compiles `word` as a Python regex and uses `re.search` per chunk of text.
Invalid regex must be tolerated (logger.warning, rule skipped) — one bad
operator entry should never crash the filter for every request.
"""
from __future__ import annotations

import logging

from django.test import TestCase

from moderation.filter import apply as moderate_text, BlockedByModerationError
from moderation.models import ForbiddenWord, ModerationLog


class PatternTypeFieldTest(TestCase):
    def test_pattern_type_choices_exist(self):
        self.assertEqual(ForbiddenWord.PatternType.KW, "KW")
        self.assertEqual(ForbiddenWord.PatternType.RE, "RE")

    def test_default_pattern_type_is_keyword(self):
        rule = ForbiddenWord.objects.create(
            word="새규칙", category="대외비",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.BOTH,
        )
        self.assertEqual(rule.pattern_type, "KW")


class KeywordRulePreservedTest(TestCase):
    def test_kw_rule_still_substring_matches(self):
        ForbiddenWord.objects.create(
            word="대외비", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.BOTH,
            pattern_type=ForbiddenWord.PatternType.KW,
        )
        with self.assertRaises(BlockedByModerationError):
            moderate_text("이건 대외비 자료", source=ModerationLog.Source.INBOUND)


class RegexRuleTest(TestCase):
    def test_regex_rule_matches_pattern(self):
        ForbiddenWord.objects.create(
            word=r"\d{6}-\d{7}", category="PII",
            severity=ForbiddenWord.Severity.MASK,
            direction=ForbiddenWord.Direction.OUTBOUND,
            mask_replacement="[주민번호REDACTED]",
            pattern_type=ForbiddenWord.PatternType.RE,
        )
        result = moderate_text("내 번호는 900101-1234567 입니다", source=ModerationLog.Source.OUTBOUND)
        self.assertIn("[주민번호REDACTED]", result.sanitized)
        self.assertNotIn("900101-1234567", result.sanitized)

    def test_regex_rule_block_severity(self):
        ForbiddenWord.objects.create(
            word=r"secret-\d+", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.BOTH,
            pattern_type=ForbiddenWord.PatternType.RE,
        )
        with self.assertRaises(BlockedByModerationError):
            moderate_text("token secret-4471 leaked", source=ModerationLog.Source.OUTBOUND)

    def test_regex_rule_no_false_match_on_literal_metacharacter(self):
        """KW=`\\d+` should match literal substring, RE=`\\d+` should match digits."""
        ForbiddenWord.objects.create(
            word=r"\d+", category="literal",
            severity=ForbiddenWord.Severity.WARNING,
            direction=ForbiddenWord.Direction.BOTH,
            pattern_type=ForbiddenWord.PatternType.KW,
        )
        # KW rule with metachar text should NOT match a string with digits but no literal "\d+"
        result = moderate_text("number 12345 here", source=ModerationLog.Source.INBOUND)
        self.assertEqual(result.warned_words, [])

    def test_regex_rule_invalid_pattern_skipped(self):
        """Bad regex from operator must NOT crash filter for whole request."""
        # `[` is an invalid regex (unterminated set).
        ForbiddenWord.objects.create(
            word=r"[unclosed", category="busted",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.BOTH,
            pattern_type=ForbiddenWord.PatternType.RE,
        )
        ForbiddenWord.objects.create(
            word="대외비", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.BOTH,
            pattern_type=ForbiddenWord.PatternType.KW,
        )
        # The invalid regex is silently skipped — the good KW rule still fires.
        with self.assertLogs("moderation.filter", level=logging.WARNING):
            with self.assertRaises(BlockedByModerationError):
                moderate_text("문서: 대외비", source=ModerationLog.Source.INBOUND)
