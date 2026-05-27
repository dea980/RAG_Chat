"""Sink 모듈 — RawDoc 들의 저장소.

- chroma.py        : 벡터 스토어 (semantic / 근사 검색)
- knowledge_orm.py : Product/Department ORM (정확 조회, Phase 6)
- composite.py     : 여러 sink 에 fan-out (hybrid retrieval, Phase 6)
"""

from .chroma import ChromaSink
from .composite import CompositeSink
from .knowledge_orm import KnowledgeOrmSink

__all__ = ["ChromaSink", "CompositeSink", "KnowledgeOrmSink"]
