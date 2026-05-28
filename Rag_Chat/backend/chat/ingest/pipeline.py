"""Ingest 파이프라인 — source → manifest 체크 → loader → splitter → sink.

Phase 2 부터 manifest 가 결합되어:
- 같은 SHA256 은 자동 skip
- 같은 source_uri 의 옛 버전은 chroma 청크 삭제 후 SUPERSEDED 표시
- 실패도 FAILED 로 기록되어 재시도 추적 가능

Phase 3 통합으로 splitter / sink 가 optional — 기본값은
`default_splitter_for(source_type)` + `ChromaSink()`. CLI/Upload/Celery 가
같은 dispatch 로직 공유.
"""
from __future__ import annotations

import logging
from typing import Iterable

from . import manifest as manifest_helpers
from .base import BaseSink, BaseSplitter, RawDoc
from .registry import loader_for

logger = logging.getLogger(__name__)


def _splitter_name(splitter: BaseSplitter) -> str:
    """클래스 이름에서 'Splitter' 접미사 떼서 manifest 저장용 이름 생성."""
    return type(splitter).__name__.replace("Splitter", "").lower() or "unknown"


def ingest_path(
    path: str,
    splitter: BaseSplitter | None = None,
    sink: BaseSink | None = None,
    *,
    force: bool = False,
    source_uri_override: str | None = None,
    sensitivity: str = "internal",
) -> int:
    """파일 1개를 ingest. 기록된 청크 수 반환 (skip 되면 0).

    Args:
        path: 디스크 파일 경로 (또는 임시 파일).
        splitter: 미지정 시 loader.source_type 에 따라 자동 선택.
        sink: 미지정 시 ChromaSink() 기본.
        force: True 면 manifest 의 skip 분기를 우회.
        source_uri_override: 임시 파일 경로 대신 안정 키를 manifest 에 기록
            (Upload API 가 `upload://<filename>` 같은 키로 dedup 가능하게).

    단계:
        1) loader 결정 (registry)
        2) splitter/sink 기본값 채우기 + SHA256 계산 → manifest 조회
        3) 같은 source_uri 의 옛 hash 청크는 sink 에서 삭제
        4) loader.load() → splitter.split() → sink.write()
        5) manifest 에 성공/실패 기록
    """
    # Layer 1 — restricted documents never enter the vector store.
    # See moderation/levels.py and 2026-05-28-moderation-architecture spec §5.1.
    from moderation.levels import should_index
    if not should_index(sensitivity):
        logger.info(
            f"skip (restricted): {path} — sensitivity={sensitivity} blocked from indexing"
        )
        return 0

    loader = loader_for(path)
    if loader is None:
        raise ValueError(f"No loader registered for: {path}")

    # Phase 3 통합 — splitter / sink 미지정 시 source_type 기반 기본값.
    if splitter is None:
        from .splitters import default_splitter_for
        splitter = default_splitter_for(getattr(loader, "source_type", ""))
    if sink is None:
        from .sinks.chroma import ChromaSink
        sink = ChromaSink()

    source_uri = source_uri_override or manifest_helpers.source_uri_for(path)
    doc_sha = manifest_helpers.file_sha256(path)
    loader_name = getattr(loader, "source_type", type(loader).__name__)
    splitter_name = _splitter_name(splitter)

    # 1) 이미 같은 hash 로 OK 인 ingest 가 있으면 skip
    if not force:
        existing = manifest_helpers.already_ingested(source_uri, doc_sha)
        if existing:
            logger.info(
                f"skip (already ingested): {source_uri} sha256={doc_sha[:8]} chunks={existing.chunk_count}"
            )
            return 0

    # 2) 같은 source 의 옛 버전 정리 — chroma 청크 제거 + manifest SUPERSEDED 처리
    prev = manifest_helpers.previous_versions(source_uri, exclude_hash=doc_sha)
    if prev:
        old_ids: list[str] = []
        for m in prev:
            old_ids.extend(m.chroma_ids or [])
        if old_ids:
            sink.delete_ids(old_ids)
        manifest_helpers.mark_superseded(prev)
        logger.info(f"superseded {len(prev)} prior version(s) of {source_uri}")

    # 3) 실제 적재
    try:
        raw_docs = list(loader.load(path))
        chunks: list[RawDoc] = []
        for d in raw_docs:
            # 모든 청크에 doc_sha256 메타데이터를 자동 부여 — Chroma 에서도 추적 가능
            d.metadata.setdefault("doc_sha256", doc_sha)
            # Layer 2 — chunk metadata 의 sensitivity 가 retrieval 필터의 기준.
            d.metadata.setdefault("sensitivity", sensitivity)
            for chunk in splitter.split(d):
                chunk.metadata.setdefault("sensitivity", sensitivity)
                chunks.append(chunk)

        result = sink.write(chunks)
    except Exception as exc:
        manifest_helpers.record_failure(
            source_uri=source_uri,
            doc_sha256=doc_sha,
            loader=loader_name,
            splitter=splitter_name,
            error=repr(exc),
        )
        logger.error(f"ingest failed: {source_uri}: {exc!r}")
        raise

    # 4) manifest 기록
    manifest_helpers.record_success(
        source_uri=source_uri,
        doc_sha256=doc_sha,
        loader=loader_name,
        splitter=splitter_name,
        chunk_count=result.count,
        chroma_ids=result.ids,
    )
    logger.info(
        f"ingested {source_uri}: {len(raw_docs)} docs → {result.count} chunks "
        f"(sha256={doc_sha[:8]}, splitter={splitter_name})"
    )
    return result.count


def ingest_paths(
    paths: Iterable[str],
    splitter: BaseSplitter | None = None,
    sink: BaseSink | None = None,
    *,
    force: bool = False,
    sensitivity: str = "internal",
) -> int:
    """여러 파일을 순차 ingest. 총 청크 수 반환. 개별 실패는 건너뜀."""
    total = 0
    for path in paths:
        try:
            total += ingest_path(path, splitter, sink, force=force, sensitivity=sensitivity)
        except ValueError as exc:
            # registry 에 없는 확장자 — 단일 파일 실패가 전체를 막지 않게
            logger.warning(f"skipped {path}: {exc}")
        except Exception as exc:
            logger.error(f"ingest_path raised for {path}: {exc!r}")
    return total
