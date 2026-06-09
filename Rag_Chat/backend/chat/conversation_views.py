"""ChatGPT-style conversation endpoints.

Endpoints:
- GET    /conversations/                 list user's conversations (newest first)
- POST   /conversations/                 create empty conversation
- GET    /conversations/<uuid>/          conv detail + messages (in order)
- PATCH  /conversations/<uuid>/          rename (title)
- DELETE /conversations/<uuid>/          soft-delete (set deleted_at)
- POST   /messages/                      send a new user message (multipart)
                                          → triggers pipeline, returns assistant msg

POST /messages/ supersedes ChatAPIView. Multipart body:
    text:             user message text (required)
    conversation_id:  UUID (optional — if omitted, new conv created)
    ingest:           '1' | '0' (default '0') — if '1', uploaded files are also
                       indexed into the vector store (permanent), otherwise they
                       live only as message attachments (ephemeral).
    files:            zero or more files (multipart)

Per-conversation LangChain history isolation: session_id = str(conversation.id).
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from moderation.filter import apply as moderate_text, BlockedByModerationError
from moderation.messages import next_steps_for
from moderation.models import ModerationLog

from .models import Attachment, Conversation, Message
from .pipeline import ModuleContext, PipelineRunner, ModuleError
from .views import RedisMessageHistory, history_session_handler

logger = logging.getLogger(__name__)

UPLOADS_ROOT = Path(settings.MEDIA_ROOT) / "uploads"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _serialize_conv(conv: Conversation, *, with_messages: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(conv.id),
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "last_message_at": conv.last_message_at.isoformat(),
        "message_count": conv.messages.filter(deleted_at__isnull=True).count(),
    }
    if with_messages:
        out["messages"] = [
            _serialize_msg(m)
            for m in conv.messages.filter(deleted_at__isnull=True).order_by("created_at")
        ]
    return out


def _serialize_msg(msg: Message) -> dict[str, Any]:
    return {
        "id": str(msg.id),
        "role": msg.role,
        "content": msg.content_text,
        "redacted_count": msg.redacted_count,
        "moderation_flags": msg.moderation_flags or {},
        "created_at": msg.created_at.isoformat(),
        "attachments": [
            {
                "id": str(a.id),
                "kind": a.kind,
                "filename": a.filename,
                "mime_type": a.mime_type,
                "size_bytes": a.size_bytes,
                "ingested": a.ingest_manifest_id is not None,
            }
            for a in msg.attachments.all()
        ],
    }


def _persist_attachment(message: Message, uploaded_file, *, ingest: bool) -> Attachment:
    """Save uploaded file to disk under media/uploads/<conv>/<msg>/<name>.

    Returns the Attachment row. If ingest=True the caller is responsible for
    pushing the file through the ingest pipeline and back-filling
    `attachment.ingest_manifest`.
    """
    conv_id = str(message.conversation_id)
    msg_id = str(message.id)
    dest_dir = UPLOADS_ROOT / conv_id / msg_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = os.path.basename(uploaded_file.name)
    dest_path = dest_dir / safe_name

    sha = hashlib.sha256()
    size = 0
    with open(dest_path, "wb") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)
            sha.update(chunk)
            size += len(chunk)

    mime = getattr(uploaded_file, "content_type", "") or ""
    kind = Attachment.Kind.IMAGE if mime.startswith("image/") else Attachment.Kind.FILE

    return Attachment.objects.create(
        message=message,
        kind=kind,
        filename=safe_name,
        mime_type=mime,
        size_bytes=size,
        storage_path=str(dest_path.relative_to(settings.MEDIA_ROOT)),
        sha256=sha.hexdigest(),
    )


def _resolve_conversation(
    request, conversation_id: str | None, first_text: str
) -> Conversation:
    """Get-or-create conversation owned by request.user."""
    if conversation_id:
        return get_object_or_404(
            Conversation,
            id=conversation_id,
            user=request.user,
            deleted_at__isnull=True,
        )
    title = (first_text or "").strip()[:30] or "(new conversation)"
    return Conversation.objects.create(user=request.user, title=title)


# ----------------------------------------------------------------------------
# Conversation CRUD
# ----------------------------------------------------------------------------


class ConversationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.GET.get("limit", 50)), 200)
        qs = (
            Conversation.objects
            .filter(user=request.user, deleted_at__isnull=True)
            .order_by("-last_message_at")[:limit]
        )
        return Response({"items": [_serialize_conv(c) for c in qs]})

    def post(self, request):
        title = (request.data.get("title") or "").strip()[:30] or "(new conversation)"
        conv = Conversation.objects.create(user=request.user, title=title)
        return Response(_serialize_conv(conv), status=status.HTTP_201_CREATED)


class ConversationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_owned(self, request, conv_id):
        return get_object_or_404(
            Conversation,
            id=conv_id,
            user=request.user,
            deleted_at__isnull=True,
        )

    def get(self, request, conv_id):
        conv = self._get_owned(request, conv_id)
        return Response(_serialize_conv(conv, with_messages=True))

    def patch(self, request, conv_id):
        conv = self._get_owned(request, conv_id)
        new_title = (request.data.get("title") or "").strip()[:120]
        if new_title:
            conv.title = new_title
            conv.save(update_fields=["title"])
        return Response(_serialize_conv(conv))

    def delete(self, request, conv_id):
        conv = self._get_owned(request, conv_id)
        conv.deleted_at = timezone.now()
        conv.save(update_fields=["deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----------------------------------------------------------------------------
# Message create — primary chat endpoint
# ----------------------------------------------------------------------------


class MessageCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response(
                {"error": "text is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_obj = request.user
        conv = _resolve_conversation(
            request, request.data.get("conversation_id"), text
        )

        # Inbound moderation
        try:
            mod_in = moderate_text(
                text, source=ModerationLog.Source.INBOUND, user=user_obj,
            )
        except BlockedByModerationError as exc:
            return Response(
                {
                    "error": "요청에 차단된 단어가 포함되어 있습니다.",
                    "blocked_words": exc.words,
                    "categories": exc.categories,
                    "next_steps": next_steps_for(exc.categories),
                    "conversation_id": str(conv.id),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        sanitized = mod_in.sanitized

        # User Message
        user_msg = Message.objects.create(
            conversation=conv,
            role=Message.Role.USER,
            content_text=sanitized,
            moderation_flags={"inbound": getattr(mod_in, "matched_words", []) or []},
        )

        # Attachments + (optional) ingest
        ingest_flag = str(request.data.get("ingest", "0")).lower() in ("1", "true", "yes")
        uploaded = request.FILES.getlist("files")
        for uf in uploaded:
            att = _persist_attachment(user_msg, uf, ingest=ingest_flag)
            if ingest_flag:
                try:
                    from .ingest.pipeline import ingest_path
                    abs_path = Path(settings.MEDIA_ROOT) / att.storage_path
                    ingest_path(
                        str(abs_path),
                        source_uri_override=f"upload://{att.filename}",
                        sensitivity=getattr(user_obj, "access_level", "internal"),
                    )
                except Exception as exc:
                    logger.error(f"attachment ingest failed: {exc!r}")
            # Refresh manifest FK if ingest created one with matching sha
            if ingest_flag:
                try:
                    from .models import IngestManifest
                    manifest = (
                        IngestManifest.objects
                        .filter(doc_sha256=att.sha256, status="OK")
                        .order_by("-ingested_at").first()
                    )
                    if manifest:
                        att.ingest_manifest = manifest
                        att.save(update_fields=["ingest_manifest"])
                except Exception:
                    pass

        # ---- Tunable knobs (per-request) ----
        def _int_form(name: str, default: int, lo: int, hi: int) -> int:
            try:
                v = int(request.data.get(name, default))
            except (TypeError, ValueError):
                v = default
            return max(lo, min(hi, v))

        def _bool_form(name: str, default: bool) -> bool:
            raw = str(request.data.get(name, default)).lower()
            return raw in ("1", "true", "yes", "on")

        top_k = _int_form("top_k", 5, 1, 20)
        history_turns = _int_form("history_turns", 5, 0, 20)
        use_reasoning = _bool_form("use_reasoning", False)
        # history_turns counts user+assistant pairs → message limit = 2 × turns
        history_limit = history_turns * 2

        # Pipeline — same as ChatAPIView but session_id = conv UUID (per-conv history)
        session_id = str(conv.id)

        def _handler(sid: str):
            return history_session_handler(sid, history_limit=history_limit)

        history = _handler(session_id)
        ctx = ModuleContext(
            question=sanitized,
            session_id=session_id,
            user_id=user_obj.user_id,
            history_handler=_handler,
            history=history,
            user_access_level=getattr(user_obj, "access_level", "internal") or "internal",
        )
        ctx.extra["top_k"] = top_k
        # Persona × audience_tier ACL — RetrieveModule reads this.
        ctx.extra["persona"] = getattr(user_obj, "persona", None)

        steps: list[dict] = [{"type": "retrieve"}, {"type": "rerank"}]
        if use_reasoning:
            steps.append({"type": "reasoning"})
        steps.append({"type": "generation"})
        pipeline = PipelineRunner(steps)
        try:
            ctx = pipeline.run(ctx)
        except ModuleError as exc:
            logger.error(f"pipeline error: {exc!r}")
            return Response(
                {"error": "컨텍스트 생성 중 오류가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        rag_metadata = ctx.extra.get("rag_metadata", {})
        response_text = ctx.response or ""

        # Outbound moderation
        try:
            mod_out = moderate_text(
                response_text,
                source=ModerationLog.Source.OUTBOUND,
                user=user_obj,
            )
            response_text = mod_out.sanitized
        except BlockedByModerationError:
            response_text = (
                "응답에 차단된 내용이 포함되어 표시할 수 없습니다. "
                "관리자에게 문의하세요."
            )

        # Assistant Message
        asst_msg = Message.objects.create(
            conversation=conv,
            role=Message.Role.ASSISTANT,
            content_text=response_text,
            redacted_count=rag_metadata.get("redacted_count", 0),
            moderation_flags={
                "outbound": getattr(mod_out, "matched_words", []) if 'mod_out' in dir() else [],
                "retrieval_redacted": rag_metadata.get("redacted_count", 0),
            },
        )

        # Bump conv timestamp
        conv.last_message_at = timezone.now()
        if not conv.title or conv.title == "(new conversation)":
            conv.title = sanitized[:30]
        conv.save(update_fields=["last_message_at", "title"])

        return Response(
            {
                "conversation_id": str(conv.id),
                "user_message": _serialize_msg(user_msg),
                "assistant_message": _serialize_msg(asst_msg),
                "title": conv.title,
            },
            status=status.HTTP_201_CREATED,
        )
