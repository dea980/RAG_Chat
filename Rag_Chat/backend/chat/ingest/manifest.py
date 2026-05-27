"""Manifest helpers — Phase 2 dedup / 멱등성 기록.

`IngestManifest` 모델을 다루는 좁은 API. pipeline 이 이 모듈만 import 하면
중복 적재 방지와 재인덱싱 cleanup 이 동작한다. Django models 는 함수 내부에서
지연 import — Django app loading 시점 부담을 줄이기 위해서.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_READ_BLOCK = 64 * 1024  # 64KB 단위로 스트리밍 — 큰 파일에서 메모리 안전


def file_sha256(path: str) -> str:
    """파일 내용의 SHA256 hex digest. 청크 단위로 읽어 큰 파일도 안전."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(_READ_BLOCK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def source_uri_for(path: str) -> str:
    """로컬 경로를 file:// URI 로 정규화. S3 등은 그대로 통과."""
    if "://" in path:
        return path
    return "file://" + os.path.abspath(path)


def already_ingested(source_uri: str, doc_sha256: str):
    """같은 (source_uri, doc_sha256) 조합이 OK 상태로 이미 있는지 조회.

    있으면 manifest 객체 반환, 없으면 None.
    """
    from ..models import IngestManifest  # lazy — Django 준비 후 호출
    return IngestManifest.objects.filter(
        source_uri=source_uri,
        doc_sha256=doc_sha256,
        status=IngestManifest.Status.OK,
    ).first()


def previous_versions(source_uri: str, exclude_hash: str) -> list:
    """같은 source_uri 의 OK 레코드 중 hash 가 다른 것들. 정리 대상."""
    from ..models import IngestManifest
    return list(
        IngestManifest.objects.filter(
            source_uri=source_uri,
            status=IngestManifest.Status.OK,
        ).exclude(doc_sha256=exclude_hash)
    )


def record_success(
    *,
    source_uri: str,
    doc_sha256: str,
    loader: str,
    splitter: str,
    chunk_count: int,
    chroma_ids: list[str],
):
    """성공한 ingest 를 manifest 에 기록.

    같은 (source_uri, doc_sha256) 가 이미 있으면 (force 재실행, 또는 이전
    FAILED 시도 등) update — 새 행을 만들지 않아 unique 제약 충돌을 피한다.
    """
    from ..models import IngestManifest
    obj, _ = IngestManifest.objects.update_or_create(
        source_uri=source_uri,
        doc_sha256=doc_sha256,
        defaults={
            "loader": loader,
            "splitter": splitter,
            "chunk_count": chunk_count,
            "chroma_ids": list(chroma_ids),
            "status": IngestManifest.Status.OK,
            "error": "",
        },
    )
    return obj


def record_failure(
    *,
    source_uri: str,
    doc_sha256: str,
    loader: str,
    splitter: str,
    error: str,
):
    """실패한 시도를 manifest 에 기록 (재시도 추적용). 같은 키가 있으면 update."""
    from ..models import IngestManifest
    obj, _ = IngestManifest.objects.update_or_create(
        source_uri=source_uri,
        doc_sha256=doc_sha256,
        defaults={
            "loader": loader,
            "splitter": splitter,
            "chunk_count": 0,
            "chroma_ids": [],
            "status": IngestManifest.Status.FAILED,
            "error": error[:8000],  # 너무 긴 traceback 절단
        },
    )
    return obj


def mark_superseded(manifests: list) -> None:
    """이전 버전들을 SUPERSEDED 로 표시 (chroma 청크 삭제 후 호출)."""
    from ..models import IngestManifest
    ids = [m.id for m in manifests]
    if ids:
        IngestManifest.objects.filter(id__in=ids).update(
            status=IngestManifest.Status.SUPERSEDED
        )


def all_orphan_chroma_ids() -> list[str]:
    """manifest 에 기록된 모든 chroma_ids 의 합집합 — full reset 시 비교용."""
    from ..models import IngestManifest
    ids: list[str] = []
    for m in IngestManifest.objects.values_list("chroma_ids", flat=True):
        ids.extend(m or [])
    return ids
