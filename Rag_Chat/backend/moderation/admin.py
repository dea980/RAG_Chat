from django.contrib import admin

from .models import ForbiddenWord, ModerationLog


@admin.register(ForbiddenWord)
class ForbiddenWordAdmin(admin.ModelAdmin):
    list_display = ("word", "category", "severity", "direction", "is_active", "updated_at")
    list_filter = ("severity", "direction", "category", "is_active")
    search_fields = ("word", "category", "note")
    list_editable = ("severity", "direction", "is_active")


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "source", "detected_words", "user", "reviewed")
    list_filter = ("action", "source", "reviewed", "created_at")
    search_fields = ("original_excerpt", "sanitized_excerpt", "user__user_id")
    readonly_fields = (
        "user", "chat", "detected_words", "matched_categories",
        "action", "source", "original_excerpt", "sanitized_excerpt", "created_at",
    )
    list_editable = ("reviewed",)
    fieldsets = (
        ("탐지 결과", {
            "fields": ("created_at", "action", "source", "detected_words", "matched_categories"),
        }),
        ("원문 vs 처리 후", {
            "fields": ("original_excerpt", "sanitized_excerpt"),
        }),
        ("관계", {
            "fields": ("user", "chat"),
        }),
        ("검수", {
            "fields": ("reviewed", "reviewer_note"),
        }),
    )
