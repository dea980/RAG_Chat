"""pgvector sink — RawDoc 들을 PostgreSQL VectorChunk 테이블에 적재.

ChromaSink 과 동일한 BaseSink 프로토콜을 따른다:
- write(docs) → WriteResult(count, ids)
- delete_ids(ids) → int

차이점: 임베딩 + 메타데이터가 PostgreSQL 에 저장되므로
ACL 필터를 SQL WHERE 로 처리할 수 있다.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Iterable

from ..base import RawDoc, WriteResult

logger = logging.getLogger(__name__)


def _chunk_id(chunk: RawDoc) -> str:
    """ChromaSink 과 동일한 결정론적 id 생성."""
    h = hashlib.sha256()
    h.update(chunk.source_file.encode("utf-8"))
    h.update(b"\0")
    h.update((chunk.section or "").encode("utf-8"))
    h.update(b"\0")
    h.update(str(chunk.metadata.get("chunk_index", 0)).encode())
    h.update(b"\0")
    h.update(chunk.content.encode("utf-8"))
    return h.hexdigest()


class PgvectorSink:
    """RawDoc 청크들을 PostgreSQL VectorChunk 테이블에 임베딩·저장."""

    def write(self, docs: Iterable[RawDoc]) -> WriteResult:
        from knowledge.models import VectorChunk
        from ...providers import provider_manager

        chunks = list(docs)
        if not chunks:
            logger.warning("PgvectorSink.write: empty input")
            return WriteResult(count=0, ids=[])

        # Batch embed
        embeddings_model = provider_manager.get_embedding_model()
        texts = [c.content for c in chunks]
        embeddings = embeddings_model.embed_documents(texts)

        ids = [_chunk_id(c) for c in chunks]

        # Upsert each chunk
        created = 0
        for chunk, emb, chunk_id in zip(chunks, embeddings, ids):
            # Collect extra metadata (non-standard fields)
            standard_keys = {
                "sensitivity", "collection", "doc_sha256", "chunk_index",
                "source_file", "source_type", "page", "section",
            }
            extra = {k: v for k, v in chunk.metadata.items() if k not in standard_keys}

            _, is_new = VectorChunk.objects.update_or_create(
                chunk_id=chunk_id,
                defaults={
                    "content": chunk.content,
                    "embedding": emb,
                    "source_file": chunk.source_file,
                    "source_type": chunk.source_type,
                    "sensitivity": chunk.metadata.get("sensitivity", "internal"),
                    "collection": chunk.metadata.get("collection", "policy"),
                    "page": chunk.page,
                    "section": chunk.section or "",
                    "doc_sha256": chunk.metadata.get("doc_sha256", ""),
                    "extra_metadata": extra,
                },
            )
            if is_new:
                created += 1

        logger.info(
            f"pgvector: {created} new, {len(chunks) - created} updated "
            f"(total {len(chunks)} chunks)"
        )
        return WriteResult(count=len(chunks), ids=ids)

    def delete_ids(self, ids: list[str]) -> int:
        if not ids:
            return 0
        from knowledge.models import VectorChunk

        deleted, _ = VectorChunk.objects.filter(chunk_id__in=ids).delete()
        logger.info(f"pgvector: deleted {deleted} chunks")
        return deleted

    def reset(self) -> None:
        from knowledge.models import VectorChunk

        count = VectorChunk.objects.count()
        VectorChunk.objects.all().delete()
        logger.warning(f"pgvector: deleted all {count} chunks")
