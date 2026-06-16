"""Phase A — sensitivity ladder + retrieval ACL filter tests.

AclLevelTest 는 순수 헬퍼 함수만 검증한다. RetrievalAclTest 는 chunk metadata 의
sensitivity 와 User.access_level 을 받아 결과를 필터링하는 단위 함수
(apply_acl_filter) 를 검증한다 — vector store / HTTP 를 거치지 않아 빠르고 안정.
"""
from __future__ import annotations

from django.test import TestCase


class AclLevelTest(TestCase):
    def test_strict_ordering_internal(self):
        from moderation.levels import can_access
        self.assertTrue(can_access("internal", "public"))
        self.assertTrue(can_access("internal", "internal"))
        self.assertFalse(can_access("internal", "confidential"))
        self.assertFalse(can_access("internal", "restricted"))

    def test_public_user_only_public(self):
        from moderation.levels import can_access
        self.assertTrue(can_access("public", "public"))
        self.assertFalse(can_access("public", "internal"))

    def test_restricted_dominates(self):
        from moderation.levels import can_access
        self.assertTrue(can_access("restricted", "public"))
        self.assertTrue(can_access("restricted", "internal"))
        self.assertTrue(can_access("restricted", "confidential"))
        self.assertTrue(can_access("restricted", "restricted"))

    def test_confidential_cannot_see_restricted(self):
        from moderation.levels import can_access
        self.assertTrue(can_access("confidential", "confidential"))
        self.assertFalse(can_access("confidential", "restricted"))

    def test_unknown_level_raises(self):
        from moderation.levels import can_access
        with self.assertRaises(KeyError):
            can_access("god", "public")
        with self.assertRaises(KeyError):
            can_access("internal", "topsecret")


class ShouldIndexTest(TestCase):
    """Layer 1 — restricted document must skip vector store ingestion."""

    def test_restricted_skips(self):
        from moderation.levels import should_index
        self.assertFalse(should_index("restricted"))

    def test_other_levels_index(self):
        from moderation.levels import should_index
        self.assertTrue(should_index("public"))
        self.assertTrue(should_index("internal"))
        self.assertTrue(should_index("confidential"))


class RetrievalAclTest(TestCase):
    """Layer 2 — chunk-level filter applied to retrieval hits.

    `apply_acl_filter(hits, user_level)` 를 통해
    - 권한 초과 chunk 제거
    - redacted_count 반환
    - chunk metadata 의 `sensitivity` 가 없으면 'internal' 로 간주
    """

    def _mkhit(self, sensitivity=None, content="chunk"):
        meta = {}
        if sensitivity is not None:
            meta["sensitivity"] = sensitivity

        class _Doc:
            def __init__(self, content, metadata):
                self.page_content = content
                self.metadata = metadata

        return _Doc(content, meta)

    def test_internal_user_filters_confidential(self):
        from moderation.levels import apply_acl_filter
        hits = [
            self._mkhit("public", "p"),
            self._mkhit("internal", "i"),
            self._mkhit("confidential", "c"),
            self._mkhit("restricted", "r"),
        ]
        kept, redacted = apply_acl_filter(hits, "internal")
        self.assertEqual([d.page_content for d in kept], ["p", "i"])
        self.assertEqual(redacted, 2)

    def test_restricted_user_sees_all(self):
        from moderation.levels import apply_acl_filter
        hits = [
            self._mkhit("public"),
            self._mkhit("confidential"),
            self._mkhit("restricted"),
        ]
        kept, redacted = apply_acl_filter(hits, "restricted")
        self.assertEqual(len(kept), 3)
        self.assertEqual(redacted, 0)

    def test_missing_sensitivity_defaults_to_internal(self):
        from moderation.levels import apply_acl_filter
        hits = [self._mkhit(None, "x")]
        # public user cannot see internal (default)
        kept, redacted = apply_acl_filter(hits, "public")
        self.assertEqual(kept, [])
        self.assertEqual(redacted, 1)
        # internal user can
        kept, redacted = apply_acl_filter(hits, "internal")
        self.assertEqual(len(kept), 1)

    def test_empty_hits(self):
        from moderation.levels import apply_acl_filter
        kept, redacted = apply_acl_filter([], "internal")
        self.assertEqual(kept, [])
        self.assertEqual(redacted, 0)


class RetrieveModuleAclWiringTest(TestCase):
    """RetrieveModule must forward ModuleContext.user_access_level to RAGUtils."""

    def test_module_context_carries_access_level_default(self):
        from chat.pipeline.base import ModuleContext
        ctx = ModuleContext(question="q", session_id="s", user_id="u")
        self.assertEqual(ctx.user_access_level, "internal")

    def test_retrieve_module_passes_access_level(self):
        from unittest.mock import patch
        from chat.pipeline.base import ModuleContext
        from chat.pipeline.modules import RetrieveModule

        ctx = ModuleContext(
            question="q", session_id="s", user_id="u",
            user_access_level="confidential",
        )
        with patch("chat.pipeline.modules.RAGUtils.get_rag_context") as fake:
            fake.return_value = {
                "context": "", "image_paths": [], "docs": [], "redacted_count": 0,
            }
            RetrieveModule().run(ctx)
        fake.assert_called_once()
        _, kwargs = fake.call_args
        self.assertEqual(kwargs.get("user_access_level"), "confidential")

    def test_retrieve_module_surfaces_redacted_count(self):
        from unittest.mock import patch
        from chat.pipeline.base import ModuleContext
        from chat.pipeline.modules import RetrieveModule

        ctx = ModuleContext(question="q", session_id="s", user_id="u")
        with patch("chat.pipeline.modules.RAGUtils.get_rag_context") as fake:
            fake.return_value = {
                "context": "ctx", "image_paths": [], "docs": [], "redacted_count": 4,
            }
            out = RetrieveModule().run(ctx)
        self.assertEqual(out.extra["rag_metadata"]["redacted_count"], 4)


class GetRagContextRedactedCountTest(TestCase):
    """Integration — RAGUtils.get_rag_context 가 redacted_count 키를 포함해야 한다.

    실제 vector store 를 띄우지 않고, process_search_results 를 직접 호출하여
    응답 schema 만 검증한다.
    """

    def test_process_search_results_contains_redacted_count(self):
        from chat.utils import RAGUtils

        class _Doc:
            def __init__(self, content, metadata):
                self.page_content = content
                self.metadata = metadata

        docs = [
            _Doc("hi", {"sensitivity": "public"}),
            _Doc("conf", {"sensitivity": "confidential"}),
        ]
        out = RAGUtils.process_search_results(docs, user_access_level="internal")
        self.assertIn("redacted_count", out)
        self.assertEqual(out["redacted_count"], 1)
        # confidential chunk filtered out of merged context
        self.assertIn("hi", out["context"])
        self.assertNotIn("conf", out["context"])
