"""Chroma sink — RawDoc 들을 벡터 스토어에 적재.

Phase 2 부터 결정론적 id 를 부여한다:
    id = sha256(source_file + section + chunk_index + content)
같은 청크는 항상 같은 id → manifest 의 chroma_ids 로 삭제·재인덱싱 가능.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Iterable

from langchain.schema import Document

from ...providers import provider_manager
from ..base import RawDoc, WriteResult

logger = logging.getLogger(__name__)

_EMBEDDING_REQUIRED_ENV = {
    "gemini": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "qwen": "QWEN_API_KEY",
}


def _check_embedding_credentials() -> None:
    """현재 EMBEDDING_PROVIDER 설정에 필요한 API key 가 있는지 확인."""
    provider = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()
    required = _EMBEDDING_REQUIRED_ENV.get(provider)
    if required and not os.getenv(required):
        raise RuntimeError(
            f"{required} is not configured (EMBEDDING_PROVIDER={provider})."
        )


def _chunk_id(chunk: RawDoc) -> str:
    """청크 content + 위치 정보로부터 결정론적 id 생성.

    같은 파일·같은 행·같은 청크는 항상 같은 id → idempotent 재인덱싱.
    파일 내용이 바뀌면 (또는 splitter 출력이 바뀌면) id 도 달라져 manifest
    의 chroma_ids 비교로 자연스레 차이가 드러난다.
    """
    h = hashlib.sha256()
    h.update(chunk.source_file.encode("utf-8"))
    h.update(b"\0")
    h.update((chunk.section or "").encode("utf-8"))
    h.update(b"\0")
    h.update(str(chunk.metadata.get("chunk_index", 0)).encode())
    h.update(b"\0")
    h.update(chunk.content.encode("utf-8"))
    return h.hexdigest()


def _to_lc_document(doc: RawDoc) -> Document:
    """RawDoc → langchain Document 변환. Chroma 는 scalar metadata 만 허용."""
    meta = {
        "source_file": doc.source_file,
        "source_type": doc.source_type,
        **doc.metadata,
    }
    flat_meta = {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}
    if doc.page is not None:
        flat_meta["page"] = doc.page
    if doc.section is not None:
        flat_meta["section"] = doc.section
    return Document(page_content=doc.content, metadata=flat_meta)


class ChromaSink:
    """RawDoc 청크들을 Chroma 컬렉션에 임베딩·저장."""

    def write(self, docs: Iterable[RawDoc]) -> WriteResult:
        """청크들을 결정론적 id 와 함께 Chroma 에 add. 같은 id 면 upsert."""
        _check_embedding_credentials()

        chunks = list(docs)
        if not chunks:
            logger.warning("ChromaSink.write: empty input — nothing to ingest")
            return WriteResult(count=0, ids=[])

        lc_docs = [_to_lc_document(c) for c in chunks]
        ids = [_chunk_id(c) for c in chunks]

        vector_store = provider_manager.get_vector_store()
        # add_documents 는 ids 인자로 결정론적 id 부여 — 같은 id 면 upsert
        # 처음 호출이면 collection 이 자동 생성된다.
        vector_store.add_documents(documents=lc_docs, ids=ids)

        try:
            count = vector_store._collection.count()
            logger.info(
                f"chroma collection size after write: {count} (added/upserted {len(lc_docs)})"
            )
        except Exception:
            logger.info(f"added/upserted {len(lc_docs)} docs to chroma")

        return WriteResult(count=len(lc_docs), ids=ids)

    def delete_ids(self, ids: list[str]) -> int:
        """저장된 청크 id 들을 컬렉션에서 제거. 삭제된 수 반환."""
        if not ids:
            return 0
        try:
            vector_store = provider_manager.get_vector_store()
            vector_store.delete(ids=ids)
            logger.info(f"deleted {len(ids)} chroma ids")
            return len(ids)
        except Exception as exc:
            logger.warning(f"delete_ids failed (collection may not exist): {exc}")
            return 0

    def reset(self) -> None:
        """컬렉션 전체 삭제 — `build_vectors --rebuild` 가 사용."""
        try:
            vector_store = provider_manager.get_vector_store()
            vector_store.delete_collection()
            logger.warning("chroma collection deleted")
        except Exception as exc:
            logger.warning(f"reset failed (collection may not exist): {exc}")
