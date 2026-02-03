from rest_framework import serializers
from .models import User, Chat, RagData, SearchLog

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'uuid', 'created_datetime', 'expired_datetime']
        read_only_fields = ['user_id', 'uuid']

class RagDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = RagData
        fields = ['data_id', 'data_text', 'image_urls']

class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ['question_id', 'user', 'question_text', 'question_created_datetime', 'response_text', 'data']

class SearchLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchLog
        fields = ['search_log_id', 'question', 'data', 'searching_time']