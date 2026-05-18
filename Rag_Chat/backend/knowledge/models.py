"""Knowledge-base models — products/services and the people who own them.

Why this app exists: sales reps were burning time tracking down "who owns
this product?" / "which department supports it?". The chatbot uses these
tables to resolve those questions deterministically (no LLM hallucination
on org structure).
"""
from django.conf import settings
from django.db import models


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
