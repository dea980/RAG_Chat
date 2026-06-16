"""Reranker implementations for the RAG pipeline."""

__all__ = ["OnnxBgeReranker"]


def __getattr__(name: str):
    if name == "OnnxBgeReranker":
        from .onnx_bge import OnnxBgeReranker

        return OnnxBgeReranker
    raise AttributeError(name)
