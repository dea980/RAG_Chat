"""Build vector store — ingest layer 진입 management command.

splitter 는 `pipeline.ingest_path` 가 source_type 별로 자동 선택 (Phase 3
통합). `--rebuild` 는 manifest + chroma 컬렉션을 완전히 비우고 처음부터
다시 인덱싱한다. 기본 동작은 manifest 가 자동으로 중복을 막아 safe re-run.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from ...ingest import loaders  # noqa: F401 — registry 등록 트리거
from ...ingest.pipeline import ingest_path
from ...ingest.registry import loader_for, registered_extensions
from ...ingest.sinks.chroma import ChromaSink
from ...models import IngestManifest


class Command(BaseCommand):
    help = "Build vector store from registered source files (CSV/XLSX/PDF/...)."

    # Phase 1/3 시점: 데모용 정형 데이터. 향후 디렉토리 스캔으로 확장.
    DEFAULT_SOURCES = ("galaxy_s25_data.csv", "galaxy_s25_data.xlsx")

    def add_arguments(self, parser):
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Chroma 컬렉션과 IngestManifest 를 전부 비우고 처음부터 재인덱싱.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="manifest 의 dedup skip 을 무시하고 같은 hash 라도 다시 적재.",
        )
        parser.add_argument(
            "--splitter",
            choices=("recursive", "row", "heading", "clause"),
            default=None,
            help="모든 소스에 강제할 splitter (예: 사규 PDF 에 clause). "
            "미지정 시 source_type 기반 자동 선택.",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            f"Registered loaders for extensions: {registered_extensions()}"
        )

        sink = ChromaSink()

        if options["rebuild"]:
            self.stdout.write(self.style.WARNING(
                "--rebuild: wiping chroma collection and IngestManifest"
            ))
            sink.reset()
            deleted, _ = IngestManifest.objects.all().delete()
            self.stdout.write(f"deleted {deleted} manifest rows")

        # --splitter 가 주어지면 모든 소스에 강제, 아니면 None 으로 넘겨
        # pipeline 이 source_type 기반으로 자동 선택하게 둔다.
        forced_splitter = None
        if options.get("splitter"):
            from ...ingest.splitters import splitter_by_name
            forced_splitter = splitter_by_name(options["splitter"])
            self.stdout.write(f"forced splitter: {options['splitter']}")

        ingested = 0
        for fname in self.DEFAULT_SOURCES:
            path = os.path.join(settings.BASE_DIR, fname)
            if not os.path.exists(path):
                self.stdout.write(f"skip (not found): {path}")
                continue
            if loader_for(path) is None:
                self.stdout.write(f"skip (no loader for extension): {path}")
                continue
            ingested += ingest_path(
                path, splitter=forced_splitter, sink=sink, force=options["force"]
            )

        self.stdout.write(self.style.SUCCESS(f"Total chunks written: {ingested}"))
