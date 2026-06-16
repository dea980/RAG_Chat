"""IngestManifest — Phase 2 ingest layer dedup/멱등성."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0005_user_department_user_email_user_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="IngestManifest",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_uri", models.CharField(max_length=512)),
                ("doc_sha256", models.CharField(max_length=64)),
                ("loader", models.CharField(max_length=32)),
                ("splitter", models.CharField(blank=True, default="", max_length=32)),
                ("chunk_count", models.IntegerField(default=0)),
                ("chroma_ids", models.JSONField(default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OK", "OK"),
                            ("FAILED", "Failed"),
                            ("SUPERSEDED", "Superseded"),
                        ],
                        default="OK",
                        max_length=16,
                    ),
                ),
                ("error", models.TextField(blank=True, default="")),
                ("ingested_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["doc_sha256"], name="chat_ingest_doc_sha_idx"
                    ),
                    models.Index(
                        fields=["source_uri"], name="chat_ingest_src_uri_idx"
                    ),
                ],
                "unique_together": {("source_uri", "doc_sha256")},
            },
        ),
    ]
