"""Stage 0 retrieval evaluation — production Chroma 인덱스 대상.

기존 ``embedding_eval`` 는 intrinsic pair (KorSTS/curated) 측정이고,
``chat/tests/evals/run_embedding_ab.py`` 는 FAISS in-memory A/B 다.

이 명령은 production ``provider_manager.get_vector_store()`` 에 대고
labeled JSONL 질문셋을 돌려 MRR / Recall@k 를 산출한다 — IR 개선 plan
Stage 0~5 의 baseline·재측정용.

Usage::

    python manage.py retrieval_eval \\
        --dataset chat/tests/evals/dataset_sales_full.jsonl \\
        --k 5 \\
        --report-path docs/reports/2026-05-29-ir-baseline.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chat.providers import provider_manager
from chat.tests.evals.eval_core import (
    keyword_recall,
    load_questions,
    mrr_score,
)


class Command(BaseCommand):
    help = "Retrieval eval against production Chroma store (MRR, Recall@k)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            required=True,
            help="JSONL path. expected_keywords=[] 인 질문은 N/A 버킷으로 분리.",
        )
        parser.add_argument("--k", type=int, default=5, help="top-k retrieval")
        parser.add_argument(
            "--report-path",
            default=None,
            help="JSON 보고서 출력 경로. 미지정 시 stdout.",
        )

    def handle(self, *args, **opts):
        dataset_path = Path(opts["dataset"])
        if not dataset_path.is_absolute():
            dataset_path = Path(settings.BASE_DIR) / dataset_path
        if not dataset_path.exists():
            raise CommandError(f"dataset not found: {dataset_path}")

        questions = load_questions(dataset_path)
        k = opts["k"]
        self.stdout.write(f"Loaded {len(questions)} questions from {dataset_path.name}")

        vs = provider_manager.get_vector_store()
        try:
            chunk_count = vs._collection.count()
        except Exception:
            chunk_count = -1
        self.stdout.write(f"Chroma collection size: {chunk_count}")

        per_question = []
        labeled_mrr = []
        labeled_recall = []
        na_queries = []

        t_start = time.perf_counter()
        for q in questions:
            hits = vs.similarity_search(q.question, k=k)
            ranked_texts = [h.page_content for h in hits]
            sources = [h.metadata.get("source_file", "?").split("/")[-1] for h in hits]

            entry = {
                "id": q.id,
                "question": q.question,
                "scenario": q.scenario,
                "expected_keywords": q.expected_keywords,
                "top_sources": sources,
                "top_previews": [t[:80].replace("\n", " ") for t in ranked_texts],
            }

            if not q.expected_keywords:
                na_queries.append(entry)
                entry["bucket"] = "n/a"
            else:
                mrr = mrr_score(q, ranked_texts)
                top1_recall = keyword_recall(q, ranked_texts[0]) if ranked_texts else 0.0
                topk_recall = max(
                    (keyword_recall(q, t) for t in ranked_texts), default=0.0
                )
                entry.update({
                    "bucket": "labeled",
                    "mrr": round(mrr, 4),
                    "recall_top1": round(top1_recall, 4),
                    f"recall_top{k}": round(topk_recall, 4),
                })
                labeled_mrr.append(mrr)
                labeled_recall.append(topk_recall)

            per_question.append(entry)

        elapsed = time.perf_counter() - t_start

        summary = {
            "dataset": dataset_path.name,
            "k": k,
            "chunk_count": chunk_count,
            "question_total": len(questions),
            "labeled_count": len(labeled_mrr),
            "na_count": len(na_queries),
            "elapsed_seconds": round(elapsed, 2),
            "metrics": {
                "mrr_mean": round(_mean(labeled_mrr), 4),
                f"recall_top{k}_mean": round(_mean(labeled_recall), 4),
            },
        }

        report = {"summary": summary, "per_question": per_question}

        # Console summary
        self.stdout.write(self.style.SUCCESS(
            f"\n=== Retrieval Eval ({dataset_path.name}) ==="
        ))
        self.stdout.write(
            f"labeled: {summary['labeled_count']}, "
            f"N/A: {summary['na_count']}, "
            f"chunks: {chunk_count}, k={k}"
        )
        self.stdout.write(
            f"  MRR                 : {summary['metrics']['mrr_mean']:.4f}"
        )
        self.stdout.write(
            f"  Recall@{k}            : {summary['metrics'][f'recall_top{k}_mean']:.4f}"
        )
        self.stdout.write(f"  elapsed             : {elapsed:.2f}s")

        # Per-question weakest
        labeled_entries = [e for e in per_question if e.get("bucket") == "labeled"]
        worst = sorted(labeled_entries, key=lambda e: e["mrr"])[:5]
        if worst:
            self.stdout.write(self.style.WARNING("\nWorst 5 (lowest MRR):"))
            for w in worst:
                self.stdout.write(
                    f"  [{w['id']}] mrr={w['mrr']:.3f} — {w['question'][:60]}"
                )
                self.stdout.write(
                    f"      top sources: {', '.join(w['top_sources'][:3])}"
                )

        # Persist JSON
        report_path = opts.get("report_path")
        if report_path:
            out_path = Path(report_path)
            if not out_path.is_absolute():
                out_path = Path(settings.BASE_DIR) / out_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.stdout.write(self.style.SUCCESS(f"\nreport: {out_path}"))


def _mean(values):
    return sum(values) / len(values) if values else 0.0
