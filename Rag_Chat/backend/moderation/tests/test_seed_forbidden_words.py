"""C4 — Phase A exit criterion: starter ForbiddenWord seed (>= 15 rows).

The seed is idempotent (running twice does not duplicate or wipe operator
edits). The starter set covers four categories the operator will see most
in the first quarter: 욕설 / 대외비 / PII / 경쟁사.
"""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from moderation.models import ForbiddenWord


class SeedForbiddenWordsTest(TestCase):
    def _run(self, **kwargs) -> str:
        out = StringIO()
        call_command("seed_forbidden_words", stdout=out, **kwargs)
        return out.getvalue()

    def test_seed_creates_at_least_15_rules(self):
        self._run()
        self.assertGreaterEqual(ForbiddenWord.objects.count(), 15)

    def test_seed_includes_regex_rules(self):
        """C5 — at least one starter rule must use pattern_type=RE for PII."""
        self._run()
        from moderation.models import ForbiddenWord as FW
        self.assertTrue(
            FW.objects.filter(pattern_type=FW.PatternType.RE, category="PII").exists(),
            "no regex PII rule seeded",
        )

    def test_seed_covers_four_categories(self):
        self._run()
        cats = set(ForbiddenWord.objects.values_list("category", flat=True))
        for required in ("욕설", "대외비", "PII", "경쟁사"):
            self.assertIn(required, cats, f"missing category: {required}")

    def test_seed_idempotent(self):
        """Running twice produces the same set — no duplicates."""
        self._run()
        count_first = ForbiddenWord.objects.count()
        self._run()
        count_second = ForbiddenWord.objects.count()
        self.assertEqual(count_first, count_second)

    def test_seed_preserves_operator_edits(self):
        """If operator marks a rule inactive, re-running seed must not flip it back."""
        self._run()
        rule = ForbiddenWord.objects.first()
        rule.is_active = False
        rule.note = "operator disabled this — keep off"
        rule.save()
        self._run()
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)
        self.assertEqual(rule.note, "operator disabled this — keep off")

    def test_seed_writes_summary(self):
        out = self._run()
        self.assertIn("seed_forbidden_words", out)
        self.assertIn("total=", out)
