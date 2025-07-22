from django.contrib import admin
from .models import User, Chat, SearchLog, RagData, MetaData

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'uuid', 'created_datetime', 'expired_datetime')
    list_filter = ('created_datetime', 'expired_datetime')
    search_fields = ('user_id', 'uuid')
    readonly_fields = ('user_id', 'uuid')

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('question_id', 'user', 'question_created_datetime', 'data')
    list_filter = ('question_created_datetime', 'user')
    search_fields = ('question_text', 'response_text')

@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ('search_log_id', 'question', 'data', 'searching_time')
    list_filter = ('searching_time',)
    search_fields = ('question__question_text',)

@admin.register(RagData)
class RagDataAdmin(admin.ModelAdmin):
    list_display = ('data_id', 'data_text')
    search_fields = ('data_text',)

@admin.register(MetaData)
class MetaDataAdmin(admin.ModelAdmin):
    list_display = ('key', 'get_value', 'last_updated', 'description')
    list_filter = ('last_updated',)
    search_fields = ('key', 'string_value', 'description')
    fieldsets = (
        (None, {
            'fields': ('key', 'description', 'last_updated')
        }),
        ('Values', {
            'fields': ('string_value', 'integer_value', 'float_value', 'boolean_value', 'json_value')
        }),
    )
    readonly_fields = ('last_updated',)
