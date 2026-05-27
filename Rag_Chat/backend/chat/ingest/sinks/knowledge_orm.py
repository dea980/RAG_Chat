"""Knowledge ORM sink — 정형 (CSV/Excel) RawDoc 들을 knowledge.Product 로 적재.

분류 3 (정형 데이터) 는 SQL/ORM 으로 정확 조회하고, 검색용 자연어 description 은
ChromaSink 가 동시에 적재하는 hybrid retrieval 의 ORM 쪽 끝.

text/PDF 같은 비정형 RawDoc 은 silently skip — Chroma sink 만 처리하게.
이 분리 덕에 pipeline 호출자가 source_type 분기를 안 해도 두 sink 를 같이
주면 알아서 자기 몫만 처리한다.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction

from knowledge.models import Department, Product

from ..base import RawDoc, WriteResult

logger = logging.getLogger(__name__)

_STRUCTURED_TYPES = {"csv", "excel"}


class KnowledgeOrmSink:
    """CSV/Excel RawDoc → knowledge.Product upsert.

    매핑 규칙:
        - name        ← metadata['fields'][name_column]  (기본 "Model")
        - description ← RawDoc.content  (loader 가 만든 "컬럼: 값" 직렬화)
        - specs       ← metadata['fields'] 전체 (name_column 제외)
        - category    ← Product.Category.PRODUCT  (고정)
        - department  ← default_department  (없으면 자동 생성)

    멱등성: `Product.name` 으로 update_or_create — 같은 name 재호출은 덮어쓰기.
    Non-structured source_type 의 RawDoc 은 무시 (ChromaSink 가 처리).
    """

    def __init__(
        self,
        *,
        default_department: str = "영업팀",
        name_column: str = "Model",
    ) -> None:
        self._default_department_name = default_department
        self._name_column = name_column

    def write(self, docs: Iterable[RawDoc]) -> WriteResult:
        """RawDoc[] → Product upsert. ChromaSink 와 동일 시그니처."""
        dept, _ = Department.objects.get_or_create(
            name=self._default_department_name,
            defaults={"description": "Auto-created by KnowledgeOrmSink"},
        )

        ids: list[str] = []
        skipped = 0

        with transaction.atomic():
            for d in docs:
                if d.source_type not in _STRUCTURED_TYPES:
                    skipped += 1
                    continue
                fields = dict(d.metadata.get("fields") or {})
                raw_name = fields.pop(self._name_column, None) or d.section or ""
                name = str(raw_name).strip()
                if not name:
                    skipped += 1
                    continue
                product, _ = Product.objects.update_or_create(
                    name=name,
                    defaults={
                        "category": Product.Category.PRODUCT,
                        "description": d.content,
                        "specs": fields,
                        "department": dept,
                        "is_active": True,
                    },
                )
                ids.append(f"product:{product.pk}")

        if skipped:
            logger.info(f"KnowledgeOrmSink: skipped {skipped} non-structured docs")
        logger.info(f"KnowledgeOrmSink: upserted {len(ids)} products in {dept.name}")
        return WriteResult(count=len(ids), ids=ids)

    def delete_ids(self, ids: list[str]) -> int:
        """`product:<pk>` 형태의 id 들을 Product 테이블에서 삭제."""
        pks: list[int] = []
        for i in ids:
            if i.startswith("product:"):
                try:
                    pks.append(int(i.removeprefix("product:")))
                except ValueError:
                    pass
        if not pks:
            return 0
        deleted, _ = Product.objects.filter(pk__in=pks).delete()
        logger.info(f"KnowledgeOrmSink: deleted {deleted} products")
        return deleted
