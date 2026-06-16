"""C1.2 — keyword filter applied to retrieval boundary.

After Layer-2 sensitivity ACL passes a chunk, scan its page_content against
OUTBOUND/BOTH rules:
- BLOCK → drop chunk + bump redacted_count + log ModerationLog
- MASK  → rewrite chunk.page_content in place
- WARN  → log only

The retrieval-side ribbon (`[수정됨·N건]`) must count keyword drops AND
sensitivity drops in the same bucket so users see a single number.
"""
from __future__ import annotations

from django.test import TestCase

from moderation.models import ForbiddenWord, ModerationLog


class _Doc:
    def __init__(self, content: str, metadata: dict | None = None):
        self.page_content = content
        self.metadata = metadata or {}


class RetrievalKeywordFilterTest(TestCase):
    def test_block_keyword_drops_chunk_and_bumps_redacted(self):
        ForbiddenWord.objects.create(
            word="대외비", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.OUTBOUND,
        )
        from chat.utils import RAGUtils
        docs = [
            _Doc("clean text", {"sensitivity": "public"}),
            _Doc("이건 대외비 문서다", {"sensitivity": "public"}),
        ]
        out = RAGUtils.process_search_results(docs, user_access_level="internal")
        self.assertEqual(out["redacted_count"], 1)
        self.assertNotIn("대외비", out["context"])
        self.assertIn("clean text", out["context"])

    def test_mask_keyword_rewrites_chunk_content(self):
        ForbiddenWord.objects.create(
            word="secret", category="비밀",
            severity=ForbiddenWord.Severity.MASK,
            direction=ForbiddenWord.Direction.OUTBOUND,
            mask_replacement="[REDACTED]",
        )
        from chat.utils import RAGUtils
        docs = [_Doc("the secret is out", {"sensitivity": "public"})]
        out = RAGUtils.process_search_results(docs, user_access_level="internal")
        self.assertIn("[REDACTED]", out["context"])
        self.assertNotIn("secret", out["context"])
        self.assertEqual(out["redacted_count"], 0)  # mask doesn't drop, only rewrites

    def test_acl_and_keyword_drops_sum_into_one_count(self):
        ForbiddenWord.objects.create(
            word="leak", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.OUTBOUND,
        )
        from chat.utils import RAGUtils
        docs = [
            _Doc("public ok", {"sensitivity": "public"}),
            _Doc("internal-only secret", {"sensitivity": "confidential"}),  # ACL drop
            _Doc("leak detected", {"sensitivity": "public"}),                # keyword drop
        ]
        out = RAGUtils.process_search_results(docs, user_access_level="internal")
        self.assertEqual(out["redacted_count"], 2)
        self.assertIn("public ok", out["context"])
        self.assertNotIn("leak", out["context"])
        self.assertNotIn("internal-only", out["context"])

    def test_inbound_only_rule_does_not_fire_on_retrieval(self):
        """If a rule is direction=INBOUND, retrieval text must NOT be affected."""
        ForbiddenWord.objects.create(
            word="질문어", category="입력",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.INBOUND,
        )
        from chat.utils import RAGUtils
        docs = [_Doc("질문어 포함 결과", {"sensitivity": "public"})]
        out = RAGUtils.process_search_results(docs, user_access_level="internal")
        self.assertEqual(out["redacted_count"], 0)
        self.assertIn("질문어", out["context"])

    def test_block_keyword_creates_audit_log(self):
        ForbiddenWord.objects.create(
            word="유출", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.OUTBOUND,
        )
        from chat.utils import RAGUtils
        docs = [_Doc("내부 유출 사고", {"sensitivity": "public"})]
        RAGUtils.process_search_results(docs, user_access_level="internal")
        log = ModerationLog.objects.filter(
            action=ModerationLog.Action.BLOCKED,
            source=ModerationLog.Source.RETRIEVAL,
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("유출", log.detected_words)
