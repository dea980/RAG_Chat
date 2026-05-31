"""Build vector store — ingest layer 진입 management command.

splitter 는 `pipeline.ingest_path` 가 source_type 별로 자동 선택 (Phase 3
통합). `--rebuild` 는 manifest + chroma 컬렉션을 완전히 비우고 처음부터
다시 인덱싱한다. 기본 동작은 manifest 가 자동으로 중복을 막아 safe re-run.
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ...ingest import loaders  # noqa: F401 — registry 등록 트리거
from ...ingest.pipeline import ingest_path
from ...ingest.registry import loader_for, registered_extensions
from ...ingest.sinks.chroma import ChromaSink, infer_tier
from ...models import IngestManifest

_CORPUS_EXTS = {".csv", ".xlsx", ".md", ".html", ".htm", ".txt", ".pdf", ".docx"}


def _discover_corpus_sources():
    """data/corpus/<tier>/ 디렉토리 자동 스캔.

    파일이 떨어지면 자동으로 인덱싱 대상에 포함 — DEFAULT_SOURCES 수정 불필요.
    `infer_tier()` 가 None 반환하는 internal_only 는 ChromaSink.write 가 차단.
    """
    base = Path(settings.BASE_DIR) / "data" / "corpus"
    if not base.exists():
        return
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _CORPUS_EXTS:
            continue
        if path.name.lower() == "readme.md":
            continue
        yield str(path.relative_to(settings.BASE_DIR))


class Command(BaseCommand):
    help = "Build vector store from registered source files (CSV/XLSX/PDF/...)."

    # Phase 1/3 시점: 데모용 정형 데이터.
    # backend/ 루트 = legacy bundled CSV. data/samples/ = 카테고리별 RAG corpus
    # (handbook = 헤딩 splitter, lineup = row splitter 검증). 향후 디렉토리
    # 스캔으로 대체 예정.
    DEFAULT_SOURCES = (
        # legacy bundled (영업팀 챗봇이 SKU 25개 색상별로 사용)
        "galaxy_s25_data.csv",
        "galaxy_s25_data.xlsx",
        # samples — Galaxy S 풀스펙 (gsmarena 추출)
        "data/samples/galaxy_lineup.csv",
        "data/samples/galaxy_handbook.md",
        "data/samples/galaxy_faq.html",
        # samples — Z Fold/Flip
        "data/samples/foldable_lineup.csv",
        "data/samples/foldable_handbook.md",
        # samples — A series (mid-range volume)
        "data/samples/a_series_lineup.csv",
        "data/samples/a_series_handbook.md",
        # samples — Tab (B2B)
        "data/samples/tab_lineup.csv",
        "data/samples/tab_handbook.md",
        # samples — Buds + Watch (번들)
        "data/samples/buds_lineup.csv",
        "data/samples/watch_lineup.csv",
        "data/samples/accessories_handbook.md",
    )

    # 사규/HR 문서 — clause/heading splitter 검증용. 영업팀 챗봇에는
    # 기본 인덱싱 안 함. --include-hr 로 opt-in.
    HR_SOURCES = (
        "data/samples/annual_leave_policy.md",
        "data/samples/employee_rules.txt",
    )

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
        parser.add_argument(
            "--include-hr",
            action="store_true",
            help="HR/사규 문서도 함께 인덱싱 (annual_leave_policy, employee_rules). "
            "기본은 제품 카탈로그만.",
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

        sources = list(self.DEFAULT_SOURCES)
        if options.get("include_hr"):
            sources.extend(self.HR_SOURCES)
            self.stdout.write(f"--include-hr: HR 문서 {len(self.HR_SOURCES)}개 포함")

        # data/corpus/<tier>/ 자동 스캔. internal/* 은 infer_tier=None → 스킵.
        corpus_files = list(_discover_corpus_sources())
        if corpus_files:
            non_internal = [f for f in corpus_files if infer_tier(f) is not None]
            internal_count = len(corpus_files) - len(non_internal)
            self.stdout.write(
                f"corpus scan: {len(non_internal)} files indexable, "
                f"{internal_count} skipped (internal_only)"
            )
            sources.extend(non_internal)

        ingested = 0
        for fname in sources:
            path = os.path.join(settings.BASE_DIR, fname)
            if not os.path.exists(path):
                self.stdout.write(f"skip (not found): {path}")
                continue
            if loader_for(path) is None:
                self.stdout.write(f"skip (no loader for extension): {path}")
                continue
            tier = infer_tier(fname)
            self.stdout.write(f"ingest [{tier}] {fname}")
            ingested += ingest_path(
                path, splitter=forced_splitter, sink=sink, force=options["force"]
            )

        self.stdout.write(self.style.SUCCESS(f"Total chunks written: {ingested}"))
