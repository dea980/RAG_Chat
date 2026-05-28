from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.timezone import now
import uuid
import random
import json


class UserManager(BaseUserManager):
    """Manager for the custom AbstractBaseUser-based chat.User.

    USERNAME_FIELD = "email" — but user_id (U0000... format) remains the PK
    so existing FKs (Chat, SearchLog, Document.sensitivity_set_by, etc.)
    don't need to be rewritten.
    """

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", "ADMIN")
        extra.setdefault("access_level", "restricted")
        if extra.get("is_staff") is not True:
            raise ValueError("superuser must have is_staff=True")
        if extra.get("is_superuser") is not True:
            raise ValueError("superuser must have is_superuser=True")
        return self._create_user(email, password, **extra)

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


class User(AbstractBaseUser, PermissionsMixin):
    # Role-based access for the internal sales-team rollout.
    # Django Admin uses these to gate the moderation / knowledge pages.
    class Role(models.TextChoices):
        USER = "USER", "Employee"
        MANAGER = "MANAGER", "Middle Manager"
        ADMIN = "ADMIN", "C-Level Admin"

    user_id = models.CharField(max_length=16, primary_key=True, editable=False)
    uuid = models.UUIDField(unique=True, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    # Phase A moderation: chunk-level retrieval is gated on this ladder.
    # See moderation/levels.py — values must stay in sync with knowledge.Sensitivity.
    access_level = models.CharField(
        max_length=20,
        choices=[
            ("public", "공개"),
            ("internal", "사내 공유"),
            ("confidential", "대외비"),
            ("restricted", "기밀"),
        ],
        default="internal",
        help_text="이 레벨 이하 sensitivity 의 chunk 만 retrieve 가능",
    )
    department = models.ForeignKey(
        "knowledge.Department",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="members",
    )
    created_datetime = models.DateTimeField(auto_now_add=True)  # SQLite time is incorrect
    last_activity = models.DateTimeField(auto_now=True, null=True)  # 활동 시간 추적을 위한 필드 추가
    expired_datetime = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

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


class IngestManifest(models.Model):
    """Ingest 이력. 같은 파일을 다시 처리하면 SHA256 비교로 건너뛴다.

    (source_uri, doc_sha256) 가 unique — 같은 source 라도 내용이 바뀌면 새
    레코드가 생기고, 이전 레코드의 chroma_ids 로 옛 청크들을 정리 후 SUPERSEDED
    상태로 표시한다.
    """
    class Status(models.TextChoices):
        OK = "OK", "OK"
        FAILED = "FAILED", "Failed"
        SUPERSEDED = "SUPERSEDED", "Superseded"

    source_uri = models.CharField(max_length=512)         # 'file:///abs/path' 또는 's3://...'
    doc_sha256 = models.CharField(max_length=64)          # 파일 hex digest
    loader = models.CharField(max_length=32)              # 'csv', 'pdf', ...
    splitter = models.CharField(max_length=32, blank=True, default="")
    chunk_count = models.IntegerField(default=0)
    chroma_ids = models.JSONField(default=list)           # 사용된 chroma id 들 (delete 시 사용)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OK)
    error = models.TextField(blank=True, default="")
    ingested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("source_uri", "doc_sha256")]
        indexes = [
            models.Index(fields=["doc_sha256"], name="chat_ingest_doc_sha_idx"),
            models.Index(fields=["source_uri"], name="chat_ingest_src_uri_idx"),
        ]

    def __str__(self):
        return f"{self.source_uri} ({self.doc_sha256[:8]}) {self.status}"
