"""C1.3 — keyword filter applied at the ingest (upload) boundary.

ingest_path receives the loader's RawDoc list. Before chunking each raw_doc's
content is scanned against INBOUND/BOTH rules under Source.UPLOAD:
- BLOCK → skip the entire doc (count toward redacted), no chunks emitted
- MASK  → rewrite raw_doc.content in place; chunks see sanitized text
- WARN  → log only, content unchanged

Tests use an in-memory loader to avoid touching disk.
"""
from __future__ import annotations

from typing import Iterable, List
from unittest.mock import patch

from django.test import TestCase

from chat.ingest.base import RawDoc, WriteResult
from moderation.models import ForbiddenWord, ModerationLog


class _FakeLoader:
    extensions = (".txt",)
    source_type = "txt"

    def __init__(self, docs: List[RawDoc]):
        self._docs = docs

    def load(self, path: str) -> Iterable[RawDoc]:
        return list(self._docs)


class _IdentitySplitter:
    def split(self, doc: RawDoc) -> Iterable[RawDoc]:
        return [doc]


class _CapturingSink:
    def __init__(self):
        self.received: list[RawDoc] = []

    def write(self, docs: Iterable[RawDoc]) -> WriteResult:
        self.received = list(docs)
        return WriteResult(count=len(self.received), ids=[f"id{i}" for i in range(len(self.received))])

    def delete_ids(self, ids: list[str]) -> int:
        return 0


def _run_ingest(loader, splitter, sink, *, sensitivity="internal"):
    """Bypass disk I/O — patch loader_for + sha + manifest helpers."""
    from chat.ingest import pipeline as p
    with patch.object(p, "loader_for", return_value=loader), \
         patch.object(p.manifest_helpers, "source_uri_for", return_value="test://x"), \
         patch.object(p.manifest_helpers, "file_sha256", return_value="sha"), \
         patch.object(p.manifest_helpers, "already_ingested", return_value=None), \
         patch.object(p.manifest_helpers, "previous_versions", return_value=[]), \
         patch.object(p.manifest_helpers, "record_success"):
        return p.ingest_path("ignored.txt", splitter=splitter, sink=sink, sensitivity=sensitivity)


class UploadBlockTest(TestCase):
    def test_block_skips_doc_and_logs(self):
        ForbiddenWord.objects.create(
            word="대외비", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.INBOUND,
        )
        loader = _FakeLoader([
            RawDoc(content="이건 대외비 문서다", source_file="x", source_type="txt"),
            RawDoc(content="clean content", source_file="x", source_type="txt"),
        ])
        sink = _CapturingSink()
        _run_ingest(loader, _IdentitySplitter(), sink)
        contents = [d.content for d in sink.received]
        self.assertEqual(contents, ["clean content"])
        self.assertTrue(
            ModerationLog.objects.filter(
                action=ModerationLog.Action.BLOCKED,
                source=ModerationLog.Source.UPLOAD,
            ).exists()
        )


class UploadMaskTest(TestCase):
    def test_mask_rewrites_content_before_chunking(self):
        ForbiddenWord.objects.create(
            word="secret", category="기밀",
            severity=ForbiddenWord.Severity.MASK,
            direction=ForbiddenWord.Direction.INBOUND,
            mask_replacement="[REDACTED]",
        )
        loader = _FakeLoader([
            RawDoc(content="the secret is out", source_file="x", source_type="txt"),
        ])
        sink = _CapturingSink()
        _run_ingest(loader, _IdentitySplitter(), sink)
        self.assertEqual(len(sink.received), 1)
        self.assertEqual(sink.received[0].content, "the [REDACTED] is out")


class UploadOutboundOnlyRuleNoOpTest(TestCase):
    def test_outbound_only_rule_does_not_fire_on_upload(self):
        ForbiddenWord.objects.create(
            word="응답어", category="응답",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.OUTBOUND,
        )
        loader = _FakeLoader([
            RawDoc(content="응답어 포함 문서", source_file="x", source_type="txt"),
        ])
        sink = _CapturingSink()
        _run_ingest(loader, _IdentitySplitter(), sink)
        # Doc passes through — outbound-only rule must not affect upload.
        self.assertEqual(len(sink.received), 1)
        self.assertEqual(sink.received[0].content, "응답어 포함 문서")


class UploadRespectsSensitivitySkipTest(TestCase):
    """Layer-1 (sensitivity restricted) takes precedence — no keyword scan needed."""

    def test_restricted_doc_skipped_before_keyword_scan(self):
        ForbiddenWord.objects.create(
            word="대외비", category="기밀",
            severity=ForbiddenWord.Severity.BLOCK,
            direction=ForbiddenWord.Direction.INBOUND,
        )
        loader = _FakeLoader([
            RawDoc(content="대외비", source_file="x", source_type="txt"),
        ])
        sink = _CapturingSink()
        # restricted → ingest returns 0 without touching the loader.
        count = _run_ingest(loader, _IdentitySplitter(), sink, sensitivity="restricted")
        self.assertEqual(count, 0)
        # No keyword log either — Layer 1 short-circuits.
        self.assertFalse(
            ModerationLog.objects.filter(source=ModerationLog.Source.UPLOAD).exists()
        )
