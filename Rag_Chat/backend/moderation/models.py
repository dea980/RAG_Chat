"""Forbidden-word registry + audit log.

Why: the chatbot's prompts and contexts are sent to an external LLM. Until we
move to a self-hosted model, we must strip / block secrets, customer PII,
competitor mentions and other sensitive tokens *before* they leave our network.
Django Admin (/admin/moderation/) is the operator-facing review page.
"""
from django.db import models


class ForbiddenWord(models.Model):
    class Severity(models.TextChoices):
        MASK = "MASK", "마스킹 후 전송 (PII)"
        WARNING = "WARNING", "경고 후 전송 (감사 기록)"
        BLOCK = "BLOCK", "즉시 차단"

    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "사용자 입력만 (LLM으로 가기 전)"
        OUTBOUND = "OUTBOUND", "LLM 응답만"
        BOTH = "BOTH", "양방향"

    word = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=50, help_text="예: 경쟁사, 고객명, 비속어, 기밀")
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.WARNING)
    direction = models.CharField(max_length=10, choices=Direction.choices, default=Direction.BOTH)
    mask_replacement = models.CharField(
        max_length=80, default="[REDACTED]",
        help_text="severity=MASK일 때 어느 문자열로 치환할지"
    )
    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-severity", "category", "word"]

    def __str__(self) -> str:
        return f"{self.word} ({self.severity}/{self.direction})"


class ModerationLog(models.Model):
    """Every detection — kept even for MASK so reviewers can audit later."""
    class Action(models.TextChoices):
        BLOCKED = "BLOCKED", "차단됨"
        WARNED = "WARNED", "경고 기록"
        MASKED = "MASKED", "마스킹됨"

    class Source(models.TextChoices):
        INBOUND = "INBOUND", "사용자 입력"
        OUTBOUND = "OUTBOUND", "LLM 응답"

    user = models.ForeignKey(
        "chat.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="moderation_events"
    )
    chat = models.ForeignKey(
        "chat.Chat", on_delete=models.SET_NULL, null=True, blank=True, related_name="moderation_events"
    )
    detected_words = models.JSONField(default=list)
    matched_categories = models.JSONField(default=list)
    action = models.CharField(max_length=10, choices=Action.choices)
    source = models.CharField(max_length=10, choices=Source.choices)
    original_excerpt = models.TextField(blank=True, help_text="감지 시점 원문 (최대 500자)")
    sanitized_excerpt = models.TextField(blank=True, help_text="마스킹/필터 후 텍스트")
    reviewed = models.BooleanField(default=False, help_text="관리자 검수 완료 여부")
    reviewer_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["action", "reviewed"]),
        ]

    def __str__(self) -> str:
        return f"[{self.action}] {self.detected_words} @ {self.created_at:%Y-%m-%d %H:%M}"
