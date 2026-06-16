"""Seed VectorChunk from `backend/data/seed/<collection>/*` files.

각 하위 폴더 이름이 `DocCollection` enum 값이 되어 청크 `collection`
컬럼에 박힌다. 검색 시 `VectorChunk.objects.filter(collection="policy")`
형태로 namespace 분리 가능.

PgvectorSink 사용 — collection 필터가 SQL WHERE 로 동작해야 하므로 Chroma 아님.

사용:
    python manage.py seed_collections                   # 전체
    python manage.py seed_collections --only policy     # 특정 collection 만
    python manage.py seed_collections --sensitivity confidential
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ...ingest import loaders  # noqa: F401 — registry 등록 트리거
from ...ingest.pipeline import ingest_path
from ...ingest.registry import registered_extensions
from ...ingest.sinks.pgvector import PgvectorSink
from knowledge.models import DocCollection


def _seed_root() -> Path:
    return Path(settings.BASE_DIR) / "data" / "seed"


def _files_in(collection_dir: Path) -> list[Path]:
    exts = registered_extensions()
    return sorted(
        p for p in collection_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in exts
    )


class Command(BaseCommand):
    help = "Ingest seed files under data/seed/<collection>/ with collection metadata."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            action="append",
            default=None,
            help="특정 collection 만 (예: --only policy --only sales). 미지정 시 전체.",
        )
        parser.add_argument(
            "--sensitivity",
            default="internal",
            help="이번 적재의 sensitivity 라벨. 기본 internal.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="manifest dedup 우회 (재적재).",
        )

    def handle(self, *args, **options):
        valid = {c.value for c in DocCollection}
        target_filter = set(options["only"]) if options["only"] else None
        sensitivity = options["sensitivity"]
        force = options["force"]

        root = _seed_root()
        if not root.exists():
            self.stderr.write(self.style.ERROR(f"seed root missing: {root}"))
            return

        sink = PgvectorSink()
        grand_total = 0

        for collection_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            collection = collection_dir.name
            if collection not in valid:
                self.stderr.write(
                    self.style.WARNING(
                        f"skip unknown collection dir: {collection} "
                        f"(valid: {sorted(valid)})"
                    )
                )
                continue
            if target_filter and collection not in target_filter:
                continue

            files = _files_in(collection_dir)
            if not files:
                self.stdout.write(f"[{collection}] no files")
                continue

            self.stdout.write(
                self.style.NOTICE(f"[{collection}] {len(files)} file(s)")
            )
            for path in files:
                try:
                    count = ingest_path(
                        str(path),
                        sink=sink,
                        force=force,
                        sensitivity=sensitivity,
                        collection=collection,
                    )
                    grand_total += count
                    self.stdout.write(
                        f"  ✓ {path.name} → {count} chunks "
                        f"(collection={collection}, sensitivity={sensitivity})"
                    )
                except Exception as exc:
                    self.stderr.write(
                        self.style.ERROR(f"  ✗ {path.name}: {exc!r}")
                    )

        self.stdout.write(
            self.style.SUCCESS(f"Done. Total new chunks: {grand_total}")
        )
