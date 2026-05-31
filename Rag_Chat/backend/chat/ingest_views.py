"""Ingest layer 의 미리보기 API.

`/api/v1/triple/ingest/preview` — 텍스트(또는 업로드 파일) + splitter 설정을
받아 **임베딩·저장 없이** 청크만 잘라 돌려준다. chunk_lab Streamlit 페이지가
chunk_size 별 결과 비교에 사용.

저장이 없으므로 인증·rate-limit 가벼움. embedding API key 도 불필요.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from rest_framework import status
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .ingest import loaders  # noqa: F401 — registry 등록 트리거
from .ingest.base import RawDoc
from .ingest.pipeline import ingest_path
from .ingest.registry import loader_for, registered_extensions
from .ingest.splitters import splitter_by_name
from .ingest.splitters.recursive import RecursiveSplitter

logger = logging.getLogger(__name__)


def _resolve_splitter(name: str, chunk_size: int, chunk_overlap: int):
    """Preview 용 — 사용자가 명시한 splitter 이름·파라미터로 인스턴스 생성."""
    return splitter_by_name(name, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def _chunks_from_text(text: str, splitter) -> list[dict[str, Any]]:
    """평문 텍스트 → splitter 적용 → JSON-friendly dict list."""
    raw = RawDoc(
        content=text,
        source_file="<inline>",
        source_type="inline",
    )
    out = []
    for c in splitter.split(raw):
        out.append({
            "content": c.content,
            "length": len(c.content),
            "section": c.section,
            "chunk_index": c.metadata.get("chunk_index", 0),
        })
    return out


def _chunks_from_file(tmp_path: str, splitter) -> list[dict[str, Any]]:
    """업로드 파일 → 등록된 loader 로 RawDoc 들 → splitter."""
    loader = loader_for(tmp_path)
    if loader is None:
        raise ValueError(
            f"No loader for extension. Registered: {registered_extensions()}"
        )
    out = []
    for raw_doc in loader.load(tmp_path):
        for c in splitter.split(raw_doc):
            out.append({
                "content": c.content,
                "length": len(c.content),
                "section": c.section,
                "chunk_index": c.metadata.get("chunk_index", 0),
            })
    return out


def _ingest_uploaded_file(
    tmp_path: str, *, original_name: str,
    sensitivity: str = "internal", collection: str = "policy",
) -> int:
    """Load + split + persist an uploaded file via the unified pipeline.

    - splitter 는 `pipeline.ingest_path` 가 source_type 별 자동 dispatch
    - source_uri 는 `upload://<original_name>` 안정 키 — 같은 이름 재업로드 시
      Phase 2 manifest 가 SHA256 비교로 dedup 처리
    - collection / sensitivity 는 chunk metadata + VectorChunk 컬럼에 박힘
    - 결과: 중복 적재 차단 + 옛 버전 청크 자동 제거 + manifest 기록
    """
    source_uri = f"upload://{original_name}"
    return ingest_path(
        tmp_path,
        source_uri_override=source_uri,
        sensitivity=sensitivity,
        collection=collection,
    )


class IngestPreviewAPIView(APIView):
    """청크 미리보기 — 저장 없음, 임베딩 없음."""

    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        """text / file 둘 중 하나 + chunk_size/overlap/splitter."""
        try:
            chunk_size = int(request.data.get("chunk_size", 500))
            chunk_overlap = int(request.data.get("chunk_overlap", 100))
            splitter_name = request.data.get("splitter", "recursive")
            text = request.data.get("text", "")
            upload = request.FILES.get("file")

            if not text and not upload:
                return Response(
                    {"error": "text 또는 file 둘 중 하나는 필요합니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            splitter = _resolve_splitter(splitter_name, chunk_size, chunk_overlap)

            if upload:
                # 임시 파일에 쓰고 loader 통과 — 디스크 영구 저장 없음
                suffix = os.path.splitext(upload.name)[1] or ".txt"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    for chunk in upload.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name
                try:
                    chunks = _chunks_from_file(tmp_path, splitter)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                source_name = upload.name
            else:
                chunks = _chunks_from_text(text, splitter)
                source_name = "<inline text>"

            lengths = [c["length"] for c in chunks]
            return Response({
                "source": source_name,
                "splitter": splitter_name,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "num_chunks": len(chunks),
                "total_chars": sum(lengths),
                "min_length": min(lengths) if lengths else 0,
                "max_length": max(lengths) if lengths else 0,
                "avg_length": (sum(lengths) // len(lengths)) if lengths else 0,
                "chunks": chunks,
            })

        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.error(f"IngestPreviewAPIView error: {exc!r}", exc_info=True)
            return Response(
                {"error": "내부 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IngestUploadAPIView(APIView):
    """업로드 파일을 실제 RAG 저장소에 적재."""

    parser_classes = [MultiPartParser]

    def post(self, request):
        uploads = request.FILES.getlist("files")
        if not uploads:
            return Response(
                {"error": "files is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        collection = request.data.get("collection", "policy")
        sensitivity = request.data.get("sensitivity", "internal")

        processed = []
        failed = []

        for upload in uploads:
            suffix = os.path.splitext(upload.name)[1].lower()
            if suffix not in registered_extensions():
                failed.append({
                    "filename": upload.name,
                    "error": f"Unsupported file extension: {suffix or '(none)'}",
                })
                continue

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    for chunk in upload.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name

                chunk_count = _ingest_uploaded_file(
                    tmp_path, original_name=upload.name,
                    sensitivity=sensitivity, collection=collection,
                )
                processed.append({
                    "filename": upload.name,
                    "status": "ok" if chunk_count > 0 else "skipped",
                    "chunks": chunk_count,
                })
            except Exception as exc:
                logger.error(
                    "IngestUploadAPIView failed for %s: %r",
                    upload.name,
                    exc,
                    exc_info=True,
                )
                failed.append({"filename": upload.name, "error": str(exc)})
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        return Response(
            {"processed": processed, "failed": failed},
            status=status.HTTP_200_OK,
        )
