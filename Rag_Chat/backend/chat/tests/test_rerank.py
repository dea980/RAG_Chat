"""Unit tests for RerankModule."""
from unittest.mock import MagicMock, patch

from langchain.schema import Document

from chat.pipeline.base import ModuleContext


def _ctx(docs):
    c = ModuleContext(question="q", session_id="s", user_id="u")
    c.extra["retrieved_docs"] = docs
    c.context_text = "\n".join(d.page_content for d in docs)
    c.images = [d.metadata["image_path"] for d in docs if "image_path" in d.metadata]
    return c


def _docs():
    return [
        Document(page_content="A", metadata={"image_path": "a.png"}),
        Document(page_content="B", metadata={}),
        Document(page_content="C", metadata={"image_path": "c.png"}),
        Document(page_content="D", metadata={}),
    ]


@patch("chat.pipeline.modules.provider_manager")
def test_rerank_keeps_top_k_in_score_order(mock_pm):
    from chat.pipeline.modules import RerankModule

    reranker = MagicMock()
    reranker.score.return_value = [0.1, 0.9, 0.2, 0.8]  # B and D are top
    mock_pm.get_reranker.return_value = reranker

    module = RerankModule(top_k=2)
    out = module.run(_ctx(_docs()))

    assert out.context_text == "B\n\nD"
    assert out.images == []  # B and D have no image_path


@patch("chat.pipeline.modules.provider_manager")
def test_rerank_passthrough_when_reranker_is_none(mock_pm):
    from chat.pipeline.modules import RerankModule

    mock_pm.get_reranker.return_value = None
    module = RerankModule(top_k=2)
    ctx = _ctx(_docs())
    original_text = ctx.context_text

    out = module.run(ctx)

    assert out.context_text == original_text


@patch("chat.pipeline.modules.provider_manager")
def test_rerank_passthrough_when_no_retrieved_docs(mock_pm):
    from chat.pipeline.modules import RerankModule

    reranker = MagicMock()
    mock_pm.get_reranker.return_value = reranker
    module = RerankModule(top_k=2)

    ctx = ModuleContext(question="q", session_id="s", user_id="u")
    ctx.context_text = "preset"
    out = module.run(ctx)

    assert out.context_text == "preset"
    reranker.score.assert_not_called()


@patch("chat.pipeline.modules.provider_manager")
def test_rerank_falls_back_on_scoring_failure(mock_pm):
    from chat.pipeline.modules import RerankModule

    reranker = MagicMock()
    reranker.score.side_effect = RuntimeError("boom")
    mock_pm.get_reranker.return_value = reranker

    module = RerankModule(top_k=2)
    ctx = _ctx(_docs())
    original_text = ctx.context_text

    out = module.run(ctx)

    assert out.context_text == original_text
