"""Concrete pipeline modules for the modular RAG pipeline."""

from __future__ import annotations

from typing import Dict, List

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory

from ..providers import provider_manager
from ..utils import RAGUtils
from .base import ModuleContext, PipelineModule, ModuleError


class RetrieveModule(PipelineModule):
    """Fetch RAG context and associated metadata."""

    name = "retrieve"

    def run(self, context: ModuleContext) -> ModuleContext:
        try:
            rag_context = RAGUtils.get_rag_context(context.question)
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
        return context


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

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are a friendly Korean AI assistant. Use the provided context and
reasoning steps to craft a clear, helpful answer. If information is missing,
acknowledge it honestly.""",
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

