"""Management command replacing the Celery check_session_expiry task.

Usage:
    python manage.py cleanup_sessions          # one-shot
    crontab:  * * * * * cd /app && python manage.py cleanup_sessions
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from chat.models import User
from chat.redis_manager import RedisMessageManager, session_expiry_threshold

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Clean up expired sessions in Redis and database"

    def handle(self, *args, **options):
        try:
            redis_manager = RedisMessageManager()
        except Exception as exc:
            self.stderr.write(f"Redis unavailable: {exc}")
            return

        processed_count = 0
        active_sessions = redis_manager.get_active_sessions()
        self.stdout.write(f"Active Redis sessions: {len(active_sessions)}")

        expiry_threshold = session_expiry_threshold()

        expired_users = User.objects.filter(
            expired_datetime__isnull=True,
            last_activity__lt=expiry_threshold,
        )
        self.stdout.write(f"Expired users in DB: {expired_users.count()}")

        for user in expired_users:
            try:
                session_uuid = str(user.uuid)
                if session_uuid in active_sessions:
                    redis_manager.end_session(session_uuid)

                redis_manager.clear_messages(session_uuid)

                user.expired_datetime = timezone.now()
                user.save(update_fields=["expired_datetime"])
                processed_count += 1
            except Exception as exc:
                logger.error(f"Error processing user {user.uuid}: {exc}")
                continue

        # Orphaned Redis sessions
        for session_uuid in active_sessions:
            try:
                user = User.objects.get(uuid=session_uuid)
                if user.expired_datetime:
                    redis_manager.end_session(session_uuid)
                    processed_count += 1
            except User.DoesNotExist:
                redis_manager.end_session(session_uuid)
                processed_count += 1

        # Purge users expired > 30 days
        old_threshold = timezone.now() - timedelta(days=30)
        old_count, _ = User.objects.filter(
            expired_datetime__lt=old_threshold,
        ).delete()

        if old_count:
            self.stdout.write(f"Purged {old_count} users expired >30 days")

        self.stdout.write(f"Processed {processed_count} sessions")
