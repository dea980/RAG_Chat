"""Run intrinsic embedding evaluation from CLI.

Example::

    DJANGO_SETTINGS_MODULE=triple_chat_pjt.settings \\
        python manage.py embedding_eval \\
            --dataset korsts-dev \\
            --models bge-m3,gemini \\
            --limit 200
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from chat.embedding_eval import DATASETS, evaluate, list_datasets
from chat.embedding_views import EMBEDDING_REGISTRY


class Command(BaseCommand):
    help = "Evaluate embedding models on KorSTS/KorNLI/curated pair datasets"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            required=True,
            choices=list(DATASETS.keys()),
            help="평가 데이터셋",
        )
        parser.add_argument(
            "--models",
            required=True,
            help="콤마 구분 모델 키 (예: bge-m3,gemini,e5-large)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="평가 쌍 상한 (디버깅용; 기본 None=전체)",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="JSON 으로 stdout 출력 (기본은 사람용 표)",
        )

    def handle(self, *args, **opts):
        model_keys = [m.strip() for m in opts["models"].split(",") if m.strip()]
        if not model_keys:
            raise CommandError("--models 비어 있음")
        unknown = [m for m in model_keys if m not in EMBEDDING_REGISTRY]
        if unknown:
            raise CommandError(
                f"미등록 모델: {unknown}. 사용 가능: {list(EMBEDDING_REGISTRY)}"
            )

        result = evaluate(opts["dataset"], model_keys, limit=opts["limit"])

        if opts["json"]:
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
            return

        meta = result.get("dataset_meta") or {}
        self.stdout.write(
            f"\n=== {result['dataset']} ({meta.get('label', '')}) — "
            f"{result['pair_count']} pairs ===\n"
        )

        for key, m in result["results"].items():
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n[{key}]"))
            if "error" in m:
                self.stdout.write(self.style.ERROR(f"  ERROR: {m['error']}"))
                continue
            self.stdout.write(f"  label    : {m['label']}")
            self.stdout.write(f"  kind     : {m['kind']}")
            for stat in ("pearson", "spearman", "separation", "separation_hard"):
                if stat in m:
                    self.stdout.write(f"  {stat:14}: {m[stat]:+.4f}")
            self.stdout.write("  bucket_means:")
            for bucket, val in m.get("bucket_means", {}).items():
                cnt = m.get("bucket_counts", {}).get(bucket, 0)
                self.stdout.write(f"    {bucket:14} {val:+.4f}  (n={cnt})")

            errors = m.get("top_errors") or []
            if errors:
                self.stdout.write("  worst pairs (max disagreement):")
                for e in errors[:5]:
                    self.stdout.write(
                        f"    err={e['err']:.3f} bucket={e['bucket']:<14}"
                        f" score={e['score']:+.3f} label={e['label']}"
                    )
                    self.stdout.write(f"      t1: {e['text1']}")
                    self.stdout.write(f"      t2: {e['text2']}")
