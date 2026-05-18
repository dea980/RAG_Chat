"""Coarse audit trail — who did what, when, from where.

Kept separate from chat.SearchLog (that one is about retrieval traceability).
This one is about compliance: every state-changing action against the API
gets a row here so security can replay an incident.
"""
from django.db import models


class AuditLog(models.Model):
    user = models.ForeignKey(
        "chat.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events"
    )
    action = models.CharField(max_length=100, help_text="예: chat.send, knowledge.product.search")
    resource = models.CharField(max_length=100, blank=True, help_text="대상 모델 이름")
    resource_id = models.CharField(max_length=100, blank=True)
    method = models.CharField(max_length=8, blank=True)
    path = models.CharField(max_length=255, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.method or '-'}] {self.action} -> {self.status_code}"
