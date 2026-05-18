from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "method", "path", "status_code", "user", "ip_address")
    list_filter = ("method", "status_code", "action", "created_at")
    search_fields = ("path", "action", "user__user_id", "ip_address", "user_agent")
    readonly_fields = tuple(
        f.name for f in AuditLog._meta.get_fields() if not f.many_to_many and not f.one_to_many
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
