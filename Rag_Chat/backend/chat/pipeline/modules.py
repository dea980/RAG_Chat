"""Concrete pipeline modules for the modular RAG pipeline."""

from __future__ import annotations

import logging
import os
from typing import Dict, List

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory

from ..providers import provider_manager
from ..utils import RAGUtils
from .base import ModuleContext, PipelineModule, ModuleError

logger = logging.getLogger(__name__)


class RetrieveModule(PipelineModule):
    """Fetch RAG context and associated metadata."""

    name = "retrieve"

    def run(self, context: ModuleContext) -> ModuleContext:
        # Retrieve a BROAD candidate pool (RERANKER_TOP_N, default 20).
        # The frontend `top_k` knob caps the FINAL output via RerankModule, not
        # the retrieve breadth — narrowing here would starve the reranker.
        persona = context.extra.get("persona")

        # Escalation 사전 탐지 (키워드 기반). 매칭 시 audit log + retrieval 계속.
        # Filter 가 어차피 권한 밖 chunk 차단 — 로그는 누적 패턴 추적용.
        from ..persona import is_escalation
        escalated, detected_tiers, allowed_tiers = is_escalation(
            context.question, persona,
        )
        if escalated:
            self._log_escalation(context, persona, detected_tiers, allowed_tiers)

        try:
            rag_context = RAGUtils.get_rag_context(
                context.question,
                k=None,
                user_access_level=context.user_access_level,
                persona=persona,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ModuleError(f"Failed to retrieve context: {exc}") from exc

        context.context_text = rag_context.get("context", "")
        raw_images = rag_context.get("image_paths", [])
        images: List[str] = []
        for image in raw_images:
            if not image:
                continue
            if isinstance(image, str):
                images.extend([item.strip() for item in image.split("\n") if item.strip()])
            else:
                images.append(str(image))

        context.images = images
        context.extra["rag_metadata"] = rag_context
        # RerankModule reads this — must be set even when empty so rerank
        # knows there are no candidates and bails cleanly.
        context.extra["retrieved_docs"] = rag_context.get("docs", [])
        return context

    @staticmethod
    def _log_escalation(context, persona, detected_tiers, allowed_tiers):
        """Persist EscalationAttempt — best-effort, never raises."""
        try:
            from ..models import EscalationAttempt, User
            user = None
            if context.user_id:
                user = User.objects.filter(user_id=context.user_id).first()
            out_of_scope = [t for t in detected_tiers if t not in allowed_tiers]
            decision = (
                EscalationAttempt.Decision.BLOCKED
                if "internal_only" in out_of_scope
                else EscalationAttempt.Decision.REDIRECTED
            )
            EscalationAttempt.objects.create(
                user=user,
                from_persona=persona or "",
                requested_query=context.question[:2000],
                allowed_tiers=allowed_tiers,
                detected_tiers=detected_tiers,
                decision=decision,
            )
            logger.warning(
                f"escalation: persona={persona} detected={detected_tiers} "
                f"allowed={allowed_tiers} decision={decision}"
            )
        except Exception as exc:  # pragma: no cover - audit never breaks chat
            logger.error(f"EscalationAttempt log failed: {exc}")


class ReasoningModule(PipelineModule):
    """Generate structured reasoning from retrieved context."""

    name = "reasoning"

    def run(self, context: ModuleContext) -> ModuleContext:
        reasoning_model = provider_manager.get_reasoning_model(context.session_id)
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """목표: 사용자의 질문에 답변하는 데 필요한 핵심 근거를 간결한 bullet list로 정리하세요.
다음 규칙을 따르세요:
- 제공된 컨텍스트 안에서만 근거를 찾을 것
- 질문에 직접적으로 도움이 되지 않는 내용은 제외할 것
- 각 근거는 한 문장으로 작성할 것""",
            ),
            (
                "human",
                "Question: {question}\nContext:\n{context}",
            ),
        ])

        try:
            chain = prompt | reasoning_model | StrOutputParser()
            context.reasoning = chain.invoke(
                {
                    "question": context.question,
                    "context": context.context_text,
                }
            )
        except Exception as exc:
            raise ModuleError(f"Failed to generate reasoning: {exc}") from exc

        return context


class GenerationModule(PipelineModule):
    """Produce the final answer using reasoning and history."""

    name = "generation"

    def run(self, context: ModuleContext) -> ModuleContext:
        generation_model = provider_manager.get_generation_model(context.session_id)

        # Persona 별 답변 길이·톤·citation 형식 가이드를 system prompt 에 주입.
        from ..persona import prompt_style_for_persona
        persona_style = prompt_style_for_persona(context.extra.get("persona"))

        system_prompt = f"""당신은 영업팀을 돕는 친절한 한국어 사내 챗봇입니다.

{persona_style}
공통 규칙:
1. 질문 의도가 불분명하면 (예: '?' 한 글자, 단순 부호) 추측 금지.
   "질문 내용을 조금 더 자세히 말씀해 주세요" 처럼 명확화를 요청하세요.
2. 사용자가 명확히 묻지 않은 카탈로그 정보 (가격·스펙 등) 는 답변에 포함하지 않습니다.
   "안녕" 같은 인사에는 인사로만 답하세요.
3. 제공된 컨텍스트와 reasoning 만 근거로. 컨텍스트에 없는 내용은 추측 금지 —
   "해당 정보가 자료에 없습니다" 라고 솔직히 답하세요.
4. 정보 부족 시 어떤 정보가 더 필요한지 물어보세요."""

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                system_prompt,
            ),
            MessagesPlaceholder(variable_name="history"),
            (
                "human",
                "Question: {question}\n\nContext:\n{context}\n\nReasoning:\n{reasoning}",
            ),
        ])

        chain = prompt | generation_model | StrOutputParser()

        inputs: Dict[str, str] = {
            "question": context.question,
            "context": context.context_text,
            "reasoning": context.reasoning or "",
        }

        try:
            if context.history_handler:
                chain_with_history = RunnableWithMessageHistory(
                    chain,
                    context.history_handler,
                    input_messages_key="question",
                    history_messages_key="history",
                )
                context.response = chain_with_history.invoke(
                    inputs,
                    config={"configurable": {"session_id": context.session_id}},
                )
            else:
                context.response = chain.invoke({**inputs, "history": []})
        except Exception as exc:
            raise ModuleError(f"Failed to generate response: {exc}") from exc

        return context


class RerankModule(PipelineModule):
    """ONNX cross-encoder rerank of retrieved documents.

    Final cut size = context.extra['top_k'] (frontend knob) when set,
    else RERANKER_TOP_K env (default 3).
    """

    name = "rerank"

    def __init__(self, top_k: int | None = None) -> None:
        self.top_k_default = top_k if top_k is not None else int(os.getenv("RERANKER_TOP_K", "3"))

    def run(self, context: ModuleContext) -> ModuleContext:
        docs = context.extra.get("retrieved_docs") or []
        if not docs:
            return context

        # Per-request override from frontend knob; cap to 1..len(docs).
        req_k = context.extra.get("top_k")
        if isinstance(req_k, int) and req_k > 0:
            final_k = min(req_k, len(docs))
        else:
            final_k = min(self.top_k_default, len(docs))

        reranker = provider_manager.get_reranker()
        if reranker is None:
            # Reranker unavailable — still narrow to final_k by original order.
            top_docs = docs[:final_k]
        else:
            try:
                scores = reranker.score(context.question, [d.page_content for d in docs])
                ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)[:final_k]
                top_docs = [d for d, _ in ranked]
            except Exception as exc:
                logger.warning("Reranker scoring failed, keeping original order: %s", exc)
                top_docs = docs[:final_k]

        context.context_text = "\n\n".join(d.page_content for d in top_docs)
        context.images = [
            d.metadata["image_path"] for d in top_docs if "image_path" in d.metadata
        ]
        context.extra["retrieved_docs"] = top_docs
        return context

