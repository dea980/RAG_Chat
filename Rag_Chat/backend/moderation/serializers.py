from rest_framework import serializers

from .models import ForbiddenWord, ModerationLog


class ForbiddenWordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForbiddenWord
        fields = [
            "id", "word", "category", "severity", "direction",
            "mask_replacement", "is_active", "note",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ModerationLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default=None)

    class Meta:
        model = ModerationLog
        fields = [
            "id", "action", "source", "detected_words", "matched_categories",
            "original_excerpt", "sanitized_excerpt",
            "user", "user_email", "chat",
            "reviewed", "reviewer_note", "created_at",
        ]
        read_only_fields = fields
