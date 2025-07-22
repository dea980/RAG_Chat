from django.db import models
from django.utils.timezone import now
import uuid
import random
import json

class MetaData(models.Model):
    key = models.CharField(max_length=50, primary_key=True)
    string_value = models.TextField(null=True, blank=True)
    integer_value = models.IntegerField(null=True, blank=True)
    float_value = models.FloatField(null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    json_value = models.TextField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    description = models.TextField(null=True, blank=True)
    
    def set_json(self, value):
        """Store a Python object as JSON string"""
        self.json_value = json.dumps(value)
    
    def get_json(self):
        """Retrieve a Python object from JSON string"""
        if self.json_value:
            return json.loads(self.json_value)
        return None
    
    def get_value(self):
        """Get the value in the most appropriate type"""
        if self.string_value is not None:
            return self.string_value
        elif self.integer_value is not None:
            return self.integer_value
        elif self.float_value is not None:
            return self.float_value
        elif self.boolean_value is not None:
            return self.boolean_value
        elif self.json_value is not None:
            return self.get_json()
        return None
    
    def __str__(self):
        return f"{self.key}: {self.get_value()}"


class User(models.Model):
    user_id = models.CharField(max_length=16, primary_key=True, editable=False)
    uuid = models.UUIDField(unique=True, editable=False)
    created_datetime = models.DateTimeField(auto_now_add=True)  # SQLite time is incorrect
    last_activity = models.DateTimeField(auto_now=True, null=True)  # 활동 시간 추적을 위한 필드 추가
    expired_datetime = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid.uuid4()
        if not self.user_id:
            while True:
                # Generate 4 random digits for the prefix and suffix
                prefix = f"{random.randint(0, 9999):04d}"
                suffix = f"{random.randint(0, 9999):04d}"
                user_id = f"U{prefix}0001{suffix}"
                # UserID Exist Check
                if not User.objects.filter(user_id=user_id).exists():
                    self.user_id = user_id
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"User {self.user_id}"


class RagData(models.Model):
    data_id = models.AutoField(primary_key=True)
    data_text = models.TextField()
    image_urls = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Data {self.data_id}"


class Chat(models.Model):
    question_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question_text = models.TextField()
    question_created_datetime = models.DateTimeField(auto_now_add=True)
    response_text = models.TextField(null=True, blank=True)
    data = models.ForeignKey(RagData, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Question {self.question_id} by User {self.user.user_id}"


class SearchLog(models.Model):
    search_log_id = models.AutoField(primary_key=True)
    question = models.ForeignKey(Chat, on_delete=models.CASCADE)
    data = models.ForeignKey(RagData, on_delete=models.SET_NULL, null=True, blank=True)
    searching_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Search {self.search_log_id} for Question {self.question.question_id}"
