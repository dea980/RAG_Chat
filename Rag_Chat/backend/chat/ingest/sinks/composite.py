"""Composite sink — 여러 sink 에 한 번에 fan-out 한다.

Phase 6 hybrid retrieval 패턴: 정형 CSV/XLSX 한 줄을 ORM (정확 조회) 와
Chroma (벡터 검색) 양쪽에 동시에 기록한다. pipeline 은 단일 sink 만 받으므로
CompositeSink 로 묶어서 넘긴다.

각 자식 sink 가 자기 source_type 만 처리한다 (KnowledgeOrmSink 는 csv/excel
이외 무시, ChromaSink 는 전부 처리). 호출자는 source_type 분기를 신경 쓰지
않아도 된다.
"""
from __future__ import annotations

import logging
from typing import Iterable, Sequence

from ..base import BaseSink, RawDoc, WriteResult

logger = logging.getLogger(__name__)


class CompositeSink:
    """주어진 sink 들에 순서대로 write/delete 를 위임한다.

    write 결과는 합쳐서 단일 WriteResult 로 돌려준다. ids 는 각 sink 의 ids 를
    `<sink_name>:<id>` 형태로 prefix 해서 합치므로 delete_ids 에서 원본 sink 로
    역디스패치가 가능하다.
    """

    def __init__(self, sinks: Sequence[BaseSink]) -> None:
        if not sinks:
            raise ValueError("CompositeSink requires at least one child sink")
        self._sinks = list(sinks)

    def _prefix_for(self, sink: BaseSink) -> str:
        """`<ClassName>` → `chroma`/`knowledgeorm` 같은 안정적 접두어."""
        return type(sink).__name__.removesuffix("Sink").lower() or "sink"

    def write(self, docs: Iterable[RawDoc]) -> WriteResult:
        chunks = list(docs)  # 여러 sink 가 같은 stream 을 소비하므로 materialize
        total_count = 0
        all_ids: list[str] = []
        for sink in self._sinks:
            result = sink.write(chunks)
            prefix = self._prefix_for(sink)
            for raw_id in result.ids:
                all_ids.append(f"{prefix}:{raw_id}")
            total_count += result.count
            logger.debug(
                f"CompositeSink: {type(sink).__name__} wrote {result.count} entries"
            )
        return WriteResult(count=total_count, ids=all_ids)

    def delete_ids(self, ids: list[str]) -> int:
        """`<prefix>:<id>` 로 묶인 id 들을 원 sink 로 역디스패치."""
        by_prefix: dict[str, list[str]] = {}
        for full in ids:
            if ":" not in full:
                continue
            prefix, raw = full.split(":", 1)
            by_prefix.setdefault(prefix, []).append(raw)

        total = 0
        for sink in self._sinks:
            prefix = self._prefix_for(sink)
            raws = by_prefix.get(prefix, [])
            if raws:
                total += sink.delete_ids(raws)
        return total
