"""Migrate existing Chroma chunks to pgvector VectorChunk table.

Usage:
    python manage.py migrate_to_pgvector          # migrate all
    python manage.py migrate_to_pgvector --dry-run # preview only
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from chat.providers import provider_manager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migrate Chroma vector store data to pgvector VectorChunk table"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Preview without writing to pgvector",
        )
        parser.add_argument(
            "--batch-size", type=int, default=20,
            help="Embedding batch size (default: 20)",
        )

    def handle(self, *args, **options):
        from knowledge.models import VectorChunk

        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        # Read all docs from Chroma
        try:
            vs = provider_manager.get_vector_store()
            collection = vs._collection
        except Exception as exc:
            self.stderr.write(f"Cannot open Chroma: {exc}")
            return

        total = collection.count()
        self.stdout.write(f"Chroma collection: {total} chunks")

        if total == 0:
            self.stdout.write("Nothing to migrate.")
            return

        # Fetch all from Chroma (includes embeddings)
        data = collection.get(include=["documents", "metadatas", "embeddings"])
        ids = data["ids"]
        documents = data["documents"]
        metadatas = data["metadatas"]
        embeddings = data["embeddings"]

        self.stdout.write(f"Fetched {len(ids)} chunks from Chroma")
        has_embeddings = embeddings and embeddings[0] is not None

        if not has_embeddings:
            self.stdout.write("Chroma has no stored embeddings — will re-embed.")
            emb_model = provider_manager.get_embedding_model()

        if dry_run:
            self.stdout.write("[DRY RUN] Would migrate:")
            for i, (cid, doc, meta) in enumerate(zip(ids, documents, metadatas)):
                src = meta.get("source", meta.get("source_file", "?"))
                sens = meta.get("sensitivity", "internal")
                self.stdout.write(f"  {i+1}. {cid[:12]}… src={src} sens={sens} len={len(doc or '')}")
            return

        created = 0
        updated = 0
        for offset in range(0, len(ids), batch_size):
            batch_ids = ids[offset:offset + batch_size]
            batch_docs = documents[offset:offset + batch_size]
            batch_meta = metadatas[offset:offset + batch_size]

            if has_embeddings:
                batch_embs = embeddings[offset:offset + batch_size]
            else:
                batch_embs = emb_model.embed_documents(
                    [d or "" for d in batch_docs]
                )

            for cid, doc, meta, emb in zip(batch_ids, batch_docs, batch_meta, batch_embs):
                # Map Chroma metadata to VectorChunk fields
                source_file = meta.get("source_file", meta.get("source", ""))
                source_type = meta.get("source_type", "")
                sensitivity = meta.get("sensitivity", "internal")
                doc_sha256 = meta.get("doc_sha256", "")
                page = meta.get("page")
                section = meta.get("section", "")

                # Everything else goes to extra_metadata
                standard_keys = {
                    "source_file", "source", "source_type", "sensitivity",
                    "doc_sha256", "page", "section",
                }
                extra = {k: v for k, v in meta.items() if k not in standard_keys}

                _, is_new = VectorChunk.objects.update_or_create(
                    chunk_id=cid,
                    defaults={
                        "content": doc or "",
                        "embedding": emb,
                        "source_file": source_file,
                        "source_type": source_type,
                        "sensitivity": sensitivity,
                        "page": int(page) if page is not None else None,
                        "section": section,
                        "doc_sha256": doc_sha256,
                        "extra_metadata": extra,
                    },
                )
                if is_new:
                    created += 1
                else:
                    updated += 1

            self.stdout.write(f"  batch {offset // batch_size + 1}: processed {len(batch_ids)}")

        self.stdout.write(
            f"Done: {created} created, {updated} updated, "
            f"{VectorChunk.objects.count()} total in pgvector"
        )
