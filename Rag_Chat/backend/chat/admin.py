from django.contrib import admin
from django.utils.html import format_html

from .models import User, Chat, SearchLog, RagData, MetaData
# 다른 앱 모델을 user detail inline 에 끌어오기 위한 import.
from moderation.models import ModerationLog
from audit.models import AuditLog


def _excerpt(text: str, limit: int = 60) -> str:
    if not text:
        return ""
    return text[:limit] + ("…" if len(text) > limit else "")


# ---------------------------------------------------------------------------
# Inlines on the User page — 한 명 직원(user_id)의 챗봇 사용 전체를 한 페이지에서 검수
# ---------------------------------------------------------------------------
class ChatInline(admin.TabularInline):
    model = Chat
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("question_id", "question_excerpt", "response_excerpt", "question_created_datetime", "data")
    readonly_fields = fields
    ordering = ("-question_created_datetime",)

    def question_excerpt(self, obj):
        return _excerpt(obj.question_text)
    question_excerpt.short_description = "질문"

    def response_excerpt(self, obj):
        return _excerpt(obj.response_text)
    response_excerpt.short_description = "응답"


class ModerationLogInline(admin.TabularInline):
    model = ModerationLog
    fk_name = "user"   # ModerationLog 는 user / chat 두 FK 보유
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("created_at", "source", "action", "detected_words", "reviewed")
    readonly_fields = ("created_at", "source", "action", "detected_words")
    ordering = ("-created_at",)


class AuditLogInline(admin.TabularInline):
    model = AuditLog
    fk_name = "user"
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("created_at", "method", "path", "status_code", "ip_address")
    readonly_fields = fields
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# User admin — 사용자 단위 "세션별 검수" 진입점
# ---------------------------------------------------------------------------
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "user_id", "role", "department", "email",
        "chat_count", "moderation_hits",
        "created_datetime", "last_activity", "expired_datetime",
    )
    list_filter = ("role", "department", "created_datetime", "expired_datetime")
    search_fields = ("user_id", "uuid", "email")
    readonly_fields = ("user_id", "uuid", "created_datetime", "last_activity")
    inlines = [ChatInline, ModerationLogInline, AuditLogInline]

    def chat_count(self, obj):
        return obj.chat_set.count()
    chat_count.short_description = "Chat 수"

    def moderation_hits(self, obj):
        n = ModerationLog.objects.filter(user=obj).count()
        if n == 0:
            return n
        return format_html('<b style="color:#dc2626">{}</b>', n)
    moderation_hits.short_description = "Moderation 발동"


# ---------------------------------------------------------------------------
# Chat admin — 시간순 흐름 / 사용자 필터
# ---------------------------------------------------------------------------
@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("question_id", "user", "question_excerpt", "response_excerpt", "question_created_datetime")
    list_filter = ("user", "question_created_datetime")
    search_fields = ("question_text", "response_text", "user__user_id")
    readonly_fields = ("question_id", "question_created_datetime")
    ordering = ("-question_created_datetime",)

    def question_excerpt(self, obj):
        return _excerpt(obj.question_text)
    question_excerpt.short_description = "질문"

    def response_excerpt(self, obj):
        return _excerpt(obj.response_text)
    response_excerpt.short_description = "응답"


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ("search_log_id", "question", "data", "searching_time")
    list_filter = ("searching_time",)
    search_fields = ("question__question_text",)


@admin.register(RagData)
class RagDataAdmin(admin.ModelAdmin):
    list_display = ("data_id", "data_text")
    search_fields = ("data_text",)


@admin.register(MetaData)
class MetaDataAdmin(admin.ModelAdmin):
    list_display = ("key", "get_value", "last_updated", "description")
    list_filter = ("last_updated",)
    search_fields = ("key", "string_value", "description")
    fieldsets = (
        (None, {"fields": ("key", "description", "last_updated")}),
        ("Values", {"fields": ("string_value", "integer_value", "float_value", "boolean_value", "json_value")}),
    )
    readonly_fields = ("last_updated",)
