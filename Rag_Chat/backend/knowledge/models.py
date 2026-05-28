"""Knowledge-base models — products/services and the people who own them.

Why this app exists: sales reps were burning time tracking down "who owns
this product?" / "which department supports it?". The chatbot uses these
tables to resolve those questions deterministically (no LLM hallucination
on org structure).

Phase A (moderation 3-layer): adds `Sensitivity` ladder + `Document` model
so each ingested source file carries an admin-tunable classification.
"""
from django.conf import settings
from django.db import models


class Sensitivity(models.TextChoices):
    """4-rung sensitivity ladder shared by Document and User.access_level.

    Mirrors `moderation.levels.SENSITIVITY_LEVEL` (string -> integer).
    `restricted` documents are blocked from vector indexing (Layer 1).
    """

    PUBLIC = "public", "공개"
    INTERNAL = "internal", "사내 공유"
    CONFIDENTIAL = "confidential", "대외비"
    RESTRICTED = "restricted", "기밀 (인덱싱 차단)"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Contact(models.Model):
    """Person responsible for a product or service line."""
    name = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=80, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="contacts"
    )
    is_primary = models.BooleanField(default=False, help_text="대표 담당자 여부")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["department__name", "-is_primary", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.department.name})"


class Product(models.Model):
    class Category(models.TextChoices):
        PRODUCT = "PRODUCT", "제품"
        SERVICE = "SERVICE", "서비스"
        SOLUTION = "SOLUTION", "솔루션"

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.PRODUCT)
    description = models.TextField(blank=True)
    specs = models.JSONField(default=dict, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="products"
    )
    primary_contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="primary_products"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} [{self.get_category_display()}]"


class Document(models.Model):
    """Source file ingested into the vector store.

    One row per uploaded file (PDF, CSV, HWP, ...). The `sensitivity` column
    drives all four moderation boundaries — restricted skips indexing, every
    other level is replicated into chunk metadata so retrieval can filter by
    `User.access_level`.
    """

    name = models.CharField(max_length=240, help_text="원본 파일명 (확장자 포함)")
    source_uri = models.CharField(
        max_length=512, blank=True, default="",
        help_text="file:// 또는 upload:// 키 — IngestManifest 와 연결",
    )
    sensitivity = models.CharField(
        max_length=20,
        choices=Sensitivity.choices,
        default=Sensitivity.INTERNAL,
        db_index=True,
        help_text="업로드 시 부여. restricted = 벡터 스토어 진입 차단",
    )
    sensitivity_set_by = models.ForeignKey(
        "chat.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="docs_classified",
    )
    sensitivity_set_at = models.DateTimeField(auto_now=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["sensitivity"]),
            models.Index(fields=["source_uri"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.sensitivity}]"
